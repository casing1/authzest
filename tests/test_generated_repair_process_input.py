"""Bounded input over inert pipes and one maintained echo child."""

from __future__ import annotations

import os
import signal
import sys
from contextlib import suppress
from time import monotonic

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
    def __init__(self):
        self.pid, self.returncode = 98765, None
        self.group_exists = True
        self.input_reader, writer = os.pipe()
        self.stdin = os.fdopen(writer, "wb", buffering=0)
        self.stdout = self.output(b"out")
        self.stderr = self.output(b"err")

    @staticmethod
    def output(data):
        reader, writer = os.pipe()
        os.write(writer, data)
        os.close(writer)
        return os.fdopen(reader, "rb", buffering=0)

    def poll(self):
        self.returncode, self.group_exists = 0, False
        return self.returncode


@pytest.fixture
def fake(monkeypatch):
    child, calls, clock = Child(), [], Clock()

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return child

    def killpg(pid, sig):
        assert pid == child.pid
        if not child.group_exists:
            raise ProcessLookupError
        if sig == signal.SIGKILL:
            child.poll()

    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    monkeypatch.setattr(transport.os, "killpg", killpg)
    pool = transport.ProcessPool(clock=clock)
    yield child, calls, pool, clock
    pool.terminate_all(clock() + 1)
    for stream in (child.stdin, child.stdout, child.stderr):
        with suppress(OSError, KeyboardInterrupt):
            stream.close()
    if child.input_reader is not None:
        os.close(child.input_reader)


def test_bounded_input_arrives_exactly_and_output_accounting_stays_separate(fake):
    child, calls, pool, clock = fake
    payload = bytes(range(256)) * 2
    handle = pool.start(["/fixed/docker"], {}, 101, "input", input_bytes=payload)
    assert os.read(child.input_reader, 1024) == payload
    assert os.read(child.input_reader, 1) == b""
    assert child.stdin.closed
    assert calls[0][1]["stdin"] == transport.subprocess.PIPE
    result = pool.wait(handle, 101)
    assert result.stdout == b"out" and result.stderr == b"err"
    assert pool.output_bytes == 6
    assert pool.terminate_all(clock() + 1)[0].local_cleanup_confirmed is True


def test_default_still_uses_devnull_without_writing_input(fake):
    child, calls, pool, _ = fake
    pool.start(["/fixed/docker"], {}, 101, "no-input")
    assert calls[0][1]["stdin"] == transport.subprocess.DEVNULL
    assert not child.stdin.closed


@pytest.mark.parametrize("value", [b"x" * 513, "text", bytearray(b"x"), True, 1])
def test_invalid_input_is_refused_before_launch(fake, value):
    _, calls, pool, _ = fake
    with pytest.raises(transport.ProcessError, match="invalid-process-input"):
        pool.start(["/fixed/docker"], {}, 101, "invalid", input_bytes=value)
    assert calls == []


def test_empty_input_closes_pipe_with_eof(fake, monkeypatch):
    child, _, pool, _ = fake
    monkeypatch.setattr(transport.os, "write", lambda *_: pytest.fail("Unexpected empty write"))
    pool.start(["/fixed/docker"], {}, 101, "empty", input_bytes=b"")
    assert child.stdin.closed
    assert os.read(child.input_reader, 1) == b""


def test_short_writes_and_eintr_preserve_exact_input(fake, monkeypatch):
    child, _, pool, _ = fake
    original_write = os.write
    calls = []

    def write(descriptor, data):
        calls.append(bytes(data))
        if len(calls) == 1:
            raise InterruptedError
        return original_write(descriptor, data[:2])

    monkeypatch.setattr(transport.os, "write", write)
    pool.start(["/fixed/docker"], {}, 101, "short", input_bytes=b"abcdef")
    assert calls == [b"abcdef", b"abcdef", b"cdef", b"ef"]
    assert os.read(child.input_reader, 16) == b"abcdef"
    assert child.stdin.closed


@pytest.mark.parametrize("error", [BlockingIOError, BrokenPipeError, OSError])
def test_write_failure_closes_input_and_retains_child_for_cleanup(fake, monkeypatch, error):
    child, _, pool, clock = fake

    def write(*_):
        raise error

    monkeypatch.setattr(transport.os, "write", write)
    with pytest.raises(transport.ProcessError, match="process-input-failed"):
        pool.start(["/fixed/docker"], {}, 101, "write-failure", input_bytes=b"manifest")
    assert child.stdin.closed
    assert len(pool.snapshots()) == 1
    assert pool.terminate_all(clock() + 1)[0].local_cleanup_confirmed is True


@pytest.mark.parametrize("written", [0, -1, 999, True])
def test_invalid_write_count_is_refused_and_pipe_closed(fake, monkeypatch, written):
    child, _, pool, _ = fake
    monkeypatch.setattr(transport.os, "write", lambda *_: written)
    with pytest.raises(transport.ProcessError, match="process-input-incomplete"):
        pool.start(["/fixed/docker"], {}, 101, "zero-write", input_bytes=b"abc")
    assert child.stdin.closed


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt, SystemExit])
def test_input_cancellation_preserves_exception_and_closes_writer(fake, monkeypatch, cancellation):
    child, _, pool, clock = fake
    expected = cancellation("cancel input")

    def write(*_):
        raise expected

    monkeypatch.setattr(transport.os, "write", write)
    with pytest.raises(cancellation) as caught:
        pool.start(["/fixed/docker"], {}, 101, "cancel-input", input_bytes=b"abc")
    assert caught.value is expected
    assert child.stdin.closed and pool.first_failure == "cancelled"
    assert pool.terminate_all(clock() + 1)[0].local_cleanup_confirmed is True


def test_deadline_during_input_closes_writer(fake, monkeypatch):
    child, _, pool, clock = fake
    original = os.write

    def write(descriptor, data):
        clock.value = 102
        return original(descriptor, data[:1])

    monkeypatch.setattr(transport.os, "write", write)
    with pytest.raises(transport.ProcessError, match="original-deadline-expired"):
        pool.start(["/fixed/docker"], {}, 101, "expiry-input", input_bytes=b"abc")
    assert child.stdin.closed and os.read(child.input_reader, 8) == b"a"


def test_writer_is_closed_after_configuration_failure(fake, monkeypatch):
    child, _, pool, _ = fake
    original = os.set_blocking

    def set_blocking(descriptor, value):
        if descriptor == child.stdin.fileno():
            raise OSError("Cannot configure input")
        return original(descriptor, value)

    monkeypatch.setattr(transport.os, "set_blocking", set_blocking)
    with pytest.raises(transport.ProcessError, match="process-input-failed"):
        pool.start(["/fixed/docker"], {}, 101, "config-input", input_bytes=b"abc")
    assert child.stdin.closed


def test_real_maintained_child_reads_manifest_and_eof():
    pool = transport.ProcessPool(phase_deadline=monotonic() + 5)
    try:
        handle = pool.start(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
            ],
            {},
            monotonic() + 5,
            "maintained-echo",
            input_bytes=b'{"source":"fixed"}',
        )
        result = pool.wait(handle, monotonic() + 5)
        assert result.stdout == b'{"source":"fixed"}' and result.stderr == b""
        assert result.returncode == 0 and result.complete
    finally:
        snapshots = pool.terminate_all(monotonic() + 1)
    assert snapshots[0].local_cleanup_confirmed is True


@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt])
def test_output_setup_failure_still_closes_input_writer(fake, monkeypatch, error):
    child, _, pool, _ = fake

    def set_blocking(*_):
        raise error("Cannot configure output")

    monkeypatch.setattr(transport.os, "set_blocking", set_blocking)
    expected = transport.ProcessError if error is OSError else KeyboardInterrupt
    with pytest.raises(expected):
        pool.start(["/fixed/docker"], {}, 101, "setup-failure", input_bytes=b"abc")
    assert child.stdin.closed


@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt])
def test_input_close_failure_remains_uncertain_even_if_retry_closes_writer(fake, error):
    child, _, pool, clock = fake
    stream = child.stdin

    class OnceFailingClose:
        def __init__(self):
            self.calls = 0

        def fileno(self):
            return stream.fileno()

        def close(self):
            self.calls += 1
            if self.calls == 1:
                raise error("Input close uncertain")
            stream.close()

    child.stdin = OnceFailingClose()
    expected = transport.ProcessError if error is OSError else KeyboardInterrupt
    with pytest.raises(expected):
        pool.start(["/fixed/docker"], {}, 101, "close-failure", input_bytes=b"abc")
    assert stream.closed and child.stdin.calls == 2
    result = pool.terminate_all(clock() + 1)[0]
    assert result.local_cleanup_confirmed is False
    assert "input-pipe-cleanup-unconfirmed" in result.errors


@pytest.mark.parametrize("limit", [511, 16_385, True, 512.0, "16384", None])
def test_input_limit_configuration_is_closed(limit):
    with pytest.raises(ValueError, match="Invalid process pool configuration"):
        transport.ProcessPool(max_input_bytes=limit)


def test_default_input_limit_remains_legacy_pipe_buf(fake, monkeypatch):
    _, calls, pool, _ = fake
    assert transport.LEGACY_INPUT_BYTES == 512
    with pytest.raises(transport.ProcessError, match="invalid-process-input"):
        pool.start(["/fixed/docker"], {}, 101, "legacy", input_bytes=b"x" * 513)
    assert calls == []


def test_opt_in_input_limit_is_exact_and_still_refuses_excess(monkeypatch):
    calls = []

    def popen(*args, **kwargs):
        calls.append(args)
        raise AssertionError("oversized input must be refused before launch")

    monkeypatch.setattr(transport.subprocess, "Popen", popen)
    pool = transport.ProcessPool(clock=Clock(), max_input_bytes=transport.MAX_INPUT_BYTES)
    with pytest.raises(transport.ProcessError, match="invalid-process-input"):
        pool.start(["/fixed/docker"], {}, 101, "excess", input_bytes=b"x" * 16_385)
    assert calls == []


def test_real_child_reads_opt_in_schedule_sized_input_and_eof():
    payload = (bytes(range(32, 127)) * 200)[: transport.MAX_INPUT_BYTES]
    pool = transport.ProcessPool(
        phase_deadline=monotonic() + 5, max_input_bytes=transport.MAX_INPUT_BYTES
    )
    try:
        handle = pool.start(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import sys; data = sys.stdin.buffer.read(); sys.stdout.write(str(len(data)))",
            ],
            {},
            monotonic() + 5,
            "schedule-echo",
            input_bytes=payload,
        )
        result = pool.wait(handle, monotonic() + 5)
        assert result.stdout == str(len(payload)).encode() and result.returncode == 0
    finally:
        snapshots = pool.terminate_all(monotonic() + 1)
    assert snapshots[0].local_cleanup_confirmed is True
