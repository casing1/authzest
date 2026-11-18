"""Synchronous CLI coordination after one current generation call has returned.

Only the CLI's directly returned generation and in-process session are consumed.
No saved result is imported, no choice is inferred, and no prompt runs in the
generation event loop. Python collaborators are trusted, not an auth boundary.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import secrets
from dataclasses import dataclass

from authzest.codex.contracts import canonical
from authzest.codex.generated_repair import (
    prepare_generated_repair_preview,
    validate_generated_repair_proposal,
    validate_generated_repair_request,
)
from authzest.codex.generated_repair_transport import (
    GeneratedRepairTransportResult,
    build_generated_repair_transport_request,
    validate_generated_repair_transport_result,
)
from authzest.runner._generated_repair_session import (
    GeneratedRepairSession,
    GeneratedRepairSessionResult,
)
from authzest.runner.codex_generated_repair import (
    GeneratedRepairInputError,
    build_generated_repair_sharing_preview,
)
from authzest.runner.generated_repair_verification import (
    build_generated_repair_verification_preview,
)

_SUCCESS = {
    "copy": "copied-private-workspace",
    "before": "checked-before",
    "source-diff": "accepted-exact-diff",
    "source-apply": "applied-copy-only",
    "after": "checked-after",
    "restore": "restored-before",
}
_ACTIONS = {
    "copy": "create_copy",
    "before": "run_before",
    "source-diff": "accept_diff",
    "source-apply": "apply_source",
    "after": "run_after",
    "restore": "restore_source",
}
_NOTICE = (
    "Review the entire current plan, actual file identities, exact diff, runtime profile and "
    "original expiry before deciding. Each phrase authorizes only this stage once, at most "
    "300 seconds from its original plan. Copies and evidence are retained, not resumed. "
    "Tests and startup hints are untrusted; complete host comparisons remain finite checks, "
    "not general authorization assurance. Enter declines; cancel skips this stage. EOF or "
    "Ctrl-C stops all further interaction. Restoration always needs a separate decision."
)


@dataclass(frozen=True, slots=True)
class ReviewedGeneratedRuntimeInput:
    """One local CLI interaction, not authenticated review or kernel proof."""

    loaded: object
    invocation_nonce: str
    profile_id: str
    decision: str

    @property
    def profile(self):
        return self.loaded.profile

    def assert_current(self):
        try:
            if self.decision != "approved" or self.profile.profile_id != self.profile_id:
                raise GeneratedRepairInputError("A current local runtime review is required")
            answer = self.loaded.assert_current()
        except ValueError:
            raise GeneratedRepairInputError("Local runtime input or review changed") from None
        if inspect.iscoroutine(answer):
            answer.close()
        if answer is not None:
            raise GeneratedRepairInputError("Runtime guard must synchronously return None")


def prepare_file_runtime(path):
    """Keep loader diagnostics stable and opt-in; never expose raw file errors."""
    from authzest.runner._generated_repair_runtime_input import (
        GeneratedRuntimeInputError,
        prepare_generated_runtime_input,
    )

    try:
        return prepare_generated_runtime_input(path)
    except GeneratedRuntimeInputError:
        raise GeneratedRepairInputError("Invalid or unsupported local runtime profile") from None


def close_file_runtime(loaded, result):
    """Keep descriptor uncertainty and any prior effects in the one final record."""
    try:
        answer = loaded.close()
        if inspect.iscoroutine(answer):
            answer.close()
        if answer is not None:
            raise GeneratedRepairInputError("Runtime input closure is unconfirmed")
        result.setdefault("file_workflow", {"requested": True, "session_result": None})[
            "runtime_input_cleanup"
        ] = "confirmed"
    except BaseException as exc:
        workflow = result.setdefault("file_workflow", {"requested": True, "session_result": None})
        workflow["runtime_input_cleanup"] = "unconfirmed"
        if not isinstance(exc, Exception):
            result.update(status="file-workflow-cancelled", exit_code=130)
        elif not result.get("exit_code", 0):
            result.update(status="file-workflow-failed", exit_code=1)
    return result


def build_generated_runtime_review(loaded):
    """Show local-only data; this is never part of the provider request."""
    try:
        loaded.assert_current()
    except ValueError:
        raise GeneratedRepairInputError("Local runtime input changed before review") from None
    nonce, profile_id = secrets.token_hex(16), loaded.profile.profile_id
    return {
        "kind": "generated-repair-runtime-review-preview",
        "invocation_nonce": nonce,
        "profile_id": profile_id,
        "runtime_input": loaded.review_dict(),
        "local_only": True,
        "sent_to_provider": False,
        "confirmation_phrase": f"runtime-review {nonce} {profile_id}",
        "notice": (
            "Review the entire local profile and file identities, trusted Docker executable, "
            "immutable preprovisioned images and current source/recipe pins. This local "
            "review is separate from source sharing and every later stage decision. "
            "It is not image attestation, kernel capability proof or execution approval. "
            "Required maintained guest kernel guards still run before target code loads. "
            "No runtime profile data is sent to the provider."
        ),
    }


def review_generated_runtime(loaded, *, emit, read):
    preview = build_generated_runtime_review(loaded)
    _emit(emit, preview)
    try:
        answer = read(
            f"Type '{preview['confirmation_phrase']}' to confirm local runtime review; "
            "Enter declines, 'cancel' cancels: "
        )
    except (EOFError, KeyboardInterrupt, asyncio.CancelledError, SystemExit):
        answer = "cancel"
    if inspect.iscoroutine(answer):
        answer.close()
    if type(answer) is not str:
        raise GeneratedRepairInputError("Runtime review must synchronously return text")
    choice = (
        "approved"
        if answer == preview["confirmation_phrase"]
        else "cancelled"
        if answer == "cancel"
        else "declined"
    )
    reviewed = ReviewedGeneratedRuntimeInput(
        loaded, preview["invocation_nonce"], preview["profile_id"], choice
    )
    if choice == "approved":
        reviewed.assert_current()
    return reviewed


def guarded_generated_sharing_read(reviewed, read):
    """Recheck local profile after input, before any sharing answer is consumed."""

    def guarded(prompt):
        answer = read(prompt)
        reviewed.assert_current()
        return answer

    return guarded


def declined_generated_runtime_result(reviewed):
    return {
        "kind": "codex-generated-file-workflow",
        "status": "runtime-review-" + reviewed.decision,
        "exit_code": 130 if reviewed.decision == "cancelled" else 0,
        "runtime_review": {
            "decision": reviewed.decision,
            "profile_id": reviewed.profile_id,
            "invocation_nonce": reviewed.invocation_nonce,
            "reviewer_authenticated": False,
            "kernel_proof": False,
        },
        "application_turn_attempts": 0,
        "sharing_decision": "not-requested",
        "generation": None,
        "applied": False,
        "original_checkout_modified": False,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
        "file_workflow": {"requested": True, "status": "not-started", "session_result": None},
    }


def _emit(emit, value):
    answer = emit(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False))
    if inspect.iscoroutine(answer):
        answer.close()
    if answer is not None:
        raise GeneratedRepairInputError("Workflow output must synchronously return None")


def _generation_preview(result, model, timeout_seconds):
    """Rebuild all current sharing and returned-artifact bindings, never code."""
    if type(result) is not dict or result.get("kind") != "codex-generated-repair-workflow":
        raise GeneratedRepairInputError("Expected the current generation workflow result")
    sharing = build_generated_repair_sharing_preview(
        model,
        timeout_seconds=timeout_seconds,
        invocation_nonce=result.get("invocation_nonce"),
    )
    for key in (
        "request_id",
        "generation_request_id",
        "sharing_id",
        "sharing_content_id",
        "limits",
    ):
        if result.get(key) != sharing[key]:
            raise GeneratedRepairInputError("Current generation sharing context changed")
    if (
        result.get("sharing_decision") != "approve"
        or type(result.get("application_turn_attempts")) is not int
        or result["application_turn_attempts"] != 1
    ):
        raise GeneratedRepairInputError("A single approved current generation is required")
    request = build_generated_repair_transport_request(model)
    checked = validate_generated_repair_transport_result(
        GeneratedRepairTransportResult(canonical(result.get("generation"))), request
    ).to_dict()
    inner = validate_generated_repair_request(canonical(request.to_dict()["request"]))
    proposal = validate_generated_repair_proposal(canonical(checked["proposal"]), inner)
    if (
        result.get("proposal_preview")
        != prepare_generated_repair_preview(proposal, inner).to_dict()
        or result.get("proposal_status") != checked["proposal"]["status"]
        or result.get("returned_identity") != checked["identity"]
        or result.get("usage") != checked["usage"]
    ):
        raise GeneratedRepairInputError("Current generated artifacts changed")
    return build_generated_repair_verification_preview(inner, proposal)


def _checkpoint(session):
    result = session.result()
    if type(result) is not GeneratedRepairSessionResult:
        raise GeneratedRepairInputError("Unexpected current file-session result")
    return result.to_dict()


def _summary(result, checkpoint):
    workflow = result["file_workflow"]
    workflow["session_result"] = checkpoint
    if checkpoint is None:
        return
    result["execution_status"] = checkpoint.get("execution_status", "unknown")
    result["patch_application"] = checkpoint.get("source_application", "unknown")
    result["restoration_status"] = checkpoint.get("restoration_status", "unknown")
    application = checkpoint.get("source_application")
    result["applied"] = (
        True if application == "applied-copy-only" else False if application == "not-run" else None
    )
    workspace = checkpoint.get("workspace")
    result["current_copy_state"] = (
        workspace.get("state", "unknown") if isinstance(workspace, dict) else "unknown"
    )
    result["original_checkout_modified"] = False
    result["authorization_status"] = "unknown"


def _stage(session, stage, *, emit, read):
    plan = session.prepare(stage)
    payload = plan.to_dict()
    phrase = f"{stage} {payload['session_nonce']} {plan.plan_id}"
    _emit(
        emit,
        {
            "kind": "generated-repair-file-stage-preview",
            "stage": stage,
            "confirmation_phrase": phrase,
            "plan": payload,
            "notice": _NOTICE,
        },
    )
    answer = read(f"Type '{phrase}' to confirm; Enter declines, 'cancel' cancels: ")
    if inspect.iscoroutine(answer):
        answer.close()
    if type(answer) is not str:
        raise GeneratedRepairInputError("Stage choice must synchronously return text")
    choice = "approved" if answer == phrase else "cancelled" if answer == "cancel" else "declined"
    session.decide(stage, choice, plan_id=plan.plan_id)
    if choice != "approved":
        return choice, _checkpoint(session)
    getattr(session, _ACTIONS[stage])()
    checkpoint = _checkpoint(session)
    _emit(
        emit,
        {
            "kind": "generated-repair-file-stage-result",
            "stage": stage,
            "session_result": checkpoint,
        },
    )
    return "approved", checkpoint


def run_generated_file_workflow(
    generation_result, *, model, timeout_seconds, runtime_input, emit, read
):
    """Continue the current call synchronously with separate expiring choices.

    The runtime input is the CLI's fresh bounded loader result, not model data or
    a serialized execution receipt. Its guard must be current before every
    effect. This helper has no adapter, source destination or resume parameter.
    """
    if type(generation_result) is not dict:
        raise GeneratedRepairInputError("Expected a current generation result")
    result = json.loads(canonical(generation_result))
    result["kind"] = "codex-generated-file-workflow"
    result["generation_workflow_kind"] = generation_result.get("kind")
    result["file_workflow"] = {
        "requested": True,
        "status": "not-started",
        "stopped_stage": None,
        "session_result": None,
        "restart_supported": False,
        "retention": "Private copies and evidence remain; no automatic rollback or deletion.",
    }
    if generation_result.get("status") != "generation-ready":
        result["file_workflow"]["status"] = "generation-not-ready"
        return result
    session = None
    stopped = None
    interrupted = False
    checkpoint = None
    try:
        preview = _generation_preview(generation_result, model, timeout_seconds)
        if preview.to_dict()["proposal_status"] != "proposed-change":
            result["file_workflow"]["status"] = "no-proposed-change"
            return result
        runtime_input.assert_current()
        session = GeneratedRepairSession(
            preview,
            runtime_profile=runtime_input.profile,
            runtime_guard=runtime_input.assert_current,
        )
        for stage in ("copy", "before", "source-diff", "source-apply", "after"):
            stopped = stage
            choice, checkpoint = _stage(session, stage, emit=emit, read=read)
            _summary(result, checkpoint)
            if choice != "approved":
                result["status"] = "file-workflow-" + choice
                result["file_workflow"]["status"] = choice
                break
            if checkpoint["stages"][stage]["status"] != _SUCCESS[stage]:
                result["status"] = "file-workflow-failed"
                result["exit_code"] = 1
                result["file_workflow"]["status"] = "stage-failed"
                break
        else:
            stopped = None
            result["status"] = "file-checks-complete"
            result["file_workflow"]["status"] = "checks-complete"
    except (EOFError, KeyboardInterrupt, asyncio.CancelledError, SystemExit):
        interrupted = True
        result.update(status="file-workflow-cancelled", exit_code=130)
        result["file_workflow"]["status"] = "cancelled"
    except Exception:
        result.update(status="file-workflow-failed", exit_code=1)
        result["file_workflow"].update(
            status="stage-failed", failure="current-context-or-stage-failed"
        )
    finally:
        if session is not None:
            try:
                checkpoint = _checkpoint(session)
                _summary(result, checkpoint)
                # Failed after with confirmed cleanup may still restore. Session
                # preparation independently enforces files/cleanup; no guessed
                # flag or imported checkpoint can open restoration.
                if not interrupted and checkpoint.get("source_application") == "applied-copy-only":
                    stopped_before_restore = stopped
                    stopped = "restore"
                    choice, checkpoint = _stage(session, "restore", emit=emit, read=read)
                    _summary(result, checkpoint)
                    if (
                        choice == "approved"
                        and checkpoint["stages"]["restore"]["status"] == _SUCCESS["restore"]
                    ):
                        if result["status"] == "file-checks-complete":
                            result["status"] = "file-workflow-complete"
                            result["file_workflow"]["status"] = "complete"
                        stopped = stopped_before_restore
                    elif choice != "approved":
                        result["file_workflow"]["restoration_decision"] = choice
                        if result["status"] == "file-checks-complete":
                            result["status"] = "file-workflow-" + choice
                            result["file_workflow"]["status"] = "restoration-" + choice
                    else:
                        result["file_workflow"]["status"] = "restore-failed"
                        result.update(status="file-workflow-failed", exit_code=1)
            except (EOFError, KeyboardInterrupt, asyncio.CancelledError, SystemExit):
                result.update(status="file-workflow-cancelled", exit_code=130)
                result["file_workflow"]["status"] = "cancelled"
            except Exception:
                result.update(status="file-workflow-failed", exit_code=1)
                result["file_workflow"]["restore_status"] = "unavailable-or-failed"
            finally:
                try:
                    closed = session.close()
                    if inspect.iscoroutine(closed):
                        closed.close()
                    if closed is not None:
                        raise GeneratedRepairInputError("Session closure is unconfirmed")
                    result["file_workflow"]["close_status"] = "confirmed"
                except (KeyboardInterrupt, asyncio.CancelledError, SystemExit):
                    result.update(status="file-workflow-cancelled", exit_code=130)
                    result["file_workflow"]["close_status"] = "cancelled-unconfirmed"
                except Exception:
                    if result.get("exit_code") != 130:
                        result.update(status="file-workflow-failed", exit_code=1)
                    result["file_workflow"]["close_status"] = "unconfirmed"
                try:
                    _summary(result, _checkpoint(session))
                except (KeyboardInterrupt, asyncio.CancelledError, SystemExit):
                    result.update(status="file-workflow-cancelled", exit_code=130)
                    result["file_workflow"]["checkpoint_status"] = "unconfirmed"
                except Exception:
                    if result.get("exit_code") != 130:
                        result.update(status="file-workflow-failed", exit_code=1)
                    result["file_workflow"]["checkpoint_status"] = "unconfirmed"
        result["file_workflow"]["stopped_stage"] = stopped
    return result
