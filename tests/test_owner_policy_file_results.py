"""Consistency-only checkpoint tests with temporary files and SCRIPTED transport.

These records are neither provider responses nor actual policy observations. No
new policy or worker is executed, compiled, imported or evaluated by these tests.
"""

import asyncio
import copy
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner import _owner_policy_file_workspace as workspace
from authzest.runner import owner_policy_file_repair as session_module
from authzest.runner.owner_policy_file_repair import validate_owner_policy_file_result
from test_owner_policy_file_session import (
    STAGES,
    _act,
    _choose,
    _mock_worker,
    _reach,
)
from test_owner_policy_file_session import (
    offline_guard as offline_guard,
)
from test_owner_policy_file_session import (
    sessions as sessions,
)

pytestmark = pytest.mark.skipif(
    not workspace.supported(),
    reason="Checkpoint fixtures use owned POSIX source-mode temporary copies",
)


def _validate(value):
    return validate_owner_policy_file_result(canonical(value)).to_dict()


@pytest.fixture
def checkpoints(sessions, tmp_path, monkeypatch):
    _mock_worker(monkeypatch)
    session = sessions()
    result = {"initial": session.result().to_dict()}
    result["created"] = session.create_copy(_parent=tmp_path).to_dict()
    for stage in STAGES:
        plan = session.prepare(stage)
        result["pending-" + stage] = session.result().to_dict()
        session.decide(stage, "approved", plan_id=plan.plan_id)
        result["approved-" + stage] = session.result().to_dict()
        result[stage] = _act(session, stage).to_dict()
    session.close()
    result["closed"] = session.result().to_dict()
    return result


def test_every_scripted_workflow_checkpoint_roundtrips(checkpoints):
    for checkpoint in checkpoints.values():
        assert _validate(checkpoint) == checkpoint
    assert checkpoints["before-check"]["checks"]["before"]["comparison_status"] == "failed"
    assert checkpoints["after-check"]["comparison_status"] == "passed"
    assert checkpoints["closed"]["provenance"]["authenticated"] is False
    assert checkpoints["closed"]["authorization_status"] == "unknown"


def test_two_full_plans_remain_within_existing_checkpoint_budget(checkpoints):
    raw = canonical(checkpoints["closed"])
    assert len(raw.encode("utf-8")) <= 256 * 1024
    assert validate_owner_policy_file_result(raw).payload_json == raw


def test_validation_is_pure_and_does_not_reopen_owned_files(checkpoints, monkeypatch):
    import builtins
    import io
    import os

    def forbidden(*args, **kwargs):
        pytest.fail("Checkpoint validation must not perform I/O or restore a session")

    record = checkpoints["closed"]
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(session_module, "OwnerPolicyRepairFileSession", forbidden)
    assert _validate(record) == record


def _assign(data, path, value):
    current = data
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("kind",), []),
        (("application_id",), "forged"),
        (("session_id",), "A" * 32),
        (("workspace",), "relative/path"),
        (("phase",), {}),
        (("phase",), "ready-before"),
        (("generation",), True),
        (("generation",), 2),
        (("closed",), 1),
        (("provider_calls",), False),
        (("authorization_status",), "authorized"),
        (("restart_supported",), True),
        (("provenance", "authenticated"), True),
        (("provenance", "kind"), "worker-attestation"),
        (("application_status",), "not-run"),
        (("restoration_status",), "failed"),
        (("diff_status",), "not-accepted"),
        (("file_binding_status",), []),
        (("evidence_status",), "unknown"),
        (("initialization_stage",), []),
        (("initialization_stage",), "create-policy"),
        (("failure",), {}),
        (("decisions",), []),
        (("attempts_consumed",), [[], "apply"]),
        (("attempts_consumed",), ["apply", "apply"]),
        (("attempts_consumed",), list(STAGES)),
        (("completed",), []),
        (("checks",), []),
        (("checks", "before"), None),
        (("comparison_status",), "failed"),
        (("comparison", 0, "expected"), "deny"),
        (("comparison", 0, "before"), 1),
        (("events",), [{}]),
        (("events",), ["arbitrary-event"]),
    ],
)
def test_malformed_top_level_records_raise_contract_error(checkpoints, path, value):
    record = copy.deepcopy(checkpoints["closed"])
    _assign(record, path, value)
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "after-check"),
        ("session_id", "a" * 32),
        ("plan_id", "owner-file-action-" + "a" * 64),
        ("choice", []),
        ("choice", "declined"),
        ("created_at", True),
        ("created_at", -1),
        ("expires_at", 100),
        ("expires_at", 401),
        ("reviewer_authenticated", True),
    ],
)
def test_check_decisions_are_bound_to_stage_session_plan_and_lifetime(checkpoints, field, value):
    record = copy.deepcopy(checkpoints["closed"])
    record["decisions"]["before-check"][field] = value
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("mapping", ["attempts_consumed", "completed", "decisions"])
def test_completed_stages_cannot_lose_their_choice_consumption_or_link(checkpoints, stage, mapping):
    record = copy.deepcopy(checkpoints["closed"])
    if mapping == "attempts_consumed":
        record[mapping].remove(stage)
    else:
        del record[mapping][stage]
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize("stage", ["before-check", "diff", "apply", "after-check"])
def test_available_completion_hash_links_are_recomputed(checkpoints, stage):
    record = copy.deepcopy(checkpoints["closed"])
    original = record["completed"][stage]
    record["completed"][stage] = original[:-64] + "a" * 64
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("stage",), "after-check"),
        (("candidate",), "after"),
        (("session_id",), "a" * 32),
        (("plan_id",), "owner-file-check-" + "a" * 64),
        (("source_sha256",), "a" * 64),
        (("file_state_sha256",), "a" * 64),
        (("worker_sha256",), "a" * 64),
        (("recipe_sha256",), "a" * 64),
        (("plan",), None),
        (("execution_status",), "not-run"),
        (("comparison_status",), "passed"),
        (("reason",), "cases-match"),
        (("observations", 0), 1),
        (("transport",), None),
        (("transport", "launch_status"), []),
        (("transport", "launch_status"), "ambiguous"),
        (("transport", "reason"), {}),
        (("transport", "reason"), "timeout"),
        (("transport", "exit_code"), True),
        (("transport", "exit_code"), 1),
        (("transport", "child_cleanup_status"), "unconfirmed"),
        (("transport", "workspace_cleanup_status"), "unconfirmed"),
    ],
)
def test_check_identity_observations_and_transport_are_strict(checkpoints, path, value):
    record = copy.deepcopy(checkpoints["closed"])
    _assign(record["checks"]["before"], path, value)
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("stage",), "after-check"),
        (("generation",), True),
        (("generation",), 2),
        (("application_id",), "a" * 64),
        (("workspace",), "/different"),
        (("root_identity",), []),
        (("root_identity", 2), 0o40755),
        (("file", "filename"), "other.py"),
        (("file", "sha256"), "a" * 64),
        (("file", "byte_count"), True),
        (("file", "identity", 2), 0o100644),
        (("file", "identity", 5), 2),
        (("file", "identity", 6), 1),
        (("prior_completions",), {"diff": "a" * 64}),
        (("recipe", "timeout_seconds"), 500),
        (("recipe", "os_sandbox"), True),
        (("worker_input", "source_text"), "print('unregistered')\n"),
        (("worker_input", "policy_source_sha256"), "a" * 64),
        (("worker_input", "file_state_sha256"), "a" * 64),
        (("worker_input", "cases", 0, "principal"), {}),
        (("worker_input", "cases", 0, "input_sha256"), "a" * 64),
    ],
)
def test_full_check_plan_rejects_changed_source_file_recipe_and_inputs(checkpoints, path, value):
    record = copy.deepcopy(checkpoints["closed"])
    _assign(record["checks"]["before"]["plan"], path, value)
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("checks",),
        ("checks", "before"),
        ("checks", "before", "plan"),
        ("checks", "before", "plan", "file"),
        ("checks", "before", "transport"),
        ("decisions", "before-check"),
    ],
)
def test_nested_records_are_closed_shapes(checkpoints, path):
    record = copy.deepcopy(checkpoints["closed"])
    target = record
    for key in path:
        target = target[key]
    target["unexpected"] = None
    with pytest.raises(ContractError):
        _validate(record)


@pytest.mark.parametrize("choice", ["pending", "declined", "cancelled"])
def test_refused_checks_roundtrip_without_claiming_execution(sessions, tmp_path, choice):
    session = sessions()
    session.create_copy(_parent=tmp_path)
    _choose(session, "before-check", choice)
    record = _act(session, "before-check").to_dict()
    assert record["checks"]["before"]["execution_status"] == "not-run"
    assert _validate(record) == record


def test_unprepared_attempts_and_no_change_records_roundtrip(sessions, tmp_path):
    session = sessions()
    assert _validate(_act(session, "before-check").to_dict()) == session.result().to_dict()
    other = sessions(status="no-change")
    record = other.create_copy(_parent=tmp_path).to_dict()
    assert record["workspace"] is None
    assert _validate(record) == record


def test_failed_after_check_can_be_restored_without_fabricated_observations(
    sessions,
    tmp_path,
    monkeypatch,
):
    _mock_worker(monkeypatch, fail_stage="after-check", reason="timeout", exit_code=-15)
    session = sessions()
    _reach(session, tmp_path, "after-check")
    _choose(session, "after-check")
    failed = _act(session, "after-check").to_dict()
    assert failed["checks"]["after"]["observations"] is None
    assert failed["comparison_status"] == "inconclusive"
    assert _validate(failed) == failed
    _choose(session, "restore")
    restored = _act(session, "restore").to_dict()
    assert _validate(restored) == restored


def test_ambiguous_launch_and_cancellation_records_roundtrip(sessions, tmp_path, monkeypatch):
    session = sessions()
    session.create_copy(_parent=tmp_path)
    _choose(session, "before-check")

    async def cancelled(worker_input, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(session_module, "_run_worker", cancelled)
    with pytest.raises(asyncio.CancelledError) as caught:
        _act(session, "before-check")
    record = caught.value.file_repair_result.to_dict()
    assert record["checks"]["before"]["transport"]["launch_status"] == "ambiguous"
    assert _validate(record) == record


def test_rehashed_wrong_observations_cannot_retain_success_status(checkpoints):
    record = copy.deepcopy(checkpoints["closed"])
    check = record["checks"]["after"]
    check["observations"][1] = True
    record["completed"]["after-check"] = "owner-file-observation-" + identity(check)
    with pytest.raises(ContractError):
        _validate(record)


def test_a_consistent_record_remains_unauthenticated_data_not_live_authority(checkpoints):
    record = copy.deepcopy(checkpoints["closed"])
    # Host records are deliberately not signed. This validator checks consistency,
    # not whether a policy worker really ran or a reviewer made these choices.
    result = validate_owner_policy_file_result(canonical(record))
    assert result.to_dict()["provenance"]["authenticated"] is False
    assert not hasattr(result, "apply")
    assert not hasattr(result, "restore")
    assert not hasattr(result, "run_check")


@pytest.mark.parametrize("stage", ["apply", "restore"])
@pytest.mark.parametrize("error", [KeyboardInterrupt, workspace.CommittedWriteError])
def test_uncertain_committed_write_checkpoint_roundtrips(
    sessions,
    tmp_path,
    monkeypatch,
    stage,
    error,
):
    _mock_worker(monkeypatch)
    session = sessions()
    _reach(session, tmp_path, stage)
    _choose(session, stage)
    replace = session._workspace.replace_policy

    def uncertain(*args, **kwargs):
        replace(*args, **kwargs)
        raise error("Scripted confirmation interruption")

    monkeypatch.setattr(session._workspace, "replace_policy", uncertain)
    if error is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt) as caught:
            _act(session, stage)
        record = caught.value.file_repair_result.to_dict()
    else:
        record = _act(session, stage).to_dict()
    assert record["phase"] == "unconfirmed"
    assert _validate(record) == record


def test_retained_incomplete_initialization_checkpoint_roundtrips(
    sessions,
    tmp_path,
    monkeypatch,
):
    retained = tmp_path / "owned-incomplete"
    retained.mkdir()

    def incomplete(*args, **kwargs):
        raise workspace.WorkspaceInitializationError(retained, "create-policy")

    monkeypatch.setattr(session_module, "PolicyFileWorkspace", incomplete)
    record = sessions().create_copy(_parent=tmp_path).to_dict()
    assert record["phase"] == "unconfirmed"
    assert _validate(record) == record


def test_evidence_failure_invalidates_passed_comparison_without_erasing_effect(
    sessions,
    tmp_path,
    monkeypatch,
):
    _mock_worker(monkeypatch)
    session = sessions()
    _reach(session, tmp_path, "restore")
    _choose(session, "restore")

    def fail_record(*args, **kwargs):
        raise OSError("Scripted record failure")

    monkeypatch.setattr(session._workspace, "write_record", fail_record)
    record = session.restore().to_dict()
    assert record["restoration_status"] == "completed"
    assert record["evidence_status"] == "unconfirmed"
    assert record["comparison_status"] == "inconclusive"
    assert _validate(record) == record


def test_missing_child_launch_checkpoint_roundtrips(sessions, tmp_path, monkeypatch):
    _mock_worker(
        monkeypatch,
        fail_stage="before-check",
        output=b"",
        reason="worker-process-error",
        exit_code=None,
        child_cleanup_status="not-needed",
        launch_status="no-child",
    )
    session = sessions()
    session.create_copy(_parent=tmp_path)
    _choose(session, "before-check")
    record = _act(session, "before-check").to_dict()
    assert record["checks"]["before"]["execution_status"] == "not-run"
    assert _validate(record) == record


def test_initial_copy_journal_interruption_preserves_a_valid_retained_checkpoint(
    sessions,
    tmp_path,
    monkeypatch,
):
    def interrupt_record(*args, **kwargs):
        raise KeyboardInterrupt("Scripted initial journal interruption")

    monkeypatch.setattr(workspace.PolicyFileWorkspace, "write_record", interrupt_record)
    with pytest.raises(KeyboardInterrupt) as caught:
        sessions().create_copy(_parent=tmp_path)
    record = caught.value.file_repair_result.to_dict()
    assert record["workspace"] is not None
    assert record["evidence_status"] == "unconfirmed"
    assert record["initialization_stage"] == "write-initial-record"
    assert _validate(record) == record


def test_initial_record_io_failure_keeps_its_stage_after_a_refused_second_creation(
    sessions,
    tmp_path,
    monkeypatch,
):
    def failed_record(*args, **kwargs):
        raise OSError("Scripted initial journal failure")

    monkeypatch.setattr(workspace.PolicyFileWorkspace, "write_record", failed_record)
    session = sessions()
    record = session.create_copy(_parent=tmp_path).to_dict()
    assert record["initialization_stage"] == "write-initial-record"
    assert _validate(record) == record
    again = session.create_copy(_parent=tmp_path).to_dict()
    assert again["failure"] == "copy-already-created"
    assert again["initialization_stage"] == "write-initial-record"
    assert _validate(again) == again


def test_more_than_128_pending_decision_events_use_existing_json_budget(
    sessions,
    tmp_path,
):
    session = sessions()
    session.create_copy(_parent=tmp_path)
    plan = session.prepare("before-check")
    for _ in range(130):
        session.decide("before-check", "pending", plan_id=plan.plan_id)
    record = session.result().to_dict()
    assert len(record["events"]) > 128
    assert _validate(record) == record
