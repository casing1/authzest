"""Memory-only transport tests; never execute a worker, policy or filesystem recipe."""

import ast
import asyncio
import builtins
import socket
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.runner import _owner_policy_file_transport as transport


@pytest.fixture(autouse=True)
def forbid_real_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Captured-file transport tests require memory-only process/filesystem mocks")

    original_compile = builtins.compile

    def guarded_compile(source, filename, mode, flags=0, *args, **kwargs):
        if (
            flags & ast.PyCF_ONLY_AST
            and sys._getframe(1).f_globals.get("__name__") == "ast"
            and sys._getframe(2).f_globals.get("__name__") in {"_pytest._code.source", "traceback"}
        ):
            return original_compile(source, filename, mode, flags, *args, **kwargs)
        forbidden()

    monkeypatch.setattr(builtins, "compile", guarded_compile)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    for method in ("open", "read_text", "read_bytes", "write_text", "write_bytes", "resolve"):
        monkeypatch.setattr(Path, method, forbidden)
    monkeypatch.setattr(transport, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(transport, "os", SimpleNamespace(name="posix", killpg=forbidden))
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


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
    pid = 54321  # Never sent to an actual OS call.

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


def fake_workspace(monkeypatch, *, create_error=None, resolve_error=None, cleanup_error=None):
    events = []

    class Temporary:
        name = "/mock/private-file-check"

        def __init__(self, *, prefix):
            events.append(("create", prefix))
            if create_error is not None:
                raise create_error("private exception text")

        def cleanup(self):
            events.append(("cleanup",))
            if cleanup_error is not None:
                raise cleanup_error("private cleanup detail")

    class Directory:
        def __init__(self, value):
            self.value = value

        def resolve(self):
            events.append(("resolve",))
            if resolve_error is not None:
                raise resolve_error("private directory detail")
            return self

        def __str__(self):
            return self.value

    monkeypatch.setattr(transport, "TemporaryDirectory", Temporary)
    monkeypatch.setattr(transport, "Path", Directory)
    return events


def fake_launch(monkeypatch, process, *, kill_error=None):
    launches = []
    kills = []

    async def create(*command, **options):
        launches.append((command, options))
        return process

    def kill(pid, sig):
        kills.append((pid, sig))
        if kill_error is not None:
            raise kill_error("private kill detail")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(transport, "os", SimpleNamespace(name="posix", killpg=kill))
    return launches, kills


@pytest.mark.parametrize("length", [0, 1, 1024, 16 * 1024])
def test_exchange_reads_only_bounded_output(length):
    process = Process(b"x" * length)
    assert asyncio.run(transport._exchange(process, b"mock-input")) == b"x" * length
    assert process.stdin.data == b"mock-input" and process.stdin.closed
    assert all(1 <= limit <= 1024 for limit in process.stdout.limits)


@pytest.mark.parametrize("length", [16 * 1024 + 1, 64 * 1024])
def test_exchange_stops_after_one_overflow_byte(length):
    process = Process(b"x" * length)
    with pytest.raises(transport._OutputLimitError):
        asyncio.run(transport._exchange(process, b"{}"))
    assert process.stdout.offset == transport.MAX_OUTPUT_BYTES + 1
    assert process.stdout.limits[-1] == 1


@pytest.mark.parametrize("raw", ["{}", bytearray(b"{}"), b"x" * (256 * 1024 + 1)])
def test_exchange_rejects_input_before_writing(raw):
    process = Process()
    with pytest.raises(ValueError):
        asyncio.run(transport._exchange(process, raw))
    assert not process.stdin.data and not process.stdin.closed and not process.stdout.limits


@pytest.mark.parametrize("pipe", ["stdin", "stdout"])
def test_exchange_requires_both_pipes(pipe):
    process = Process()
    setattr(process, pipe, None)
    with pytest.raises(ValueError):
        asyncio.run(transport._exchange(process, b"{}"))


@pytest.mark.parametrize(
    "wire",
    [None, [], {"x": object()}, {"x": float("nan")}, {"x": "x" * (256 * 1024)}, {"x": "\ud800"}],
)
def test_invalid_input_has_no_filesystem_or_process_lifecycle(wire):
    result = asyncio.run(transport.run_worker(wire))
    assert result == transport.WorkerTransport(
        b"", None, "worker-input-error", "not-needed", "not-needed", "not-attempted"
    )


def test_worker_transport_is_frozen():
    result = transport.WorkerTransport(b"", None, None, "not-needed", "not-needed", "not-attempted")
    with pytest.raises(FrozenInstanceError):
        result.output = b"altered"


def test_fixed_command_environment_and_private_workspace(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process(b"mock-result")
    launches, kills = fake_launch(monkeypatch, process)
    wire = {"test-only": "not executable policy data"}
    result = asyncio.run(transport.run_worker(wire))
    assert result == transport.WorkerTransport(
        b"mock-result", 0, None, "confirmed", "confirmed", "started"
    )
    assert events[0] == ("create", "authzest-owner-file-check-")
    assert len(launches) == 1
    command, options = launches[0]
    assert command == (transport.sys.executable, "-I", "-S", "-c", transport.WORKER_SOURCE)
    assert options == {
        "stdin": asyncio.subprocess.PIPE,
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.DEVNULL,
        "cwd": options["cwd"],
        "env": {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": "/mock/private-file-check",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
            "NO_COLOR": "1",
            "TERM": "dumb",
        },
        "start_new_session": True,
        "limit": transport.MAX_OUTPUT_BYTES + 1,
    }
    assert str(options["cwd"]) == "/mock/private-file-check"
    assert process.stdin.data == canonical(wire).encode("utf-8")
    assert kills == [(process.pid, transport.signal.SIGKILL)]
    assert process.waits == 2
    assert events[-1] == ("cleanup",)


def test_prelaunch_guard_runs_after_directory_resolution_before_child(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process(b"scripted-result")
    launches, _ = fake_launch(monkeypatch, process)

    def guard():
        assert events == [("create", "authzest-owner-file-check-"), ("resolve",)]
        assert launches == []
        events.append(("guard",))

    result = asyncio.run(transport.run_worker({}, before_launch=guard))
    assert result.reason is None
    assert len(launches) == 1
    assert events == [
        ("create", "authzest-owner-file-check-"),
        ("resolve",),
        ("guard",),
        ("cleanup",),
    ]


@pytest.mark.parametrize("guard_error", [ContractError, ValueError, OSError, RuntimeError])
@pytest.mark.parametrize("cleanup_error", [None, OSError])
def test_rejected_prelaunch_guard_has_no_child_and_independent_cleanup(
    monkeypatch, guard_error, cleanup_error
):
    events = fake_workspace(monkeypatch, cleanup_error=cleanup_error)
    launches, kills = fake_launch(monkeypatch, Process())

    def reject():
        assert events[-1] == ("resolve",)
        raise guard_error("Private rejected decision details")

    result = asyncio.run(transport.run_worker({}, before_launch=reject))
    assert result == transport.WorkerTransport(
        b"",
        None,
        "worker-process-error",
        "not-needed",
        "confirmed" if cleanup_error is None else "unconfirmed",
        "not-attempted",
    )
    assert launches == kills == []
    assert events[-1] == ("cleanup",)
    assert "Private" not in repr(result)


def test_launch_task_queue_delay_rechecks_expired_guard_before_process(monkeypatch):
    events = fake_workspace(monkeypatch)
    launches, kills = fake_launch(monkeypatch, Process())
    now = [100.0]
    guard_times = []
    real_create_task = asyncio.create_task

    def scheduled(coroutine, *args, **kwargs):
        if coroutine.cr_code.co_name == "_launch":
            # Simulate time advancing between scheduling and executing the task.
            now[0] = 101.0
        return real_create_task(coroutine, *args, **kwargs)

    def guard():
        guard_times.append(now[0])
        if now[0] >= 101.0:
            raise ContractError("Expired decision")

    monkeypatch.setattr(asyncio, "create_task", scheduled)
    result = asyncio.run(transport.run_worker({}, before_launch=guard))
    assert guard_times == [101.0]
    assert launches == kills == []
    assert result.launch_status == "not-attempted"
    assert result.child_cleanup_status == "not-needed"
    assert result.workspace_cleanup_status == "confirmed"
    assert events[-1] == ("cleanup",)


@pytest.mark.parametrize("value", [False, "decision-expired", 0, []])
def test_non_none_guard_result_never_silently_authorizes_launch(monkeypatch, value):
    fake_workspace(monkeypatch)
    launches, kills = fake_launch(monkeypatch, Process())
    result = asyncio.run(transport.run_worker({}, before_launch=lambda: value))
    assert result.reason == "worker-process-error"
    assert result.launch_status == "not-attempted"
    assert result.workspace_cleanup_status == "confirmed"
    assert launches == kills == []


def test_async_guard_is_rejected_without_awaiting_or_leaking_coroutine(monkeypatch):
    fake_workspace(monkeypatch)
    launches, kills = fake_launch(monkeypatch, Process())

    async def invalid_guard():
        pytest.fail("The trusted prelaunch guard must be synchronous")

    result = asyncio.run(transport.run_worker({}, before_launch=invalid_guard))
    assert result.reason == "worker-process-error"
    assert result.launch_status == "not-attempted"
    assert result.workspace_cleanup_status == "confirmed"
    assert launches == kills == []


def test_guard_cancellation_preserves_original_with_no_child(monkeypatch):
    events = fake_workspace(monkeypatch)
    launches, kills = fake_launch(monkeypatch, Process())
    original = asyncio.CancelledError("guard cancellation")

    def cancel():
        raise original

    with pytest.raises(asyncio.CancelledError) as caught:
        asyncio.run(transport.run_worker({}, before_launch=cancel))
    assert caught.value is original
    result = caught.value.worker_transport
    assert result.reason == "cancelled"
    assert result.launch_status == "not-attempted"
    assert result.child_cleanup_status == "not-needed"
    assert result.workspace_cleanup_status == "confirmed"
    assert launches == kills == []
    assert events[-1] == ("cleanup",)


@pytest.mark.parametrize("guard", [False, 1, "approved", {}])
def test_non_callable_guard_rejected_before_filesystem_or_launch(guard):
    result = asyncio.run(transport.run_worker({}, before_launch=guard))
    assert result == transport.WorkerTransport(
        b"", None, "worker-input-error", "not-needed", "not-needed", "not-attempted"
    )


@pytest.mark.parametrize("cleanup_error", [None, OSError])
def test_launch_failure_has_no_child_but_independent_workspace_cleanup(monkeypatch, cleanup_error):
    events = fake_workspace(monkeypatch, cleanup_error=cleanup_error)

    async def failed(*args, **kwargs):
        raise OSError("private launcher detail")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failed)
    result = asyncio.run(transport.run_worker({}))
    assert result.output == b"" and result.exit_code is None
    assert result.reason == "worker-process-error" and result.launch_status == "no-child"
    assert result.child_cleanup_status == "not-needed"
    assert result.workspace_cleanup_status == (
        "confirmed" if cleanup_error is None else "unconfirmed"
    )
    assert events[-1] == ("cleanup",)
    assert "private" not in repr(result)


def test_workspace_creation_failure_is_not_no_cleanup_needed(monkeypatch):
    events = fake_workspace(monkeypatch, create_error=OSError)
    result = asyncio.run(transport.run_worker({}))
    assert result.child_cleanup_status == "not-needed"
    assert result.workspace_cleanup_status == "unconfirmed"
    assert result.launch_status == "not-attempted" and result.reason == "worker-process-error"
    assert len(events) == 1


@pytest.mark.parametrize("cleanup_error", [None, OSError])
def test_resolve_failure_still_cleans_workspace(monkeypatch, cleanup_error):
    events = fake_workspace(monkeypatch, resolve_error=OSError, cleanup_error=cleanup_error)
    result = asyncio.run(transport.run_worker({}))
    assert result.child_cleanup_status == "not-needed" and result.launch_status == "not-attempted"
    assert result.workspace_cleanup_status == (
        "confirmed" if cleanup_error is None else "unconfirmed"
    )
    assert events[-1] == ("cleanup",)


@pytest.mark.parametrize("phase", ["create", "resolve"])
def test_synchronous_filesystem_timeout_is_not_a_started_process_deadline(monkeypatch, phase):
    events = fake_workspace(monkeypatch, **{f"{phase}_error": TimeoutError})
    result = asyncio.run(transport.run_worker({}))
    assert result.reason == "worker-process-error"
    assert result.launch_status == "not-attempted"
    assert result.child_cleanup_status == "not-needed"
    assert result.workspace_cleanup_status == ("unconfirmed" if phase == "create" else "confirmed")
    assert result.output == b"" and result.exit_code is None
    assert "private" not in repr(result)
    if phase == "resolve":
        assert events[-1] == ("cleanup",)


@pytest.mark.parametrize("exit_code", [0, 2])
@pytest.mark.parametrize("kill_error", [None, ProcessLookupError, PermissionError])
@pytest.mark.parametrize("cleanup_error", [None, OSError])
def test_exit_and_cleanup_uncertainty_never_publish_success(
    monkeypatch, exit_code, kill_error, cleanup_error
):
    fake_workspace(monkeypatch, cleanup_error=cleanup_error)
    process = Process(b"mock-output", exit_code)
    fake_launch(monkeypatch, process, kill_error=kill_error)
    result = asyncio.run(transport.run_worker({}))
    success = exit_code == 0 and kill_error is not PermissionError and cleanup_error is None
    assert result.output == (b"mock-output" if success else b"")
    assert result.exit_code == exit_code
    assert result.child_cleanup_status == (
        "unconfirmed" if kill_error is PermissionError else "confirmed"
    )
    assert result.workspace_cleanup_status == (
        "confirmed" if cleanup_error is None else "unconfirmed"
    )
    assert result.reason == (
        None if success else "worker-exit-error" if exit_code else "cleanup-unconfirmed"
    )
    assert process.waits == 2


def test_overflow_reaps_child_and_discards_partial_output(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process(b"x" * (transport.MAX_OUTPUT_BYTES * 2))
    _, kills = fake_launch(monkeypatch, process)
    result = asyncio.run(transport.run_worker({}))
    assert result.output == b"" and result.reason == "output-limit"
    assert result.child_cleanup_status == result.workspace_cleanup_status == "confirmed"
    assert process.stdout.offset == transport.MAX_OUTPUT_BYTES + 1
    assert kills and events[-1] == ("cleanup",)


@pytest.mark.parametrize("phase", ["drain", "read", "wait"])
def test_exchange_and_completion_share_timeout(monkeypatch, phase):
    events = fake_workspace(monkeypatch)
    process = Process()
    _, kills = fake_launch(monkeypatch, process)
    entered = []

    async def blocked(*args):
        entered.append(True)
        if phase == "wait" and len(entered) > 1:
            process.returncode = -9
            return -9
        await asyncio.Event().wait()

    if phase == "drain":
        process.stdin.drain = blocked
    elif phase == "read":
        process.stdout.read = blocked
    else:
        process.wait = blocked
    monkeypatch.setattr(transport, "TIMEOUT_SECONDS", 0.01)
    result = asyncio.run(transport.run_worker({}))
    assert result.output == b"" and result.reason == "timeout"
    assert result.child_cleanup_status == result.workspace_cleanup_status == "confirmed"
    assert kills and events[-1] == ("cleanup",)


def test_startup_timeout_with_no_handle_is_ambiguous_not_no_child(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def launching(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launching)
    monkeypatch.setattr(transport, "TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(transport, "MAX_CLEANUP_SECONDS", 0.01)
    result = asyncio.run(transport.run_worker({}))
    assert result.reason == "timeout" and result.launch_status == "ambiguous"
    assert (
        result.child_cleanup_status == "unconfirmed"
        and result.workspace_cleanup_status == "confirmed"
    )
    assert events[-1] == ("cleanup",)


def test_delayed_launch_handle_is_reaped_within_cleanup_budget(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process()
    _, kills = fake_launch(monkeypatch, process)

    async def launching(*args, **kwargs):
        await asyncio.sleep(0.02)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launching)
    monkeypatch.setattr(transport, "TIMEOUT_SECONDS", 0.01)
    result = asyncio.run(transport.run_worker({}))
    assert result.reason == "timeout" and result.launch_status == "started"
    assert result.child_cleanup_status == result.workspace_cleanup_status == "confirmed"
    assert kills and events[-1] == ("cleanup",)


def test_reaper_deadline_is_bounded_and_records_uncertainty(monkeypatch):
    events = fake_workspace(monkeypatch)
    process = Process()
    fake_launch(monkeypatch, process)
    calls = []

    async def wait():
        calls.append(True)
        if len(calls) == 1:
            process.returncode = 0
            return 0
        await asyncio.Event().wait()

    process.wait = wait
    monkeypatch.setattr(transport, "MAX_CLEANUP_SECONDS", 0.01)
    result = asyncio.run(transport.run_worker({}))
    assert result.reason == "cleanup-unconfirmed" and result.output == b""
    assert (
        result.child_cleanup_status == "unconfirmed"
        and result.workspace_cleanup_status == "confirmed"
    )
    assert events[-1] == ("cleanup",)


@pytest.mark.parametrize("cleanup_error", [None, OSError])
@pytest.mark.parametrize("reap_error", [None, OSError])
def test_repeated_cancel_preserves_original_and_final_cleanup_diagnostics(
    monkeypatch, cleanup_error, reap_error
):
    events = fake_workspace(monkeypatch, cleanup_error=cleanup_error)

    async def scenario():
        reading, reaping, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        process = Process()
        fake_launch(monkeypatch, process)
        originals = []

        async def read(limit):
            reading.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError as exc:
                originals.append(exc)
                raise

        async def wait():
            reaping.set()
            await release.wait()
            process.returncode = -9
            if reap_error is not None:
                raise reap_error("private reaper detail")
            return -9

        process.stdout.read = read
        process.wait = wait
        task = asyncio.create_task(transport.run_worker({}))
        await reading.wait()
        task.cancel("original cancellation")
        await reaping.wait()
        for index in range(5):
            task.cancel(f"later cancellation {index}")
            await asyncio.sleep(0)
            assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value is originals[0]
        assert caught.value.args == ("original cancellation",)
        result = caught.value.worker_transport
        assert result.output == b"" and result.reason == "cancelled" and result.exit_code == -9
        assert result.child_cleanup_status == ("confirmed" if reap_error is None else "unconfirmed")
        assert result.launch_status == "started"
        assert result.workspace_cleanup_status == (
            "confirmed" if cleanup_error is None else "unconfirmed"
        )
        assert events[-1] == ("cleanup",)

    asyncio.run(scenario())


def test_startup_cancellation_can_recover_and_reap_its_owned_handle(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def scenario():
        launching, release = asyncio.Event(), asyncio.Event()
        process = Process()
        _, kills = fake_launch(monkeypatch, process)

        async def create(*args, **kwargs):
            launching.set()
            await release.wait()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
        task = asyncio.create_task(transport.run_worker({}))
        await launching.wait()
        task.cancel("startup cancellation")
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        result = caught.value.worker_transport
        assert caught.value.args == ("startup cancellation",)
        assert result.reason == "cancelled" and result.launch_status == "started"
        assert result.child_cleanup_status == result.workspace_cleanup_status == "confirmed"
        assert not process.stdin.data
        assert kills == [(process.pid, transport.signal.SIGKILL)]
        assert events[-1] == ("cleanup",)

    asyncio.run(scenario())


def test_unexpected_startup_error_does_not_claim_no_child(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def create(*args, **kwargs):
        raise RuntimeError("unclassified startup detail")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    result = asyncio.run(transport.run_worker({}))
    assert result.reason == "worker-process-error" and result.launch_status == "ambiguous"
    assert (
        result.child_cleanup_status == "unconfirmed"
        and result.workspace_cleanup_status == "confirmed"
    )
    assert "unclassified" not in repr(result)
    assert events[-1] == ("cleanup",)


def test_repeated_cancellation_cannot_extend_reaper_deadline(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def scenario():
        reading, reaping = asyncio.Event(), asyncio.Event()
        process = Process()
        fake_launch(monkeypatch, process)

        async def read(limit):
            reading.set()
            await asyncio.Event().wait()

        async def wait():
            reaping.set()
            await asyncio.Event().wait()

        process.stdout.read = read
        process.wait = wait
        monkeypatch.setattr(transport, "MAX_CLEANUP_SECONDS", 0.01)
        task = asyncio.create_task(transport.run_worker({}))
        await reading.wait()
        task.cancel("original")
        await reaping.wait()
        for _ in range(5):
            task.cancel("later")
            await asyncio.sleep(0)
        with pytest.raises(asyncio.CancelledError) as caught:
            await asyncio.wait_for(task, timeout=0.5)
        assert caught.value.args == ("original",)
        assert caught.value.worker_transport.child_cleanup_status == "unconfirmed"
        assert caught.value.worker_transport.workspace_cleanup_status == "confirmed"
        assert events[-1] == ("cleanup",)

    asyncio.run(scenario())


def test_startup_cancel_is_not_mislabeled_as_no_child(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def scenario():
        launching = asyncio.Event()

        async def create(*args, **kwargs):
            launching.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
        monkeypatch.setattr(transport, "MAX_CLEANUP_SECONDS", 0.01)
        task = asyncio.create_task(transport.run_worker({}))
        await launching.wait()
        task.cancel("startup cancelled")
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        result = caught.value.worker_transport
        assert caught.value.args == ("startup cancelled",)
        assert result.reason == "cancelled" and result.launch_status == "ambiguous"
        assert (
            result.child_cleanup_status == "unconfirmed"
            and result.workspace_cleanup_status == "confirmed"
        )
        assert events[-1] == ("cleanup",)

    asyncio.run(scenario())


def test_first_cancellation_during_cleanup_is_preserved(monkeypatch):
    events = fake_workspace(monkeypatch)

    async def scenario():
        reaping, release = asyncio.Event(), asyncio.Event()
        process = Process()
        fake_launch(monkeypatch, process)

        async def wait():
            process.waits += 1
            if process.waits > 1:
                reaping.set()
                await release.wait()
            process.returncode = 0
            return 0

        process.wait = wait
        task = asyncio.create_task(transport.run_worker({}))
        await reaping.wait()
        task.cancel("cleanup cancellation")
        await asyncio.sleep(0)
        task.cancel("replacement cancellation")
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value.args == ("cleanup cancellation",)
        assert caught.value.worker_transport.reason == "cancelled"
        assert caught.value.worker_transport.child_cleanup_status == "confirmed"
        assert events[-1] == ("cleanup",)

    asyncio.run(scenario())


@pytest.mark.parametrize("platform", ["non-posix", "frozen"])
def test_unsupported_platform_refuses_before_filesystem_or_process(monkeypatch, platform):
    if platform == "non-posix":
        monkeypatch.setattr(transport.os, "name", "nt")
    else:
        monkeypatch.setattr(transport.sys, "frozen", True, raising=False)
    result = asyncio.run(transport.run_worker({}))
    assert result == transport.WorkerTransport(
        b"", None, "unsupported-platform", "not-needed", "not-needed", "not-attempted"
    )


def test_transport_has_no_command_source_callback_or_environment_options():
    import inspect

    parameters = inspect.signature(transport.run_worker).parameters
    assert list(parameters) == ["worker_input", "before_launch"]
    assert parameters["before_launch"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["before_launch"].default is None
    assert transport.TIMEOUT_SECONDS == 5.0
    assert transport.MAX_CLEANUP_SECONDS == 1.0
