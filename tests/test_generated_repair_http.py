"""Pure fake-stream observations: no application, socket, worker, or provider."""

from __future__ import annotations

import ast
import asyncio
import base64
import builtins
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError
from authzest.runner._generated_repair_http import (
    HOST,
    PORT,
    FixedRequest,
    HTTPProfileError,
    HTTPResponseParser,
    capture_fixed_http,
    encode_request,
    fixed_requests,
)
from authzest.runner._generated_repair_relay import compare_generated_repair_relay_capture
from authzest.runner.generated_repair_controls import build_generated_repair_controls


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    """These scripted stream tests cannot silently become application execution."""
    assert ast.unparse(ast.Constant(value=None)) == "None"
    original_import = builtins.__import__
    original_compile = builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("HTTP relay tests require inert memory streams only")

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


def _wire(body=b"{}", status=200):
    return (
        f"HTTP/1.1 {status} OK\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
        + body
    )


class _Stream:
    def __init__(self, wire):
        self.wire = wire
        self.closed = False
        self.sent = []
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def sendall(self, request):
        self.sent.append(request)

    def recv(self, maximum):
        answer, self.wire = self.wire[:maximum], self.wire[maximum:]
        return answer

    def close(self):
        self.closed = True


def test_fixed_request_projection_contains_only_inputs():
    requests = fixed_requests()
    assert len(requests) == 21
    assert len({request.request_id for request in requests}) == 21
    assert requests[0] == FixedRequest(
        "owner-alice/1", "/documents/doc-alice", (("x-demo-actor", "alice"),)
    )
    encoded = encode_request(requests[0])
    assert encoded.startswith(b"GET /documents/doc-alice HTTP/1.1\r\n")
    assert b"Connection: close\r\nAccept-Encoding: identity\r\n" in encoded
    with pytest.raises(HTTPProfileError):
        encode_request(FixedRequest("owner-alice/1", "https://example.invalid", ()))


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 4096])
def test_parser_handles_every_boundary_and_binary_body(chunk_size):
    body = b"\x00\xff\r\n{}"
    parser = HTTPResponseParser(fixed_requests()[0].request_id)
    wire = _wire(body)
    for offset in range(0, len(wire), chunk_size):
        parser.feed(wire[offset : offset + chunk_size])
    fact = parser.finish()
    assert fact["status_code"] == 200
    assert base64.b64decode(fact["body_base64"]) == body
    with pytest.raises(HTTPProfileError):
        parser.finish()


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_fake_capture_compares_only_on_host_and_stays_unverified(candidate):
    controls = build_generated_repair_controls()
    requests = [row for case in controls.to_dict()["cases"] for row in case["requests"]]
    streams = []

    def factory(host, port, timeout):
        assert (host, port, timeout) == (HOST, PORT, 40)
        expected = requests[len(streams)][f"expected_{candidate}"]
        body = json.dumps(expected["body_json"], separators=(",", ":")).encode()
        stream = _Stream(_wire(body, expected["status_code"]))
        streams.append(stream)
        return stream

    capture = capture_fixed_http(stream_factory=factory, phase_deadline=50, clock=lambda: 10)
    assert capture.to_dict()["status"] == "complete"
    assert capture.to_dict()["call_count"] == 42
    assert len(streams) == 21 and all(stream.closed for stream in streams)
    assert [stream.sent for stream in streams] == [
        [encode_request(row)] for row in fixed_requests()
    ]
    result = compare_generated_repair_relay_capture(
        capture.payload_json, controls, candidate=candidate
    ).to_dict()
    assert result["matches_expected_profile"] is True
    assert result["execution_status"] == "not-established"
    assert result["provenance"] == "caller-supplied-unverified"
    assert result["authorization_status"] == "unknown"
    assert result["verified_fix"] is False


def test_partial_capture_cannot_reach_comparator():
    stream = _Stream(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nx")
    capture = capture_fixed_http(
        stream_factory=lambda *_: stream, phase_deadline=40, clock=lambda: 0
    )
    assert capture.to_dict()["failure"] == "http-truncated"
    assert capture.to_dict()["close_status"] == "closed"
    assert stream.closed
    with pytest.raises(ContractError):
        compare_generated_repair_relay_capture(
            capture.payload_json, build_generated_repair_controls(), candidate="after"
        )
