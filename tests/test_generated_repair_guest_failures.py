"""Adversarial fake-only checks; no real guest, socket, pytest or generated import."""

from __future__ import annotations

import builtins
import inspect
from types import SimpleNamespace

import pytest
from runtime.generated_repair import _guest_common as common
from runtime.generated_repair import app_launcher, relay_launcher, test_launcher

from authzest.runner import _generated_repair_http as codec
from test_generated_repair_guest import FakeSocket, no_external_effects  # noqa: F401


def _entry(role="T"):
    name = {"T": "test", "A": "app", "B": "relay"}[role]
    path = f"/opt/authzest-guest/{name}_launcher.py"
    return {
        "script_path": path,
        "argv": [path, "1000"] if role == "B" else [path],
        "platform": "linux",
        "isolated": 1,
        "dont_write_bytecode": True,
        "uid": 65532,
        "gid": 65532,
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("script_path", "/tmp/test_launcher.py"),
        ("script_path", "/opt/authzest-guest/../test_launcher.py"),
        ("argv", []),
        ("argv", ["/opt/authzest-guest/test_launcher.py", "arbitrary.py"]),
        ("argv", ("/opt/authzest-guest/test_launcher.py",)),
        ("platform", "darwin"),
        ("isolated", 0),
        ("isolated", 1.0),
        ("dont_write_bytecode", False),
        ("uid", 0),
        ("uid", True),
        ("gid", 0),
        ("gid", True),
    ],
)
def test_entry_refuses_unsupported_layout_and_types(key, value):
    entry = _entry()
    entry[key] = value
    assert common.entry_allowed("T", **entry) is False


@pytest.mark.parametrize("role", [None, True, "", "t", "C"])
def test_unknown_role_never_dispatches(role):
    assert common.entry_allowed(role, **_entry()) is False


@pytest.mark.parametrize(
    "value",
    [None, True, 0, "", "0", "-1", "+1", "01", "40001", "1.0", "1e3", " 1", "1\n", "١"],
)
def test_noncanonical_remaining_duration_is_refused(value):
    with pytest.raises(ValueError, match="guest-duration"):
        relay_launcher.parse_remaining_ms(value)
    if type(value) is str:
        entry = _entry("B")
        entry["argv"][1] = value
        assert common.entry_allowed("B", **entry) is False


@pytest.mark.parametrize("value", ["1", "999", "40000"])
def test_guest_budget_is_only_a_bounded_duration(value):
    assert relay_launcher.parse_remaining_ms(value) == int(value)
    entry = _entry("B")
    entry["argv"][1] = value
    assert common.entry_allowed("B", **entry)


@pytest.mark.parametrize("value", [True, False, None, -1, 6, 1.0, "0"])
def test_unexpected_pytest_return_is_not_normalized_to_success(value):
    with pytest.raises(ValueError, match="guest-test-exit-contract"):
        test_launcher.run_test(lambda _, **__: value)


def test_async_pytest_server_and_clock_are_closed_not_awaited():
    async def pending():
        pytest.fail("a fake async collaborator must never run")

    test = pending()
    server = pending()
    clock = pending()
    with pytest.raises(ValueError):
        test_launcher.run_test(lambda _, **__: test)
    with pytest.raises(ValueError):
        app_launcher.run_app(lambda *_, **__: server)
    with pytest.raises(ValueError):
        _capture(clock=lambda: clock)
    assert all(
        inspect.getcoroutinestate(value) == inspect.CORO_CLOSED for value in (test, server, clock)
    )


def _capture(*, socket_factory=lambda *_: FakeSocket(), clock=lambda: 9000, **overrides):
    parameters = {
        "remaining_ms": 10000,
        "codec": codec,
        "socket_factory": socket_factory,
        "af_inet": 2,
        "sock_stream": 1,
        "clock": clock,
    }
    parameters.update(overrides)
    return relay_launcher.capture_relay(**parameters)


@pytest.mark.parametrize("value", [True, 0, -1, 40001, 1000.0, "1000", None])
def test_invalid_capture_budget_has_no_socket_effect(value):
    def forbidden(*_):
        pytest.fail("invalid budget must not allocate a socket")

    with pytest.raises(ValueError):
        _capture(remaining_ms=value, socket_factory=forbidden)


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), 2**4096, None])
def test_invalid_clock_has_no_socket_effect(value):
    def forbidden(*_):
        pytest.fail("invalid initial clock must not allocate a socket")

    with pytest.raises(ValueError):
        _capture(clock=lambda: value, socket_factory=forbidden)


@pytest.mark.parametrize("key", ["af_inet", "sock_stream"])
@pytest.mark.parametrize("value", [True, 0, 2.0, "2", None])
def test_socket_family_cannot_select_other_protocol(key, value):
    with pytest.raises(ValueError, match="guest-address-family"):
        _capture(**{key: value})


@pytest.mark.parametrize("operation", ["settimeout", "connect", "sendall", "recv"])
@pytest.mark.parametrize("exception", [OSError, KeyboardInterrupt, SystemExit])
def test_owned_socket_closes_once_on_setup_io_failure_and_cancellation(operation, exception):
    socket = FakeSocket()
    closed = []

    def fail(*_):
        raise exception("not-for-output")

    def close():
        closed.append(True)

    setattr(socket, operation, fail)
    socket.close = close
    result = _capture(socket_factory=lambda *_: socket).to_dict()
    assert result["status"] == "partial" and result["facts"] == []
    assert result["close_status"] == "closed" and closed == [True]
    assert "not-for-output" not in str(result)
    if exception is not OSError:
        assert result["cancellation"] == exception.__name__


def test_connect_and_close_failures_remain_separate():
    socket = FakeSocket()

    def connect(*_):
        raise OSError("connect")

    def close():
        raise OSError("close")

    socket.connect, socket.close = connect, close
    result = _capture(socket_factory=lambda *_: socket).to_dict()
    assert result["failure"] == "send-failed"
    assert result["close_failure"] == "close-failed"
    assert result["close_status"] == "unconfirmed"
    assert result["status"] == "partial"


def test_connection_consumes_same_deadline_and_resets_send_timeout_to_remaining_only():
    current = [9000]
    sockets = []

    def factory(*_):
        socket = FakeSocket()
        original = socket.connect
        first = not sockets

        def connect(endpoint):
            original(endpoint)
            if first:
                current[0] += 9

        socket.connect = connect
        sockets.append(socket)
        return socket

    result = _capture(socket_factory=factory, clock=lambda: current[0]).to_dict()
    assert result["status"] == "complete"
    assert sockets[0].calls[-2][0] == "timeout"
    assert sockets[0].calls[-2][1] == 1
    assert all(timeout <= 1 for kind, timeout in sockets[1].calls if kind == "timeout")
    assert sum(kind == "connect" for kind, _ in sockets[0].calls) == 1


def test_expiry_during_connect_refuses_send_and_still_closes():
    current = [9000]
    socket = FakeSocket()

    def connect(_):
        current[0] += 10

    socket.connect = connect
    result = _capture(socket_factory=lambda *_: socket, clock=lambda: current[0]).to_dict()
    assert result["status"] == "partial" and socket.closed
    assert not any(kind == "send" for kind, _ in socket.calls)
    assert result["close_status"] == "closed"


def test_factory_post_allocation_expiry_does_not_lose_socket():
    current = [9000]
    socket = FakeSocket()

    def factory(*_):
        current[0] += 10
        return socket

    result = _capture(socket_factory=factory, clock=lambda: current[0]).to_dict()
    assert result["status"] == "partial" and socket.closed
    assert not any(kind == "connect" for kind, _ in socket.calls)


@pytest.mark.parametrize("operation", ["settimeout", "connect", "sendall"])
def test_unexpected_socket_native_return_does_not_become_complete(operation):
    socket = FakeSocket()
    setattr(socket, operation, lambda *_: True)
    result = _capture(socket_factory=lambda *_: socket).to_dict()
    assert result["status"] == "partial" and socket.closed


@pytest.mark.parametrize("returned", [None, True, -1, 0, 262145])
def test_short_or_noninteger_output_write_is_not_success(returned):
    capture = codec.RelayCapture('{"status":"partial"}')
    with pytest.raises(ValueError, match="guest-output-incomplete"):
        relay_launcher.emit_capture(capture, lambda _: returned)


@pytest.mark.parametrize(
    "raw",
    ["not-json", "null", "[]", '{"status":"other"}', '"text"', "[" * 1000 + "]" * 1000],
    ids=["malformed", "null", "array", "status", "string", "deep"],
)
def test_malformed_capture_is_not_written(raw):
    writes = []
    with pytest.raises(ValueError):
        relay_launcher.emit_capture(codec.RelayCapture(raw), lambda data: writes.append(data))
    assert writes == []


def test_unicode_output_budget_is_checked_in_bytes_before_write():
    writes = []
    raw = '{"status":"partial","data":"' + "가" * 90000 + '"}'
    with pytest.raises(ValueError, match="guest-output-budget"):
        relay_launcher.emit_capture(codec.RelayCapture(raw), lambda data: writes.append(data))
    assert writes == []


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_entry_wiring_imports_only_fake_dependencies_after_environment_cleanup(monkeypatch, role):
    module = {"T": test_launcher, "A": app_launcher, "B": relay_launcher}[role]
    entry = _entry(role)
    env = {"OPENAI_API_KEY": "FAKE-NOT-A-SECRET", "PYTEST_ADDOPTS": "--invalid", "HTTP_PROXY": "x"}
    events, output = [], []
    fake_sys = SimpleNamespace(
        path=["", "/input", "/input/tests", "/usr/lib/python3", "/opt/authzest-guest"],
        argv=entry["argv"],
        platform="linux",
        flags=SimpleNamespace(isolated=1),
        dont_write_bytecode=True,
        stdout=SimpleNamespace(
            buffer=SimpleNamespace(
                write=lambda data: output.append(data) or len(data),
                flush=lambda: events.append("flush"),
            )
        ),
    )
    fake_os = SimpleNamespace(environ=env, getuid=lambda: 65532, getgid=lambda: 65532)
    original = builtins.__import__

    def native_test(args, *, plugins):
        assert fake_sys.path[0] == "/input"
        assert args[-1] == "/input/tests/test_generated_ownership.py"
        assert plugins == []
        events.append("test")
        return 1

    def native_server(*args, **kwargs):
        assert "/input" not in fake_sys.path
        assert args == ("app:app",) and kwargs["app_dir"] == "/input"
        events.append("server")

    def fake_capture(*args, **kwargs):
        assert args == (1000,)
        events.append("capture")
        return codec.RelayCapture('{"status":"partial"}')

    def fake_import(name, *args, **kwargs):
        if name in {"os", "sys", "_guest_common"}:
            return {"os": fake_os, "sys": fake_sys, "_guest_common": common}[name]
        if name in {"pytest", "uvicorn", "socket", "time", "_generated_repair_http"}:
            assert env == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
            assert "/input" not in fake_sys.path and "" not in fake_sys.path
            events.append("import:" + name)
            return {
                "pytest": SimpleNamespace(main=native_test),
                "uvicorn": SimpleNamespace(run=native_server),
                "socket": SimpleNamespace(socket=None, AF_INET=2, SOCK_STREAM=1),
                "time": SimpleNamespace(monotonic=None),
                "_generated_repair_http": codec,
            }[name]
        return original(name, *args, **kwargs)

    monkeypatch.setattr(module, "__file__", entry["script_path"])
    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(relay_launcher, "capture_relay", fake_capture)
    assert module._script_main() == (1 if role in {"T", "B"} else 0)
    assert events[-1] == {"T": "test", "A": "server", "B": "flush"}[role]
    assert not any(name.startswith("import:authzest") for name in events)
