"""Cross-entry I/O bookkeeping regressions using simulated approvals and drafts only."""

import asyncio
import errno
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import demo_verify
from typer.testing import CliRunner

from authzest import cli
from authzest.codex.contracts import canonical, decode
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE, validate_fixture_draft
from authzest.codex.mock import scripted_response
from authzest.runner import _fixture_workspace as io
from authzest.runner import codex_fixture, fixture_check, fixture_runtime
from authzest.runner.fixture_apply import FixtureApplySession

pytestmark = pytest.mark.skipif(not io.supported(), reason="POSIX owned fixture workflow")
ENTRIES = ("codex-source", "codex-runtime", "demo-runtime")
PRIVATE_ERROR = "/private/not-for-output/workflow-error"
MODEL = "fixture-failure-test-model"
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Failure bookkeeping tests must not execute checks, providers or source")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(fixture_check, "run_configuration_check", forbidden)
    monkeypatch.setattr(fixture_runtime, "run_runtime_check", forbidden)


def exact(prompt):
    """A test-authored simulated terminal choice, not authenticated human consent."""
    return prompt.split("'")[1]


@pytest.fixture
def call_workflow():
    drafts = []

    class FakeAdapter:
        async def draft(self, request):
            drafts.append(request.request_id)
            raw = {
                "answers": decode(scripted_response(request, {"review": None}))["answers"],
                "after_text": FIXTURE_AFTER,
                "reason": "Test-authored offline draft; no provider request was made.",
                "uncertainties": ["Not an executed or verified fix."],
                "side_effects": ["Debug diagnostics would be disabled."],
            }
            return validate_fixture_draft(canonical(raw), request, usage=None)

    async def call(entry, parent, *, read=exact, emit=lambda _: None):
        if entry == "demo-runtime":
            return await demo_verify.run_demo(
                runtime_check=True, read=read, emit=emit, parent=parent
            )
        return await codex_fixture.run_codex_fixture(
            MODEL,
            runtime_check=entry == "codex-runtime",
            read=read,
            emit=emit,
            parent=parent,
            adapter_factory=lambda **kw: FakeAdapter(),
        )

    return call, drafts


def journal(result):
    return json.loads(Path(result["workspace"]).joinpath("record.json").read_text())


def assert_not_checked(result, entry):
    scope = "source-configuration" if entry == "codex-source" else "owned-fixture-runtime"
    assert result["verification_scope"] == scope
    assert result["verification_status"] == result["runtime_verification_status"] == "not-run"
    verification = result["verification"]
    assert verification["status"] == verification["runtime_verification_status"] == "not-run"
    assert verification["verification_scope"] == scope
    assert verification["execution_attempted"] is False
    assert verification["elapsed_ms"] is verification["exit_code"] is None
    if entry != "codex-source":
        assert verification["runtime_evidence"] is None


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("stage", ["verification_preview", "decide_verification"])
@pytest.mark.parametrize("restoration", ["approve", "decline", "edit"])
def test_preparation_failure_is_not_run_with_separate_restoration(
    tmp_path, monkeypatch, call_workflow, entry, stage, restoration
):
    call, drafts = call_workflow
    output, prompts = [], []

    def fail(*args, **kwargs):
        raise OSError(PRIVATE_ERROR)

    monkeypatch.setattr(FixtureApplySession, stage, fail)

    def read(prompt):
        prompts.append(prompt)
        if "'restore " in prompt:
            preview = json.loads(output[-1])
            assert (
                preview["verification_status"]
                == preview["runtime_verification_status"]
                == "not-run"
            )
            if restoration == "decline":
                return ""
            if restoration == "edit":
                Path(preview["workspace"]).joinpath("main.py").write_text("# later local edit\n")
        return exact(prompt)

    result = asyncio.run(call(entry, tmp_path, read=read, emit=output.append))
    assert result["exit_code"] == 1
    assert_not_checked(result, entry)
    assert result["verification"]["reason"] == "verification-setup-failed"
    assert result["verification"]["journal_status"] == "recorded"
    assert "'restore " in prompts[-1]
    assert result["restoration"]["verification_status"] == "not-run"
    assert result["restoration"]["runtime_verification_status"] == "not-run"
    assert result["restoration"]["restored"] is (restoration == "approve")
    record = journal(result)
    assert record["verification"] == result["verification"]
    assert record["verification_status"] == record["runtime_verification_status"] == "not-run"
    assert record["verification_decision_consumed"] is True
    expected = {"approve": FIXTURE_SOURCE, "decline": FIXTURE_AFTER, "edit": "# later local edit\n"}
    assert Path(result["workspace"]).joinpath("main.py").read_text() == expected[restoration]
    assert len(drafts) == (0 if entry == "demo-runtime" else 1)
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("committed", [False, True])
def test_decision_journal_failure_reports_unconfirmed_or_recovered_not_run(
    tmp_path, monkeypatch, call_workflow, entry, persistent, committed
):
    call, _ = call_workflow
    write = io.FixtureWorkspace.write_record
    failures = []

    def faulty_write(self, data):
        payload = json.loads(data)
        event = payload["events"][-1]["event"]
        failed = event == "verification-decision-recorded" or (persistent and bool(failures))
        if committed or not failed:
            write(self, data)
        if failed:
            failures.append(event)
            raise OSError(PRIVATE_ERROR)

    monkeypatch.setattr(io.FixtureWorkspace, "write_record", faulty_write)
    output, prompts = [], []

    def read(prompt):
        prompts.append(prompt)
        return exact(prompt)

    result = asyncio.run(call(entry, tmp_path, read=read, emit=output.append))
    assert failures and result["exit_code"] == 1
    assert_not_checked(result, entry)
    verification = result["verification"]
    assert verification["reason"] == (
        "journal-unavailable" if persistent else "verification-setup-failed"
    )
    assert verification["journal_status"] == ("unconfirmed" if persistent else "recorded")
    assert "'restore " in prompts[-1]
    assert result["restoration"]["verification_status"] == "not-run"
    assert result["restoration"]["runtime_verification_status"] == "not-run"
    record = journal(result)
    assert record["verification_status"] == record["runtime_verification_status"] == "not-run"
    if committed or not persistent:
        assert record["verification"] == verification
    else:
        assert record["verification"] is None  # Last durable applied record is explicitly stale.
    if persistent:
        assert "record may be stale" in result["detail"]
    expected = FIXTURE_AFTER if persistent else FIXTURE_SOURCE
    assert Path(result["workspace"]).joinpath("main.py").read_text() == expected
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


@pytest.mark.parametrize("entry", ENTRIES)
def test_escaped_verify_error_preserves_copy_without_invented_result_or_restore(
    tmp_path, monkeypatch, call_workflow, entry
):
    call, _ = call_workflow
    output, prompts = [], []

    async def fail(self):
        raise RuntimeError(PRIVATE_ERROR)

    monkeypatch.setattr(FixtureApplySession, "verify", fail)

    def read(prompt):
        prompts.append(prompt)
        return exact(prompt)

    result = asyncio.run(call(entry, tmp_path, read=read, emit=output.append))
    assert result["status"] == "workflow-failed" and result["exit_code"] == 1
    assert result["verification"] is result["restoration"] is None
    assert "verification_status" not in result
    if entry != "codex-source":
        assert "runtime_verification_status" not in result
    assert not any("'restore " in prompt for prompt in prompts)
    assert Path(result["workspace"]).joinpath("main.py").read_text() == FIXTURE_AFTER
    assert journal(result)["applied"] is True and journal(result)["restored"] is False
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("stage", ["read-initial-source", "write-initial-record"])
@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt, asyncio.CancelledError])
def test_initialization_failure_retains_path_stage_and_fd_cleanup(
    tmp_path, monkeypatch, call_workflow, entry, stage, failure
):
    call, _ = call_workflow
    close = io.FixtureWorkspace.close
    closed = []
    output = []

    def fail(*args, **kwargs):
        raise failure(PRIVATE_ERROR)

    def observe(self):
        fd = self._fd
        close(self)
        closed.append((self, fd))

    monkeypatch.setattr(io.FixtureWorkspace, "close", observe)
    monkeypatch.setattr(
        io.FixtureWorkspace, "read_main" if stage == "read-initial-source" else "write_record", fail
    )
    if entry.startswith("codex") and failure is not OSError:
        with pytest.raises(failure) as interrupted:
            asyncio.run(call(entry, tmp_path, emit=output.append))
        metadata = interrupted.value.workspace_initialization
        assert isinstance(metadata, io.WorkspaceInitializationError)
        retained = metadata.created_path
        assert metadata.initialization_stage == stage
        assert PRIVATE_ERROR not in str(metadata)
    else:
        result = asyncio.run(call(entry, tmp_path, emit=output.append))
        assert result["status"] == ("workflow-failed" if failure is OSError else "cancelled")
        assert result["exit_code"] == (1 if failure is OSError else 130)
        assert result["initialization_stage"] == stage
        assert result["runtime_verification_status"] == "not-run"
        assert "verification_status" not in result
        assert result["application"] is result["verification"] is result["restoration"] is None
        assert PRIVATE_ERROR not in json.dumps(result)
        retained = Path(result["workspace"])
    assert len(closed) == 1 and closed[0][0]._fd == -1
    with pytest.raises(OSError) as closed_error:
        os.fstat(closed[0][1])
    assert closed_error.value.errno == errno.EBADF
    assert retained.parent == tmp_path and retained == closed[0][0].path
    assert retained.joinpath("main.py").read_text() == FIXTURE_SOURCE
    assert retained.joinpath("before.txt").read_text() == FIXTURE_SOURCE
    assert retained.joinpath("after.txt").read_text() == FIXTURE_AFTER
    assert not retained.joinpath("record.json").exists()
    assert PRIVATE_ERROR not in "".join(output)


@pytest.mark.parametrize("entry", ENTRIES)
def test_failure_before_directory_creation_does_not_invent_retained_path(
    tmp_path, monkeypatch, call_workflow, entry
):
    call, _ = call_workflow
    mkdtemp = io.tempfile.mkdtemp

    def fail(*args, **kwargs):
        if kwargs.get("prefix") == "authzest-fixture-":
            raise OSError(PRIVATE_ERROR)
        return mkdtemp(*args, **kwargs)

    monkeypatch.setattr(io.tempfile, "mkdtemp", fail)
    result = asyncio.run(call(entry, tmp_path))
    assert result["exit_code"] == 1
    assert result["workspace"] is None and "initialization_stage" not in result
    assert result["application"] is None and list(tmp_path.iterdir()) == []
    assert PRIVATE_ERROR not in json.dumps(result)


@pytest.mark.parametrize("runtime_check", [False, True])
@pytest.mark.parametrize("initialization", [False, True])
@pytest.mark.parametrize("converted", [False, True])
def test_cli_preserves_recovery_metadata_when_asyncio_replaces_cancellation(
    tmp_path, monkeypatch, runtime_check, initialization, converted
):
    retained = tmp_path / "retained-workspace"
    retained.mkdir()
    retained.joinpath("main.py").write_text(FIXTURE_SOURCE)

    async def interrupted(*args, **kwargs):
        failure = asyncio.CancelledError(PRIVATE_ERROR)
        if initialization:
            failure.workspace_initialization = io.WorkspaceInitializationError(
                retained, "write-initial-record"
            )
        else:
            failure.fixture_workspace = retained
        raise failure

    monkeypatch.setattr(codex_fixture, "run_codex_fixture", interrupted)
    if converted:
        actual_run = asyncio.run

        def converting_run(coroutine):
            try:
                return actual_run(coroutine)
            except asyncio.CancelledError:
                # Simulates asyncio.run's signal conversion without sending a real signal.
                raise KeyboardInterrupt() from None

        monkeypatch.setattr(cli.asyncio, "run", converting_run)
    args = ["codex-fixture", "--model", MODEL] + (["--runtime-check"] if runtime_check else [])
    command = runner.invoke(cli.app, args)
    assert command.exit_code == 130
    summary = json.loads(command.stdout)
    assert summary["status"] == "cancelled" and summary["workspace"] == str(retained)
    assert "verification_status" not in summary
    if initialization:
        assert summary["initialization_stage"] == "write-initial-record"
        assert summary["runtime_verification_status"] == "not-run"
    elif runtime_check:
        assert "runtime_verification_status" not in summary
    assert retained.joinpath("main.py").read_text() == FIXTURE_SOURCE
    assert PRIVATE_ERROR not in command.output
