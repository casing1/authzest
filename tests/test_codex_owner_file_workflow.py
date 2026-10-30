"""Offline CLI coordinator tests: fake recommendation and SCRIPTED observations.

Only temporary owned-copy I/O is real. No provider, worker, policy compilation,
policy execution, external process or network operation is allowed by these tests.
"""

import ast
import asyncio
import builtins
import copy
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import canonical
from authzest.codex.owner_policy_repair_pair import build_owner_policy_repair_pair
from authzest.codex.owner_policy_repair_transport import (
    OwnerPolicyRepairTransportResult,
    prepare_owner_policy_repair_transport_result,
)
from authzest.runner import _owner_policy_file_transport as transport
from authzest.runner import _owner_policy_file_workspace as workspace
from authzest.runner import codex_owner_file_workflow as workflow
from authzest.runner import codex_owner_repair as recommendation_workflow
from authzest.runner import owner_policy_file_repair as session_module

MODEL = "offline-owner-file-model"
STAGES = ("before-check", "diff", "apply", "after-check", "restore")
# Authored mock data, never observations from executed policies.
MOCK_BEFORE = [True, True, False, False, False, False, False, True]
MOCK_AFTER = [True, False, False, False, False, False, False, False]


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline coordinator tests must not execute policies, providers or children")

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

    connect = socket.socket.connect
    policy = asyncio.get_event_loop_policy()
    new_loop = policy.new_event_loop

    def initialize_loop():
        # Windows event-loop setup may use connect solely for private socketpair IPC.
        with monkeypatch.context() as initialization:
            initialization.setattr(socket.socket, "connect", connect)
            return new_loop()

    monkeypatch.setattr(policy, "new_event_loop", initialize_loop)
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
    monkeypatch.setattr(recommendation_workflow, "_default_adapter_factory", forbidden)


def fake_result(request, status="registered-change"):
    inner = request.to_dict()["request"]
    raw = {
        "schema_version": "1.0",
        "request_id": request.to_dict()["request_id"],
        "status": status,
        "rationale": "Caller-authored mock recommendation, not actual model evidence.",
        "evidence_ids": list(inner["evidence_ids"].values()),
        "case_ids": [case["case_id"] for case in inner["content"]["cases"]],
        "assumptions": ["Synthetic context is trusted."],
        "uncertainties": ["No policy has been executed by this test."],
        "expected_effects": ["Only the registered predicate can be selected."],
        "limitations": ["No endpoint enforcement claim or authenticated attestation."],
        "change_pair_id": inner["registry"]["pair_id"] if status == "registered-change" else None,
    }
    return prepare_owner_policy_repair_transport_result(
        canonical(raw), request, usage={"input_tokens": 11, "output_tokens": 22}
    )


@pytest.fixture
def harness(monkeypatch, tmp_path):
    if not workspace.supported():
        pytest.skip("Owned file effects require supported POSIX non-frozen source mode")
    state = SimpleNamespace(
        emitted=[],
        prompts=[],
        sessions=[],
        adapter_calls=[],
        worker_calls=[],
        choices={},
        clock=100.0,
        status="registered-change",
        read_hook=None,
        emit_hook=None,
        worker_hook=None,
        adapter_hook=None,
    )
    monkeypatch.setattr(workflow, "monotonic", lambda: state.clock)
    original_session = session_module.OwnerPolicyRepairFileSession

    def factory(application, *, clock):
        session = original_session(application, clock=clock)
        create_copy = session.create_copy
        monkeypatch.setattr(session, "create_copy", lambda: create_copy(_parent=tmp_path))
        state.sessions.append(session)
        return session

    monkeypatch.setattr(workflow, "OwnerPolicyRepairFileSession", factory)

    class Adapter:
        warnings_seen = 1
        retry_notifications_seen = 0

        def __init__(self, **kwargs):
            state.adapter_calls.append(kwargs)

        async def recommend_owner_policy_repair(self, request):
            if state.adapter_hook:
                return state.adapter_hook(request)
            return fake_result(request, state.status)

    async def scripted_worker(wire, *, before_launch=None):
        before_launch()
        state.worker_calls.append(copy.deepcopy(wire))
        output = copy.deepcopy(wire)
        output.pop("source_text")
        observations = MOCK_BEFORE if wire["candidate"] == "before" else MOCK_AFTER
        output["cases"] = [
            {"case_id": case["case_id"], "input_sha256": case["input_sha256"], "observed": value}
            for case, value in zip(wire["cases"], observations, strict=True)
        ]
        response = {
            "output": canonical(output).encode(),
            "exit_code": 0,
            "reason": None,
            "child_cleanup_status": "confirmed",
            "workspace_cleanup_status": "confirmed",
            "launch_status": "started",
        }
        if state.worker_hook:
            state.worker_hook(wire, output, response)
        return transport.WorkerTransport(**response)

    monkeypatch.setattr(session_module, "_run_worker", scripted_worker)

    def read(prompt):
        phrase = prompt.split("'")[1]
        words = phrase.split()
        stage = words[1] if words[0] == "approve" else words[0]
        state.prompts.append(stage)
        if state.read_hook:
            state.read_hook(stage, phrase)
        return state.choices.get(stage, phrase)

    def emit(text):
        data = json.loads(text)
        state.emitted.append(data)
        if state.emit_hook:
            state.emit_hook(data)

    def run(**kwargs):
        return asyncio.run(
            workflow.run_codex_owner_file_workflow(
                MODEL, read=read, emit=emit, adapter_factory=Adapter, **kwargs
            )
        )

    state.run = run
    state.parent = tmp_path
    state.policy = lambda: Path(state.sessions[-1].result().to_dict()["workspace"]) / "policy.py"
    return state


def checkpoint(result):
    return result["file_workflow"]["session_result"]


def test_whole_flow_has_seven_exact_independent_choices_and_closed_checkpoint(harness):
    result = harness.run()
    data = checkpoint(result)
    assert harness.prompts == ["share", "copy", *STAGES]
    assert len(harness.adapter_calls) == 1
    assert [wire["stage"] for wire in harness.worker_calls] == ["before-check", "after-check"]
    assert result["kind"] == "codex-owner-file-workflow"
    assert result["status"] == "completed" and result["exit_code"] == 0
    assert result["execution_status"] == "completed"
    assert result["patch_application"] == result["restoration_status"] == "completed"
    assert result["observations"] == {"before": MOCK_BEFORE, "after": MOCK_AFTER}
    assert result["comparison_status"] == "passed"
    assert data["checks"]["before"]["comparison_status"] == "failed"
    assert data["checks"]["before"]["execution_status"] == "completed"
    assert data["phase"] == "restored-before" and data["closed"] is True
    assert data["generation"] == 3
    assert data["attempts_consumed"] == sorted(STAGES)
    assert data["provider_calls"] == 0
    assert result["application_turn_attempts"] == 1
    assert result["usage"] == {"input_tokens": 11, "output_tokens": 22}
    assert result["returned_identity"]["model"] == MODEL
    assert result["provider_warning_count"] == 1
    assert result["provider_retry_notification_count"] == 0
    assert result["latency_ms"] >= 0
    assert result["authorization_status"] == "unknown"
    assert result["original_checkout_modified"] is False
    assert data["restart_supported"] is False
    assert harness.policy().parent.parent == harness.parent
    pair = build_owner_policy_repair_pair().to_dict()["content"]
    assert harness.policy().read_text() == pair["before"]["text"]
    disk = json.loads((harness.policy().parent / "record.json").read_text())
    assert disk["closed"] is False and disk["phase"] == "restored-before"
    assert {
        name
        for name in ("before.txt", "after.txt", "record.json")
        if (harness.policy().parent / name).is_file()
    } == {"before.txt", "after.txt", "record.json"}


def test_full_copy_and_stage_previews_precede_each_prompt(harness):
    def check_preview(stage, phrase):
        event = harness.emitted[-1]
        if stage == "share":
            assert event["kind"] == "codex-owner-repair-sharing-preview"
        elif stage == "copy":
            assert event["kind"] == "owner-policy-file-copy-preview"
            confirmation = event["copy_confirmation"]
            assert confirmation["confirmation_phrase"] == phrase
            assert confirmation["created_at"] == 100
            assert confirmation["expires_at"] == 400
            assert confirmation["reviewer_authenticated"] is False
            assert event["application"]["request"]["content"]["before"]["text"]
            assert list(harness.parent.iterdir()) == []
        else:
            assert event["kind"] == "owner-policy-file-stage-preview"
            assert event["stage"] == stage
            assert event["plan"]["application"]["pair_preview"]
            assert event["decision"]["choice"] == "pending"
            assert event["decision"]["plan_id"] == event["plan"]["plan_id"]
            assert event["decision"]["expires_at"] - event["decision"]["created_at"] <= 300
            if stage.endswith("check"):
                assert event["plan"]["recipe"]["worker_source"]
                assert event["plan"]["worker_input"]["source_text"]
                assert len(event["plan"]["worker_input"]["cases"]) == 8

    harness.read_hook = check_preview
    assert harness.run()["exit_code"] == 0


@pytest.mark.parametrize("candidate", ["before", "after"])
@pytest.mark.parametrize("status", ["no-change", "unknown"])
def test_normal_nonchange_outcomes_do_not_create_sessions_or_copies(harness, candidate, status):
    harness.status = status
    result = harness.run(candidate=candidate)
    assert result["status"] == status and result["exit_code"] == 0
    assert harness.prompts == ["share"]
    assert harness.sessions == harness.worker_calls == []
    assert list(harness.parent.iterdir()) == []
    assert checkpoint(result) is None


def test_after_candidate_cannot_select_registered_change(harness):
    result = harness.run(candidate="after")
    assert result["status"] == "recommendation-failed" and result["exit_code"] == 1
    assert not harness.sessions and not harness.worker_calls
    assert list(harness.parent.iterdir()) == []


@pytest.mark.parametrize("stage", ["share", "copy", *STAGES])
@pytest.mark.parametrize("answer", ["", "cancel", "approve stale-id"])
def test_every_gate_refuses_nonexact_input_without_approving_effect(harness, stage, answer):
    harness.choices[stage] = answer
    result = harness.run()
    assert result["exit_code"] == 0
    if stage in {"share", "copy"}:
        assert list(harness.parent.iterdir()) == []
        assert not harness.worker_calls
        assert len(harness.adapter_calls) == (stage == "copy")
    else:
        data = checkpoint(result)
        assert data["decisions"][stage]["choice"] == (
            "cancelled" if answer == "cancel" else "declined"
        )
        assert stage not in data["attempts_consumed"]
        assert data["closed"] is True
        if stage == "after-check":
            assert harness.prompts[-1] == "restore"
            assert data["restoration_status"] == "completed"
            assert data["checks"]["after"] is None
        elif stage == "restore":
            assert data["phase"] == "applied-after"
            assert data["restoration_status"] == "not-run"
        else:
            assert data["phase"] == "ready-before"
            assert data["application_status"] == "not-run"


@pytest.mark.parametrize("bad_time", [400.0, 99.0, float("nan"), float("inf")])
def test_copy_expiry_or_invalid_clock_never_creates_directory(harness, bad_time):
    def alter(stage, phrase):
        if stage == "copy":
            harness.clock = bad_time

    harness.read_hook = alter
    result = harness.run()
    assert result["exit_code"] == 1
    assert list(harness.parent.iterdir()) == []
    assert not harness.worker_calls
    assert checkpoint(result)["closed"] is True


@pytest.mark.parametrize("stage", STAGES)
def test_expired_stage_does_not_reopen_or_execute_and_after_check_can_restore(harness, stage):
    def expire(current, phrase):
        if current == stage:
            harness.clock += 300

    harness.read_hook = expire
    result = harness.run()
    data = checkpoint(result)
    assert result["exit_code"] == 1
    assert data["decisions"][stage]["choice"] == "pending"
    assert stage not in data["attempts_consumed"]
    assert harness.prompts.count(stage) == 1
    if stage == "after-check":
        assert data["restoration_status"] == "completed"
        assert len(harness.worker_calls) == 1


@pytest.mark.parametrize("stage", STAGES)
def test_user_edit_at_confirmation_is_preserved_and_blocks_further_effects(harness, stage):
    changed = "# User-owned edit must survive\n"

    def edit(current, phrase):
        if current == stage:
            harness.policy().write_text(changed)

    harness.read_hook = edit
    result = harness.run()
    assert result["exit_code"] == 1
    assert harness.policy().read_text() == changed
    assert checkpoint(result)["file_binding_status"] == "unconfirmed"
    assert checkpoint(result)["restoration_status"] != "completed"
    assert harness.prompts[-1] == stage


@pytest.mark.parametrize("stage", ["before-check", "after-check"])
def test_scripted_worker_failure_stops_or_offers_separate_restore(harness, stage):
    def fail(wire, output, response):
        if wire["stage"] == stage:
            response.update(output=b"", reason="timeout", exit_code=-9)

    harness.worker_hook = fail
    result = harness.run()
    data = checkpoint(result)
    assert result["exit_code"] == 1
    assert result["execution_status"] == "failed"
    assert result["file_workflow"]["failure"] == {"stage": stage, "code": "timeout"}
    assert data["checks"]["before" if stage == "before-check" else "after"]["observations"] is None
    if stage == "after-check":
        assert data["restoration_status"] == "completed"
        assert harness.prompts[-1] == "restore"
        assert data["failure"] is None  # Outer history still preserves the earlier failure.
    else:
        assert data["application_status"] == "not-run"


def test_after_mismatch_is_failed_comparison_not_infrastructure_failure(harness):
    def mismatch(wire, output, response):
        if wire["stage"] == "after-check":
            output["cases"][1]["observed"] = True
            response["output"] = canonical(output).encode()

    harness.worker_hook = mismatch
    result = harness.run()
    assert result["exit_code"] == 1 and result["execution_status"] == "completed"
    assert result["comparison_status"] == "failed"
    assert result["restoration_status"] == "completed"
    assert result["file_workflow"]["failure"]["code"] == "case-mismatch"


@pytest.mark.parametrize("stage", ["copy", "before-check", "after-check", "restore"])
@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_interrupted_input_stops_without_automatic_restore_and_retains_state(harness, stage, error):
    def interrupt(current, phrase):
        if current == stage:
            raise error("private terminal detail")

    harness.read_hook = interrupt
    result = harness.run()
    assert result["status"] == "cancelled" and result["exit_code"] == 130
    assert harness.prompts[-1] == stage
    assert checkpoint(result)["closed"] is True
    assert result["restoration_status"] == "not-run"
    assert "private terminal detail" not in canonical(result)
    if stage in {"after-check", "restore"}:
        assert result["patch_application"] == "completed"
        assert result["execution_status"] == "completed"


@pytest.mark.parametrize("stage", ["before-check", "after-check"])
def test_worker_cancellation_keeps_attached_ambiguous_transport_and_no_auto_restore(harness, stage):
    def cancel(wire, output, response):
        if wire["stage"] == stage:
            raise asyncio.CancelledError()

    harness.worker_hook = cancel
    result = harness.run()
    data = checkpoint(result)
    check = data["checks"]["before" if stage == "before-check" else "after"]
    assert result["exit_code"] == 130 and result["execution_status"] == "cancelled"
    assert check["observations"] is None
    assert check["transport"]["launch_status"] == "ambiguous"
    assert data["closed"] is True
    assert data["restoration_status"] == "not-run"
    assert "restore" not in harness.prompts


@pytest.mark.parametrize("stage", ["before-check", "after-check"])
@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_nonasync_worker_interruption_after_dispatch_has_unknown_execution(harness, stage, error):
    def interrupt(wire, output, response):
        if wire["stage"] == stage:
            raise error("private interruption detail")

    harness.worker_hook = interrupt
    result = harness.run()
    data = checkpoint(result)
    candidate = "before" if stage == "before-check" else "after"
    assert result["status"] == "cancelled" and result["exit_code"] == 130
    assert result["execution_status"] == "unknown"
    assert data["checks"][candidate] is None
    assert stage in data["attempts_consumed"]
    assert result["file_workflow"]["unconfirmed_check"] == {
        "stage": stage,
        "execution_status": "unknown",
        "reason": "no-accepted-checkpoint-after-dispatch",
    }
    assert data["closed"] is True
    assert result["restoration_status"] == "not-run"
    assert "restore" not in harness.prompts
    assert "private interruption detail" not in canonical(result)
    if stage == "after-check":
        assert result["patch_application"] == "completed"
        assert result["observations"]["before"] == MOCK_BEFORE
        assert data["file_binding_status"] == data["evidence_status"] == "confirmed"


def test_apply_journal_failure_preserves_actual_effect_and_blocks_restore(harness, monkeypatch):
    def arm(stage, phrase):
        if stage == "apply":
            session = harness.sessions[-1]
            original = session._workspace.replace_policy

            def replacement(*args, **kwargs):
                value = original(*args, **kwargs)

                def fail_record(*args):
                    raise OSError("private record detail")

                monkeypatch.setattr(session._workspace, "write_record", fail_record)
                return value

            monkeypatch.setattr(session._workspace, "replace_policy", replacement)

    harness.read_hook = arm
    result = harness.run()
    assert result["exit_code"] == 1
    assert result["patch_application"] == "completed"
    assert checkpoint(result)["evidence_status"] == "unconfirmed"
    assert result["restoration_status"] == "not-run"
    assert harness.prompts[-1] == "apply"
    assert (
        harness.policy().read_text()
        == build_owner_policy_repair_pair().to_dict()["content"]["after"]["text"]
    )


@pytest.mark.parametrize("error", [workspace.CommittedWriteError, KeyboardInterrupt, SystemExit])
def test_uncertain_committed_write_is_not_claimed_unmodified_or_restored(
    harness, monkeypatch, error
):
    def arm(stage, phrase):
        if stage == "apply":
            session = harness.sessions[-1]
            original = session._workspace.replace_policy

            def replacement(*args, **kwargs):
                original(*args, **kwargs)
                raise error("private replacement detail")

            monkeypatch.setattr(session._workspace, "replace_policy", replacement)

    harness.read_hook = arm
    result = harness.run()
    assert result["exit_code"] in {1, 130}
    assert result["patch_application"] == "state-unconfirmed"
    assert checkpoint(result)["phase"] == "unconfirmed"
    assert result["restoration_status"] == "not-run"
    assert "restore" not in harness.prompts
    assert "private replacement detail" not in canonical(result)


@pytest.mark.parametrize("callback", ["read", "emit"])
def test_presentation_failure_after_apply_retains_checkpoint_without_more_effects(
    harness, callback
):
    def fail_read(stage, phrase):
        if stage == "after-check":
            raise RuntimeError("private presentation detail")

    def fail_emit(event):
        if event["kind"] == "owner-policy-file-stage-result" and event["stage"] == "apply":
            raise RuntimeError("private presentation detail")

    harness.read_hook = fail_read if callback == "read" else None
    harness.emit_hook = fail_emit if callback == "emit" else None
    result = harness.run()
    assert result["exit_code"] == 1
    assert result["patch_application"] == "completed"
    assert result["restoration_status"] == "not-run"
    assert checkpoint(result)["closed"] is True
    assert "private presentation detail" not in canonical(result)


@pytest.mark.parametrize("field", ["identity", "citations", "cases", "diff", "sharing"])
def test_full_current_result_revalidation_precedes_any_session(harness, monkeypatch, field):
    original = workflow.run_codex_owner_repair

    async def altered(*args, **kwargs):
        result = await original(*args, **kwargs)
        if field == "identity":
            result["recommendation"]["identity"]["model"] = "forged-model"
        elif field == "citations":
            result["recommendation"]["recommendation"]["evidence_ids"] = ["forged-evidence"]
        elif field == "cases":
            result["recommendation"]["recommendation"]["case_ids"] = ["forged-case"]
        elif field == "diff":
            result["recommendation_preview"]["pair_preview"] = {"diff": "forged-diff"}
        else:
            result["sharing_id"] = "share-old-session"
        return result

    monkeypatch.setattr(workflow, "run_codex_owner_repair", altered)
    result = harness.run()
    assert result["exit_code"] == 1
    assert result["file_workflow"]["failure"]["stage"] == "application-validation"
    assert not harness.sessions and not harness.worker_calls
    assert list(harness.parent.iterdir()) == []


def test_forged_adapter_output_does_not_reach_file_stage(harness):
    def forge(request):
        data = fake_result(request).to_dict()
        data["recommendation"]["case_ids"] = ["forged-case"]
        return OwnerPolicyRepairTransportResult(canonical(data))

    harness.adapter_hook = forge
    result = harness.run()
    assert result["status"] == "recommendation-failed"
    assert not harness.sessions and not harness.worker_calls


def test_copy_confirmation_is_fresh_and_cannot_reuse_previous_session_phrase(harness):
    harness.choices["copy"] = ""
    first = harness.run()
    phrase = first["file_workflow"]["copy_confirmation"]["confirmation_phrase"]
    harness.choices["copy"] = phrase
    second = harness.run()
    assert second["status"] == "copy-declined"
    assert second["file_workflow"]["copy_confirmation"]["confirmation_phrase"] != phrase
    assert list(harness.parent.iterdir()) == []


def test_provider_failure_is_not_retried_and_creates_no_file_session(harness):
    def fail(request):
        raise RuntimeError("private provider detail")

    harness.adapter_hook = fail
    result = harness.run()
    assert result["status"] == "recommendation-failed" and result["exit_code"] == 1
    assert len(harness.adapter_calls) == 1
    assert not harness.sessions and not harness.worker_calls
    assert result["usage"] is None
    assert "private provider detail" not in canonical(result)
    assert list(harness.parent.iterdir()) == []


def test_unknown_usage_is_not_invented_by_file_workflow(harness):
    def no_usage(request):
        data = fake_result(request).to_dict()
        data["usage"] = None
        return OwnerPolicyRepairTransportResult(canonical(data))

    harness.adapter_hook = no_usage
    result = harness.run()
    assert result["status"] == "completed"
    assert result["usage"] is None
    assert result["returned_identity"]["model"] == MODEL


def test_changed_recommendation_during_copy_prompt_is_revalidated_before_creation(
    harness, monkeypatch
):
    captured = {}
    original = workflow.run_codex_owner_repair

    async def capture(*args, **kwargs):
        result = await original(*args, **kwargs)
        captured["result"] = result
        return result

    def change(stage, phrase):
        if stage == "copy":
            captured["result"]["recommendation_preview"]["pair_preview"] = {"changed": True}

    monkeypatch.setattr(workflow, "run_codex_owner_repair", capture)
    harness.read_hook = change
    result = harness.run()
    assert result["exit_code"] == 1
    assert result["file_workflow"]["failure"]["stage"] == "copy"
    assert checkpoint(result)["closed"] is True
    assert list(harness.parent.iterdir()) == []


def test_copy_initial_record_failure_retains_created_path_and_blocks_checks(harness, monkeypatch):
    def fail_record(*args):
        raise OSError("private initial record detail")

    def arm(stage, phrase):
        if stage == "copy":
            monkeypatch.setattr(workspace.PolicyFileWorkspace, "write_record", fail_record)

    harness.read_hook = arm
    result = harness.run()
    data = checkpoint(result)
    assert result["exit_code"] == 1
    assert data["workspace"] and Path(data["workspace"]).is_dir()
    assert data["phase"] == "unconfirmed" and data["closed"] is True
    assert data["evidence_status"] == "unconfirmed"
    assert not (Path(data["workspace"]) / "record.json").exists()
    assert not harness.worker_calls
    assert "private initial record detail" not in canonical(result)


def test_plan_journal_failure_after_apply_blocks_recovery_but_keeps_actual_effect(
    harness, monkeypatch
):
    def arm(event):
        if event["kind"] == "owner-policy-file-stage-result" and event["stage"] == "apply":

            def fail_record(*args):
                raise OSError("private stage record detail")

            monkeypatch.setattr(harness.sessions[-1]._workspace, "write_record", fail_record)

    harness.emit_hook = arm
    result = harness.run()
    assert result["exit_code"] == 1
    assert result["patch_application"] == "completed"
    assert checkpoint(result)["evidence_status"] == "unconfirmed"
    assert "after-check" not in harness.prompts and "restore" not in harness.prompts
    assert result["restoration_status"] == "not-run"


def test_close_failure_exports_last_checkpoint_as_historical_and_current_state_unknown(
    harness, monkeypatch
):
    def arm(stage, phrase):
        if stage == "restore":
            close = harness.sessions[-1].close

            def failed_close():
                close()
                raise OSError("private close detail")

            monkeypatch.setattr(harness.sessions[-1], "close", failed_close)

    harness.read_hook = arm
    result = harness.run()
    assert result["exit_code"] == 1
    assert checkpoint(result) is None
    details = result["file_workflow"]
    assert details["checkpoint_status"] == "unavailable"
    assert details["last_checkpoint"]["phase"] == "restored-before"
    assert details["last_checkpoint"]["workspace"]
    assert result["execution_status"] == "unknown"
    assert result["patch_application"] == result["restoration_status"] == "unknown"
    assert "private close detail" not in canonical(result)


def test_failed_after_check_and_restore_conflict_preserve_both_failures_and_user_edit(harness):
    def fail(wire, output, response):
        if wire["stage"] == "after-check":
            response.update(reason="timeout", output=b"", exit_code=-9)

    def edit(stage, phrase):
        if stage == "restore":
            harness.policy().write_text("# Retain this user edit\n")

    harness.worker_hook = fail
    harness.read_hook = edit
    result = harness.run()
    assert result["exit_code"] == 1
    assert result["restoration_status"] == "not-run"
    assert [item["stage"] for item in result["file_workflow"]["failures"]] == [
        "after-check",
        "restore",
    ]
    assert harness.policy().read_text() == "# Retain this user edit\n"


def test_unsupported_platform_fails_before_interaction_provider_or_copy(monkeypatch):
    monkeypatch.setattr(workflow, "supported", lambda: False)

    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported workflow must not interact or create effects")

    with pytest.raises(workflow.OwnerRepairInputError, match="POSIX non-frozen"):
        asyncio.run(
            workflow.run_codex_owner_file_workflow(
                MODEL, read=forbidden, emit=forbidden, adapter_factory=forbidden
            )
        )


@pytest.mark.parametrize(
    "options", [{"model": "bad model"}, {"candidate": "user.py"}, {"timeout_seconds": 121}]
)
def test_invalid_inputs_precede_interaction_or_provider(options):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid workflow must not interact or create effects")

    with pytest.raises(workflow.OwnerRepairInputError):
        asyncio.run(
            workflow.run_codex_owner_file_workflow(
                **{"model": MODEL, **options},
                read=forbidden,
                emit=forbidden,
                adapter_factory=forbidden,
            )
        )
