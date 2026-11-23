"""Scheduled relay tests use inert streams and injected fake socket objects only."""

from __future__ import annotations

import ast
import asyncio
import builtins
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
from runtime.repository import relay_launcher as launcher

from authzest.runner import _repository_http as codec


def _schedule(count=4):
    return {
        "schema_version": "1.0",
        "kind": "repository-observer-schedule",
        "plan_id": "repository-verification-plan-" + "a" * 64,
        "phase": "before",
        "requests": [
            {"case_id": f"custom-{i}", "method": "GET", "path": f"/objects/{i}", "headers": {}}
            for i in range(count)
        ],
    }


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    original_import = builtins.__import__
    original_compile = builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Scheduled relay tests require inert streams only")

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


def _wire(body=b"{}", status=200, headers=None):
    if headers is None:
        headers = [("Content-Length", str(len(body)))]
    return (
        f"HTTP/1.1 {status} OK\r\n".encode()
        + b"".join(f"{key}: {value}\r\n".encode() for key, value in headers)
        + b"\r\n"
        + body
    )


class Stream:
    def __init__(self, wire, *, chunk=4096, fault=None):
        self.wire = wire
        self.chunk = chunk
        self.fault = fault
        self.closed = 0
        self.sent = []
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def sendall(self, request):
        self.sent.append(request)
        if self.fault == "send":
            raise OSError("private details")

    def recv(self, maximum):
        if self.fault == "receive":
            raise TimeoutError("private details")
        length = min(self.chunk, maximum)
        answer, self.wire = self.wire[:length], self.wire[length:]
        return answer

    def close(self):
        self.closed += 1
        if self.fault == "close":
            raise OSError("private details")


def _capture(streams, *, schedule=None, clock=lambda: 0, phase_deadline=40):
    iterator = iter(streams)
    return codec.capture_repository_http(
        schedule or _schedule(),
        stream_factory=lambda *_: next(iterator),
        clock=clock,
        phase_deadline=phase_deadline,
    ).to_dict()


def _fact(wire, case_id="custom-fact", chunk=4096):
    parser = codec.HTTPResponseParser(case_id)
    for offset in range(0, len(wire), chunk):
        parser.feed(wire[offset : offset + chunk])
    return parser.finish()


def test_schedule_is_detached_and_contains_no_oracle_fields():
    schedule = _schedule(8)
    schedule["requests"][0]["headers"] = {"x-user-id": "test-owner", "x-role": "test-admin"}
    detached = codec.validate_observer_schedule(schedule)
    detached["requests"][0]["path"] = "/different"
    assert schedule["requests"][0]["path"] == "/objects/0"
    request = codec.encode_repository_request(schedule, "custom-0")
    assert request == (
        b"GET /objects/0 HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n"
        b"Accept-Encoding: identity\r\nx-role: test-admin\r\nx-user-id: test-owner\r\n\r\n"
    )
    assert b"custom-0" not in request
    assert b"repository-verification-plan" not in request


@pytest.mark.parametrize("count", [0, 3, 9, 100])
def test_schedule_count_is_four_to_eight(count):
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_observer_schedule(_schedule(count))


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_id", "x" * 100000),
        ("case_id", ""),
        ("case_id", "bad/id"),
        ("method", "POST"),
        ("method", True),
        ("path", "//host/x"),
        ("path", "/a/../b"),
        ("path", "/./b"),
        ("path", "/a%2fb"),
        ("path", "/a?x=1"),
        ("path", "/a#x"),
        ("path", "http://host/x"),
        ("path", "/a\\b"),
        ("path", "/é"),
        ("path", "/" + "x" * 512),
        ("headers", {"Authorization": "test-value"}),
        ("headers", {"x-user": "Bearer credentials"}),
        ("headers", {"x-user": "test-a\r\nCookie: x"}),
        ("headers", {"x-role": "test-" + "x" * 60}),
        ("headers", {"X-User": "test-a"}),
    ],
    ids=[
        "oversize-case-id",
        "empty-case-id",
        "ambiguous-case-id",
        "wrong-method",
        "boolean-method",
        "authority-path",
        "parent-segment",
        "current-segment",
        "percent-path",
        "query-path",
        "fragment-path",
        "absolute-url",
        "backslash-path",
        "unicode-path",
        "oversize-path",
        "authorization-header",
        "credential-value",
        "header-injection",
        "oversize-header-value",
        "mixed-case-header",
    ],
)
def test_schedule_rejects_ambiguous_requests(field, value):
    schedule = _schedule()
    schedule["requests"][0][field] = value
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_observer_schedule(schedule)


@pytest.mark.parametrize("extra", ["expected", "before", "after", "source", "pytest", "cleanup"])
def test_schedule_rejects_oracle_and_execution_fields(extra):
    schedule = _schedule()
    schedule[extra] = {}
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_observer_schedule(schedule)


def test_schedule_duplicate_ids_keys_and_bytes_are_bounded():
    schedule = _schedule()
    schedule["requests"][1]["case_id"] = "custom-0"
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_observer_schedule(schedule)
    raw = json.dumps(_schedule()).replace('"phase": "before"', '"phase":"before","phase":"after"')
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_observer_schedule(raw)
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_observer_schedule(" " * (codec.MAX_SCHEDULE_BYTES + 1))


@pytest.mark.parametrize("chunk", [1, 2, 7, 4096])
def test_fragmentation_complete_denominator_and_close_facts(chunk):
    streams = [Stream(_wire(), chunk=chunk) for _ in range(8)]
    capture = _capture(streams, schedule=_schedule(8))
    assert capture["status"] == "complete"
    assert capture["planned_count"] == len(capture["records"]) == 8
    assert capture["recv_calls"] <= capture["wire_bytes"] + 8
    assert all(row["dispatch_status"] == "response" for row in capture["records"])
    assert all(row["close_status"] == "closed" for row in capture["records"])
    assert all(stream.closed == 1 and len(stream.sent) == 1 for stream in streams)
    assert capture["provenance"] == "caller-supplied-unverified"
    assert capture["execution_status"] == "not-established"
    assert capture["verified_fix"] is False
    assert not {"pytest", "cleanup", "T", "A", "B", "supplied_criteria_met"} & capture.keys()


@pytest.mark.parametrize("status", [204, 205, 304])
@pytest.mark.parametrize("headers", [[], [("Content-Length", "0")]])
def test_bodyless_status_accepts_only_empty_wire(status, headers):
    fact = _fact(_wire(b"", status, headers), chunk=1)
    assert codec.decode_response_fact(fact) == {"status": status, "body": {"kind": "empty"}}
    for bad in (_wire(b"{}", status), _wire(b"x", status, headers)):
        with pytest.raises(codec.HTTPProfileError):
            _fact(bad)


@pytest.mark.parametrize("value", [None, True, False, 0, 1, 1.0, -1.2, [], [1, True], {}, "문자열"])
def test_typed_body_accepts_every_json_root_and_preserves_types(value):
    body = json.dumps(value, ensure_ascii=False).encode()
    result = codec.decode_response_fact(_fact(_wire(body)))
    assert type(result["body"]["value"]) is type(value)
    assert result == {"status": 200, "body": {"kind": "json", "value": value}}


@pytest.mark.parametrize(
    "body",
    [
        b'{"a":1,"a":2}',
        b'{"nested":{"a":1,"a":2}}',
        b"NaN",
        b"Infinity",
        b"1e309",
        b"9007199254740992",
        b'"\\ud800"',
        b"\xff",
        b"not JSON",
        b"[" * 9 + b"0" + b"]" * 9,
        b"[" + b",".join([b"0"] * 128) + b"]",
        json.dumps("a" * 1025).encode(),
        json.dumps({"a" * 129: 1}).encode(),
    ],
    ids=[
        "duplicate-root-key",
        "duplicate-nested-key",
        "nan",
        "infinity",
        "overflow-float",
        "nonportable-integer",
        "surrogate",
        "invalid-utf8",
        "non-json",
        "oversize-depth",
        "oversize-nodes",
        "oversize-string",
        "oversize-key",
    ],
)
def test_invalid_body_stays_error_and_keeps_raw_fact(body):
    fact = _fact(_wire(body))
    with pytest.raises(codec.HTTPProfileError):
        codec.decode_response_fact(fact)
    streams = [Stream(_wire(body)), Stream(_wire())]
    capture = _capture(streams)
    assert capture["status"] == "partial"
    assert capture["records"][0]["fact"] == fact
    assert capture["records"][0]["error_code"] == "body-invalid"
    assert [row["dispatch_status"] for row in capture["records"]] == [
        "error",
        "not-dispatched",
        "not-dispatched",
        "not-dispatched",
    ]
    assert streams[0].closed == 1 and streams[1].closed == 0


@pytest.mark.parametrize(
    "wire",
    [
        b"HTTP/1.0 200 OK\r\nContent-Length: 0\r\n\r\n",
        b"HTTP/1.1 100 Continue\r\n\r\n",
        b"HTTP/1.1 200 OK\nContent-Length: 0\n\n",
        _wire(b"", headers=[]),
        _wire(b"", headers=[("Content-Length", "00")]),
        _wire(b"", headers=[("Content-Length", "0"), ("content-length", "0")]),
        _wire(b"", headers=[("Content-Length", "0"), ("Transfer-Encoding", "chunked")]),
        _wire(b"", headers=[("Content-Length", "0"), ("Content-Encoding", "gzip")]),
        _wire(b"", headers=[("Content-Length", "0"), ("Connection", "upgrade")]),
        _wire() + b"extra",
        _wire()[:-1],
        _wire(b"x" * 4097),
        _wire(b"", headers=[("Content-Length", "0"), ("x-long", "x" * 4096)]),
        _wire(b"", headers=[("Content-Length", "0")] + [("x-h", "a")] * 32),
    ],
    ids=[
        "http10",
        "informational",
        "bare-lf",
        "missing-length",
        "noncanonical-length",
        "duplicate-length",
        "transfer-coding",
        "compression",
        "upgrade",
        "trailing-data",
        "truncated-body",
        "oversize-body",
        "oversize-header",
        "oversize-header-count",
    ],
)
def test_strict_http_rejects_ambiguity_budgets_and_truncation(wire):
    with pytest.raises(codec.HTTPProfileError):
        _fact(wire, chunk=1)


def test_raw_fact_cannot_be_rehashed_to_bypass_http_or_typed_bounds():
    good = _fact(_wire())
    for changed in (
        {**good, "status_code": True},
        {**good, "body_base64": "e30=" + "="},
        {**good, "headers": [["Content-Length", "02"]]},
        {**good, "headers": [["Content-Length", "2\r\nCookie: x"]]},
        {**good, "headers": [["Content-Length", "2"], ["x-control", "\t"]]},
        {**good, "expected": True},
    ):
        with pytest.raises(codec.HTTPProfileError):
            codec.decode_response_fact(changed)


@pytest.mark.parametrize("fault", ["send", "receive", "close"])
def test_first_failure_keeps_full_denominator_and_never_retries(fault):
    streams = [Stream(_wire()), Stream(_wire(), fault=fault), Stream(_wire())]
    capture = _capture(streams)
    assert capture["status"] == "partial"
    assert len(capture["records"]) == 4
    assert [row["dispatch_status"] for row in capture["records"]] == [
        "response",
        "error",
        "not-dispatched",
        "not-dispatched",
    ]
    assert streams[0].closed == streams[1].closed == 1
    assert streams[2].closed == 0
    assert "private details" not in json.dumps(capture)
    assert capture["records"][1]["close_status"] == (
        "unconfirmed" if fault == "close" else "closed"
    )


def test_original_deadline_not_reset_and_late_factory_is_still_closed():
    state = {"now": 0}
    stream = Stream(_wire())

    def factory(*_):
        state["now"] = 41
        return stream

    capture = codec.capture_repository_http(
        _schedule(), stream_factory=factory, phase_deadline=40, clock=lambda: state["now"]
    ).to_dict()
    assert capture["failure"] == "deadline-expired"
    assert stream.closed == 1 and stream.sent == []
    assert len(capture["records"]) == 4
    assert capture["records"][1]["dispatch_status"] == "not-dispatched"


def test_expired_initial_deadline_keeps_full_not_dispatched_records():
    capture = _capture([], phase_deadline=40, clock=lambda: 40)
    assert capture["status"] == "partial"
    assert all(row["dispatch_status"] == "not-dispatched" for row in capture["records"])
    assert all(row["close_status"] == "not-acquired" for row in capture["records"])


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(), BaseException()])
def test_cancellation_still_closes_and_stops(interruption):
    stream = Stream(_wire())

    def interrupt(_):
        raise interruption

    stream.sendall = interrupt
    capture = _capture([stream])
    assert capture["failure"] == "capture-cancelled"
    assert capture["cancellation"] in {"KeyboardInterrupt", "SystemExit", "BaseException"}
    assert stream.closed == 1
    assert capture["records"][1]["dispatch_status"] == "not-dispatched"


def test_same_stream_is_never_sent_twice():
    stream = Stream(_wire())
    capture = _capture([stream, stream])
    assert capture["status"] == "partial"
    assert len(stream.sent) == 1 and stream.closed == 1
    assert capture["records"][0]["close_status"] == "closed"
    assert capture["records"][1]["dispatch_status"] == "error"
    assert capture["records"][1]["close_status"] == "not-acquired"
    assert capture["records"][1]["fact"] is None


def test_launcher_stdin_is_bounded_and_charged_to_existing_deadline():
    calls = []

    def read(maximum):
        calls.append(maximum)
        return json.dumps(_schedule()).encode()

    result = launcher.read_schedule(read, codec=codec, phase_deadline=40, clock=lambda: 0)
    assert result == _schedule()
    assert calls == [codec.MAX_SCHEDULE_BYTES + 1]
    with pytest.raises(ValueError):
        launcher.read_schedule(
            lambda _: b" " * (codec.MAX_SCHEDULE_BYTES + 1),
            codec=codec,
            phase_deadline=40,
            clock=lambda: 0,
        )
    times = iter([0, 40])
    with pytest.raises(TimeoutError):
        launcher.read_schedule(read, codec=codec, phase_deadline=40, clock=lambda: next(times))


def test_launcher_uses_one_connection_and_original_deadline():
    raw_streams = []
    state = {"now": 10}

    class Raw(Stream):
        def connect(self, address):
            assert address == ("127.0.0.1", 8765)
            state["now"] += 1

    def fake_socket(family, kind):
        assert (family, kind) == (2, 1)
        stream = Raw(_wire())
        raw_streams.append(stream)
        return stream

    result = launcher.capture_relay(
        _schedule(),
        phase_deadline=50,
        codec=codec,
        socket_factory=fake_socket,
        af_inet=2,
        sock_stream=1,
        clock=lambda: state["now"],
    ).to_dict()
    assert result["status"] == "complete"
    assert len(raw_streams) == 4
    assert all(stream.closed == 1 for stream in raw_streams)
    assert raw_streams[-1].timeouts[-1] == 36
    assert raw_streams[0].timeouts[2] == 39  # connect time was charged before send


@pytest.mark.parametrize(
    "text",
    ["0", "40001", "040", "1.0", "-1", "x" * 10000],
    ids=["zero", "above-limit", "leading-zero", "fractional", "negative", "oversize-duration"],
)
def test_launcher_duration_is_not_a_new_or_unbounded_phase(text):
    with pytest.raises(ValueError):
        launcher.parse_remaining_ms(text)


def test_output_is_bounded_raw_json_and_not_execution_proof():
    capture = codec.RepositoryRelayCapture(
        json.dumps(_capture([Stream(_wire()) for _ in range(4)]))
    )
    writes = []
    assert launcher.emit_capture(capture, lambda value: writes.append(value) or len(value)) == 0
    assert len(writes[0]) <= codec.MAX_CAPTURE_BYTES
    assert json.loads(writes[0])["execution_status"] == "not-established"
    with pytest.raises(ValueError):
        launcher.emit_capture(capture, lambda _: None)


@pytest.mark.parametrize("bad", [True, None, float("nan"), float("inf"), -1, 2**49])
def test_invalid_clock_or_deadline_never_opens_a_stream(bad):
    with pytest.raises(codec.HTTPProfileError):
        _capture([], clock=lambda: bad)
    with pytest.raises(codec.HTTPProfileError):
        _capture([], phase_deadline=bad)
    with pytest.raises(ValueError):
        launcher.read_schedule(
            lambda _: pytest.fail("clock must fail before stdin"),
            codec=codec,
            phase_deadline=40,
            clock=lambda: bad,
        )


def test_clock_failure_after_acquisition_cannot_skip_close():
    state = {"acquired": False}
    stream = Stream(_wire())

    def factory(*_):
        state["acquired"] = True
        return stream

    def clock():
        if state["acquired"]:
            raise OSError("private clock detail")
        return 0

    result = codec.capture_repository_http(
        _schedule(), stream_factory=factory, phase_deadline=40, clock=clock
    ).to_dict()
    assert result["failure"] == "clock-failed"
    assert stream.closed == 1 and stream.sent == []
    assert result["records"][0]["close_status"] == "closed"


@pytest.mark.parametrize("operation", ["settimeout", "sendall", "recv", "close"])
def test_async_collaborators_are_closed_and_never_awaited(operation):
    returned = []

    async def coroutine():
        pytest.fail("No async collaborator may run")

    def async_return(*_):
        result = coroutine()
        returned.append(result)
        return result

    stream = Stream(_wire())
    setattr(stream, operation, async_return)
    result = _capture([stream])
    assert result["status"] == "partial"
    assert returned and all(value.cr_frame is None for value in returned)
    assert len(result["records"]) == 4


def test_json_numbers_stay_distinct_and_observed_error_status_has_no_approval():
    facts = [_fact(_wire(body, status=503)) for body in (b"true", b"1", b"1.0")]
    values = [codec.decode_response_fact(fact)["body"]["value"] for fact in facts]
    assert [type(value) for value in values] == [bool, int, float]
    capture = _capture([Stream(_wire(b"null", status=503)) for _ in range(4)])
    assert capture["status"] == "complete"  # observation completion only
    assert capture["verified_fix"] is False
    assert capture["authorization_status"] == "unknown"


def test_wire_body_at_budget_and_parser_terminal_states():
    body = json.dumps(["x" * 1000] * 4, separators=(",", ":")).encode()
    assert len(body) <= codec.MAX_BODY_BYTES
    fact = _fact(_wire(body))
    assert codec.decode_response_fact(fact)["body"]["value"] == ["x" * 1000] * 4
    parser = codec.HTTPResponseParser("case")
    parser.feed(_wire())
    parser.finish()
    for method, args in ((parser.finish, ()), (parser.feed, (b"x",))):
        with pytest.raises(codec.HTTPProfileError):
            method(*args)


def test_schedule_is_frozen_before_collaborator_can_mutate_it():
    schedule = _schedule()
    streams = []

    def factory(*_):
        schedule["requests"][1]["path"] = "https://external.invalid"
        stream = Stream(_wire())
        streams.append(stream)
        return stream

    result = codec.capture_repository_http(
        schedule, stream_factory=factory, phase_deadline=40, clock=lambda: 0
    ).to_dict()
    assert result["status"] == "complete"
    assert streams[1].sent[0].startswith(b"GET /objects/1 HTTP/1.1\r\n")


def test_launcher_connection_error_closes_allocated_raw_socket():
    raw = Stream(_wire())

    def connect(_):
        raise OSError("private target")

    raw.connect = connect
    result = launcher.capture_relay(
        _schedule(),
        phase_deadline=40,
        codec=codec,
        socket_factory=lambda *_: raw,
        af_inet=2,
        sock_stream=1,
        clock=lambda: 0,
    ).to_dict()
    assert result["status"] == "partial"
    assert raw.closed == 1 and raw.sent == []
    assert result["records"][1]["dispatch_status"] == "not-dispatched"
