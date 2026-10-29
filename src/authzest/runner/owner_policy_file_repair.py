"""Live, single-copy repair workflow; exported records never grant authority.

Only registered policy bytes are supported. Each stage requires a fresh choice;
the worker executes a captured file snapshot, not an embedded substitute. This
module is source-only and does not call a provider or alter an existing checkout.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import sys
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from uuid import uuid4

from authzest.codex.contracts import ContractError, _object, canonical, decode, identity
from authzest.codex.owner_policy_file_repair import (
    OwnerPolicyFileRepairApplication,
    validate_owner_policy_file_repair,
)
from authzest.runner._owner_policy_file_transport import (
    WorkerTransport,
)
from authzest.runner._owner_policy_file_transport import (
    run_worker as _run_worker,
)
from authzest.runner._owner_policy_file_worker import (
    CHECK_ID,
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    WORKER_SHA256,
    WORKER_SOURCE,
)
from authzest.runner._owner_policy_file_workspace import (
    CommittedWriteError,
    PolicyFileWorkspace,
    WorkspaceError,
    WorkspaceInitializationError,
    supported,
)

STAGES = ("before-check", "diff", "apply", "after-check", "restore")
MAX_DECISION_SECONDS = 300.0
MAX_APPLICATION_BYTES = 32_768
MAX_EVENTS = 256
_SOURCE_LIMIT = 32_768
_REASONS = {
    "attempt-already-consumed",
    "session-closed",
    "operation-in-progress",
    "copy-not-created",
    "unsupported-platform",
    "recommendation-has-no-change",
    "copy-already-created",
    "initialization-failed",
    "invalid-context",
    "file-state-changed",
    "evidence-unconfirmed",
    "wrong-phase",
    "baseline-required",
    "diff-acceptance-required",
    "plan-required",
    "stale-plan",
    "decision-pending",
    "decision-declined",
    "decision-cancelled",
    "decision-expired",
    "invalid-decision-time",
    "write-failed",
    "committed-state-unconfirmed",
    "worker-input-error",
    "worker-process-error",
    "worker-exit-error",
    "timeout",
    "output-limit",
    "cleanup-unconfirmed",
    "cancelled",
    "invalid-worker-transport",
    "invalid-worker-output",
    "cases-match",
    "case-mismatch",
}


@dataclass(frozen=True, slots=True)
class _Snapshot:
    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class OwnerPolicyFilePlan(_Snapshot):
    @property
    def plan_id(self) -> str:
        return self.to_dict()["plan_id"]


@dataclass(frozen=True, slots=True)
class OwnerPolicyFileResult(_Snapshot):
    """An unauthenticated checkpoint, not a capability or a current-file attestation."""


def _snapshot(data: dict, kind=_Snapshot):
    raw = canonical(data)
    decode(raw)
    return kind(raw)


def _finite(value) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ContractError("Expected a finite decision time")
    return float(value)


def _expiry(now: float, duration: float) -> float:
    expires = _finite(now + duration)
    if expires - now > duration:
        expires = math.nextafter(expires, now)
    if not 0 < expires - now <= duration:
        raise ContractError("Decision clock cannot represent the approval lifetime")
    return expires


def _stage(value) -> str:
    if type(value) is not str or value not in STAGES:
        raise ContractError("Unknown file workflow stage")
    return value


def _recipe() -> dict:
    if sha256(WORKER_SOURCE.encode("utf-8")).hexdigest() != WORKER_SHA256:
        raise ContractError("File worker identity changed")
    return {
        "id": CHECK_ID,
        "version": "1.0",
        "mapping": "registered-eight-nullable-dataclasses-v1",
        "worker_sha256": WORKER_SHA256,
        "worker_source": WORKER_SOURCE,
        "launch": ["trusted sys.executable", "-I", "-S", "-c", "pinned worker text"],
        "timeout_seconds": 5,
        "cleanup_timeout_seconds": 1,
        "max_input_bytes": MAX_INPUT_BYTES,
        "max_output_bytes": MAX_OUTPUT_BYTES,
        "max_source_bytes": _SOURCE_LIMIT,
        "max_depth": 32,
        "max_nodes": 8192,
        "max_identifier_characters": 128,
        "max_scopes": 16,
        "case_count": 8,
        "attempt_limit": 1,
        "max_decision_seconds": MAX_DECISION_SECONDS,
        "max_application_bytes": MAX_APPLICATION_BYTES,
        "max_events": MAX_EVENTS,
        "environment": {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": "fresh private worker directory",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
            "NO_COLOR": "1",
            "TERM": "dumb",
        },
        "scope": "captured registered bytes from the session-owned policy.py",
        "platform": "POSIX non-frozen Python source only",
        "os_sandbox": False,
        "filesystem_deadline_hard_capped": False,
    }


def _file_state(state) -> dict:
    return {
        "filename": "policy.py",
        "sha256": sha256(state.data).hexdigest(),
        "byte_count": len(state.data),
        "identity": list(state.identity),
    }


def _comparison(content: dict, checks: dict) -> tuple[str, list[dict]]:
    before = checks["before"]["observations"] if checks["before"] else None
    after = checks["after"]["observations"] if checks["after"] else None
    rows = [
        {
            "case_id": case["case_id"],
            "expected": case["expected"],
            "before": before[i] if before is not None else None,
            "after": after[i] if after is not None else None,
            "change": ("unchanged" if before[i] == after[i] else "changed")
            if before is not None and after is not None
            else "not-evaluated",
        }
        for i, case in enumerate(content["cases"])
    ]
    if before is not None and after is not None:
        return (
            "passed" if after == [c["expected"] == "allow" for c in content["cases"]] else "failed",
            rows,
        )
    return ("inconclusive" if checks["after"] is not None else "not-evaluated", rows)


class OwnerPolicyRepairFileSession:
    """One in-process session, one attempt per stage; construction performs no I/O."""

    def __init__(self, application: OwnerPolicyFileRepairApplication, *, clock=monotonic):
        if type(application) is not OwnerPolicyFileRepairApplication or not callable(clock):
            raise ContractError("Invalid application or clock")
        self._application = validate_owner_policy_file_repair(application.payload_json)
        if len(self._application.payload_json.encode("utf-8")) > MAX_APPLICATION_BYTES:
            raise ContractError("Application exceeds the live checkpoint budget")
        self._clock = clock
        self._last_time = _finite(clock())
        self._recipe = _recipe()
        self._session_id = uuid4().hex
        self._workspace = None
        self._workspace_path = None
        self._initialization_stage = None
        self._original = self._current = None
        self._phase = "not-created"
        self._generation = 0
        self._create_used = self._closed = self._running = False
        self._critical = None
        self._failure = None
        self._file_binding = "not-evaluated"
        self._evidence = "confirmed"
        self._application_status = self._restoration_status = "not-run"
        self._diff_status = "not-accepted"
        self._plans: dict[str, OwnerPolicyFilePlan] = {}
        self._decisions: dict[str, dict] = {}
        self._used: set[str] = set()
        self._completed: dict[str, str] = {}
        self._checks = {"before": None, "after": None}
        self._events: list[str] = []

    def _time(self):
        now = _finite(self._clock())
        if now < self._last_time:
            raise ContractError("Decision clock moved backwards")
        self._last_time = now
        return now

    def _context(self):
        current = validate_owner_policy_file_repair(self._application.payload_json)
        if current.payload_json != self._application.payload_json or _recipe() != self._recipe:
            raise ContractError("File workflow context changed")
        return current.to_dict()

    def _content(self):
        return self._application.to_dict()["request"]["content"]

    def result(self) -> OwnerPolicyFileResult:
        comparison_status, comparison = _comparison(self._content(), self._checks)
        if self._critical is not None and comparison_status == "passed":
            comparison_status = "inconclusive"
        return _snapshot(
            {
                "schema_version": "1.0",
                "kind": "owner-policy-file-repair-result",
                "application": self._application.to_dict(),
                "application_id": self._application.application_id,
                "session_id": self._session_id,
                "workspace": self._workspace_path,
                "initialization_stage": self._initialization_stage,
                "phase": self._phase,
                "generation": self._generation,
                "closed": self._closed,
                "application_status": self._application_status,
                "restoration_status": self._restoration_status,
                "diff_status": self._diff_status,
                "checks": self._checks,
                "comparison_status": comparison_status,
                "comparison": comparison,
                "file_binding_status": self._file_binding,
                "evidence_status": self._evidence,
                "failure": self._failure,
                "decisions": self._decisions,
                "attempts_consumed": sorted(self._used),
                "completed": self._completed,
                "events": self._events,
                "provider_calls": 0,
                "authorization_status": "unknown",
                "provenance": {"kind": "unauthenticated-host-checkpoint", "authenticated": False},
                "restart_supported": False,
            },
            OwnerPolicyFileResult,
        )

    def _record(self, event):
        if len(self._events) >= MAX_EVENTS:
            self._evidence = "unconfirmed"
            self._critical = self._failure = "evidence-unconfirmed"
            return
        self._events.append(event)
        if self._closed or self._workspace is None or self._evidence != "confirmed":
            return
        try:
            self._workspace.write_record(self.result().payload_json.encode("utf-8"))
        except (OSError, WorkspaceError, ContractError):
            self._evidence = "unconfirmed"
            self._critical = self._failure = "evidence-unconfirmed"
        except BaseException as exc:
            self._evidence = "unconfirmed"
            self._critical = self._failure = "evidence-unconfirmed"
            exc.file_repair_result = self.result()
            raise

    def create_copy(self, *, _parent=None) -> OwnerPolicyFileResult:
        if self._create_used or self._closed:
            self._failure = "copy-already-created" if self._create_used else "session-closed"
            return self.result()
        self._create_used = True
        if self._application.to_dict()["status"] != "registered-change":
            self._failure = "recommendation-has-no-change"
            return self.result()
        if os.name != "posix" or getattr(sys, "frozen", False) or not supported():
            self._failure = "unsupported-platform"
            return self.result()
        stage = None
        try:
            self._context()
            self._workspace = PolicyFileWorkspace(_parent=_parent)
            self._workspace_path = str(self._workspace.path)
            stage = "read-initial-source"
            self._original = self._current = self._workspace.read_policy()
            if self._original.data != self._content()["before"]["text"].encode("utf-8"):
                raise WorkspaceError("Unexpected initial file")
            self._phase, self._generation = "ready-before", 1
            self._file_binding = "confirmed"
            stage = "write-initial-record"
            self._record("copy-created")
            if self._evidence == "unconfirmed":
                self._initialization_stage = stage
                self._critical = self._failure = "initialization-failed"
                self._file_binding = "unconfirmed"
                self._phase = "unconfirmed"
        except WorkspaceInitializationError as exc:
            self._workspace_path = str(exc.created_path)
            self._initialization_stage = exc.initialization_stage
            self._critical = self._failure = "initialization-failed"
            self._file_binding = "unconfirmed"
            self._phase = "unconfirmed"
        except (OSError, WorkspaceError, ContractError):
            self._initialization_stage = stage
            self._critical = self._failure = "initialization-failed"
            self._file_binding = "unconfirmed"
            self._phase = "unconfirmed"
        except BaseException as exc:
            failure = getattr(exc, "workspace_initialization", None)
            if type(failure) is WorkspaceInitializationError:
                self._workspace_path = str(failure.created_path)
                self._initialization_stage = failure.initialization_stage
            else:
                self._initialization_stage = stage
            self._critical = self._failure = "initialization-failed"
            self._file_binding = "unconfirmed"
            self._phase = "unconfirmed"
            exc.file_repair_result = self.result()
            raise
        return self.result()

    def _prerequisite(self, stage):
        if self._closed:
            return "session-closed"
        if self._running:
            return "operation-in-progress"
        if self._critical:
            return self._critical
        if self._workspace is None or self._current is None:
            return "copy-not-created"
        required = "applied-after" if stage in {"after-check", "restore"} else "ready-before"
        if self._phase != required:
            return "wrong-phase"
        if stage in {"diff", "apply"} and "before-check" not in self._completed:
            return "baseline-required"
        if stage == "apply" and self._diff_status != "accepted":
            return "diff-acceptance-required"
        return None

    def _read_tracked(self):
        try:
            current = self._workspace.read_policy()
            if current != self._current:
                raise WorkspaceError("Tracked file changed")
            self._file_binding = "confirmed"
            return current
        except (OSError, WorkspaceError):
            self._file_binding = "unconfirmed"
            self._critical = "file-state-changed"
            raise ContractError("Tracked file changed") from None

    def _prior(self, stage):
        names = {
            "before-check": (),
            "diff": ("before-check",),
            "apply": ("before-check", "diff"),
            "after-check": ("before-check", "diff", "apply"),
            "restore": ("before-check", "diff", "apply"),
        }[stage]
        return {name: self._completed[name] for name in names}

    def _plan(self, stage):
        current = self._read_tracked()
        data = {
            "schema_version": "1.0",
            "kind": "owner-policy-file-plan",
            "stage": stage,
            "session_id": self._session_id,
            "generation": self._generation,
            "application_id": self._application.application_id,
            "application": self._application.to_dict(),
            "workspace": self._workspace_path,
            "root_identity": list(self._workspace.root_identity),
            "file": _file_state(current),
            "prior_completions": self._prior(stage),
            "recipe": self._recipe
            if stage.endswith("check")
            else {
                "version": "1.0",
                "action": stage,
                "max_decision_seconds": MAX_DECISION_SECONDS,
                "atomic_rename_is_compare_and_swap": False,
                "retain_copy": True,
            },
        }
        if stage.endswith("check"):
            candidate = "before" if stage == "before-check" else "after"
            if current.data != self._content()[candidate]["text"].encode("utf-8"):
                raise ContractError("Unexpected registered file state")
            cases = []
            for case in self._content()["cases"]:
                row = {k: case[k] for k in ("case_id", "principal", "report")}
                cases.append({**row, "input_sha256": identity(row)})
            wire = {
                "schema_version": "1.0",
                "check_id": CHECK_ID,
                "session_id": self._session_id,
                "stage": stage,
                "candidate": candidate,
                "file_state_sha256": identity(
                    {"root": data["root_identity"], "file": data["file"]}
                ),
                "policy_source_sha256": sha256(current.data).hexdigest(),
                "source_text": current.data.decode("utf-8"),
                "worker_sha256": WORKER_SHA256,
                "input_sha256": identity(cases),
                "cases": cases,
            }
            plan_id = "owner-file-check-" + identity({**data, "worker_input": wire})
            wire["plan_id"] = plan_id
            if len(canonical(wire).encode("utf-8")) > MAX_INPUT_BYTES:
                raise ContractError("Worker input exceeds budget")
            data["worker_input"] = wire
        else:
            plan_id = "owner-file-action-" + identity(data)
        return _snapshot({**data, "plan_id": plan_id}, OwnerPolicyFilePlan)

    def prepare(self, stage) -> OwnerPolicyFilePlan:
        stage = _stage(stage)
        if stage in self._used:
            raise ContractError("Stage attempt already consumed")
        reason = self._prerequisite(stage)
        if reason:
            raise ContractError("Stage is not available")
        self._context()
        plan = self._plan(stage)
        if stage in self._plans:
            if plan.payload_json != self._plans[stage].payload_json:
                raise ContractError("Stage plan changed")
            return self._plans[stage]
        now = self._time()
        expires = _expiry(now, MAX_DECISION_SECONDS)
        self._plans[stage] = plan
        self._decisions[stage] = {
            "stage": stage,
            "session_id": self._session_id,
            "plan_id": plan.plan_id,
            "choice": "pending",
            "created_at": now,
            "expires_at": expires,
            "reviewer_authenticated": False,
        }
        self._record("plan-" + stage)
        if self._critical:
            raise ContractError("Evidence persistence failed")
        return plan

    def decide(self, stage, choice, *, plan_id, lifetime_seconds=MAX_DECISION_SECONDS):
        stage = _stage(stage)
        if stage in self._used or stage not in self._plans or self._prerequisite(stage):
            raise ContractError("No current unused plan")
        decision = self._decisions[stage]
        now = self._time()
        if (
            decision["choice"] != "pending"
            or not decision["created_at"] <= now < decision["expires_at"]
        ):
            raise ContractError("Only an unexpired pending decision can change")
        if type(choice) is not str or choice not in {
            "pending",
            "approved",
            "declined",
            "cancelled",
        }:
            raise ContractError("Unsupported file action choice")
        if type(plan_id) is not str or plan_id != self._plans[stage].plan_id:
            raise ContractError("Decision is for another plan")
        duration = _finite(lifetime_seconds)
        if not 0 < duration <= MAX_DECISION_SECONDS:
            raise ContractError("Invalid decision lifetime")
        self._context()
        if self._plan(stage).payload_json != self._plans[stage].payload_json:
            raise ContractError("Stale decision plan")
        now = self._time()
        if not now < decision["expires_at"]:
            raise ContractError("Pending decision expired during revalidation")
        expires = min(decision["expires_at"], _expiry(now, duration))
        self._decisions[stage] = {
            **decision,
            "choice": choice,
            "created_at": now,
            "expires_at": expires,
        }
        self._record("decision-" + stage + "-" + choice)
        if self._critical:
            raise ContractError("Evidence persistence failed")
        return _snapshot(self._decisions[stage])

    def _guard(self, stage):
        if len(self._events) >= MAX_EVENTS:
            self._evidence = "unconfirmed"
            self._critical = self._failure = "evidence-unconfirmed"
        if self._critical or self._evidence != "confirmed":
            return self._critical or "evidence-unconfirmed"
        if self._closed:
            return "session-closed"
        self._context()
        decision = self._decisions[stage]
        if decision["choice"] != "approved":
            return "decision-" + decision["choice"]
        try:
            now = self._time()
        except (ContractError, ValueError, TypeError, OverflowError):
            return "invalid-decision-time"
        if not decision["created_at"] <= now < decision["expires_at"]:
            return "decision-expired"
        if self._plan(stage).payload_json != self._plans[stage].payload_json:
            return "stale-plan"
        # The bounded read above is synchronous and has no hard wall-clock cap.
        # Recheck the choice after I/O, before the caller performs its effect.
        now = self._time()
        if not decision["created_at"] <= now < decision["expires_at"]:
            return "decision-expired"
        return None

    def _claim(self, stage):
        if stage in self._used:
            return "attempt-already-consumed"
        self._used.add(stage)
        if len(self._events) >= MAX_EVENTS:
            self._evidence = "unconfirmed"
            self._critical = self._failure = "evidence-unconfirmed"
        reason = self._prerequisite(stage)
        if reason:
            return reason
        if stage not in self._plans:
            return "plan-required"
        try:
            return self._guard(stage)
        except (ContractError, OSError, WorkspaceError):
            return self._critical or "invalid-context"

    def _finish(self, stage, reason=None):
        if reason == "attempt-already-consumed":
            return _snapshot({**self.result().to_dict(), "failure": reason}, OwnerPolicyFileResult)
        self._failure = reason
        self._record("result-" + stage + ("-" + reason if reason else "-completed"))
        return self.result()

    def accept_diff(self):
        reason = self._claim("diff")
        if reason is None:
            self._diff_status = "accepted"
            self._completed["diff"] = "owner-file-diff-" + identity(self._decisions["diff"])
        return self._finish("diff", reason)

    def _write(self, stage):
        reason = self._claim(stage)
        if reason:
            return self._finish(stage, reason)
        candidate = "after" if stage == "apply" else "before"

        def guard():
            reason = self._guard(stage)
            if reason:
                raise ContractError("File write decision is no longer current")

        def before_commit():
            decision = self._decisions[stage]
            now = self._time()
            if not decision["created_at"] <= now < decision["expires_at"]:
                raise ContractError("File write decision expired before replacement")

        try:
            current = self._workspace.replace_policy(
                self._current,
                self._content()[candidate]["text"].encode("utf-8"),
                guard=guard,
                before_commit=before_commit,
            )
            self._current = current
            self._phase = "applied-after" if stage == "apply" else "restored-before"
            self._generation += 1
            self._file_binding = "confirmed"
            if stage == "apply":
                self._application_status = "completed"
            else:
                self._restoration_status = "completed"
            self._completed[stage] = "owner-file-write-" + identity(
                {
                    "plan_id": self._plans[stage].plan_id,
                    "file": _file_state(current),
                    "generation": self._generation,
                }
            )
        except CommittedWriteError:
            self._phase = "unconfirmed"
            self._file_binding = "unconfirmed"
            self._critical = reason = "committed-state-unconfirmed"
            if stage == "apply":
                self._application_status = "state-unconfirmed"
            else:
                self._restoration_status = "state-unconfirmed"
        except (ContractError, OSError, WorkspaceError):
            with suppress(ContractError):
                self._read_tracked()
            reason = self._critical or "write-failed"
            if stage == "apply":
                self._application_status = "failed"
            else:
                self._restoration_status = "failed"
        except BaseException as exc:
            self._phase = "unconfirmed"
            self._file_binding = "unconfirmed"
            self._critical = self._failure = "committed-state-unconfirmed"
            if stage == "apply":
                self._application_status = "state-unconfirmed"
            else:
                self._restoration_status = "state-unconfirmed"
            # Preserve the original interruption if retaining its checkpoint is interrupted too.
            with suppress(BaseException):
                self._record("interrupted-" + stage)
            exc.file_repair_result = self.result()
            raise
        return self._finish(stage, reason)

    def apply(self):
        return self._write("apply")

    def restore(self):
        return self._write("restore")

    async def run_check(self, stage):
        stage = _stage(stage)
        if stage not in {"before-check", "after-check"}:
            raise ContractError("Expected a file check stage")
        reason = self._claim(stage)
        if reason == "attempt-already-consumed":
            return self._finish(stage, reason)
        plan = self._plans.get(stage)
        transport = None
        observed = None
        cancellation = None
        owns_running = reason is None
        if owns_running:
            self._running = True
        try:
            if reason is None:
                if os.name != "posix" or getattr(sys, "frozen", False):
                    reason = "unsupported-platform"
                else:
                    launch_refusal = None

                    def before_launch():
                        nonlocal launch_refusal
                        launch_refusal = self._guard(stage)
                        if launch_refusal:
                            raise ContractError("Check decision is no longer current")

                    try:
                        transport = await _run_worker(
                            plan.to_dict()["worker_input"], before_launch=before_launch
                        )
                        if launch_refusal is not None:
                            reason = launch_refusal
                    except asyncio.CancelledError as exc:
                        cancellation = exc
                        transport = getattr(exc, "worker_transport", None)
                        if _transport_data(transport) is None:
                            transport = _unknown_transport("cancelled")
                        reason = "cancelled"
                    except Exception:
                        transport = _unknown_transport("worker-process-error")
                        reason = "worker-process-error"
                if reason is None:
                    reason = _transport_reason(transport)
                    if reason == "invalid-worker-transport":
                        transport = _unknown_transport(reason)
                if reason is None:
                    try:
                        observed = _observations(transport.output, plan.to_dict()["worker_input"])
                    except (ContractError, ValueError, UnicodeError, TypeError):
                        reason = "invalid-worker-output"
                try:
                    self._context()
                    self._read_tracked()
                    if self._critical or self._evidence != "confirmed":
                        reason = self._critical or "evidence-unconfirmed"
                        observed = None
                except (ContractError, OSError, WorkspaceError):
                    reason = self._critical or "invalid-context"
                    observed = None
        finally:
            if owns_running:
                self._running = False
        candidate = "before" if stage == "before-check" else "after"
        if observed is not None:
            reason = (
                "cases-match"
                if observed == [c["expected"] == "allow" for c in self._content()["cases"]]
                else "case-mismatch"
            )
        check = {
            "stage": stage,
            "candidate": candidate,
            "session_id": self._session_id,
            "plan_id": plan.plan_id if plan else None,
            "plan": plan.to_dict() if plan else None,
            "source_sha256": self._content()[candidate]["sha256"],
            "file_state_sha256": plan.to_dict()["worker_input"]["file_state_sha256"]
            if plan
            else None,
            "worker_sha256": WORKER_SHA256,
            "recipe_sha256": identity(self._recipe),
            "observations": observed,
            "execution_status": "completed"
            if observed is not None
            else ("cancelled" if cancellation else "failed" if _started(transport) else "not-run"),
            "comparison_status": ("passed" if reason == "cases-match" else "failed")
            if observed is not None
            else "not-evaluated",
            "reason": reason,
            "transport": _transport_data(transport),
        }
        self._checks[candidate] = check
        if observed is not None:
            self._completed[stage] = "owner-file-observation-" + identity(check)
        result = self._finish(stage, None if observed is not None else reason)
        if cancellation is not None:
            cancellation.file_repair_result = result
            raise cancellation
        return result

    def close(self):
        if self._running:
            raise ContractError("Cannot close an active check")
        if self._workspace is not None:
            self._workspace.close()
        self._closed = True


def _transport_data(value):
    if type(value) is not WorkerTransport:
        return None
    data = {
        name: getattr(value, name)
        for name in (
            "exit_code",
            "reason",
            "child_cleanup_status",
            "workspace_cleanup_status",
            "launch_status",
        )
    }
    if (
        type(value.output) is not bytes
        or len(value.output) > MAX_OUTPUT_BYTES
        or (data["exit_code"] is not None and type(data["exit_code"]) is not int)
        or (data["reason"] is not None and data["reason"] not in _REASONS)
        or data["child_cleanup_status"] not in {"confirmed", "unconfirmed", "not-needed"}
        or data["workspace_cleanup_status"] not in {"confirmed", "unconfirmed", "not-needed"}
        or data["launch_status"] not in {"started", "ambiguous", "not-attempted", "no-child"}
    ):
        return None
    return data


def _unknown_transport(reason):
    return WorkerTransport(b"", None, reason, "unconfirmed", "unconfirmed", "ambiguous")


def _started(value):
    data = _transport_data(value)
    return data is not None and data["launch_status"] in {"started", "ambiguous"}


def _transport_reason(value):
    data = _transport_data(value)
    if data is None:
        return "invalid-worker-transport"
    if data["reason"] is not None:
        return data["reason"]
    if (
        data["child_cleanup_status"] != "confirmed"
        or data["workspace_cleanup_status"] != "confirmed"
    ):
        return "cleanup-unconfirmed"
    if data["launch_status"] != "started":
        return "invalid-worker-transport"
    return "worker-exit-error" if data["exit_code"] != 0 else None


def _observations(raw, wire):
    data = decode(raw.decode("utf-8"))
    _object(data, set(wire) - {"source_text"})
    expected = {k: v for k, v in wire.items() if k not in {"source_text", "cases"}}
    if canonical({k: data[k] for k in expected}) != canonical(expected):
        raise ContractError("Worker output binding mismatch")
    cases = data["cases"]
    if type(cases) is not list or len(cases) != 8:
        raise ContractError("Invalid observation count")
    observed = []
    for case, original in zip(cases, wire["cases"], strict=True):
        _object(case, {"case_id", "input_sha256", "observed"})
        if (
            case["case_id"] != original["case_id"]
            or case["input_sha256"] != original["input_sha256"]
            or type(case["observed"]) is not bool
        ):
            raise ContractError("Invalid bound observation")
        observed.append(case["observed"])
    return observed


def validate_owner_policy_file_result(raw: str) -> OwnerPolicyFileResult:
    """Check closed data and current bindings, never attest or restore a live session."""
    import stat as validator_stat

    def require(condition, message="Inconsistent file checkpoint"):
        if not condition:
            raise ContractError(message)

    def enum(value, allowed):
        return type(value) is str and value in allowed

    def identifier(value, prefix):
        return type(value) is str and re.fullmatch(prefix + r"[a-f0-9]{64}", value) is not None

    def finite_nonnegative(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    def transport_record(value):
        if value is None:
            return None
        _object(
            value,
            {
                "exit_code",
                "reason",
                "child_cleanup_status",
                "workspace_cleanup_status",
                "launch_status",
            },
        )
        launch = value["launch_status"]
        child = value["child_cleanup_status"]
        workspace = value["workspace_cleanup_status"]
        code = value["exit_code"]
        reason = value["reason"]
        require(enum(launch, {"started", "ambiguous", "not-attempted", "no-child"}))
        require(enum(child, {"confirmed", "unconfirmed", "not-needed"}))
        require(enum(workspace, {"confirmed", "unconfirmed", "not-needed"}))
        require(code is None or type(code) is int)
        require(
            reason is None
            or enum(
                reason,
                {
                    "worker-input-error",
                    "worker-process-error",
                    "worker-exit-error",
                    "timeout",
                    "output-limit",
                    "cleanup-unconfirmed",
                    "cancelled",
                    "unsupported-platform",
                    "invalid-worker-transport",
                },
            )
        )
        if launch in {"not-attempted", "no-child"}:
            require(child == "not-needed" and code is None)
        elif launch == "ambiguous":
            require(child == "unconfirmed" and code is None)
        else:
            require(child != "not-needed")
            if child == "confirmed":
                require(type(code) is int)
        if reason is None:
            require(
                launch == "started" and child == workspace == "confirmed" and code == 0,
                "Incomplete successful transport",
            )
        elif reason in {"worker-input-error", "unsupported-platform"}:
            require(launch == "not-attempted" and child == workspace == "not-needed")
        elif reason == "worker-exit-error":
            require(launch == "started" and type(code) is int and code != 0)
        elif reason == "cleanup-unconfirmed":
            require("unconfirmed" in {child, workspace})
        return value

    def check_plan(plan, stage, data, application, recipe):
        _object(
            plan,
            {
                "schema_version",
                "kind",
                "stage",
                "session_id",
                "generation",
                "application_id",
                "application",
                "workspace",
                "root_identity",
                "file",
                "prior_completions",
                "recipe",
                "worker_input",
                "plan_id",
            },
        )
        candidate = "before" if stage == "before-check" else "after"
        generation = 1 if candidate == "before" else 2
        content = application.to_dict()["request"]["content"]
        require(
            plan["schema_version"] == "1.0"
            and plan["kind"] == "owner-policy-file-plan"
            and plan["stage"] == stage
            and plan["session_id"] == data["session_id"]
            and type(plan["generation"]) is int
            and plan["generation"] == generation
            and plan["application_id"] == application.application_id
            and canonical(plan["application"]) == application.payload_json
            and plan["workspace"] == data["workspace"]
            and data["workspace"] is not None
            and canonical(plan["recipe"]) == canonical(recipe)
        )
        root = plan["root_identity"]
        require(
            type(root) is list
            and len(root) == 5
            and all(type(value) is int and value >= 0 for value in root)
        )
        require(validator_stat.S_ISDIR(root[2]) and validator_stat.S_IMODE(root[2]) == 0o700)
        state = _object(plan["file"], {"filename", "sha256", "byte_count", "identity"})
        stamp = state["identity"]
        source = content[candidate]["text"]
        source_bytes = source.encode("utf-8")
        require(
            state["filename"] == "policy.py"
            and state["sha256"] == content[candidate]["sha256"]
            and type(state["byte_count"]) is int
            and state["byte_count"] == len(source_bytes) <= _SOURCE_LIMIT
            and type(stamp) is list
            and len(stamp) == 9
            and all(type(value) is int and value >= 0 for value in stamp)
        )
        require(
            validator_stat.S_ISREG(stamp[2])
            and validator_stat.S_IMODE(stamp[2]) == 0o600
            and stamp[0] == root[0]
            and stamp[3] == root[3]
            and stamp[5] == 1
            and stamp[6] == len(source_bytes)
        )
        prior_names = () if candidate == "before" else ("before-check", "diff", "apply")
        prior = {name: data["completed"][name] for name in prior_names}
        require(canonical(plan["prior_completions"]) == canonical(prior))
        rows = []
        for case in content["cases"]:
            row = {key: case[key] for key in ("case_id", "principal", "report")}
            rows.append({**row, "input_sha256": identity(row)})
        wire = {
            "schema_version": "1.0",
            "check_id": CHECK_ID,
            "session_id": data["session_id"],
            "stage": stage,
            "candidate": candidate,
            "file_state_sha256": identity({"root": root, "file": state}),
            "policy_source_sha256": sha256(source_bytes).hexdigest(),
            "source_text": source,
            "worker_sha256": WORKER_SHA256,
            "input_sha256": identity(rows),
            "cases": rows,
        }
        base = {key: value for key, value in plan.items() if key not in {"plan_id", "worker_input"}}
        plan_id = "owner-file-check-" + identity({**base, "worker_input": wire})
        wire["plan_id"] = plan_id
        require(
            plan["plan_id"] == plan_id
            and canonical(plan["worker_input"]) == canonical(wire)
            and len(canonical(wire).encode("utf-8")) <= MAX_INPUT_BYTES,
            "File plan or captured-source binding mismatch",
        )
        return plan

    try:
        data = decode(raw)
        _object(
            data,
            {
                "schema_version",
                "kind",
                "application",
                "application_id",
                "session_id",
                "workspace",
                "phase",
                "generation",
                "closed",
                "application_status",
                "restoration_status",
                "diff_status",
                "checks",
                "comparison_status",
                "comparison",
                "file_binding_status",
                "evidence_status",
                "initialization_stage",
                "failure",
                "decisions",
                "attempts_consumed",
                "completed",
                "events",
                "provider_calls",
                "authorization_status",
                "provenance",
                "restart_supported",
            },
        )
        application = validate_owner_policy_file_repair(canonical(data["application"]))
        require(len(application.payload_json.encode("utf-8")) <= MAX_APPLICATION_BYTES)
        require(
            data["schema_version"] == "1.0"
            and data["kind"] == "owner-policy-file-repair-result"
            and data["application_id"] == application.application_id
            and type(data["session_id"]) is str
            and re.fullmatch(r"[a-f0-9]{32}", data["session_id"]) is not None
            and type(data["closed"]) is bool
            and data["restart_supported"] is False
            and type(data["provider_calls"]) is int
            and data["provider_calls"] == 0
            and data["authorization_status"] == "unknown"
            and canonical(data["provenance"])
            == canonical(
                {
                    "kind": "unauthenticated-host-checkpoint",
                    "authenticated": False,
                }
            )
            and enum(
                data["phase"],
                {
                    "not-created",
                    "ready-before",
                    "applied-after",
                    "restored-before",
                    "unconfirmed",
                },
            )
            and type(data["generation"]) is int
            and 0 <= data["generation"] <= 3
            and enum(
                data["application_status"], {"not-run", "completed", "failed", "state-unconfirmed"}
            )
            and enum(
                data["restoration_status"], {"not-run", "completed", "failed", "state-unconfirmed"}
            )
            and enum(data["diff_status"], {"not-accepted", "accepted"})
            and enum(data["file_binding_status"], {"not-evaluated", "confirmed", "unconfirmed"})
            and enum(data["evidence_status"], {"confirmed", "unconfirmed"})
            and (
                data["initialization_stage"] is None
                or enum(data["initialization_stage"], WorkspaceInitializationError.STAGES)
            )
            and (data["failure"] is None or enum(data["failure"], _REASONS))
        )
        workspace = data["workspace"]
        require(
            workspace is None
            or (
                type(workspace) is str
                and workspace.startswith("/")
                and len(workspace) <= 4096
                and not any(ord(character) < 32 for character in workspace)
            )
        )
        content = application.to_dict()["request"]["content"]
        recipe = _recipe()
        decisions = data["decisions"]
        consumed = data["attempts_consumed"]
        completed = data["completed"]
        require(type(decisions) is dict and set(decisions) <= set(STAGES))
        require(
            type(consumed) is list
            and all(enum(stage, STAGES) for stage in consumed)
            and sorted(set(consumed)) == consumed
        )
        require(type(completed) is dict and set(completed) <= set(STAGES))
        require(set(completed) <= set(consumed) & set(decisions))
        if data["initialization_stage"] is not None:
            require(
                workspace is not None
                and data["phase"] == "unconfirmed"
                and data["generation"] in {0, 1}
                and data["application_status"] == data["restoration_status"] == "not-run"
                and not decisions
                and not completed
            )
        for stage, decision in decisions.items():
            _object(
                decision,
                {
                    "stage",
                    "session_id",
                    "plan_id",
                    "choice",
                    "created_at",
                    "expires_at",
                    "reviewer_authenticated",
                },
            )
            prefix = "owner-file-check-" if stage.endswith("check") else "owner-file-action-"
            require(
                decision["stage"] == stage
                and decision["session_id"] == data["session_id"]
                and identifier(decision["plan_id"], prefix)
                and enum(decision["choice"], {"pending", "approved", "declined", "cancelled"})
                and decision["reviewer_authenticated"] is False
                and finite_nonnegative(decision["created_at"])
                and finite_nonnegative(decision["expires_at"])
                and 0 < decision["expires_at"] - decision["created_at"] <= MAX_DECISION_SECONDS
            )
            require(workspace is not None)
            if stage != "before-check":
                require("before-check" in completed)
            if stage == "apply":
                require("diff" in completed)
            elif stage in {"after-check", "restore"}:
                require({"diff", "apply"} <= set(completed))
        for stage, completion in completed.items():
            prefix = (
                "owner-file-observation-"
                if stage.endswith("check")
                else "owner-file-diff-"
                if stage == "diff"
                else "owner-file-write-"
            )
            require(identifier(completion, prefix) and decisions[stage]["choice"] == "approved")
            if stage == "diff":
                require(completion == "owner-file-diff-" + identity(decisions[stage]))
        _object(data["checks"], {"before", "after"})
        for candidate, check in data["checks"].items():
            stage = candidate + "-check"
            if check is None:
                require(stage not in completed)
                continue
            _object(
                check,
                {
                    "stage",
                    "candidate",
                    "session_id",
                    "plan",
                    "plan_id",
                    "source_sha256",
                    "file_state_sha256",
                    "worker_sha256",
                    "recipe_sha256",
                    "observations",
                    "execution_status",
                    "comparison_status",
                    "reason",
                    "transport",
                },
            )
            require(
                check["candidate"] == candidate
                and check["stage"] == stage
                and check["session_id"] == data["session_id"]
                and stage in consumed
                and check["source_sha256"] == content[candidate]["sha256"]
                and check["worker_sha256"] == WORKER_SHA256
                and check["recipe_sha256"] == identity(recipe)
                and enum(check["reason"], _REASONS)
                and enum(check["execution_status"], {"completed", "not-run", "failed", "cancelled"})
            )
            if check["plan"] is None:
                require(
                    check["plan_id"] is None
                    and check["file_state_sha256"] is None
                    and stage not in decisions
                )
            else:
                plan = check_plan(check["plan"], stage, data, application, recipe)
                require(
                    stage in decisions
                    and check["plan_id"] == plan["plan_id"]
                    and decisions[stage]["plan_id"] == plan["plan_id"]
                    and check["file_state_sha256"] == plan["worker_input"]["file_state_sha256"]
                )
            diagnostic = transport_record(check["transport"])
            observations = check["observations"]
            if observations is not None:
                require(
                    type(observations) is list
                    and len(observations) == 8
                    and all(type(value) is bool for value in observations)
                    and check["plan"] is not None
                    and decisions[stage]["choice"] == "approved"
                )
                matched = observations == [case["expected"] == "allow" for case in content["cases"]]
                require(
                    check["execution_status"] == "completed"
                    and check["comparison_status"] == ("passed" if matched else "failed")
                    and check["reason"] == ("cases-match" if matched else "case-mismatch")
                    and diagnostic is not None
                    and diagnostic["reason"] is None
                    and completed.get(stage) == "owner-file-observation-" + identity(check)
                )
            else:
                require(
                    stage not in completed
                    and check["comparison_status"] == "not-evaluated"
                    and check["execution_status"] != "completed"
                    and check["reason"] not in {"cases-match", "case-mismatch"}
                )
                started = diagnostic is not None and diagnostic["launch_status"] in {
                    "started",
                    "ambiguous",
                }
                if check["execution_status"] == "failed":
                    require(started)
                elif check["execution_status"] == "not-run":
                    require(not started)
                else:
                    require(diagnostic is not None and diagnostic["reason"] == "cancelled")
                if check["reason"] in {
                    "decision-pending",
                    "decision-declined",
                    "decision-cancelled",
                }:
                    require(
                        stage in decisions
                        and diagnostic is None
                        and decisions[stage]["choice"] == check["reason"].removeprefix("decision-")
                    )
                if diagnostic is not None:
                    require(check["plan"] is not None and decisions[stage]["choice"] == "approved")
        require((data["diff_status"] == "accepted") == ("diff" in completed))
        require((data["application_status"] == "completed") == ("apply" in completed))
        require((data["restoration_status"] == "completed") == ("restore" in completed))
        if completed:
            require(
                application.to_dict()["status"] == "registered-change" and workspace is not None
            )
        if "diff" in completed:
            require("before-check" in completed)
        if "apply" in completed:
            require({"before-check", "diff"} <= set(completed))
        if "restore" in completed:
            require("apply" in completed)
        phase = data["phase"]
        generation = data["generation"]
        applied = data["application_status"]
        restored = data["restoration_status"]
        if phase == "not-created":
            require(
                generation == 0
                and workspace is None
                and not decisions
                and not completed
                and applied == restored == "not-run"
                and data["file_binding_status"] == "not-evaluated"
            )
        elif phase == "ready-before":
            require(
                generation == 1
                and workspace is not None
                and applied in {"not-run", "failed"}
                and restored == "not-run"
                and data["file_binding_status"] != "not-evaluated"
            )
        elif phase == "applied-after":
            require(
                generation == 2
                and workspace is not None
                and applied == "completed"
                and restored in {"not-run", "failed"}
                and data["file_binding_status"] != "not-evaluated"
            )
        elif phase == "restored-before":
            require(
                generation == 3
                and workspace is not None
                and applied == restored == "completed"
                and data["file_binding_status"] != "not-evaluated"
            )
        else:
            require(data["file_binding_status"] == "unconfirmed")
            require(
                (generation == 0 and applied == restored == "not-run" and not completed)
                or (
                    generation == 1
                    and applied == restored == "not-run"
                    and not decisions
                    and not completed
                    and data["initialization_stage"] == "write-initial-record"
                    and data["evidence_status"] == "unconfirmed"
                )
                or (
                    generation == 1
                    and applied == "state-unconfirmed"
                    and restored == "not-run"
                    and {"before-check", "diff"} <= set(completed)
                )
                or (generation == 2 and applied == "completed" and restored == "state-unconfirmed")
            )
        if "after-check" in completed:
            require("apply" in completed)
        after = data["checks"]["after"]
        if after is not None and after["plan"] is not None:
            file_state = after["plan"]["file"]
            require(
                completed["apply"]
                == "owner-file-write-"
                + identity(
                    {
                        "plan_id": decisions["apply"]["plan_id"],
                        "file": file_state,
                        "generation": 2,
                    }
                )
            )
        comparison_status, comparison = _comparison(content, data["checks"])
        if comparison_status == "passed" and (
            data["file_binding_status"] == "unconfirmed" or data["evidence_status"] == "unconfirmed"
        ):
            comparison_status = "inconclusive"
        require(
            data["comparison_status"] == comparison_status
            and canonical(data["comparison"]) == canonical(comparison)
        )
        events = data["events"]
        event_values = {"copy-created", "interrupted-apply", "interrupted-restore"}
        for stage in STAGES:
            event_values.add("plan-" + stage)
            event_values.update(
                "decision-" + stage + "-" + choice
                for choice in (
                    "pending",
                    "approved",
                    "declined",
                    "cancelled",
                )
            )
            event_values.update(
                "result-" + stage + "-" + reason for reason in _REASONS | {"completed"}
            )
        require(
            type(events) is list
            and len(events) <= MAX_EVENTS
            and all(enum(event, event_values) for event in events)
        )
        return _snapshot(data, OwnerPolicyFileResult)
    except ContractError:
        raise
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        UnicodeError,
        RecursionError,
    ):
        raise ContractError("Invalid file checkpoint shape or binding") from None
