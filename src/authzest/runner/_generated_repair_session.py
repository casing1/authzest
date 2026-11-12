"""Private one-use offline decisions for a fresh copy and disabled preparation.

These in-memory decisions are trusted caller coordination, not authenticated
consent, runtime evidence, a resumable journal or permission to apply source.
There is deliberately no generated execution, baseline importer or write stage.
"""

from __future__ import annotations

import hashlib
import inspect
import math
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from authzest.codex.contracts import canonical, decode, identity
from authzest.codex.generated_repair import build_generated_repair_request
from authzest.runner._generated_repair_workspace import (
    FileState,
    GeneratedRepairWorkspace,
    WorkspaceInitializationError,
)
from authzest.runner.generated_repair_verification import (
    DisabledGeneratedRepairExecutor,
    GeneratedRepairExecutorReadiness,
    _checked_preview,
    validate_generated_repair_executor_readiness,
)

MAX_PLAN_BYTES = 262_144
MAX_RESULT_BYTES = 65_536
MAX_HISTORY_ITEMS = 8
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
    """Coordinate only a fresh private copy and default disabled preparation.

    The synchronous clock and ``_parent`` are trusted test seams. This object
    cannot execute a worker or apply/restore a source, even with forged evidence.
    Files and records are retained on close and on uncertain initialization.
    """

    def __init__(self, preview, *, clock: Callable[[], float] = monotonic):
        self._busy = True
        self._closed = False
        self._clock_failed = False
        self._last_time: float | None = None
        self._clock = clock
        self._workspace: GeneratedRepairWorkspace | None = None
        self._plans: dict[str, GeneratedRepairSessionPlan] = {}
        self._history: list[dict] = []
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
            for stage in _STAGES
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
        if checked.payload_json != self._preview.payload_json:
            raise GeneratedRepairSessionError("Current verification context changed")

    @staticmethod
    def _stage(stage: str) -> str:
        if type(stage) is not str:
            raise GeneratedRepairSessionError("Unknown offline session stage")
        if stage in _LATER_STAGES:
            raise GeneratedRepairSessionError("runtime-not-implemented")
        if stage not in _STAGES:
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
            if self._workspace is not None and self._workspace.state != "ready-before":
                self._workspace_result["state"] = "state-unconfirmed"
            raise

    def _capture_manifest(self) -> dict:
        copy = self._workspace
        if copy is None or copy.state != "ready-before":
            raise GeneratedRepairSessionError("A confirmed ready-before private copy is required")
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
                "phase": "ready-before",
                "pending_operation": None,
                "source_application": "not-run",
                "test_materialization": "materialized-private-copy",
                "restoration": "not-run",
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
            "app.py": expected_hashes["before"],
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
            source.data != before
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
        ):
            raise GeneratedRepairSessionError("Current stage plan identity changed")
        effective = self._stages[stage]["effective_expires_at"]
        expiry = data["expires_at"] if effective is None else min(data["expires_at"], effective)
        if now >= expiry:
            self._stages[stage]["expired"] = True
            raise GeneratedRepairSessionError("Current stage plan expired")
        return plan

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
            if stage in self._plans:
                plan = self._current_plan(stage, now)
                if stage == "before" and self._manifest() != plan.to_dict()["file_manifest"]:
                    raise GeneratedRepairSessionError("Captured stage files changed")
                self._check_context()
                self._current_plan(stage, self._now())
                return plan
            if stage == "before" and self._stages["copy"]["status"] != "copied-private-workspace":
                raise GeneratedRepairSessionError("A confirmed fresh copy is required first")
            manifest = self._manifest() if stage == "before" else None
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
                    "generation": 1 if stage == "copy" else 2,
                    "created_at": now,
                    "expires_at": expires_at,
                    "maximum_decision_seconds": MAX_DECISION_SECONDS,
                    "verification_preview_id": self._preview_id,
                    "verification_preview": self._preview.to_dict(),
                    "request": build_generated_repair_request().to_dict(),
                    "workspace_path": str(self._workspace.path) if stage == "before" else None,
                    "file_manifest": manifest,
                    "permitted_effect": "fresh-private-copy"
                    if stage == "copy"
                    else "disabled-executor-preparation-only",
                    "original_checkout_is_target": False,
                    "execution_authorized": False,
                    "baseline": "not-established",
                    "authorization_status": "unknown",
                    "verified_fix": False,
                },
                GeneratedRepairSessionPlan,
                MAX_PLAN_BYTES,
            )
            self._check_context()
            if stage == "before" and self._manifest() != manifest:
                raise GeneratedRepairSessionError("Captured stage files changed during preparation")
            if self._now() >= expires_at:
                raise GeneratedRepairSessionError("Preparation exceeded the original deadline")
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
            if stage == "before" and self._manifest() != plan.to_dict()["file_manifest"]:
                raise GeneratedRepairSessionError("Captured stage files changed before decision")
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
        if self._workspace is not None and self._workspace.state != "ready-before":
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
                "execution_status": "not-run",
                "baseline": "not-established",
                "test_materialization": "materialized-private-copy"
                if self._workspace_result["path"] is not None
                and self._workspace_result["initialization_stage"] == "complete"
                else "not-confirmed",
                "source_application": "not-run",
                "restoration_status": "not-run",
                "authorization_status": "unknown",
                "execution_authorized": False,
                "provider_calls_made_by_this_session": 0,
                "verified_fix": False,
            },
            GeneratedRepairSessionResult,
            MAX_RESULT_BYTES,
        )

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
