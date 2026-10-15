"""Mocked host transport only: no worker/template, policy, process or filesystem runs."""

import asyncio
import builtins
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import canonical, identity
from authzest.runner import owner_policy_check as check


@pytest.fixture(autouse=True)
def forbid_real_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Transport tests must use fake memory-only process/filesystem objects")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(check, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(check, "os", SimpleNamespace(name="posix", killpg=forbidden))


class Writer:
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def write(self, raw):
        self.data.extend(raw)

    async def drain(self):
        return None

    def close(self):
        self.closed = True


class Reader:
    def __init__(self, raw=b"{}"):
        self.raw = raw
        self.offset = 0
        self.limits = []

    async def read(self, limit):
        self.limits.append(limit)
        chunk = self.raw[self.offset : self.offset + limit]
        self.offset += len(chunk)
        return chunk


class Process:
    pid = 12345  # Test-owned identifier, never sent to a real operating-system call.

    def __init__(self, raw=b"{}", exit_code=0):
        self.stdin = Writer()
        self.stdout = Reader(raw)
        self.returncode = None
        self.exit_code = exit_code
        self.waits = 0

    async def wait(self):
        self.waits += 1
        if self.returncode is None:
            self.returncode = self.exit_code
        return self.returncode


class Directory:
    def __init__(self, value):
        self.value = value

    def resolve(self):
        return self

    def __str__(self):
        return self.value


def fake_workspace(monkeypatch):
    events = []

    class Temporary:
        def __init__(self, *, prefix):
            events.append(("create", prefix))

        def __enter__(self):
            events.append(("enter",))
            return "/mock/private-owner-workspace"

        def __exit__(self, *args):
            events.append(("removed",))

    monkeypatch.setattr(check, "TemporaryDirectory", Temporary)
    monkeypatch.setattr(check, "Path", Directory)
    return events


def plan():
    # Only mock transport serialization is tested; this is not an approved plan.
    cases = [{"id": "mock-case", "case_sha256": "0" * 64, "principal": None, "report": None}]
    wire = {
        "schema_version": "1.0",
        "check_id": check.CHECK_ID,
        "plan_id": "owner-policy-check-" + "0" * 64,
        "policy_source_sha256": check.POLICY_SHA256,
        "worker_sha256": check.WORKER_SHA256,
        "input_sha256": identity(cases),
        "cases": cases,
    }
    return check.OwnerPolicyCheckPlan(canonical({"worker_input": wire}))


@pytest.mark.parametrize("length", [0, 1, 1024, 16 * 1024])
def test_exchange_reads_at_most_output_budget_plus_one_byte(length):
    process = Process(b"x" * length)
    output = asyncio.run(check._exchange(process, b"mock-input"))
    assert output == b"x" * length
    assert process.stdin.data == b"mock-input" and process.stdin.closed
    assert all(1 <= size <= 1024 for size in process.stdout.limits)
    assert process.stdout.offset <= check.MAX_OUTPUT_BYTES


@pytest.mark.parametrize("length", [16 * 1024 + 1, 64 * 1024])
def test_exchange_rejects_over_budget_stream_without_reading_its_tail(length):
    process = Process(b"x" * length)
    with pytest.raises(check._OutputLimitError):
        asyncio.run(check._exchange(process, b"mock-input"))
    assert process.stdout.offset == check.MAX_OUTPUT_BYTES + 1
    assert process.stdout.limits[-1] == 1


@pytest.mark.parametrize(
    "raw",
    ["not-bytes", bytearray(b"{}"), b"x" * (256 * 1024 + 1)],
    ids=["text", "bytearray", "oversize"],
)
def test_exchange_invalid_input_rejected_before_writing(raw):
    process = Process()
    with pytest.raises(ValueError):
        asyncio.run(check._exchange(process, raw))
    assert not process.stdin.data and not process.stdin.closed and not process.stdout.limits


def test_stop_uses_only_mock_process_group_and_bounded_wait(monkeypatch):
    calls = []
    process = Process()
    monkeypatch.setattr(
        check, "os", SimpleNamespace(killpg=lambda pid, sig: calls.append((pid, sig)))
    )
    asyncio.run(check._stop(process))
    assert calls == [(process.pid, check.signal.SIGKILL)] and process.waits == 1


def test_stop_still_reaps_when_mock_process_group_has_gone(monkeypatch):
    process = Process()

    def gone(*args):
        raise ProcessLookupError

    monkeypatch.setattr(check, "os", SimpleNamespace(killpg=gone))
    asyncio.run(check._stop(process))
    assert process.waits == 1


def test_stop_wait_is_bounded(monkeypatch):
    async def waiting():
        await asyncio.Event().wait()

    process = SimpleNamespace(pid=12345, wait=waiting)
    monkeypatch.setattr(check, "os", SimpleNamespace(killpg=lambda *args: None))
    monkeypatch.setattr(check, "MAX_CLEANUP_SECONDS", 0.01)
    with pytest.raises(TimeoutError):
        asyncio.run(check._stop(process))


@pytest.mark.parametrize("error", [None, TimeoutError, OSError])
def test_cleanup_reports_completion_or_failure_without_cancel(monkeypatch, error):
    async def stop(process):
        if error is not None:
            raise error("test-owned failure")

    monkeypatch.setattr(check, "_stop", stop)
    assert asyncio.run(check._cleanup(object())) == (
        "confirmed" if error is None else "unconfirmed"
    )


@pytest.mark.parametrize("error", [None, TimeoutError, OSError])
def test_repeated_cancellation_waits_for_reaper_then_preserves_cancel(monkeypatch, error):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        completed = []

        async def stop(process):
            entered.set()
            await release.wait()
            completed.append(True)
            if error is not None:
                raise error("test-owned reaper failure")

        monkeypatch.setattr(check, "_stop", stop)
        task = asyncio.create_task(check._cleanup(object()))
        await entered.wait()
        for _ in range(5):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and not completed
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert completed == [True]

    asyncio.run(scenario())


def test_run_worker_launches_only_fixed_source_command_in_fake_private_workspace(monkeypatch):
    events = fake_workspace(monkeypatch)
    calls = []
    process = Process(b"mock-output")

    async def create(*command, **options):
        calls.append((command, options))
        return process

    async def stop(process):
        return None

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(check, "_stop", stop)
    prepared = plan()
    result = asyncio.run(check._run_worker(prepared))
    assert result.output == b"mock-output" and result.exit_code == 0
    assert result.reason is None and result.cleanup_status == "confirmed"
    command, options = calls[0]
    assert command == (check.sys.executable, "-I", "-S", "-c", check.WORKER_SOURCE)
    assert str(options["cwd"]) == "/mock/private-owner-workspace"
    assert options["start_new_session"] is True
    assert options["stderr"] == asyncio.subprocess.DEVNULL
    assert options["limit"] == check.MAX_OUTPUT_BYTES + 1
    assert set(options["env"]) == {
        "PATH",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONUTF8",
        "NO_COLOR",
        "TERM",
    }
    assert options["env"]["PATH"] == "/usr/bin:/bin"
    assert options["env"]["TMPDIR"] == "/mock/private-owner-workspace"
    assert process.stdin.data == canonical(prepared.to_dict()["worker_input"]).encode()
    assert events[-1] == ("removed",) and len(calls) == 1


def test_run_worker_launch_failure_is_not_success_or_confirmed_execution(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def failed(*args, **kwargs):
        raise OSError("test-owned launch failure")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failed)
    result = asyncio.run(check._run_worker(plan()))
    assert result.output == b"" and result.exit_code is None
    assert result.reason == "worker-process-error" and result.cleanup_status == "not-needed"
    assert events[-1] == ("removed",)


@pytest.mark.parametrize("exit_code", [0, 2])
@pytest.mark.parametrize("cleanup_error", [None, TimeoutError, OSError])
def test_run_worker_preserves_nonzero_exit_and_unconfirmed_cleanup(
    monkeypatch, exit_code, cleanup_error
):
    events = fake_workspace(monkeypatch)
    process = Process(b"mock-output", exit_code=exit_code)

    async def create(*args, **kwargs):
        return process

    async def stop(process):
        if cleanup_error is not None:
            raise cleanup_error("test-owned cleanup failure")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(check, "_stop", stop)
    result = asyncio.run(check._run_worker(plan()))
    assert result.exit_code == exit_code
    assert result.cleanup_status == ("confirmed" if cleanup_error is None else "unconfirmed")
    assert events[-1] == ("removed",)


def test_run_worker_output_limit_is_bounded_and_reaped(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process(b"x" * (check.MAX_OUTPUT_BYTES * 2))
    stopped = []

    async def create(*args, **kwargs):
        return process

    async def stop(process):
        stopped.append(True)
        process.returncode = -9

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(check, "_stop", stop)
    result = asyncio.run(check._run_worker(plan()))
    assert result.reason == "output-limit" and result.output == b""
    assert result.exit_code == -9 and result.cleanup_status == "confirmed"
    assert process.stdout.offset == check.MAX_OUTPUT_BYTES + 1
    assert stopped == [True] and events[-1] == ("removed",)


def test_run_worker_timeout_reaps_mock_process_and_removes_fake_workspace(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process()
    stopped = []

    async def read(limit):
        await asyncio.Event().wait()

    async def create(*args, **kwargs):
        process.stdout.read = read
        return process

    async def stop(process):
        stopped.append(True)
        process.returncode = -9

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(check, "_stop", stop)
    monkeypatch.setattr(check, "TIMEOUT_SECONDS", 0.01)
    result = asyncio.run(check._run_worker(plan()))
    assert result.output == b"" and result.reason == "timeout" and result.exit_code == -9
    assert result.cleanup_status == "confirmed"
    assert stopped == [True] and events[-1] == ("removed",)


@pytest.mark.parametrize("cleanup_error", [None, TimeoutError, OSError])
def test_run_worker_cancel_waits_for_repeatedly_shielded_mock_reaper(monkeypatch, cleanup_error):
    events = fake_workspace(monkeypatch)

    async def scenario():
        reading, reaping, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        completed = []
        process = Process()

        async def read(limit):
            reading.set()
            await asyncio.Event().wait()

        async def create(*args, **kwargs):
            process.stdout.read = read
            return process

        async def stop(process):
            reaping.set()
            await release.wait()
            process.returncode = -9
            completed.append(True)
            if cleanup_error is not None:
                raise cleanup_error("test-owned reaper failure")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
        monkeypatch.setattr(check, "_stop", stop)
        task = asyncio.create_task(check._run_worker(plan()))
        await reading.wait()
        task.cancel()
        await reaping.wait()
        for _ in range(5):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and not completed
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert completed == [True]
        assert events[-1] == ("removed",)

    asyncio.run(scenario())
