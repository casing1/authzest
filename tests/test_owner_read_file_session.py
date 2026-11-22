"""Exercise the private coordinator with inert artifacts and supplied fake guest captures."""

import hashlib
import json
from pathlib import Path

import pytest

from authzest.codex.owner_read_suggestion import build_owner_read_request
from authzest.owner_read_demo.checks import owner_read_controls
from authzest.runner import _owner_read_copy_files as files
from authzest.runner._owner_read_file_session import OwnerReadFileSession
from authzest.runner._owner_read_phase_result import validate_owner_read_phase
from authzest.runner.owner_read_suggestion import _changes

SOURCE = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_owner_archive(owner_client):\n"
    '    assert owner_client.get("/records/archived-note").status_code == 200\n'
)


def evidence(capture, *, wrong=False, cleanup=True):
    before = capture["phase"] == "before"
    cases = owner_read_controls()
    base = {
        "kind": "owner-read-guest-observation",
        "schema_version": "1.0",
        "source_sha256": capture["source_sha256"],
        "test_sha256": capture["test_sha256"],
    }
    regression = {
        "status": "assertion-failed" if before else "passed",
        "pytest_exit": int(before),
        "collected": 1,
        "setup": "passed",
        "call": "failed" if before else "passed",
        "teardown": "passed",
        "requests": 1,
        "response": cases[1]["before" if before else "intended"],
    }
    observations = [
        {"case_id": case["case_id"], **case["before" if before or wrong else "intended"]}
        for case in cases
    ]
    rows = {
        "test": {**base, "role": "test", "regression": regression},
        "controls": {**base, "role": "controls", "observations": observations},
    }
    captures = {
        role: {
            "exit_code": 0,
            "stdout": json.dumps(row).encode(),
            "stderr": b"",
            "cleanup_confirmed": cleanup,
        }
        for role, row in rows.items()
    }
    return validate_owner_read_phase(
        phase=capture["phase"],
        plan_id=capture["plan_id"],
        source_sha256=capture["source_sha256"],
        test_sha256=capture["test_sha256"],
        captures=captures,
    )


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(files, "_TEMP_PARENT", tmp_path)
    request = build_owner_read_request("offline-owner-session")
    proposal = {
        "request_id": request.request_id,
        "status": "proposed-change",
        "source": SOURCE,
        "test": TEST,
        "rationale": "Offline fake proposal.",
    }
    diffs = _changes(request, proposal)

    def inputs():
        return request, proposal, diffs

    plans, calls = [], []
    now = [10.0]

    def dispatch(capture, *, guard):
        guard()
        calls.append(capture)
        return evidence(capture)

    def session(dispatcher=dispatch):
        return OwnerReadFileSession(
            sharing_id="share-offline-session",
            inputs=inputs,
            dispatcher=dispatcher,
            clock=lambda: now[0],
        )

    def emit(text):
        plans.append(json.loads(text))

    def approve(prompt):
        stage = plans[-1]["stage"]
        return stage + " " + plans[-1]["plan_id"]

    return session, emit, approve, plans, calls, now, proposal, diffs


def test_complete_flow_preserves_baseline_and_test_bytes_and_records_intent(setup):
    session, emit, approve, plans, calls, _, _, _ = setup
    flow = session()
    value = flow.run(emit=emit, read=approve)
    assert value["status"] == "completed", value
    assert value["exit_code"] == 0 and value["recovery_required"] is False
    assert value["patch_application"] == "applied-to-copy"
    assert value["restoration_status"] == "restored"
    assert value["descriptor_cleanup_confirmed"] is True
    assert [plan["stage"] for plan in plans] == [
        "copy",
        "before",
        "diff",
        "apply",
        "after",
        "restore",
    ]
    assert [call["phase"] for call in calls] == ["before", "after"]
    path = Path(value["copy"]["path"])
    assert (path / "availability.py").read_bytes() == calls[0]["source"]
    assert calls[1]["source"] == SOURCE.encode()
    assert (path / "test_owner_archived_read.py").read_text() == TEST
    assert (path / "proposed-availability.txt").read_text() == SOURCE
    record = json.loads((path / "record.json").read_text())
    assert record["state"] == "restored-before"
    for call in calls:
        assert call["source_sha256"] == hashlib.sha256(call["source"]).hexdigest()
    with pytest.raises(ValueError, match="twice"):
        flow.run()


@pytest.mark.parametrize("stage", ["copy", "before", "diff", "apply", "after", "restore"])
def test_each_decision_is_required_and_stale_answers_do_not_approve(setup, stage):
    session, emit, approve, plans, calls, _, _, _ = setup

    def read(prompt):
        if plans[-1]["stage"] == stage:
            return stage + " stale"
        return approve(prompt)

    value = session().run(emit=emit, read=read)
    assert value["status"] == "declined", value
    assert value["stages"][stage]["status"] == "declined"
    if stage in ("copy", "before"):
        assert calls == []
    if stage in ("copy", "before", "diff", "apply"):
        assert value["patch_application"] == "not-run"
    elif stage == "after":
        assert value["restoration_status"] == "restored"
    else:
        assert value["recovery_required"] is True
        assert value["restoration_status"] == "required"


@pytest.mark.parametrize("stage", ["copy", "before", "diff", "apply", "after", "restore"])
def test_decisions_expire_without_retry(setup, stage):
    session, emit, approve, plans, calls, now, _, _ = setup

    def read(prompt):
        answer = approve(prompt)
        if plans[-1]["stage"] == stage:
            now[0] += 300
        return answer

    value = session().run(emit=emit, read=read)
    assert value["status"] == "expired", value
    assert value["stages"][stage]["status"] == "expired"
    assert len(calls) <= 2
    if stage == "after":
        assert value["restoration_status"] == "restored"


def test_changed_current_proposal_stops_before_copy(setup):
    session, emit, approve, _, calls, _, proposal, diffs = setup

    def read(prompt):
        answer = approve(prompt)
        proposal["rationale"] = "Changed after preview."
        return answer

    value = session().run(emit=emit, read=read)
    assert value["status"] == "inputs-changed" and value["copy"] is None and calls == []


def test_user_source_edit_after_application_is_preserved(setup):
    session, emit, approve, plans, _, _, _, _ = setup
    modified = []

    def read(prompt):
        answer = approve(prompt)
        if plans[-1]["stage"] == "after":
            path = Path(plans[-1]["files"]["path"]) / "availability.py"
            path.write_text("User edit\n")
            modified.append(path)
        return answer

    value = session().run(emit=emit, read=read)
    assert value["status"] == "state-unconfirmed", value
    assert value["recovery_required"] is True and value["restoration_status"] == "required"
    assert modified[0].read_text() == "User edit\n"
    assert value["after"] is None


def test_after_independent_control_mismatch_still_allows_separate_restore(setup):
    session, emit, approve, plans, _, _, _, _ = setup

    def dispatch(capture, *, guard):
        guard()
        return evidence(capture, wrong=capture["phase"] == "after")

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "after-mismatch", value
    assert value["exit_code"] == 1
    assert value["after"]["regression"]["status"] == "passed"
    assert value["after"]["comparison"]["intended_matches"] == 6
    assert value["restoration_status"] == "restored" and not value["recovery_required"]
    assert plans[-1]["stage"] == "restore"


def test_unconfirmed_cleanup_blocks_restore(setup):
    session, emit, approve, plans, _, _, _, _ = setup

    def dispatch(capture, *, guard):
        return evidence(capture, cleanup=capture["phase"] == "before")

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "after-failed", value
    assert value["after"]["failure"] == "cleanup-unconfirmed"
    assert plans[-1]["stage"] == "after"
    assert value["recovery_required"] is True


def test_dispatcher_exception_has_no_automatic_retry_or_restore(setup):
    session, emit, approve, plans, _, _, _, _ = setup
    calls = []

    def dispatch(capture, *, guard):
        calls.append(capture["phase"])
        if capture["phase"] == "after":
            raise OSError("Unknown runtime state")
        return evidence(capture)

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "state-unconfirmed", value
    assert calls == ["before", "after"] and plans[-1]["stage"] == "after"
    assert value["recovery_required"] is True and value["after"] is None


def test_dispatcher_cannot_change_the_expected_phase_identity(setup):
    session, emit, approve, plans, _, _, _, _ = setup

    def dispatch(capture, *, guard):
        capture["plan_id"] = "stale-plan"
        return evidence(capture)

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "phase-identity-mismatch"
    assert value["stages"]["before"]["status"] == "unconfirmed"
    assert value["patch_application"] == "not-run" and plans[-1]["stage"] == "before"


def test_directly_constructed_matched_wrapper_cannot_bypass_control_validation(setup):
    from authzest.runner._owner_read_phase_result import OwnerReadPhaseResult

    session, emit, approve, plans, _, _, _, _ = setup

    def dispatch(capture, *, guard):
        value = evidence(capture).to_dict()
        value["cleanup_confirmed"] = False
        return OwnerReadPhaseResult(json.dumps(value))

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "invalid-phase-result"
    assert value["patch_application"] == "not-run" and plans[-1]["stage"] == "before"


def test_control_mismatch_before_prevents_diff_acceptance_and_application(setup):
    session, emit, approve, plans, _, _, _, _ = setup

    def dispatch(capture, *, guard):
        changed = dict(capture, phase="after")
        from authzest.runner._owner_read_phase_result import OwnerReadPhaseResult

        result = evidence(changed).to_dict()
        result["phase"] = "before"
        return OwnerReadPhaseResult(json.dumps(result))

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "invalid-phase-result"
    assert value["stages"]["diff"]["status"] == "not-run"
    assert value["patch_application"] == "not-run"
    assert plans[-1]["stage"] == "before"


def test_slow_validation_cannot_extend_an_apply_decision(setup, monkeypatch):
    session, emit, approve, plans, _, now, _, _ = setup
    flow = session()
    original = flow._check
    slow = [False]

    def check(**kwargs):
        original(**kwargs)
        if slow[0]:
            now[0] += 300

    monkeypatch.setattr(flow, "_check", check)

    def read(prompt):
        if plans[-1]["stage"] == "apply":
            slow[0] = True
        return approve(prompt)

    value = flow.run(emit=emit, read=read)
    assert value["status"] == "expired"
    assert value["patch_application"] == "not-run"
    assert value["stages"]["apply"]["status"] == "expired"


def test_journal_failure_exposes_current_uncertainty_and_retains_source(setup, monkeypatch):
    from authzest.runner._owner_read_workspace import OwnerReadWorkspace

    session, emit, approve, _, _, _, _, _ = setup

    def persist(*args, **kwargs):
        raise OSError("Synthetic journal failure")

    monkeypatch.setattr(OwnerReadWorkspace, "_persist", persist)
    value = session().run(emit=emit, read=approve)
    assert value["status"] == "state-unconfirmed"
    assert value["recovery_required"] is True
    assert value["workspace_state"] == "state-unconfirmed"
    assert value["workspace_failure"]["stage"] == "record-event-before"
    assert value["last_verified_workspace"]["state"] == "state-unconfirmed"
    assert value["descriptor_cleanup_confirmed"] is True
    assert value["guest_cleanup_confirmed"] is None
    assert value["patch_application"] == "not-run"


def test_dispatcher_edit_followed_by_exception_is_reported_as_current_uncertainty(setup):
    session, emit, approve, plans, _, _, _, _ = setup
    changed = []

    def dispatch(capture, *, guard):
        if capture["phase"] == "after":
            path = Path(plans[-1]["files"]["path"]) / "availability.py"
            path.write_text("User edit during runtime\n")
            changed.append(path)
            raise RuntimeError("Dispatcher cleanup unknown")
        return evidence(capture)

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "dispatcher-failed"
    assert value["workspace_state"] == "state-unconfirmed"
    assert value["last_verified_workspace"]["state"] == "applied-after"
    assert value["guest_cleanup_confirmed"] is None
    assert value["recovery_required"] is True
    assert changed[0].read_text() == "User edit during runtime\n"


@pytest.mark.parametrize("exception", [False, True])
def test_before_guest_cleanup_uncertainty_requires_recovery_without_a_source_change(
    setup, exception
):
    session, emit, approve, plans, _, _, _, _ = setup

    def dispatch(capture, *, guard):
        if exception:
            raise RuntimeError("Before guest cleanup unknown")
        return evidence(capture, cleanup=False)

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == ("dispatcher-failed" if exception else "before-failed")
    assert value["stages"]["before"]["guest_dispatch_started"] is True
    assert value["guest_cleanup_confirmed"] is (None if exception else False)
    assert value["recovery_required"] is True
    assert value["restoration_status"] == "not-needed"
    assert value["patch_application"] == "not-run"
    assert plans[-1]["stage"] == "before"


def test_guard_expiry_inside_after_dispatch_cannot_be_treated_as_no_dispatch(setup):
    session, emit, approve, plans, _, now, _, _ = setup

    def dispatch(capture, *, guard):
        if capture["phase"] == "after":
            now[0] += 300
            guard()
        return evidence(capture)

    value = session(dispatch).run(emit=emit, read=approve)
    assert value["status"] == "expired"
    assert value["stages"]["after"]["guest_dispatch_started"] is True
    assert value["stages"]["after"]["status"] == "expired"
    assert value["after"] is None and value["guest_cleanup_confirmed"] is None
    assert value["recovery_required"] is True and value["restoration_status"] == "required"
    assert value["stages"]["restore"]["status"] == "not-run"
    assert plans[-1]["stage"] == "after"
    assert (Path(value["copy"]["path"]) / "availability.py").read_text() == SOURCE


def test_descriptor_cleanup_uncertainty_remains_recovery_required_after_restoration(
    setup, monkeypatch
):
    from authzest.runner._owner_read_workspace import OwnerReadWorkspace

    session, emit, approve, _, _, _, _, _ = setup
    close = OwnerReadWorkspace.close

    def uncertain_close(workspace):
        close(workspace)
        raise OSError("Descriptor closure unconfirmed")

    monkeypatch.setattr(OwnerReadWorkspace, "close", uncertain_close)
    value = session().run(emit=emit, read=approve)
    assert value["status"] == "descriptor-cleanup-unconfirmed"
    assert value["descriptor_cleanup_confirmed"] is False
    assert value["recovery_required"] is True
    assert value["restoration_status"] == "restored"
    assert value["exit_code"] == 1


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_interrupted_initial_journal_retains_partial_file_and_adoption_failure(
    setup, monkeypatch, interruption
):
    import os

    from authzest.runner._owner_read_workspace import OwnerReadWorkspace

    session, emit, approve, _, _, _, _, _ = setup
    original_create = OwnerReadWorkspace._create

    def interrupted_create(workspace, name, data):
        if name != "record.json":
            return original_create(workspace, name, data)
        descriptor = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=workspace._fd
        )
        try:
            os.write(descriptor, b"{")
        finally:
            os.close(descriptor)
        raise interruption

    monkeypatch.setattr(OwnerReadWorkspace, "_create", interrupted_create)
    value = session().run(emit=emit, read=approve)
    assert value["status"] == "cancelled" and value["exit_code"] == 130
    assert value["recovery_required"] is True
    assert value["workspace_failure"]["stage"] == "create-initial-record"
    assert value["workspace_failure"]["state"] == "state-unconfirmed"
    assert value["descriptor_cleanup_confirmed"] is True
    assert value["patch_application"] == "not-run"
    assert (Path(value["copy"]["path"]) / "record.json").read_bytes() == b"{"


def test_interrupted_apply_intent_preserves_workspace_failure_metadata(setup, monkeypatch):
    from authzest.runner._owner_read_workspace import OwnerReadWorkspace

    session, emit, approve, _, _, _, _, _ = setup
    persist = OwnerReadWorkspace._persist

    def interrupted_intent(workspace, state, *, pending=None):
        persist(workspace, state, pending=pending)
        if pending == "apply":
            raise KeyboardInterrupt

    monkeypatch.setattr(OwnerReadWorkspace, "_persist", interrupted_intent)
    value = session().run(emit=emit, read=approve)
    assert value["status"] == "cancelled" and value["exit_code"] == 130
    assert value["recovery_required"] is True
    assert value["workspace_failure"]["stage"] == "persist-apply-intent"
    assert value["workspace_failure"]["source_replace_attempted"] is False
    assert value["workspace_failure"]["source_replaced"] is False
    assert value["descriptor_cleanup_confirmed"] is True


@pytest.mark.parametrize("interrupted", [False, True])
def test_incomplete_copy_preserves_partial_recovery_and_cancellation(
    setup, monkeypatch, interrupted
):
    from authzest.runner import _owner_read_file_session as module

    session, emit, approve, plans, calls, _, _, _ = setup
    original = module.stage_private_copy

    def partial(*args, **kwargs):
        value = original(*args, **kwargs)
        value.update(status="incomplete", interrupted=interrupted, exit_code=1)
        return value

    monkeypatch.setattr(module, "stage_private_copy", partial)
    value = session().run(emit=emit, read=approve)
    assert value["status"] == ("cancelled" if interrupted else "copy-incomplete")
    assert value["exit_code"] == (130 if interrupted else 1)
    assert value["recovery_required"] is True
    assert value["copy"]["status"] == "incomplete"
    assert value["copy"]["files"] and value["copy"]["path"] is not None
    assert calls == [] and plans[-1]["stage"] == "copy"
    assert not (Path(value["copy"]["path"]) / "record.json").exists()


def test_explicit_cancel_after_application_stops_without_a_restore_prompt(setup):
    session, emit, approve, plans, _, _, _, _ = setup

    def read(prompt):
        return "cancel" if plans[-1]["stage"] == "after" else approve(prompt)

    value = session().run(emit=emit, read=read)
    assert value["status"] == "cancelled" and value["exit_code"] == 130
    assert value["recovery_required"] is True
    assert value["restoration_status"] == "required"
    assert value["stages"]["restore"]["status"] == "not-run"
    assert plans[-1]["stage"] == "after"


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_final_observation_interruption_still_closes_workspace(setup, monkeypatch, interruption):
    from authzest.runner._owner_read_workspace import OwnerReadWorkspace

    session, emit, approve, _, _, _, _, _ = setup
    flow = session()
    restore = flow._restore
    snapshot = OwnerReadWorkspace.snapshot
    armed = [False]

    def restore_and_arm(*args):
        restore(*args)
        armed[0] = True

    def final_snapshot(workspace):
        if armed[0]:
            raise interruption
        return snapshot(workspace)

    monkeypatch.setattr(flow, "_restore", restore_and_arm)
    monkeypatch.setattr(OwnerReadWorkspace, "snapshot", final_snapshot)
    value = flow.run(emit=emit, read=approve)
    assert value["status"] == "cancelled" and value["exit_code"] == 130
    assert value["descriptor_cleanup_confirmed"] is True
    assert flow._workspace._fd == -1
    assert value["workspace_state"] == "state-unconfirmed"
    assert value["recovery_required"] is True
