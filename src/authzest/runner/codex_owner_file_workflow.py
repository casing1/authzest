"""Opt-in CLI coordination of one recommendation and one owned file session.

The selector is not consent. Sharing, copy creation and every file-session stage
have separate exact choices. Only current in-process data is accepted; this module
does not import receipts, resume sessions or choose sources, workers or paths.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable
from time import monotonic
from typing import Any

from authzest.codex.contracts import ContractError, canonical
from authzest.codex.owner_policy_file_repair import prepare_owner_policy_file_repair
from authzest.codex.owner_policy_repair_recommendation import (
    prepare_owner_policy_repair_recommendation_preview,
    validate_owner_policy_repair_recommendation,
    validate_owner_policy_repair_recommendation_request,
)
from authzest.codex.owner_policy_repair_transport import (
    OwnerPolicyRepairTransportResult,
    validate_owner_policy_repair_transport_request,
    validate_owner_policy_repair_transport_result,
)
from authzest.runner._owner_policy_file_workspace import supported
from authzest.runner.codex_owner_repair import (
    OwnerRepairInputError,
    build_owner_repair_preview,
    run_codex_owner_repair,
)
from authzest.runner.owner_policy_file_repair import (
    MAX_DECISION_SECONDS,
    OwnerPolicyFileResult,
    OwnerPolicyRepairFileSession,
)

RETENTION_NOTICE = (
    "Copies and checkpoints are retained; close releases the descriptor without deleting files "
    "or rewriting record.json. The final in-memory closed checkpoint can therefore differ from "
    "the last durable record. No automatic rollback, retry, approval import or restart/resume. "
    "Inspect a retained workspace manually if state or evidence is unconfirmed. Historical "
    "after observations do not describe the restored before file. Records and terminal choices "
    "are not authenticated attestations; authorization remains unknown."
)
STAGE_NOTICE = (
    "Review the complete plan and its original expiry before deciding. This choice authorizes "
    "only this stage, once, while the same inputs and file identities remain current. "
    "A check executes only captured registered bytes in the fixed worker, not arbitrary source. "
    "It is not an OS sandbox or endpoint authorization proof. Enter declines; cancel skips "
    "this stage. If a confirmed applied copy remains, restore requires another separate choice."
)


def _emit(emit, value):
    emit(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False))


def _application(result, model, candidate, timeout_seconds):
    """Revalidate the complete current recommendation, not a saved authority token."""
    preview = build_owner_repair_preview(
        model,
        candidate=candidate,
        timeout_seconds=timeout_seconds,
        invocation_nonce=result["invocation_nonce"],
    )
    for name in (
        "request_id",
        "recommendation_request_id",
        "candidate",
        "sharing_id",
        "sharing_content_id",
        "limits",
    ):
        if result[name] != preview[name]:
            raise ContractError("Current sharing context changed")
    if result["sharing_decision"] != "approve" or result["application_turn_attempts"] != 1:
        raise ContractError("Expected one approved current recommendation attempt")
    request = validate_owner_policy_repair_transport_request(
        canonical(preview["transport_request"])
    )
    checked = validate_owner_policy_repair_transport_result(
        OwnerPolicyRepairTransportResult(canonical(result["recommendation"])), request
    ).to_dict()
    inner = validate_owner_policy_repair_recommendation_request(
        canonical(request.to_dict()["request"])
    )
    selected = validate_owner_policy_repair_recommendation(
        canonical(checked["recommendation"]), inner
    )
    composed = prepare_owner_policy_repair_recommendation_preview(selected, inner).to_dict()
    if (
        composed != result["recommendation_preview"]
        or checked["identity"] != result["returned_identity"]
        or checked["usage"] != result["usage"]
    ):
        raise ContractError("Current recommendation context changed")
    return prepare_owner_policy_file_repair(inner, selected)


def _choice(read, phrase):
    # EOF / KeyboardInterrupt are not the literal, stage-local 'cancel' choice.
    # They stop interaction; a later restore prompt must not silently consume input.
    answer = read(f"Type '{phrase}' to confirm; Enter declines, 'cancel' cancels: ")
    return "approved" if answer == phrase else "cancelled" if answer == "cancel" else "declined"


def _now():
    value = monotonic()
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ContractError("Invalid copy decision clock")
    return float(value)


def _copy_confirmation(session, application):
    created = _now()
    expires = created + MAX_DECISION_SECONDS
    if expires - created > MAX_DECISION_SECONDS:
        expires = math.nextafter(expires, created)
    if not math.isfinite(expires) or not 0 < expires - created <= MAX_DECISION_SECONDS:
        raise ContractError("Copy decision lifetime cannot be represented")
    session_id = session.result().to_dict()["session_id"]
    return {
        "session_id": session_id,
        "application_id": application.application_id,
        "created_at": created,
        "expires_at": expires,
        "reviewer_authenticated": False,
        "confirmation_phrase": f"copy {session_id} {application.application_id}",
    }


def _may_restore(checkpoint):
    return (
        checkpoint is not None
        and checkpoint["phase"] == "applied-after"
        and checkpoint["application_status"] == "completed"
        and checkpoint["file_binding_status"] == "confirmed"
        and checkpoint["evidence_status"] == "confirmed"
    )


def _summarize(result, checkpoint):
    """Summarize actual activity; individual checks remain authoritative and separate."""
    result["file_workflow"]["session_result"] = checkpoint
    result["file_workflow"]["checkpoint_status"] = "current"
    result["patch_application"] = checkpoint["application_status"]
    result["restoration_status"] = checkpoint["restoration_status"]
    result["comparison_status"] = checkpoint["comparison_status"]
    result["observations"] = {
        name: check["observations"] if check else None
        for name, check in checkpoint["checks"].items()
    }
    states = {check["execution_status"] for check in checkpoint["checks"].values() if check}
    result["execution_status"] = next(
        (state for state in ("cancelled", "failed", "completed") if state in states), "not-run"
    )
    dispatched = result["file_workflow"].get("check_dispatch")
    if dispatched is not None:
        candidate = "before" if dispatched["stage"] == "before-check" else "after"
        obtained = checkpoint["checks"][candidate] is not None
        dispatched["checkpoint_obtained"] = obtained
        result["file_workflow"]["unconfirmed_check"] = (
            None
            if obtained
            else {
                "stage": dispatched["stage"],
                "execution_status": "unknown",
                "reason": "no-accepted-checkpoint-after-dispatch",
            }
        )
        if not obtained:
            # A non-async interruption may escape the existing session without
            # a check result. Dispatch is not proof of launch or non-execution.
            result["execution_status"] = "unknown"


def _unknown_checkpoint(result):
    details = result["file_workflow"]
    details["last_checkpoint"] = details["session_result"]
    details["session_result"] = None
    details["checkpoint_status"] = "unavailable"
    for key in ("execution_status", "patch_application", "restoration_status"):
        result[key] = "unknown"
    result["observations"] = {"before": None, "after": None}
    result["comparison_status"] = "inconclusive"


def _failure(result, stage, code):
    failure = {"stage": stage, "code": code}
    result["file_workflow"]["failure"] = failure
    result["file_workflow"]["failures"].append(failure)
    result.update(status="file-workflow-failed", exit_code=1, failure=failure)


async def _stage(session, stage, result, read, emit):
    try:
        plan = session.prepare(stage)
    except ContractError:
        _summarize(result, session.result().to_dict())
        _failure(result, stage, "validation-failed")
        return False
    checkpoint = session.result().to_dict()
    _summarize(result, checkpoint)
    _emit(
        emit,
        {
            "kind": "owner-policy-file-stage-preview",
            "stage": stage,
            "plan": plan.to_dict(),
            "decision": checkpoint["decisions"][stage],
            "notice": STAGE_NOTICE,
        },
    )
    choice = _choice(read, f"approve {stage} {plan.plan_id}")
    try:
        session.decide(stage, choice, plan_id=plan.plan_id)
        if choice == "approved":
            if stage.endswith("-check"):
                result["file_workflow"]["check_dispatch"] = {
                    "stage": stage,
                    "checkpoint_obtained": False,
                }
                await session.run_check(stage)
            else:
                {"diff": session.accept_diff, "apply": session.apply, "restore": session.restore}[
                    stage
                ]()
    except ContractError:
        _summarize(result, session.result().to_dict())
        _failure(result, stage, "validation-failed")
        return False
    checkpoint = session.result().to_dict()
    _summarize(result, checkpoint)
    _emit(
        emit,
        {"kind": "owner-policy-file-stage-result", "stage": stage, "session_result": checkpoint},
    )
    if choice != "approved":
        if not result["file_workflow"]["failures"]:
            result["status"] = f"{stage}-{choice}"
        return False
    if checkpoint["failure"]:
        _failure(result, stage, checkpoint["failure"])
        return False
    if stage.endswith("-check"):
        check = checkpoint["checks"]["before" if stage == "before-check" else "after"]
        if check["execution_status"] != "completed" or (
            stage == "after-check" and check["comparison_status"] != "passed"
        ):
            _failure(result, stage, check["reason"])
            return False
    return True


async def run_codex_owner_file_workflow(
    model: str,
    *,
    candidate: str = "before",
    timeout_seconds: float = 120,
    read: Callable[[str], str] = input,
    emit: Callable[[str], Any] = print,
    adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Coordinate the existing recommendation and separately approved file effects."""
    # Pure validation/capability checks precede account access and copy creation.
    build_owner_repair_preview(model, candidate=candidate, timeout_seconds=timeout_seconds)
    if not supported():
        raise OwnerRepairInputError(
            "Owned file workflow requires supported POSIX non-frozen Python source operations"
        )
    result = await run_codex_owner_repair(
        model,
        candidate=candidate,
        timeout_seconds=timeout_seconds,
        read=read,
        emit=emit,
        adapter_factory=adapter_factory,
    )
    result.update(
        kind="codex-owner-file-workflow",
        file_workflow={
            "copy_decision": "not-requested",
            "copy_confirmation": None,
            "session_result": None,
            "checkpoint_status": "not-created",
            "check_dispatch": None,
            "unconfirmed_check": None,
            "failure": None,
            "failures": [],
            "retention_notice": RETENTION_NOTICE,
        },
    )
    if result["status"] != "recommendation-ready":
        return result
    session = None
    stage = "application-validation"
    try:
        application = _application(result, model, candidate, timeout_seconds)
        if application.to_dict()["status"] != "registered-change":
            result["status"] = application.to_dict()["status"]
            return result
        stage = "copy"
        session = OwnerPolicyRepairFileSession(application, clock=monotonic)
        confirmation = _copy_confirmation(session, application)
        details = result["file_workflow"]
        details.update(copy_decision="pending", copy_confirmation=confirmation)
        _summarize(result, session.result().to_dict())
        _emit(
            emit,
            {
                "kind": "owner-policy-file-copy-preview",
                "application": application.to_dict(),
                "copy_confirmation": confirmation,
                "limits": {"max_decision_seconds": MAX_DECISION_SECONDS, "copy_attempts": 1},
                "notice": (
                    "Create one fresh private temporary copy of the registered before policy "
                    "with before/after text and record.json. No existing checkout is changed. "
                    "This choice does not approve checks, diff acceptance, apply or restore. "
                    "All five stages require separate complete previews and exact decisions. "
                    + RETENTION_NOTICE
                ),
            },
        )
        details["copy_decision"] = _choice(read, confirmation["confirmation_phrase"])
        if details["copy_decision"] != "approved":
            result["status"] = "copy-" + details["copy_decision"]
            return result
        current = _application(result, model, candidate, timeout_seconds)
        if current.payload_json != application.payload_json:
            raise ContractError("Copy application changed")
        if not confirmation["created_at"] <= _now() < confirmation["expires_at"]:
            details["copy_decision"] = "expired"
            _failure(result, stage, "decision-expired")
            return result
        session.create_copy()
        checkpoint = session.result().to_dict()
        _summarize(result, checkpoint)
        if checkpoint["failure"] or checkpoint["phase"] != "ready-before":
            _failure(result, stage, checkpoint["failure"] or "copy-not-created")
            return result
        completed = True
        for stage in ("before-check", "diff", "apply", "after-check"):
            if not await _stage(session, stage, result, read, emit):
                completed = False
                break
        if _may_restore(session.result().to_dict()):
            stage = "restore"
            restored = await _stage(session, stage, result, read, emit)
            if completed and restored:
                result["status"] = "completed"
    except (asyncio.CancelledError, KeyboardInterrupt, EOFError, SystemExit) as exc:
        if type(getattr(exc, "file_repair_result", None)) is OwnerPolicyFileResult:
            _summarize(result, exc.file_repair_result.to_dict())
        if stage == "copy" and result["file_workflow"]["copy_decision"] == "pending":
            result["file_workflow"]["copy_decision"] = "cancelled"
        _failure(result, stage, "interrupted")
        result.update(status="cancelled", exit_code=130)
    except Exception as exc:
        if type(getattr(exc, "file_repair_result", None)) is OwnerPolicyFileResult:
            _summarize(result, exc.file_repair_result.to_dict())
        _failure(
            result,
            stage,
            "validation-failed" if isinstance(exc, ContractError) else "unexpected-error",
        )
    finally:
        if session is not None:
            try:
                session.close()
                _summarize(result, session.result().to_dict())
            except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                _unknown_checkpoint(result)
                _failure(result, "close", "checkpoint-unavailable")
    return result
