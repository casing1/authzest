"""Offline CLI/output tests; only explicitly guarded temporary-copy I/O is real.

Provider replies and worker observations are scripted. No policy compilation or
execution, child process or network is permitted, including the CLI integration cases.
"""

import asyncio
import builtins
import copy
import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click import unstyle
from click.testing import CliRunner as ClickRunner
from typer.main import get_command
from typer.testing import CliRunner

from authzest.cli import app
from authzest.cli_output import (
    WorkflowOutput,
    format_file_workflow_result,
    json_output,
)
from authzest.codex.contracts import canonical
from authzest.codex.owner_policy_repair_pair import build_owner_policy_repair_pair
from authzest.codex.owner_policy_repair_transport import (
    prepare_owner_policy_repair_transport_result,
)
from authzest.runner import _owner_policy_file_transport as file_transport
from authzest.runner import _owner_policy_file_workspace as file_workspace
from authzest.runner import codex_owner_repair as recommendation_workflow
from authzest.runner import owner_policy_file_repair as file_session

MODEL = "owner-file-cli-test-model"
MODULE = "authzest.runner.codex_owner_file_workflow"
CASES = (
    "owner-control",
    "non-owner",
    "missing-read-scope",
    "unauthenticated-owner",
    "missing-principal",
    "missing-report",
    "wildcard-is-not-read",
    "exact-owner-no-normalization",
)
runner = CliRunner()
# Saved before the autouse guard; only the opt-in integration fixture may call it,
# always with its pytest-owned tmp_path as the private test-only parent.
_CREATE_TEMP_COPY = file_session.OwnerPolicyRepairFileSession.create_copy


@pytest.fixture(autouse=True)
def no_live_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("CLI tests must not invoke providers, workers, copies, processes or network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(recommendation_workflow, "_default_adapter_factory", forbidden)
    monkeypatch.setattr(file_session, "_run_worker", forbidden)
    monkeypatch.setattr(file_session.OwnerPolicyRepairFileSession, "create_copy", forbidden)
    connect = socket.socket.connect
    policy = asyncio.get_event_loop_policy()
    create_loop = policy.new_event_loop

    def new_event_loop():
        # Windows constructs its event-loop socketpair before test/workflow code runs.
        with monkeypatch.context() as initialization:
            initialization.setattr(socket.socket, "connect", connect)
            return create_loop()

    monkeypatch.setattr(policy, "new_event_loop", new_event_loop)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def stub_runner(monkeypatch, implementation):
    monkeypatch.setitem(
        sys.modules, MODULE, SimpleNamespace(run_codex_owner_file_workflow=implementation)
    )


def scripted_checkpoint(*, restored=True):
    """Caller-authored display data, not a valid receipt or actual execution observation."""
    before = [True, True, False, False, False, False, False, True]
    after = [True, False, False, False, False, False, False, False]
    return {
        "phase": "restored-before" if restored else "applied-after",
        "generation": 3 if restored else 2,
        "workspace": "SCRIPTED retained copy\\nnot a real path",
        "closed": True,
        "diff_status": "accepted",
        "application_status": "completed",
        "restoration_status": "completed" if restored else "not-run",
        "comparison_status": "passed",
        "file_binding_status": "confirmed",
        "evidence_status": "confirmed",
        "authorization_status": "unknown",
        "provider_calls": 0,
        "failure": None,
        "attempts_consumed": ["before-check", "diff", "apply", "after-check", "restore"],
        "restart_supported": False,
        "provenance": {"kind": "SCRIPTED unauthenticated checkpoint", "authenticated": False},
        "checks": {
            candidate: {
                "execution_status": "completed",
                "comparison_status": "failed" if candidate == "before" else "passed",
                "reason": "case-mismatch" if candidate == "before" else "cases-match",
                "transport": {"returncode": 0, "cleanup_status": "confirmed"},
            }
            for candidate in ("before", "after")
        },
        "comparison": [
            {
                "case_id": case,
                "expected": "allow" if index == 0 else "deny",
                "before": before[index],
                "after": after[index],
                "change": "changed" if before[index] != after[index] else "unchanged",
            }
            for index, case in enumerate(CASES)
        ],
    }


def scripted_result(checkpoint=None):
    return {
        "kind": "codex-owner-file-workflow",
        "status": "SCRIPTED completed",
        "exit_code": 0,
        "candidate": "before",
        "sharing_decision": "approve",
        "application_turn_attempts": 1,
        "returned_identity": {"model": MODEL},
        "usage": {"input_tokens": 10, "output_tokens": 20},
        "latency_ms": 1,
        "provider_warning_count": 0,
        "provider_retry_notification_count": 0,
        "execution_status": "completed",
        "patch_application": "completed",
        "restoration_status": "completed",
        "comparison_status": "passed",
        "authorization_status": "unknown",
        "failure": None,
        "limits": {"os_sandbox": False},
        "recommendation": {"rationale": "SCRIPTED caller-authored data, not a model reply"},
        "file_workflow": {
            "copy_decision": "approved",
            "copy_confirmation": {"confirmation_phrase": "SCRIPTED not a real choice"},
            "session_result": checkpoint,
            "failure": None,
            "retention_notice": "SCRIPTED retained files; no resume or authenticated authority",
        },
    }


@pytest.mark.parametrize("color", [True, False])
def test_file_workflow_help_is_explicit_opt_in(color):
    result = runner.invoke(app, ["codex-owner-repair", "--help"], color=color)
    assert result.exit_code == 0
    assert "--file-workflow" in unstyle(result.output)
    assert "not approval" in unstyle(result.output)


@pytest.mark.parametrize("candidate", ["before", "after"])
@pytest.mark.parametrize("as_json", [True, False])
def test_file_flag_preview_uses_identical_existing_offline_builder(candidate, as_json, monkeypatch):
    original = recommendation_workflow.build_owner_repair_preview
    calls = []

    def preview(model, **kwargs):
        calls.append((model, kwargs))
        return original(model, **kwargs, invocation_nonce="a" * 32)

    async def forbidden(*args, **kwargs):
        pytest.fail("Preview must not start either workflow")

    monkeypatch.setattr(recommendation_workflow, "build_owner_repair_preview", preview)
    monkeypatch.setattr(recommendation_workflow, "run_codex_owner_repair", forbidden)
    stub_runner(monkeypatch, forbidden)
    options = ["codex-owner-repair", "--model", MODEL, "--candidate", candidate, "--preview-only"]
    if as_json:
        options.append("--json")
    existing = runner.invoke(app, options)
    opted_in = runner.invoke(app, [*options, "--file-workflow"])
    assert existing.exit_code == opted_in.exit_code == 0
    assert existing.stdout == opted_in.stdout
    assert existing.stderr == opted_in.stderr == ""
    assert calls == [(MODEL, {"candidate": candidate, "timeout_seconds": 120.0})] * 2
    if as_json:
        data = json.loads(opted_in.stdout)
        assert data["kind"] == "codex-owner-repair-sharing-preview"
        assert "file_workflow" not in data and "owner-file-check-" not in opted_in.stdout


def test_no_flag_keeps_original_runner_and_result_unchanged(monkeypatch):
    expected = {
        "kind": "SCRIPTED recommendation-only",
        "exit_code": 0,
        "execution_status": "not-run",
    }
    calls = []

    async def old_runner(model, **kwargs):
        calls.append((model, kwargs))
        return expected

    async def forbidden(*args, **kwargs):
        pytest.fail("Default command must not invoke file workflow")

    monkeypatch.setattr(recommendation_workflow, "run_codex_owner_repair", old_runner)
    stub_runner(monkeypatch, forbidden)
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL, "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected and result.stderr == ""
    assert len(calls) == 1


def test_file_flag_routes_exact_arguments_and_json_has_one_stdout_document(monkeypatch):
    calls, prompts = [], []
    checkpoint = scripted_checkpoint()
    final = scripted_result(checkpoint)
    events = [
        {
            "kind": "owner-policy-file-copy-preview",
            "application": {"source_text": "SCRIPTED source\\nwith controls\x1b[31m"},
            "copy_confirmation": {"confirmation_phrase": "copy SCRIPTED session application"},
        },
        {
            "kind": "owner-policy-file-stage-preview",
            "stage": "before-check",
            "plan": {"worker_source": "SCRIPTED never compiled", "all_fields": [1, 2, 3]},
            "decision": {"choice": "pending", "expires_at": 300},
        },
        {
            "kind": "owner-policy-file-stage-result",
            "stage": "after-check",
            "session_result": checkpoint,
        },
    ]

    async def fake(model, *, candidate, timeout_seconds, emit, read):
        calls.append((model, candidate, timeout_seconds))
        for event in events:
            emit(json.dumps(event))
        prompts.append(read("SCRIPTED exact choice? "))
        return final

    stub_runner(monkeypatch, fake)
    result = runner.invoke(
        app,
        [
            "codex-owner-repair",
            "--model",
            MODEL,
            "--candidate",
            "after",
            "--timeout-seconds",
            "12",
            "--file-workflow",
            "--json",
        ],
        input="cancel\n",
    )
    assert result.exit_code == 0 and json.loads(result.stdout) == final
    assert calls == [(MODEL, "after", 12.0)] and prompts == ["cancel"]
    assert (
        result.stderr
        == "".join(json_output(event) + "\n" for event in events) + "SCRIPTED exact choice? "
    )
    assert "\x1b" not in result.stderr and "\\u001b" in result.stderr


@pytest.mark.parametrize(
    "kind", ["owner-policy-file-copy-preview", "owner-policy-file-stage-preview"]
)
def test_human_consent_preview_contains_complete_authoritative_json(kind, monkeypatch):
    event = {
        "kind": kind,
        "stage": "SCRIPTED\nHEADING\x1b[2J\u202e",
        "application": {"all_content": "SCRIPTED source\n\x1b[31m\u202e"},
        "copy_confirmation": {"session_id": "SCRIPTED", "confirmation_phrase": "SCRIPTED copy"},
        "plan": {"worker_source": "SCRIPTED never compiled", "nested": {"complete": True}},
        "decision": {"choice": "pending", "expires_at": 300},
    }

    async def fake(model, *, emit, **kwargs):
        emit(json.dumps(event))
        return scripted_result()

    stub_runner(monkeypatch, fake)
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL, "--file-workflow"])
    assert result.exit_code == 0
    assert "Complete authoritative JSON (review every field before consent)" in result.stdout
    assert json_output(event) in result.stdout
    assert "\x1b" not in result.stdout and "\u202e" not in result.stdout
    assert "\\u001b" in result.stdout and "\\u202e" in result.stdout
    assert "SCRIPTED\nHEADING" not in result.stdout


def test_human_final_separates_all_eight_cases_and_historical_restored_pass():
    checkpoint = scripted_checkpoint()
    rendered = format_file_workflow_result(scripted_result(checkpoint))
    assert "Case | Expected | Before | Applied after | Change" in rendered
    for case in CASES:
        assert rendered.count(json.dumps(case)) == 1
    assert '"non-owner" | "deny" | true | false | "changed"' in rendered
    assert '"owner-control" | "allow" | true | true | "unchanged"' in rendered
    for status in (
        "execution_status",
        "comparison_status",
        "application_status",
        "restoration_status",
        "file_binding_status",
        "evidence_status",
        "provenance",
    ):
        assert json.dumps(status) in rendered
    assert "HISTORICAL" in rendered and "currently restored before file passes" in rendered
    assert "unauthenticated" in rendered and "Session provider_calls excludes" in rendered
    assert '"input_tokens": 10' in rendered and '"output_tokens": 20' in rendered


@pytest.mark.parametrize("unknown", [None, 0, 1, "false", {}, []])
def test_unknown_or_non_boolean_observations_are_never_rendered_as_denial(unknown):
    checkpoint = scripted_checkpoint(restored=False)
    checkpoint["comparison"][1]["before"] = unknown
    checkpoint["comparison"][1]["after"] = unknown
    rendered = format_file_workflow_result(scripted_result(checkpoint))
    assert (
        '"non-owner" | "deny" | unknown (no accepted observation) | '
        "unknown (no accepted observation)" in rendered
    )
    assert "HISTORICAL" not in rendered


def test_human_result_quotes_paths_labels_and_model_metadata():
    checkpoint = scripted_checkpoint()
    attack = "SCRIPTED\nFORGED TITLE\x1b[2J\u202e"
    checkpoint["workspace"] = attack
    checkpoint["comparison"][0]["case_id"] = attack
    final = scripted_result(checkpoint)
    final["returned_identity"] = {"model": attack}
    rendered = format_file_workflow_result(final)
    assert "\x1b" not in rendered and "\u202e" not in rendered
    assert "SCRIPTED\nFORGED TITLE" not in rendered
    assert rendered.count(json.dumps(attack, ensure_ascii=True)) == 3


@pytest.mark.parametrize("status", ["no-change", "unknown", "not-shared"])
def test_normal_no_session_outcome_is_not_checkpoint_failure_and_keeps_rationale(status):
    final = scripted_result()
    final.update(
        status=status,
        execution_status="not-run",
        patch_application="not-run",
        restoration_status="not-run",
        comparison_status="not-evaluated",
    )
    final["file_workflow"].update(checkpoint_status="not-created", copy_decision="not-requested")
    rationale = "SCRIPTED rationale\nNOT A HEADING\x1b[2J\u202e"
    final["recommendation"] = {
        "recommendation": {"status": status, "rationale": rationale, "uncertainties": ["unknown"]}
    }
    rendered = format_file_workflow_result(final)
    assert "File workflow not started: no file session or copy was created" in rendered
    assert "File checkpoint unavailable" not in rendered
    assert "Untrusted recommendation - not execution or permission" in rendered
    assert json.dumps(rationale, ensure_ascii=True) in rendered
    assert '"uncertainties"' in rendered
    assert "\x1b" not in rendered and "\u202e" not in rendered


def test_missing_checkpoint_is_unknown_even_when_last_historical_checkpoint_exists():
    final = scripted_result()
    final["file_workflow"].update(
        checkpoint_status="unavailable", last_checkpoint=scripted_checkpoint()
    )
    rendered = format_file_workflow_result(final)
    assert "File checkpoint unavailable" in rendered
    assert "no file session or copy was created" not in rendered
    assert "Case | Expected | Before | Applied after | Change" not in rendered


@pytest.mark.parametrize("as_json", [False, True])
def test_actual_runner_share_decline_never_starts_file_session(as_json, monkeypatch):
    workflow = importlib.import_module(MODULE)
    monkeypatch.setattr(workflow, "supported", lambda: True)
    options = ["codex-owner-repair", "--model", MODEL, "--file-workflow"]
    result = runner.invoke(app, [*options, *(["--json"] if as_json else [])], input="\n")
    assert result.exit_code == 0
    if as_json:
        final = json.loads(result.stdout)
        assert final["status"] == "not-shared"
        assert final["file_workflow"]["checkpoint_status"] == "not-created"
        assert final["file_workflow"]["session_result"] is None
        assert final["application_turn_attempts"] == 0
        assert final["execution_status"] == "not-run"
        assert "codex-owner-repair-sharing-preview" in result.stderr
    else:
        assert "File workflow not started: no file session or copy was created" in result.stdout
        assert "File checkpoint unavailable" not in result.stdout


@pytest.mark.parametrize("as_json", [False, True])
def test_runner_partial_failure_checkpoint_survives_cli_output(as_json, monkeypatch):
    checkpoint = scripted_checkpoint(restored=False)
    checkpoint.update(
        evidence_status="unconfirmed",
        failure="evidence-unconfirmed",
        comparison_status="inconclusive",
    )
    final = scripted_result(checkpoint)
    final.update(
        status="cancelled",
        exit_code=130,
        restoration_status="not-run",
        comparison_status="inconclusive",
    )

    async def fake(*args, **kwargs):
        return final

    stub_runner(monkeypatch, fake)
    options = ["codex-owner-repair", "--model", MODEL, "--file-workflow"]
    result = runner.invoke(app, [*options, *(["--json"] if as_json else [])])
    assert result.exit_code == 130
    if as_json:
        assert json.loads(result.stdout) == final
    else:
        assert '"application_status": "completed"' in result.stdout
        assert '"evidence_status": "unconfirmed"' in result.stdout
        assert '"restoration_status": "not-run"' in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    "error,code", [(RuntimeError, 1), (asyncio.CancelledError, 130), (KeyboardInterrupt, 130)]
)
def test_unexpected_file_runner_failure_does_not_invent_non_execution(error, code, monkeypatch):
    async def fail(*args, **kwargs):
        raise error("PRIVATE FAILURE\x1b[2J")

    stub_runner(monkeypatch, fail)
    result = runner.invoke(
        app, ["codex-owner-repair", "--model", MODEL, "--file-workflow", "--json"]
    )
    assert result.exit_code == code
    final = json.loads(result.stdout)
    assert (
        final["execution_status"]
        == final["patch_application"]
        == final["restoration_status"]
        == "unknown"
    )
    assert final["file_workflow"]["session_result"] is None
    assert "No rollback, deletion or non-execution" in final["file_workflow"]["retention_notice"]
    assert "PRIVATE" not in result.output and "not-run" not in result.stdout


def test_stage_observation_is_visible_before_next_prompt(monkeypatch):
    seen = []

    async def fake(*args, emit, read, **kwargs):
        emit(
            json.dumps(
                {
                    "kind": "owner-policy-file-stage-result",
                    "stage": "before-check",
                    "session_result": scripted_checkpoint(restored=False),
                }
            )
        )
        seen.append(read("SCRIPTED next separate decision: "))
        return scripted_result()

    monkeypatch.setattr(builtins, "input", lambda: "cancel")
    stub_runner(monkeypatch, fake)
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL, "--file-workflow"])
    assert result.exit_code == 0 and seen == ["cancel"]
    assert "Owned-file stage observation" in result.stdout
    assert "Case | Expected | Before | Applied after | Change" in result.stdout
    assert result.stderr == "SCRIPTED next separate decision: "


def test_reader_keeps_control_characters_quoted(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", lambda: "exact answer")
    assert WorkflowOutput(True).read("SCRIPTED\n\x1b[2J\u202e ") == "exact answer"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "SCRIPTED\\n\\u001b[2J\\u202e "


@pytest.fixture
def file_cli_integration(monkeypatch, tmp_path):
    """Run the actual CLI and coordinators; replace only adapter and worker effects."""
    if not file_workspace.supported():
        pytest.skip("Real temporary-copy I/O requires supported POSIX non-frozen source mode")
    workflow = importlib.import_module(MODULE)
    # Build Typer's Click command/annotations before forbidding eval/compile.
    # Invocation below still parses the actual CLI arguments and runs the real command.
    command = get_command(app)
    # Prime lazy CLI parser/help imports without invoking any product callback.
    with (
        command.make_context("authzest", [], resilient_parsing=True) as context,
        command.commands["codex-owner-repair"].make_context(
            "codex-owner-repair", ["--model", MODEL], parent=context
        ),
    ):
        pass
    state = SimpleNamespace(
        events=[],
        prompts=[],
        sessions=[],
        adapters=[],
        requests=[],
        workers=[],
        final=None,
        fail_after=False,
    )
    monkeypatch.setattr(workflow, "monotonic", lambda: 100.0)
    original_session = file_session.OwnerPolicyRepairFileSession

    def session_factory(application, *, clock):
        session = original_session(application, clock=clock)
        monkeypatch.setattr(
            session, "create_copy", lambda: _CREATE_TEMP_COPY(session, _parent=tmp_path)
        )
        state.sessions.append(session)
        return session

    monkeypatch.setattr(workflow, "OwnerPolicyRepairFileSession", session_factory)

    class ScriptedAdapter:
        warnings_seen = 0
        retry_notifications_seen = 0

        def __init__(self, **kwargs):
            state.adapters.append(kwargs)

        async def recommend_owner_policy_repair(self, request):
            state.requests.append(request.to_dict())
            envelope = request.to_dict()
            inner = envelope["request"]
            raw = {
                "schema_version": "1.0",
                "request_id": envelope["request_id"],
                "status": "registered-change",
                "rationale": "SCRIPTED CLI integration data, not a model reply or runtime proof.",
                "evidence_ids": list(inner["evidence_ids"].values()),
                "case_ids": [case["case_id"] for case in inner["content"]["cases"]],
                "assumptions": ["Synthetic context is trusted for this offline test."],
                "uncertainties": ["No policy is compiled or executed in this test."],
                "expected_effects": ["Only the registered predicate may be selected."],
                "limitations": ["Not live-model, policy or endpoint acceptance."],
                "change_pair_id": inner["registry"]["pair_id"],
            }
            return prepare_owner_policy_repair_transport_result(
                canonical(raw), request, usage={"input_tokens": 11, "output_tokens": 22}
            )

    monkeypatch.setattr(recommendation_workflow, "_default_adapter_factory", ScriptedAdapter)

    async def scripted_worker(wire, *, before_launch=None):
        before_launch()
        state.workers.append(copy.deepcopy(wire))
        if state.fail_after and wire["stage"] == "after-check":
            return file_transport.WorkerTransport(
                output=b"",
                exit_code=-9,
                reason="timeout",
                child_cleanup_status="confirmed",
                workspace_cleanup_status="confirmed",
                launch_status="started",
            )
        output = copy.deepcopy(wire)
        output.pop("source_text")
        # Authored booleans are transport stubs, never outputs from executed policies.
        observations = (
            [True, True, False, False, False, False, False, True]
            if wire["candidate"] == "before"
            else [True, False, False, False, False, False, False, False]
        )
        output["cases"] = [
            {"case_id": case["case_id"], "input_sha256": case["input_sha256"], "observed": observed}
            for case, observed in zip(wire["cases"], observations, strict=True)
        ]
        return file_transport.WorkerTransport(
            output=canonical(output).encode(),
            exit_code=0,
            reason=None,
            child_cleanup_status="confirmed",
            workspace_cleanup_status="confirmed",
            launch_status="started",
        )

    monkeypatch.setattr(file_session, "_run_worker", scripted_worker)
    original_emit = WorkflowOutput.emit
    original_finish = WorkflowOutput.finish

    def emit(output, text):
        original_emit(output, text)
        state.events.append(json.loads(text))

    def finish(output, result, **kwargs):
        original_finish(output, result, **kwargs)
        state.final = copy.deepcopy(result)

    monkeypatch.setattr(WorkflowOutput, "emit", emit)
    monkeypatch.setattr(WorkflowOutput, "finish", finish)

    def input_choice():
        # The real output.read has already printed its prompt, and original_emit
        # displayed the complete current envelope before we supply a test choice.
        event = state.events[-1]
        if event["kind"] == "codex-owner-repair-sharing-preview":
            stage, phrase = "share", "share " + event["sharing_id"]
        elif event["kind"] == "owner-policy-file-copy-preview":
            stage = "copy"
            phrase = event["copy_confirmation"]["confirmation_phrase"]
            assert list(tmp_path.iterdir()) == []
            assert event["application"]["request"]["content"]["before"]["text"]
        else:
            assert event["kind"] == "owner-policy-file-stage-preview"
            stage = event["stage"]
            phrase = f"approve {stage} {event['plan']['plan_id']}"
            assert event["decision"]["choice"] == "pending"
            assert event["decision"]["plan_id"] == event["plan"]["plan_id"]
            if stage.endswith("-check"):
                assert event["plan"]["recipe"]["worker_source"]
                assert event["plan"]["worker_input"]["source_text"]
                assert len(event["plan"]["worker_input"]["cases"]) == 8
        state.prompts.append((stage, phrase))
        return phrase

    monkeypatch.setattr(builtins, "input", input_choice)

    def forbidden(*args, **kwargs):
        pytest.fail("Offline CLI integration must not compile/evaluate policies or use live I/O")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn", "openai", "httpx", "requests"}:
            forbidden()
        if name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    def invoke(*, as_json):
        options = ["codex-owner-repair", "--model", MODEL, "--file-workflow"]
        if as_json:
            options.append("--json")
        with monkeypatch.context() as guard:
            guard.setattr(builtins, "__import__", guarded_import)
            for name in ("compile", "eval", "exec"):
                guard.setattr(builtins, name, forbidden)
            guard.setattr(os, "system", forbidden)
            guard.setattr(asyncio, "create_subprocess_shell", forbidden)
            guard.setattr(socket.socket, "connect_ex", forbidden)
            guard.setattr(socket, "create_connection", forbidden)
            guard.setattr(file_transport, "run_worker", forbidden)
            return ClickRunner().invoke(command, options)

    state.invoke = invoke
    state.parent = tmp_path
    return state


@pytest.mark.parametrize("as_json", [False, True])
def test_actual_cli_full_seven_gate_flow_with_only_scripted_execution(
    file_cli_integration, as_json
):
    state = file_cli_integration
    result = state.invoke(as_json=as_json)
    assert result.exit_code == 0, result.output
    final = state.final
    checkpoint = final["file_workflow"]["session_result"]
    assert [stage for stage, _ in state.prompts] == [
        "share",
        "copy",
        "before-check",
        "diff",
        "apply",
        "after-check",
        "restore",
    ]
    assert len({phrase for _, phrase in state.prompts}) == 7
    assert len(state.adapters) == len(state.requests) == 1
    assert [wire["stage"] for wire in state.workers] == ["before-check", "after-check"]
    assert final["status"] == "completed"
    assert final["application_turn_attempts"] == 1
    assert final["usage"] == {"input_tokens": 11, "output_tokens": 22}
    assert checkpoint["checks"]["before"]["comparison_status"] == "failed"
    assert checkpoint["checks"]["after"]["comparison_status"] == "passed"
    assert checkpoint["application_status"] == checkpoint["restoration_status"] == "completed"
    assert checkpoint["file_binding_status"] == checkpoint["evidence_status"] == "confirmed"
    assert checkpoint["phase"] == "restored-before" and checkpoint["generation"] == 3
    assert checkpoint["closed"] is True and checkpoint["provider_calls"] == 0
    assert checkpoint["authorization_status"] == "unknown"
    policy = Path(checkpoint["workspace"]) / "policy.py"
    assert policy.parent.parent == state.parent
    pair = build_owner_policy_repair_pair().to_dict()["content"]
    assert policy.read_text() == pair["before"]["text"]
    assert [wire["source_text"] for wire in state.workers] == [
        pair["before"]["text"],
        pair["after"]["text"],
    ]
    durable = json.loads((policy.parent / "record.json").read_text())
    assert durable["closed"] is False and durable["phase"] == "restored-before"
    previews = [event for event in state.events if event["kind"].endswith("preview")]
    assert len(previews) == 7
    if as_json:
        assert json.loads(result.stdout) == final
        assert all(json_output(event) in result.stderr for event in previews)
    else:
        assert all(json_output(event) in result.stdout for event in previews)
        assert "Case | Expected | Before | Applied after | Change" in result.stdout
        assert '"non-owner" | "deny" | true | false | "changed"' in result.stdout
        assert "HISTORICAL" in result.stdout
    for _, phrase in state.prompts:
        assert f"Type '{phrase}' to confirm" in result.stderr


def test_actual_cli_after_failure_still_requires_and_records_separate_restore(file_cli_integration):
    state = file_cli_integration
    state.fail_after = True
    result = state.invoke(as_json=True)
    assert result.exit_code == 1
    final = json.loads(result.stdout)
    assert final == state.final
    checkpoint = final["file_workflow"]["session_result"]
    assert [stage for stage, _ in state.prompts] == [
        "share",
        "copy",
        "before-check",
        "diff",
        "apply",
        "after-check",
        "restore",
    ]
    assert final["execution_status"] == "failed"
    assert final["file_workflow"]["failure"] == {"stage": "after-check", "code": "timeout"}
    assert checkpoint["checks"]["after"]["observations"] is None
    assert checkpoint["checks"]["after"]["execution_status"] == "failed"
    assert checkpoint["restoration_status"] == "completed"
    assert checkpoint["phase"] == "restored-before" and checkpoint["generation"] == 3
    assert checkpoint["comparison_status"] == "inconclusive"
    after_event = next(
        event
        for event in state.events
        if event["kind"] == "owner-policy-file-stage-result" and event["stage"] == "after-check"
    )
    restore_event = next(
        event
        for event in state.events
        if event["kind"] == "owner-policy-file-stage-preview" and event["stage"] == "restore"
    )
    assert state.events.index(after_event) < state.events.index(restore_event)
    assert restore_event["decision"]["choice"] == "pending"
    assert len(state.adapters) == 1 and len(state.workers) == 2
    policy = Path(checkpoint["workspace"]) / "policy.py"
    assert policy.parent.parent == state.parent
    assert (
        policy.read_text()
        == build_owner_policy_repair_pair().to_dict()["content"]["before"]["text"]
    )
