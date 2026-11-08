"""Synthetic serial ledger tests, not actual authorization or runtime observation."""

from __future__ import annotations

import copy
import json
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from scripts import evaluation_dispatch as state
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_trial_plan as planner

NS = 1_000_000_000


def configuration(*, repetitions=1, timeout=30):
    return planner.TrialConfig("offline-model", "medium", repetitions, timeout)


def clock(value=0, wall=None):
    return state.Clock(value, value if wall is None else wall)


@pytest.fixture
def candidate():
    return codec.prepare_candidate(codec.ROOT, configuration())


@pytest.fixture
def batch(candidate):
    return state.Batch(candidate, clock())


def approve(batch, at=0):
    return batch.decide(
        batch.revision, clock(at), preview_id=batch.revision.preview_id, approve=True
    )


def reserve_ack(batch, at=0):
    batch.reserve(batch.revision, clock(at))
    batch.mark_send(batch.revision, clock(at + 1))
    return batch.acknowledge(batch.revision, clock(at + 2))


def raw_for(candidate, index=0):
    invocation = candidate.invocations[index]
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


def assert_denominators(result, repetitions=1):
    assert result["planned_slots"] == 14 * repetitions
    assert result["question_opportunities"] == 42 * repetitions
    assert len(result["slots"]) == 14 * repetitions
    assert len(result["groups"]) == 2 * repetitions
    for group in result["groups"]:
        assert group["planned_cases"] == sum(group["cases_by_status"].values()) == 7
        assert group["question_opportunities"] == sum(group["questions_by_status"].values()) == 21


def assert_offline(result):
    for key in (
        "runtime_observed",
        "provider_freshness_verified",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "model_quality_measured",
        "actual_timer_enforced",
    ):
        assert result[key] is False
    assert result["live_trials"] == result["provider_calls_by_this_tool"] == 0
    assert result["scoring_status"] == "not-run"
    assert result["transport_status"] == "not-implemented"
    assert result["observation_origin"] == "caller-supplied-offline-simulation"


@pytest.mark.parametrize("value", [True, False, -1, 1.0, "1", None, 1 << 63])
@pytest.mark.parametrize("field", ["monotonic_ns", "wall_ns"])
def test_clock_rejects_wrong_types_and_ranges(value, field):
    values = {"monotonic_ns": 0, "wall_ns": 0, field: value}
    with pytest.raises(state.DispatchError, match="invalid-clock"):
        state.Clock(**values)


def test_clock_extremes_and_preview_deadline_overflow(candidate):
    state.Clock(0, 0)
    state.Clock(state.MAX_CLOCK_NS, state.MAX_CLOCK_NS)
    with pytest.raises(state.DispatchError, match="clock-overflow"):
        state.Batch(candidate, clock(state.MAX_CLOCK_NS - 1))


@pytest.mark.parametrize("delay,accepted", [(0, True), (300 * NS - 1, True), (300 * NS, False)])
def test_confirmation_exact_boundary(batch, delay, accepted):
    result = approve(batch, delay)
    assert result["phase"] == ("running" if accepted else "stopped")
    assert result["dispatch_deadline_ns"] == (delay + 620 * NS if accepted else None)
    assert_denominators(result)
    assert_offline(result)


@pytest.mark.parametrize("decision", [False, 0, 1, "approve", None, [], {}])
def test_decisions_are_terminal_without_authenticated_permission(batch, decision):
    result = batch.decide(
        batch.revision, clock(), preview_id=batch.revision.preview_id, approve=decision
    )
    reason = "declined" if decision is False else "invalid-decision"
    assert result["stop_reason"] == reason
    assert all(s["status"] == "skipped-" + reason for s in result["slots"])
    assert result["reserved_slots"] == result["simulated_send_attempts"] == 0
    with pytest.raises(state.DispatchError, match="decision-already-terminal"):
        approve(batch)
    assert_offline(result)


@pytest.mark.parametrize("identity", ["stale", "", None, True, [], {}])
def test_stale_or_invalid_batch_decision_is_terminal(batch, identity):
    result = batch.decide(batch.revision, clock(), preview_id=identity, approve=True)
    assert result["stop_reason"] == "invalid-decision"


def test_preview_identity_has_fresh_namespace_and_old_other_revision_cannot_mutate(candidate):
    first, second = state.Batch(candidate, clock()), state.Batch(candidate, clock())
    assert first.revision.preview_id != second.revision.preview_id
    previous = first.snapshot()
    for revision in (second.revision, replace(first.revision, number=True), "forged", None):
        with pytest.raises(state.DispatchError, match="stale-revision"):
            first.decide(revision, clock(1), preview_id=first.revision.preview_id, approve=True)
        assert first.snapshot() == previous
    stale = first.revision
    approve(first)
    current = first.snapshot()
    with pytest.raises(state.DispatchError, match="stale-revision"):
        first.reserve(stale, clock(3))
    assert first.snapshot() == current


def test_snapshot_and_preview_are_detached_and_copy_is_not_a_second_ledger(batch):
    snapshot = batch.snapshot()
    snapshot["slots"][0]["status"] = "valid"
    snapshot["configuration"]["effort"] = "other"
    preview = batch.preview()
    preview["candidate"]["invocations"][0]["message_text"] = "changed"
    preview["recipe"]["configuration"]["effort"] = "other"
    assert batch.snapshot()["slots"][0]["status"] == "planned"
    assert batch.snapshot()["configuration"]["effort"] == "medium"
    for copier in (copy.copy, copy.deepcopy):
        with pytest.raises(state.DispatchError, match="ledger-copy-unsupported"):
            copier(batch)


@pytest.mark.parametrize("repetitions,window", [(1, 1880), (2, 3700), (3, 5520)])
def test_maximum_windows_and_complete_null_runs(repetitions, window):
    candidate = codec.prepare_candidate(
        codec.ROOT, configuration(repetitions=repetitions, timeout=120)
    )
    batch = state.Batch(candidate, clock())
    assert batch.snapshot()["dispatch_window_seconds"] == window
    result = state.dry_run(batch)
    assert result["phase"] == "completed"
    assert result["reserved_slots"] == result["simulated_send_attempts"] == 14 * repetitions
    assert all(s["status"] == "valid" and s["cleanup_confirmed"] for s in result["slots"])
    assert [s["invocation_id"] for s in result["slots"]] == [
        i.invocation_id for i in candidate.invocations
    ]
    assert_denominators(result, repetitions)
    assert_offline(result)


def test_serial_order_send_ack_and_completion_are_distinct(batch, candidate):
    with pytest.raises(state.DispatchError, match="reservation-not-available"):
        batch.reserve(batch.revision, clock())
    approve(batch)
    result = batch.reserve(batch.revision, clock(1))
    assert result["reserved_slots"] == 1
    assert result["simulated_send_attempts"] == 0
    assert result["active_ordinal"] == 1
    for method, message in (
        ("reserve", "reservation-not-available"),
        ("acknowledge", "ack-without-attempt"),
    ):
        with pytest.raises(state.DispatchError, match=message):
            getattr(batch, method)(batch.revision, clock(2))
    with pytest.raises(state.DispatchError, match="completion-without-ack"):
        batch.finish(batch.revision, clock(2), raw=raw_for(candidate), cleanup_confirmed=True)
    batch.mark_send(batch.revision, clock(2))
    with pytest.raises(state.DispatchError, match="send-already-attempted"):
        batch.mark_send(batch.revision, clock(3))
    with pytest.raises(state.DispatchError, match="completion-without-ack"):
        batch.finish(batch.revision, clock(3), raw=raw_for(candidate), cleanup_confirmed=True)
    batch.acknowledge(batch.revision, clock(3))
    result = batch.finish(batch.revision, clock(4), raw=raw_for(candidate), cleanup_confirmed=True)
    assert result["slots"][0]["status"] == "valid"
    assert result["phase"] == "running"
    result = batch.reserve(batch.revision, clock(5))
    assert result["active_ordinal"] == 2


@pytest.mark.parametrize("offset,expired", [(-1, False), (0, True), (1, True)])
def test_dispatch_cutoff_on_reservation(batch, offset, expired):
    approve(batch)
    deadline = batch.snapshot()["dispatch_deadline_ns"]
    result = batch.reserve(batch.revision, clock(deadline + offset))
    assert result["active_ordinal"] == (None if expired else 1)
    assert result["stop_reason"] == ("expired" if expired else None)
    assert_denominators(result)


def test_prewrite_expiry_preserves_reserved_no_send_and_cleanup(batch):
    approve(batch)
    deadline = batch.snapshot()["dispatch_deadline_ns"]
    batch.reserve(batch.revision, clock(deadline - NS))
    result = batch.mark_send(batch.revision, clock(deadline))
    assert result["phase"] == "draining-expired"
    first = result["slots"][0]
    assert first["reserved"] and first["send_state"] == "not-attempted"
    assert first["pending_terminal"] == "skipped-expired"
    assert first["cleanup_confirmed"] is None
    result = batch.finish(batch.revision, clock(deadline + 1), cleanup_confirmed=True)
    assert result["slots"][0]["status"] == "skipped-expired"
    assert result["slots"][0]["cleanup_confirmed"] is True
    assert result["simulated_send_attempts"] == 0
    assert_denominators(result)


def test_already_sent_slot_drains_under_original_budget_after_window(batch, candidate):
    approve(batch)
    deadline = batch.snapshot()["dispatch_deadline_ns"]
    reserve_ack(batch, deadline - 2 * NS)
    result = batch.checkpoint(batch.revision, clock(deadline))
    assert result["phase"] == "draining-expired"
    assert result["slots"][0]["pending_terminal"] is None
    result = batch.finish(
        batch.revision, clock(deadline + NS), raw=raw_for(candidate), cleanup_confirmed=True
    )
    assert result["slots"][0]["status"] == "valid"
    assert all(s["status"] == "skipped-expired" for s in result["slots"][1:])
    assert result["phase"] == "stopped"
    assert_denominators(result)


def test_startup_and_send_do_not_reset_the_single_slot_timer(batch, candidate):
    approve(batch)
    batch.reserve(batch.revision, clock(0))
    batch.mark_send(batch.revision, clock(29 * NS))
    batch.acknowledge(batch.revision, clock(29 * NS + 1))
    result = batch.finish(
        batch.revision, clock(30 * NS), raw=raw_for(candidate), cleanup_confirmed=True
    )
    assert result["slots"][0]["status"] == "timeout"
    assert result["slots"][0]["reserved_ns"] == 0
    assert result["slots"][0]["primary_failure"] == "timeout"
    assert result["slots"][0]["decoded_status"] is None


def test_final_sent_slot_can_complete_after_dispatch_cutoff(batch, candidate):
    approve(batch)
    for index in range(13):
        reserve_ack(batch, index * 10)
        batch.finish(
            batch.revision,
            clock(index * 10 + 3),
            raw=raw_for(candidate, index),
            cleanup_confirmed=True,
        )
    deadline = batch.snapshot()["dispatch_deadline_ns"]
    reserve_ack(batch, deadline - NS)
    result = batch.finish(
        batch.revision,
        clock(deadline + NS),
        raw=raw_for(candidate, 13),
        cleanup_confirmed=True,
    )
    assert result["phase"] == "completed"
    assert result["stop_reason"] is None
    assert all(s["status"] == "valid" for s in result["slots"])


def test_generation_completion_and_cleanup_clock_are_separate(batch, candidate):
    approve(batch)
    reserve_ack(batch)
    result = batch.finish(
        batch.revision,
        clock(29 * NS),
        raw=raw_for(candidate),
        cleanup_confirmed=True,
        cleanup_clock=clock(34 * NS),
    )
    assert result["slots"][0]["status"] == "valid"
    assert result["phase"] == "running"
    assert result["cleanup_wait_timing"] == "not-modeled-per-process"
    result = batch.reserve(batch.revision, clock(34 * NS + 1))
    assert result["active_ordinal"] == 2


def test_pending_timeout_still_records_cleanup_clock_failure(batch):
    approve(batch)
    reserve_ack(batch)
    result = batch.checkpoint(batch.revision, clock(30 * NS))
    assert result["slots"][0]["primary_failure"] == "timeout"
    result = batch.finish(
        batch.revision,
        clock(30 * NS),
        cleanup_confirmed=True,
        cleanup_clock=clock(31 * NS, 37 * NS),
    )
    assert result["slots"][0]["primary_failure"] == "timeout"
    assert result["slots"][0]["clock_failure"] is True
    assert result["slots"][0]["status"] == "timeout"
    assert result["stop_reason"] == "clock"


def test_valid_generation_with_bad_cleanup_clock_is_not_success(batch, candidate):
    approve(batch)
    reserve_ack(batch)
    result = batch.finish(
        batch.revision,
        clock(4),
        raw=raw_for(candidate),
        cleanup_confirmed=True,
        cleanup_clock=clock(3),
    )
    assert result["slots"][0]["decoded_status"] == "valid"
    assert result["slots"][0]["status"] == "failed"
    assert result["slots"][0]["clock_failure"] is True
    assert result["stop_reason"] == "clock"


def test_earlier_window_cutoff_wins_when_both_unsent_deadlines_pass():
    candidate = codec.prepare_candidate(codec.ROOT, configuration(timeout=1))
    batch = state.Batch(candidate, clock())
    approve(batch)
    deadline = batch.snapshot()["dispatch_deadline_ns"]
    batch.reserve(batch.revision, clock(deadline - NS // 2))
    result = batch.mark_send(batch.revision, clock(deadline + NS))
    assert result["slots"][0]["send_state"] == "not-attempted"
    assert result["slots"][0]["pending_terminal"] == "skipped-expired"
    assert result["stop_reason"] == "expired"


@pytest.mark.parametrize("skew,failed", [(5 * NS, False), (5 * NS + 1, True), (-5 * NS - 1, True)])
def test_clock_discrepancy_strict_threshold(candidate, skew, failed):
    batch = state.Batch(candidate, clock(10 * NS))
    result = batch.decide(
        batch.revision,
        clock(20 * NS, 20 * NS + skew),
        preview_id=batch.revision.preview_id,
        approve=True,
    )
    assert (result["stop_reason"] == "clock") is failed


def test_clock_anchor_does_not_move_on_acceptance_or_per_slot(batch):
    batch.decide(
        batch.revision, clock(NS, 3 * NS), preview_id=batch.revision.preview_id, approve=True
    )
    batch.reserve(batch.revision, clock(2 * NS, 6 * NS))
    result = batch.mark_send(batch.revision, clock(3 * NS, 9 * NS))
    assert result["stop_reason"] == "clock"
    assert result["slots"][0]["send_state"] == "not-attempted"
    assert result["slots"][0]["primary_failure"] == "clock-integrity"


def test_monotonic_regression_cancels_active_and_primary_survives_cleanup_failure(batch):
    approve(batch)
    reserve_ack(batch, 10 * NS)
    result = batch.checkpoint(batch.revision, clock(10 * NS + 1))
    assert result["stop_reason"] == "clock"
    assert result["slots"][0]["cleanup_confirmed"] is None
    result = batch.finish(batch.revision, clock(20 * NS), cleanup_confirmed=False)
    assert result["slots"][0]["status"] == "failed"
    assert result["slots"][0]["primary_failure"] == "clock-integrity"
    assert result["slots"][0]["cleanup_confirmed"] is False
    assert result["stop_reason"] == "cleanup"
    assert all(s["status"] == "skipped-clock" for s in result["slots"][1:])


def test_checkpoint_expiry_before_decision_and_accepted_overflow(candidate):
    batch = state.Batch(candidate, clock())
    assert batch.checkpoint(batch.revision, clock(300 * NS))["stop_reason"] == "expired"
    created = state.MAX_CLOCK_NS - recipe.CONFIRM_TTL_NS
    batch = state.Batch(candidate, clock(created))
    result = approve(batch, created)
    assert result["stop_reason"] == "clock"
    assert result["dispatch_deadline_ns"] is None


@pytest.mark.parametrize("raw,expected", [(None, "missing"), ("not-json", "invalid")])
def test_missing_and_invalid_are_not_unknown_or_retried(batch, raw, expected):
    approve(batch)
    reserve_ack(batch)
    result = batch.finish(batch.revision, clock(3), raw=raw, cleanup_confirmed=True)
    assert result["slots"][0]["status"] == expected
    assert result["slots"][0]["decoded_status"] == expected
    assert result["phase"] == "stopped"
    assert all(s["status"] == "skipped-stopped" for s in result["slots"][1:])
    assert result["simulated_send_attempts"] == 1
    assert_denominators(result)


@pytest.mark.parametrize("failure", state.FAILURES)
@pytest.mark.parametrize("cleanup", [True, False])
def test_explicit_failure_without_send_and_cleanup_are_separate(batch, failure, cleanup):
    approve(batch)
    batch.reserve(batch.revision, clock())
    result = batch.finish(batch.revision, clock(1), failure=failure, cleanup_confirmed=cleanup)
    first = result["slots"][0]
    assert first["send_state"] == "not-attempted"
    assert first["primary_failure"] == failure
    assert first["cleanup_confirmed"] is cleanup
    assert result["simulated_send_attempts"] == 0
    assert first["status"] == (failure if cleanup and failure != "integrity" else "failed")
    if failure == "integrity" and cleanup:
        assert result["stop_reason"] == "integrity"
    assert_denominators(result)


def test_valid_decode_with_unconfirmed_cleanup_is_not_success(batch, candidate):
    approve(batch)
    reserve_ack(batch)
    result = batch.finish(batch.revision, clock(3), raw=raw_for(candidate), cleanup_confirmed=False)
    first = result["slots"][0]
    assert first["decoded_status"] == "valid" and first["status"] == "failed"
    assert first["primary_failure"] is None and first["cleanup_confirmed"] is False
    assert all(s["status"] == "skipped-cleanup" for s in result["slots"][1:])


@pytest.mark.parametrize("cleanup", [1, 0, None, "yes"])
def test_cleanup_assertion_is_strict_and_does_not_consume_revision(batch, cleanup):
    approve(batch)
    batch.reserve(batch.revision, clock())
    previous = batch.snapshot()
    with pytest.raises(state.DispatchError, match="invalid-cleanup-assertion"):
        batch.finish(batch.revision, clock(1), failure="failed", cleanup_confirmed=cleanup)
    assert batch.snapshot() == previous


@pytest.mark.parametrize("stage", ["reserve", "mark_send"])
def test_candidate_integrity_is_rechecked_before_reservation_and_prewrite(batch, stage):
    approve(batch)
    if stage == "mark_send":
        batch.reserve(batch.revision, clock())
    object.__setattr__(batch._candidate.invocations[0], "original_message", "{}")
    result = getattr(batch, stage)(batch.revision, clock(1))
    assert result["stop_reason"] == "integrity"
    assert result["simulated_send_attempts"] == 0


def test_recipe_hash_change_is_not_silently_accepted(batch, monkeypatch):
    approve(batch)
    monkeypatch.setattr(recipe, "recipe_id", lambda config: "changed")
    result = batch.reserve(batch.revision, clock(1))
    assert result["stop_reason"] == "integrity"


def test_invalidated_candidate_configuration_keeps_original_denominators_visible(batch):
    approve(batch)
    object.__setattr__(batch._candidate.session, "configuration", None)
    result = batch.reserve(batch.revision, clock(1))
    assert result["stop_reason"] == "integrity"
    assert result["configuration"] == {
        "model": "offline-model",
        "effort": "medium",
        "repetitions": 1,
        "timeout_seconds": 30,
    }
    assert_denominators(result)


@pytest.mark.parametrize("fault", state.FAULTS)
def test_all_cli_fault_simulations_preserve_counts_and_false_flags(batch, fault):
    result = state.dry_run(batch, fault)
    assert result["phase"] == "stopped"
    assert_denominators(result)
    assert_offline(result)
    assert result["simulated_send_attempts"] <= 1


def test_state_and_dry_run_have_no_file_network_process_or_reference_access(batch, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("I/O is forbidden in the in-memory simulation")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = state.dry_run(batch)
    assert result["phase"] == "completed"
    assert_offline(result)


def test_cli_json_is_one_synthetic_result_and_human_output_is_explicit(capsys):
    args = [
        "--model",
        "offline-model",
        "--effort",
        "medium",
        "--repetitions",
        "1",
        "--timeout-seconds",
        "30",
    ]
    assert state.main([*args, "--dry-run", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["phase"] == "completed"
    assert_offline(result)
    assert state.main([*args, "--dry-run", "--fault", "clock"]) == 0
    text = capsys.readouterr().out
    assert "OFFLINE DISPATCH SIMULATION" in text and "UNVERIFIED" in text
    assert "State: stopped; reason: clock" in text


def test_cli_has_no_live_import_or_auto_approval_option(capsys):
    args = [
        "--model",
        "offline-model",
        "--effort",
        "medium",
        "--repetitions",
        "1",
        "--timeout-seconds",
        "30",
    ]
    for option in ("--live", "--receipt-file", "--approve", "--resume", "--fault"):
        with pytest.raises(SystemExit):
            state.main([*args, option])
    with pytest.raises(SystemExit):
        state.main([*args, "--fault", "missing"])
    capsys.readouterr()
