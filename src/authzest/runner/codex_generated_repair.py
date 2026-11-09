"""Consent-gated generation of inert source/test proposals for one owned scenario.

This workflow never runs generated code or creates, applies or restores files.
Confirmation authorizes only the displayed transport request, not its response.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import secrets
from collections.abc import Callable
from hashlib import sha256
from time import perf_counter
from typing import Any

from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    AdapterConfig,
    ContractError,
    canonical,
    contract_failure_code,
    identity,
)
from authzest.codex.fixture_draft import MAX_RETRY_NOTIFICATIONS
from authzest.codex.generated_repair import (
    prepare_generated_repair_preview,
    validate_generated_repair_proposal,
    validate_generated_repair_request,
)
from authzest.codex.generated_repair_transport import (
    GENERATED_REPAIR_MODEL_IDENTITY_BASIS,
    build_generated_repair_transport_request,
    validate_generated_repair_transport_result,
)
from authzest.runner.codex_owner_review import _failure_snapshot


class GeneratedRepairInputError(ValueError):
    """Closed local input error, containing no provider/account data."""


def _default_adapter_factory(**kwargs):
    from authzest.codex.app_server import CodexAppServerAdapter

    return CodexAppServerAdapter(**kwargs)


def build_generated_repair_sharing_preview(
    model: str,
    *,
    timeout_seconds: float = 120,
    invocation_nonce: str | None = None,
) -> dict[str, Any]:
    """Preview the complete fixed request offline with a fresh local challenge.

    Explicit nonces only reconstruct the same invocation for revalidation. This
    is not an authenticated approval service or a time-limited consent token.
    """
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise GeneratedRepairInputError(
            "Timeout must be finite and greater than 0, up to 120 seconds"
        )
    try:
        AdapterConfig(model=model, temperature=None)
    except ContractError as exc:
        raise GeneratedRepairInputError("An explicit valid model identifier is required") from exc
    nonce = secrets.token_hex(16) if invocation_nonce is None else invocation_nonce
    if (
        type(nonce) is not str
        or len(nonce) != 32
        or any(c not in "0123456789abcdef" for c in nonce)
    ):
        raise GeneratedRepairInputError(
            "An invocation nonce must contain 32 lowercase hex characters"
        )
    request = build_generated_repair_transport_request(model)
    payload = request.to_dict()
    limits = {
        "timeout_seconds": float(timeout_seconds),
        "max_response_bytes": MAX_JSON_BYTES,
        "max_application_turn_attempts": 1,
        "application_retries": 0,
        "max_accepted_retry_notifications": MAX_RETRY_NOTIFICATIONS,
        "codex_internal_transport_retries_hard_capped": False,
        "token_hard_cap": None,
        "dollar_hard_cap": None,
    }
    preview = {
        "kind": "codex-generated-repair-sharing-preview",
        "request_id": request.request_id,
        "generation_request_id": payload["request_id"],
        "source_scope": (
            "maintained-owned-fastapi/app.py+policy+source-declarations; no after-template"
        ),
        "transport_request": payload,
        "host_instructions": payload["host_instructions"],
        "prompt": payload["prompt"],
        "prompt_sha256": sha256(payload["prompt"].encode("utf-8")).hexdigest(),
        "output_schema": payload["output_schema"],
        "output_schema_sha256": identity(payload["output_schema"]),
        "limits": limits,
        "limits_sha256": identity(limits),
        "sharing": (
            "Send the displayed fixed synthetic FastAPI source, assistant-authored policy "
            "pending maintainer review and source declarations, prompt, host instructions and "
            "output schema through local Codex App Server to OpenAI using your existing ChatGPT "
            "login. Codex adds harness context; account data handling applies. No arbitrary "
            "repository files or API-key input. One application attempt, no model fallback. "
            "Internal transport retries and token/dollar use are not hard-capped. X-Demo-Actor "
            "is caller-controlled fixture identity, not production authentication. Request a "
            "new defensive test and repair source, not a registered after-template selection. "
            "Returned code and explanations are untrusted and unverified. AST parsing is not "
            "code safety, a runtime test or policy correctness. No tools, generated-code "
            "execution, copies, edits, application or restoration are authorized."
        ),
    }
    challenged = {
        **preview,
        "sharing_content_id": "content-" + identity(preview),
        "invocation_nonce": nonce,
    }
    return {**challenged, "sharing_id": "share-" + identity(challenged)}


async def run_codex_generated_repair(
    model: str,
    *,
    timeout_seconds: float = 120,
    read: Callable[[str], str] = input,
    emit: Callable[[str], Any] = print,
    adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Make at most one adapter call after exact current sharing confirmation."""
    preview = build_generated_repair_sharing_preview(model, timeout_seconds=timeout_seconds)
    emit(json.dumps(preview, ensure_ascii=True, indent=2, allow_nan=False))
    try:
        answer = read(
            f"Type 'share {preview['sharing_id']}' to confirm; Enter declines, 'cancel' cancels: "
        )
    except (EOFError, KeyboardInterrupt):
        answer = "cancel"
    choice = (
        "approve"
        if answer == f"share {preview['sharing_id']}"
        else "cancel"
        if answer == "cancel"
        else "decline"
    )
    result: dict[str, Any] = {
        "kind": "codex-generated-repair-workflow",
        "status": "not-shared",
        "exit_code": 0,
        "request_id": preview["request_id"],
        "generation_request_id": preview["generation_request_id"],
        "sharing_id": preview["sharing_id"],
        "sharing_content_id": preview["sharing_content_id"],
        "invocation_nonce": preview["invocation_nonce"],
        "sharing_decision": choice,
        "limits": preview["limits"],
        "application_turn_attempts": 0,
        "attempt_count_basis": "local adapter calls; not accepted/billed provider turns",
        "returned_identity": None,
        "model_identity_basis": GENERATED_REPAIR_MODEL_IDENTITY_BASIS,
        "usage": None,
        "provider_warning_count": None,
        "provider_retry_notification_count": None,
        "latency_ms": None,
        "generation": None,
        "proposal_status": None,
        "proposal_preview": None,
        "preview_scope": "nested provider_calls count covers local composition only, not transport",
        "failure": None,
        "applied": False,
        "original_checkout_modified": False,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
    }
    if choice != "approve":
        return result
    if os.name != "posix":
        raise GeneratedRepairInputError("Live generated repair requests require POSIX operations")
    current = build_generated_repair_sharing_preview(
        model, timeout_seconds=timeout_seconds, invocation_nonce=preview["invocation_nonce"]
    )
    request = build_generated_repair_transport_request(model)
    if current != preview or request.to_dict() != preview["transport_request"]:
        result.update(
            status="preview-changed",
            exit_code=1,
            failure={
                "stage": "request-validation",
                "code": "request-invalid",
                "turn_start": "not-attempted",
            },
        )
        return result
    started = perf_counter()
    adapter = None
    stage = "adapter-setup"
    try:
        factory = adapter_factory if adapter_factory is not None else _default_adapter_factory
        async with asyncio.timeout(timeout_seconds):
            adapter = factory(
                approved_request_id=request.request_id, timeout_seconds=timeout_seconds
            )
            result["application_turn_attempts"] = 1
            stage = "unknown"
            generation = await adapter.generate_repair(request)
        stage = "result-validation"
        checked = validate_generated_repair_transport_result(generation, request).to_dict()
        inner = validate_generated_repair_request(canonical(request.to_dict()["request"]))
        proposal = validate_generated_repair_proposal(canonical(checked["proposal"]), inner)
        composed = prepare_generated_repair_preview(proposal, inner).to_dict()
    except asyncio.CancelledError:
        raise
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
    result.update(
        status="generation-ready",
        generation=checked,
        proposal_status=checked["proposal"]["status"],
        proposal_preview=composed,
        returned_identity=checked["identity"],
        usage=checked["usage"],
    )
    warnings = getattr(adapter, "warnings_seen", None)
    retries = getattr(adapter, "retry_notifications_seen", None)
    if type(warnings) is int and 0 <= warnings <= 4096:
        result["provider_warning_count"] = warnings
    if type(retries) is int and 0 <= retries <= MAX_RETRY_NOTIFICATIONS:
        result["provider_retry_notification_count"] = retries
    return result
