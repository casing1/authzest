"""Test-only fixed child pipes join the real offline Batch and Slot coordinators.

The reused five-second watchdog and TERM/KILL/reap controls belong to this owned
fixture harness. Supplied Clock values are synthetic, not observed slot timing,
production cleanup enforcement, provider provenance, or permission for live use.
"""

from __future__ import annotations

import json
import os
import signal

import pytest
from scripts import evaluation_batch_coordinator as bridge
from scripts import evaluation_dispatch as dispatch
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts import evaluation_trial_plan as planner

import test_evaluation_coordinator_process as peers

pytestmark = peers.pytestmark
# Reuse the exact fixed-argv/environment/empty-cwd guard and final reap assertions.
# No existing helper or product module is modified or generalized by these tests.
owned_process_only = peers.owned_process_only
NS = 1_000_000_000


def clock(seconds=0):
    return dispatch.Clock(seconds * NS, seconds * NS)


@pytest.fixture
def batch_case(owned_process_only):
    configuration = planner.TrialConfig("synthetic-model", "high", 1, 30)
    candidate = codec.prepare_candidate(codec.ROOT, configuration)
    coordinator = bridge.BatchCoordinator(candidate, clock())
    coordinator.decide(
        coordinator.revision, clock(), preview_id=coordinator.revision.preview_id, approve=True
    )
    boundary = common.Boundary(configuration, "/synthetic/empty", "synthetic-thread")
    coordinator.reserve(coordinator.revision, clock(), boundary)
    return candidate, coordinator, boundary, owned_process_only


def _reaped(process):
    assert process.returncode is not None
    assert process.stdin.closed and process.stdout.closed
    with pytest.raises(ChildProcessError):
        os.waitpid(process.pid, os.WNOHANG)


def _drive_phase(
    case,
    tmp_path,
    phase,
    *,
    ordinal=0,
    mode="success",
    at=0,
    before_turn_at=None,
    finish_at=None,
    cleanup=True,
    cancel=False,
):
    """Small fixed-peer driver, not a configurable executable or product launcher."""
    candidate, coordinator, boundary, started = case
    snapshot = coordinator.snapshot()
    assert snapshot["slots"][ordinal]["reserved"] is True  # Reservation precedes child creation.
    assert snapshot["protocol"]["phase"] == phase
    for previous in started:
        _reaped(previous)  # In particular discovery cannot overlap generation.
    steps = peers._steps(candidate.invocations[ordinal], boundary, phase)
    sent = []
    first_read = True
    with peers._OwnedPeer(mode, tmp_path) as peer:
        peer.write(peers._frame({"steps": steps}))
        try:
            while True:
                snapshot = coordinator.snapshot()
                protocol = snapshot["protocol"]
                if protocol["failed"]:
                    break
                if cancel and protocol["turn_acknowledged"]:
                    coordinator.abort(coordinator.revision, clock(at), "interrupted")
                    break
                if protocol["next_method"] is not None:
                    method = protocol["next_method"]
                    moment = (
                        before_turn_at
                        if method == "turn/start" and before_turn_at is not None
                        else at
                    )
                    raw = coordinator.next_frame(coordinator.revision, clock(moment))
                    if raw is None:
                        break  # Expiry must not transmit the turn to this real child.
                    assert json.loads(raw) == steps[len(sent)]["request"]
                    current = coordinator.snapshot()["slots"][ordinal]
                    if method == "turn/start":
                        assert current["send_state"] == "attempted"  # BEFORE actual pipe write.
                        assert not coordinator.snapshot()["protocol"]["turn_acknowledged"]
                    else:
                        assert current["send_state"] == "not-attempted"
                    peer.write(raw)
                    sent.append(method)
                    if method == "turn/start":
                        assert coordinator.snapshot()["slots"][ordinal]["send_state"] == "attempted"
                        assert not coordinator.snapshot()["protocol"]["turn_acknowledged"]
                    if len(sent) == len(steps):
                        peer.process.stdin.close()
                    continue
                if protocol["awaiting_phase_finish"]:
                    # Matching final bytes alone are not a valid ledger observation.
                    assert snapshot["slots"][ordinal]["status"] != "valid"
                stall = mode in ("stall", "ignore-term") and protocol["turn_acknowledged"]
                chunk = peer.read(
                    # Force one real partial read. Later bounded reads may coalesce
                    # the fixture's seven-byte writes; OS reads are not atomic.
                    size=7 if mode == "fragmented" and first_read else 65536,
                    timeout=0.15 if stall else None,
                )
                first_read = False
                if not chunk:
                    peer.process.wait(timeout=peer._remaining())
                    break
                coordinator.feed(coordinator.revision, clock(at), chunk)
        except TimeoutError:
            assert coordinator.snapshot()["protocol"]["turn_acknowledged"]
            coordinator.abort(coordinator.revision, clock(30), "timeout")
        except bridge.BatchCoordinatorError:
            assert coordinator.snapshot()["protocol"]["failed"]
    # Actual fixture pipes are closed and its child reaped BEFORE the pure callback.
    _reaped(peer.process)
    moment = at if finish_at is None else finish_at
    coordinator.finish_phase(
        coordinator.revision,
        clock(moment),
        exit_code=peer.process.returncode,
        cleanup_confirmed=cleanup,
    )
    return sent, peer


def _denominators(snapshot):
    assert snapshot["planned_slots"] == len(snapshot["slots"]) == 14
    assert snapshot["question_opportunities"] == 42
    for group in snapshot["groups"]:
        assert group["planned_cases"] == sum(group["cases_by_status"].values()) == 7
        assert group["question_opportunities"] == sum(group["questions_by_status"].values()) == 21
    for flag in (
        "runtime_observed",
        "provider_freshness_verified",
        "authenticated",
        "accepted_trial",
        "timing_verified",
        "cleanup_verified",
        "ready_for_live_trial",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
    ):
        assert snapshot[flag] is False
    assert snapshot["actual_model_calls"] == 0
    if snapshot["phase"] == "running":
        assert all(
            item["status"] == "planned" for item in snapshot["slots"] if not item["reserved"]
        )
    else:
        assert snapshot["phase"] == "stopped"
        assert all(
            item["status"].startswith("skipped-")
            for item in snapshot["slots"]
            if not item["reserved"]
        )


@pytest.mark.parametrize("mode", ["success", "fragmented"])
def test_two_owned_children_join_actual_batch_lifecycle_without_live_claims(
    batch_case, tmp_path, mode, capfd
):
    _, coordinator, _, started = batch_case
    sent, first = _drive_phase(batch_case, tmp_path, "discovery", mode=mode)
    assert sent == ["initialize", "initialized", "config/read"]
    assert coordinator.snapshot()["simulated_send_attempts"] == 0
    assert first.process.returncode == 0
    sent, second = _drive_phase(batch_case, tmp_path, "generation", mode=mode)
    assert sent[-1] == "turn/start" and second.process.returncode == 0
    snapshot = coordinator.snapshot()
    assert snapshot["slots"][0]["status"] == "valid"
    assert snapshot["slots"][0]["send_state"] == "acknowledged"
    assert snapshot["slots"][0]["cleanup_confirmed"] is True
    assert snapshot["simulated_send_attempts"] == 1 and len(started) == 2
    assert snapshot["phase"] == "running" and snapshot["reserved_slots"] == 1
    _denominators(snapshot)
    rendered = json.dumps(snapshot)
    assert "synthetic@example.test" not in rendered and "synthetic-thread" not in rendered
    assert "OWNED_COORDINATOR_STDERR" not in "".join(capfd.readouterr())


def test_owned_ack_then_malformed_tail_retains_ack_but_never_valid(batch_case, tmp_path):
    _, coordinator, boundary, started = batch_case
    _drive_phase(batch_case, tmp_path, "discovery")
    _drive_phase(batch_case, tmp_path, "generation", mode="ack-malformed", at=1, finish_at=30)
    snapshot = coordinator.snapshot()
    assert snapshot["slots"][0]["send_state"] == "acknowledged"
    assert snapshot["slots"][0]["primary_failure"] == "integrity"
    assert snapshot["slots"][0]["status"] == "failed"
    assert snapshot["protocol"]["turn_acknowledged"] is True
    assert len(started) == 2
    _denominators(snapshot)
    with pytest.raises(bridge.BatchCoordinatorError, match="invalid-reservation-transition"):
        coordinator.reserve(coordinator.revision, clock(40), boundary)


def test_nonzero_owned_exit_after_valid_final_bytes_does_not_promote_batch_slot(
    batch_case, tmp_path
):
    _, coordinator, _, started = batch_case
    _drive_phase(batch_case, tmp_path, "discovery")
    _, peer = _drive_phase(batch_case, tmp_path, "generation", mode="nonzero")
    snapshot = coordinator.snapshot()
    assert peer.process.returncode == 9 and len(started) == 2
    assert snapshot["slots"][0]["send_state"] == "acknowledged"
    assert snapshot["slots"][0]["status"] == "failed"
    assert snapshot["slots"][0]["primary_failure"] == "failed"
    _denominators(snapshot)


def test_original_slot_budget_includes_discovery_and_expiry_blocks_actual_turn_write(
    batch_case, tmp_path
):
    _, coordinator, _, started = batch_case
    _drive_phase(batch_case, tmp_path, "discovery", finish_at=20)
    sent, _ = _drive_phase(
        batch_case, tmp_path, "generation", at=29, before_turn_at=30, finish_at=30
    )
    snapshot = coordinator.snapshot()
    assert "turn/start" not in sent
    assert snapshot["simulated_send_attempts"] == 0
    assert snapshot["slots"][0]["send_state"] == "not-attempted"
    assert snapshot["slots"][0]["primary_failure"] == "timeout"
    assert snapshot["slots"][0]["status"] == "timeout"
    assert len(started) == 2
    _denominators(snapshot)


def test_batch_window_expiry_prevents_actual_turn_write_without_restarting_slot_timer(
    batch_case, tmp_path
):
    candidate, _, boundary, started = batch_case
    coordinator = bridge.BatchCoordinator(candidate, clock())
    coordinator.decide(
        coordinator.revision, clock(), preview_id=coordinator.revision.preview_id, approve=True
    )
    deadline = recipe.dispatch_window_seconds(boundary.configuration)
    coordinator.reserve(coordinator.revision, clock(deadline - 1), boundary)
    case = (candidate, coordinator, boundary, started)
    _drive_phase(case, tmp_path, "discovery", at=deadline - 1)
    sent, _ = _drive_phase(
        case, tmp_path, "generation", at=deadline - 1, before_turn_at=deadline, finish_at=deadline
    )
    snapshot = coordinator.snapshot()
    assert "turn/start" not in sent and len(started) == 2
    assert snapshot["simulated_send_attempts"] == 0
    assert snapshot["slots"][0]["send_state"] == "not-attempted"
    assert snapshot["slots"][0]["status"] == "skipped-expired"
    assert snapshot["stop_reason"] == "expired"
    _denominators(snapshot)


@pytest.mark.parametrize(
    "mode,cancel,expected",
    [
        ("stall", False, "timeout"),
        ("stall", True, "interrupted"),
        ("ignore-term", False, "timeout"),
    ],
)
def test_owned_ack_timeout_or_cancel_survives_late_lifecycle_finish(
    batch_case, tmp_path, mode, cancel, expected
):
    _, coordinator, _, _ = batch_case
    _drive_phase(batch_case, tmp_path, "discovery")
    _, peer = _drive_phase(
        batch_case, tmp_path, "generation", mode=mode, cancel=cancel, at=1, finish_at=40
    )
    snapshot = coordinator.snapshot()
    assert snapshot["slots"][0]["send_state"] == "acknowledged"
    assert snapshot["slots"][0]["primary_failure"] == expected
    assert snapshot["slots"][0]["status"] == expected
    assert signal.SIGTERM in peer.signals
    if mode == "ignore-term":
        assert signal.SIGKILL in peer.signals
        assert peer.process.returncode == -signal.SIGKILL
    _denominators(snapshot)


def test_valid_owned_bytes_with_unconfirmed_cleanup_never_promote_slot(batch_case, tmp_path):
    _, coordinator, _, _ = batch_case
    _drive_phase(batch_case, tmp_path, "discovery")
    _drive_phase(batch_case, tmp_path, "generation", cleanup=False)
    snapshot = coordinator.snapshot()
    assert snapshot["slots"][0]["status"] == "failed"
    assert snapshot["slots"][0]["cleanup_confirmed"] is False
    assert snapshot["stop_reason"] == "cleanup"
    _denominators(snapshot)


def test_prior_owned_success_then_failed_slot_keeps_all_planned_denominators(batch_case, tmp_path):
    candidate, coordinator, boundary, started = batch_case
    _drive_phase(batch_case, tmp_path, "discovery")
    _drive_phase(batch_case, tmp_path, "generation")
    assert coordinator.snapshot()["slots"][0]["status"] == "valid"
    second_boundary = common.Boundary(
        boundary.configuration, boundary.cwd, "synthetic-thread-second"
    )
    coordinator.reserve(coordinator.revision, clock(1), second_boundary)
    second = (candidate, coordinator, second_boundary, started)
    _drive_phase(second, tmp_path, "discovery", ordinal=1, at=1)
    _drive_phase(
        second, tmp_path, "generation", ordinal=1, mode="ack-malformed", at=1, finish_at=40
    )
    snapshot = coordinator.snapshot()
    assert [item["status"] for item in snapshot["slots"][:2]] == ["valid", "failed"]
    assert snapshot["slots"][1]["primary_failure"] == "integrity"
    assert all(item["status"].startswith("skipped-") for item in snapshot["slots"][2:])
    assert snapshot["reserved_slots"] == snapshot["simulated_send_attempts"] == 2
    assert len(started) == 4
    _denominators(snapshot)
