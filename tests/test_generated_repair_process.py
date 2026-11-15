"""Maintained fake children over real inert pipes, without spawning commands."""

from __future__ import annotations

import os
import signal
from dataclasses import FrozenInstanceError

import pytest

from authzest.runner import _generated_repair_process as transport

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX local pipe transport")


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        self.value += 0.001
        return self.value


class Child:
    def __init__(self, pid, stdout=b"", stderr=b"", *, running=False, returncode=0):
        self.pid, self.returncode, self.final_code = pid, None, returncode
        self.running, self.killed, self.group_exists = running, False, True
        self.stdout, self.stdout_writer = self.pipe(stdout, not running)
        self.stderr, self.stderr_writer = self.pipe(stderr, not running)

    @staticmethod
    def pipe(raw, close_writer):
        reader, writer = os.pipe()
        stream = os.fdopen(reader, "rb", buffering=0)
        if raw:
            os.write(writer, raw)
        if close_writer:
            os.close(writer)
            writer = None
        return stream, writer

    def poll(self):
        if not self.running or self.killed:
            self.returncode = -signal.SIGKILL if self.killed else self.final_code
            self.group_exists = False
        return self.returncode

    def kill_group(self):
        self.killed, self.running = True, False
        for name in ("stdout_writer", "stderr_writer"):
            descriptor = getattr(self, name)
            if descriptor is not None:
                os.close(descriptor)
                setattr(self, name, None)


@pytest.fixture
def children(monkeypatch):
    supplied, calls, signals = [], [], []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return supplied[len(calls) - 1]

    def killpg(pid, sig):
        child = next(item for item in supplied if item.pid == pid)
        signals.append((pid, sig))
        if not child.group_exists:
            raise ProcessLookupError
        if sig == signal.SIGKILL:
            child.kill_group()

    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    monkeypatch.setattr(transport.os, "killpg", killpg)
    yield supplied, calls, signals
    for child in supplied:
        child.kill_group()
        child.stdout.close()
        child.stderr.close()


def test_exact_spawn_options_and_two_pipe_completion(children):
    supplied, calls, _ = children
    supplied.append(Child(11111, b"out", b"err"))
    clock, pool = Clock(), transport.ProcessPool(clock=Clock())
    argv, env = ["/fixed/docker", "inspect", "literal;$()"], {"DOCKER_API_VERSION": "1.51"}
    handle = pool.start(argv, env, 101, "inspect-A")
    snapshot = pool.wait(handle, 101)
    assert (snapshot.stdout, snapshot.stderr, snapshot.returncode) == (b"out", b"err", 0)
    assert snapshot.complete is True and snapshot.local_cleanup_confirmed is False
    actual_argv, options = calls[0]
    assert actual_argv == argv and options["env"] == env
    assert options["shell"] is False and options["start_new_session"] is True
    assert options["stdin"] == transport.subprocess.DEVNULL
    assert options["stdout"] == options["stderr"] == transport.subprocess.PIPE
    assert options["bufsize"] == 0
    assert pool.output_bytes == 6 and pool.first_failure is None
    assert pool.terminate_all(clock() + 1)[0].local_cleanup_confirmed is True
    with pytest.raises(FrozenInstanceError):
        snapshot.stdout = b"changed"


def test_waiting_for_b_drains_still_running_a(children):
    supplied, _, _ = children
    supplied.extend(
        [Child(11111, b"A-out", b"A-err", running=True), Child(22222, b"B-out", b"B-err")]
    )
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    a = pool.start(["/fixed/a"], {}, 101, "A")
    b = pool.start(["/fixed/b"], {}, 101, "B")
    assert pool.wait(b, 101).complete is True
    assert (pool.snapshot(a).stdout, pool.snapshot(a).stderr) == (b"A-out", b"A-err")
    assert pool.snapshot(a).complete is False
    cleanup = pool.terminate_all(clock() + 1)
    assert all(item.local_cleanup_confirmed for item in cleanup)
    assert pool.snapshot(a).complete is False


def test_combined_output_limit_is_shared_and_sticky(children):
    supplied, calls, _ = children
    supplied.extend([Child(11111, b"1234", b"5"), Child(22222, b"6789", b"0")])
    clock = Clock()
    pool = transport.ProcessPool(clock=clock, max_output_bytes=8)
    a = pool.start(["/fixed/a"], {}, 101, "A")
    pool.wait(a, 101)
    b = pool.start(["/fixed/b"], {}, 101, "B")
    with pytest.raises(transport.ProcessError, match="combined-output-limit"):
        pool.wait(b, 101)
    assert pool.output_bytes == 9
    assert sum(len(item.stdout) + len(item.stderr) for item in pool.snapshots()) == 8
    with pytest.raises(transport.ProcessError, match="combined-output-limit"):
        pool.start(["/fixed/c"], {}, 102, "C")
    assert len(calls) == 2
    assert all(item.local_cleanup_confirmed for item in pool.terminate_all(clock() + 1))
    assert pool.first_failure == "combined-output-limit"


def test_original_phase_deadline_cannot_be_extended(children):
    supplied, _, _ = children
    supplied.append(Child(11111, running=True))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    handle = pool.start(["/fixed/a"], {}, 100.02, "A")
    clock.value = 100.03
    with pytest.raises(transport.ProcessError, match="original-deadline-expired"):
        pool.wait(handle, 999)
    assert pool.terminate_all(clock() + 1)[0].local_cleanup_confirmed is True


def test_completed_setup_wait_does_not_shorten_the_original_phase(children):
    supplied, _, _ = children
    supplied.extend([Child(11111, b"setup"), Child(22222, b"later")])
    clock = Clock()
    pool = transport.ProcessPool(clock=clock, phase_deadline=102)
    setup = pool.start(["/fixed/setup"], {}, 102, "setup")
    assert pool.wait(setup, 100.1).complete is True
    clock.value = 100.5
    later = pool.start(["/fixed/later"], {}, 102, "later")
    assert pool.wait(later, 102).stdout == b"later"
    assert all(item.local_cleanup_confirmed for item in pool.terminate_all(clock() + 1))


def test_cleanup_commands_share_one_new_window_without_erasing_first_failure(children):
    supplied, _, _ = children
    supplied.extend([Child(11111, b"A", running=True), Child(22222, b"stopped")])
    clock = Clock()
    pool = transport.ProcessPool(clock=clock, phase_deadline=101)
    attached = pool.start(["/fixed/attach"], {}, 101, "attach-A")
    clock.value = 101.1
    with pytest.raises(transport.ProcessError, match="original-deadline-expired"):
        pool.wait(attached, 101)
    pool.begin_cleanup(102)
    cleanup = pool.start(["/fixed/cleanup"], {}, 999, "cleanup-A")
    assert pool.wait(cleanup, 999).stdout == b"stopped"
    assert pool.snapshot(attached).stdout == b"A"
    assert pool.first_failure == "original-deadline-expired"
    assert pool.output_bytes == 8
    with pytest.raises(transport.ProcessError):
        pool.begin_cleanup(103)
    assert all(item.local_cleanup_confirmed for item in pool.terminate_all(999))


def test_cleanup_does_not_reset_an_overflowed_output_budget(children):
    supplied, calls, _ = children
    supplied.append(Child(11111, b"12345"))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock, max_output_bytes=4)
    handle = pool.start(["/fixed/noisy"], {}, 101, "noisy")
    with pytest.raises(transport.ProcessError, match="combined-output-limit"):
        pool.wait(handle, 101)
    pool.begin_cleanup(102)
    with pytest.raises(transport.ProcessError, match="combined-output-limit"):
        pool.start(["/fixed/cleanup"], {}, 102, "cleanup")
    assert len(calls) == 1 and pool.output_bytes == 5
    assert pool.terminate_all(102)[0].local_cleanup_confirmed is True


def test_normal_output_limit_preserves_reserve_for_fixed_cleanup(children):
    supplied, calls, _ = children
    supplied.extend([Child(11111, b"123456789FLOOD", running=True), Child(22222, b"OK")])
    clock = Clock()
    pool = transport.ProcessPool(clock=clock, max_output_bytes=16, cleanup_reserve_bytes=8)
    noisy = pool.start(["/fixed/noisy"], {}, 101, "noisy")
    with pytest.raises(transport.ProcessError, match="normal-output-limit"):
        pool.wait(noisy, 101)
    assert pool.output_bytes == 9 and pool.snapshot(noisy).stdout == b"123456789"
    pool.begin_cleanup(102)
    assert supplied[0].stdout.closed and supplied[0].stderr.closed
    assert pool.snapshot(noisy).complete is False
    marker = pool.start(["/fixed/cleanup"], {}, 102, "cleanup")
    assert pool.wait(marker, 102).stdout == b"OK"
    assert len(calls) == 2 and pool.output_bytes == 11
    assert pool.first_failure == "normal-output-limit"
    assert all(item.local_cleanup_confirmed for item in pool.terminate_all(102))


def test_cleanup_hard_overflow_remains_incomplete_and_never_refreshes_budget(children):
    supplied, calls, _ = children
    supplied.extend([Child(11111, b"123456789", running=True), Child(22222, b"too-much-cleanup")])
    clock = Clock()
    pool = transport.ProcessPool(clock=clock, max_output_bytes=16, cleanup_reserve_bytes=8)
    noisy = pool.start(["/fixed/noisy"], {}, 101, "noisy")
    with pytest.raises(transport.ProcessError):
        pool.wait(noisy, 101)
    pool.begin_cleanup(102)
    marker = pool.start(["/fixed/cleanup"], {}, 102, "cleanup")
    with pytest.raises(transport.ProcessError):
        pool.wait(marker, 102)
    assert pool.output_bytes == 17
    assert pool.first_failure == "normal-output-limit"
    assert "combined-output-limit" in pool.snapshot(marker).errors
    assert pool.snapshot(marker).complete is False
    assert sum(len(item.stdout) + len(item.stderr) for item in pool.snapshots()) == 16
    with pytest.raises(transport.ProcessError):
        pool.start(["/fixed/another-cleanup"], {}, 102, "another-cleanup")
    assert len(calls) == 2
    assert all(item.local_cleanup_confirmed for item in pool.terminate_all(102))


@pytest.mark.parametrize("reserve", [-1, True, 16, 17])
def test_cleanup_reserve_has_a_native_positive_normal_remainder(reserve):
    with pytest.raises(ValueError):
        transport.ProcessPool(max_output_bytes=16, cleanup_reserve_bytes=reserve)


@pytest.mark.parametrize("cancel", [KeyboardInterrupt, SystemExit])
def test_cancellation_preserves_original_and_retained_observation(children, monkeypatch, cancel):
    supplied, _, _ = children
    supplied.append(Child(11111, running=True))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    handle = pool.start(["/fixed/a"], {}, 101, "A")
    original = cancel("maintained cancellation")

    def interrupted(_):
        raise original

    monkeypatch.setattr(pool._selector, "select", interrupted)
    with pytest.raises(cancel) as caught:
        pool.wait(handle, 101)
    assert caught.value is original
    assert original.process_observation[0].label == "A"
    assert original.process_first_failure == pool.first_failure == "cancelled"
    assert pool.terminate_all(clock() + 1)[0].local_cleanup_confirmed is True


def test_reversing_clock_fails_before_launch(children):
    _, calls, _ = children
    values = iter([100.0, 99.0])
    pool = transport.ProcessPool(clock=lambda: next(values))
    pool._now()
    with pytest.raises(transport.ProcessError, match="invalid-or-reversing-clock"):
        pool.start(["/fixed/a"], {}, 101, "A")
    assert calls == []
    pool.terminate_all(102)


def test_foreign_handle_cannot_be_waited(children):
    supplied, _, _ = children
    supplied.append(Child(11111))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    handle = pool.start(["/fixed/a"], {}, 101, "A")
    forged = transport.ProcessHandle(handle.token, handle.label)
    with pytest.raises(transport.ProcessError, match="foreign-process-handle"):
        pool.wait(forged, 101)
    pool.terminate_all(clock() + 1)


def test_cleanup_deadline_is_not_refreshed_and_group_absence_must_be_observed(
    children, monkeypatch
):
    supplied, _, _ = children
    supplied.append(Child(11111, running=True))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    pool.start(["/fixed/a"], {}, 101, "A")

    def unknown_group(pid, sig):
        if sig == signal.SIGKILL:
            supplied[0].kill_group()

    monkeypatch.setattr(transport.os, "killpg", unknown_group)
    cleanup = pool.terminate_all(clock() + 0.005)
    assert cleanup[0].returncode == -signal.SIGKILL
    assert cleanup[0].local_cleanup_confirmed is False
    assert pool.first_failure == "local-cleanup-unconfirmed"


def test_launch_failure_keeps_an_ambiguous_snapshot(children, monkeypatch):
    def failed(*args, **kwargs):
        raise OSError("maintained failed launch")

    monkeypatch.setattr(transport.subprocess, "Popen", failed)
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    with pytest.raises(transport.ProcessError, match="process-start-failed"):
        pool.start(["/fixed/a"], {}, 101, "A")
    snapshot = pool.terminate_all(clock() + 1)[0]
    assert snapshot.pid is None and snapshot.local_cleanup_confirmed is False
    assert pool.first_failure == "process-start-failed"


def test_cleanup_close_cancellation_still_signals_other_known_groups(children, monkeypatch):
    supplied, _, signals = children
    supplied.extend([Child(11111, running=True), Child(22222, running=True)])
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    pool.start(["/fixed/a"], {}, 101, "A")
    pool.start(["/fixed/b"], {}, 101, "B")
    original = KeyboardInterrupt("maintained close cancellation")

    def interrupted():
        raise original

    with monkeypatch.context() as scoped:
        scoped.setattr(supplied[0].stdout, "close", interrupted)
        with pytest.raises(KeyboardInterrupt) as caught:
            pool.terminate_all(clock() + 1)
    assert caught.value is original
    assert (11111, signal.SIGKILL) in signals and (22222, signal.SIGKILL) in signals
    snapshots = pool.snapshots()
    assert snapshots[0].local_cleanup_confirmed is False
    assert snapshots[1].local_cleanup_confirmed is True
    assert original.process_observation == snapshots


def test_pipe_close_uncertainty_cannot_be_reported_as_confirmed(children, monkeypatch):
    supplied, _, _ = children
    supplied.append(Child(11111))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    handle = pool.start(["/fixed/a"], {}, 101, "A")

    def refused():
        raise OSError("maintained close failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(supplied[0].stdout, "close", refused)
        with pytest.raises(transport.ProcessError, match="pipe-cleanup-unconfirmed"):
            pool.wait(handle, 101)
        snapshot = pool.terminate_all(clock() + 0.005)[0]
    assert snapshot.local_cleanup_confirmed is False
    assert pool.first_failure == "pipe-cleanup-unconfirmed"


def test_cleanup_window_cannot_exceed_ten_seconds(children):
    _, calls, _ = children
    pool = transport.ProcessPool(clock=Clock())
    with pytest.raises(transport.ProcessError, match="invalid-cleanup-window"):
        pool.begin_cleanup(111)
    assert calls == []
    pool.terminate_all(102)


@pytest.mark.parametrize("group_still_exists", [True, False])
def test_reaped_leader_never_authorizes_signaling_its_stale_group_id(
    children, monkeypatch, group_still_exists
):
    supplied, _, _ = children
    supplied.append(Child(11111, b"complete"))
    clock = Clock()
    pool = transport.ProcessPool(clock=clock)
    handle = pool.start(["/fixed/completed"], {}, 101, "completed")
    assert pool.wait(handle, 101).returncode == 0
    monkeypatch.setattr(supplied[0], "poll", lambda: 0)
    observations = []

    def observe_only(pid, sig):
        observations.append((pid, sig))
        assert sig == 0, "A stale reaped leader must never receive SIGKILL"
        if not group_still_exists:
            raise ProcessLookupError

    monkeypatch.setattr(transport.os, "killpg", observe_only)
    snapshot = pool.terminate_all(clock() + 0.005)[0]
    assert observations and all(sig == 0 for _, sig in observations)
    assert snapshot.local_cleanup_confirmed is (not group_still_exists)
    assert supplied[0].killed is False
    count = len(observations)
    assert pool.terminate_all(clock() + 1)[0] == snapshot
    assert len(observations) == count
    if not group_still_exists:
        assert count == 1
