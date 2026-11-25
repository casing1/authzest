"""Current-process private file decisions; no model, target execution or original writes.

This HTTP-only coordinator is not a product operator or authorization verifier. Its clocks
and caller are trusted. Plans/phrases do not authenticate a human or provider, and
saved JSON cannot reopen a session. All file artifacts survive close and failure.
"""

from __future__ import annotations

import inspect
import math
import os
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from authzest.analyzer.repository_origin import RepositoryOrigin
from authzest.codex.contracts import canonical, decode, identity
from authzest.codex.repository_http_copy_plan import (
    RepositoryHttpCopyPlan,
    validate_repository_http_copy_plan,
)
from authzest.codex.repository_http_proposal import (
    RepositoryHttpRequest,
    prepare_repository_http_preview,
    validate_repository_http_request,
    validate_repository_http_response,
)
from authzest.runner._repository_http_files import RepositoryHttpFiles
from authzest.runner.repository_http_cases import (
    RepositoryHttpCaseSet,
    validate_repository_http_cases,
)
from authzest.runner.repository_http_verification import (
    RepositoryHttpVerificationPlan,
    build_repository_http_verification_plan,
    validate_repository_http_verification_plan,
)

_STATES = {
    "copy": "captured",
    "accept-diff": "copied-before",
    "apply": "diff-accepted",
    "restore": "applied-after",
}
_NEXT = {
    "copy": "copied-before",
    "accept-diff": "diff-accepted",
    "apply": "applied-after",
    "restore": "restored-before",
}
DECISION_SECONDS = 300.0


class RepositoryHttpSessionError(RuntimeError):
    """Closed coordination failure; messages contain no source or private paths."""


class RepositoryHttpSessionEffectError(RepositoryHttpSessionError):
    """An attempted private effect failed; inspect the retained, detached result."""

    def __init__(self, result: dict):
        super().__init__("Private file operation failed; do not retry or blindly restore")
        self.result = decode(canonical(result))


@dataclass(frozen=True, slots=True)
class RepositoryHttpFilePlan:
    """Review data, accepted only as the exact current live object, never an opener."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class RepositoryHttpFileDecision:
    """A local one-use object, not a serialized or authenticated approval."""

    session_id: str
    plan_id: str
    step: str
    nonce: str


@dataclass(frozen=True, slots=True)
class _RepositoryHttpRuntimeCheckpoint:
    """Same-session live read binding, never a saved-result or execution capability."""

    phase: str
    session_id: str
    revision: int
    private_root: Path
    root_identity: tuple[int, ...]
    file_identities: tuple[tuple[str, tuple[int, ...]], ...]
    request: RepositoryHttpRequest
    _response_json: str
    materials: tuple[tuple[str, bytes], ...]
    cases: RepositoryHttpCaseSet
    verification_plan: RepositoryHttpVerificationPlan
    copy_plan: RepositoryHttpCopyPlan
    source_path: str
    source_bytes: bytes
    journal_bytes: bytes

    @property
    def response(self) -> dict:
        return decode(self._response_json)

    def __copy__(self):
        raise TypeError("Live runtime checkpoints cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live runtime checkpoints cannot be copied")

    def __reduce__(self):
        raise TypeError("Live runtime checkpoints cannot be serialized")


@dataclass(frozen=True, slots=True)
class _RepositoryHttpOriginalTarget:
    """Live original-source binding for one separately approved write; never saved."""

    session_id: str
    revision: int
    verification_plan_id: str
    root: Path
    source_path: str
    parent_fd: int
    source_fd: int
    name: str
    identity: tuple
    before: bytes
    after: bytes

    def __copy__(self):
        raise TypeError("Live original targets cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live original targets cannot be copied")

    def __reduce__(self):
        raise TypeError("Live original targets cannot be serialized")


def _hash(data: bytes) -> str:
    return sha256(data).hexdigest()


class RepositoryHttpFileSession:
    """Own one origin capture and at most one fresh private selected-source copy.

    Construction validates supplied data but creates no files. A successful
    construction transfers descriptor ownership of ``origin`` to this session.
    The synchronous ``_clock`` and owned ``_parent`` are test seams. There is no
    runner, original-write API or adoption from saved plans/results/journals.
    """

    def __init__(
        self,
        origin: RepositoryOrigin,
        request: RepositoryHttpRequest,
        response: dict,
        cases: RepositoryHttpCaseSet,
        copy_plan: RepositoryHttpCopyPlan,
        *,
        _clock: Callable[[], float] = time.monotonic,
        _parent: Path | None = None,
    ):
        if type(self) is not RepositoryHttpFileSession:
            raise RepositoryHttpSessionError("File session subclass adoption is unsupported")
        checked = validate_repository_http_request(request)
        response = validate_repository_http_response(canonical(response), checked)
        checked_cases = validate_repository_http_cases(cases)
        verification = build_repository_http_verification_plan(checked, response, checked_cases)
        if verification is None:
            raise RepositoryHttpSessionError("A proposed HTTP source change is required")
        plan = validate_repository_http_copy_plan(copy_plan, checked, response, checked_cases)
        if (
            type(origin) is not RepositoryOrigin
            or not callable(_clock)
            or inspect.iscoroutinefunction(_clock)
            or inspect.isgeneratorfunction(_clock)
            or inspect.isasyncgenfunction(_clock)
        ):
            raise RepositoryHttpSessionError("A live origin and synchronous clock are required")
        origin.verify(checked.to_dict()["selection"])
        self._request, self._response, self._copy_plan = checked, response, plan
        self._cases, self._verification_plan = checked_cases, verification
        self._origin, self._parent, self._clock = origin, _parent, _clock
        self._pid, self._thread = os.getpid(), threading.get_ident()
        self._session_id = "repository-http-file-session-" + secrets.token_hex(16)
        self._state, self._source_observation = "captured", "not-copied"
        self._closed = self._busy = self._consumed = False
        self._pending = self._decision = None
        self._expires = None
        self._files = None
        self._retained_path = None
        self._failure = None
        self._cleanup = "not-requested"
        self._revision = 0
        self._last_clock = None
        self._runtime_checkpoint = None
        self._history: list[dict] = []
        selection = checked.to_dict()["selection"]
        proposal = response["proposal"]
        self._source_path = "project/" + selection["source"]
        self._before = selection["files"][0]["text"].encode("utf-8")
        self._after = proposal["after_text"].encode("utf-8")
        self._origin_token = object()
        origin._claim(self._origin_token)

    def __copy__(self):
        raise TypeError("Live file sessions cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live file sessions cannot be copied")

    def __reduce__(self):
        raise TypeError("Live file sessions cannot be serialized")

    @property
    def state(self) -> str:
        return self._state

    @property
    def closed(self) -> bool:
        return self._closed

    def _enter(self) -> None:
        if (
            type(self) is not RepositoryHttpFileSession
            or getattr(self, "_closed", True)
            or self._busy
            or self._pid != os.getpid()
            or self._thread != threading.get_ident()
            or self._state in {"refused", "recovery-required"}
        ):
            raise RepositoryHttpSessionError("File session is unavailable for ordinary operations")
        self._busy = True

    def _now(self) -> float:
        try:
            value = self._clock()
            if inspect.iscoroutine(value):
                value.close()
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError
            value = float(value)
            if self._last_clock is not None and value < self._last_clock:
                raise ValueError
        except BaseException as exc:
            self._state = "recovery-required" if self._files else "refused"
            self._failure = {"step": "clock", "status": "clock-unconfirmed"}
            if not isinstance(exc, Exception):
                raise
            raise RepositoryHttpSessionError("Monotonic decision clock is unconfirmed") from None
        self._last_clock = value
        return value

    def _contracts(self) -> None:
        """Rebuild complete current HTTP data, without importing or reading an app."""
        checked = validate_repository_http_request(self._request)
        response = validate_repository_http_response(canonical(self._response), checked)
        cases = validate_repository_http_cases(self._cases)
        validate_repository_http_verification_plan(
            self._verification_plan, checked, response, cases
        )
        validate_repository_http_copy_plan(self._copy_plan, checked, response, cases)
        selection = checked.to_dict()["selection"]
        if (
            self._source_path != "project/" + selection["source"]
            or self._before != selection["files"][0]["text"].encode("utf-8")
            or self._after != response["proposal"]["after_text"].encode("utf-8")
        ):
            raise RepositoryHttpSessionError("HTTP source transition binding differs")

    def _check(self, step: str) -> None:
        if type(step) is not str or step not in _STATES or self._state != _STATES[step]:
            raise RepositoryHttpSessionError("File stage does not allow that operation")
        try:
            self._contracts()
            if step == "copy":
                self._origin.verify(self._request.to_dict()["selection"])
            else:
                self._files.verify()
                self._completed_journal()
                expected = self._after if step == "restore" else self._before
                policy = self._request.to_dict()["selection"]["files"][1]["text"].encode()
                if (
                    self._files.read(self._source_path) != expected
                    or self._files.read("evidence/source.before") != self._before
                    or self._files.read("evidence/source.after") != self._after
                    or self._files.read("evidence/policy.txt") != policy
                ):
                    raise RepositoryHttpSessionError("Private source differs from its transition")
        except BaseException as exc:
            self._state = "recovery-required" if self._files else "refused"
            self._failure = {"step": step, "status": "input-integrity-unconfirmed"}
            if not isinstance(exc, Exception):
                exc.repository_http_session_result = self.result()
                raise
            raise RepositoryHttpSessionError(
                "File inputs no longer match their live binding"
            ) from None

    def _guard(self) -> None:
        self._contracts()
        if self._pending is None or self._decision is None:
            raise RepositoryHttpSessionError("A current live decision is required")
        if self._now() >= self._expires:
            self._expired()

    def _read_runtime_checkpoint(self, phase: str) -> _RepositoryHttpRuntimeCheckpoint:
        expected_state = {"before": "copied-before", "after": "applied-after"}
        if (
            type(phase) is not str
            or phase not in expected_state
            or self._state != expected_state[phase]
            or type(self._files) is not RepositoryHttpFiles
            or self._pending is not None
            or self._decision is not None
            or self._consumed
            or self._expires is not None
            or self._failure is not None
            or self._cleanup == "unconfirmed"
        ):
            raise RepositoryHttpSessionError("A quiescent current before/after copy is required")
        try:
            self._files.verify()
            self._contracts()
            selection = self._request.to_dict()["selection"]
            source_path = selection["source"]
            expected = self._after if phase == "after" else self._before
            source_bytes = self._files.read("project/" + source_path)
            policy_bytes = selection["files"][1]["text"].encode("utf-8")
            if (
                source_bytes != expected
                or self._files.read("evidence/source.before") != self._before
                or self._files.read("evidence/source.after") != self._after
                or self._files.read("evidence/policy.txt") != policy_bytes
            ):
                raise RepositoryHttpSessionError(
                    "Private artifacts differ from current HTTP inputs"
                )
            journal_bytes = self._completed_journal()
            checkpoint = _RepositoryHttpRuntimeCheckpoint(
                phase=phase,
                session_id=self._session_id,
                revision=self._revision,
                private_root=self._files.path,
                root_identity=self._files.root_identity,
                file_identities=tuple(
                    (name, tuple(value)) for name, value in sorted(self._files.identities.items())
                ),
                request=self._request,
                _response_json=canonical(self._response),
                materials=((source_path, source_bytes),),
                cases=self._cases,
                verification_plan=self._verification_plan,
                copy_plan=self._copy_plan,
                source_path=source_path,
                source_bytes=source_bytes,
                journal_bytes=journal_bytes,
            )
            self._files.verify()
            return checkpoint
        except BaseException as exc:
            self._state = "recovery-required"
            self._failure = {"step": "runtime-checkpoint", "status": "input-integrity-unconfirmed"}
            if not isinstance(exc, Exception):
                exc.repository_http_session_result = self.result()
                raise
            raise RepositoryHttpSessionError(
                "Current private checkpoint integrity is unconfirmed"
            ) from None

    def _capture_runtime_checkpoint(self, phase: str) -> _RepositoryHttpRuntimeCheckpoint:
        """Freshly read all current source bytes for an HTTP-only A checkpoint.

        This internal bridge performs no writes, decisions, import or execution.
        Old sessions, test artifacts and supplied JSON are never adopted here.
        """
        self._enter()
        try:
            fresh = self._read_runtime_checkpoint(phase)
            if self._runtime_checkpoint != fresh:
                self._runtime_checkpoint = fresh
            return self._runtime_checkpoint
        finally:
            self._busy = False

    def _recheck_runtime_checkpoint(self, checkpoint: _RepositoryHttpRuntimeCheckpoint) -> None:
        """Recheck only this session's exact issued object against the live copy."""
        self._enter()
        try:
            if (
                type(checkpoint) is not _RepositoryHttpRuntimeCheckpoint
                or checkpoint is not self._runtime_checkpoint
            ):
                raise RepositoryHttpSessionError(
                    "Only the current issued live checkpoint is accepted"
                )
            if self._read_runtime_checkpoint(checkpoint.phase) != checkpoint:
                raise RepositoryHttpSessionError(
                    "Runtime checkpoint differs from current private state"
                )
        finally:
            self._busy = False

    def _original_target(self) -> _RepositoryHttpOriginalTarget:
        """Recheck the applied private copy and every held original input.

        Refuses unless quiescent in ``applied-after``. Any change to the selected
        original files or directories since capture is an edit conflict. This
        bridge itself writes nothing; the caller owns the separate decision.
        """
        self._enter()
        try:
            if (
                self._state != "applied-after"
                or type(self._files) is not RepositoryHttpFiles
                or self._pending is not None
                or self._decision is not None
                or self._consumed
                or self._failure is not None
            ):
                raise RepositoryHttpSessionError("A quiescent applied private copy is required")
            self._contracts()
            self._files.verify()
            if self._files.read(self._source_path) != self._after:
                raise RepositoryHttpSessionError("Private source differs from the applied repair")
            selection = self._request.to_dict()["selection"]
            snapshot = self._origin.verify(selection)
            parent, name, observed, raw, source_fd = self._origin._source_target()
            if raw != self._before:
                raise RepositoryHttpSessionError("Original source differs from its capture")
            return _RepositoryHttpOriginalTarget(
                session_id=self._session_id,
                revision=self._revision,
                verification_plan_id=self._verification_plan.plan_id,
                root=snapshot.root,
                source_path=selection["source"],
                parent_fd=parent,
                source_fd=source_fd,
                name=name,
                identity=tuple(observed),
                before=self._before,
                after=self._after,
            )
        finally:
            self._busy = False

    def _expired(self) -> None:
        self._state = "recovery-required" if self._files else "refused"
        self._failure = {"step": "decision", "status": "expired-not-extended"}
        raise RepositoryHttpSessionError("File decision expired without deadline extension")

    def prepare(self, step: str) -> RepositoryHttpFilePlan:
        """Prepare one complete current review; repeated calls never reset its clock."""
        self._enter()
        try:
            self._check(step)
            if self._pending is not None:
                if self._pending.to_dict()["step"] != step:
                    raise RepositoryHttpSessionError("Another file review is already pending")
                if self._now() >= self._expires:
                    self._expired()
                return self._pending
            preview = prepare_repository_http_preview(self._response, self._request)
            payload = {
                "kind": "repository-http-file-plan",
                "schema_version": "2.0",
                "session_id": self._session_id,
                "revision": self._revision,
                "step": step,
                "state": self._state,
                "copy_plan": self._copy_plan.to_dict(),
                "origin_root": str(self._origin.snapshot.root),
                "private_root": self._retained_path,
                "private_file_identities": self._files.identities if self._files else None,
                "review": {
                    "request": self._request.to_dict(),
                    "response": self._response,
                    "cases": self._cases.to_dict(),
                    "verification_plan": self._verification_plan.to_dict(),
                    "diffs": [{"path": c["path"], "diff": c["diff"]} for c in preview["changes"]],
                },
                "confirmation": "CONFIRM " + step.upper() + " " + secrets.token_hex(16),
                "execution_status": "not-run",
                "authorization_status": "unknown",
                "verified_fix": False,
            }
            issued = self._now()
            end = issued + DECISION_SECONDS
            if end - issued > DECISION_SECONDS:
                end = math.nextafter(end, -math.inf)
            if not math.isfinite(end) or end <= issued or end - issued > DECISION_SECONDS:
                raise RepositoryHttpSessionError("File decision deadline is not representable")
            payload.update(issued_at=issued, expires_at=end)
            payload["plan_id"] = "repository-http-file-plan-" + identity(payload)
            pending = RepositoryHttpFilePlan(canonical(payload))
            pending.to_dict()  # Bound the entire local review before allocating any private files.
            self._runtime_checkpoint = None
            self._pending = pending
            self._expires = end
            return pending
        finally:
            self._busy = False

    def decide(self, plan: RepositoryHttpFilePlan, confirmation: str) -> RepositoryHttpFileDecision:
        """Bind the exact phrase to this live object; this does not authenticate a human."""
        self._enter()
        try:
            if plan is not self._pending or self._pending is None or self._decision is not None:
                raise RepositoryHttpSessionError(
                    "Only the current unconsumed review can be decided"
                )
            data = plan.to_dict()
            self._check(data["step"])
            if type(confirmation) is not str or confirmation != data["confirmation"]:
                raise RepositoryHttpSessionError(
                    "File confirmation does not match the current review"
                )
            if self._now() >= self._expires:
                self._expired()
            self._decision = RepositoryHttpFileDecision(
                self._session_id, data["plan_id"], data["step"], secrets.token_hex(16)
            )
            return self._decision
        finally:
            self._busy = False

    def _journal(
        self, state: str, *, pending: str | None, revision: int, file_plan_id: str
    ) -> dict:
        return {
            "kind": "repository-http-private-file-record",
            "schema_version": "2.0",
            "session_id": self._session_id,
            "request_id": self._request.request_id,
            "copy_plan_id": self._copy_plan.plan_id,
            "response_identity": self._copy_plan.to_dict()["response_identity"],
            "case_set_id": self._cases.case_set_id,
            "verification_plan_id": self._verification_plan.plan_id,
            "revision": revision,
            "state": state,
            "pending_operation": pending,
            "file_plan_id": file_plan_id,
            "file_identities": (
                {k: v for k, v in self._files.identities.items() if k != "record.json"}
                if self._files
                else None
            ),
            "source_transition": self._copy_plan.to_dict()["source_transition"],
            "last_confirmed_source": self._source_observation,
            "execution_status": "not-run",
            "authorization_status": "unknown",
            "verified_fix": False,
        }

    def _record(self, state: str, *, pending: str | None = None) -> bytes:
        return canonical(
            self._journal(
                state,
                pending=pending,
                revision=self._revision + (pending is None),
                file_plan_id=self._pending.to_dict()["plan_id"],
            )
        ).encode("utf-8")

    def _completed_journal(self) -> bytes:
        if not self._history or self._history[-1]["status"] != "completed":
            raise RepositoryHttpSessionError("Private journal has no completed transition")
        current = self._files.read("record.json")
        expected = self._journal(
            self._state,
            pending=None,
            revision=self._revision,
            file_plan_id=self._history[-1]["plan_id"],
        )
        if current != canonical(expected).encode("utf-8"):
            raise RepositoryHttpSessionError("Private journal is not the exact completed state")
        return current

    def _materials(self) -> dict[str, bytes]:
        source, policy = self._request.to_dict()["selection"]["files"]
        material = {
            "project/" + source["path"]: self._before,
            "evidence/policy.txt": policy["text"].encode("utf-8"),
            "evidence/source.before": self._before,
            "evidence/source.after": self._after,
        }
        for file in self._copy_plan.to_dict()["files"]:
            value = material[file["workspace_path"]]
            if len(value) != file["utf8_bytes"] or _hash(value) != file["sha256"]:
                raise RepositoryHttpSessionError("Private material differs from current copy plan")
        material["record.json"] = self._record("copy-pending", pending="copy")
        return material

    def perform(self, decision: RepositoryHttpFileDecision) -> dict:
        """Consume one local file decision, retaining failures without execution claims."""
        self._enter()
        try:
            if decision is not self._decision or decision is None or self._consumed:
                raise RepositoryHttpSessionError(
                    "File decision is not the current unused live object"
                )
            step = decision.step
            self._check(step)
            self._guard()
            self._runtime_checkpoint = None
            self._consumed = True
            phase = "copy-material"
            try:
                if step == "copy":
                    materials = self._materials()

                    def copy_guard():
                        self._origin.verify(self._request.to_dict()["selection"])
                        self._guard()  # Last check after origin I/O, immediately before mkdir.

                    self._files = RepositoryHttpFiles(
                        materials, self._source_path, _parent=self._parent, guard=copy_guard
                    )
                    self._retained_path = str(self._files.path)
                    self._source_observation = "before"
                elif step in {"apply", "restore"}:
                    phase = "intent-journal"
                    self._files.replace(
                        "record.json",
                        self._record("transition-pending", pending=step),
                        guard=self._guard,
                    )
                    phase = "source-replacement"
                    # The helper rechecks all exact private baselines, including its NEW
                    # self-committed intent journal, before calling the final guard.
                    self._files.replace(
                        self._source_path,
                        self._after if step == "apply" else self._before,
                        guard=self._guard,
                    )
                    self._source_observation = "after" if step == "apply" else "restored-before"
                phase = "completion-journal"
                self._files.replace("record.json", self._record(_NEXT[step]), guard=self._guard)
                self._files.verify()
                self._state = _NEXT[step]
                self._history.append(
                    {"step": step, "status": "completed", "plan_id": decision.plan_id}
                )
                self._revision += 1
                self._pending = self._decision = None
                self._expires = None
                self._consumed = False
                return self.result()
            except BaseException as exc:
                failure = (
                    getattr(exc, "repository_http_files_initialization", None)
                    or getattr(exc, "repository_http_files_write", None)
                    or exc
                )
                self._retained_path = self._retained_path or (
                    str(failure.created_path)
                    if getattr(failure, "created_path", None) is not None
                    else None
                )
                self._state = "recovery-required" if self._retained_path else "refused"
                self._failure = {
                    "step": step,
                    "phase": phase,
                    "status": "effect-unconfirmed",
                    "commit_attempted": getattr(failure, "commit_attempted", None),
                    "committed": getattr(failure, "committed", None),
                    "stage": getattr(failure, "stage", None),
                    "staging_path": (
                        str(failure.staging_path)
                        if getattr(failure, "staging_path", None)
                        else None
                    ),
                    "initialization_file_states": getattr(failure, "file_states", None),
                    "initialization_cleanup_confirmed": getattr(
                        failure, "descriptor_cleanup_confirmed", None
                    ),
                }
                self._history.append(
                    {"step": step, "status": "failed", "plan_id": decision.plan_id}
                )
                if not isinstance(exc, Exception):
                    exc.repository_http_session_result = self.result()
                    raise
                raise RepositoryHttpSessionEffectError(self.result()) from None
        finally:
            self._busy = False

    def result(self) -> dict:
        """Detached historical metadata only; this call does not refresh file observations."""
        return decode(
            canonical(
                {
                    "kind": "repository-http-file-session",
                    "schema_version": "2.0",
                    "session_id": self._session_id,
                    "request_id": self._request.request_id,
                    "copy_plan_id": self._copy_plan.plan_id,
                    "case_set_id": self._cases.case_set_id,
                    "verification_plan_id": self._verification_plan.plan_id,
                    "state": self._state,
                    "closed": self._closed,
                    "private_root": self._retained_path,
                    "source_observation": {
                        "status": self._source_observation,
                        "basis": "last-confirmed-not-refreshed-by-result",
                    },
                    "history": self._history,
                    "failure": self._failure,
                    "descriptor_cleanup": self._cleanup,
                    "original_write": "not-supported",
                    "execution_status": "not-run",
                    "authorization_status": "unknown",
                    "verified_fix": False,
                }
            )
        )

    def close(self) -> None:
        """Close owned descriptors without deleting any retained workspace artifact."""
        if self._closed:
            return
        if self._busy:
            raise RepositoryHttpSessionError("Cannot close during a file operation")
        self._closed = True
        self._runtime_checkpoint = None
        self._cleanup = "confirmed"
        interrupted = None
        for handle in (self._files, self._origin):
            if handle is not None:
                try:
                    handle.close()
                except BaseException as exc:
                    self._cleanup = "unconfirmed"
                    self._state = "recovery-required" if self._retained_path else "refused"
                    if interrupted is None and not isinstance(exc, Exception):
                        interrupted = exc
        if interrupted is not None:
            interrupted.repository_http_session_result = self.result()
            raise interrupted
        if self._cleanup == "unconfirmed":
            raise RepositoryHttpSessionError(
                "Descriptor cleanup is unconfirmed; artifacts retained"
            )

    def __enter__(self) -> RepositoryHttpFileSession:
        if self._closed:
            raise RepositoryHttpSessionError("File session is closed")
        return self

    def __exit__(self, *exc) -> None:
        self.close()
