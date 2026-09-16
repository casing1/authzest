"""Ordinary I/O failure regressions; no provider, checker or fixture execution."""

import asyncio
import errno
import json
import os
import socket
import stat
import subprocess
from pathlib import Path

import pytest

from authzest.codex.fixture_demo import build_demo_proposal
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import _fixture_workspace as io
from authzest.runner import fixture_check
from authzest.runner import fixture_demo as workflow
from authzest.runner.fixture_apply import FixtureApplySession

pytestmark = pytest.mark.skipif(not io.supported(), reason="POSIX private fixture workflow")
PRIVATE_ERROR = "/private/do-not-disclose/initialization-error"


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Failure bookkeeping must not execute any checker, source or provider")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(fixture_check, "run_configuration_check", forbidden)


@pytest.fixture
def owned(tmp_path):
    request, review, proposal = build_demo_proposal()
    session = FixtureApplySession(proposal, request, review, parent=tmp_path)
    yield session
    session.close()


def approve_apply(session):
    session.decide("approve")
    assert session.apply().status == "applied"


def journal(workspace):
    return json.loads(Path(workspace).joinpath("record.json").read_text())


def exact_choice(prompt):
    """A test-owned simulated response, not a human consent attestation."""
    return prompt.split("'")[1]


def assert_no_execution_claim(result):
    assert result["verification_status"] == "not-run"
    verification = result["verification"]
    assert verification["status"] == "not-run"
    assert verification["execution_attempted"] is False
    assert verification["elapsed_ms"] is verification["exit_code"] is None
    assert result["runtime_verification_status"] == "not-run"


@pytest.mark.parametrize("failure", ["preview", "decision", "decision-journal"])
@pytest.mark.parametrize("restoration", ["approve", "decline", "edit"])
def test_setup_failure_records_not_run_and_keeps_restoration_separate(
    tmp_path, monkeypatch, failure, restoration
):
    output, prompts = [], []

    def fail(*args, **kwargs):
        raise OSError(PRIVATE_ERROR)

    if failure == "preview":
        monkeypatch.setattr(FixtureApplySession, "verification_preview", fail)
    elif failure == "decision":
        monkeypatch.setattr(FixtureApplySession, "decide_verification", fail)
    else:
        write = io.FixtureWorkspace.write_record

        def fail_decision(self, data):
            if json.loads(data)["events"][-1]["event"] == "verification-decision-recorded":
                raise OSError(PRIVATE_ERROR)
            write(self, data)

        monkeypatch.setattr(io.FixtureWorkspace, "write_record", fail_decision)

    def read(prompt):
        prompts.append(prompt)
        if "'restore " in prompt:
            values = [json.loads(item) for item in output]
            verification = next(item for item in values if "execution_attempted" in item)
            assert verification["status"] == "not-run"
            assert values[-1]["verification_status"] == "not-run"
            if restoration == "decline":
                return ""
            if restoration == "edit":
                Path(values[-1]["workspace"]).joinpath("main.py").write_text("# later edit\n")
        return exact_choice(prompt)

    result = asyncio.run(workflow.run_fixture_demo(read=read, emit=output.append, parent=tmp_path))
    assert result["exit_code"] == 1
    assert_no_execution_claim(result)
    assert result["verification"]["reason"] == "verification-setup-failed"
    assert result["verification"]["journal_status"] == "recorded"
    assert "'restore " in prompts[-1]
    assert len(prompts) == (2 if failure == "preview" else 3)
    assert result["restoration"]["verification_status"] == "not-run"
    record = journal(result["workspace"])
    assert record["verification"] == result["verification"]
    assert record["verification_status"] == "not-run"
    assert record["verification_decision_consumed"] is True
    expected = {"approve": FIXTURE_SOURCE, "decline": FIXTURE_AFTER, "edit": "# later edit\n"}
    assert Path(result["workspace"]).joinpath("main.py").read_text() == expected[restoration]
    assert result["restoration"]["restored"] is (restoration == "approve")
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("committed", [False, True])
def test_setup_journal_failure_is_unconfirmed_without_claiming_a_check(
    tmp_path, monkeypatch, persistent, committed
):
    write = io.FixtureWorkspace.write_record
    failures = []

    def fail_preview(self):
        raise OSError(PRIVATE_ERROR)

    def faulty_write(self, data):
        payload = json.loads(data)
        failed = payload["verification"] is not None and (persistent or not failures)
        if committed or not failed:
            write(self, data)
        if failed:
            failures.append(payload)
            raise OSError(PRIVATE_ERROR)

    monkeypatch.setattr(FixtureApplySession, "verification_preview", fail_preview)
    monkeypatch.setattr(io.FixtureWorkspace, "write_record", faulty_write)
    output = []
    result = asyncio.run(
        workflow.run_fixture_demo(read=exact_choice, emit=output.append, parent=tmp_path)
    )
    assert failures and result["exit_code"] == 1
    assert_no_execution_claim(result)
    assert result["verification"]["reason"] == "journal-unavailable"
    assert result["verification"]["journal_status"] == "unconfirmed"
    assert "record may be stale" in result["detail"]
    assert result["restoration"]["verification_status"] == "not-run"
    record = journal(result["workspace"])
    assert record["verification_status"] == "not-run"
    if committed or not persistent:
        assert record["verification"] == result["verification"]
    else:
        # Every later write failed before replacement: the last durable record is only applied.
        assert record["verification"] is None
        assert record["phase"] == "applied"
    expected = FIXTURE_AFTER if persistent else FIXTURE_SOURCE
    assert Path(result["workspace"]).joinpath("main.py").read_text() == expected
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


def test_setup_failure_helper_consumes_attempt_and_returns_detached_history(owned):
    approve_apply(owned)
    first = owned.fail_verification_setup()
    assert first["status"] == "not-run" and first["execution_attempted"] is False
    first["status"] = "passed"
    assert owned.fail_verification_setup()["status"] == "not-run"
    assert asyncio.run(owned.verify())["reason"] == "decision-consumed"
    with pytest.raises(io.WorkspaceError):
        owned.verification_preview()
    assert owned.restore("approve").verification_status == "not-run"
    assert owned.fail_verification_setup() == journal(owned.workspace)["verification"]


@pytest.mark.parametrize("state", ["prepared", "consumed", "running"])
def test_setup_failure_helper_rejects_impossible_lifecycle_without_writing(owned, state):
    if state != "prepared":
        approve_apply(owned)
    before = owned.workspace.joinpath("record.json").read_bytes()
    if state == "consumed":
        owned._verification_used = True
    elif state == "running":
        owned._verification_running = True
    with pytest.raises(io.WorkspaceError):
        owned.fail_verification_setup()
    assert owned.workspace.joinpath("record.json").read_bytes() == before


def test_setup_failure_helper_does_not_replace_existing_outcome(owned):
    approve_apply(owned)
    plan = owned.verification_preview()
    owned.decide_verification("decline", plan["plan_id"])
    previous = asyncio.run(owned.verify())
    before = owned.workspace.joinpath("record.json").read_bytes()
    assert previous["reason"] == "declined"
    assert owned.fail_verification_setup() == previous
    assert owned.workspace.joinpath("record.json").read_bytes() == before


def test_unexpected_verify_exception_is_not_reclassified_as_known_setup_failure(
    tmp_path, monkeypatch
):
    async def fail(self):
        raise RuntimeError(PRIVATE_ERROR)

    monkeypatch.setattr(FixtureApplySession, "verify", fail)
    prompts, output = [], []

    def read(prompt):
        prompts.append(prompt)
        return exact_choice(prompt)

    result = asyncio.run(workflow.run_fixture_demo(read=read, emit=output.append, parent=tmp_path))
    assert result["status"] == "workflow-failed" and result["exit_code"] == 1
    assert "verification_status" not in result
    assert result["verification"] is result["restoration"] is None
    assert not any("'restore " in prompt for prompt in prompts)
    assert Path(result["workspace"]).joinpath("main.py").read_text() == FIXTURE_AFTER
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


@pytest.fixture
def closed_workspaces(monkeypatch):
    closed = []
    close = io.FixtureWorkspace.close

    def observe(self):
        fd = self._fd
        close(self)
        closed.append((self, fd))

    monkeypatch.setattr(io.FixtureWorkspace, "close", observe)
    return closed


def assert_closed(closed):
    assert len(closed) == 1
    workspace, fd = closed[0]
    assert workspace._fd == -1
    if fd >= 0:
        with pytest.raises(OSError) as failure:
            os.fstat(fd)
        assert failure.value.errno == errno.EBADF


@pytest.mark.parametrize("stage", ["read-initial-source", "write-initial-record"])
@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt, asyncio.CancelledError])
def test_session_initialization_reports_retained_path_stage_and_closes_fd(
    tmp_path, monkeypatch, closed_workspaces, stage, failure
):
    def fail(*args, **kwargs):
        raise failure(PRIVATE_ERROR)

    method = "read_main" if stage == "read-initial-source" else "write_record"
    monkeypatch.setattr(io.FixtureWorkspace, method, fail)
    output = []
    result = asyncio.run(workflow.run_fixture_demo(emit=output.append, parent=tmp_path))
    assert_closed(closed_workspaces)
    assert result["exit_code"] == (1 if failure is OSError else 130)
    assert result["status"] == ("workflow-failed" if failure is OSError else "cancelled")
    assert result["initialization_stage"] == stage
    retained = Path(result["workspace"])
    assert retained == closed_workspaces[0][0].path and retained.parent == tmp_path
    assert stat.S_IMODE(retained.stat().st_mode) == 0o700
    assert retained.joinpath("main.py").read_text() == FIXTURE_SOURCE
    assert retained.joinpath("before.txt").read_text() == FIXTURE_SOURCE
    assert retained.joinpath("after.txt").read_text() == FIXTURE_AFTER
    assert not retained.joinpath("record.json").exists()
    assert "verification_status" not in result
    assert result["application"] is result["verification"] is result["restoration"] is None
    assert "record may be absent" in result["detail"]
    assert PRIVATE_ERROR not in json.dumps(result) + "".join(output)


@pytest.mark.parametrize("stage", ["open-directory", "inspect-directory", "create-before"])
def test_workspace_constructor_failure_returns_actual_partial_directory(
    tmp_path, monkeypatch, closed_workspaces, stage
):
    if stage == "open-directory":
        original_open = os.open

        def fail_open(path, flags, *args, **kwargs):
            if flags & os.O_DIRECTORY and Path(path).name.startswith("authzest-fixture-"):
                raise OSError(PRIVATE_ERROR)
            return original_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(os, "open", fail_open)
    elif stage == "inspect-directory":
        original_open, original_fstat = os.open, os.fstat
        opened = []

        def track_open(path, flags, *args, **kwargs):
            fd = original_open(path, flags, *args, **kwargs)
            if flags & os.O_DIRECTORY and Path(path).name.startswith("authzest-fixture-"):
                opened.append(fd)
            return fd

        def fail_fstat(fd):
            if opened and fd == opened.pop():
                raise OSError(PRIVATE_ERROR)
            return original_fstat(fd)

        monkeypatch.setattr(os, "open", track_open)
        monkeypatch.setattr(os, "fstat", fail_fstat)
    else:
        create = io.FixtureWorkspace._create

        def fail_create(self, name, data):
            if name == "before.txt":
                raise OSError(PRIVATE_ERROR)
            return create(self, name, data)

        monkeypatch.setattr(io.FixtureWorkspace, "_create", fail_create)
    result = asyncio.run(workflow.run_fixture_demo(emit=lambda _: None, parent=tmp_path))
    assert_closed(closed_workspaces)
    assert result["status"] == "workflow-failed" and result["exit_code"] == 1
    assert result["initialization_stage"] == stage
    retained = Path(result["workspace"])
    assert retained.is_dir() and retained.parent == tmp_path
    assert set(path.name for path in retained.iterdir()) == (
        {"main.py"} if stage == "create-before" else set()
    )
    if stage == "create-before":
        assert retained.joinpath("main.py").read_text() == FIXTURE_SOURCE
    assert PRIVATE_ERROR not in json.dumps(result)


def test_before_directory_creation_failure_does_not_invent_a_recovery_path(tmp_path, monkeypatch):
    mkdtemp = io.tempfile.mkdtemp

    def fail(*args, **kwargs):
        if kwargs.get("prefix") == "authzest-fixture-":
            raise OSError(PRIVATE_ERROR)
        return mkdtemp(*args, **kwargs)

    monkeypatch.setattr(io.tempfile, "mkdtemp", fail)
    result = asyncio.run(workflow.run_fixture_demo(emit=lambda _: None, parent=tmp_path))
    assert result["status"] == "workflow-failed" and result["exit_code"] == 1
    assert result["workspace"] is None and "initialization_stage" not in result
    assert list(tmp_path.iterdir()) == []
    assert PRIVATE_ERROR not in json.dumps(result)


def test_initialization_exception_has_fixed_message_and_structured_metadata(tmp_path, monkeypatch):
    def fail(self, data):
        raise OSError(PRIVATE_ERROR)

    request, review, proposal = build_demo_proposal()
    monkeypatch.setattr(io.FixtureWorkspace, "write_record", fail)
    with pytest.raises(io.WorkspaceInitializationError) as error:
        FixtureApplySession(proposal, request, review, parent=tmp_path)
    assert error.value.created_path.is_dir()
    assert error.value.initialization_stage == "write-initial-record"
    assert (
        str(error.value)
        == "Fixture workspace initialization failed; inspect the retained directory."
    )
    assert PRIVATE_ERROR not in str(error.value)
    with pytest.raises(ValueError):
        io.WorkspaceInitializationError(tmp_path, PRIVATE_ERROR)
