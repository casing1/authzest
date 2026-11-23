"""Explicit selected-file sharing and inert external-repository proposals.

No target import, generated-code execution, copy, file application or restoration.
The account-backed transport is constructed only after a current typed decision and
a fresh comparison of all selected input bytes. Local checks do not attest policy.
"""

from __future__ import annotations

import asyncio
import json
import math
import secrets
import sys
from collections.abc import Callable
from pathlib import Path
from time import monotonic, perf_counter
from typing import Any

from authzest.analyzer.repository_input import RepositoryInputError, capture_repository
from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    ContractError,
    canonical,
    contract_failure_code,
    identity,
)
from authzest.codex.fixture_draft import MAX_RETRY_NOTIFICATIONS
from authzest.codex.repository_proposal import (
    build_repository_request,
    prepare_repository_preview,
    validate_repository_response,
)
from authzest.runner.codex_owner_review import _failure_snapshot

SHARING_LIFETIME_SECONDS = 300


def _default_adapter_factory(**kwargs):
    from authzest.codex.app_server import CodexAppServerAdapter

    return CodexAppServerAdapter(**kwargs)


def build_repository_sharing_preview(
    root: Path,
    source: str,
    policy: str,
    model: str,
    *,
    contexts: tuple[str, ...] = (),
    timeout_seconds: float = 120,
    invocation_nonce: str | None = None,
) -> dict[str, Any]:
    """Read only explicitly selected files; this function never contacts Codex."""
    if getattr(sys, "frozen", False):
        raise ContractError("Repository proposals require a non-frozen source installation")
    if (
        type(timeout_seconds) not in (int, float)
        or not 0 < timeout_seconds <= 120
        or not math.isfinite(timeout_seconds)
    ):
        raise ContractError("Expected a finite timeout in (0, 120]")
    nonce = secrets.token_hex(16) if invocation_nonce is None else invocation_nonce
    if (
        type(nonce) is not str
        or len(nonce) != 32
        or any(char not in "0123456789abcdef" for char in nonce)
    ):
        raise ContractError("Invalid sharing nonce")
    snapshot = capture_repository(root, source, policy, contexts)
    request = build_repository_request(snapshot, model)
    payload = {
        "schema_version": "1.0",
        "kind": "repository-sharing-preview",
        "source_scope": "explicit external repository files only; proposal-only",
        "request_id": request.request_id,
        "request": request.to_dict(),
        "limits": {
            "timeout_seconds": float(timeout_seconds),
            "sharing_lifetime_seconds": SHARING_LIFETIME_SECONDS,
            "max_response_bytes": MAX_JSON_BYTES,
            "max_application_turn_attempts": 1,
            "application_retries": 0,
            "model_fallback": False,
            "max_accepted_retry_notifications": MAX_RETRY_NOTIFICATIONS,
            "codex_internal_transport_retries_hard_capped": False,
            "token_hard_cap": None,
            "dollar_hard_cap": None,
        },
        "sharing": (
            "Send only the displayed selected source/context and policy text, static evidence, "
            "prompt, schema and fixed host instructions through local Codex App Server to OpenAI "
            "using your existing ChatGPT login. Review all text for secrets before sharing; "
            "explicit selection is not secret detection. Absolute root paths are excluded from "
            "the request. Codex adds harness context and can consume account usage. There is one "
            "application attempt and no model fallback; internal retries and token/dollar usage "
            "are not hard-capped. The policy is user-supplied intent, not verified runtime truth. "
            "Generated source/test/diffs are untrusted data. Nothing is executed or applied; "
            "this decision does not authorize repository edits, copies or test execution."
        ),
    }
    challenged = {
        **payload,
        "sharing_content_id": "content-" + identity(payload),
        "invocation_nonce": nonce,
    }
    return {**challenged, "sharing_id": "share-" + identity(challenged)}


async def run_repository_suggestion(
    root: Path,
    source: str,
    policy: str,
    model: str,
    *,
    contexts: tuple[str, ...] = (),
    timeout_seconds: float = 120,
    emit: Callable[[str], Any] = print,
    read: Callable[[str], str] = input,
    adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    preview = build_repository_sharing_preview(
        root, source, policy, model, contexts=contexts, timeout_seconds=timeout_seconds
    )
    expires = monotonic() + SHARING_LIFETIME_SECONDS
    emit(json.dumps(preview, ensure_ascii=True, indent=2, allow_nan=False))
    result = {
        "schema_version": "1.0",
        "kind": "repository-suggestion",
        "status": "not-shared",
        "exit_code": 0,
        "request_id": preview["request_id"],
        "sharing_id": preview["sharing_id"],
        "model": model,
        "source_evidence": preview["request"],
        "sharing_decision": "decline",
        "application_turn_attempts": 0,
        "attempt_count_basis": "local adapter calls; not accepted or billed provider turns",
        "limits": preview["limits"],
        "proposal": None,
        "proposal_preview": None,
        "failure": None,
        "latency_ms": None,
        "usage": None,
        "provider_warning_count": None,
        "provider_retry_notification_count": None,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "original_checkout_modified": False,
        "authorization_status": "unknown",
    }
    try:
        answer = read(f"Type 'share {preview['sharing_id']}' to send; Enter declines: ")
    except (EOFError, KeyboardInterrupt):
        answer = "cancel"
    if answer == "cancel":
        result.update(status="cancelled", sharing_decision="cancel", exit_code=130)
        return result
    if answer != f"share {preview['sharing_id']}":
        return result
    result["sharing_decision"] = "approve"
    if monotonic() >= expires:
        result.update(status="sharing-expired", exit_code=1)
        return result
    try:
        current = build_repository_sharing_preview(
            root,
            source,
            policy,
            model,
            contexts=contexts,
            timeout_seconds=timeout_seconds,
            invocation_nonce=preview["invocation_nonce"],
        )
    except (ContractError, RepositoryInputError):
        current = None
    if current != preview:
        result.update(status="inputs-changed", exit_code=1)
        return result
    if monotonic() >= expires:
        result.update(status="sharing-expired", exit_code=1)
        return result
    # Reconstruct the same approved request from a fresh selected-byte snapshot.
    # No filesystem reads occur inside the contract or the adapter's validation.
    from authzest.codex.repository_proposal import RepositoryProposalRequest

    request = RepositoryProposalRequest(canonical(current["request"]))
    factory = adapter_factory if adapter_factory is not None else _default_adapter_factory
    started = perf_counter()
    adapter = None
    stage = "adapter-setup"
    try:
        async with asyncio.timeout(timeout_seconds):
            adapter = factory(
                approved_request_id=request.request_id, timeout_seconds=timeout_seconds
            )
            result["application_turn_attempts"] = 1
            stage = "unknown"
            response = await adapter.suggest_repository(request)
        stage = "result-validation"
        checked = validate_repository_response(canonical(response), request)
        composed = prepare_repository_preview(checked, request)
    except asyncio.CancelledError:
        result.update(status="cancelled", exit_code=130)
        return result
    except Exception as exc:
        code = (
            "timeout"
            if isinstance(exc, TimeoutError)
            else contract_failure_code(exc)
            if stage == "result-validation" and isinstance(exc, ContractError)
            else "unexpected-error"
        )
        result.update(
            status="generation-failed",
            exit_code=1,
            failure=_failure_snapshot(
                None if stage == "result-validation" else adapter, stage=stage, code=code
            ),
        )
        return result
    finally:
        result["latency_ms"] = (perf_counter() - started) * 1000
    result.update(status="proposal-ready", proposal=checked, proposal_preview=composed)
    for key in ("provider_warning_count", "provider_retry_notification_count"):
        attr = "warnings_seen" if key == "provider_warning_count" else "retry_notifications_seen"
        count = getattr(adapter, attr, None)
        maximum = 4096 if key == "provider_warning_count" else MAX_RETRY_NOTIFICATIONS
        if type(count) is int and 0 <= count <= maximum:
            result[key] = count
    return result
