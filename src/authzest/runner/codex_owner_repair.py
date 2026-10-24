"""One separately consented recommendation, not policy execution or patch authority.

Only packaged synthetic repair data can be shared. The model selects a registered
template or no change/unknown; the host alone composes the inert exact-diff preview.
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
from authzest.codex.owner_policy_repair_recommendation import (
    prepare_owner_policy_repair_recommendation_preview,
    validate_owner_policy_repair_recommendation,
    validate_owner_policy_repair_recommendation_request,
)
from authzest.codex.owner_policy_repair_transport import (
    build_owner_policy_repair_transport_request,
    validate_owner_policy_repair_transport_result,
)
from authzest.runner.codex_owner_review import _failure_snapshot


class OwnerRepairInputError(ValueError):
    """Closed local input error, never provider text or account information."""


def _default_adapter_factory(**kwargs):
    from authzest.codex.app_server import CodexAppServerAdapter

    return CodexAppServerAdapter(**kwargs)


def build_owner_repair_preview(
    model: str,
    *,
    candidate: str = "before",
    timeout_seconds: float = 120,
    invocation_nonce: str | None = None,
) -> dict[str, Any]:
    """Build a portable, complete sharing preview without consulting an account.

    Explicit nonces reconstruct the same invocation for revalidation only. CLI
    invocations always create a fresh challenge, not a portable approval token.
    """
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise OwnerRepairInputError("Timeout must be finite and greater than 0, up to 120 seconds")
    try:
        AdapterConfig(model=model, temperature=None)
    except ContractError as exc:
        raise OwnerRepairInputError("An explicit valid model identifier is required") from exc
    if type(candidate) is not str or candidate not in {"before", "after"}:
        raise OwnerRepairInputError("Candidate must be before or after")
    nonce = secrets.token_hex(16) if invocation_nonce is None else invocation_nonce
    if (
        type(nonce) is not str
        or len(nonce) != 32
        or any(c not in "0123456789abcdef" for c in nonce)
    ):
        raise OwnerRepairInputError("An invocation nonce must contain 32 lowercase hex characters")
    request = build_owner_policy_repair_transport_request(model, candidate=candidate)
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
        "kind": "codex-owner-repair-sharing-preview",
        "request_id": request.request_id,
        "recommendation_request_id": payload["request_id"],
        "candidate": candidate,
        "source_scope": "registered-owned-policy/before+after+criteria+eight-reviewed-cases",
        "transport_request": payload,
        "host_instructions": payload["host_instructions"],
        "prompt": payload["prompt"],
        "prompt_sha256": sha256(payload["prompt"].encode("utf-8")).hexdigest(),
        "output_schema": payload["output_schema"],
        "output_schema_sha256": identity(payload["output_schema"]),
        "limits": limits,
        "limits_sha256": identity(limits),
        "sharing": (
            "Send the displayed registered before/after synthetic policy, criteria, assumptions "
            "and eight reviewed case labels with this prompt, host instructions and output "
            "schema through local Codex App Server to OpenAI using your existing ChatGPT login. "
            "Codex adds harness context; account data handling applies. No arbitrary repository "
            "files or API-key input. One application attempt, no model fallback. Internal "
            "transport retries and token/dollar use are not hard-capped. The before candidate "
            "is intentionally incorrect test-only text, not a production finding. Labels are "
            "expectations, not observations. Returned explanations remain untrusted. Selecting "
            "a registered template, no-change or unknown grants no execution or patch approval. "
            "No tools, policy execution, tests, file edits, application or restore are authorized."
        ),
    }
    challenged = {
        **preview,
        "sharing_content_id": "content-" + identity(preview),
        "invocation_nonce": nonce,
    }
    return {**challenged, "sharing_id": "share-" + identity(challenged)}


async def run_codex_owner_repair(
    model: str,
    *,
    candidate: str = "before",
    timeout_seconds: float = 120,
    read: Callable[[str], str] = input,
    emit: Callable[[str], Any] = print,
    adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Share once after an exact current choice; return only validated display data."""
    preview = build_owner_repair_preview(
        model, candidate=candidate, timeout_seconds=timeout_seconds
    )
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
        "kind": "codex-owner-repair-workflow",
        "status": "not-shared",
        "exit_code": 0,
        "request_id": preview["request_id"],
        "recommendation_request_id": preview["recommendation_request_id"],
        "candidate": candidate,
        "sharing_id": preview["sharing_id"],
        "sharing_content_id": preview["sharing_content_id"],
        "invocation_nonce": preview["invocation_nonce"],
        "sharing_decision": choice,
        "limits": preview["limits"],
        "application_turn_attempts": 0,
        "returned_identity": None,
        "model_identity_basis": (
            "negotiated-thread-model; not independently served-model attestation"
        ),
        "usage": None,
        "provider_warning_count": None,
        "provider_retry_notification_count": None,
        "latency_ms": None,
        "recommendation": None,
        "recommendation_preview": None,
        "preview_scope": (
            "local composition only; provider_calls in nested preview excludes transport"
        ),
        "failure": None,
        "original_checkout_modified": False,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "observations": {"before": None, "after": None},
        "comparison_status": "not-evaluated",
        "authorization_status": "unknown",
    }
    if choice != "approve":
        return result
    if os.name != "posix":
        raise OwnerRepairInputError(
            "Live owner-policy repair recommendation requires POSIX operations"
        )
    current = build_owner_repair_preview(
        model,
        candidate=candidate,
        timeout_seconds=timeout_seconds,
        invocation_nonce=preview["invocation_nonce"],
    )
    request = build_owner_policy_repair_transport_request(model, candidate=candidate)
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
            recommendation = await adapter.recommend_owner_policy_repair(request)
        stage = "result-validation"
        checked = validate_owner_policy_repair_transport_result(recommendation, request).to_dict()
        inner = validate_owner_policy_repair_recommendation_request(
            canonical(request.to_dict()["request"])
        )
        selected = validate_owner_policy_repair_recommendation(
            canonical(checked["recommendation"]), inner
        )
        composed = prepare_owner_policy_repair_recommendation_preview(selected, inner).to_dict()
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
            status="recommendation-failed",
            exit_code=1,
            failure=_failure_snapshot(
                None if stage == "result-validation" else adapter, stage=stage, code=code
            ),
        )
        return result
    finally:
        result["latency_ms"] = (perf_counter() - started) * 1000
    result.update(
        status="recommendation-ready",
        recommendation=checked,
        recommendation_preview=composed,
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
