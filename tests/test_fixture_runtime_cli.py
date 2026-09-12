"""Offline selector/consent integration; no live provider or process is permitted."""

import asyncio
import importlib
import json
import socket
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest
from click import unstyle
from scripts import demo_verify
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import codex_fixture as workflow
from authzest.runner._fixture_workspace import supported
from test_codex_fixture_cli import fake_draft

MODEL = "fixture-test-model"
runner = CliRunner()
SIMULATED_RUNTIME_EVIDENCE = {
    "debug": False,
    "health_status": 200,
    "health_body": {"status": "ok"},
    "dependency_versions": {
        "python": "3.12.7",
        "fastapi": "0.115.0",
        "starlette": "0.41.0",
        "pydantic": "2.10.0",
    },
}  # Caller-authored test values, not an observation of installed dependency versions.


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Runtime CLI unit tests must not start a provider, process or connection")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def exact(prompt):
    return prompt.split("'")[1]


@pytest.fixture
def fake_adapter():
    calls = []

    class Adapter:
        async def draft(self, request):
            calls.append(request.request_id)
            return fake_draft(request)

    return lambda **kwargs: Adapter(), calls


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
@pytest.mark.parametrize("entry", ["codex", "demo"])
def test_runtime_selector_is_boolean_before_any_side_effect(value, entry, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid selection must not prepare source, emit output or ask for approval")

    monkeypatch.setattr(workflow, "build_fixture_request", forbidden)
    monkeypatch.setattr(demo_verify, "build_demo_proposal", forbidden)
    with pytest.raises(ValueError, match="boolean"):
        asyncio.run(
            workflow.run_codex_fixture(MODEL, runtime_check=value, read=forbidden, emit=forbidden)
            if entry == "codex"
            else demo_verify.run_demo(runtime_check=value, read=forbidden, emit=forbidden)
        )


@pytest.mark.skipif(not supported(), reason="POSIX owned fixture")
def test_runtime_selection_does_not_approve_source_sharing(tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("The runtime selector does not approve sharing or creating a copy")

    output = []
    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            runtime_check=True,
            read=lambda _: "",
            emit=output.append,
            adapter_factory=forbidden,
            parent=tmp_path,
        )
    )
    assert result["status"] == "not-shared" and result["exit_code"] == 0
    assert result["verification_scope"] == "owned-fixture-runtime"
    assert result["runtime_verification_status"] == "not-run"
    assert result["runtime_check_requested"] is True
    assert result["verification"] is result["application"] is None
    assert list(tmp_path.iterdir()) == []
    preview = json.loads(output[0])
    assert preview["verification_scope"] == "owned-fixture-runtime"
    assert "drafting step does not execute source" in preview["sharing"]


@pytest.mark.skipif(not supported(), reason="POSIX owned fixture")
@pytest.mark.parametrize("entry", ["codex", "demo"])
@pytest.mark.parametrize(
    "choice",
    ["approve", "failed", "missing-dependency", "worker-error", "skip", "cancel", "wrong-token"],
)
def test_runtime_plan_needs_separate_exact_consent_and_preserves_restoration(
    tmp_path, monkeypatch, fake_adapter, entry, choice
):
    from authzest.runner import fixture_runtime

    factory, drafts = fake_adapter
    calls = []
    output = []
    prompts = []

    async def fixed_runtime(source):
        calls.append(source)
        if choice == "worker-error":
            raise RuntimeError("PRIVATE-RUNTIME-EXCEPTION")
        status, reason = (
            ("not-run", "runtime-dependency-unavailable")
            if choice == "missing-dependency"
            else ("failed", "runtime-check-failed")
            if choice == "failed"
            else ("passed", "runtime-check-passed")
        )
        return fixture_runtime.RuntimeOutcome(
            status,
            reason,
            fixture_runtime.CHECK_ID,
            sha256(source).hexdigest(),
            fixture_runtime.WORKER_SHA256,
            1.0,
            0,
            SIMULATED_RUNTIME_EVIDENCE if status == "passed" else None,
        )

    monkeypatch.setattr(fixture_runtime, "run_runtime_check", fixed_runtime)

    def read(prompt):
        prompts.append(prompt)
        if "'verify " in prompt:
            plan = json.loads(output[-1])
            assert plan["verification_scope"] == "owned-fixture-runtime"
            assert plan["check_id"] == fixture_runtime.CHECK_ID
            assert plan["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
            assert exact(prompt) == f"verify {plan['plan_id']}"
            assert calls == []
            if choice == "skip":
                return ""
            if choice == "cancel":
                raise EOFError()
            if choice == "wrong-token":
                return "verify verification-static-plan-not-displayed"
        return exact(prompt)

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            runtime_check=True,
            read=read,
            emit=output.append,
            adapter_factory=factory,
            parent=tmp_path,
        )
        if entry == "codex"
        else demo_verify.run_demo(
            runtime_check=True, read=read, emit=output.append, parent=tmp_path
        )
    )
    assert len(drafts) == (1 if entry == "codex" else 0)
    assert [exact(prompt).split()[0] for prompt in prompts] == (
        ["share", "apply", "verify", "restore"]
        if entry == "codex"
        else ["apply", "verify", "restore"]
    )
    assert result["verification_scope"] == "owned-fixture-runtime"
    assert result["application"]["applied"] is True
    assert result["restoration"]["restored"] is True
    assert result["original_checkout_modified"] is False
    if choice in ("skip", "cancel", "wrong-token"):
        assert calls == []
        assert result["runtime_verification_status"] == "not-run"
        assert result["verification_status"] == "not-run"
        assert result["exit_code"] == 0
    else:
        assert calls == [FIXTURE_AFTER.encode()]
        expected = (
            "passed"
            if choice == "approve"
            else "not-run"
            if choice == "missing-dependency"
            else "failed"
        )
        assert result["verification_status"] == result["runtime_verification_status"] == expected
        assert result["restoration"]["runtime_verification_status"] == expected
        assert result["exit_code"] == (0 if choice == "approve" else 1)
    workspace = Path(result["application"]["workspace"])
    assert workspace.joinpath("main.py").read_text() == FIXTURE_SOURCE
    assert "PRIVATE-RUNTIME-EXCEPTION" not in json.dumps(result) + "".join(output)
    if entry == "demo":
        assert result["live_provider_calls"] == 0 and result["simulated_draft"] is True
        assert result["kind"] == "offline-owned-fixture-runtime-workflow"
        preview = json.loads(output[0])
        assert "executes only the exact maintained fixture" in " ".join(preview["limitations"])


@pytest.mark.skipif(not supported(), reason="POSIX owned fixture")
@pytest.mark.parametrize("entry", ["codex", "demo"])
def test_uncertain_runtime_stage_failure_omits_runtime_status_but_still_restores(
    tmp_path, monkeypatch, fake_adapter, entry
):
    factory, _ = fake_adapter

    async def fail(self):
        raise RuntimeError("PRIVATE-RUNTIME-EXCEPTION")

    monkeypatch.setattr(workflow.FixtureApplySession, "verify", fail)
    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            runtime_check=True,
            read=exact,
            emit=lambda _: None,
            adapter_factory=factory,
            parent=tmp_path,
        )
        if entry == "codex"
        else demo_verify.run_demo(
            runtime_check=True, read=exact, emit=lambda _: None, parent=tmp_path
        )
    )
    assert result["status"] == "verification-failed" and result["exit_code"] == 1
    assert "runtime_verification_status" not in result
    assert "runtime_verification_status" not in result["verification"]
    assert result["restoration"]["restored"] is True
    assert "PRIVATE-RUNTIME-EXCEPTION" not in json.dumps(result)


@pytest.mark.skipif(not supported(), reason="POSIX owned fixture")
@pytest.mark.parametrize("entry", ["codex", "demo"])
def test_declined_application_in_runtime_mode_never_asks_for_or_runs_verification(
    tmp_path, fake_adapter, entry
):
    factory, _ = fake_adapter
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        return exact(prompt) if "'share " in prompt else ""

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            runtime_check=True,
            read=read,
            emit=lambda _: None,
            adapter_factory=factory,
            parent=tmp_path,
        )
        if entry == "codex"
        else demo_verify.run_demo(
            runtime_check=True, read=read, emit=lambda _: None, parent=tmp_path
        )
    )
    assert result["application"]["status"] == "declined"
    assert result["verification"] is result["restoration"] is None
    assert result["runtime_verification_status"] == "not-run"
    assert result["verification_scope"] == "owned-fixture-runtime"
    assert result["exit_code"] == 0
    assert not any("'verify " in prompt for prompt in prompts)


@pytest.mark.skipif(not supported(), reason="POSIX owned fixture")
@pytest.mark.parametrize("entry", ["codex", "demo"])
def test_runtime_cancellation_retains_failed_journal_without_claiming_no_execution(
    tmp_path, monkeypatch, fake_adapter, entry
):
    from authzest.runner import fixture_runtime

    factory, _ = fake_adapter
    state = []

    async def waiting_check(source):
        assert source == FIXTURE_AFTER.encode()
        state.append("started")
        try:
            await asyncio.Event().wait()
        finally:
            state.append("finished")

    monkeypatch.setattr(fixture_runtime, "run_runtime_check", waiting_check)

    async def run():
        task = asyncio.create_task(
            workflow.run_codex_fixture(
                MODEL,
                runtime_check=True,
                read=exact,
                emit=lambda _: None,
                adapter_factory=factory,
                parent=tmp_path,
            )
            if entry == "codex"
            else demo_verify.run_demo(
                runtime_check=True, read=exact, emit=lambda _: None, parent=tmp_path
            )
        )
        async with asyncio.timeout(2):
            while not state:
                await asyncio.sleep(0)
        task.cancel()
        if entry == "codex":
            with pytest.raises(asyncio.CancelledError):
                await task
            return None
        return await task

    result = asyncio.run(run())
    assert state == ["started", "finished"]
    if result is not None:
        assert result["status"] == "cancelled" and result["exit_code"] == 130
        assert "verification_status" not in result
        assert "runtime_verification_status" not in result
    workspace = next(tmp_path.iterdir())
    journal = json.loads(workspace.joinpath("record.json").read_text())
    assert journal["runtime_verification_status"] == "failed"
    assert journal["verification"]["execution_attempted"] is True
    assert journal["applied"] is True and journal["restored"] is False
    assert workspace.joinpath("main.py").read_text() == FIXTURE_AFTER


def test_public_runtime_flag_is_selector_only_and_exposes_no_arbitrary_targets(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    help_text = unstyle(runner.invoke(app, ["codex-fixture", "--help"]).stdout)
    assert "--runtime-check" in help_text
    assert "separate verification approval" in " ".join(help_text.split())
    assert all(option not in help_text for option in ("--yes", "--path", "--command", "--test"))
    assert "_runtime-worker" not in unstyle(runner.invoke(app, ["--help"]).stdout)
    assert "_runtime-smoke" not in unstyle(runner.invoke(app, ["--help"]).stdout)


@pytest.mark.parametrize("bad_value", ["true", "false", "main.py"])
def test_cli_selector_rejects_values_before_workflow(monkeypatch, bad_value):
    monkeypatch.setattr(workflow, "run_codex_fixture", lambda *a, **kw: pytest.fail("Invalid CLI"))
    assert (
        runner.invoke(
            app, ["codex-fixture", "--model", MODEL, "--runtime-check", bad_value]
        ).exit_code
        == 2
    )


@pytest.mark.parametrize("selected", [False, True])
def test_cli_forwards_only_boolean_runtime_selection(monkeypatch, selected):
    calls = []

    async def run(*args, **kwargs):
        calls.append(kwargs["runtime_check"])
        return {"exit_code": 0, "runtime_verification_status": "not-run"}

    monkeypatch.setattr(workflow, "run_codex_fixture", run)
    args = ["codex-fixture", "--model", MODEL] + (["--runtime-check"] if selected else [])
    assert runner.invoke(app, args).exit_code == 0
    assert calls == [selected]


@pytest.mark.parametrize("entry", ["codex", "demo"])
@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError])
def test_outer_runtime_failure_never_claims_not_run(monkeypatch, capsys, entry, failure):
    async def fail(*args, **kwargs):
        raise failure("PRIVATE-RUNTIME-EXCEPTION")

    if entry == "codex":
        monkeypatch.setattr(workflow, "run_codex_fixture", fail)
        result = runner.invoke(app, ["codex-fixture", "--model", MODEL, "--runtime-check"])
        output = result.stdout
    else:
        monkeypatch.setattr("sys.argv", ["demo_verify", "--runtime-check"])
        monkeypatch.setattr(demo_verify, "run_demo", fail)
        demo_verify.main()
        output = capsys.readouterr().out
    summary = json.loads(output)
    assert "runtime_verification_status" not in summary
    assert "verification_status" not in summary
    assert "PRIVATE-RUNTIME-EXCEPTION" not in output


@pytest.mark.parametrize("exit_code", [0, 2])
def test_hidden_runtime_worker_dispatches_only_fixed_entry(monkeypatch, exit_code):
    worker = importlib.import_module("authzest.runner._runtime_worker")
    calls = []

    def fixed_main():
        calls.append("fixed")
        return exit_code

    monkeypatch.setattr(worker, "worker_main", fixed_main)
    result = runner.invoke(app, ["_runtime-worker"])
    assert result.exit_code == exit_code
    assert calls == ["fixed"]


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_hidden_runtime_smoke_preserves_fixed_helper_status(monkeypatch, exit_code):
    helper = importlib.import_module("authzest.runner.runtime_smoke")

    async def fixed_smoke():
        return {"status": "scripted-smoke-result", "exit_code": exit_code}

    monkeypatch.setattr(helper, "run_runtime_smoke", fixed_smoke)
    result = runner.invoke(app, ["_runtime-smoke"])
    assert result.exit_code == exit_code
    assert json.loads(result.stdout)["status"] == "scripted-smoke-result"


@pytest.mark.parametrize("command", ["_runtime-worker", "_runtime-smoke"])
def test_hidden_runtime_entries_reject_target_paths(command):
    assert runner.invoke(app, [command, "main.py"]).exit_code == 2


def test_demo_cli_forwards_runtime_selector_without_inventing_consent(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["demo_verify", "--runtime-check"])
    selections = []

    async def run(*, runtime_check):
        selections.append(runtime_check)
        return {"exit_code": 0, "runtime_verification_status": "not-run"}

    monkeypatch.setattr(demo_verify, "run_demo", run)
    assert demo_verify.main() == 0
    assert selections == [True]
    assert json.loads(capsys.readouterr().out)["runtime_verification_status"] == "not-run"
