"""Pure bridge transitions with owned mock slots; not provider or timing evidence."""

from __future__ import annotations

import copy
import json

import pytest
from scripts import evaluation_batch_coordinator as bridge
from scripts import evaluation_dispatch as dispatch
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts.evaluation_trial_plan import TrialConfig

NS = 1_000_000_000


def clock(seconds=0, *, wall_offset=0):
    return dispatch.Clock(seconds * NS, (1000 + seconds + wall_offset) * NS)


def raw_response(invocation):
    spec = invocation.slot.spec
    return json.dumps(
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


def selected_steps(invocation, boundary, phase, *, fault=None):
    from test_evaluation_coordinator import reply_for, turn_events

    frames = recipe.frames(invocation, cwd=boundary.cwd, thread_id=boundary.thread_id)
    candidates = (
        frames["frame_candidates"][:3] if phase == "discovery" else frames["frame_candidates"]
    )
    for candidate in candidates:
        request = candidate["message"]
        replies = []
        if "id" in request:
            replies.append(
                {"id": request["id"], "result": reply_for(request["method"], invocation, boundary)}
            )
        if request["method"] == "turn/start":
            _, events = turn_events(invocation, boundary)
            if fault == "failed":
                events[-1]["params"]["turn"]["status"] = "failed"
            elif fault == "stale":
                value = json.loads(events[-2]["params"]["item"]["text"])
                value["invocation_id"] = "eval-invocation-v2-" + "0" * 64
                for item in (
                    events[-2]["params"]["item"],
                    events[-1]["params"]["turn"]["items"][0],
                ):
                    item["text"] = json.dumps(value)
            replies.extend(events)
        yield {"request": request, "replies": replies}


class MockSlot:
    """Only the public slot interface is mocked; the existing Batch is real."""

    def __init__(self, invocation, boundary):
        self.invocation = invocation
        self.method = "initialize"
        self.ack = self.failed = self.ready = self.taken = False
        self.failure = None
        self.emitted = 0

    def snapshot(self):
        return {
            "next_method": self.method,
            "turn_acknowledged": self.ack,
            "failed": self.failed,
            "outcome_ready": self.ready,
            "failure_code": self.failure,
            "terminal": self.ready,
            **common.limitations(),
        }

    def next_frame(self):
        if self.failed or self.ready or self.method is None:
            raise bridge.protocol.CoordinatorError("invalid-transition")
        self.emitted += 1
        method, self.method = self.method, None
        return json.dumps({"id": self.emitted, "method": method}).encode() + b"\n"

    def feed(self, chunk):
        if chunk == b"invalid-private-text":
            self.abort("integrity")
            raise bridge.protocol.CoordinatorError("closed-fixture-error")
        if self.emitted == 1:
            self.method = "turn/start"
        else:
            self.ack = True

    def abort(self, reason):
        if not self.failed:
            self.failure = reason
        self.failed = True
        self.method = None

    def finish_phase(self, *, exit_code, cleanup_confirmed):
        if exit_code != 0 and not self.failed:
            self.abort("failed")
        if not cleanup_confirmed and not self.failed:
            self.abort("failed")
        self.ready = True

    def take_outcome(self):
        assert self.ready and not self.taken
        self.taken = True
        self.ready = False
        return {
            "raw": None if self.failed else raw_response(self.invocation),
            "failure": self.failure,
        }


@pytest.fixture
def prepared(monkeypatch):
    monkeypatch.setattr(bridge.protocol, "SlotCoordinator", MockSlot)
    cfg = TrialConfig("synthetic-model", "medium", 1, 30)
    candidate = codec.prepare_candidate(codec.ROOT, cfg)
    return candidate, bridge.BatchCoordinator(candidate, clock())


def approve(coordinator):
    preview = coordinator.preview()
    coordinator.decide(
        coordinator.revision, clock(), preview_id=preview["preview_id"], approve=True
    )


def reserve(candidate, coordinator, at=0):
    boundary = common.Boundary(candidate.session.configuration, "/synthetic", "thread-owned")
    return coordinator.reserve(coordinator.revision, clock(at), boundary)


def send_and_ack(coordinator, at=0):
    assert (
        json.loads(coordinator.next_frame(coordinator.revision, clock(at)))["method"]
        == "initialize"
    )
    assert coordinator.snapshot()["simulated_send_attempts"] == 0
    coordinator.feed(coordinator.revision, clock(at), b"owned-config-and-session-candidate")
    assert (
        json.loads(coordinator.next_frame(coordinator.revision, clock(at)))["method"]
        == "turn/start"
    )
    assert coordinator.snapshot()["simulated_send_attempts"] >= 1
    coordinator.feed(coordinator.revision, clock(at), b"owned-turn-ack-and-final-candidate")


def test_full_declared_batch_keeps_all_denominators_and_negative_flags(prepared):
    candidate, coordinator = prepared
    approve(coordinator)
    for index in range(len(candidate.invocations)):
        reserve(candidate, coordinator)
        # Each mock slot has one initialization before its model send.
        coordinator.next_frame(coordinator.revision, clock())
        coordinator.feed(coordinator.revision, clock(), b"owned")
        coordinator.next_frame(coordinator.revision, clock())
        coordinator.feed(coordinator.revision, clock(), b"owned")
        before = coordinator.snapshot()
        assert before["slots"][index]["status"] == "acknowledged"
        coordinator.finish_phase(coordinator.revision, clock(), exit_code=0, cleanup_confirmed=True)
    result = coordinator.snapshot()
    assert result["phase"] == "completed"
    assert result["planned_slots"] == result["simulated_send_attempts"] == 14
    assert result["question_opportunities"] == 42
    assert all(slot["status"] == "valid" for slot in result["slots"])
    assert sum(g["planned_cases"] for g in result["groups"]) == 14
    assert sum(g["question_opportunities"] for g in result["groups"]) == 42
    for key, value in common.limitations().items():
        assert result[key] == value
    public = json.dumps(result)
    for private in (
        candidate.candidate_id,
        candidate.session.collection_id,
        "synthetic-model",
        "/synthetic",
        "thread-owned",
        "invocation_id",
        "message_text",
    ):
        assert private not in public


@pytest.mark.parametrize("cleanup", [True, False])
def test_startup_failure_consumes_one_slot_and_never_attempts_model(prepared, cleanup):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    coordinator.next_frame(coordinator.revision, clock())
    with pytest.raises(bridge.BatchCoordinatorError, match="protocol-input-rejected"):
        coordinator.feed(coordinator.revision, clock(), b"invalid-private-text")
    assert coordinator.snapshot()["simulated_send_attempts"] == 0
    coordinator.finish_phase(coordinator.revision, clock(), exit_code=1, cleanup_confirmed=cleanup)
    result = coordinator.snapshot()
    assert result["phase"] == "stopped"
    assert result["reserved_slots"] == 1 and result["planned_slots"] == 14
    assert result["slots"][0]["primary_failure"] == "integrity"
    assert all(s["status"].startswith("skipped-") for s in result["slots"][1:])
    with pytest.raises(bridge.BatchCoordinatorError):
        reserve(candidate, coordinator)


def test_never_restart_original_slot_budget_at_send_or_ack(prepared):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    coordinator.next_frame(coordinator.revision, clock(10))
    coordinator.feed(coordinator.revision, clock(20), b"owned")
    assert coordinator.next_frame(coordinator.revision, clock(30)) is None
    assert coordinator.snapshot()["simulated_send_attempts"] == 0
    coordinator.finish_phase(coordinator.revision, clock(30), exit_code=0, cleanup_confirmed=True)
    assert coordinator.snapshot()["slots"][0]["status"] == "timeout"


def test_ack_not_inferred_from_request_or_protocol_final_candidate(prepared):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    coordinator.next_frame(coordinator.revision, clock())
    coordinator.feed(coordinator.revision, clock(), b"owned")
    coordinator.next_frame(coordinator.revision, clock())
    assert coordinator.snapshot()["slots"][0]["status"] == "attempted"
    coordinator.feed(coordinator.revision, clock(), b"owned")
    assert coordinator.snapshot()["slots"][0]["status"] == "acknowledged"
    coordinator.finish_phase(coordinator.revision, clock(), exit_code=0, cleanup_confirmed=True)
    with pytest.raises(bridge.BatchCoordinatorError, match="no-active-slot"):
        coordinator.feed(coordinator.revision, clock(), b"old-slot-result")


@pytest.mark.parametrize("failure", ["failed", "interrupted", "timeout", "integrity"])
def test_abort_waits_for_lifecycle_before_marking_remaining_skipped(prepared, failure):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    coordinator.abort(coordinator.revision, clock(), failure)
    assert coordinator.snapshot()["slots"][0]["status"] == "reserved"
    coordinator.finish_phase(coordinator.revision, clock(), exit_code=0, cleanup_confirmed=True)
    result = coordinator.snapshot()
    assert result["phase"] == "stopped"
    assert result["slots"][0]["primary_failure"] == failure
    assert len(result["slots"]) == 14


def test_unconfirmed_cleanup_and_secondary_clock_do_not_erase_primary(prepared):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    coordinator.abort(coordinator.revision, clock(), "interrupted")
    coordinator.finish_phase(
        coordinator.revision,
        clock(),
        exit_code=9,
        cleanup_confirmed=False,
        cleanup_clock=clock(1, wall_offset=6),
    )
    result = coordinator.snapshot()
    assert result["stop_reason"] == "cleanup"
    assert result["slots"][0]["primary_failure"] == "interrupted"
    assert result["slots"][0]["clock_failure"] is True


def test_stale_revision_blocks_bytes_and_cross_slot_mutation(prepared):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    stale = coordinator.revision
    coordinator.next_frame(stale, clock())
    with pytest.raises(bridge.BatchCoordinatorError, match="invalid-checkpoint"):
        coordinator.feed(stale, clock(), b"old")
    assert coordinator.snapshot()["simulated_send_attempts"] == 0


def test_decline_and_confirmation_expiry_never_reserve(prepared):
    candidate, coordinator = prepared
    preview = coordinator.preview()
    coordinator.decide(
        coordinator.revision, clock(300), preview_id=preview["preview_id"], approve=True
    )
    assert coordinator.snapshot()["phase"] == "stopped"
    assert coordinator.snapshot()["reserved_slots"] == 0
    with pytest.raises(bridge.BatchCoordinatorError):
        reserve(candidate, coordinator, 300)


def test_no_copy_and_private_preview_is_detached(prepared):
    _, coordinator = prepared
    preview = coordinator.preview()
    preview["candidate"]["private"] = "edited"
    assert "private" not in coordinator.preview()["candidate"]
    for function in (copy.copy, copy.deepcopy):
        with pytest.raises(bridge.BatchCoordinatorError, match="coordinator-copy-unsupported"):
            function(coordinator)


@pytest.mark.parametrize(
    "exit_code,cleanup", [(True, True), (0, 1), ("0", True), (2**31, True), (-(2**31) - 1, True)]
)
def test_lifecycle_types_do_not_finish_slot(prepared, exit_code, cleanup):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    previous = coordinator.revision
    with pytest.raises(bridge.BatchCoordinatorError):
        coordinator.finish_phase(
            coordinator.revision, clock(), exit_code=exit_code, cleanup_confirmed=cleanup
        )
    assert coordinator.snapshot()["reserved_slots"] == 1
    assert coordinator.snapshot()["phase"] == "running"
    assert coordinator.revision == previous


def test_real_selected_slot_and_batch_keep_prior_success_then_stop_on_startup_failure():
    candidate = codec.prepare_candidate(codec.ROOT, TrialConfig("synthetic-model", "high", 1, 30))
    coordinator = bridge.BatchCoordinator(candidate, clock())
    approve(coordinator)
    boundary = common.Boundary(
        candidate.session.configuration, "/synthetic/empty", "synthetic-thread"
    )
    coordinator.reserve(coordinator.revision, clock(), boundary)
    for phase in ("discovery", "generation"):
        for step in selected_steps(candidate.invocations[0], boundary, phase):
            request = coordinator.next_frame(coordinator.revision, clock())
            assert json.loads(request) == step["request"]
            raw = b"".join(
                json.dumps(reply, ensure_ascii=False).encode() + b"\n" for reply in step["replies"]
            )
            midpoint = len(raw) // 2
            for chunk in (raw[:midpoint], raw[midpoint:]):
                if chunk:
                    coordinator.feed(coordinator.revision, clock(), chunk)
        coordinator.finish_phase(coordinator.revision, clock(), exit_code=0, cleanup_confirmed=True)
    assert coordinator.snapshot()["slots"][0]["status"] == "valid"
    assert coordinator.snapshot()["phase"] == "running"
    coordinator.reserve(coordinator.revision, clock(), boundary)
    request = json.loads(coordinator.next_frame(coordinator.revision, clock()))
    with pytest.raises(bridge.BatchCoordinatorError, match="protocol-input-rejected"):
        coordinator.feed(
            coordinator.revision,
            clock(),
            json.dumps({"id": request["id"], "result": {}}).encode() + b"\n",
        )
    coordinator.finish_phase(coordinator.revision, clock(), exit_code=1, cleanup_confirmed=True)
    result = coordinator.snapshot()
    assert result["phase"] == "stopped"
    assert result["reserved_slots"] == 2 and result["simulated_send_attempts"] == 1
    assert result["planned_slots"] == 14 and result["question_opportunities"] == 42
    assert result["slots"][0]["status"] == "valid"
    assert result["slots"][1]["status"] == "failed"
    assert all(slot["status"].startswith("skipped-") for slot in result["slots"][2:])


@pytest.mark.parametrize("fault", ["stale", "failed"])
def test_real_correlated_ack_is_preserved_when_later_final_in_same_chunk_fails(fault):
    candidate = codec.prepare_candidate(codec.ROOT, TrialConfig("synthetic-model", "high", 1, 30))
    coordinator = bridge.BatchCoordinator(candidate, clock())
    approve(coordinator)
    boundary = common.Boundary(
        candidate.session.configuration, "/synthetic/empty", "synthetic-thread"
    )
    coordinator.reserve(coordinator.revision, clock(), boundary)
    for phase in ("discovery", "generation"):
        for step in selected_steps(candidate.invocations[0], boundary, phase, fault=fault):
            assert (
                json.loads(coordinator.next_frame(coordinator.revision, clock())) == step["request"]
            )
            raw = b"".join(json.dumps(reply).encode() + b"\n" for reply in step["replies"])
            if step["request"]["method"] == "turn/start":
                with pytest.raises(bridge.BatchCoordinatorError, match="protocol-input-rejected"):
                    coordinator.feed(coordinator.revision, clock(), raw)
                assert coordinator.snapshot()["slots"][0]["send_state"] == "acknowledged"
            elif raw:
                coordinator.feed(coordinator.revision, clock(), raw)
        coordinator.finish_phase(coordinator.revision, clock(), exit_code=0, cleanup_confirmed=True)
    result = coordinator.snapshot()
    assert result["phase"] == "stopped"
    assert result["slots"][0]["status"] == "failed"
    assert result["slots"][0]["primary_failure"] == "integrity"


def test_turn_ack_does_not_restart_original_reserved_slot_timeout(prepared):
    candidate, coordinator = prepared
    approve(coordinator)
    reserve(candidate, coordinator)
    send_and_ack(coordinator, at=29)
    coordinator.finish_phase(coordinator.revision, clock(30), exit_code=0, cleanup_confirmed=True)
    result = coordinator.snapshot()
    assert result["phase"] == "stopped"
    assert result["slots"][0]["status"] == "timeout"
    assert result["slots"][0]["send_state"] == "acknowledged"
