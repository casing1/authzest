"""Image-entry source checked with trusted memory-only tool/socket collaborators."""

from __future__ import annotations

import ast
import asyncio
import builtins
import os
import socket
import subprocess
from enum import IntEnum
from pathlib import Path

import pytest
from runtime.generated_repair import _guest_common as common
from runtime.generated_repair import app_launcher, relay_launcher, test_launcher

from authzest.runner import _generated_repair_http as codec


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    assert ast.unparse(ast.Constant(value=None)) == "None"
    original_import, original_compile = builtins.__import__, builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Guest source tests require fake collaborators only")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app",
            "docker",
            "fastapi",
            "httpx",
            "openai",
            "pytest",
            "requests",
            "uvicorn",
        }:
            forbidden()
        return original_import(name, *args, **kwargs)

    def ast_only_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)
    for name in ("open", "eval", "exec"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_diagnostic_guard_and_clean_environment():
    path = "/opt/authzest-guest/test_launcher.py"
    assert common.entry_allowed(
        "T",
        script_path=path,
        argv=[path],
        platform="linux",
        isolated=1,
        dont_write_bytecode=True,
        uid=65532,
        gid=65532,
    )
    env = {"PYTEST_ADDOPTS": "malicious", "HTTP_PROXY": "http://invalid"}
    search = ["", ".", "/input", "/input/tests", "/opt/authzest-guest", "/usr/lib/python3"]
    common.prepare_environment(env, search)
    assert env == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    assert search == ["/opt/authzest-guest", "/usr/lib/python3"]


def test_fixed_test_arguments_and_native_exit_enum():
    class ExitCode(IntEnum):
        FAILED = 1

    seen = []

    def fake_pytest(args, plugins):
        assert plugins == []
        seen.append(args)
        return ExitCode.FAILED

    assert test_launcher.run_test(fake_pytest) == 1
    assert seen == [list(test_launcher.PYTEST_ARGS)]
    assert "--noconftest" in seen[0] and "--import-mode=importlib" in seen[0]
    assert seen[0][-1] == "/input/tests/test_generated_ownership.py"


def test_fixed_independent_server_configuration():
    seen = []
    app_launcher.run_app(lambda *args, **kwargs: seen.append((args, kwargs)))
    args, config = seen[0]
    assert args == ("app:app",)
    assert config["app_dir"] == "/input"
    assert config["host"] == "127.0.0.1" and config["port"] == 8765
    assert config["workers"] == 1 and config["reload"] is False
    assert config["proxy_headers"] is False and config["env_file"] is None
    assert config["lifespan"] == "off" and config["ws"] == "none"


class FakeSocket:
    def __init__(self):
        self.calls = []
        self.wire = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        self.closed = False

    def settimeout(self, timeout):
        self.calls.append(("timeout", timeout))

    def connect(self, endpoint):
        self.calls.append(("connect", endpoint))

    def sendall(self, raw):
        self.calls.append(("send", raw))

    def recv(self, count):
        raw, self.wire = self.wire[:count], self.wire[count:]
        return raw

    def close(self):
        self.closed = True


def test_fixed_relay_fake_sockets_and_bounded_json_output():
    sockets = []

    def factory(family, kind):
        assert (family, kind) == (2, 1)
        stream = FakeSocket()
        sockets.append(stream)
        return stream

    result = relay_launcher.capture_relay(
        40000, codec=codec, socket_factory=factory, af_inet=2, sock_stream=1, clock=lambda: 1000
    )
    data = result.to_dict()
    assert data["status"] == "complete" and len(sockets) == 21
    assert all(stream.closed for stream in sockets)
    assert all(("connect", ("127.0.0.1", 8765)) in stream.calls for stream in sockets)
    assert data["verified_fix"] is False and data["execution_status"] == "not-established"
    output = []
    assert relay_launcher.emit_capture(result, lambda raw: output.append(raw) or len(raw)) == 0
    assert output == [result.payload_json.encode()]
    assert len(output[0]) <= 262144


def test_repository_entry_paths_are_not_executable_guest_locations():
    assert test_launcher._script_main() == 64
    assert app_launcher._script_main() == 64
    assert relay_launcher._script_main() == 64


def test_reusing_a_raw_socket_cannot_forge_fresh_request_connections():
    stream = FakeSocket()
    result = relay_launcher.capture_relay(
        40000,
        codec=codec,
        socket_factory=lambda *_: stream,
        af_inet=2,
        sock_stream=1,
        clock=lambda: 1000,
    ).to_dict()
    assert result["status"] == "partial" and len(result["facts"]) == 1
    assert result["failed_request_index"] == 1 and stream.closed
    assert len([row for row in stream.calls if row[0] == "connect"]) == 1
