"""Opt-in, one-turn Codex drafting followed by separately approved fixture-copy edits."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    AdapterConfig,
    ContractError,
    canonical,
    validate_response,
)
from authzest.codex.fixture_draft import (
    FIXTURE_AFTER,
    HOST_INSTRUCTIONS,
    MAX_RETRY_NOTIFICATIONS,
    build_fixture_request,
    fixture_output_schema,
    fixture_prompt,
)
from authzest.codex.proposals import validate_proposal
from authzest.runner._fixture_workspace import WorkspaceError, supported
from authzest.runner.fixture_apply import FixtureApplySession


class FixtureInputError(ValueError):
    """Invalid local command configuration; contains no source or transport output."""


def _default_adapter_factory(**kwargs):
    # Import and construction are deferred until the exact sharing confirmation.
    from authzest.codex.app_server import CodexAppServerAdapter

    return CodexAppServerAdapter(**kwargs)


def _choice(read: Callable[[str], str], action: str, identifier: str) -> str:
    try:
        answer = read(
            f"Type '{action} {identifier}' to confirm; Enter declines, 'cancel' cancels: "
        )
    except (EOFError, KeyboardInterrupt):
        return "cancel"
    if answer == f"{action} {identifier}":
        return "approve"
    return "cancel" if answer == "cancel" else "decline"


def _emit_json(emit: Callable[[str], Any], value: Any) -> None:
    # Free-form model text is data: escape terminal controls and non-ASCII characters.
    emit(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False))


async def run_codex_fixture(
    model: str,
    *,
    timeout_seconds: float = 120,
    read: Callable[[str], str] = input,
    emit: Callable[[str], Any] = print,
    adapter_factory: Callable[..., Any] | None = None,
    parent: Path | None = None,
) -> dict[str, Any]:
    """Run only the packaged owned fixture, never an arbitrary checkout or generated test.

    One application-level drafting attempt is allowed. Source-sharing permission does
    not authorize application or restoration. The adapter owns child-process cleanup;
    cancellation propagates through its await. No token or dollar hard cap is claimed.
    ``parent`` and injected I/O/adapter factory exist for offline tests, not CLI options.
    """
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise FixtureInputError("Timeout must be finite and greater than 0, up to 120 seconds")
    try:
        AdapterConfig(model=model, temperature=None)
    except ContractError as exc:
        raise FixtureInputError("An explicit valid model identifier is required") from exc
    if not supported():
        raise FixtureInputError("This owned-fixture workflow requires supported POSIX operations")

    request = build_fixture_request(model)
    prompt = fixture_prompt(request)
    output_schema = fixture_output_schema(request)
    limits = {
        "timeout_seconds": timeout_seconds,
        "max_response_bytes": MAX_JSON_BYTES,
        "max_application_turn_attempts": 1,
        "application_retries": 0,
        "max_accepted_retry_notifications": MAX_RETRY_NOTIFICATIONS,
        "codex_internal_transport_retries_hard_capped": False,
        "token_hard_cap": None,
        "dollar_hard_cap": None,
    }
    _emit_json(
        emit,
        {
            "kind": "codex-fixture-sharing-preview",
            "request_id": request.request_id,
            "source_scope": "packaged-owned-fixture/main.py",
            "config": request.to_dict()["config"],
            "limits": limits,
            "limits_sha256": sha256(canonical(limits).encode("utf-8")).hexdigest(),
            "sharing": (
                "Send the displayed task/source payload, host instructions and output schema "
                "through local Codex App Server (which also adds its own harness context) "
                "to OpenAI using your existing Codex session. Account data handling applies. "
                "No API-key input, arbitrary repository source, source execution or model tools. "
                f"At most {MAX_RETRY_NOTIFICATIONS} validated same-turn recovery notices "
                "are accepted; this is "
                "not a count or hard cap of provider attempts. Codex internal transport "
                "retries are not hard-capped; token and dollar hard "
                "caps are unsupported. Sharing does not approve a file edit or verification."
            ),
            "request": request.to_dict(),
            "host_instructions": HOST_INSTRUCTIONS,
            "prompt": prompt,
            "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "output_schema": output_schema,
            "output_schema_sha256": sha256(canonical(output_schema).encode("utf-8")).hexdigest(),
        },
    )
    sharing = _choice(read, "share", request.request_id)
    result: dict[str, Any] = {
        "kind": "codex-owned-fixture-workflow",
        "status": "not-shared",
        "exit_code": 0,
        "request_id": request.request_id,
        "sharing_decision": sharing,
        "limits": limits,
        "limits_sha256": sha256(canonical(limits).encode("utf-8")).hexdigest(),
        "application_turn_attempts": 0,
        "returned_identity": None,
        "model_identity_basis": (
            "negotiated-thread-model; not independently served-model attestation"
        ),
        "usage": None,
        "provider_warning_count": None,
        "provider_retry_notification_count": None,
        "latency_ms": None,
        "application": None,
        "restoration": None,
        "original_checkout_modified": False,
        "verification_status": "not-run",
    }
    if sharing != "approve":
        return result

    started = perf_counter()
    try:
        factory = adapter_factory if adapter_factory is not None else _default_adapter_factory
        async with asyncio.timeout(timeout_seconds):
            adapter = factory(
                approved_request_id=request.request_id,
                timeout_seconds=timeout_seconds,
            )
            result["application_turn_attempts"] = 1
            draft = await adapter.draft(request)
        review = validate_response(draft.review.payload_json, request)
        proposal = validate_proposal(draft.proposal.payload_json, request, review)
        changes = proposal.to_dict()["changes"]
        if (
            len(changes) != 1
            or changes[0]["path"] != "main.py"
            or changes[0]["after_text"] != FIXTURE_AFTER
        ):
            raise ContractError("Only the maintained fixture configuration change is supported")
    except asyncio.CancelledError:
        raise
    except Exception:
        # Never expose provider exceptions, stderr, credentials or a partial model draft.
        result.update(status="draft-failed", exit_code=1)
        return result
    finally:
        result["latency_ms"] = (perf_counter() - started) * 1000

    result["returned_identity"] = review.to_dict()["identity"]
    result["usage"] = review.to_dict()["usage"]
    warnings = getattr(adapter, "warnings_seen", None)
    if type(warnings) is int and 0 <= warnings <= 4096:
        result["provider_warning_count"] = warnings
    retries = getattr(adapter, "retry_notifications_seen", None)
    if type(retries) is int and 0 <= retries <= MAX_RETRY_NOTIFICATIONS:
        result["provider_retry_notification_count"] = retries
    _emit_json(emit, {"kind": "codex-fixture-review", "review": review.to_dict()})
    session = None
    try:
        session = FixtureApplySession(proposal, request, review, parent=parent)
        _emit_json(emit, session.preview())
        session.decide(_choice(read, "apply", proposal.proposal_id))
        applied = session.apply()
        result["application"] = asdict(applied)
        _emit_json(emit, result["application"])
        if applied.status == "applied":
            _emit_json(emit, session.restoration_preview())
            restored = session.restore(_choice(read, "restore", proposal.proposal_id))
            result["restoration"] = asdict(restored)
            _emit_json(emit, result["restoration"])
        success = applied.status in ("applied", "declined", "cancelled")
        if result["restoration"] is not None:
            success = success and result["restoration"]["status"] in (
                "restored",
                "restoration-decline",
                "restoration-cancel",
            )
        result.update(
            status="completed" if success else "application-failed", exit_code=0 if success else 1
        )
    except (OSError, WorkspaceError, ContractError):
        result.update(status="application-failed", exit_code=1)
    finally:
        if session is not None:
            session.close()
    return result
