"""Interactive HTTP-only external repair flow for one selected FastAPI file.

capture -> share/propose -> private copy -> isolated before check -> accept
and privately apply the exact diff -> isolated after check -> approved
original write with backup. Every effect needs its own current typed answer
with a 300-second deadline; Enter declines. Expected answers stay on the host
in the reviewed case file; the model output and guest output stay untrusted.
Results are retained history and never resume a flow.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from time import monotonic
from typing import Any

from authzest.analyzer.repository_input import RepositoryInputError
from authzest.analyzer.repository_origin import capture_repository_origin
from authzest.codex.contracts import (
    ContractError,
    canonical,
    contract_failure_code,
    decode,
    identity,
)
from authzest.codex.repository_http_copy_plan import prepare_repository_http_copy_plan
from authzest.codex.repository_http_proposal import (
    RepositoryHttpRequest,
    build_repository_http_request,
    prepare_repository_http_preview,
    validate_repository_http_options,
    validate_repository_http_response,
)
from authzest.runner._generated_repair_phase import PhaseError, SessionEvidenceBudget
from authzest.runner._repository_http_phase import execute_repository_http_phase
from authzest.runner._repository_http_runtime_input import (
    RepositoryHttpRuntimeInputError,
    prepare_repository_http_runtime_input,
)
from authzest.runner.repository_http_cases import build_repository_http_cases
from authzest.runner.repository_http_file_session import (
    RepositoryHttpFileSession,
    RepositoryHttpSessionError,
)
from authzest.runner.repository_http_original import (
    RepositoryHttpOriginalError,
    apply_original,
    default_recovery_parent,
    prepare_original_application,
)
from authzest.runner.repository_http_verification import build_repository_http_verification_plan
from authzest.runner.repository_suggestion import run_repository_suggestion

SCHEMA_VERSION = "2.0"
KIND = "repository-http-fix-result"
DECISION_SECONDS = 300.0
MAX_CASE_FILE_BYTES = 65_536
_PHASE_SUMMARY_DROP = {"captures", "runtime_metadata"}


class _Declined(Exception):
    def __init__(self, status: str, exit_code: int = 0):
        super().__init__(status)
        self.status, self.exit_code = status, exit_code


def case_basis(request: RepositoryHttpRequest) -> dict:
    """The exact ``basis`` a reviewed case file must carry for these inputs."""
    data = request.to_dict()
    source, policy = data["selection"]["files"]
    return {
        "selection_id": identity(data["selection"]),
        "interface_id": data["http_interface"]["interface_id"],
        "source_path": source["path"],
        "source_sha256": source["sha256"],
        "policy_path": policy["path"],
        "policy_sha256": policy["sha256"],
    }


def _read_case_file(path: Path) -> dict:
    """Bounded no-follow read of the human-reviewed independent case file."""
    if not isinstance(path, Path):
        raise ContractError("Expected a case file path", code="validation-shape")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CASE_FILE_BYTES:
            raise ContractError(
                "Case file must be a bounded regular file", code="validation-budget"
            )
        raw = os.read(fd, MAX_CASE_FILE_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) > MAX_CASE_FILE_BYTES:
        raise ContractError("Case file must be a bounded regular file", code="validation-budget")
    try:
        return decode(raw.decode("utf-8"))
    except UnicodeError:
        raise ContractError("Case file must be UTF-8 JSON", code="validation-text") from None


def _phase_summary(result) -> dict:
    data = result.to_dict()
    return {key: value for key, value in data.items() if key not in _PHASE_SUMMARY_DROP}


class _Flow:
    def __init__(self, emit, read, clock):
        self.emit, self.read, self.clock = emit, read, clock
        self.deadline = None

    def step(self, name: str, **values) -> None:
        self.emit(json.dumps({"kind": "repository-http-fix-step", "step": name, **values}))

    def confirm(self, action: str, description: str, declined: str) -> None:
        code = action + " " + secrets.token_hex(3)
        issued = self.clock()
        try:
            answer = self.read(f"{description}\nType '{code}' to continue; Enter declines: ")
        except (EOFError, KeyboardInterrupt):
            raise _Declined("cancelled", 130) from None
        if answer != code:
            raise _Declined(declined)
        if self.clock() >= issued + DECISION_SECONDS:
            raise _Declined("decision-expired", 1)
        self.deadline = issued + DECISION_SECONDS

    def guard(self) -> None:
        if self.deadline is None or self.clock() >= self.deadline:
            raise RepositoryHttpOriginalError("decision-expired")


def _perform(session: RepositoryHttpFileSession, step: str, flow: _Flow) -> dict:
    """Perform one private step only within the user's original answer deadline.

    The session issues its own short-lived plan; it never extends the user's
    decision, which is rechecked immediately before the effect.
    """
    plan = session.prepare(step)
    decision = session.decide(plan, plan.to_dict()["confirmation"])
    try:
        flow.guard()
    except RepositoryHttpOriginalError:
        raise _Declined("decision-expired", 1) from None
    return session.perform(decision)


def build_repository_http_fix_preview(
    root: Path, source: str, policy: str, model: str, *, app_attribute: str | None = None
) -> dict:
    """Capture selected inputs and show the sharing data and required case basis."""
    validate_repository_http_options(source, app_attribute=app_attribute or "app")
    origin = capture_repository_origin(root, source, policy)
    try:
        request = build_repository_http_request(
            origin.snapshot, model, app_attribute=app_attribute or "app"
        )
    finally:
        origin.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "repository-http-fix-preview",
        "request_id": request.request_id,
        "request": request.to_dict(),
        "case_basis": case_basis(request),
        "effects": "none: no account, copy, guest or original write",
    }


async def run_repository_http_fix(
    root: Path,
    source: str,
    policy: str,
    model: str,
    *,
    cases_path: Path,
    profile_path: Path,
    app_attribute: str | None = None,
    recovery_parent: Path | None = None,
    timeout_seconds: float = 120,
    emit: Callable[[str], Any] = print,
    read: Callable[[str], str] = input,
    adapter_factory: Callable[..., Any] | None = None,
    phase_runner: Callable[..., Any] = execute_repository_http_phase,
    clock: Callable[[], float] = monotonic,
) -> dict:
    flow = _Flow(emit, read, clock)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "status": "invalid-input",
        "exit_code": 2,
        "model": model,
        "request_id": None,
        "case_basis": None,
        "cases": None,
        "suggestion": None,
        "proposal_status": None,
        "proposal": None,
        "diff": None,
        "failure": None,
        "private_copy": None,
        "before_phase": None,
        "after_phase": None,
        "original": None,
        "restore_command": None,
        "original_checkout_modified": False,
        "verified_fix": False,
        "verification_scope": "independent-reviewed-cases-only",
        "authorization_status": "unknown",
    }
    origin = session = profile = None
    try:
        attribute = app_attribute or "app"
        validate_repository_http_options(source, app_attribute=attribute)
        origin = capture_repository_origin(root, source, policy)
        request = build_repository_http_request(origin.snapshot, model, app_attribute=attribute)
        result["request_id"] = request.request_id
        result["case_basis"] = case_basis(request)
        cases = build_repository_http_cases(_read_case_file(cases_path))
        case_data = cases.to_dict()
        if case_data["basis"] != result["case_basis"]:
            result["failure"] = {"code": "case-basis-mismatch"}
            return result
        result["cases"] = {
            "case_set_id": cases.case_set_id,
            "regression_case_id": case_data["regression_case_id"],
            "case_ids": [case["id"] for case in case_data["cases"]],
            "authorship": case_data["authorship"],
        }
        profile = prepare_repository_http_runtime_input(profile_path)
        flow.step("inputs-captured", request_id=request.request_id, cases=result["cases"])

        sharing = {"expected": None, "answer": None}

        def sharing_read(prompt: str) -> str:
            # Remember only whether a typed answer missed the exact phrase.
            match = re.search(r"Type '([^']+)'", prompt)
            sharing["expected"] = match.group(1) if match else None
            answer = read(prompt)
            sharing["answer"] = answer
            return answer

        suggestion = await run_repository_suggestion(
            root,
            source,
            policy,
            model,
            http_poc=True,
            app_attribute=app_attribute,
            timeout_seconds=timeout_seconds,
            emit=emit,
            read=sharing_read,
            adapter_factory=adapter_factory,
        )
        result["suggestion"] = {
            key: suggestion.get(key)
            for key in (
                "status",
                "sharing_decision",
                "application_turn_attempts",
                "latency_ms",
                "usage",
                "failure",
            )
        }
        if suggestion["status"] != "proposal-ready":
            result.update(status=suggestion["status"], exit_code=suggestion["exit_code"])
            if (
                suggestion["status"] == "not-shared"
                and sharing["answer"]
                and sharing["answer"] != sharing["expected"]
            ):
                result["failure"] = {
                    "code": "sharing-phrase-mismatch",
                    "hint": "Type the whole phrase shown in quotes, including its first word.",
                }
            return result
        shared = RepositoryHttpRequest(canonical(suggestion["source_evidence"]))
        if shared.payload_json != request.payload_json:
            result.update(status="inputs-changed", exit_code=1)
            return result
        response = validate_repository_http_response(canonical(suggestion["proposal"]), request)
        result["proposal"] = response
        result["proposal_status"] = response["status"]
        if response["status"] != "proposed-change":
            result.update(status="no-proposed-change", exit_code=0)
            return result
        preview = prepare_repository_http_preview(response, request)
        result["diff"] = preview["changes"][0]["diff"]
        try:
            plan = build_repository_http_verification_plan(request, response, cases)
        except ContractError as exc:
            result.update(
                status="poc-not-covered",
                exit_code=1,
                failure={"code": contract_failure_code(exc), "poc": response["proposal"]["poc"]},
            )
            return result
        copy_plan = prepare_repository_http_copy_plan(request, response, cases)
        session = RepositoryHttpFileSession(origin, request, response, cases, copy_plan)
        origin = None  # The session now owns and closes the origin descriptors.
        budget = SessionEvidenceBudget()
        phases = {}

        def run_phase(phase: str):
            flow.confirm(
                "run-" + phase,
                f"Run the isolated {phase} check: start owned A/B containers from the "
                "reviewed images with the private copy only; expected answers stay here.",
                phase + "-declined",
            )
            flow.step(phase + "-phase-started")
            try:
                value = phase_runner(
                    session,
                    request,
                    response,
                    cases,
                    plan,
                    profile,
                    phase=phase,
                    session_nonce=secrets.token_hex(16),
                    dispatch_guard=flow.guard,
                    evidence_budget=budget,
                )
            except PhaseError as exc:
                result["failure"] = {"code": str(exc), "phase": phase}
                raise _Declined(phase + "-phase-failed", 1) from None
            phases[phase] = value
            summary = _phase_summary(value)
            result[phase + "_phase"] = summary
            flow.step(
                phase + "-phase-finished",
                status=summary["status"],
                criteria_met=summary["criteria_met"],
                failure=summary["failure"],
                outcomes=(summary["comparison"] or {}).get("outcomes"),
                evidence_directory=summary["evidence_directory"],
            )
            if summary["status"] != "complete":
                raise _Declined(phase + "-phase-failed", 1)
            if not summary["criteria_met"]:
                raise _Declined(
                    "before-not-reproduced" if phase == "before" else "after-not-verified", 1
                )

        flow.confirm(
            "copy",
            "Create a fresh private copy of the selected source and policy "
            "(the original stays unchanged).",
            "copy-declined",
        )
        _perform(session, "copy", flow)
        result["private_copy"] = session.result()
        run_phase("before")
        flow.step("proposed-diff", diff=result["diff"], poc=response["proposal"]["poc"])
        flow.confirm(
            "apply-private",
            "Accept this exact diff and apply it to the private copy only.",
            "private-apply-declined",
        )
        _perform(session, "accept-diff", flow)
        _perform(session, "apply", flow)
        result["private_copy"] = session.result()
        run_phase("after")
        result["verified_fix"] = True
        try:
            original = prepare_original_application(session, phases["after"])
        except Exception as exc:
            # Any change to the held original inputs since capture is a conflict.
            result.update(status="original-conflict", exit_code=1)
            result["failure"] = {"code": getattr(exc, "code", None) or type(exc).__name__}
            return result
        flow.step("original-preview", **original)
        flow.confirm(
            "apply-original",
            f"Write this verified change to {original['root']}/{original['source_path']}; "
            "a private backup and recovery record are kept.",
            "original-declined",
        )
        try:
            record = apply_original(
                session,
                phases["after"],
                recovery_parent=recovery_parent or default_recovery_parent(),
                guard=flow.guard,
                verification={
                    "before_phase_evidence": result["before_phase"]["evidence_directory"],
                    "case_set_id": cases.case_set_id,
                    "request_id": request.request_id,
                },
            )
        except RepositoryHttpOriginalError as exc:
            result["original"] = exc.result
            if exc.result is not None and exc.result.get("state") == "recovery-required":
                result.update(status="original-recovery-required", exit_code=1)
                result["original_checkout_modified"] = None
                result["restore_command"] = "authzest repo-restore " + exc.result["record_path"]
            else:
                conflict = exc.code == "original-edit-conflict"
                result.update(
                    status="original-conflict" if conflict else "original-failed", exit_code=1
                )
            result["failure"] = {"code": exc.code}
            return result
        result["original"] = record
        result["original_checkout_modified"] = True
        result["restore_command"] = "authzest repo-restore " + record["record_path"]
        result.update(status="original-applied", exit_code=0)
        return result
    except _Declined as exc:
        result.update(status=exc.status, exit_code=exc.exit_code)
        return result
    except (ContractError, RepositoryInputError, RepositoryHttpRuntimeInputError) as exc:
        code = contract_failure_code(exc) if isinstance(exc, ContractError) else str(exc)
        result["failure"] = {"code": code}
        return result
    except (RepositoryHttpSessionError, RepositoryHttpOriginalError, OSError) as exc:
        result.update(status="failed", exit_code=1, failure={"code": type(exc).__name__})
        return result
    finally:
        if session is not None:
            result["private_copy"] = session.result()
            try:
                session.close()
            except BaseException:
                result["private_copy"]["descriptor_cleanup"] = "unconfirmed"
        for handle in (origin, profile):
            if handle is not None:
                with suppress(Exception):
                    handle.close()
