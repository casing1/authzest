"""Private one-use decisions for a fresh copy and opt-in fixed runtime flow.

These in-memory decisions are trusted caller coordination, not authenticated
consent, runtime evidence, a resumable journal or permission to apply source.
The default remains disabled. Only an explicit trusted runtime configuration can
connect the fixed phase and guarded copy-only transitions; JSON is never imported
as a baseline, runtime acceptance, or source-write capability.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import inspect
import math
import re
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from authzest.codex.contracts import canonical, decode, identity
from authzest.codex.generated_repair import build_generated_repair_request
from authzest.runner._generated_repair_phase import (
    MAX_PHASE_RESULT_BYTES,
    GeneratedRepairPhaseResult,
    PhaseError,
    SessionEvidenceBudget,
    execute_generated_repair_phase,
)
from authzest.runner._generated_repair_relay import compare_generated_repair_relay_capture
from authzest.runner._generated_repair_runtime_profile import (
    RuntimeProfile,
    validate_runtime_profile,
)
from authzest.runner._generated_repair_workspace import (
    FileState,
    GeneratedRepairWorkspace,
    WorkspaceInitializationError,
)
from authzest.runner.generated_repair_controls import build_generated_repair_controls
from authzest.runner.generated_repair_verification import (
    DisabledGeneratedRepairExecutor,
    GeneratedRepairExecutorReadiness,
    _checked_preview,
    validate_generated_repair_executor_readiness,
)

MAX_PLAN_BYTES = 262_144
MAX_RESULT_BYTES = 65_536
MAX_HISTORY_ITEMS = 32
MAX_DECISION_SECONDS = 300
_STAGES = ("copy", "before")
_LATER_STAGES = ("source-diff", "source-apply", "after", "restore")
_FILE_NAMES = (
    "app.py",
    "tests/test_generated_ownership.py",
    "before.txt",
    "after.txt",
    "test.txt",
    "record.json",
)


class GeneratedRepairSessionError(RuntimeError):
    """A current, one-use offline session precondition was not met."""


@dataclass(frozen=True, slots=True)
class GeneratedRepairSessionPlan:
    """Detached full review material, not importable execution authority."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return "generated-repair-session-plan-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class GeneratedRepairSessionResult:
    """Historical bookkeeping only; reading this never observes files or time."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


def _snapshot(data: dict, kind, maximum: int):
    raw = canonical(data)
    if len(raw.encode("utf-8")) > maximum:
        raise GeneratedRepairSessionError("Offline session snapshot exceeds its fixed budget")
    decode(raw)
    return kind(raw)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _deadline(now: float, duration: float) -> float:
    end = now + duration
    if not math.isfinite(end) or end <= now:
        raise GeneratedRepairSessionError("Decision deadline is not representable")
    # Round toward the earlier representable time, never extending authority.
    if end - now > duration:
        end = math.nextafter(end, -math.inf)
    if end <= now or end - now > duration:
        raise GeneratedRepairSessionError("Decision deadline is not representable")
    return end


class GeneratedRepairSession:
    """Keep default preparation inert; explicitly bind a trusted active runtime.

    The synchronous clock and ``_parent`` are trusted test seams. This object
    The optional runtime guard must be trusted synchronous coordination for
    reviewed provisioned images/capabilities and current private profile input.
    Supplying a profile alone cannot activate execution. Files and records are
    retained on close and on uncertain initialization; no checkpoint importer exists.
    """

    def __init__(
        self,
        preview,
        *,
        runtime_profile=None,
        runtime_guard=None,
        clock: Callable[[], float] = monotonic,
    ):
        self._busy = True
        self._closed = False
        self._clock_failed = False
        self._last_time: float | None = None
        self._clock = clock
        self._workspace: GeneratedRepairWorkspace | None = None
        self._plans: dict[str, GeneratedRepairSessionPlan] = {}
        self._history: list[dict] = []
        self._profile = None
        self._runtime_guard = None
        self._phase_results = {"before": None, "after": None}
        self._evidence_budget = None
        self._baseline = False
        self._diff_acceptance = None
        self._source_application = "not-run"
        self._restoration_status = "not-run"
        self._cleanup_unconfirmed = False
        self._expected_workspace_state = "ready-before"
        if runtime_profile is not None:
            if (
                type(runtime_profile) is not RuntimeProfile
                or not callable(runtime_guard)
                or inspect.iscoroutinefunction(runtime_guard)
            ):
                raise GeneratedRepairSessionError("A trusted synchronous runtime guard is required")
            self._profile = validate_runtime_profile(runtime_profile.payload_json)
            self._profile_id = self._profile.profile_id
            self._runtime_guard = runtime_guard
            self._evidence_budget = SessionEvidenceBudget()
            # Keep bounded recovery/result capacity available even if a later
            # phase consumes the remaining ordinary evidence allowance.
            self._evidence_budget.charge(MAX_RESULT_BYTES + MAX_PLAN_BYTES)
        elif runtime_guard is not None:
            raise GeneratedRepairSessionError("Runtime guard requires an explicit runtime profile")
        self._supported_stages = _STAGES + _LATER_STAGES if self._profile is not None else _STAGES
        self._stages = {
            stage: {
                "plan_id": None,
                "decision": "pending",
                "decided_at": None,
                "effective_expires_at": None,
                "expired": False,
                "attempted": False,
                "dispatched": False,
                "status": "not-run",
                "reason": None,
            }
            for stage in self._supported_stages
        }
        self._workspace_result = {
            "path": None,
            "state": "not-created",
            "initialization_stage": None,
            "file_states": {},
            "descriptor_cleanup_confirmed": None,
        }
        self._preparation_status = "not-run"
        self._readiness = None
        try:
            self._preview = _checked_preview(preview)
            self._preview_id = self._preview.verification_preview_id
            self._nonce = uuid.uuid4().hex
            if not callable(clock) or inspect.iscoroutinefunction(clock):
                raise GeneratedRepairSessionError("A synchronous monotonic clock is required")
            self._now()
        finally:
            self._busy = False

    @contextmanager
    def _operation(self):
        if self._busy:
            raise GeneratedRepairSessionError("Reentrant offline session operation is refused")
        if self._closed:
            raise GeneratedRepairSessionError("Offline session is closed")
        self._busy = True
        try:
            yield
        finally:
            self._busy = False

    def _now(self) -> float:
        if self._clock_failed:
            raise GeneratedRepairSessionError("Offline session clock is unconfirmed")
        try:
            value = self._clock()
            if inspect.iscoroutine(value):
                value.close()
            if type(value) not in (int, float):
                raise GeneratedRepairSessionError("Clock must return a finite nonnegative number")
            now = float(value)
            if not math.isfinite(now) or now < 0:
                raise GeneratedRepairSessionError("Clock must return a finite nonnegative number")
            _deadline(now, MAX_DECISION_SECONDS)
            if self._last_time is not None and now < self._last_time:
                raise GeneratedRepairSessionError("Clock moved backwards")
            self._last_time = now
            return now
        except BaseException as exc:
            self._clock_failed = True
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, GeneratedRepairSessionError):
                raise
            raise GeneratedRepairSessionError("Offline session clock failed") from exc

    def _check_context(self) -> None:
        checked = _checked_preview(self._preview)
        if (
            checked.payload_json != self._preview.payload_json
            or checked.verification_preview_id != self._preview_id
        ):
            raise GeneratedRepairSessionError("Current verification context changed")
        if self._profile is not None:
            checked_profile = validate_runtime_profile(self._profile.payload_json)
            if (
                checked_profile.payload_json != self._profile.payload_json
                or checked_profile.profile_id != self._profile_id
            ):
                raise GeneratedRepairSessionError("Current runtime profile changed")
            answer = self._runtime_guard()
            if inspect.iscoroutine(answer):
                answer.close()
            if answer is not None:
                raise GeneratedRepairSessionError("Runtime guard must synchronously return None")

    def _stage(self, stage: str) -> str:
        if type(stage) is not str:
            raise GeneratedRepairSessionError("Unknown offline session stage")
        if stage in _LATER_STAGES and self._profile is None:
            raise GeneratedRepairSessionError("runtime-not-implemented")
        if stage not in self._supported_stages:
            raise GeneratedRepairSessionError("Unknown offline session stage")
        return stage

    def _event(self, stage: str, event: str) -> None:
        if len(self._history) >= MAX_HISTORY_ITEMS:
            raise GeneratedRepairSessionError("Offline session history is full")
        self._history.append({"stage": stage, "event": event})

    def _require_change(self) -> None:
        if self._preview.to_dict()["proposal_status"] != "proposed-change":
            raise GeneratedRepairSessionError("Only a current proposed change can prepare a copy")

    def _manifest(self) -> dict:
        try:
            return self._capture_manifest()
        except BaseException:
            # Preserve observed integrity failures even when preparation or a
            # decision raises before any stage action has been consumed.
            if (
                self._workspace is not None
                and self._workspace.state != self._expected_workspace_state
            ):
                self._workspace_result["state"] = "state-unconfirmed"
            raise

    def _capture_manifest(self) -> dict:
        copy = self._workspace
        if copy is None or copy.state != self._expected_workspace_state:
            raise GeneratedRepairSessionError("A confirmed current private copy is required")
        source, test, record = copy.read_source(), copy.read_test(), copy.read_record()
        if any(type(state) is not FileState for state in (source, test, record)):
            raise GeneratedRepairSessionError("Unexpected captured file state")
        data = decode(record.data.decode("utf-8"))
        expected_keys = {
            "schema_version",
            "kind",
            "verification_preview_id",
            "hashes",
            "phase",
            "pending_operation",
            "directories",
            "files",
            "source_application",
            "test_materialization",
            "restoration",
            "execution_status",
            "authorization_status",
            "approval",
            "verified_fix",
        }
        if set(data) != expected_keys or any(
            data[key] != value
            for key, value in {
                "schema_version": "1.0",
                "kind": "generated-repair-private-workspace-record",
                "verification_preview_id": self._preview_id,
                "phase": self._expected_workspace_state,
                "pending_operation": None,
                "source_application": "not-run"
                if self._expected_workspace_state == "ready-before"
                else "applied-copy-only",
                "test_materialization": "materialized-private-copy",
                "restoration": "restored-before"
                if self._expected_workspace_state == "restored-before"
                else "not-run",
                "execution_status": "not-run",
                "authorization_status": "unknown",
                "approval": "not-provided",
                "verified_fix": False,
            }.items()
        ):
            raise GeneratedRepairSessionError(
                "Private copy journal does not describe this baseline"
            )
        before = build_generated_repair_request().to_dict()["scenario"]["source"]["text"].encode()
        proposal = self._preview.to_dict()["proposal_preview"]["proposal"]["proposal"]
        expected_hashes = {
            "before": _sha(before),
            "after": _sha(proposal["after_text"].encode()),
            "test": _sha(proposal["test_text"].encode()),
        }
        directories, files = data["directories"], data["files"]
        if (
            data["hashes"] != expected_hashes
            or type(directories) is not dict
            or set(directories) != {"root", "tests"}
            or any(
                type(value) is not list
                or len(value) != 5
                or any(type(part) is not int for part in value)
                for value in directories.values()
            )
            or type(files) is not dict
            or set(files) != set(_FILE_NAMES[:-1])
        ):
            raise GeneratedRepairSessionError("Private copy manifest is incomplete")
        expected_files = {
            "app.py": expected_hashes[
                "after" if self._expected_workspace_state == "applied-after" else "before"
            ],
            "before.txt": expected_hashes["before"],
            "after.txt": expected_hashes["after"],
            "tests/test_generated_ownership.py": expected_hashes["test"],
            "test.txt": expected_hashes["test"],
        }
        for name, value in files.items():
            if (
                type(value) is not dict
                or set(value) != {"sha256", "identity"}
                or value["sha256"] != expected_files[name]
                or type(value["identity"]) is not list
                or len(value["identity"]) != 9
                or any(type(part) is not int for part in value["identity"])
            ):
                raise GeneratedRepairSessionError("Private copy file identity is incomplete")
        if (
            source.data
            != (
                proposal["after_text"].encode()
                if self._expected_workspace_state == "applied-after"
                else before
            )
            or test.data != proposal["test_text"].encode()
            or list(source.identity) != files["app.py"]["identity"]
            or list(test.identity) != files["tests/test_generated_ownership.py"]["identity"]
            or copy.read_source() != source
            or copy.read_test() != test
            or copy.read_record() != record
        ):
            raise GeneratedRepairSessionError("Private copy file bindings changed")
        files["record.json"] = {"sha256": _sha(record.data), "identity": list(record.identity)}
        return {"directories": directories, "files": files}

    def _current_plan(self, stage: str, now: float) -> GeneratedRepairSessionPlan:
        if self._stages[stage]["expired"]:
            raise GeneratedRepairSessionError("Current stage plan is permanently expired")
        plan = self._plans.get(stage)
        if plan is None:
            raise GeneratedRepairSessionError("A current stage plan is required")
        data = plan.to_dict()
        if (
            data["session_nonce"] != self._nonce
            or data["stage"] != stage
            or data["verification_preview_id"] != self._preview_id
            or self._stages[stage]["plan_id"] != plan.plan_id
            or self._profile is not None
            and (
                data.get("runtime_profile_id") != self._profile.profile_id
                or data.get("prior_results") != self._prior_bindings()
            )
        ):
            raise GeneratedRepairSessionError("Current stage plan identity changed")
        effective = self._stages[stage]["effective_expires_at"]
        expiry = data["expires_at"] if effective is None else min(data["expires_at"], effective)
        if now >= expiry:
            self._stages[stage]["expired"] = True
            raise GeneratedRepairSessionError("Current stage plan expired")
        return plan

    def _prior_bindings(self) -> dict:
        return {
            "before": None
            if self._phase_results["before"] is None
            else self._phase_results["before"]["phase_result_id"],
            "accepted_diff_plan": self._diff_acceptance,
            "source_application": self._source_application,
            "after": None
            if self._phase_results["after"] is None
            else self._phase_results["after"]["phase_result_id"],
            "restoration": self._restoration_status,
        }

    def _requirements(self, stage: str) -> None:
        if stage == "copy":
            return
        if self._stages["copy"]["status"] != "copied-private-workspace":
            raise GeneratedRepairSessionError("A confirmed fresh copy is required first")
        if self._profile is None:
            return
        if self._cleanup_unconfirmed:
            raise GeneratedRepairSessionError("Runtime cleanup remains unconfirmed")
        if stage == "before":
            required = "ready-before"
        elif stage in {"source-diff", "source-apply"}:
            required = "ready-before"
            if not self._baseline:
                raise GeneratedRepairSessionError(
                    "A current independent before baseline is required"
                )
            if stage == "source-apply" and self._diff_acceptance is None:
                raise GeneratedRepairSessionError("The exact source diff must be accepted first")
        else:
            required = "applied-after"
            if self._source_application != "applied-copy-only":
                raise GeneratedRepairSessionError(
                    "A confirmed copy-only source application is required"
                )
        if self._expected_workspace_state != required:
            raise GeneratedRepairSessionError("Current workspace phase does not allow this stage")

    def _bound_manifest(self, stage, plan):
        if stage != "copy" and self._manifest() != plan.to_dict()["file_manifest"]:
            raise GeneratedRepairSessionError("Captured stage files changed")

    def _active_plan_fields(self, stage):
        if self._profile is None:
            return {}
        effects = {
            "copy": "fresh-private-copy",
            "before": "fixed-generated-before-phase",
            "source-diff": "accept-exact-source-diff-only",
            "source-apply": "exact-source-replacement-in-private-copy-only",
            "after": "fresh-fixed-generated-after-phase",
            "restore": "restore-exact-original-before-in-private-copy-only",
        }
        return {
            "runtime_profile_id": self._profile.profile_id,
            "runtime_profile": self._profile.to_dict(),
            "prior_results": self._prior_bindings(),
            "permitted_effect": effects[stage],
            "baseline": "intended-before-defect-observed" if self._baseline else "not-established",
            "source_diff": [
                row
                for row in self._preview.to_dict()["proposal_preview"]["changes"]
                if row.get("path") == "app.py"
            ]
            if stage in {"source-diff", "source-apply"}
            else None,
        }

    def prepare(self, stage: str) -> GeneratedRepairSessionPlan:
        """Prepare at most one original-expiry full plan for each supported stage."""
        with self._operation():
            stage = self._stage(stage)
            self._check_context()
            self._require_change()
            state = self._stages[stage]
            if state["attempted"]:
                raise GeneratedRepairSessionError("Stage attempt has already been consumed")
            now = self._now()
            self._requirements(stage)
            if stage in self._plans:
                plan = self._current_plan(stage, now)
                self._bound_manifest(stage, plan)
                self._check_context()
                self._current_plan(stage, self._now())
                return plan
            manifest = self._manifest() if stage != "copy" else None
            self._check_context()
            self._now()  # Original preparation time still owns the full hard deadline.
            expires_at = _deadline(now, MAX_DECISION_SECONDS)
            if self._last_time >= expires_at:
                raise GeneratedRepairSessionError("Preparation exceeded the original deadline")
            plan = _snapshot(
                {
                    "schema_version": "1.0",
                    "kind": "generated-repair-session-plan",
                    "session_nonce": self._nonce,
                    "stage": stage,
                    "generation": self._supported_stages.index(stage) + 1,
                    "created_at": now,
                    "expires_at": expires_at,
                    "maximum_decision_seconds": MAX_DECISION_SECONDS,
                    "verification_preview_id": self._preview_id,
                    "verification_preview": self._preview.to_dict(),
                    "request": build_generated_repair_request().to_dict(),
                    "workspace_path": str(self._workspace.path) if stage != "copy" else None,
                    "file_manifest": manifest,
                    "permitted_effect": "fresh-private-copy"
                    if stage == "copy"
                    else "disabled-executor-preparation-only",
                    "original_checkout_is_target": False,
                    "execution_authorized": False,
                    "baseline": "not-established",
                    "authorization_status": "unknown",
                    "verified_fix": False,
                    **self._active_plan_fields(stage),
                },
                GeneratedRepairSessionPlan,
                MAX_PLAN_BYTES,
            )
            self._check_context()
            if stage != "copy" and self._manifest() != manifest:
                raise GeneratedRepairSessionError("Captured stage files changed during preparation")
            if self._now() >= expires_at:
                raise GeneratedRepairSessionError("Preparation exceeded the original deadline")
            if self._evidence_budget is not None and stage != "restore":
                self._evidence_budget.charge(len(plan.payload_json.encode("utf-8")))
            self._plans[stage] = plan
            state["plan_id"] = plan.plan_id
            self._event(stage, "plan-prepared")
            return plan

    def decide(
        self, stage: str, choice: str, *, plan_id: str, lifetime_seconds: float = 300
    ) -> GeneratedRepairSessionResult:
        """Bind one exact supported choice to the current, unrefreshed stage plan."""
        with self._operation():
            stage = self._stage(stage)
            if type(choice) is not str or choice not in {"approved", "declined", "cancelled"}:
                raise GeneratedRepairSessionError("Unknown offline decision choice")
            if type(plan_id) is not str or len(plan_id) > 128:
                raise GeneratedRepairSessionError("Current stage plan ID is required")
            if type(lifetime_seconds) not in (int, float):
                raise GeneratedRepairSessionError("Decision lifetime must be finite and positive")
            try:
                duration = float(lifetime_seconds)
            except (OverflowError, ValueError) as exc:
                raise GeneratedRepairSessionError("Invalid decision lifetime") from exc
            if not math.isfinite(duration) or not 0 < duration <= MAX_DECISION_SECONDS:
                raise GeneratedRepairSessionError("Decision lifetime must be at most 300 seconds")
            state = self._stages[stage]
            plan = self._plans.get(stage)
            if plan is None or plan_id != plan.plan_id:
                raise GeneratedRepairSessionError("Decision does not match the current stage plan")
            if state["attempted"] or state["decision"] != "pending":
                raise GeneratedRepairSessionError("Stage decision is already terminal or consumed")
            self._check_context()
            now = self._now()
            plan = self._current_plan(stage, now)
            effective = min(plan.to_dict()["expires_at"], _deadline(now, duration))
            self._requirements(stage)
            self._bound_manifest(stage, plan)
            self._check_context()
            decision_now = self._now()
            if decision_now >= effective:
                state["expired"] = True
                raise GeneratedRepairSessionError("Decision expired while being checked")
            state["decision"] = choice
            state["decided_at"] = decision_now
            state["effective_expires_at"] = effective
            self._event(stage, "decision-" + choice)
            return self.result()

    def _action_start(self, stage: str) -> dict:
        state = self._stages[stage]
        if state["attempted"]:
            raise GeneratedRepairSessionError("Stage attempt has already been consumed")
        state["attempted"] = True
        state["status"] = "refused"
        state["reason"] = "preconditions-not-met"
        self._event(stage, "attempt-consumed")
        return state

    def _dispatch_plan(self, stage: str) -> GeneratedRepairSessionPlan:
        self._check_context()
        self._require_change()
        # Finish full plan decoding/identity checks before the final clock call.
        plan = self._current_plan(stage, self._last_time)
        if self._profile is not None:
            self._requirements(stage)
            self._bound_manifest(stage, plan)
        state = self._stages[stage]
        if state["decision"] != "approved":
            raise GeneratedRepairSessionError("A separate approved current decision is required")
        original_expiry = plan.to_dict()["expires_at"]
        effective_expiry = state["effective_expires_at"]
        if effective_expiry is None:
            raise GeneratedRepairSessionError("A current stage decision expiry is required")
        now = self._now()
        if now >= min(original_expiry, effective_expiry):
            state["expired"] = True
            raise GeneratedRepairSessionError("Current stage decision expired")
        return plan

    def _retain_initialization_failure(self, failure: WorkspaceInitializationError) -> None:
        self._workspace_result.update(
            path=str(failure.created_path),
            state="state-unconfirmed",
            initialization_stage=failure.initialization_stage,
            file_states=dict(failure.file_states),
            descriptor_cleanup_confirmed=getattr(failure, "descriptor_cleanup_confirmed", None),
        )

    def _failure(self, stage: str, exc: BaseException) -> GeneratedRepairSessionResult:
        state = self._stages[stage]
        if self._workspace is not None and self._workspace.state != self._expected_workspace_state:
            self._workspace_result["state"] = "state-unconfirmed"
        if self._workspace_result["state"] == "state-unconfirmed":
            state["status"] = "state-unconfirmed"
        elif state["expired"]:
            state["status"] = "expired"
        elif isinstance(exc, GeneratedRepairSessionError) and not state["dispatched"]:
            state["status"] = "refused"
        else:
            state["status"] = "failed"
        state["reason"] = (
            "operation-unconfirmed"
            if state["status"] == "state-unconfirmed"
            else (
                "clock-unconfirmed" if self._clock_failed else "preconditions-or-operation-failed"
            )
        )
        if stage == "before" and state["dispatched"]:
            self._preparation_status = "failed"
        if not isinstance(exc, Exception):
            exc.generated_repair_session_result = self.result()
            raise exc
        return self.result()

    def create_copy(self, *, _parent: Path | None = None) -> GeneratedRepairSessionResult:
        """Consume one copy attempt, retaining every confirmed or partial effect."""
        with self._operation():
            state = self._action_start("copy")
            try:
                self._dispatch_plan("copy")

                def before_create():
                    # The workspace invokes this after its own validation and
                    # immediately before its first directory allocation.
                    self._dispatch_plan("copy")
                    state["dispatched"] = True

                copy = GeneratedRepairWorkspace(
                    self._preview, _parent=_parent, _before_create=before_create
                )
                self._workspace = copy
                self._workspace_result.update(
                    path=str(copy.path),
                    state=copy.state,
                    initialization_stage="complete",
                    file_states=dict.fromkeys(_FILE_NAMES, "confirmed"),
                    descriptor_cleanup_confirmed=False,
                )
                self._manifest()
                self._check_context()
                # A late return does not undo or hide the already materialized copy.
                self._now()
                state.update(status="copied-private-workspace", reason=None)
                return self.result()
            except BaseException as exc:
                failure = (
                    exc
                    if isinstance(exc, WorkspaceInitializationError)
                    else getattr(exc, "workspace_initialization", None)
                )
                if isinstance(failure, WorkspaceInitializationError):
                    self._retain_initialization_failure(failure)
                if self._workspace is not None:
                    self._workspace_result["state"] = "state-unconfirmed"
                return self._failure("copy", exc)

    def prepare_before(self) -> GeneratedRepairSessionResult:
        """Consume before preparation, without running tests, code or a worker."""
        with self._operation():
            state = self._action_start("before")
            try:
                if self._profile is not None:
                    raise GeneratedRepairSessionError(
                        "Active runtime uses run_before, not disabled preparation"
                    )
                plan = self._dispatch_plan("before")
                if self._manifest() != plan.to_dict()["file_manifest"]:
                    raise GeneratedRepairSessionError(
                        "Captured stage files changed before preparation"
                    )
                self._dispatch_plan("before")
                if self._manifest() != plan.to_dict()["file_manifest"]:
                    raise GeneratedRepairSessionError(
                        "Captured stage files changed before dispatch"
                    )
                self._dispatch_plan("before")
                # No injected adapter/executor is accepted by this session API.
                executor = DisabledGeneratedRepairExecutor()
                self._dispatch_plan("before")
                state["dispatched"] = True
                readiness = executor.prepare(self._preview)
                if type(readiness) is not GeneratedRepairExecutorReadiness:
                    raise GeneratedRepairSessionError("Invalid disabled preparation result type")
                checked = validate_generated_repair_executor_readiness(
                    readiness.payload_json, self._preview
                )
                if checked.to_dict()["reason"] != "runtime-not-implemented":
                    raise GeneratedRepairSessionError("Unexpected default disabled readiness")
                if self._manifest() != plan.to_dict()["file_manifest"]:
                    raise GeneratedRepairSessionError(
                        "Captured stage files changed during preparation"
                    )
                self._dispatch_plan("before")
                self._readiness = checked.to_dict()
                self._preparation_status = "completed"
                state.update(status="prepared-disabled", reason="runtime-not-implemented")
                return self.result()
            except BaseException as exc:
                return self._failure("before", exc)

    def _phase_summary(self, value, stage, plan):
        """Validate one directly returned current-call result; never import it."""
        if type(value) is not GeneratedRepairPhaseResult or type(value.payload_json) is not str:
            raise GeneratedRepairSessionError("Unexpected current phase result type")
        if len(value.payload_json.encode("utf-8")) > MAX_PHASE_RESULT_BYTES:
            raise GeneratedRepairSessionError(
                "Current phase result exceeds the fixed record budget"
            )
        data = value.to_dict()
        manifest = plan.to_dict()["file_manifest"]
        for key, expected in {
            "schema_version": "1.0",
            "kind": "generated-repair-phase-result",
            "candidate": stage,
            "session_nonce": self._nonce,
            "phase_plan_id": plan.plan_id,
            "profile_id": self._profile.profile_id,
            "application_sha256": manifest["files"]["app.py"]["sha256"],
            "test_sha256": manifest["files"]["tests/test_generated_ownership.py"]["sha256"],
            "execution_authorized": False,
            "authorization_status": "unknown",
            "verified_fix": False,
            "source_applied": False,
        }.items():
            if type(data.get(key)) is not type(expected) or data[key] != expected:
                raise GeneratedRepairSessionError("Current phase result bindings changed")
        if (
            data.get("status") not in {"complete", "failed"}
            or type(data.get("cleanup_confirmed")) is not bool
            or type(data.get("engine_transport_cleanup_confirmed")) is not bool
            or type(data.get("generated_runtime_attempted")) is not bool
            or type(data.get("cleanup_errors")) is not list
            or len(data["cleanup_errors"]) > 16
            or any(
                type(reason) is not str or len(reason) > 128 for reason in data["cleanup_errors"]
            )
            or data.get("test_exit_code") is not None
            and (
                type(data["test_exit_code"]) is not int or not -255 <= data["test_exit_code"] <= 255
            )
        ):
            raise GeneratedRepairSessionError("Current phase observation shape changed")
        owned = data.get("owned")
        if type(owned) is not list or len(owned) > 3:
            raise GeneratedRepairSessionError("Current phase ownership is incomplete")
        for index, item in enumerate(owned):
            role = "TAB"[index]
            if (
                type(item) is not dict
                or item.get("role") != role
                or type(item.get("name")) is not str
                or re.fullmatch(
                    r"authzest-generated-" + self._nonce + "-" + role.lower() + r"-[0-9a-f]{32}",
                    item["name"],
                )
                is None
                or type(item.get("create_attempted")) is not bool
                or type(item.get("absence_observed")) is not bool
                or item.get("id") is not None
                and (
                    type(item["id"]) is not str or re.fullmatch(r"[0-9a-f]{64}", item["id"]) is None
                )
            ):
                raise GeneratedRepairSessionError("Current phase ownership bindings changed")
        clean = (
            data["cleanup_confirmed"]
            and data["engine_transport_cleanup_confirmed"]
            and not data["cleanup_errors"]
            and all(not item["create_attempted"] or item["absence_observed"] for item in owned)
        )
        if data["cleanup_confirmed"] and not clean:
            raise GeneratedRepairSessionError("Current phase cleanup claims conflict")
        comparison = None
        if data["status"] == "complete":
            if (
                not clean
                or data.get("failure") is not None
                or len(owned) != 3
                or data["test_exit_code"] not in (0, 1)
                or data["generated_runtime_attempted"] is not True
                or any(not item["create_attempted"] or item["id"] is None for item in owned)
            ):
                raise GeneratedRepairSessionError(
                    "Complete phase lacks confirmed effects and cleanup"
                )
            captures = data.get("captures")
            if type(captures) is not list or not 1 <= len(captures) <= 64:
                raise GeneratedRepairSessionError("Complete phase lacks bounded captures")
            captured, total, labels = {}, 0, set()
            for item in captures:
                if (
                    type(item) is not dict
                    or type(item.get("label")) is not str
                    or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", item["label"]) is None
                    or item["label"] in labels
                ):
                    raise GeneratedRepairSessionError("Phase capture labels changed")
                labels.add(item["label"])
                for field in ("stdout_base64", "stderr_base64"):
                    raw = item.get(field)
                    if type(raw) is not str or len(raw) > 349_528:
                        raise GeneratedRepairSessionError("Phase capture exceeds its byte budget")
                    try:
                        decoded = base64.b64decode(raw, validate=True)
                    except (ValueError, binascii.Error) as exc:
                        raise GeneratedRepairSessionError("Invalid phase capture encoding") from exc
                    if base64.b64encode(decoded).decode("ascii") != raw:
                        raise GeneratedRepairSessionError("Noncanonical phase capture encoding")
                    total += len(decoded)
                    if total > 262_144:
                        raise GeneratedRepairSessionError(
                            "Combined phase capture exceeds its byte budget"
                        )
                    if field == "stdout_base64":
                        for role in ("T", "B"):
                            if re.fullmatch("attach-start-" + role + r"-[0-9]+", item["label"]):
                                if role in captured or item.get("complete") is not True:
                                    raise GeneratedRepairSessionError(
                                        "Complete phase capture is ambiguous"
                                    )
                                captured[role] = (decoded, item.get("returncode"))
            if (
                set(captured) != {"T", "B"}
                or type(captured["T"][1]) is not int
                or captured["T"][1] != data["test_exit_code"]
                or type(captured["B"][1]) is not int
                or captured["B"][1] != 0
            ):
                raise GeneratedRepairSessionError("Phase exit observations disagree")
            try:
                comparison = compare_generated_repair_relay_capture(
                    captured["B"][0].decode("utf-8"),
                    build_generated_repair_controls(),
                    candidate=stage,
                ).to_dict()
            except (UnicodeError, ValueError) as exc:
                raise GeneratedRepairSessionError(
                    "Independent relay observation is invalid"
                ) from exc
            if (
                comparison != data.get("comparison")
                or comparison["matches_expected_profile"] is not True
            ):
                raise GeneratedRepairSessionError("Independent host comparison does not match")
        for key in ("failure", "transport_failure"):
            if data.get(key) is not None and (
                type(data[key]) is not str
                or len(data[key]) > 128
                or re.fullmatch(r"[A-Za-z0-9_.-]+", data[key]) is None
            ):
                raise GeneratedRepairSessionError("Unexpected phase failure diagnostic")
        directory = data.get("evidence_directory")
        if directory is not None and (
            type(directory) is not str or len(directory) > 1024 or not directory.startswith("/")
        ):
            raise GeneratedRepairSessionError("Invalid private phase evidence reference")
        return {
            "phase_result_id": "generated-repair-phase-result-"
            + hashlib.sha256(value.payload_json.encode("utf-8")).hexdigest(),
            "candidate": stage,
            "status": data["status"],
            "failure": data.get("failure"),
            "profile_id": data["profile_id"],
            "phase_plan_id": data["phase_plan_id"],
            "application_sha256": data["application_sha256"],
            "test_sha256": data["test_sha256"],
            "cleanup_confirmed": clean,
            "generated_runtime_attempted": data["generated_runtime_attempted"],
            "test_exit_code": data["test_exit_code"],
            "comparison": None
            if comparison is None
            else {
                key: comparison[key]
                for key in (
                    "controls_id",
                    "expected_profile",
                    "comparison_status",
                    "matches_expected_profile",
                    "case_count",
                    "matching_case_count",
                    "request_count",
                    "matching_request_count",
                )
            },
            "evidence_directory": directory,
            "transport_failure": data.get("transport_failure"),
        }

    def _run_phase(self, stage):
        with self._operation():
            self._stage(stage)
            state = self._action_start(stage)
            invoked = False
            summary = None
            try:
                if self._profile is None:
                    raise GeneratedRepairSessionError("runtime-not-implemented")
                plan = self._dispatch_plan(stage)

                def guard():
                    self._dispatch_plan(stage)

                state["dispatched"] = True
                invoked = True
                value = execute_generated_repair_phase(
                    self._workspace,
                    stage,
                    self._profile,
                    session_nonce=self._nonce,
                    phase_plan_id=plan.plan_id,
                    dispatch_guard=guard,
                    evidence_budget=self._evidence_budget,
                )
                summary = self._phase_summary(value, stage, plan)
                self._cleanup_unconfirmed = not summary["cleanup_confirmed"]
                # Keep the current plan's old prior bindings until its last guard
                # has run; the result becomes a prerequisite only afterward.
                if summary["status"] != "complete":
                    self._phase_results[stage] = summary
                    state.update(status="failed", reason=summary["failure"] or "phase-failed")
                    return self.result()
                self._dispatch_plan(stage)
                self._phase_results[stage] = summary
                if stage == "before":
                    self._baseline = True
                state.update(status="checked-" + stage, reason=None)
                return self.result()
            except BaseException as exc:
                attached = getattr(exc, "generated_repair_phase_result", None)
                if summary is not None:
                    self._phase_results[stage] = summary
                    self._cleanup_unconfirmed = not summary["cleanup_confirmed"]
                elif attached is not None and invoked:
                    try:
                        summary = self._phase_summary(attached, stage, plan)
                        self._phase_results[stage] = summary
                        self._cleanup_unconfirmed = not summary["cleanup_confirmed"]
                    except Exception:
                        self._cleanup_unconfirmed = True
                elif invoked and (
                    type(exc) is not PhaseError or str(exc) != "retained-session-evidence-limit"
                ):
                    # This exact fixed entry raises a budget error before phase
                    # construction. Later budget failures return a phase record.
                    self._cleanup_unconfirmed = True
                return self._failure(stage, exc)

    def run_before(self):
        """Consume one explicitly configured before phase, never imported facts."""
        return self._run_phase("before")

    def run_after(self):
        """Consume a fresh after phase over the confirmed applied-copy bytes."""
        return self._run_phase("after")

    def accept_diff(self):
        """Accept the current exact source diff without changing a file."""
        with self._operation():
            stage = self._stage("source-diff")
            state = self._action_start(stage)
            try:
                plan = self._dispatch_plan(stage)
                self._dispatch_plan(stage)
                self._diff_acceptance = plan.plan_id
                state.update(status="accepted-exact-diff", reason=None)
                return self.result()
            except BaseException as exc:
                return self._failure(stage, exc)

    def _commit_decision(self, stage, expected, expected_test):
        """Check the same decision after pending intent, with the clock last.

        The old journal manifest intentionally no longer matches: the workspace
        has durably recorded state-unconfirmed/pending. Its tracked-file reader
        still validates all current source/test/snapshot/journal identities.
        """
        self._check_context()
        self._require_change()
        plan = self._current_plan(stage, self._last_time)
        self._requirements(stage)
        state = self._stages[stage]
        if state["decision"] != "approved" or state["effective_expires_at"] is None:
            raise GeneratedRepairSessionError("A separate approved current decision is required")
        if (
            self._workspace.read_source() != expected
            or self._workspace.read_test() != expected_test
        ):
            raise GeneratedRepairSessionError("Pending source/test bindings changed")
        record = decode(self._workspace.read_record().data.decode("utf-8"))
        if (
            record.get("verification_preview_id") != self._preview_id
            or record.get("phase") != "state-unconfirmed"
            or record.get("pending_operation") != ("restore" if stage == "restore" else "apply")
        ):
            raise GeneratedRepairSessionError("Pending source journal does not match this decision")
        # This final synchronous clock call follows profile/plan/file I/O. The
        # workspace performs no further filesystem validation before os.replace.
        expires_at = min(plan.to_dict()["expires_at"], state["effective_expires_at"])
        now = self._now()
        if now >= expires_at:
            state["expired"] = True
            raise GeneratedRepairSessionError("Current stage decision expired before source rename")

    def _transition(self, stage, *, restore):
        with self._operation():
            stage = self._stage(stage)
            state = self._action_start(stage)
            try:
                self._dispatch_plan(stage)
                expected = self._workspace.read_source()
                expected_test = self._workspace.read_test()

                def guard():
                    self._dispatch_plan(stage)

                def commit_guard():
                    self._commit_decision(stage, expected, expected_test)

                state["dispatched"] = True
                operation = (
                    self._workspace.restore_source if restore else self._workspace.apply_source
                )
                operation(expected, guard=guard, commit_guard=commit_guard)
                self._expected_workspace_state = "restored-before" if restore else "applied-after"
                self._workspace_result["state"] = self._expected_workspace_state
                if restore:
                    self._restoration_status = "restored-before"
                else:
                    self._source_application = "applied-copy-only"
                self._manifest()
                self._check_context()
                self._now()
                state.update(
                    status="restored-before" if restore else "applied-copy-only", reason=None
                )
                return self.result()
            except BaseException as exc:
                if self._workspace is not None and self._workspace.state == "state-unconfirmed":
                    if restore:
                        self._restoration_status = "state-unconfirmed"
                    else:
                        self._source_application = "state-unconfirmed"
                return self._failure(stage, exc)

    def apply_source(self):
        """Apply only the accepted exact after source to this session's copy."""
        return self._transition("source-apply", restore=False)

    def restore_source(self):
        """Restore exact before bytes after a separate current recovery decision."""
        return self._transition("restore", restore=True)

    def result(self) -> GeneratedRepairSessionResult:
        """Return detached historical data, never fresh time/file observations."""
        return _snapshot(
            {
                "schema_version": "1.0",
                "kind": "generated-repair-session-result",
                "session_nonce": self._nonce,
                "verification_preview_id": self._preview_id,
                "stages": self._stages,
                "workspace": self._workspace_result,
                "history": self._history,
                "preparation_status": self._preparation_status,
                "readiness": self._readiness,
                "closed": self._closed,
                "clock_unconfirmed": self._clock_failed,
                "execution_status": self._execution_status(),
                "baseline": "intended-before-defect-observed"
                if self._baseline
                else "not-established",
                "test_materialization": "materialized-private-copy"
                if self._workspace_result["path"] is not None
                and self._workspace_result["initialization_stage"] == "complete"
                else "not-confirmed",
                "source_application": self._source_application,
                "restoration_status": self._restoration_status,
                "authorization_status": "unknown",
                "execution_authorized": False,
                "provider_calls_made_by_this_session": 0,
                "verified_fix": False,
                **self._active_result_fields(),
            },
            GeneratedRepairSessionResult,
            MAX_RESULT_BYTES,
        )

    def _execution_status(self):
        if self._profile is None:
            return "not-run"
        for stage in ("after", "before"):
            if self._stages[stage]["dispatched"]:
                return stage + (
                    "-checked" if self._stages[stage]["status"] == "checked-" + stage else "-failed"
                )
        return "not-run"

    def _active_result_fields(self):
        if self._profile is None:
            return {}
        before, after = self._phase_results["before"], self._phase_results["after"]
        return {
            "runtime_profile_id": self._profile.profile_id,
            "checks": self._phase_results,
            "cleanup_unconfirmed": self._cleanup_unconfirmed,
            "retained_evidence_bytes_reserved_or_charged": self._evidence_budget.used,
            "poc_exit_pattern": "before-1-after-0"
            if (
                before is not None
                and after is not None
                and before["test_exit_code"] == 1
                and after["test_exit_code"] == 0
            )
            else "not-observed",
            "test_report_authenticity": "not-established",
            "finite_controls_match": self._stages["after"]["status"] == "checked-after",
            "isolation_established": False,
            "resource_enforcement_established": False,
        }

    def close(self) -> None:
        """Close descriptors only; no file deletion, restoration or silent retry."""
        with self._operation():
            self._closed = True
            self._event("session", "closed")
            if self._workspace is not None:
                try:
                    self._workspace.close()
                except BaseException as exc:
                    self._workspace_result["descriptor_cleanup_confirmed"] = False
                    if not isinstance(exc, Exception):
                        exc.generated_repair_session_result = self.result()
                        raise
                    raise GeneratedRepairSessionError(
                        "Workspace descriptor closure is unconfirmed"
                    ) from exc
                self._workspace_result["descriptor_cleanup_confirmed"] = True
