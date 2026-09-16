"""Packaged offline demo: simulated terminal choices, never live provider or runtime calls."""

import asyncio
import builtins
import json
import socket
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.fixture_demo import build_demo_proposal
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.codex.proposals import proposal_preview
from authzest.runner import fixture_check
from authzest.runner import fixture_demo as workflow
from authzest.runner._fixture_workspace import supported

runner = CliRunner()
posix_only = pytest.mark.skipif(not supported(), reason="POSIX owned-fixture workflow")


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Packaged demo tests must not connect, start providers or execute fixture code")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def fixed_check(monkeypatch):
    """Script a fixed-check result; this is not evidence that a real worker ran."""
    calls = []

    async def check(source):
        assert source == FIXTURE_AFTER.encode()
        calls.append(source)
        return fixture_check.VerificationOutcome(
            "passed",
            "debug-disabled",
            fixture_check.CHECK_ID,
            sha256(source).hexdigest(),
            fixture_check.WORKER_SHA256,
            0.0,
            0,
        )

    monkeypatch.setattr(fixture_check, "run_configuration_check", check)
    return calls


def exact_choice(prompt):
    """Inject a test-owned response, never claim authenticated human consent."""
    return prompt.split("'")[1]


def records(output):
    return [json.loads(value) for value in output]


def json_stream(text):
    values = []
    decoder = json.JSONDecoder()
    remaining = text.lstrip()
    while remaining:
        value, end = decoder.raw_decode(remaining)
        values.append(value)
        remaining = remaining[end:].lstrip()
    return values


@pytest.mark.parametrize("color", [False, True])
def test_help_is_discoverable_without_preparing_artifacts_or_workspace(monkeypatch, color):
    def forbidden(*args, **kwargs):
        pytest.fail("Help must not prepare artifacts, workspaces or workflow")

    monkeypatch.setattr(workflow, "run_fixture_demo", forbidden)
    monkeypatch.setattr(workflow, "build_demo_proposal", forbidden)
    monkeypatch.setattr(workflow, "FixtureApplySession", forbidden)
    help_result = runner.invoke(app, ["fixture-demo", "--help"], color=color)
    assert help_result.exit_code == 0
    text = unstyle(help_result.stdout)
    assert "fixture-demo" in text and "--help" in text
    assert all(option not in text for option in ("--yes", "--model", "--runtime-check", "--path"))
    top = runner.invoke(app, ["--help"], color=color)
    assert top.exit_code == 0 and "fixture-demo" in unstyle(top.stdout)


@pytest.mark.parametrize(
    "argument",
    [
        "main.py",
        "bundle.json",
        "--yes",
        "--model=model",
        "--provider=mock",
        "--target=.",
        "--path=.",
        "--parent=.",
        "--runtime-check",
        "--command=echo",
    ],
)
def test_no_arbitrary_target_model_execution_or_automatic_approval_options(monkeypatch, argument):
    monkeypatch.setattr(
        workflow, "run_fixture_demo", lambda **kw: pytest.fail("Reject before workflow")
    )
    result = runner.invoke(app, ["fixture-demo", argument])
    assert result.exit_code == 2


def test_unsupported_platform_rejected_before_builder_or_workspace(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported platform must be rejected before any artifact or choice")

    monkeypatch.setattr(workflow, "supported", lambda: False)
    monkeypatch.setattr(workflow, "build_demo_proposal", forbidden)
    monkeypatch.setattr(workflow, "FixtureApplySession", forbidden)
    result = asyncio.run(
        workflow.run_fixture_demo(read=forbidden, emit=lambda _: None, parent=tmp_path)
    )
    assert result["status"] == "unsupported-platform" and result["exit_code"] == 2
    assert result["workspace"] is None and list(tmp_path.iterdir()) == []
    assert result["application"] is result["verification"] is result["restoration"] is None
    assert result["live_provider_calls"] == 0
    assert result["runtime_verification_status"] == "not-run"


def test_packaged_builder_uses_owned_constants_and_mock_identity_outside_checkout(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    original_import = builtins.__import__
    original_open = Path.open

    def packaged_only(name, *args, **kwargs):
        if name.split(".")[0] in {"scripts", "tests"}:
            pytest.fail("Product code must not import development scripts or fixtures")
        return original_import(name, *args, **kwargs)

    def packaged_source_only(path, *args, **kwargs):
        assert "tests" not in path.parts and "scripts" not in path.parts
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", packaged_only)
    monkeypatch.setattr(Path, "open", packaged_source_only)
    request, review, proposal = build_demo_proposal()
    payload = request.to_dict()
    source = [item for item in payload["evidence"] if item["kind"] == "source"]
    assert len(source) == 1 and source[0]["data"]["text"] == FIXTURE_SOURCE
    assert payload["source_revision"] is None
    assert payload["config"]["provider"] == "mock"
    assert review.to_dict()["identity"]["provider"] == "mock"
    assert review.to_dict()["usage"] is None
    assert all(answer["status"] != "confirmed" for answer in review.to_dict()["answers"])
    change = proposal.to_dict()["changes"]
    assert len(change) == 1 and change[0]["path"] == "main.py"
    assert change[0]["after_text"] == FIXTURE_AFTER
    diff = proposal_preview(proposal, request, review)["changes"][0]["diff"]
    assert "-app = FastAPI(debug=True)" in diff
    assert "+app = FastAPI(debug=False)" in diff
    assert list(tmp_path.iterdir()) == []
    repeated = build_demo_proposal()
    assert tuple(item.payload_json for item in repeated) == tuple(
        item.payload_json for item in (request, review, proposal)
    )


@posix_only
@pytest.mark.parametrize("action", ["decline", "cancel", "eof", "interrupt", "wrong-token"])
def test_apply_choices_without_approval_keep_original_and_never_check(
    tmp_path, fixed_check, action
):
    output = []
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        previews = records(output)
        preview = next(value for value in previews if "changes" in value)
        assert preview["changes"][0]["diff"] and preview["proposal_id"] in prompt
        assert (
            next(item["data"]["text"] for item in preview["evidence"] if item["kind"] == "source")
            == FIXTURE_SOURCE
        )
        evidence_ids = {item["id"] for item in preview["evidence"]}
        assert all(
            set(answer["evidence_ids"]) <= evidence_ids for answer in preview["review"]["answers"]
        )
        assert previews[0]["draft_provenance"] == "caller-authored-mock"
        assert previews[0]["limitations"]
        if action == "eof":
            raise EOFError()
        if action == "interrupt":
            raise KeyboardInterrupt()
        return {"decline": "", "cancel": "cancel", "wrong-token": "apply wrong"}[action]

    result = asyncio.run(workflow.run_fixture_demo(read=read, emit=output.append, parent=tmp_path))
    assert len(prompts) == 1 and fixed_check == []
    assert result["status"] == "completed" and result["exit_code"] == 0
    assert result["application"]["status"] == (
        "declined" if action in {"decline", "wrong-token"} else "cancelled"
    )
    assert result["verification"] is result["restoration"] is None
    assert result["verification_status"] == result["runtime_verification_status"] == "not-run"
    workspace = Path(result["workspace"])
    assert (
        workspace.parent == tmp_path and workspace.joinpath("main.py").read_text() == FIXTURE_SOURCE
    )
    assert workspace.joinpath("record.json").is_file()
    assert result["live_provider_calls"] == 0
    assert result["simulated_draft"] is True and result["decisions_authenticated"] is False
    assert result["original_checkout_modified"] is False
    assert all(value.isascii() for value in output)


@posix_only
@pytest.mark.parametrize(
    "action", ["approve", "skip-verify", "cancel-verify", "wrong-verify", "keep"]
)
def test_apply_verify_and_restore_are_independent_choices(tmp_path, fixed_check, action):
    output = []
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        if "'apply " in prompt:
            assert fixed_check == []
        elif "'verify " in prompt:
            assert fixed_check == []  # Applying is not permission to start a checker.
            preview = records(output)[-1]
            assert preview["kind"] == "fixture-configuration-verification-plan"
            assert exact_choice(prompt) == f"verify {preview['plan_id']}"
            assert preview["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
            assert preview["worker_sha256"] == fixture_check.WORKER_SHA256
            if action == "skip-verify":
                return ""
            if action == "cancel-verify":
                raise EOFError()
            if action == "wrong-verify":
                return exact_choice(prompts[0])
        else:
            assert "'restore " in prompt
            if action == "keep":
                return ""
        return exact_choice(prompt)

    result = asyncio.run(workflow.run_fixture_demo(read=read, emit=output.append, parent=tmp_path))
    assert [exact_choice(prompt).split()[0] for prompt in prompts] == ["apply", "verify", "restore"]
    assert result["status"] == "completed" and result["exit_code"] == 0
    checked = action in {"approve", "keep"}
    assert len(fixed_check) == int(checked)
    assert result["verification_status"] == ("passed" if checked else "not-run")
    assert result["runtime_verification_status"] == "not-run"
    assert result["verification_scope"] == "source-configuration"
    workspace = Path(result["workspace"])
    expected = FIXTURE_AFTER if action == "keep" else FIXTURE_SOURCE
    assert workspace.joinpath("main.py").read_text() == expected
    record = json.loads(workspace.joinpath("record.json").read_text())
    assert record["applied"] is True
    assert record["restored"] is (action != "keep")
    assert record["verification_status"] == result["verification_status"]
    assert record["runtime_verification_status"] == "not-run"


@posix_only
@pytest.mark.parametrize("phase", ["apply", "verify", "restore"])
def test_later_copy_edits_are_retained_without_overwrite(tmp_path, fixed_check, phase):
    output = []

    def read(prompt):
        if f"'{phase} " in prompt:
            preview = next(value for value in records(output) if "changes" in value)
            Path(preview["workspace"]).joinpath("main.py").write_text("# later user edit\n")
        return exact_choice(prompt)

    result = asyncio.run(workflow.run_fixture_demo(read=read, emit=output.append, parent=tmp_path))
    assert result["exit_code"] == 1
    assert Path(result["workspace"]).joinpath("main.py").read_text() == "# later user edit\n"
    assert len(fixed_check) == int(phase == "restore")
    assert result["runtime_verification_status"] == "not-run"
    if phase != "apply":
        assert result["restoration"]["restored"] is False


@posix_only
def test_verification_failure_is_redacted_and_still_offers_independent_restore(
    tmp_path, monkeypatch
):
    async def fail(source):
        assert source == FIXTURE_AFTER.encode()
        raise OSError("PRIVATE-DEMO-ERROR")

    monkeypatch.setattr(fixture_check, "run_configuration_check", fail)
    output = []
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        return exact_choice(prompt)

    result = asyncio.run(workflow.run_fixture_demo(read=read, emit=output.append, parent=tmp_path))
    assert result["status"] == "verification-failed" and result["exit_code"] == 1
    assert result["verification_status"] == "failed"
    assert result["restoration"]["restored"] is True
    assert "'restore " in prompts[-1]
    assert "PRIVATE-DEMO-ERROR" not in json.dumps(result) + "".join(output)


@posix_only
def test_cancellation_during_fixed_check_keeps_record_and_does_not_auto_restore(
    tmp_path, monkeypatch
):
    started = asyncio.Event()
    stopped = []

    async def wait(source):
        assert source == FIXTURE_AFTER.encode()
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(True)

    monkeypatch.setattr(fixture_check, "run_configuration_check", wait)

    async def run():
        task = asyncio.create_task(
            workflow.run_fixture_demo(read=exact_choice, emit=lambda _: None, parent=tmp_path)
        )
        async with asyncio.timeout(2):
            await started.wait()
        task.cancel()
        return await task

    result = asyncio.run(run())
    assert stopped == [True]
    assert result["status"] == "cancelled" and result["exit_code"] == 130
    assert "verification_status" not in result
    assert result["runtime_verification_status"] == "not-run"
    assert result["restoration"] is None
    workspace = Path(result["workspace"])
    assert workspace.joinpath("main.py").read_text() == FIXTURE_AFTER
    record = json.loads(workspace.joinpath("record.json").read_text())
    assert record["applied"] is True and record["restored"] is False
    assert record["verification_status"] == "failed"


@posix_only
def test_setup_failure_is_sanitized_without_false_verification_or_workspace(tmp_path, monkeypatch):
    def fail():
        raise RuntimeError("PRIVATE-DEMO-ERROR")

    monkeypatch.setattr(workflow, "build_demo_proposal", fail)
    output = []
    result = asyncio.run(workflow.run_fixture_demo(emit=output.append, parent=tmp_path))
    assert result["status"] == "workflow-failed" and result["exit_code"] == 1
    assert result["workspace"] is None and list(tmp_path.iterdir()) == []
    assert "verification_status" not in result
    assert "PRIVATE-DEMO-ERROR" not in json.dumps(result) + "".join(output)


@pytest.mark.parametrize("exit_code", [0, 1, 2, 130])
def test_cli_prints_summary_and_preserves_runner_exit_code(monkeypatch, exit_code):
    async def result(**kwargs):
        assert set(kwargs) <= {"emit", "read"}
        kwargs["emit"](
            json.dumps({"kind": "test-preview", "runtime_verification_status": "not-run"})
        )
        return {"exit_code": exit_code, "runtime_verification_status": "not-run"}

    monkeypatch.setattr(workflow, "run_fixture_demo", result)
    cli = runner.invoke(app, ["fixture-demo"])
    assert cli.exit_code == exit_code
    values = json_stream(cli.stdout)
    assert values[0]["kind"] == "test-preview" and values[-1]["exit_code"] == exit_code


@pytest.mark.parametrize("failure,expected", [(KeyboardInterrupt, 130), (RuntimeError, 1)])
def test_cli_unhandled_failures_are_sanitized_and_not_success(monkeypatch, failure, expected):
    async def fail(**kwargs):
        raise failure("PRIVATE-DEMO-ERROR")

    monkeypatch.setattr(workflow, "run_fixture_demo", fail)
    cli = runner.invoke(app, ["fixture-demo"])
    assert cli.exit_code == expected
    result = json.loads(cli.stdout)
    assert "verification_status" not in result
    assert result["runtime_verification_status"] == "not-run"
    assert "PRIVATE-DEMO-ERROR" not in cli.stdout


@posix_only
def test_cli_outside_checkout_uses_no_development_imports_and_leaves_cwd_alone(
    tmp_path, monkeypatch
):
    outside = tmp_path / "outside"
    workspaces = tmp_path / "workspaces"
    outside.mkdir()
    workspaces.mkdir()
    outside.joinpath("main.py").write_text("# unrelated working directory source\n")
    monkeypatch.chdir(outside)
    original_run = workflow.run_fixture_demo
    original_import = builtins.__import__

    def packaged_only(name, *args, **kwargs):
        if name.split(".")[0] in {"scripts", "tests"}:
            pytest.fail("Installed product path must not import development code")
        return original_import(name, *args, **kwargs)

    async def isolated(**kwargs):
        return await original_run(read=lambda _: "", emit=kwargs["emit"], parent=workspaces)

    monkeypatch.setattr(builtins, "__import__", packaged_only)
    monkeypatch.setattr(workflow, "run_fixture_demo", isolated)
    cli = runner.invoke(app, ["fixture-demo"])
    assert cli.exit_code == 0
    result = json_stream(cli.stdout)[-1]
    assert result["application"]["status"] == "declined"
    assert result["live_provider_calls"] == 0 and result["runtime_verification_status"] == "not-run"
    assert Path(result["workspace"]).parent == workspaces
    assert list(outside.iterdir()) == [outside / "main.py"]
    assert outside.joinpath("main.py").read_text() == "# unrelated working directory source\n"
