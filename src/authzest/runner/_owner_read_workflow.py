"""Connect the current owner-read suggestion to a reviewed local Docker runtime."""

from __future__ import annotations

import asyncio
import json
import secrets
from time import monotonic

from authzest.codex.contracts import ContractError, identity
from authzest.runner._owner_read_docker_phase import OwnerReadDockerDispatcher
from authzest.runner._owner_read_runtime import OwnerReadRuntime, OwnerReadRuntimeError


def _options(*, file_workflow, prepare_copy, runtime_config):
    if not file_workflow or prepare_copy or runtime_config is None:
        raise ContractError(
            "Use --file-workflow with --runtime-config, separately from --prepare-copy"
        )


def _review(runtime):
    fields = {
        "kind": "owner-read-runtime-review",
        "schema_version": "1.0",
        "invocation_nonce": secrets.token_hex(16),
        "runtime": runtime.review_dict(),
        "image_trust": "The operator provisions and reviews the exact local image before use.",
        "scope": {
            "source": "one fixed synthetic availability rule",
            "test": "one positive owner archived-note regression",
            "roles_per_phase": ["test", "controls"],
            "phases": ["before", "after"],
            "phase_seconds": 40,
            "cleanup_seconds": 10,
            "phase_output_bytes": 262144,
            "network": "none",
            "memory_bytes": 536870912,
            "pids": 64,
            "cpu": 1,
            "root_filesystem": "read-only",
            "input_mounts": "two captured read-only files",
            "credentials": "empty private Docker configuration and fixed environment",
        },
        "decision_expires_after_seconds": 300,
    }
    return {**fields, "runtime_review_id": "owner-read-runtime-" + identity(fields)}


def file_preview(sharing, *, file_workflow, prepare_copy, runtime_config):
    _options(file_workflow=file_workflow, prepare_copy=prepare_copy, runtime_config=runtime_config)
    try:
        with OwnerReadRuntime(runtime_config) as runtime:
            return {
                "kind": "owner-read-file-offline-preview",
                "schema_version": "1.0",
                "status": "preview-only",
                "sharing_preview": sharing,
                "runtime_review": _review(runtime),
                "stages": ["copy", "before", "diff", "apply", "after", "restore"],
            }
    except (OwnerReadRuntimeError, OSError):
        raise ContractError("The private owner-read runtime configuration is unavailable") from None


async def run_file_workflow(
    model,
    *,
    timeout_seconds,
    emit,
    read,
    adapter_factory,
    prepare_copy,
    file_workflow,
    runtime_config,
):
    from authzest.runner.owner_read_suggestion import _run_suggestion, build_preview

    build_preview(model, timeout_seconds=timeout_seconds)
    _options(file_workflow=file_workflow, prepare_copy=prepare_copy, runtime_config=runtime_config)
    result = {
        "kind": "owner-read-suggestion",
        "schema_version": "1.0",
        "status": "runtime-not-approved",
        "exit_code": 0,
        "model": model,
        "application_turn_attempts": 0,
        "proposal": None,
        "diffs": [],
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "original_checkout_modified": False,
    }
    runtime = dispatcher = None
    preview = preflight = None
    progress = {}
    try:
        runtime = OwnerReadRuntime(runtime_config)
        preview = _review(runtime)
        result["runtime_review"] = preview
        deadline = monotonic() + 300
        emit(json.dumps(preview, ensure_ascii=True, indent=2))
        expected = "runtime " + preview["runtime_review_id"]
        answer = read(f"Type '{expected}' to review this runtime, or press Enter to decline: ")
        if answer == "cancel":
            result.update(status="cancelled", exit_code=130)
        elif answer == expected:

            def guard():
                runtime.check()
                if monotonic() >= deadline:
                    raise OwnerReadRuntimeError("runtime-review-expired")

            guard()
            dispatcher = OwnerReadDockerDispatcher(runtime)
            preflight = dispatcher.preflight(guard=guard)
            result["runtime_preflight"] = preflight
            if preflight["status"] == "ready":
                result = await _run_suggestion(
                    model,
                    timeout_seconds=timeout_seconds,
                    emit=emit,
                    read=read,
                    adapter_factory=adapter_factory,
                    file_context=(runtime, dispatcher),
                    progress=progress,
                )
                result.update(runtime_review=preview, runtime_preflight=preflight)
            else:
                result.update(status="runtime-unavailable", exit_code=2)
    except (EOFError, KeyboardInterrupt, SystemExit, asyncio.CancelledError) as exc:
        result = progress.get("result", result)
        result.update(status="cancelled", exit_code=130)
        cleanup = getattr(exc, "runtime_descriptor_cleanup_confirmed", None)
        if type(cleanup) is bool:
            result["runtime_descriptor_cleanup_confirmed"] = cleanup
    except (OwnerReadRuntimeError, OSError, ContractError) as exc:
        result = progress.get("result", result)
        started = result.get("application_turn_attempts", 0) > 0
        result.update(
            status="file-workflow-unavailable" if started else "runtime-unavailable",
            exit_code=1 if started else 2,
        )
        cleanup = getattr(exc, "runtime_descriptor_cleanup_confirmed", None)
        if type(cleanup) is bool:
            result["runtime_descriptor_cleanup_confirmed"] = cleanup
    finally:
        if preview is not None:
            result.setdefault("runtime_review", preview)
        if preflight is not None:
            result.setdefault("runtime_preflight", preflight)
        try:
            if dispatcher is not None:
                result["runtime_observations"] = dispatcher.observations()
        except (Exception, KeyboardInterrupt, SystemExit) as exc:
            cancelled = isinstance(exc, (KeyboardInterrupt, SystemExit))
            result.update(
                status="cancelled" if cancelled else "runtime-observations-unconfirmed",
                exit_code=130 if cancelled else 1,
                runtime_observations_status="unconfirmed",
            )
            if result.get("file_workflow"):
                result["file_workflow"]["recovery_required"] = True
        finally:
            if runtime is not None:
                try:
                    runtime.close()
                    result["runtime_descriptor_cleanup_confirmed"] = True
                except (OSError, KeyboardInterrupt, SystemExit):
                    result.update(
                        status="runtime-descriptor-cleanup-unconfirmed",
                        exit_code=1,
                        runtime_descriptor_cleanup_confirmed=False,
                    )
    return result
