"""Pure selected two-phase fake-session glue, not a process transport or live gate.

Frames and outcomes are private in-memory values. Caller-declared EOF, exit and
cleanup assertions establish neither actual process cleanup nor authenticated order.
There is no clock, timer, process, I/O, retry, account access or model execution here.
"""

from __future__ import annotations

import json
from contextlib import suppress

from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_jsonl as wire
from scripts import evaluation_preflight as preflight
from scripts import evaluation_semantics as common
from scripts import evaluation_session_semantics as session
from scripts import evaluation_turn_semantics as turns

ABORT_REASONS = ("failed", "timeout", "interrupted", "integrity")


class CoordinatorError(ValueError):
    """Closed diagnostics, never received server text or private candidate values."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CoordinatorError(code)


def _canonical(value: dict) -> bytes:
    raw = (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
        + b"\n"
    )
    _require(len(raw) <= recipe.MAX_FRAME_BYTES, "request-frame-too-large")
    return raw


class SlotCoordinator:
    """Single-owner in-memory candidate lifecycle; no persistence or resume API.

    A failed receive latches and raises. The caller must still finish the current
    phase's asserted lifecycle before taking a failure outcome. Methods do not prove
    that frames were written, processes existed, cleanup ran, or any model was used.
    """

    def __copy__(self):
        raise CoordinatorError("coordinator-copy-unsupported")

    def __deepcopy__(self, memo):
        raise CoordinatorError("coordinator-copy-unsupported")

    def __init__(self, invocation: codec.Invocation, boundary: common.Boundary):
        _require(type(invocation) is codec.Invocation, "invalid-invocation")
        _require(type(boundary) is common.Boundary, "invalid-boundary")
        try:
            invocation.__post_init__()
            boundary.validate()
            _require(
                invocation.session.configuration == boundary.configuration, "configuration-mismatch"
            )
            candidates = recipe.frames(invocation, cwd=boundary.cwd, thread_id=boundary.thread_id)
        except (
            codec.InvocationError,
            common.SemanticError,
            recipe.RecipeError,
            AttributeError,
            TypeError,
        ):
            raise CoordinatorError("invalid-candidate") from None
        self._invocation = invocation
        self._boundary = boundary
        self._signature = self._identity()
        self._parameters = candidates["parameters"]
        self._budget = wire.Budget()
        self._inbox = wire.RpcInbox(self._budget)
        self._phase = "discovery"
        self._next: str | None = "initialize"
        self._awaiting: str | None = None
        self._rpc_id = 0
        self._emitted = 0
        self._awaiting_close = False
        self._failure: str | None = None
        self._failure_code: str | None = None
        self._cleanup_failure: str | None = None
        self._exit_failure = False
        self._closed_phases = 0
        self._outcome_ready = self._outcome_taken = False
        self._discovery: dict | None = None
        self._pages: list[dict] = []
        self._cursor: str | None = None
        self._cursors: set[str] = set()
        self._turn_sent = self._turn_acknowledged = self._turn_checked = False
        self._start: dict | None = None
        self._events: list[dict] = []
        self._raw: str | None = None

    def _identity(self) -> tuple:
        return (
            self._invocation.invocation_id,
            self._invocation.original_message_sha256,
            self._invocation.message_sha256,
            self._invocation.output_schema_sha256,
            self._boundary.configuration.model,
            self._boundary.configuration.effort,
            self._boundary.configuration.repetitions,
            self._boundary.configuration.timeout_seconds,
            self._boundary.cwd,
            self._boundary.thread_id,
        )

    def _verify(self) -> None:
        try:
            self._invocation.__post_init__()
            self._boundary.validate()
            _require(self._identity() == self._signature, "candidate-changed")
        except (
            codec.InvocationError,
            common.SemanticError,
            CoordinatorError,
            AttributeError,
            TypeError,
        ):
            self._fail("candidate-changed")

    def _fail(self, code: str, failure: str = "integrity") -> None:
        if self._failure is None:
            self._failure, self._failure_code = failure, code
        self._next = None
        raise CoordinatorError(code)

    def _active(self) -> None:
        _require(not self._outcome_ready, "slot-terminal")
        _require(self._failure is None, "slot-failed")
        self._verify()

    def next_frame(self) -> bytes:
        self._active()
        _require(self._next is not None and not self._awaiting_close, "frame-not-ready")
        method = self._next
        params = self._parameters[method]
        if method == "model/list" and self._cursor is not None:
            params = {"limit": 100, "includeHidden": False, "cursor": self._cursor}
        if method == "initialized":
            raw = _canonical({"method": method})
            self._next = "config/read"
        else:
            identity = self._rpc_id + 1
            raw = _canonical({"id": identity, "method": method, "params": params})
            self._inbox.arm(identity)
            self._rpc_id = identity
            self._awaiting, self._next = method, None
            if method == "turn/start":
                self._turn_sent = True
        self._emitted += 1
        return raw

    def _catalog_page(self, value: dict) -> None:
        page = common.checked(value)
        common.require(
            type(page) is dict and set(page) == {"data", "nextCursor"}, "invalid-catalog-page"
        )
        common.require(
            type(page["data"]) is list and len(page["data"]) <= 100, "invalid-catalog-page"
        )
        common.require(len(self._pages) < 10, "too-many-catalog-pages")
        cursor = page["nextCursor"]
        common.require(
            cursor is None or type(cursor) is str and 1 <= len(cursor) <= 512,
            "invalid-catalog-cursor",
        )
        if cursor is not None:
            common.require(cursor not in self._cursors, "catalog-cursor-cycle")
            common.require(len(self._pages) < 9, "incomplete-catalog")
            self._cursors.add(cursor)
        self._pages.append(page)
        common.require(sum(len(item["data"]) for item in self._pages) <= 1000, "too-many-models")
        common.checked(self._pages, max_bytes=common.MAX_TOTAL_BYTES)
        self._cursor = cursor
        if cursor is None:
            session.check_catalog(self._pages, self._boundary.configuration)
            self._next = "thread/start"
        else:
            self._next = "model/list"

    def _ack(self, value: dict) -> None:
        common.require(set(value) == {"turn"} and type(value["turn"]) is dict, "invalid-turn-ack")
        turn = value["turn"]
        common.require(
            {"id", "items", "status", "error"} <= turn.keys()
            and turn.keys()
            <= {
                "id",
                "items",
                "status",
                "error",
                "itemsView",
                "startedAt",
                "completedAt",
                "durationMs",
            },
            "invalid-turn-ack",
        )
        common.identifier(turn["id"])
        common.require(
            type(turn["items"]) is list
            and turn["items"] == []
            and turn["status"] == "inProgress"
            and turn["error"] is None
            and turn.get("itemsView", "full") == "full"
            and turn.get("completedAt") is None
            and turn.get("durationMs") is None,
            "invalid-turn-ack",
        )
        started = turn.get("startedAt")
        common.require(
            started is None or type(started) is int and 0 <= started < 2**63, "invalid-turn-ack"
        )
        self._start = value
        self._turn_acknowledged = True

    def _result(self, value: dict) -> None:
        method = self._awaiting
        common.require(method is not None, "unexpected-result")
        if method == "initialize":
            session.check_initialize(value)
            self._next = "initialized"
        elif method == "config/read":
            if self._phase == "discovery":
                preflight.check_config(value, self._boundary.configuration, phase="discovery")
                self._discovery = common.checked(value)
                self._awaiting_close = True
            else:
                preflight.compare_configs(self._discovery, value, self._boundary.configuration)
                self._next = "remoteControl/status/read"
        elif method == "remoteControl/status/read":
            session.check_remote(value)
            self._next = "account/read"
        elif method == "account/read":
            session.check_account(value)
            self._next = "model/list"
        elif method == "model/list":
            self._catalog_page(value)
        elif method == "thread/start":
            session.check_thread_start(value, self._boundary)
            self._next = "turn/start"
        elif method == "turn/start":
            self._ack(value)
        self._awaiting = None

    def _notifications(self, values: tuple[dict, ...]) -> None:
        for value in values:
            common.require(
                self._turn_sent and not self._turn_checked, "premature-or-trailing-event"
            )
            common.require(value["method"] in turns.METHODS, "unsupported-turn-event")
            common.require(len(self._events) < turns.MAX_EVENTS, "too-many-turn-events")
            self._events.append(value)
        if self._turn_acknowledged and any(
            event["method"] == "turn/completed" for event in self._events
        ):
            turns.check_turn(self._invocation, self._boundary, self._start, self._events)
            final = next(event for event in self._events if event["method"] == "item/completed")
            self._raw = final["params"]["item"]["text"]
            self._turn_checked = self._awaiting_close = True

    def feed(self, chunk: bytes) -> None:
        self._active()
        _require(type(chunk) is bytes, "invalid-bytes")
        if self._emitted == 0:
            self._fail("receive-before-request")
        if chunk and (self._awaiting_close or self._awaiting is None and not self._turn_sent):
            self._fail("receive-outside-request")
        try:
            self._inbox.feed(chunk)
            notifications = self._inbox.drain_notifications()
            if notifications and not self._turn_sent:
                self._fail("premature-or-trailing-event")
            result = self._inbox.take_result()
            if result is not None:
                self._result(result)
                if not self._turn_sent and not chunk.endswith(b"\n"):
                    self._fail("premature-response-fragment")
            self._notifications(notifications)
            if self._awaiting_close and chunk and not notifications and result is None:
                common.require(False, "trailing-data")
        except wire.JsonlError:
            self._fail("wire-rejected")
        except (common.SemanticError, preflight.PreflightError):
            self._fail("semantic-rejected")

    def finish_phase(self, *, exit_code: int, cleanup_confirmed: bool) -> None:
        _require(type(exit_code) is int and -(2**31) <= exit_code < 2**31, "invalid-exit-code")
        _require(type(cleanup_confirmed) is bool, "invalid-cleanup-assertion")
        _require(not self._outcome_ready, "slot-terminal")
        if self._failure is None:
            try:
                self._verify()
                self._inbox.finish()
                common.require(self._awaiting_close, "incomplete-phase")
            except CoordinatorError:
                pass
            except (wire.JsonlError, common.SemanticError):
                self._failure, self._failure_code = "integrity", "incomplete-phase"
        if exit_code != 0:
            self._exit_failure = True
            if self._failure is None:
                self._failure, self._failure_code = "failed", "nonzero-exit"
        if not cleanup_confirmed:
            self._cleanup_failure = "cleanup-unconfirmed"
            if self._failure is None:
                self._failure, self._failure_code = "integrity", "cleanup-unconfirmed"
        self._closed_phases += 1
        if self._failure is not None or self._phase == "generation":
            self._phase = "terminal"
            self._next = self._awaiting = None
            self._outcome_ready = True
        else:
            self._phase = "generation"
            self._inbox = wire.RpcInbox(self._budget)
            self._rpc_id = self._emitted = 0
            self._awaiting_close = False
            self._next = "initialize"

    def abort(self, reason: str) -> None:
        _require(type(reason) is str and reason in ABORT_REASONS, "invalid-abort-reason")
        _require(not self._outcome_ready, "slot-terminal")
        if self._failure is None:
            self._failure, self._failure_code = reason, "caller-abort"
        self._next = None

    def take_outcome(self) -> dict:
        _require(self._outcome_ready, "outcome-not-ready")
        _require(not self._outcome_taken, "outcome-already-taken")
        if self._failure is None:
            with suppress(CoordinatorError):
                self._verify()
        self._outcome_taken = True
        return {"raw": self._raw if self._failure is None else None, "failure": self._failure}

    def snapshot(self) -> dict:
        budget = self._budget.snapshot()
        return {
            "kind": "offline-selected-slot-coordinator",
            "phase": self._phase,
            "next_method": self._next,
            "awaiting_method": self._awaiting,
            "turn_acknowledged": self._turn_acknowledged,
            "outcome_ready": self._outcome_ready,
            "outcome_taken": self._outcome_taken,
            "terminal": self._outcome_ready,
            "failure_code": self._failure_code,
            "failure": self._failure,
            "failed": self._failure is not None,
            "cleanup_failure": self._cleanup_failure,
            "exit_failure": self._exit_failure,
            "awaiting_phase_finish": self._awaiting_close or self._failure is not None,
            "closed_phases": self._closed_phases,
            "catalog_pages": len(self._pages),
            "turn_events": len(self._events),
            "stream_bytes": budget["stream_bytes"],
            "received_events": budget["events"],
            **common.limitations(),
            "entitlement_verified": False,
            "timer_enforced": False,
            "cleanup_verified": False,
        }
