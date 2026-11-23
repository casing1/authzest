"""Current-process private file decisions; no model, target execution or original writes.

This S2 coordinator is not a product operator or authorization verifier. Its clocks
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
from authzest.codex.repository_copy_plan import (
    RepositoryCopyPlan,
    validate_repository_copy_plan,
)
from authzest.codex.repository_proposal import (
    RepositoryProposalRequest,
    prepare_repository_preview,
    validate_repository_request,
    validate_repository_response,
)
from authzest.runner._repository_files import RepositoryFiles

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


class RepositorySessionError(RuntimeError):
    """Closed coordination failure; messages contain no source or private paths."""


class RepositorySessionEffectError(RepositorySessionError):
    """An attempted private effect failed; inspect the retained, detached result."""

    def __init__(self, result: dict):
        super().__init__("Private file operation failed; do not retry or blindly restore")
        self.result = decode(canonical(result))


@dataclass(frozen=True, slots=True)
class RepositoryFilePlan:
    """Review data, accepted only as the exact current live object, never an opener."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class RepositoryFileDecision:
    """A local one-use object, not a serialized or authenticated approval."""

    session_id: str
    plan_id: str
    step: str
    nonce: str


def _hash(data: bytes) -> str:
    return sha256(data).hexdigest()


class RepositoryFileSession:
    """Own one origin capture and at most one fresh private selected-source copy.

    Construction validates supplied data but creates no files. A successful
    construction transfers descriptor ownership of ``origin`` to this session.
    The synchronous ``_clock`` and owned ``_parent`` are test seams. There is no
    runner, original-write API or adoption from saved plans/results/journals.
    """

    def __init__(
        self,
        origin: RepositoryOrigin,
        request: RepositoryProposalRequest,
        response: dict,
        copy_plan: RepositoryCopyPlan,
        *,
        _clock: Callable[[], float] = time.monotonic,
        _parent: Path | None = None,
    ):
        if type(self) is not RepositoryFileSession:
            raise RepositorySessionError("File session subclass adoption is unsupported")
        checked = validate_repository_request(request)
        response = validate_repository_response(canonical(response), checked)
        plan = validate_repository_copy_plan(copy_plan, checked, response)
        if (
            type(origin) is not RepositoryOrigin
            or not callable(_clock)
            or inspect.iscoroutinefunction(_clock)
        ):
            raise RepositorySessionError("A live origin and synchronous clock are required")
        origin.verify(checked.to_dict()["selection"])
        self._request, self._response, self._copy_plan = checked, response, plan
        self._origin, self._parent, self._clock = origin, _parent, _clock
        self._pid, self._thread = os.getpid(), threading.get_ident()
        self._session_id = "repository-file-session-" + secrets.token_hex(16)
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
        self._history: list[dict] = []
        selection = checked.to_dict()["selection"]
        proposal = response["proposal"]
        self._source_path = "project/" + selection["source"]
        self._before = selection["files"][0]["text"].encode("utf-8")
        self._after = proposal["after_text"].encode("utf-8")
        self._test = proposal["test_text"].encode("utf-8")
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
            type(self) is not RepositoryFileSession
            or getattr(self, "_closed", True)
            or self._busy
            or self._pid != os.getpid()
            or self._thread != threading.get_ident()
            or self._state in {"refused", "recovery-required"}
        ):
            raise RepositorySessionError("File session is unavailable for ordinary operations")
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
            raise RepositorySessionError("Monotonic decision clock is unconfirmed") from None
        self._last_clock = value
        return value

    def _check(self, step: str) -> None:
        if type(step) is not str or step not in _STATES or self._state != _STATES[step]:
            raise RepositorySessionError("File stage does not allow that operation")
        try:
            if step == "copy":
                self._origin.verify(self._request.to_dict()["selection"])
            else:
                self._files.verify()
                expected = self._after if step == "restore" else self._before
                if (
                    self._files.read(self._source_path) != expected
                    or self._files.read("evidence/source.before") != self._before
                    or self._files.read("evidence/source.after") != self._after
                ):
                    raise RepositorySessionError("Private source differs from its exact transition")
        except Exception:
            self._state = "recovery-required" if self._files else "refused"
            self._failure = {"step": step, "status": "input-integrity-unconfirmed"}
            raise RepositorySessionError("File inputs no longer match their live binding") from None

    def _guard(self) -> None:
        if self._pending is None or self._decision is None:
            raise RepositorySessionError("A current live decision is required")
        if self._now() >= self._expires:
            self._expired()

    def _expired(self) -> None:
        self._state = "recovery-required" if self._files else "refused"
        self._failure = {"step": "decision", "status": "expired-not-extended"}
        raise RepositorySessionError("File decision expired without deadline extension")

    def prepare(self, step: str) -> RepositoryFilePlan:
        """Prepare one complete current review; repeated calls never reset its clock."""
        self._enter()
        try:
            self._check(step)
            if self._pending is not None:
                if self._pending.to_dict()["step"] != step:
                    raise RepositorySessionError("Another file review is already pending")
                if self._now() >= self._expires:
                    self._expired()
                return self._pending
            preview = prepare_repository_preview(self._response, self._request)
            payload = {
                "kind": "repository-file-plan",
                "schema_version": "1.0",
                "session_id": self._session_id,
                "revision": self._revision,
                "step": step,
                "state": self._state,
                "copy_plan": self._copy_plan.to_dict(),
                "origin_root": str(self._origin.snapshot.root),
                "private_root": self._retained_path,
                "private_file_identities": self._files.identities if self._files else None,
                "review": {
                    "selection": self._request.to_dict()["selection"],
                    "response": self._response,
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
                raise RepositorySessionError("File decision deadline is not representable")
            payload.update(issued_at=issued, expires_at=end)
            payload["plan_id"] = "repository-file-plan-" + identity(payload)
            pending = RepositoryFilePlan(canonical(payload))
            pending.to_dict()  # Bound the entire local review before allocating any private files.
            self._pending = pending
            self._expires = end
            return pending
        finally:
            self._busy = False

    def decide(self, plan: RepositoryFilePlan, confirmation: str) -> RepositoryFileDecision:
        """Bind the exact phrase to this live object; this does not authenticate a human."""
        self._enter()
        try:
            if plan is not self._pending or self._pending is None or self._decision is not None:
                raise RepositorySessionError("Only the current unconsumed review can be decided")
            data = plan.to_dict()
            self._check(data["step"])
            if type(confirmation) is not str or confirmation != data["confirmation"]:
                raise RepositorySessionError("File confirmation does not match the current review")
            if self._now() >= self._expires:
                self._expired()
            self._decision = RepositoryFileDecision(
                self._session_id, data["plan_id"], data["step"], secrets.token_hex(16)
            )
            return self._decision
        finally:
            self._busy = False

    def _record(self, state: str, *, pending: str | None = None) -> bytes:
        data = {
            "kind": "repository-private-file-record",
            "schema_version": "1.0",
            "session_id": self._session_id,
            "request_id": self._request.request_id,
            "copy_plan_id": self._copy_plan.plan_id,
            "response_identity": self._copy_plan.to_dict()["response_identity"],
            "revision": self._revision + (pending is None),
            "state": state,
            "pending_operation": pending,
            "file_plan_id": self._pending.to_dict()["plan_id"],
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
        return canonical(data).encode("utf-8")

    def _materials(self) -> dict[str, bytes]:
        selected = self._request.to_dict()["selection"]["files"]
        source, policy, *contexts = selected
        material = {
            "project/" + source["path"]: self._before,
            **{"project/" + f["path"]: f["text"].encode("utf-8") for f in contexts},
            "project/" + self._response["proposal"]["test_path"]: self._test,
            "evidence/policy.txt": policy["text"].encode("utf-8"),
            "evidence/source.before": self._before,
            "evidence/source.after": self._after,
            "evidence/test.txt": self._test,
        }
        for file in self._copy_plan.to_dict()["files"]:
            value = material[file["workspace_path"]]
            if len(value) != file["utf8_bytes"] or _hash(value) != file["sha256"]:
                raise RepositorySessionError("Private material differs from the current copy plan")
        material["record.json"] = self._record("copy-pending", pending="copy")
        return material

    def perform(self, decision: RepositoryFileDecision) -> dict:
        """Consume one local file decision, retaining failures without execution claims."""
        self._enter()
        try:
            if decision is not self._decision or decision is None or self._consumed:
                raise RepositorySessionError("File decision is not the current unused live object")
            step = decision.step
            self._check(step)
            self._guard()
            self._consumed = True
            phase = "copy-material"
            try:
                if step == "copy":
                    materials = self._materials()

                    def copy_guard():
                        self._origin.verify(self._request.to_dict()["selection"])
                        self._guard()  # Last check after origin I/O, immediately before mkdir.

                    self._files = RepositoryFiles(
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
                    getattr(exc, "repository_files_initialization", None)
                    or getattr(exc, "repository_files_write", None)
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
                    "commit_attempted": bool(getattr(failure, "commit_attempted", False)),
                    "committed": bool(getattr(failure, "committed", False)),
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
                    exc.repository_session_result = self.result()
                    raise
                raise RepositorySessionEffectError(self.result()) from None
        finally:
            self._busy = False

    def result(self) -> dict:
        """Detached historical metadata only; this call does not refresh file observations."""
        return decode(
            canonical(
                {
                    "kind": "repository-file-session",
                    "schema_version": "1.0",
                    "session_id": self._session_id,
                    "request_id": self._request.request_id,
                    "copy_plan_id": self._copy_plan.plan_id,
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
            raise RepositorySessionError("Cannot close during a file operation")
        self._closed = True
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
            interrupted.repository_session_result = self.result()
            raise interrupted
        if self._cleanup == "unconfirmed":
            raise RepositorySessionError("Descriptor cleanup is unconfirmed; artifacts retained")

    def __enter__(self) -> RepositoryFileSession:
        if self._closed:
            raise RepositorySessionError("File session is closed")
        return self

    def __exit__(self, *exc) -> None:
        self.close()
