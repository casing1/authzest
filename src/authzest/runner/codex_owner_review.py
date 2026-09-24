"""Separate sharing consent for a fixed, read-only owner-policy review.

The preview is portable and has no filesystem, account or process effects. Only
the exact interactive sharing choice constructs the opt-in App Server adapter.
Model output is untrusted data, never test code, patch authority or a verdict.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from collections.abc import Callable
from hashlib import sha256
from time import perf_counter
from typing import Any

from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    AdapterConfig,
    ContractError,
    canonical,
    identity,
)
from authzest.codex.fixture_draft import HOST_INSTRUCTIONS, MAX_RETRY_NOTIFICATIONS
from authzest.codex.owner_policy_review import (
    build_owner_policy_request,
    owner_policy_output_schema,
    owner_policy_prompt,
    validate_owner_policy_result,
)


class OwnerReviewInputError(ValueError):
    """Stable local input error containing no provider output or credentials."""


def _default_adapter_factory(**kwargs):
    from authzest.codex.app_server import CodexAppServerAdapter

    return CodexAppServerAdapter(**kwargs)


def build_owner_review_preview(model: str, *, timeout_seconds: float = 120) -> dict[str, Any]:
    """Preview the complete task payload, not ambient Codex harness/account context."""
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise OwnerReviewInputError("Timeout must be finite and greater than 0, up to 120 seconds")
    try:
        AdapterConfig(model=model, temperature=None)
    except ContractError as exc:
        raise OwnerReviewInputError("An explicit valid model identifier is required") from exc
    request = build_owner_policy_request(model)
    prompt = owner_policy_prompt(request)
    schema = owner_policy_output_schema(request)
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
        "kind": "codex-owner-review-sharing-preview",
        "request_id": request.request_id,
        "source_scope": "packaged-owned-policy/main.py+policy.py",
        "request": request.to_dict(),
        "host_instructions": HOST_INSTRUCTIONS,
        "prompt": prompt,
        "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "output_schema": schema,
        "output_schema_sha256": sha256(canonical(schema).encode("utf-8")).hexdigest(),
        "limits": limits,
        "limits_sha256": sha256(canonical(limits).encode("utf-8")).hexdigest(),
        "sharing": (
            "Send only the displayed packaged source snapshots, policy and static evidence "
            "with these host instructions and schema through local Codex App Server to OpenAI "
            "using your existing ChatGPT login. Codex adds its own harness context; account "
            "data handling applies. No evaluation labels, arbitrary repository files or API-key "
            "input. One application attempt, no model fallback. Codex internal transport "
            "retries and token/dollar use are not hard-capped. Returned review/case drafts "
            "are untrusted, unreviewed and not executed. No tools, source execution, patches, "
            "file edits or test execution are authorized. This is not a security verdict."
        ),
    }
    return {**preview, "sharing_id": "share-" + identity(preview)}


async def run_codex_owner_review(
    model: str,
    *,
    timeout_seconds: float = 120,
    read: Callable[[str], str] = input,
    emit: Callable[[str], Any] = print,
    adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Request one review after full-input consent; never apply or execute its output."""
    preview = build_owner_review_preview(model, timeout_seconds=timeout_seconds)
    # Escape all free-form text, including model content, when displaying JSON.
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
        "kind": "codex-owner-review-workflow",
        "status": "not-shared",
        "exit_code": 0,
        "request_id": preview["request_id"],
        "sharing_id": preview["sharing_id"],
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
        "draft": None,
        "original_checkout_modified": False,
        "execution_status": "not-run",
        "authorization_status": "unknown",
    }
    if choice != "approve":
        return result
    if os.name != "posix":
        raise OwnerReviewInputError("Live owner-policy review requires supported POSIX operations")
    # Bind the displayed in-memory data, instructions, schema and limits. This is
    # not an authenticated approval service or a freshness check of a checkout.
    current = build_owner_review_preview(model, timeout_seconds=timeout_seconds)
    if current != preview:
        result.update(status="preview-changed", exit_code=1)
        return result
    request = build_owner_policy_request(model)
    if request.request_id != preview["request_id"]:
        result.update(status="preview-changed", exit_code=1)
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
            draft = await adapter.review_owner_policy(request)
        checked = validate_owner_policy_result(draft, request)
    except asyncio.CancelledError:
        raise
    except Exception:
        # Never emit provider exceptions, partial model content, logs or account details.
        result.update(status="review-failed", exit_code=1)
        return result
    finally:
        result["latency_ms"] = (perf_counter() - started) * 1000
    review = checked.review.to_dict()
    result.update(
        status="draft-ready",
        draft=checked.to_dict(),
        returned_identity=review["identity"],
        usage=review["usage"],
    )
    warnings = getattr(adapter, "warnings_seen", None)
    retries = getattr(adapter, "retry_notifications_seen", None)
    if type(warnings) is int and 0 <= warnings <= 4096:
        result["provider_warning_count"] = warnings
    if type(retries) is int and 0 <= retries <= MAX_RETRY_NOTIFICATIONS:
        result["provider_retry_notification_count"] = retries
    return result
