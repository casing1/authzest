"""Temporary owned copies and SCRIPTED worker data, never policy observations.

No test launches, compiles or evaluates the new worker or either policy. Expected
booleans below belong to the mock transport, not operational acceptance evidence.
"""

import ast
import asyncio
import builtins
import copy
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical
from authzest.codex.owner_policy_file_repair import (
    prepare_owner_policy_file_repair,
    validate_owner_policy_file_repair,
)
from authzest.codex.owner_policy_repair_pair import build_owner_policy_repair_pair
from authzest.codex.owner_policy_repair_recommendation import (
    build_owner_policy_repair_recommendation_request,
    validate_owner_policy_repair_recommendation,
)
from authzest.runner import _owner_policy_file_transport as transport
from authzest.runner import _owner_policy_file_workspace as workspace
from authzest.runner import owner_policy_file_repair as session_module

pytestmark = pytest.mark.skipif(
    not workspace.supported(),
    reason="Owned policy file sessions require supported POSIX source mode",
)

# SCRIPTED mock responses only, never executed policy results.
MOCK_BEFORE = (True, True, False, False, False, False, False, True)
MOCK_AFTER = (True, False, False, False, False, False, False, False)
STAGES = ("before-check", "diff", "apply", "after-check", "restore")


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Session unit tests must not execute policies, workers, providers or processes")

    async def forbidden_worker(*args, **kwargs):
        forbidden()

    original_import = builtins.__import__
    original_compile = builtins.compile

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn", "openai", "httpx", "requests"}:
            forbidden()
        if name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    def guarded_compile(source, filename, mode, flags=0, *args, **kwargs):
        if (
            flags & ast.PyCF_ONLY_AST
            and sys._getframe(1).f_globals.get("__name__") == "ast"
            and sys._getframe(2).f_globals.get("__name__") in {"_pytest._code.source", "traceback"}
        ):
            return original_compile(source, filename, mode, flags, *args, **kwargs)
        forbidden()

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", guarded_compile)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(transport, "run_worker", forbidden_worker)
    monkeypatch.setattr(session_module, "_run_worker", forbidden_worker)


def _application(status="registered-change"):
    request = build_owner_policy_repair_recommendation_request()
    context = request.to_dict()
    data = {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted test data, not provider or maintainer evidence.",
        "evidence_ids": list(context["evidence_ids"].values()),
        "case_ids": [case["case_id"] for case in context["content"]["cases"]],
        "assumptions": ["Synthetic input context is trusted."],
        "uncertainties": ["No policy has been executed."],
        "expected_effects": ["Registered ownership check is expected to be restored."],
        "limitations": ["No endpoint authorization or authenticated approval."],
        "change_pair_id": context["registry"]["pair_id"] if status == "registered-change" else None,
    }
    recommendation = validate_owner_policy_repair_recommendation(canonical(data), request)
    return prepare_owner_policy_file_repair(request, recommendation)


@pytest.fixture
def sessions():
    opened = []

    def create(*, status="registered-change", clock=lambda: 100.0):
        session = session_module.OwnerPolicyRepairFileSession(_application(status), clock=clock)
        opened.append(session)
        return session

    yield create
    for session in opened:
        session.close()


def _mock_worker(monkeypatch, *, fail_stage=None, mutate=None, **diagnostics):
    calls = []

    async def scripted(worker_input, *, before_launch=None):
        if before_launch is not None:
            before_launch()
        calls.append(copy.deepcopy(worker_input))
        output = copy.deepcopy(worker_input)
        output.pop("source_text")
        observations = MOCK_BEFORE if worker_input["candidate"] == "before" else MOCK_AFTER
        output["cases"] = [
            {"case_id": row["case_id"], "input_sha256": row["input_sha256"], "observed": observed}
            for row, observed in zip(worker_input["cases"], observations, strict=True)
        ]
        if mutate is not None:
            mutate(worker_input, output)
        failure = diagnostics if worker_input["stage"] == fail_stage else {}
        return transport.WorkerTransport(
            **{
                "output": canonical(output).encode("utf-8"),
                "exit_code": 0,
                "reason": None,
                "child_cleanup_status": "confirmed",
                "workspace_cleanup_status": "confirmed",
                "launch_status": "started",
                **failure,
            }
        )

    monkeypatch.setattr(session_module, "_run_worker", scripted)
    return calls


def _choose(session, stage, choice="approved", **kwargs):
    plan = session.prepare(stage)
    session.decide(stage, choice, plan_id=plan.plan_id, **kwargs)
    return plan


def _act(session, stage):
    if stage.endswith("-check"):
        return asyncio.run(session.run_check(stage))
    return {"diff": session.accept_diff, "apply": session.apply, "restore": session.restore}[
        stage
    ]()


def _create_copy(session, tmp_path):
    result = session.create_copy(_parent=tmp_path).to_dict()
    assert result["phase"] == "ready-before"
    policy = Path(result["workspace"]) / "policy.py"
    assert policy.parent.parent == tmp_path
    assert (
        policy.read_text()
        == build_owner_policy_repair_pair().to_dict()["content"]["before"]["text"]
    )
    return policy


def _reach(session, tmp_path, stage):
    policy = _create_copy(session, tmp_path)
    for preceding in STAGES[: STAGES.index(stage)]:
        _choose(session, preceding)
        _act(session, preceding)
    return policy


def test_constructor_does_not_create_copy_and_close_does_not_delete_it(sessions, tmp_path):
    session = sessions()
    initial = session.result().to_dict()
    assert initial["phase"] == "not-created"
    assert initial["workspace"] is None
    assert initial["checks"] == {"before": None, "after": None}
    assert list(tmp_path.iterdir()) == []
    policy = _create_copy(session, tmp_path)
    before = policy.read_bytes()
    session.close()
    assert session.result().to_dict()["closed"] is True
    assert policy.read_bytes() == before
    assert {"policy.py", "before.txt", "after.txt", "record.json"} <= {
        child.name for child in policy.parent.iterdir()
    }
    with pytest.raises(ContractError):
        session.prepare("before-check")


def test_whole_workflow_uses_separate_decisions_and_captured_bytes(sessions, tmp_path, monkeypatch):
    calls = _mock_worker(monkeypatch)
    session = sessions()
    policy = _create_copy(session, tmp_path)
    content = build_owner_policy_repair_pair().to_dict()["content"]
    before_inode = policy.stat().st_ino
    plans = []
    for stage in STAGES:
        plans.append(_choose(session, stage))
        _act(session, stage)
        data = session.result().to_dict()
        if stage == "before-check":
            assert data["checks"]["before"]["execution_status"] == "completed"
            assert data["checks"]["before"]["comparison_status"] == "failed"
            assert data["application_status"] == "not-run"
            assert policy.read_text() == content["before"]["text"]
        elif stage == "diff":
            assert data["diff_status"] == "accepted"
            assert data["phase"] == "ready-before"
            assert policy.read_text() == content["before"]["text"]
        elif stage == "apply":
            assert data["phase"] == "applied-after"
            assert data["application_status"] == "completed"
            assert data["checks"]["after"] is None
            assert policy.read_text() == content["after"]["text"]
            assert policy.stat().st_ino != before_inode
        elif stage == "after-check":
            assert data["checks"]["after"]["execution_status"] == "completed"
            assert data["checks"]["after"]["comparison_status"] == "passed"
            assert data["restoration_status"] == "not-run"
    final = session.result().to_dict()
    assert final["phase"] == "restored-before"
    assert final["restoration_status"] == "completed"
    assert final["evidence_status"] == "confirmed"
    assert final["authorization_status"] == "unknown"
    assert final["provider_calls"] == 0
    assert policy.read_text() == content["before"]["text"]
    assert len({plan.plan_id for plan in plans}) == 5
    assert [item["candidate"] for item in calls] == ["before", "after"]
    assert [item["source_text"] for item in calls] == [
        content["before"]["text"],
        content["after"]["text"],
    ]
    for item in calls:
        assert all("expected" not in case for case in item["cases"])
        assert "path" not in item and "workspace" not in item


@pytest.mark.parametrize("status", ["no-change", "unknown"])
def test_no_change_and_unknown_do_not_create_copies(sessions, tmp_path, status):
    session = sessions(status=status)
    session.create_copy(_parent=tmp_path)
    assert session.result().to_dict()["phase"] == "not-created"
    assert session.result().to_dict()["workspace"] is None
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ContractError):
        session.prepare("before-check")


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("choice", ["declined", "cancelled"])
def test_refusal_is_terminal_and_does_not_perform_stage(
    sessions, tmp_path, monkeypatch, stage, choice
):
    calls = _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, stage)
    before = policy.read_bytes()
    count = len(calls)
    plan = _choose(session, stage, choice)
    _act(session, stage)
    assert policy.read_bytes() == before
    assert len(calls) == count
    with pytest.raises(ContractError):
        session.decide(stage, "approved", plan_id=plan.plan_id)


def test_diff_and_application_require_completed_baseline(sessions, tmp_path):
    session = sessions()
    _create_copy(session, tmp_path)
    for stage in ("diff", "apply", "after-check", "restore"):
        with pytest.raises(ContractError):
            session.prepare(stage)


def test_expired_before_check_does_not_call_worker_and_cannot_be_reapproved(
    sessions, tmp_path, monkeypatch
):
    calls = _mock_worker(monkeypatch)
    now = [100.0]
    session = sessions(clock=lambda: now[0])
    _create_copy(session, tmp_path)
    plan = _choose(session, "before-check", lifetime_seconds=1)
    now[0] = 101.0
    asyncio.run(session.run_check("before-check"))
    assert calls == []
    assert session.result().to_dict()["checks"]["before"]["execution_status"] != "completed"
    with pytest.raises(ContractError):
        session.decide("before-check", "approved", plan_id=plan.plan_id)


def test_wrong_stage_and_other_session_plans_cannot_authorize(sessions, tmp_path):
    first, second = sessions(), sessions()
    _create_copy(first, tmp_path)
    _create_copy(second, tmp_path)
    first_plan = first.prepare("before-check")
    second_plan = second.prepare("before-check")
    assert first_plan.plan_id != second_plan.plan_id
    with pytest.raises(ContractError):
        first.decide("apply", "approved", plan_id=first_plan.plan_id)
    with pytest.raises(ContractError):
        second.decide("before-check", "approved", plan_id=first_plan.plan_id)


def test_worker_attempt_is_consumed_before_await_and_cannot_replay(sessions, tmp_path, monkeypatch):
    session = sessions()
    _create_copy(session, tmp_path)
    plan = _choose(session, "before-check")

    def assert_consumed(_worker_input, _output):
        assert "before-check" in session.result().to_dict()["attempts_consumed"]

    calls = _mock_worker(monkeypatch, mutate=assert_consumed)
    asyncio.run(session.run_check("before-check"))
    original_check = session.result().to_dict()["checks"]["before"]
    asyncio.run(session.run_check("before-check"))
    assert len(calls) == 1
    assert session.result().to_dict()["checks"]["before"] == original_check
    with pytest.raises(ContractError):
        session.decide("before-check", "approved", plan_id=plan.plan_id)


def test_user_edit_after_apply_approval_is_preserved_without_write(sessions, tmp_path, monkeypatch):
    _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "apply")
    _choose(session, "apply")
    edited = policy.read_text() + "# Operator edit; not executable test input.\n"
    policy.write_text(edited)
    session.apply()
    assert policy.read_text() == edited
    assert session.result().to_dict()["application_status"] != "completed"
    with pytest.raises(ContractError):
        session.prepare("apply")


def test_mid_worker_file_edit_discards_mock_observations(sessions, tmp_path, monkeypatch):
    session = sessions()
    policy = _create_copy(session, tmp_path)
    edited = policy.read_text() + "# Operator edit while scripted worker is pending.\n"

    def mutate(_worker_input, _output):
        policy.write_text(edited)

    calls = _mock_worker(monkeypatch, mutate=mutate)
    _choose(session, "before-check")
    asyncio.run(session.run_check("before-check"))
    data = session.result().to_dict()
    assert len(calls) == 1
    assert data["checks"]["before"]["observations"] is None
    assert data["comparison_status"] in {"not-evaluated", "inconclusive"}
    assert policy.read_text() == edited
    with pytest.raises(ContractError):
        session.prepare("diff")


def test_user_edit_after_apply_prevents_fresh_restore_and_preserves_edit(
    sessions, tmp_path, monkeypatch
):
    _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "restore")
    edited = policy.read_text() + "# Operator change after the scripted successful check.\n"
    policy.write_text(edited)
    with pytest.raises(ContractError):
        session.prepare("restore")
    session.restore()
    result = session.result().to_dict()
    assert result["restoration_status"] != "completed"
    assert result["file_binding_status"] == "unconfirmed"
    assert policy.read_text() == edited


@pytest.mark.parametrize("reason", ["declined", "transport-failure", "malformed-output"])
def test_after_check_refusal_or_failure_still_allows_safe_fresh_restore(
    sessions, tmp_path, monkeypatch, reason
):
    calls = _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "after-check")
    if reason == "transport-failure":
        calls = _mock_worker(
            monkeypatch, fail_stage="after-check", output=b"", reason="timeout", exit_code=-9
        )
    elif reason == "malformed-output":
        calls = _mock_worker(monkeypatch, fail_stage="after-check", output=b"not JSON")
    _choose(session, "after-check", "declined" if reason == "declined" else "approved")
    count = len(calls)
    asyncio.run(session.run_check("after-check"))
    failed = session.result().to_dict()
    assert failed["application_status"] == "completed"
    assert failed["evidence_status"] == "confirmed"
    assert failed["checks"]["after"]["observations"] is None
    assert failed["comparison_status"] in {"not-evaluated", "inconclusive"}
    assert len(calls) == count + (reason != "declined")
    _choose(session, "restore")
    session.restore()
    final = session.result().to_dict()
    assert final["phase"] == "restored-before"
    assert final["restoration_status"] == "completed"
    assert (
        policy.read_text()
        == build_owner_policy_repair_pair().to_dict()["content"]["before"]["text"]
    )


def test_other_check_cannot_release_an_active_check_or_allow_close(sessions, tmp_path, monkeypatch):
    _mock_worker(monkeypatch)
    scripted = session_module._run_worker
    session = sessions()
    _create_copy(session, tmp_path)
    _choose(session, "before-check")

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def blocked(wire, **kwargs):
            entered.set()
            await release.wait()
            return await scripted(wire, **kwargs)

        monkeypatch.setattr(session_module, "_run_worker", blocked)
        task = asyncio.create_task(session.run_check("before-check"))
        await entered.wait()
        other = await session.run_check("after-check")
        assert other.to_dict()["failure"] == "operation-in-progress"
        with pytest.raises(ContractError):
            session.close()
        release.set()
        await task

    asyncio.run(scenario())
    assert session.result().to_dict()["checks"]["before"]["execution_status"] == "completed"


@pytest.mark.parametrize("pause", ["before-launch-guard", "after-launch-guard"])
def test_concurrent_evidence_failure_blocks_launch_or_discards_pending_response(
    sessions, tmp_path, monkeypatch, pause
):
    calls = _mock_worker(monkeypatch)
    scripted = session_module._run_worker
    session = sessions()
    policy = _reach(session, tmp_path, "after-check")
    _choose(session, "after-check")
    initial_calls = len(calls)
    applied_bytes = policy.read_bytes()

    def fail_record(*args):
        raise OSError("Scripted persistence failure during an active check")

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def paused(wire, *, before_launch):
            if pause == "before-launch-guard":
                entered.set()
                await release.wait()
                try:
                    before_launch()
                except ContractError:
                    # Mirror the real transport's known prelaunch refusal without
                    # invoking any process, worker or policy in this unit test.
                    return transport.WorkerTransport(
                        b"",
                        None,
                        "worker-process-error",
                        "not-needed",
                        "confirmed",
                        "not-attempted",
                    )
                return await scripted(wire)
            before_launch()
            response = await scripted(wire)
            entered.set()
            await release.wait()
            return response

        monkeypatch.setattr(session_module, "_run_worker", paused)
        task = asyncio.create_task(session.run_check("after-check"))
        await asyncio.wait_for(entered.wait(), timeout=5)
        try:
            monkeypatch.setattr(session._workspace, "write_record", fail_record)
            busy = session.restore().to_dict()
            assert busy["evidence_status"] == "unconfirmed"
            assert busy["failure"] == "evidence-unconfirmed"
            assert busy["restoration_status"] == "not-run"
        finally:
            release.set()
        return (await asyncio.wait_for(task, timeout=5)).to_dict()

    result = asyncio.run(scenario())
    assert len(calls) == initial_calls + (pause == "after-launch-guard")
    after = result["checks"]["after"]
    assert after["observations"] is None
    assert after["comparison_status"] == "not-evaluated"
    assert after["execution_status"] != "completed"
    assert after["reason"] == "evidence-unconfirmed"
    assert result["comparison_status"] == "inconclusive"
    assert result["evidence_status"] == "unconfirmed"
    assert result["application_status"] == "completed"
    assert policy.read_bytes() == applied_bytes
    if pause == "before-launch-guard":
        assert after["transport"]["launch_status"] == "not-attempted"
        assert after["transport"]["child_cleanup_status"] == "not-needed"
        assert after["transport"]["workspace_cleanup_status"] == "confirmed"
    else:
        assert after["transport"]["launch_status"] == "started"
    with pytest.raises(ContractError):
        session.prepare("restore")


def test_unexpected_transport_exception_retains_uncertain_launch_status(
    sessions, tmp_path, monkeypatch
):
    session = sessions()
    _create_copy(session, tmp_path)
    _choose(session, "before-check")

    async def broken(*args, **kwargs):
        raise RuntimeError("private exception must not appear in results")

    monkeypatch.setattr(session_module, "_run_worker", broken)
    data = asyncio.run(session.run_check("before-check")).to_dict()
    check = data["checks"]["before"]
    assert check["execution_status"] == "failed"
    assert check["observations"] is None
    assert check["transport"]["launch_status"] == "ambiguous"
    assert check["transport"]["child_cleanup_status"] == "unconfirmed"
    assert "private exception" not in canonical(data)


def test_cancellation_retains_checkpoint_and_reraises_original(sessions, tmp_path, monkeypatch):
    session = sessions()
    _create_copy(session, tmp_path)
    _choose(session, "before-check")
    original = asyncio.CancelledError()

    async def cancelled(*args, **kwargs):
        raise original

    monkeypatch.setattr(session_module, "_run_worker", cancelled)
    with pytest.raises(asyncio.CancelledError) as captured:
        asyncio.run(session.run_check("before-check"))
    assert captured.value is original
    data = original.file_repair_result.to_dict()
    assert data["checks"]["before"]["execution_status"] == "cancelled"
    assert data["checks"]["before"]["transport"]["launch_status"] == "ambiguous"
    assert data["checks"]["before"]["observations"] is None


def test_apply_journal_failure_reports_actual_effect_and_blocks_restore(
    sessions, tmp_path, monkeypatch
):
    _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "apply")
    _choose(session, "apply")

    def fail_record(*args):
        raise OSError("private journal details")

    monkeypatch.setattr(session._workspace, "write_record", fail_record)
    data = session.apply().to_dict()
    assert data["application_status"] == "completed"
    assert data["evidence_status"] == "unconfirmed"
    assert data["failure"] == "evidence-unconfirmed"
    expected = build_owner_policy_repair_pair().to_dict()["content"]["after"]["text"]
    assert policy.read_text() == expected
    with pytest.raises(ContractError):
        session.prepare("restore")
    assert session.restore().to_dict()["restoration_status"] != "completed"
    assert policy.read_text() == expected


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_interrupted_committed_apply_preserves_original_exception_and_uncertainty(
    sessions, tmp_path, monkeypatch, error
):
    _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "apply")
    _choose(session, "apply")
    replace = session._workspace.replace_policy
    original = error()

    def interrupted(*args, **kwargs):
        replace(*args, **kwargs)
        raise original

    monkeypatch.setattr(session._workspace, "replace_policy", interrupted)
    with pytest.raises(error) as captured:
        session.apply()
    assert captured.value is original
    data = original.file_repair_result.to_dict()
    assert data["application_status"] == "state-unconfirmed"
    assert data["phase"] == "unconfirmed"
    assert data["file_binding_status"] == "unconfirmed"
    assert (
        policy.read_text() == build_owner_policy_repair_pair().to_dict()["content"]["after"]["text"]
    )
    with pytest.raises(ContractError):
        session.prepare("restore")


def test_committed_write_failure_is_not_reported_as_unchanged(sessions, tmp_path, monkeypatch):
    _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "apply")
    _choose(session, "apply")
    replace = session._workspace.replace_policy

    def unconfirmed(*args, **kwargs):
        replace(*args, **kwargs)
        raise workspace.CommittedWriteError("The write committed but confirmation failed")

    monkeypatch.setattr(session._workspace, "replace_policy", unconfirmed)
    data = session.apply().to_dict()
    assert data["application_status"] == "state-unconfirmed"
    assert data["restoration_status"] == "not-run"
    assert data["phase"] == "unconfirmed"
    assert (
        policy.read_text() == build_owner_policy_repair_pair().to_dict()["content"]["after"]["text"]
    )


def test_midstage_edit_is_reported_as_unconfirmed_and_retained(sessions, tmp_path, monkeypatch):
    _mock_worker(monkeypatch)
    session = sessions()
    policy = _reach(session, tmp_path, "apply")
    _choose(session, "apply")
    stage = session._workspace._stage
    edited = b"# Operator edit during staging.\n"

    def mutate(raw):
        name = stage(raw)
        policy.write_bytes(edited)
        return name

    monkeypatch.setattr(session._workspace, "_stage", mutate)
    data = session.apply().to_dict()
    assert data["file_binding_status"] == "unconfirmed"
    assert data["application_status"] == "failed"
    assert policy.read_bytes() == edited


def test_initialization_failure_preserves_confirmed_created_path(sessions, tmp_path, monkeypatch):
    retained = tmp_path / "retained-incomplete-copy"
    retained.mkdir()

    def fail(*args, **kwargs):
        raise workspace.WorkspaceInitializationError(retained, "create-policy")

    monkeypatch.setattr(session_module, "PolicyFileWorkspace", fail)
    data = sessions().create_copy(_parent=tmp_path).to_dict()
    assert data["workspace"] == str(retained)
    assert data["phase"] == "unconfirmed"
    assert data["failure"] == "initialization-failed"
    assert data["initialization_stage"] == "create-policy"
    assert retained.exists()


@pytest.mark.parametrize("clock", [lambda: -1, lambda: True, lambda: float("nan")])
def test_invalid_decision_clock_is_rejected_before_copy_creation(clock, tmp_path):
    with pytest.raises(ContractError):
        session_module.OwnerPolicyRepairFileSession(_application(), clock=clock)
    assert list(tmp_path.iterdir()) == []


def test_pure_valid_large_application_is_rejected_before_live_copy_creation(tmp_path):
    request = build_owner_policy_repair_recommendation_request()
    data = _application().to_dict()["recommendation"]
    data["rationale"] = "r" * 4096
    data["limitations"] = ["l" * 4096] * 8
    recommendation = validate_owner_policy_repair_recommendation(canonical(data), request)
    application = prepare_owner_policy_file_repair(request, recommendation)
    assert session_module.MAX_APPLICATION_BYTES == 32_768
    assert (
        session_module.MAX_APPLICATION_BYTES
        < len(application.payload_json.encode("utf-8"))
        <= MAX_JSON_BYTES
    )
    assert validate_owner_policy_file_repair(application.payload_json) == application
    with pytest.raises(ContractError):
        session_module.OwnerPolicyRepairFileSession(application)
    assert list(tmp_path.iterdir()) == []


def test_pending_event_budget_terminates_with_valid_checkpoint_and_no_worker(
    sessions, tmp_path, monkeypatch
):
    calls = _mock_worker(monkeypatch)
    session = sessions()
    _create_copy(session, tmp_path)
    plan = session.prepare("before-check")
    assert session_module.MAX_EVENTS == 256
    remaining = session_module.MAX_EVENTS - len(session.result().to_dict()["events"])
    for _ in range(remaining):
        session.decide("before-check", "pending", plan_id=plan.plan_id)
        snapshot = session.result()
        assert session_module.validate_owner_policy_file_result(snapshot.payload_json) == snapshot
        assert len(snapshot.to_dict()["events"]) <= session_module.MAX_EVENTS
    with pytest.raises(ContractError):
        session.decide("before-check", "pending", plan_id=plan.plan_id)
    exhausted = session.result()
    assert exhausted.to_dict()["evidence_status"] == "unconfirmed"
    assert exhausted.to_dict()["failure"] == "evidence-unconfirmed"
    assert len(exhausted.to_dict()["events"]) == session_module.MAX_EVENTS
    assert session_module.validate_owner_policy_file_result(exhausted.payload_json) == exhausted
    with pytest.raises(ContractError):
        session.decide("before-check", "approved", plan_id=plan.plan_id)
    stopped = asyncio.run(session.run_check("before-check"))
    assert calls == []
    assert stopped.to_dict()["checks"]["before"]["observations"] is None
    assert session_module.validate_owner_policy_file_result(stopped.payload_json) == stopped


def test_record_serialization_failure_blocks_effects_and_preserves_valid_result(
    sessions, tmp_path, monkeypatch
):
    calls = _mock_worker(monkeypatch)
    session = sessions()
    policy = _create_copy(session, tmp_path)
    plan = session.prepare("before-check")
    old_record = (policy.parent / "record.json").read_bytes()
    result = session.result
    serializations = []

    def fail_once():
        serializations.append(True)
        if len(serializations) == 1:
            raise ContractError("Scripted complete-record serialization limit")
        return result()

    monkeypatch.setattr(session, "result", fail_once)
    with pytest.raises(ContractError):
        session.decide("before-check", "approved", plan_id=plan.plan_id)
    failed = session.result()
    assert failed.to_dict()["evidence_status"] == "unconfirmed"
    assert failed.to_dict()["failure"] == "evidence-unconfirmed"
    assert (policy.parent / "record.json").read_bytes() == old_record
    assert session_module.validate_owner_policy_file_result(failed.payload_json) == failed
    stopped = asyncio.run(session.run_check("before-check"))
    assert calls == []
    assert stopped.to_dict()["checks"]["before"]["observations"] is None
    assert session_module.validate_owner_policy_file_result(stopped.payload_json) == stopped


def test_unrepresentable_expiry_does_not_store_invalid_decision(sessions, tmp_path):
    session = sessions(clock=lambda: 1e308)
    _create_copy(session, tmp_path)
    initial = session.result()
    assert session_module.validate_owner_policy_file_result(initial.payload_json) == initial
    with pytest.raises(ContractError):
        session.prepare("before-check")
    unchanged = session.result()
    assert unchanged == initial
    assert unchanged.to_dict()["decisions"] == {}
    assert unchanged.to_dict()["evidence_status"] == "confirmed"
    assert session_module.validate_owner_policy_file_result(unchanged.payload_json) == unchanged


def test_near_live_application_limit_retains_both_check_plans_within_result_budget(
    tmp_path, monkeypatch
):
    request = build_owner_policy_repair_recommendation_request()
    data = _application().to_dict()["recommendation"]
    data["rationale"] = "r"
    data["limitations"] = ["l"] * 8

    def prepare():
        recommendation = validate_owner_policy_repair_recommendation(canonical(data), request)
        return prepare_owner_policy_file_repair(request, recommendation)

    target = session_module.MAX_APPLICATION_BYTES - 1
    remaining = target - len(prepare().payload_json.encode("utf-8"))
    assert 0 < remaining <= 9 * 4095
    extra = min(remaining, 4095)
    data["rationale"] += "r" * extra
    remaining -= extra
    for index in range(8):
        extra = min(remaining, 4095)
        data["limitations"][index] += "l" * extra
        remaining -= extra
    assert remaining == 0
    application = prepare()
    assert len(application.payload_json.encode("utf-8")) == target

    calls = _mock_worker(monkeypatch)
    session = session_module.OwnerPolicyRepairFileSession(application)
    try:
        policy = _reach(session, tmp_path, "restore")
        _choose(session, "restore")
        snapshot = session.restore()
        result = snapshot.to_dict()
        assert result["phase"] == "restored-before"
        assert result["application_status"] == result["restoration_status"] == "completed"
        assert result["comparison_status"] == "passed"
        assert result["evidence_status"] == "confirmed"
        assert [item["candidate"] for item in calls] == ["before", "after"]
        assert result["checks"]["before"]["plan"]["application"] == application.to_dict()
        assert result["checks"]["after"]["plan"]["application"] == application.to_dict()
        assert len(snapshot.payload_json.encode("utf-8")) <= MAX_JSON_BYTES
        pending = [result]
        nodes = 0
        while pending:
            value = pending.pop()
            nodes += 1
            if type(value) is dict:
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                pending.extend(value)
        assert nodes <= 8192
        assert session_module.validate_owner_policy_file_result(snapshot.payload_json) == snapshot
        assert policy.read_text() == request.to_dict()["content"]["before"]["text"]
    finally:
        session.close()


def test_clock_rounding_cannot_extend_plan_lifetime_beyond_300_seconds(sessions, tmp_path):
    now = 3e18
    assert now + session_module.MAX_DECISION_SECONDS - now > session_module.MAX_DECISION_SECONDS
    session = sessions(clock=lambda: now)
    _create_copy(session, tmp_path)
    initial = session.result()
    with pytest.raises(ContractError):
        session.prepare("before-check")
    unchanged = session.result()
    assert unchanged == initial
    assert unchanged.to_dict()["decisions"] == {}
    assert session_module.validate_owner_policy_file_result(unchanged.payload_json) == unchanged


def test_subresolution_decision_lifetime_does_not_mutate_pending_choice(sessions, tmp_path):
    session = sessions(clock=lambda: 100.0)
    _create_copy(session, tmp_path)
    plan = session.prepare("before-check")
    initial = session.result()
    assert 100.0 + 1e-20 == 100.0
    with pytest.raises(ContractError):
        session.decide("before-check", "approved", plan_id=plan.plan_id, lifetime_seconds=1e-20)
    unchanged = session.result()
    assert unchanged == initial
    assert unchanged.to_dict()["decisions"]["before-check"]["choice"] == "pending"
    assert session_module.validate_owner_policy_file_result(unchanged.payload_json) == unchanged


def test_event_limit_reached_during_launch_wait_blocks_child(sessions, tmp_path, monkeypatch):
    calls = _mock_worker(monkeypatch)
    scripted = session_module._run_worker
    session = sessions()
    policy = _create_copy(session, tmp_path)
    plan = session.prepare("before-check")
    remaining = session_module.MAX_EVENTS - 2 - len(session.result().to_dict()["events"])
    for _ in range(remaining):
        session.decide("before-check", "pending", plan_id=plan.plan_id)
    session.decide("before-check", "approved", plan_id=plan.plan_id)
    assert len(session.result().to_dict()["events"]) == session_module.MAX_EVENTS - 1
    original_bytes = policy.read_bytes()

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def paused(wire, *, before_launch):
            entered.set()
            await release.wait()
            try:
                before_launch()
            except ContractError:
                return transport.WorkerTransport(
                    b"", None, "worker-process-error", "not-needed", "confirmed", "not-attempted"
                )
            return await scripted(wire)

        monkeypatch.setattr(session_module, "_run_worker", paused)
        task = asyncio.create_task(session.run_check("before-check"))
        await asyncio.wait_for(entered.wait(), timeout=5)
        try:
            busy = session.apply().to_dict()
            assert busy["failure"] == "operation-in-progress"
            assert len(busy["events"]) == session_module.MAX_EVENTS
            assert busy["application_status"] == "not-run"
            assert calls == []
        finally:
            release.set()
        return await asyncio.wait_for(task, timeout=5)

    snapshot = asyncio.run(scenario())
    result = snapshot.to_dict()
    assert calls == []
    assert result["evidence_status"] == "unconfirmed"
    assert result["failure"] == "evidence-unconfirmed"
    assert len(result["events"]) == session_module.MAX_EVENTS
    assert result["checks"]["before"]["observations"] is None
    assert result["checks"]["before"]["transport"]["launch_status"] == "not-attempted"
    assert result["checks"]["before"]["transport"]["workspace_cleanup_status"] == "confirmed"
    assert policy.read_bytes() == original_bytes
    assert session_module.validate_owner_policy_file_result(snapshot.payload_json) == snapshot
