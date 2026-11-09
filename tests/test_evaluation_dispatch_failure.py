"""Retain first caller-declared failures during synthetic cleanup, never live calls."""

from __future__ import annotations

import builtins
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_dispatch as state
from scripts import evaluation_invocation as codec
from scripts import evaluation_trial_plan as planner

NS = 1_000_000_000


def clock(seconds=0, *, drift=0):
    return state.Clock(seconds * NS, (seconds + drift) * NS)


@pytest.fixture
def batch():
    configuration = planner.TrialConfig("synthetic-model", "high", 1, 30)
    candidate = codec.prepare_candidate(codec.ROOT, configuration)
    result = state.Batch(candidate, clock())
    result.decide(result.revision, clock(), preview_id=result.revision.preview_id, approve=True)
    result.reserve(result.revision, clock())
    return result


def assert_denominators(result):
    assert result["planned_slots"] == len(result["slots"]) == 14
    assert result["question_opportunities"] == 42
    for group in result["groups"]:
        assert group["planned_cases"] == sum(group["cases_by_status"].values()) == 7
        assert group["question_opportunities"] == sum(group["questions_by_status"].values()) == 21
    assert result["runtime_observed"] is False
    assert result["provider_calls_by_this_tool"] == result["live_trials"] == 0


@pytest.mark.parametrize("failure", state.FAILURES)
def test_failure_at_one_second_survives_timeout_boundary_checkpoint_and_finish(batch, failure):
    first = batch.fail(batch.revision, clock(1), failure=failure)
    expected = "failed" if failure == "integrity" else failure
    assert first["active_ordinal"] == 1
    assert first["slots"][0]["pending_terminal"] == expected
    assert first["slots"][0]["primary_failure"] == failure
    assert all(slot["status"].startswith("skipped-") for slot in first["slots"][1:])
    batch.checkpoint(batch.revision, clock(30))
    final = batch.finish(batch.revision, clock(30), cleanup_confirmed=True)
    assert final["slots"][0]["status"] == expected
    assert final["slots"][0]["primary_failure"] == failure
    assert final["slots"][0]["cleanup_confirmed"] is True
    assert_denominators(final)


def test_second_report_does_not_replace_retained_primary_or_unsent_denominators(batch):
    first = batch.fail(batch.revision, clock(1), failure="interrupted")
    final = batch.fail(batch.revision, clock(2), failure="integrity")
    assert final["revision"] == first["revision"] + 1
    assert final["slots"][0]["pending_terminal"] == "interrupted"
    assert final["slots"][0]["primary_failure"] == "interrupted"
    assert final["slots"][1:] == first["slots"][1:]
    assert_denominators(final)


def test_clock_timeout_at_failure_receipt_wins_before_new_failure_is_installed(batch):
    result = batch.fail(batch.revision, clock(30), failure="interrupted")
    assert result["slots"][0]["primary_failure"] == "timeout"
    assert result["slots"][0]["pending_terminal"] == "timeout"
    final = batch.finish(batch.revision, clock(30), failure="failed", cleanup_confirmed=True)
    assert final["slots"][0]["primary_failure"] == "timeout"
    assert_denominators(final)


def test_clock_integrity_already_present_at_failure_receipt_wins(batch):
    result = batch.fail(batch.revision, clock(1, drift=6), failure="interrupted")
    assert result["slots"][0]["primary_failure"] == "clock-integrity"
    assert result["slots"][0]["clock_failure"] is True
    assert_denominators(result)


def test_later_clock_drift_and_cleanup_failure_are_secondary_not_new_primary(batch):
    batch.fail(batch.revision, clock(1), failure="interrupted")
    final = batch.finish(
        batch.revision,
        clock(30),
        cleanup_confirmed=False,
        cleanup_clock=clock(31, drift=6),
    )
    slot = final["slots"][0]
    assert slot["primary_failure"] == "interrupted"
    assert slot["clock_failure"] is True
    assert slot["cleanup_confirmed"] is False
    assert slot["status"] == "failed"
    assert final["stop_reason"] == "cleanup"
    assert_denominators(final)


def test_stale_revision_cannot_install_or_replace_failure(batch):
    old = batch.revision
    batch.fail(batch.revision, clock(1), failure="interrupted")
    before = batch.snapshot()
    with pytest.raises(state.DispatchError, match="stale-revision"):
        batch.fail(old, clock(2), failure="integrity")
    assert batch.snapshot() == before


def test_invalid_failure_is_mutation_free_and_no_active_slot_is_rejected(batch):
    for failure in (None, True, [], "private-error", "timeout "):
        before = batch.snapshot()
        with pytest.raises(state.DispatchError, match="invalid-failure"):
            batch.fail(batch.revision, clock(1), failure=failure)
        assert batch.snapshot() == before
    batch.fail(batch.revision, clock(1), failure="interrupted")
    batch.finish(batch.revision, clock(2), cleanup_confirmed=True)
    with pytest.raises(state.DispatchError, match="no-active-slot"):
        batch.fail(batch.revision, clock(3), failure="failed")


def test_failure_recording_and_cleanup_require_no_io_process_network_or_model_calls(
    batch, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("synthetic failure recording must not perform external work")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(codec.collector.secrets, "token_hex", forbidden)
    batch.fail(batch.revision, clock(1), failure="interrupted")
    batch.checkpoint(batch.revision, clock(30))
    result = batch.finish(batch.revision, clock(30), cleanup_confirmed=True)
    assert result["slots"][0]["primary_failure"] == "interrupted"
    assert_denominators(result)
