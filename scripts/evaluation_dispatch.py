"""Simulate one offline batch ledger, never authorize or perform a provider call.

Clock samples, decisions, acknowledgements and cleanup assertions are caller-supplied
synthetic data. A serial mutable owner rejects stale revisions within this object;
it is not an authenticated, persistent, concurrent or cross-process execution gate.
"""

from __future__ import annotations

import argparse
import json
import secrets
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_trial_plan as planner

ROOT = Path(__file__).resolve().parents[1]
MAX_CLOCK_NS = (1 << 63) - 1
FAILURES = ("failed", "interrupted", "timeout", "integrity")
FAULTS = (
    "decline",
    "stale-decision",
    "confirm-expired",
    "dispatch-expired",
    "clock",
    "missing",
    "invalid",
    "failed",
    "interrupted",
    "timeout",
    "cleanup",
)
LIMITATIONS = (
    "SYNTHETIC offline state only: no account, network, process or target execution.",
    "Caller-supplied clocks/decisions/ack/cleanup assertions are not trusted runtime evidence.",
    "One-use applies only to this serial object; no persistent/concurrent/authenticated gate.",
    "No actual timer, cancellation, process cleanup or filesystem bound is enforced.",
    "Current IDs and schema-valid answers do not prove provider origin/freshness/correctness.",
    "All planned denominators remain; truncated runs do not establish mode superiority.",
    "No reference scoring, independent/blind-review claim, live freeze or live permission.",
)


class DispatchError(ValueError):
    """Closed offline misuse diagnostic, never include caller data in errors."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DispatchError(code)


@dataclass(frozen=True, slots=True)
class Clock:
    monotonic_ns: int
    wall_ns: int

    def __post_init__(self) -> None:
        _require(
            all(type(x) is int and 0 <= x <= MAX_CLOCK_NS for x in asdict(self).values()),
            "invalid-clock",
        )


@dataclass(frozen=True, slots=True)
class Revision:
    preview_id: str
    number: int


@dataclass(frozen=True, slots=True)
class _Slot:
    ordinal: int
    invocation_id: str
    repetition: int
    mode: str
    questions: int
    status: str = "planned"
    reserved: bool = False
    send_state: str = "not-attempted"
    reserved_ns: int | None = None
    pending_terminal: str | None = None
    primary_failure: str | None = None
    decoded_status: str | None = None
    decoder_error: str | None = None
    cleanup_confirmed: bool | None = None
    clock_failure: bool = False


class Batch:
    """Serial in-memory simulation; no import, restore, executable consent or I/O API."""

    def __init__(self, candidate: codec.Candidate, created: Clock):
        _require(type(candidate) is codec.Candidate, "invalid-candidate")
        candidate.__post_init__()
        _require(type(created) is Clock, "invalid-clock")
        created.__post_init__()
        _require(
            created.monotonic_ns + recipe.CONFIRM_TTL_NS <= MAX_CLOCK_NS,
            "clock-overflow",
        )
        self._candidate = candidate
        self._configuration = replace(candidate.session.configuration)
        self._candidate_id = candidate.candidate_id
        self._recipe_id = recipe.recipe_id(candidate.session.configuration)
        self._created = created
        self._last = created
        self._window_seconds = recipe.dispatch_window_seconds(candidate.session.configuration)
        self._preview_id = planner._identity(
            "offline-dispatch-v1-",
            {
                "candidate_id": self._candidate_id,
                "recipe_id": self._recipe_id,
                "created": asdict(created),
                "window_seconds": self._window_seconds,
                "namespace_nonce": secrets.token_hex(32),
            },
        )
        self._revision = 0
        self._phase = "awaiting-decision"
        self._stop_reason: str | None = None
        self._deadline_ns: int | None = None
        self._active: int | None = None
        self._slots = [
            _Slot(
                item.slot.ordinal,
                item.invocation_id,
                item.slot.repetition,
                item.slot.mode,
                len(item.slot.spec.questions),
            )
            for item in candidate.invocations
        ]

    def __copy__(self):
        raise DispatchError("ledger-copy-unsupported")

    def __deepcopy__(self, memo):
        raise DispatchError("ledger-copy-unsupported")

    @property
    def revision(self) -> Revision:
        return Revision(self._preview_id, self._revision)

    def _begin(self, revision: Revision, clock: Clock) -> None:
        _require(
            type(revision) is Revision
            and type(revision.preview_id) is str
            and type(revision.number) is int
            and revision == self.revision,
            "stale-revision",
        )
        _require(type(clock) is Clock, "invalid-clock")
        clock.__post_init__()

    def _intact(self) -> bool:
        try:
            self._candidate.__post_init__()
            return (
                self._candidate.candidate_id == self._candidate_id
                and recipe.recipe_id(self._candidate.session.configuration) == self._recipe_id
            )
        except (ValueError, TypeError, KeyError, AttributeError):
            return False

    def _stop(self, reason: str, active_status: str, primary: str | None = None) -> None:
        self._stop_reason = reason
        self._phase = "draining-" + reason if self._active is not None else "stopped"
        for index, slot in enumerate(self._slots):
            if index == self._active:
                if slot.pending_terminal is None:
                    self._slots[index] = replace(
                        slot, pending_terminal=active_status, primary_failure=primary
                    )
            elif slot.status == "planned":
                self._slots[index] = replace(slot, status="skipped-" + reason)

    def _tick(self, clock: Clock, *, slot_budget: bool = True) -> None:
        if (
            clock.monotonic_ns < self._last.monotonic_ns
            or abs(
                (clock.wall_ns - self._created.wall_ns)
                - (clock.monotonic_ns - self._created.monotonic_ns)
            )
            > recipe.CLOCK_SKEW_NS
        ):
            if self._active is not None:
                self._slots[self._active] = replace(self._slots[self._active], clock_failure=True)
            self._stop("clock", "failed", "clock-integrity")
            return
        self._last = clock
        if not self._intact():
            self._stop("integrity", "failed", "candidate-integrity")
            return
        if self._active is not None and self._slots[self._active].pending_terminal is not None:
            return  # Keep checking clocks, but never replace a retained primary failure.
        if (
            self._phase == "awaiting-decision"
            and clock.monotonic_ns - self._created.monotonic_ns >= recipe.CONFIRM_TTL_NS
        ):
            self._stop("expired", "skipped-expired")
            return
        if self._active is not None and slot_budget:
            slot = self._slots[self._active]
            assert slot.reserved_ns is not None
            budget = self._configuration.timeout_seconds * recipe.NS
            if (
                slot.send_state == "not-attempted"
                and self._deadline_ns is not None
                and self._deadline_ns <= slot.reserved_ns + budget
                and clock.monotonic_ns >= self._deadline_ns
            ):
                self._stop("expired", "skipped-expired")
                return
            if clock.monotonic_ns - slot.reserved_ns >= budget:
                self._stop("stopped", "timeout", "timeout")
                return
        if self._deadline_ns is not None and clock.monotonic_ns >= self._deadline_ns:
            if self._active is None or self._slots[self._active].send_state == "not-attempted":
                self._stop("expired", "skipped-expired")
            else:
                # Already attempted sends drain under their original slot budget.
                self._stop_reason = "expired"
                self._phase = "draining-expired"
                for index, slot in enumerate(self._slots):
                    if slot.status == "planned":
                        self._slots[index] = replace(slot, status="skipped-expired")

    def decide(
        self, revision: Revision, clock: Clock, *, preview_id: object, approve: object
    ) -> dict:
        self._begin(revision, clock)
        _require(self._phase == "awaiting-decision", "decision-already-terminal")
        self._tick(clock)
        if self._phase != "awaiting-decision":
            pass
        elif clock.monotonic_ns - self._created.monotonic_ns >= recipe.CONFIRM_TTL_NS:
            self._stop("expired", "skipped-expired")
        elif (
            type(preview_id) is not str
            or preview_id != self._preview_id
            or type(approve) is not bool
        ):
            self._stop("invalid-decision", "skipped-invalid-decision")
        elif not approve:
            self._stop("declined", "skipped-declined")
        else:
            deadline = clock.monotonic_ns + self._window_seconds * recipe.NS
            if deadline > MAX_CLOCK_NS:
                self._stop("clock", "failed", "clock-overflow")
            else:
                self._deadline_ns = deadline
                self._phase = "running"
        self._revision += 1
        return self.snapshot()

    def reserve(self, revision: Revision, clock: Clock) -> dict:
        self._begin(revision, clock)
        _require(self._phase == "running" and self._active is None, "reservation-not-available")
        self._tick(clock)
        if self._phase == "running":
            index = next(i for i, slot in enumerate(self._slots) if slot.status == "planned")
            self._slots[index] = replace(
                self._slots[index], status="reserved", reserved=True, reserved_ns=clock.monotonic_ns
            )
            self._active = index
        self._revision += 1
        return self.snapshot()

    def mark_send(self, revision: Revision, clock: Clock) -> dict:
        self._begin(revision, clock)
        _require(self._active is not None, "no-active-slot")
        slot = self._slots[self._active]
        _require(slot.send_state == "not-attempted", "send-already-attempted")
        self._tick(clock)
        slot = self._slots[self._active]
        if slot.pending_terminal is None:
            self._slots[self._active] = replace(slot, status="attempted", send_state="attempted")
        self._revision += 1
        return self.snapshot()

    def acknowledge(self, revision: Revision, clock: Clock) -> dict:
        self._begin(revision, clock)
        _require(self._active is not None, "no-active-slot")
        slot = self._slots[self._active]
        _require(slot.send_state == "attempted", "ack-without-attempt")
        self._tick(clock)
        slot = self._slots[self._active]
        if slot.pending_terminal is None:
            self._slots[self._active] = replace(
                slot, status="acknowledged", send_state="acknowledged"
            )
        self._revision += 1
        return self.snapshot()

    def checkpoint(self, revision: Revision, clock: Clock) -> dict:
        self._begin(revision, clock)
        _require(self._phase not in {"completed", "stopped"}, "batch-terminal")
        self._tick(clock)
        self._revision += 1
        return self.snapshot()

    def finish(
        self,
        revision: Revision,
        clock: Clock,
        *,
        raw: object = None,
        failure: str | None = None,
        cleanup_confirmed: bool,
        cleanup_clock: Clock | None = None,
    ) -> dict:
        """Clock marks generation end; optional cleanup_clock is a separate synthetic sample.

        Group wait durations are not observed or enforced by this offline assertion.
        """
        self._begin(revision, clock)
        _require(self._active is not None, "no-active-slot")
        _require(type(cleanup_confirmed) is bool, "invalid-cleanup-assertion")
        _require(failure is None or type(failure) is str and failure in FAILURES, "invalid-failure")
        if cleanup_clock is not None:
            _require(type(cleanup_clock) is Clock, "invalid-clock")
            cleanup_clock.__post_init__()
        slot = self._slots[self._active]
        _require(
            failure is not None
            or slot.pending_terminal is not None
            or slot.send_state == "acknowledged",
            "completion-without-ack",
        )
        self._tick(clock)
        slot = self._slots[self._active]
        decoded = None
        if slot.pending_terminal is not None:
            outcome, primary = slot.pending_terminal, slot.primary_failure
        elif failure is not None:
            outcome, primary = ("failed" if failure == "integrity" else failure), failure
        else:
            decoded = codec.decode_response(self._candidate.invocations[self._active], raw)
            outcome = decoded["status"]
            primary = None if outcome == "valid" else outcome
        if outcome != "valid":
            self._slots[self._active] = replace(
                slot, pending_terminal=outcome, primary_failure=primary
            )
        if cleanup_clock is not None:
            # No generation-timeout check during cleanup. Clock/config checks remain active.
            self._tick(cleanup_clock, slot_budget=False)
            slot = self._slots[self._active]
            if slot.pending_terminal is not None:
                outcome, primary = slot.pending_terminal, slot.primary_failure
        self._slots[self._active] = replace(
            slot,
            status=outcome if cleanup_confirmed else "failed",
            pending_terminal=None,
            primary_failure=primary,
            decoded_status=decoded["status"] if decoded is not None else None,
            decoder_error=decoded["error"] if decoded is not None else None,
            cleanup_confirmed=cleanup_confirmed,
        )
        self._active = None
        if not cleanup_confirmed:
            self._stop("cleanup", "failed")
        elif outcome != "valid":
            self._stop(
                self._stop_reason or ("integrity" if failure == "integrity" else "stopped"),
                "failed",
            )
        elif all(slot.status == "valid" for slot in self._slots):
            self._phase = "completed"
            self._stop_reason = None
        elif self._stop_reason is not None:
            self._phase = "stopped"
        else:
            self._phase = "running"
        self._revision += 1
        return self.snapshot()

    def preview(self) -> dict:
        return {
            **self.snapshot(),
            "candidate": self._candidate.to_dict(),
            "recipe": recipe.descriptor(self._candidate.session.configuration),
        }

    def snapshot(self) -> dict:
        groups = []
        for repetition in range(1, self._configuration.repetitions + 1):
            for mode in planner.AI_MODES:
                slots = [s for s in self._slots if (s.repetition, s.mode) == (repetition, mode)]
                statuses = sorted({s.status for s in slots})
                groups.append(
                    {
                        "repetition": repetition,
                        "mode": mode,
                        "planned_cases": len(slots),
                        "question_opportunities": sum(s.questions for s in slots),
                        "cases_by_status": {k: sum(s.status == k for s in slots) for k in statuses},
                        "questions_by_status": {
                            k: sum(s.questions for s in slots if s.status == k) for k in statuses
                        },
                    }
                )
        return {
            "schema_version": "0.1",
            "kind": "offline-dispatch-simulation",
            "preview_id": self._preview_id,
            "candidate_id": self._candidate_id,
            "recipe_id": self._recipe_id,
            "configuration": asdict(self._configuration),
            "revision": self._revision,
            "phase": self._phase,
            "stop_reason": self._stop_reason,
            "created": asdict(self._created),
            "dispatch_window_seconds": self._window_seconds,
            "dispatch_deadline_ns": self._deadline_ns,
            "active_ordinal": None if self._active is None else self._active + 1,
            "planned_slots": len(self._slots),
            "question_opportunities": sum(s.questions for s in self._slots),
            "reserved_slots": sum(s.reserved for s in self._slots),
            "simulated_send_attempts": sum(s.send_state != "not-attempted" for s in self._slots),
            "slots": [asdict(slot) for slot in self._slots],
            "groups": groups,
            "observation_origin": "caller-supplied-offline-simulation",
            "provider_calls_by_this_tool": 0,
            "live_trials": 0,
            "runtime_observed": False,
            "provider_freshness_verified": False,
            "sharing_authorized": False,
            "execution_authorized": False,
            "live_configuration_frozen": False,
            "model_quality_measured": False,
            "scoring_status": "not-run",
            "transport_status": "not-implemented",
            "model_availability": "unverified",
            "effort_support": "unverified",
            "actual_timer_enforced": False,
            "cleanup_observation": "caller-asserted-not-process-inspected",
            "cleanup_wait_timing": "not-modeled-per-process",
            "limitations": list(LIMITATIONS),
        }


def prepare(root: Path, configuration: planner.TrialConfig, created: Clock) -> Batch:
    return Batch(codec.prepare_candidate(root, configuration), created)


def _null_response(invocation: codec.Invocation) -> str:
    spec = invocation.slot.spec
    return planner._canonical(
        {
            "schema_version": "0.2",
            "kind": "evaluation-invocation-response",
            "invocation_id": invocation.invocation_id,
            "response": {
                "schema_version": "0.1",
                "kind": "evaluation-comparison-response",
                "task_id": spec.task_id,
                "request_id": spec.request_id,
                "answers": [{"question_id": q.id, "answer": None} for q in spec.questions],
            },
        }
    )


def dry_run(batch: Batch, fault: str | None = None) -> dict:
    _require(type(batch) is Batch, "invalid-batch")
    _require(fault is None or type(fault) is str and fault in FAULTS, "invalid-fault")
    _require(batch.snapshot()["phase"] == "awaiting-decision", "simulation-already-used")
    mono, wall = batch._created.monotonic_ns, batch._created.wall_ns
    if fault == "confirm-expired":
        mono += recipe.CONFIRM_TTL_NS
        wall += recipe.CONFIRM_TTL_NS
    batch.decide(
        batch.revision,
        Clock(mono, wall),
        preview_id="stale" if fault == "stale-decision" else batch.revision.preview_id,
        approve=fault != "decline",
    )
    while batch.snapshot()["phase"] == "running":
        mono += 1
        wall += 1
        if fault == "dispatch-expired":
            mono = batch._deadline_ns
            wall = batch._created.wall_ns + mono - batch._created.monotonic_ns
        batch.reserve(batch.revision, Clock(mono, wall))
        if batch._active is None:
            break
        if fault == "clock":
            wall += recipe.CLOCK_SKEW_NS + 1
        batch.mark_send(batch.revision, Clock(mono, wall))
        slot = batch._slots[batch._active]
        if slot.pending_terminal is None:
            batch.acknowledge(batch.revision, Clock(mono, wall))
        if fault == "timeout":
            mono += batch._candidate.session.configuration.timeout_seconds * recipe.NS
            wall = batch._created.wall_ns + mono - batch._created.monotonic_ns
        raw = _null_response(batch._candidate.invocations[batch._active])
        if fault == "missing":
            raw = None
        elif fault == "invalid":
            raw = "not-json"
        batch.finish(
            batch.revision,
            Clock(mono, wall),
            raw=raw,
            failure=fault if fault in {"failed", "interrupted"} else None,
            cleanup_confirmed=fault != "cleanup",
        )
        fault = None
    return {**batch.snapshot(), "simulation_input": "synthetic-clock-decision-null-responses"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fault", choices=FAULTS)
    args = parser.parse_args(argv)
    if args.fault and not args.dry_run:
        parser.error("--fault requires --dry-run")
    try:
        batch = prepare(
            ROOT,
            planner.TrialConfig(args.model, args.effort, args.repetitions, args.timeout_seconds),
            Clock(0, 0),
        )
        result = dry_run(batch, args.fault) if args.dry_run else batch.preview()
    except (ValueError, TypeError) as error:
        print(json.dumps({"error": str(error), "execution_authorized": False}))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    else:
        print(
            "OFFLINE DISPATCH SIMULATION. No live decisions, provider calls or timer enforcement."
        )
        print(f"Model/effort UNVERIFIED: {args.model} / {args.effort}.")
        print(f"{result['planned_slots']} slots / {result['question_opportunities']} questions.")
        print(f"State: {result['phase']}; reason: {result['stop_reason'] or 'none'}.")
        print(f"Proposed dispatch window: {result['dispatch_window_seconds']} seconds.")
        for group in result["groups"]:
            print(
                f"  repetition {group['repetition']} / {group['mode']}: {group['cases_by_status']}"
            )
        print("Synthetic valid nulls are not scores. Runtime/freshness/approval flags false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
