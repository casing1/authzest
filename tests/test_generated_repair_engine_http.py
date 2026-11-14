"""Fixed metadata transport with memory sockets only, never a daemon or guest."""

from __future__ import annotations

import asyncio
import builtins
import copy
import os
import socket
import stat
import subprocess
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from authzest.runner import _generated_repair_engine_http as engine
from test_generated_repair_runtime_profile import profile

PIN = {
    "socket_identity": [1, 2, stat.S_IFSOCK | 0o660, 0, 0, 1, 0, 7, 8],
    "parent_chain_sha256": "a" * 64,
}

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Unix socket source scope")


class MemorySocket:
    def __init__(self, wire=b""):
        self.wire = wire
        self.sent = []
        self.connected = []
        self.timeouts = []
        self.read_sizes = []
        self.closed = 0

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, path):
        self.connected.append(path)

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, size):
        self.read_sizes.append(size)
        result, self.wire = self.wire[:size], self.wire[size:]
        return result

    def close(self):
        self.closed += 1


def response(body=b'{"synthetic":true}', framing="length"):
    header = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
    if framing == "length":
        return header + b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    if framing == "chunked":
        chunks = b"".join(
            f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n"
            for chunk in (body[:3], body[3:])
            if chunk
        )
        return header + b"Transfer-Encoding: chunked\r\n\r\n" + chunks + b"0\r\n\r\n"
    return header + b"\r\n" + body


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch, request):
    assert len(request.node.nodeid) < 512
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        pytest.fail("Engine HTTP tests use only maintained data and a memory socket")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app",
            "docker",
            "fastapi",
            "httpx",
            "openai",
            "requests",
            "uvicorn",
        } or name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for name in ("eval", "exec", "compile", "open"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


@pytest.fixture
def memory(monkeypatch):
    made = []

    def use(wire):
        connection = MemorySocket(wire)

        def create(*args, **kwargs):
            made.append((args, kwargs))
            return connection

        monkeypatch.setattr(socket, "socket", create)
        return connection

    monkeypatch.setattr(engine.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: copy.deepcopy(PIN))
    use.made = made
    return use


@pytest.mark.parametrize("operation", ["version", "info", "image-T", "image-A", "image-B"])
@pytest.mark.parametrize("framing", ["length", "chunked", "close"])
def test_fixed_requests_and_bounded_memory_responses(memory, operation, framing):
    body = b'{"synthetic":true}'
    wire = response(body, framing)
    connection = memory(wire)
    budget = engine.WireBudget()
    result = engine.read_engine(profile(), operation, deadline=109.0, budget=budget)
    assert result == engine.EngineResponse(operation, body, len(wire), PIN)
    assert budget.used == len(wire)
    assert connection.closed == 1
    assert connection.connected == ["/reviewed/run/docker.sock"]
    assert memory.made == [((socket.AF_UNIX, socket.SOCK_STREAM), {})]
    target = "/version" if operation == "version" else "/v1.45"
    if operation == "info":
        target += "/info"
    elif operation.startswith("image-"):
        target += "/images/" + profile().to_dict()["images"][operation[-1]]["image_id"] + "/json"
    assert connection.sent == [
        (
            "GET " + target + " HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\n"
            "Connection: close\r\n\r\n"
        ).encode()
    ]
    assert all(0 < value <= 9 for value in connection.timeouts)
    assert all(0 < value <= 4096 for value in connection.read_sizes)
    with pytest.raises(FrozenInstanceError):
        result.operation = "info"


def test_wire_budget_is_shared_across_separate_fixed_queries(memory):
    wire = response()
    budget = engine.WireBudget()
    for operation in ("version", "info", "image-T", "image-A", "image-B"):
        connection = memory(wire)
        engine.read_engine(profile(), operation, deadline=109.0, budget=budget)
        assert connection.closed == 1
    assert budget.used == 5 * len(wire)


def test_one_original_deadline_is_passed_to_each_socket_operation(memory, monkeypatch):
    connection = memory(response())
    now = [100.0]
    original = connection.connect

    def connect(path):
        original(path)
        now[0] += 2.0

    monkeypatch.setattr(connection, "connect", connect)
    monkeypatch.setattr(engine.time, "monotonic", lambda: now[0])
    engine.read_engine(profile(), "version", deadline=109.0, budget=engine.WireBudget())
    assert connection.timeouts[0] == 9
    assert all(value == 7 for value in connection.timeouts[1:])


def test_guard_and_endpoint_rechecks_precede_contact_and_follow_closure(memory, monkeypatch):
    events = []
    connection = memory(response())
    original_connect, original_close = connection.connect, connection.close

    def pin(path):
        events.append("pin")
        return copy.deepcopy(PIN)

    def connect(path):
        events.append("connect")
        original_connect(path)

    def close():
        events.append("close")
        original_close()

    monkeypatch.setattr(engine, "_endpoint_identity", pin)
    monkeypatch.setattr(connection, "connect", connect)
    monkeypatch.setattr(connection, "close", close)
    engine.read_engine(
        profile(),
        "version",
        deadline=109.0,
        budget=engine.WireBudget(),
        before_connect=lambda: events.append("guard"),
    )
    assert events == ["pin", "guard", "pin", "connect", "close", "pin"]


def test_endpoint_observes_bounded_parent_cores_and_full_socket_identity(monkeypatch):
    def value(mode, inode):
        return SimpleNamespace(
            st_dev=1,
            st_ino=inode,
            st_mode=mode,
            st_uid=0,
            st_gid=0,
            st_nlink=1,
            st_size=0,
            st_mtime_ns=7,
            st_ctime_ns=8,
        )

    facts = {
        "/": value(stat.S_IFDIR | 0o755, 1),
        "/reviewed": value(stat.S_IFDIR | 0o755, 2),
        "/reviewed/run": value(stat.S_IFDIR | 0o700, 3),
        "/reviewed/run/docker.sock": value(stat.S_IFSOCK | 0o660, 4),
    }
    names = []

    def lstat(path):
        names.append(path)
        return facts[path]

    monkeypatch.setattr(os, "lstat", lstat)
    result = engine._endpoint_identity("/reviewed/run/docker.sock")
    assert names == list(facts)
    assert result["socket_identity"] == [1, 4, stat.S_IFSOCK | 0o660, 0, 0, 1, 0, 7, 8]
    assert len(result["parent_chain_sha256"]) == 64
