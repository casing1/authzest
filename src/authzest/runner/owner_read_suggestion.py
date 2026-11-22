"""Review and share the fixed owner-read request, returning an inert suggestion."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
from collections.abc import Callable
from typing import Any

from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    ContractError,
    canonical,
    contract_failure_code,
    identity,
)
from authzest.codex.fixture_draft import MAX_RETRY_NOTIFICATIONS
from authzest.codex.generated_repair import _diff
from authzest.codex.owner_read_suggestion import (
    SOURCE_PATH,
    TEST_PATH,
    OwnerReadRequest,
    build_owner_read_request,
    validate_owner_read_request,
    validate_owner_read_response,
)
from authzest.codex.proposals import content_hash
from authzest.runner.codex_owner_review import _failure_snapshot


def _preview(request: OwnerReadRequest, timeout_seconds: float, nonce: str) -> dict[str, Any]:
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 120:
        raise ContractError("Expected a timeout greater than 0 and at most 120 seconds")
    envelope = {
        "kind": "owner-read-sharing-preview",
        "source_scope": SOURCE_PATH,
        "request_id": request.request_id,
        "request": request.to_dict(),
        "limits": {
            "timeout_seconds": float(timeout_seconds),
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
            "The local Codex App Server sends the displayed prompt and output schema to OpenAI "
            "under the displayed host instructions using your existing ChatGPT login. Codex adds "
            "its harness context. One adapter call can consume account usage. Internal transport "
            "retries and token or dollar use have no guaranteed cap here. The returned test and "
            "source are untrusted suggestions for review only."
        ),
    }
    challenged = {
        **envelope,
        "sharing_content_id": "content-" + identity(envelope),
        "invocation_nonce": nonce,
    }
    return {**challenged, "sharing_id": "share-" + identity(challenged)}


def build_preview(
    model: str,
    *,
    timeout_seconds: float = 120,
    prepare_copy: bool = False,
    file_workflow: bool = False,
    runtime_config=None,
) -> dict[str, Any]:
    """Build an offline, complete sharing preview for a new invocation."""
    sharing = _preview(build_owner_read_request(model), timeout_seconds, secrets.token_hex(16))
    if file_workflow or runtime_config is not None:
        from authzest.runner._owner_read_workflow import file_preview

        return file_preview(
            sharing,
            file_workflow=file_workflow,
            prepare_copy=prepare_copy,
            runtime_config=runtime_config,
        )
    if not prepare_copy:
        return sharing
    from authzest.runner.owner_read_copy import copy_spec

    return {
        "kind": "owner-read-copy-offline-preview",
        "schema_version": "1.0",
        "sharing_preview": sharing,
        "local_copy": copy_spec(),
        "status": "preview-only",
    }


def _changes(request: OwnerReadRequest, proposal: dict[str, Any]) -> list[dict[str, Any]]:
    if proposal["status"] != "proposed-change":
        return []
    before = request.to_dict()["source"]
    return [
        {
            "path": SOURCE_PATH,
            "before_sha256": before["sha256"],
            "after_sha256": content_hash(proposal["source"]),
            "diff": _diff(before["text"], proposal["source"], SOURCE_PATH),
        },
        {
            "path": TEST_PATH,
            "before_sha256": None,
            "after_sha256": content_hash(proposal["test"]),
            "diff": _diff("", proposal["test"], TEST_PATH, new=True),
        },
    ]


async def _run_suggestion(
    model: str,
    *,
    timeout_seconds: float = 120,
    emit: Callable[[str], Any] = print,
    read: Callable[[str], str] = input,
    adapter_factory: Callable[..., Any] | None = None,
    prepare_copy: bool = False,
    file_context=None,
    progress=None,
) -> dict[str, Any]:
    preview = build_preview(model, timeout_seconds=timeout_seconds)
    emit(json.dumps(preview, ensure_ascii=True, indent=2, allow_nan=False))
    result = {
        "schema_version": "1.0",
        "kind": "owner-read-suggestion",
        "status": "not-shared",
        "exit_code": 0,
        "model": model,
        "request_id": preview["request_id"],
        "sharing_id": preview["sharing_id"],
        "sharing_decision": "decline",
        "application_turn_attempts": 0,
        "attempt_count_basis": "local adapter calls",
        "proposal": None,
        "diffs": [],
        "failure": None,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "original_checkout_modified": False,
    }
    if progress is not None:
        progress["result"] = result
    if file_context is not None:
        result["file_workflow"] = {"status": "not-started", "recovery_required": False}
    if prepare_copy:
        from authzest.runner.owner_read_copy import copy_supported, prepare_current_copy

        result["copy"] = {"status": "not-started", "path": None}
        if not copy_supported():
            result.update(status="unsupported", sharing_decision="not-requested", exit_code=2)
            return result
    try:
        answer = read(f"Type 'share {preview['sharing_id']}' to send, or press Enter to decline: ")
    except (EOFError, KeyboardInterrupt):
        answer = "cancel"
    if answer == "cancel":
        result.update(sharing_decision="cancel", status="cancelled")
        if file_context is not None:
            result["exit_code"] = 130
        return result
    if answer != f"share {preview['sharing_id']}":
        return result
    result["sharing_decision"] = "approve"
    if os.name != "posix" or getattr(sys, "frozen", False):
        result.update(status="unsupported", exit_code=2)
        return result

    try:
        request = validate_owner_read_request(build_owner_read_request(model))
        if _preview(request, timeout_seconds, preview["invocation_nonce"]) != preview:
            raise ContractError("Sharing input changed", code="validation-identity")
    except (ContractError, OSError):
        result.update(status="preview-changed", exit_code=1)
        return result

    if file_context is not None:
        file_context[0].check()
    stage = "adapter-setup"
    adapter = None
    try:
        if adapter_factory is None:
            from authzest.codex.app_server import CodexAppServerAdapter

            adapter_factory = CodexAppServerAdapter
        async with asyncio.timeout(timeout_seconds):
            adapter = adapter_factory(
                approved_request_id=request.request_id, timeout_seconds=timeout_seconds
            )
            stage = "unknown"
            result["application_turn_attempts"] = 1
            response = await adapter.suggest_owner_read(request)
        stage = "result-validation"
        proposal = validate_owner_read_response(canonical(response), request)
        diffs = _changes(request, proposal)
    except Exception as exc:
        code = "unexpected-error"
        if isinstance(exc, TimeoutError):
            code = "timeout"
        elif stage == "result-validation" and isinstance(exc, ContractError):
            code = contract_failure_code(exc)
        failure = _failure_snapshot(
            None if stage == "result-validation" else adapter, stage=stage, code=code
        )
        result.update(status="suggestion-failed", exit_code=1, failure=failure)
        return result
    result.update(status=proposal["status"], proposal=proposal, diffs=diffs)
    if (prepare_copy or file_context is not None) and proposal["status"] == "proposed-change":

        def current_plan_inputs():
            rebuilt = validate_owner_read_request(build_owner_read_request(model))
            if _preview(rebuilt, timeout_seconds, preview["invocation_nonce"]) != preview:
                raise ContractError("Sharing identity changed", code="validation-identity")
            artifacts = validate_owner_read_response(canonical(proposal), rebuilt)
            exact_diffs = _changes(rebuilt, artifacts)
            if exact_diffs != diffs:
                raise ContractError("Proposed diffs changed", code="validation-identity")
            return rebuilt, artifacts, exact_diffs

        if file_context is not None:
            from authzest.runner._owner_read_file_session import OwnerReadFileSession

            runtime, dispatcher = file_context
            session = OwnerReadFileSession(
                sharing_id=preview["sharing_id"],
                inputs=current_plan_inputs,
                dispatcher=dispatcher,
                runtime_context=runtime.review_dict(),
                runtime_guard=runtime.check,
            )
            observed = session.run(emit=emit, read=read)
            result.update(
                file_workflow=observed,
                execution_status="completed"
                if all(
                    observed[stage] is not None and observed[stage]["status"] == "matched"
                    for stage in ("before", "after")
                )
                else "partial"
                if any(
                    observed["stages"][stage]["guest_dispatch_started"]
                    for stage in ("before", "after")
                )
                else "not-run",
                patch_application=observed["patch_application"],
                restoration_status=observed["restoration_status"],
                exit_code=observed["exit_code"],
            )
        else:
            result["copy"] = prepare_current_copy(
                sharing_id=preview["sharing_id"], inputs=current_plan_inputs, emit=emit, read=read
            )
            result["exit_code"] = result["copy"]["exit_code"]
    return result


async def run_suggestion(
    model: str,
    *,
    timeout_seconds: float = 120,
    emit: Callable[[str], Any] = print,
    read: Callable[[str], str] = input,
    adapter_factory: Callable[..., Any] | None = None,
    prepare_copy: bool = False,
    file_workflow: bool = False,
    runtime_config=None,
) -> dict[str, Any]:
    if file_workflow or runtime_config is not None:
        from authzest.runner._owner_read_workflow import run_file_workflow

        return await run_file_workflow(
            model,
            timeout_seconds=timeout_seconds,
            emit=emit,
            read=read,
            adapter_factory=adapter_factory,
            prepare_copy=prepare_copy,
            file_workflow=file_workflow,
            runtime_config=runtime_config,
        )
    return await _run_suggestion(
        model,
        timeout_seconds=timeout_seconds,
        emit=emit,
        read=read,
        adapter_factory=adapter_factory,
        prepare_copy=prepare_copy,
    )
