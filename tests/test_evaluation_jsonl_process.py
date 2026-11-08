"""Real pipes to one fixed owned fixture, not a product launcher or live acceptance.

POSIX-only lifecycle checks use no descendants or broad process discovery. The
I/O watchdog and bounded cleanup are test controls, not sandbox/isolation proof
or a hard time bound on every host syscall. No model response corpus is used.
"""

from __future__ import annotations

import json
import os
import selectors
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from scripts import evaluation_jsonl as wire

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owned POSIX pipe lifecycle fixture")

FIXTURE = Path(__file__).parent / "fixtures/evaluation_protocol/fake_jsonl_server.py"
PYTHON = str(Path(sys.executable).absolute())
ENVIRONMENT = {"LANG": "C", "LC_ALL": "C"}
MODES = frozenset(
    {
        "success",
        "fragmented",
        "coalesced",
        "truncated",
        "malformed",
        "invalid-utf8",
        "warning",
        "foreign",
        "duplicate",
        "request-error",
        "eof",
        "nonzero",
        "wait",
        "ignore-term",
        "broken-pipe",
    }
)
INITIALIZED = {
    "codexHome": "/synthetic/codex-home",
    "platformFamily": "unix",
    "platformOs": "synthetic",
    "userAgent": "authzest-fake/0.153.0",
}
RESULT = {"config": {"fixture_label": "한글"}, "origins": {}}


def _frame(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def _ready(state: str) -> bytes:
    return _frame(
        {
            "method": "thread/status/changed",
            "params": {"threadId": "synthetic-" + state, "status": {"type": "idle"}},
        }
    )


@pytest.fixture(autouse=True)
def fixed_owned_process_only(monkeypatch, tmp_path):
    original_popen = subprocess.Popen

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network or non-owned process forbidden")

    def checked_popen(args, **kwargs):
        assert type(args) is list and len(args) == 5
        assert args[:4] == [PYTHON, "-I", "-S", str(FIXTURE.resolve())]
        assert args[4] in MODES
        assert kwargs == {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "cwd": tmp_path,
            "env": ENVIRONMENT,
            "bufsize": 0,
            "start_new_session": True,
        }
        assert not list(tmp_path.iterdir())
        return original_popen(args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", checked_popen)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


class _OwnedPeer:
    """Test-only harness with a closed executable, script and mode allowlist."""

    def __init__(self, mode: str, cwd: Path):
        assert mode in MODES
        self.deadline = time.monotonic() + 5
        self.signals: list[int] = []
        self.process = subprocess.Popen(
            [PYTHON, "-I", "-S", str(FIXTURE.resolve()), mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            env=ENVIRONMENT.copy(),
            bufsize=0,
            start_new_session=True,
        )
        try:
            assert self.process.stdin is not None and self.process.stdout is not None
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
        except BaseException:
            # __enter__ has not run yet, so constructor failure owns cleanup.
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("owned-fixture-watchdog")
        return remaining

    def _wait(self, pipe, event: int, timeout: float | None = None) -> None:
        remaining = self._remaining()
        if timeout is not None:
            remaining = min(remaining, timeout)
        with selectors.DefaultSelector() as selector:
            selector.register(pipe, event)
            if not selector.select(remaining):
                raise TimeoutError("owned-fixture-io-timeout")

    def write(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            self._wait(self.process.stdin, selectors.EVENT_WRITE)
            try:
                count = os.write(self.process.stdin.fileno(), view)
            except BlockingIOError:
                continue
            assert count > 0
            view = view[count:]

    def read(self, *, timeout: float | None = None) -> bytes:
        self._wait(self.process.stdout, selectors.EVENT_READ, timeout)
        return os.read(self.process.stdout.fileno(), 65536)

    def read_exact(self, count: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < count:
            self._wait(self.process.stdout, selectors.EVENT_READ)
            chunk = os.read(self.process.stdout.fileno(), count - len(chunks))
            assert chunk, "owned fixture closed before its synchronization boundary"
            chunks.extend(chunk)
        return bytes(chunks)

    def finish(self, inbox: wire.RpcInbox) -> None:
        while chunk := self.read():
            inbox.feed(chunk)
        inbox.finish()
        if self.process.wait(timeout=self._remaining()) != 0:
            raise RuntimeError("owned-fixture-nonzero-exit")

    def _signal_live_owned_group(self, signum: int) -> None:
        if self.process.poll() is not None:
            return
        try:
            # start_new_session gives this single owned process its own group.
            assert os.getpgid(self.process.pid) == self.process.pid
            os.killpg(self.process.pid, signum)
            self.signals.append(signum)
        except ProcessLookupError:
            pass

    def close(self) -> None:
        try:
            if self.process.poll() is None:
                self._signal_live_owned_group(signal.SIGTERM)
                try:
                    self.process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    self._signal_live_owned_group(signal.SIGKILL)
                    self.process.wait(timeout=1)
            else:
                self.process.wait(timeout=1)
        finally:
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe is not None:
                    pipe.close()


def _initialize(peer: _OwnedPeer, inbox: wire.RpcInbox, *, split_request=False) -> None:
    inbox.arm(1)
    request = _frame(
        {
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "owned-fixture", "version": "0.153.0"}},
        }
    )
    if split_request:
        peer.write(request[:9])
        peer.write(request[9:])
    else:
        peer.write(request)
    result = None
    while result is None:
        chunk = peer.read()
        assert chunk, "owned fixture exited before initialization"
        inbox.feed(chunk)
        result = inbox.take_result()
    assert result == INITIALIZED
    assert inbox.drain_notifications() == ()
    peer.write(_frame({"method": "initialized"}))


def _request(peer: _OwnedPeer, inbox: wire.RpcInbox) -> None:
    inbox.arm(2)
    peer.write(_frame({"id": 2, "method": "config/read", "params": {"includeLayers": False}}))


def _process_reaped(process: subprocess.Popen) -> None:
    assert process.returncode is not None
    assert process.stdin.closed and process.stdout.closed
    with pytest.raises(ChildProcessError):
        os.waitpid(process.pid, os.WNOHANG)


def _reaped(peer: _OwnedPeer) -> None:
    _process_reaped(peer.process)


@pytest.mark.parametrize("failure_on,error", [(1, OSError), (2, KeyboardInterrupt)])
def test_owned_pipe_setup_failure_closes_and_reaps_before_enter(
    tmp_path, monkeypatch, failure_on, error
):
    guarded_popen = subprocess.Popen
    original_set_blocking = os.set_blocking
    started = []
    calls = 0

    def record_popen(*args, **kwargs):
        process = guarded_popen(*args, **kwargs)
        started.append(process)
        return process

    def fail_setup(fd, blocking):
        nonlocal calls
        calls += 1
        if calls == failure_on:
            raise error("owned-fixture-setup-failure")
        return original_set_blocking(fd, blocking)

    monkeypatch.setattr(subprocess, "Popen", record_popen)
    monkeypatch.setattr(os, "set_blocking", fail_setup)
    with pytest.raises(error, match="owned-fixture-setup-failure"):
        _OwnedPeer("wait", tmp_path)
    assert calls == failure_on
    assert len(started) == 1
    _process_reaped(started[0])


def test_owned_pipe_initialization_and_serial_response(tmp_path, capfd):
    inbox = wire.RpcInbox()
    with _OwnedPeer("success", tmp_path) as peer:
        _initialize(peer, inbox, split_request=True)
        _request(peer, inbox)
        peer.finish(inbox)
        assert inbox.take_result() == RESULT
        assert peer.process.returncode == 0
        assert peer.process.stderr is None
    _reaped(peer)
    assert not list(tmp_path.iterdir())
    assert "OWNED_FIXTURE_STDERR" not in "".join(capfd.readouterr())


def test_owned_pipe_waits_for_fragmented_utf8_and_complete_line(tmp_path):
    inbox = wire.RpcInbox()
    payload = _frame({"id": 2, "result": RESULT})
    split = payload.index("한".encode()) + 1
    with _OwnedPeer("fragmented", tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        first = peer.read_exact(split)
        assert first == payload[:split]
        inbox.feed(first)
        assert inbox.take_result() is None
        # This private fixture-only synchronization is not an app-server RPC.
        peer.write(b"fixture-release-fragment\n")
        peer.finish(inbox)
        assert inbox.take_result() == RESULT
    _reaped(peer)


def test_owned_pipe_coalesced_notification_and_response(tmp_path):
    inbox = wire.RpcInbox()
    payload = _ready("coalesced") + _frame({"id": 2, "result": RESULT})
    with _OwnedPeer("coalesced", tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        captured = peer.read_exact(len(payload))
        assert captured == payload
        inbox.feed(captured)
        assert inbox.take_result() == RESULT
        assert inbox.drain_notifications() == (
            {
                "method": "thread/status/changed",
                "params": {"threadId": "synthetic-coalesced", "status": {"type": "idle"}},
            },
        )
        peer.finish(inbox)
    _reaped(peer)


@pytest.mark.parametrize(
    "mode,code",
    [
        ("truncated", "truncated-frame"),
        ("malformed", "invalid-json"),
        ("invalid-utf8", "invalid-utf8"),
        ("warning", "notification-rejected"),
        ("foreign", "response-id-mismatch"),
        ("duplicate", "duplicate-response"),
        ("request-error", "rpc-error"),
        ("eof", "missing-response"),
    ],
)
def test_owned_pipe_bad_receive_is_terminal_and_child_reaped(tmp_path, mode, code):
    inbox = wire.RpcInbox()
    with _OwnedPeer(mode, tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        with pytest.raises(wire.JsonlError) as raised:
            peer.finish(inbox)
        assert raised.value.code == code
        assert "PRIVATE_FIXTURE_TEXT" not in str(raised.value)
        with pytest.raises(wire.JsonlError, match="terminal-budget"):
            inbox.feed(b"")
    _reaped(peer)


def test_owned_pipe_valid_result_does_not_hide_nonzero_exit(tmp_path):
    inbox = wire.RpcInbox()
    with _OwnedPeer("nonzero", tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        with pytest.raises(RuntimeError, match="owned-fixture-nonzero-exit"):
            peer.finish(inbox)
        assert inbox.take_result() == RESULT
        assert peer.process.returncode == 7
    _reaped(peer)


def test_owned_pipe_timeout_after_ready_terminates_and_reaps(tmp_path):
    inbox = wire.RpcInbox()
    with (
        pytest.raises(TimeoutError, match="owned-fixture-io-timeout"),
        _OwnedPeer("wait", tmp_path) as peer,
    ):
        _initialize(peer, inbox)
        _request(peer, inbox)
        inbox.feed(peer.read_exact(len(_ready("wait"))))
        assert inbox.drain_notifications()[0]["params"] == {
            "threadId": "synthetic-wait",
            "status": {"type": "idle"},
        }
        assert inbox.take_result() is None
        peer.read(timeout=0.2)
    assert signal.SIGTERM in peer.signals
    _reaped(peer)


def test_owned_pipe_cancellation_after_ready_terminates_and_reaps(tmp_path):
    inbox = wire.RpcInbox()
    with pytest.raises(KeyboardInterrupt), _OwnedPeer("wait", tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        inbox.feed(peer.read_exact(len(_ready("wait"))))
        assert inbox.drain_notifications()[0]["params"] == {
            "threadId": "synthetic-wait",
            "status": {"type": "idle"},
        }
        raise KeyboardInterrupt
    assert signal.SIGTERM in peer.signals
    _reaped(peer)


def test_owned_pipe_closed_input_reports_broken_pipe_and_reaps(tmp_path):
    inbox = wire.RpcInbox()
    with _OwnedPeer("broken-pipe", tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        inbox.feed(peer.read_exact(len(_ready("broken-pipe"))))
        assert inbox.drain_notifications()[0]["params"] == {
            "threadId": "synthetic-broken-pipe",
            "status": {"type": "idle"},
        }
        with pytest.raises(BrokenPipeError):
            peer.write(b"fixture-input-after-reader-closed\n")
    _reaped(peer)


def test_owned_pipe_cleanup_escalates_only_its_term_ignoring_child(tmp_path):
    inbox = wire.RpcInbox()
    with _OwnedPeer("ignore-term", tmp_path) as peer:
        _initialize(peer, inbox)
        _request(peer, inbox)
        inbox.feed(peer.read_exact(len(_ready("ignore-term"))))
        assert inbox.drain_notifications()[0]["params"] == {
            "threadId": "synthetic-ignore-term",
            "status": {"type": "idle"},
        }
    assert peer.signals == [signal.SIGTERM, signal.SIGKILL]
    assert peer.process.returncode == -signal.SIGKILL
    _reaped(peer)
