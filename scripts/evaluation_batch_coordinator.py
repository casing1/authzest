"""Join selected offline protocol states to the existing synthetic batch ledger.

Nothing here reads a pipe, starts a process, samples time, approves sharing or
authenticates cleanup. All clocks, bytes, exits and cleanup assertions are caller
supplied. Frame/preview/outcome data is private in-memory metadata, not public logs.
"""

from __future__ import annotations

from scripts import evaluation_coordinator as protocol
from scripts import evaluation_dispatch as dispatch
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common


class BatchCoordinatorError(ValueError):
    """Closed bridge diagnostic; never relay candidate/provider data."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BatchCoordinatorError(code)


class BatchCoordinator:
    """Serial offline glue, not a live transport or an authorization boundary."""

    def __init__(self, candidate: codec.Candidate, created: dispatch.Clock):
        try:
            self._batch = dispatch.Batch(candidate, created)
        except (ValueError, AttributeError, TypeError, KeyError):
            raise BatchCoordinatorError("invalid-candidate-or-clock") from None
        self._candidate = candidate
        self._slot: protocol.SlotCoordinator | None = None
        self._last_protocol: dict | None = None

    def __copy__(self):
        raise BatchCoordinatorError("coordinator-copy-unsupported")

    def __deepcopy__(self, memo):
        raise BatchCoordinatorError("coordinator-copy-unsupported")

    @property
    def revision(self) -> dispatch.Revision:
        return self._batch.revision

    def preview(self) -> dict:
        """Private owned metadata for inspection, not a public summary or consent."""
        return self._batch.preview()

    def decide(self, revision, clock, *, preview_id: object, approve: object) -> dict:
        try:
            self._batch.decide(revision, clock, preview_id=preview_id, approve=approve)
        except (ValueError, AttributeError, TypeError, KeyError):
            raise BatchCoordinatorError("invalid-decision-transition") from None
        return self.snapshot()

    def reserve(self, revision, clock, boundary: common.Boundary) -> dict:
        _require(self._slot is None, "slot-already-active")
        try:
            _require(type(boundary) is common.Boundary, "invalid-boundary")
            boundary.validate()
            _require(
                boundary.configuration == self._candidate.session.configuration,
                "configuration-mismatch",
            )
            state = self._batch.reserve(revision, clock)
        except (ValueError, AttributeError, TypeError, KeyError):
            raise BatchCoordinatorError("invalid-reservation-transition") from None
        if state["active_ordinal"] is not None:
            invocation = self._candidate.invocations[state["active_ordinal"] - 1]
            try:
                self._slot = protocol.SlotCoordinator(invocation, boundary)
            except (ValueError, AttributeError, TypeError, KeyError):
                self._batch.finish(
                    self.revision, clock, failure="integrity", cleanup_confirmed=True
                )
                raise BatchCoordinatorError("invalid-slot-candidate") from None
        return self.snapshot()

    def _checkpoint(self, revision, clock) -> dict:
        _require(self._slot is not None, "no-active-slot")
        try:
            state = self._batch.checkpoint(revision, clock)
        except (ValueError, AttributeError, TypeError, KeyError):
            raise BatchCoordinatorError("invalid-checkpoint") from None
        slot = state["slots"][state["active_ordinal"] - 1]
        if slot["pending_terminal"] is not None and not self._slot.snapshot()["failed"]:
            reason = "timeout" if slot["pending_terminal"] == "timeout" else "integrity"
            self._slot.abort(reason)
        return slot

    def next_frame(self, revision, clock) -> bytes | None:
        """Prepare private bytes; attempted turn send is marked before returning them."""
        state = self._checkpoint(revision, clock)
        if state["pending_terminal"] is not None:
            return None
        method = self._slot.snapshot()["next_method"]
        try:
            frame = self._slot.next_frame()
        except protocol.CoordinatorError:
            raise BatchCoordinatorError("invalid-frame-transition") from None
        if method == "turn/start":
            # Frame construction is pure. Nothing can transmit these bytes until
            # the current ledger clock/integrity gate has accepted the attempt.
            try:
                current = self._batch.mark_send(self.revision, clock)
            except (ValueError, AttributeError, TypeError, KeyError):
                self._slot.abort("integrity")
                raise BatchCoordinatorError("invalid-send-transition") from None
            sent = current["slots"][current["active_ordinal"] - 1]
            if sent["send_state"] != "attempted" or sent["pending_terminal"] is not None:
                self._slot.abort("integrity")
                return None
        return frame

    def feed(self, revision, clock, chunk: bytes) -> dict:
        state = self._checkpoint(revision, clock)
        if state["pending_terminal"] is not None:
            return self.snapshot()
        try:
            self._slot.feed(chunk)
        except protocol.CoordinatorError:
            self._acknowledge_if_reported(state, clock)
            raise BatchCoordinatorError("protocol-input-rejected") from None
        self._acknowledge_if_reported(state, clock)
        return self.snapshot()

    def _acknowledge_if_reported(self, state: dict, clock: dispatch.Clock) -> None:
        # A valid correlated RPC ack may precede a later invalid final item in
        # the same chunk. Preserve that ack, but never salvage the final answer.
        if self._slot.snapshot()["turn_acknowledged"] and state["send_state"] == "attempted":
            try:
                self._batch.acknowledge(self.revision, clock)
            except (ValueError, AttributeError, TypeError, KeyError):
                self._slot.abort("integrity")
                raise BatchCoordinatorError("invalid-ack-transition") from None

    def abort(self, revision, clock, reason: str) -> dict:
        _require(type(reason) is str and reason in dispatch.FAILURES, "invalid-abort-reason")
        self._checkpoint(revision, clock)
        try:
            self._slot.abort(reason)
        except protocol.CoordinatorError:
            raise BatchCoordinatorError("invalid-abort-transition") from None
        return self.snapshot()

    def finish_phase(
        self,
        revision,
        clock,
        *,
        exit_code: int,
        cleanup_confirmed: bool,
        cleanup_clock: dispatch.Clock | None = None,
    ) -> dict:
        """Supply lifecycle assertions; none is process inspection or trusted time."""
        _require(type(exit_code) is int and -(2**31) <= exit_code < 2**31, "invalid-exit-code")
        _require(type(cleanup_confirmed) is bool, "invalid-cleanup-assertion")
        if cleanup_clock is not None:
            try:
                _require(type(cleanup_clock) is dispatch.Clock, "invalid-cleanup-clock")
                cleanup_clock.__post_init__()
            except (ValueError, AttributeError, TypeError):
                raise BatchCoordinatorError("invalid-cleanup-clock") from None
        self._checkpoint(revision, clock)
        try:
            self._slot.finish_phase(exit_code=exit_code, cleanup_confirmed=cleanup_confirmed)
        except protocol.CoordinatorError:
            # A rejected EOF/exit may latch a failure and still establish that
            # lifecycle assertions were supplied. Never salvage its former text.
            if not self._slot.snapshot()["outcome_ready"]:
                raise BatchCoordinatorError("invalid-phase-finish") from None
        current = self._slot.snapshot()
        if current["outcome_ready"]:
            outcome = self._slot.take_outcome()
            self._last_protocol = self._slot.snapshot()
            self._batch.finish(
                self.revision,
                clock,
                raw=outcome["raw"],
                failure=outcome["failure"],
                cleanup_confirmed=cleanup_confirmed,
                cleanup_clock=cleanup_clock,
            )
            self._slot = None
        elif cleanup_clock is not None:
            # Discovery cleanup is still startup work within the original slot T.
            self._checkpoint(self.revision, cleanup_clock)
        return self.snapshot()

    def snapshot(self) -> dict:
        state = self._batch.snapshot()
        fields = (
            "phase",
            "stop_reason",
            "revision",
            "planned_slots",
            "question_opportunities",
            "reserved_slots",
            "simulated_send_attempts",
            "groups",
        )
        return {
            "kind": "offline-selected-batch-coordinator",
            **{key: state[key] for key in fields},
            "slots": [
                {
                    key: slot[key]
                    for key in (
                        "ordinal",
                        "mode",
                        "questions",
                        "status",
                        "reserved",
                        "send_state",
                        "primary_failure",
                        "cleanup_confirmed",
                        "clock_failure",
                    )
                }
                for slot in state["slots"]
            ],
            "protocol": self._slot.snapshot() if self._slot is not None else self._last_protocol,
            **common.limitations(),
        }
