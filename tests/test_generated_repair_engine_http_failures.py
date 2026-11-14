"""In-memory Engine refusal tests; never connect to a socket or execute code."""

from __future__ import annotations

import asyncio
import inspect
import os
import stat
import subprocess
from copy import deepcopy
from types import SimpleNamespace

import pytest

from authzest.runner import _generated_repair_engine_http as engine
from test_generated_repair_runtime_profile import profile

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX Engine socket transport")
_REAL_ENDPOINT_IDENTITY = engine._endpoint_identity
PIN = {
    "socket_identity": [1, 2, stat.S_IFSOCK | 0o600, 0, 0, 1, 0, 10, 10],
    "parent_chain_sha256": "a" * 64,
}


def response(headers=b"Content-Length: 2\r\n", body=b"{}", status=b"HTTP/1.1 200 OK"):
    return status + b"\r\nContent-Type: application/json\r\n" + headers + b"\r\n" + body


class MemorySocket:
    def __init__(self, wire):
        self.wire, self.closed, self.connected = wire, False, False
        self.sent, self.timeouts = [], []

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, path):
        self.connected = True

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, maximum):
        result, self.wire = self.wire[:maximum], self.wire[maximum:]
        return result

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def no_real_boundaries(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Only maintained in-memory Engine socket fakes may run")

    monkeypatch.setattr(engine.socket, "socket", forbidden)
    monkeypatch.setattr(engine.socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: deepcopy(PIN))
    monkeypatch.setattr(engine.time, "monotonic", lambda: 100.0)


@pytest.fixture
def installed(monkeypatch):
    def install(wire):
        fake = MemorySocket(wire)
        monkeypatch.setattr(engine.socket, "socket", lambda *args, **kwargs: fake)
        return fake

    return install


@pytest.mark.parametrize(
    "wire",
    [
        response(status=b"HTTP/1.1 302 Found"),
        response(status=b"HTTP/1.1 500 Error"),
        response(status=b"HTTP/2 200 OK"),
        response().replace(b"\r\n", b"\n"),
        response(b"Content-Length: 2\r\ncontent-length: 2\r\n"),
        response(b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n"),
        response(b"Content-Length: -1\r\n"),
        response(b"Content-Length: true\r\n"),
        response(b"Content-Length: 3\r\n"),
        response(b"Content-Length: 1\r\n"),
        response(b"Content-Length: 65537\r\n"),
        response(b"Transfer-Encoding: gzip\r\n"),
        response(b"Content-Length: 2\r\nContent-Encoding: gzip\r\n"),
        response(b"Content-Length: 2\r\n X-Folded: bad\r\n"),
        response(b"Content-Length: 2\r\nBad Header: bad\r\n"),
        response(b"Content-Length: 2\r\nX-Control: a\x00b\r\n"),
        response().replace(b"application/json", b"text/plain"),
        response(b"Transfer-Encoding: chunked\r\n", b"z\r\n{}\r\n0\r\n\r\n"),
        response(b"Transfer-Encoding: chunked\r\n", b"2;ext=x\r\n{}\r\n0\r\n\r\n"),
        response(b"Transfer-Encoding: chunked\r\n", b"2\r\n{}xx0\r\n\r\n"),
        response(b"Transfer-Encoding: chunked\r\n", b"2\r\n{}\r\n0\r\nX: y\r\n\r\n"),
        response(b"Transfer-Encoding: chunked\r\n", b"2\r\n{}\r\n"),
        response(b"", b"x" * 65537),
        response(body=b"{}extra"),
        response(b"X-Large: " + b"x" * 16384 + b"\r\n"),
        response(b"".join(b"X-" + str(n).encode() + b": y\r\n" for n in range(33))),
    ],
)
def test_unsupported_or_ambiguous_response_never_returns_evidence(installed, wire):
    fake = installed(wire)
    budget = engine.WireBudget()
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(profile(), "version", deadline=105.0, budget=budget)
    assert fake.closed and fake.connected and len(fake.sent) == 1
    assert caught.value.diagnostic["contact_attempted"] is True
    assert caught.value.diagnostic["socket_cleanup"] == "confirmed"
    assert 0 < budget.used <= engine.MAX_WIRE_BYTES


@pytest.mark.parametrize("deadline", [True, None, float("nan"), float("inf"), 99.0, 111.0])
def test_invalid_deadline_refuses_before_socket_acquisition(deadline):
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(profile(), "version", deadline=deadline, budget=engine.WireBudget())
    assert caught.value.diagnostic["contact_attempted"] is False


@pytest.mark.parametrize("operation", [None, True, "", "create", "info?x=y", "image-C"])
def test_no_caller_selected_operation_or_path(operation):
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(profile(), operation, deadline=105.0, budget=engine.WireBudget())
    assert caught.value.diagnostic["contact_attempted"] is False


@pytest.mark.parametrize("used", [True, -1, engine.MAX_WIRE_BYTES + 1])
def test_invalid_shared_budget_refuses_before_contact(used):
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(profile(), "version", deadline=105.0, budget=engine.WireBudget(used))
    assert caught.value.diagnostic["contact_attempted"] is False


def test_wire_budget_is_not_reset_between_queries(installed):
    wire = response()
    budget = engine.WireBudget()
    installed(wire)
    first = engine.read_engine(profile(), "version", deadline=105.0, budget=budget)
    assert first.wire_bytes == budget.used == len(wire)
    budget.used = engine.MAX_WIRE_BYTES - len(wire) + 1
    fake = installed(wire)
    with pytest.raises(engine.EngineHTTPError):
        engine.read_engine(profile(), "info", deadline=105.0, budget=budget)
    assert fake.closed and budget.used == engine.MAX_WIRE_BYTES + 1


def test_returned_chunk_larger_than_requested_is_rejected_before_accumulation(installed):
    fake = installed(b"")
    fake.recv = lambda maximum: b"x" * (maximum + 1)
    budget = engine.WireBudget()
    with pytest.raises(engine.EngineHTTPError):
        engine.read_engine(profile(), "info", deadline=105.0, budget=budget)
    assert fake.closed and 0 < budget.used <= 4097


def test_endpoint_change_after_socket_close_invalidates_body(installed, monkeypatch):
    fake = installed(response())
    calls = []

    def pin(path):
        calls.append(path)
        value = deepcopy(PIN)
        if fake.closed:
            value["socket_identity"][1] += 1
        return value

    monkeypatch.setattr(engine, "_endpoint_identity", pin)
    with pytest.raises(engine.EngineHTTPError):
        engine.read_engine(profile(), "info", deadline=105.0, budget=engine.WireBudget())
    assert fake.closed and len(calls) >= 3


def test_guard_change_is_rechecked_before_connect(installed, monkeypatch):
    fake = installed(response())
    value = deepcopy(PIN)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: deepcopy(value))

    def guard():
        value["socket_identity"][1] += 1

    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(
            profile(), "info", deadline=105.0, budget=engine.WireBudget(), before_connect=guard
        )
    assert not fake.connected and caught.value.diagnostic["contact_attempted"] is False


def test_async_guard_body_is_not_awaited(installed):
    fake = installed(response())

    async def pending():
        pytest.fail("Async guard must remain inert")

    coroutine = pending()
    with pytest.raises(engine.EngineHTTPError):
        engine.read_engine(
            profile(),
            "info",
            deadline=105.0,
            budget=engine.WireBudget(),
            before_connect=lambda: coroutine,
        )
    assert not fake.connected and inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED


@pytest.mark.parametrize("phase", ["connect", "sendall", "recv", "close"])
def test_cancellation_keeps_original_exception_and_final_cleanup(installed, phase):
    fake = installed(response())
    original_close = fake.close
    cancellation = KeyboardInterrupt("owned fake cancellation")

    def cancel(*args):
        if phase == "close":
            original_close()
        raise cancellation

    setattr(fake, phase, cancel)
    with pytest.raises(KeyboardInterrupt) as caught:
        engine.read_engine(profile(), "info", deadline=105.0, budget=engine.WireBudget())
    assert caught.value is cancellation and fake.closed
    assert caught.value.engine_http_observation["socket_cleanup"] == (
        "unconfirmed" if phase == "close" else "confirmed"
    )


def test_successful_body_cannot_hide_close_failure(installed):
    fake = installed(response())
    original = fake.close

    def close():
        original()
        raise OSError("owned close failure")

    fake.close = close
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(profile(), "info", deadline=105.0, budget=engine.WireBudget())
    assert fake.closed and caught.value.diagnostic["socket_cleanup"] == "unconfirmed"


def test_unreturned_socket_handle_is_not_reported_as_known_clean(monkeypatch):
    def acquire(*args, **kwargs):
        raise OSError("owned fake acquisition ambiguity")

    monkeypatch.setattr(engine.socket, "socket", acquire)
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine(profile(), "version", deadline=105.0, budget=engine.WireBudget())
    assert caught.value.diagnostic["contact_attempted"] is False
    assert caught.value.diagnostic["socket_cleanup"] == "unconfirmed"


def test_clock_reversal_after_receive_still_closes_socket(installed, monkeypatch):
    fake = installed(response())
    now = [100.0]
    original = fake.recv

    def read(maximum):
        value = original(maximum)
        now[0] = 99.0
        return value

    fake.recv = read
    monkeypatch.setattr(engine.time, "monotonic", lambda: now[0])
    budget = engine.WireBudget()
    with pytest.raises(engine.EngineHTTPError):
        engine.read_engine(profile(), "info", deadline=105.0, budget=budget)
    assert fake.closed and budget.used > 0


@pytest.mark.parametrize("fault", ["parent-link", "socket-link", "world-write"])
def test_endpoint_inspection_rejects_links_and_world_writable_socket(monkeypatch, fault):
    uid = os.geteuid()
    value = SimpleNamespace(
        st_dev=1,
        st_ino=2,
        st_mode=stat.S_IFDIR | 0o755,
        st_uid=uid,
        st_gid=0,
        st_nlink=1,
        st_size=0,
        st_mtime_ns=10,
        st_ctime_ns=10,
    )

    def metadata(path):
        info = deepcopy(value)
        if path == "/safe/run/docker.sock":
            info.st_mode = {
                "parent-link": stat.S_IFSOCK | 0o600,
                "socket-link": stat.S_IFLNK | 0o777,
                "world-write": stat.S_IFSOCK | 0o666,
            }[fault]
        if path == "/safe" and fault == "parent-link":
            info.st_mode = stat.S_IFLNK | 0o777
        return info

    with monkeypatch.context() as change:
        change.setattr(os, "lstat", metadata)
        with pytest.raises(ValueError):
            _REAL_ENDPOINT_IDENTITY("/safe/run/docker.sock")


@pytest.mark.parametrize("setter", [1, 2, 3])
def test_timeout_setter_cannot_dispatch_io_after_original_deadline(installed, monkeypatch, setter):
    fake = installed(response())
    now, calls = [100.0], []
    reads = []
    original_read = fake.recv

    def timeout(value):
        calls.append(value)
        if len(calls) == setter:
            now[0] = 106.0

    def read(maximum):
        reads.append(maximum)
        return original_read(maximum)

    fake.settimeout, fake.recv = timeout, read
    monkeypatch.setattr(engine.time, "monotonic", lambda: now[0])
    with pytest.raises(engine.EngineHTTPError):
        engine.read_engine(profile(), "info", deadline=105.0, budget=engine.WireBudget())
    assert fake.closed
    assert fake.connected is (setter > 1)
    assert len(fake.sent) == (1 if setter > 2 else 0)
    assert reads == []


def test_first_close_cancellation_is_not_replaced_by_postclose_pin_failure(installed, monkeypatch):
    fake = installed(response())
    original_close = fake.close
    first, later = (
        KeyboardInterrupt("first owned close cancel"),
        SystemExit("later owned pin cancel"),
    )

    def close():
        original_close()
        raise first

    def pin(path):
        if fake.closed:
            raise later
        return deepcopy(PIN)

    fake.close = close
    monkeypatch.setattr(engine, "_endpoint_identity", pin)
    with pytest.raises(KeyboardInterrupt) as caught:
        engine.read_engine(profile(), "info", deadline=105.0, budget=engine.WireBudget())
    assert caught.value is first and fake.closed
    assert first.engine_http_observation["socket_cleanup"] == "unconfirmed"
