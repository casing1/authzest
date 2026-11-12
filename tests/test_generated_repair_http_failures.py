"""Adversarial scripted HTTP only; no sockets, application or guest is run."""

from __future__ import annotations

import ast
import asyncio
import base64
import builtins
import copy
import json
import math
import os
import socket
import subprocess
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.runner import _generated_repair_http as http
from authzest.runner import _generated_repair_relay as relay
from authzest.runner import generated_repair_controls as controls


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    """Warm trusted stdlib laziness before blocking execution and filesystem APIs."""
    assert ast.unparse(ast.Constant(value=None)) == "None"
    assert base64.b64encode(b"{}").decode("ascii") == "e30="
    json.dumps({"warmup": True})

    def forbidden(*args, **kwargs):
        pytest.fail("Relay failure tests must use scripted memory streams only")

    original_import = builtins.__import__
    original_compile = builtins.compile

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


class Clock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value


class Stream:
    """Only implements the explicit trusted fake-stream contract, never a socket."""

    def __init__(self, response=None, *, clock=None, hook=None, chunk_size=None):
        self.remaining = _response() if response is None else response
        self.clock = clock
        self.hook = hook
        self.chunk_size = chunk_size
        self.calls = []
        self.closed = False

    def _call(self, name, value=None):
        self.calls.append((name, value))
        if self.hook is not None:
            return self.hook(name, value)
        return None

    def settimeout(self, value):
        return self._call("settimeout", value)

    def sendall(self, value):
        return self._call("sendall", value)

    def recv(self, count):
        custom = self._call("recv", count)
        if custom is not None:
            return custom
        take = min(count, self.chunk_size or count)
        result, self.remaining = self.remaining[:take], self.remaining[take:]
        return result

    def close(self):
        self.closed = True
        return self._call("close")


class Factory:
    def __init__(self, *, clock=None, hook=None, streams=None):
        self.clock = clock or Clock()
        self.hook = hook
        self.streams = []
        self.supplied = streams
        self.calls = []

    def __call__(self, host, port, timeout):
        self.calls.append((host, port, timeout))
        if self.hook is not None:
            self.hook()
        stream = (
            self.supplied[len(self.streams)]
            if self.supplied is not None
            else Stream(clock=self.clock)
        )
        self.streams.append(stream)
        return stream


def _response(body=b"{}", *, status=b"200 OK", fields=None):
    if fields is None:
        fields = [(b"Content-Length", str(len(body)).encode("ascii"))]
    return (
        b"HTTP/1.1 "
        + status
        + b"\r\n"
        + b"".join(name + b": " + value + b"\r\n" for name, value in fields)
        + b"\r\n"
        + body
    )


def _parse(response, *, chunk_size=None):
    parser = http.HTTPResponseParser(http.fixed_requests()[0].request_id)
    if chunk_size is None:
        parser.feed(response)
    else:
        for offset in range(0, len(response), chunk_size):
            parser.feed(response[offset : offset + chunk_size])
    return parser.finish()


def _capture(factory=None, *, clock=None, deadline=None):
    clock = clock or Clock()
    factory = factory or Factory(clock=clock)
    return http.capture_fixed_http(
        stream_factory=factory,
        phase_deadline=clock.value + 40 if deadline is None else deadline,
        clock=clock,
    ).to_dict()


def _assert_untrusted(data):
    assert data["provenance"] == "caller-supplied-unverified"
    assert data["execution_status"] == "not-established"
    assert data["authorization_status"] == "unknown"
    assert data["verified_fix"] is False


def _controls_requests():
    material = controls.build_generated_repair_controls()
    return material, [row for case in material.to_dict()["cases"] for row in case["requests"]]


def _profile_capture(candidate="after"):
    material, requests = _controls_requests()
    streams = [
        Stream(
            _response(
                canonical(row[f"expected_{candidate}"]["body_json"]).encode("utf-8"),
                status=str(row[f"expected_{candidate}"]["status_code"]).encode("ascii")
                + b" Scripted",
            )
        )
        for row in requests
    ]
    return material, _capture(Factory(streams=streams))


def _compare(data, *, candidate="after", material=None):
    return relay.compare_generated_repair_relay_capture(
        canonical(data), material or controls.build_generated_repair_controls(), candidate=candidate
    ).to_dict()


def test_status_line_limit_counts_its_crlf_and_segmented_input():
    prefix = b"HTTP/1.1 200 "
    line = prefix + b"x" * (512 - len(prefix) - 2) + b"\r\n"
    suffix = b"Content-Length: 2\r\n\r\n{}"
    assert _parse(line + suffix, chunk_size=1)["status_code"] == 200
    with pytest.raises(http.HTTPProfileError):
        _parse(line[:-2] + b"x\r\n" + suffix, chunk_size=1)


@pytest.mark.parametrize(
    "status",
    [b"100 Continue", b"101 Switching Protocols", b"199 Interim", b"204 Empty", b"304 Cached"],
)
def test_informational_upgrade_and_special_no_body_statuses_are_outside_profile(status):
    with pytest.raises(http.HTTPProfileError):
        _parse(_response(status=status))


@pytest.mark.parametrize("status", [b"200 Fine", b"302 Elsewhere", b"401 No", b"599 Unknown"])
def test_ordinary_final_status_is_captured_without_a_redirect_or_verdict(status):
    assert _parse(_response(status=status))["status_code"] == int(status[:3])


@pytest.mark.parametrize(
    "wire",
    [
        b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 20 OK\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 600 Invalid\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 O\x00K\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\nContent-Length: 2\n\n{}",
        b"HTTP/1.1 200 OK\r\n Folded: no\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nBad Name: no\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nName : no\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nName: no\x00\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nName: no\x7f\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nName: \xff\r\nContent-Length: 2\r\n\r\n{}",
    ],
)
def test_malformed_or_unsupported_status_and_header_text_never_produce_facts(wire):
    with pytest.raises(http.HTTPProfileError):
        _parse(wire, chunk_size=1)


@pytest.mark.parametrize(
    "fields",
    [
        [],
        [(b"Content-Length", b"2"), (b"Content-Length", b"2")],
        [(b"Content-Length", b"2"), (b"content-length", b"3")],
        [(b"Content-Length", b"2,2")],
        [(b"Content-Length", b"+2")],
        [(b"Content-Length", b"02")],
        [(b"Content-Length", b"-1")],
        [(b"Content-Length", b"2"), (b"Transfer-Encoding", b"chunked")],
        [(b"Transfer-Encoding", b"chunked")],
        [(b"Content-Length", b"2"), (b"Transfer-Encoding", b"identity")],
        [(b"Content-Length", b"2"), (b"Content-Encoding", b"gzip")],
        [(b"Content-Length", b"2"), (b"Content-Encoding", b"br")],
        [(b"Content-Length", b"2"), (b"Connection", b"upgrade")],
        [(b"Content-Length", b"2"), (b"Upgrade", b"websocket")],
    ],
)
def test_closed_framing_rejects_ambiguous_lengths_transfer_coding_and_upgrade(fields):
    with pytest.raises(http.HTTPProfileError):
        _parse(_response(fields=fields))


def test_header_count_and_full_header_block_boundaries():
    fields = [(b"Content-Length", b"2")] + [(b"X", b"")] * 31
    assert len(_parse(_response(fields=fields))["headers"]) == 32
    with pytest.raises(http.HTTPProfileError):
        _parse(_response(fields=fields + [(b"X", b"")]))
    fixed = len(b"Content-Length: 2\r\nX: \r\n\r\n")
    fields = [(b"Content-Length", b"2"), (b"X", b"x" * (4096 - fixed))]
    assert _parse(_response(fields=fields), chunk_size=1)["body_base64"] == "e30="
    with pytest.raises(http.HTTPProfileError):
        _parse(_response(fields=[fields[0], (b"X", fields[1][1] + b"x")]), chunk_size=1)


def test_body_limit_zero_and_exact_maximum_and_one_byte_over():
    assert _parse(_response(b""))["body_base64"] == ""
    body = b"x" * 8192
    assert base64.b64decode(_parse(_response(body), chunk_size=1)["body_base64"]) == body
    with pytest.raises(http.HTTPProfileError):
        _parse(_response(body + b"x"))


@pytest.mark.parametrize(
    "wire",
    [
        b"",
        b"HTTP/1.1 200 OK\r",
        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{",
        _response() + b"x",
        _response() + _response(),
    ],
)
def test_eof_truncation_extra_bytes_and_second_responses_are_not_complete(wire):
    with pytest.raises(http.HTTPProfileError):
        _parse(wire)


@pytest.mark.parametrize("value", [None, True, "{}", bytearray(b"{}"), memoryview(b"{}")])
def test_parser_feed_requires_exact_bytes(value):
    parser = http.HTTPResponseParser(http.fixed_requests()[0].request_id)
    with pytest.raises(http.HTTPProfileError):
        parser.feed(value)


def test_finished_parser_cannot_accept_later_bytes_or_forge_another_request():
    parser = http.HTTPResponseParser(http.fixed_requests()[0].request_id)
    parser.feed(_response())
    parser.finish()
    with pytest.raises(http.HTTPProfileError):
        parser.feed(b"x")
    with pytest.raises(http.HTTPProfileError):
        http.HTTPResponseParser("caller-selected/request")


def test_fixed_requests_do_not_carry_expected_labels_or_allow_a_caller_url():
    material, expected = _controls_requests()
    requests = http.fixed_requests()
    assert len(requests) == len(expected) == 21
    for request, row in zip(requests, expected, strict=True):
        assert request.request_id == row["request_id"]
        assert request.path == row["path"]
        assert tuple(request.headers) == tuple(tuple(pair) for pair in row["headers"])
        assert not hasattr(request, "expected_before")
        assert not hasattr(request, "expected_after")
    forged = http.FixedRequest(requests[0].request_id, "http://elsewhere.invalid/", ())
    with pytest.raises(http.HTTPProfileError):
        http.encode_request(forged)
    assert material.to_dict()["request_count"] == 21


@pytest.mark.parametrize("field", ["request_id", "path", "headers", "header_name", "header_value"])
def test_request_encoder_rejects_equal_but_non_exact_closed_field_types(field):
    class StringSubclass(str):
        pass

    class TupleSubclass(tuple):
        pass

    request = http.fixed_requests()[0]
    request_id, path, headers = request.request_id, request.path, request.headers
    if field == "request_id":
        request_id = StringSubclass(request_id)
    elif field == "path":
        path = StringSubclass(path)
    elif field == "headers":
        headers = TupleSubclass(headers)
    elif field == "header_name":
        headers = ((StringSubclass(headers[0][0]), headers[0][1]),)
    else:
        headers = ((headers[0][0], StringSubclass(headers[0][1])),)
    with pytest.raises(http.HTTPProfileError):
        http.encode_request(http.FixedRequest(request_id, path, headers))


def test_scripted_capture_is_ordered_fresh_and_has_no_runtime_authority():
    factory = Factory()
    data = _capture(factory)
    assert data["status"] == "complete"
    assert len(data["facts"]) == len(factory.streams) == 21
    assert [row["request_id"] for row in data["facts"]] == [
        row.request_id for row in http.fixed_requests()
    ]
    assert all((host, port) == ("127.0.0.1", 8765) for host, port, _ in factory.calls)
    assert all(stream.closed for stream in factory.streams)
    assert all(0 < timeout <= 40 for _, _, timeout in factory.calls)
    assert all(
        b"Connection: close\r\n" in value
        for stream in factory.streams
        for name, value in stream.calls
        if name == "sendall"
    )
    _assert_untrusted(data)


@pytest.mark.parametrize("point", ["settimeout", "sendall", "recv", "close"])
def test_collaborator_failure_stops_without_a_second_connection_and_attempts_close(point):
    def hook(name, value):
        if name == point:
            raise OSError("scripted private error not returned verbatim")

    stream = Stream(hook=hook)
    factory = Factory(streams=[stream])
    data = _capture(factory)
    assert data["status"] == "partial"
    assert data["failure"] is not None
    assert len(factory.calls) == 1
    assert stream.closed is True
    assert "scripted private error" not in canonical(data)
    _assert_untrusted(data)


def test_factory_failure_preserves_prior_complete_facts_and_never_retries():
    factory = Factory()
    original = factory.__class__.__call__

    def wrapped(host, port, remaining):
        if len(factory.streams) == 2:
            raise OSError("private factory failure")
        return original(factory, host, port, remaining)

    data = _capture(wrapped)
    assert data["status"] == "partial"
    assert len(data["facts"]) == 2
    assert all(stream.closed for stream in factory.streams)
    assert data["failed_request_index"] == 2


@pytest.mark.parametrize("returned", [None, object()])
def test_invalid_stream_objects_are_failures_not_user_cancellation(returned):
    data = _capture(lambda host, port, remaining: returned)
    assert data["status"] == "partial"
    assert data["failure"] is not None
    assert data["cancellation"] is None
    assert data["facts"] == []


@pytest.mark.parametrize("point", ["factory", "settimeout", "sendall", "recv", "close"])
def test_exact_original_deadline_is_checked_after_each_collaborator(point):
    clock = Clock()

    def hook(name, value):
        if name == point:
            clock.value = 1040.0

    stream = Stream(hook=hook)
    factory = Factory(
        clock=clock,
        streams=[stream],
        hook=(lambda: setattr(clock, "value", 1040.0)) if point == "factory" else None,
    )
    data = _capture(factory, clock=clock, deadline=1040.0)
    assert data["status"] == "partial"
    assert data["failure"] is not None
    assert len(factory.calls) == 1
    assert stream.closed is True
    _assert_untrusted(data)


def test_byte_at_a_time_progress_does_not_refresh_the_phase_deadline():
    clock = Clock()

    def hook(name, value):
        if name == "recv":
            clock.value += 1

    stream = Stream(clock=clock, hook=hook, chunk_size=1)
    factory = Factory(clock=clock, streams=[stream])
    data = _capture(factory, clock=clock, deadline=1040.0)
    assert data["status"] == "partial"
    assert data["facts"] == []
    assert len(factory.calls) == 1
    assert stream.closed is True
    assert clock.value == 1040.0


@pytest.mark.parametrize(
    "value",
    [True, -1, math.inf, math.nan, 10**1000],
    ids=["bool", "negative", "inf", "nan", "huge"],
)
def test_invalid_initial_clock_prevents_factory_dispatch(value):
    clock = Clock(value)
    factory = Factory()
    with pytest.raises(http.HTTPProfileError):
        _capture(factory, clock=clock, deadline=1040.0)
    assert factory.calls == []


@pytest.mark.parametrize(
    "deadline",
    [True, 1000.0, 999.0, 1040.0001, math.inf, 10**1000],
    ids=["bool", "expired", "past", "overlong", "inf", "huge"],
)
def test_expired_nonfinite_and_more_than_40_second_deadlines_prevent_dispatch(deadline):
    factory = Factory()
    with pytest.raises(http.HTTPProfileError):
        _capture(factory, deadline=deadline)
    assert factory.calls == []


def test_clock_reversal_after_factory_cannot_dispatch_request_but_still_closes():
    clock = Clock()
    stream = Stream()
    factory = Factory(clock=clock, streams=[stream], hook=lambda: setattr(clock, "value", 999.0))
    data = _capture(factory, clock=clock)
    assert data["status"] == "partial"
    assert stream.closed is True
    assert not any(name == "sendall" for name, _ in stream.calls)


def test_async_clock_is_rejected_and_its_coroutine_is_closed_before_dispatch():
    returned = []

    async def asynchronous_value():
        return 1000.0

    def clock():
        value = asynchronous_value()
        returned.append(value)
        return value

    factory = Factory()
    with pytest.raises(http.HTTPProfileError):
        http.capture_fixed_http(stream_factory=factory, phase_deadline=1040.0, clock=clock)
    assert factory.calls == []
    assert returned and all(value.cr_frame is None for value in returned)


@pytest.mark.parametrize("point", ["factory", "settimeout", "sendall", "recv", "close"])
def test_async_collaborator_results_are_rejected_without_leaking_coroutines(point):
    returned = []

    async def asynchronous_value():
        return None

    def result():
        value = asynchronous_value()
        returned.append(value)
        return value

    stream = Stream(hook=lambda name, value: result() if name == point else None)
    factory = (
        (lambda host, port, timeout: result()) if point == "factory" else Factory(streams=[stream])
    )
    data = _capture(factory)
    assert data["status"] == "partial"
    assert data["failure"] is not None
    assert returned and all(value.cr_frame is None for value in returned)
    if point != "factory":
        assert stream.closed is True


@pytest.mark.parametrize("point", ["factory", "recv", "close"])
def test_async_result_is_closed_even_when_the_same_call_expires_the_deadline(point):
    clock = Clock()
    returned = []

    async def asynchronous_value():
        return None

    def result():
        clock.value = 1040.0
        value = asynchronous_value()
        returned.append(value)
        return value

    stream = Stream(hook=lambda name, value: result() if name == point else None)
    factory = (
        (lambda host, port, timeout: result()) if point == "factory" else Factory(streams=[stream])
    )
    data = _capture(factory, clock=clock, deadline=1040.0)
    assert data["status"] == "partial"
    assert returned and all(value.cr_frame is None for value in returned)
    if point != "factory":
        assert stream.closed is True


def test_a_factory_cannot_reuse_one_stream_for_multiple_fixed_requests():
    stream = Stream()
    data = _capture(lambda host, port, timeout: stream)
    assert data["status"] == "partial"
    assert data["failed_request_index"] == 1
    assert len(data["facts"]) == 1
    assert sum(name == "sendall" for name, _ in stream.calls) == 1


@pytest.mark.parametrize("bad", ["wire", True, bytearray(b"wire"), 123])
def test_recv_requires_exact_bytes_and_preserves_no_partial_fact(bad):
    stream = Stream(hook=lambda name, value: bad if name == "recv" else None)
    data = _capture(Factory(streams=[stream]))
    assert data["status"] == "partial"
    assert data["facts"] == []
    assert stream.closed is True


def test_recv_returning_more_than_requested_is_rejected_before_parsing():
    stream = Stream(hook=lambda name, value: b"x" * (value + 1) if name == "recv" else None)
    data = _capture(Factory(streams=[stream]))
    assert data["status"] == "partial"
    assert data["facts"] == []
    assert stream.closed is True


def test_close_error_is_separate_and_does_not_replace_the_original_parse_failure():
    def hook(name, value):
        if name == "close":
            raise OSError("scripted cleanup failure")

    first = _capture(Factory(streams=[Stream(response=b"invalid")]))
    second = _capture(Factory(streams=[Stream(response=b"invalid", hook=hook)]))
    assert second["failure"] == first["failure"]
    assert second["close_status"] == "unconfirmed"
    assert second["close_failure"] is not None
    assert second["facts"] == []


def test_post_error_clock_cancellation_is_retained_without_replacing_first_cause():
    class InterruptOnceClock(Clock):
        interrupt = False

        def __call__(self):
            if self.interrupt:
                self.interrupt = False
                raise KeyboardInterrupt()
            return self.value

    clock = InterruptOnceClock()

    def hook(name, value):
        if name == "recv":
            clock.interrupt = True
            raise OSError("scripted initial receive failure")

    stream = Stream(hook=hook)
    data = _capture(Factory(streams=[stream]), clock=clock)
    assert data["status"] == "partial"
    assert data["failure"] == "receive-failed"
    assert data["cancellation"] == "KeyboardInterrupt"
    assert stream.closed is True


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_cancellation_is_inert_failed_data_with_cleanup_and_no_retry(exception):
    def hook(name, value):
        if name == "recv":
            raise exception()

    stream = Stream(hook=hook)
    data = _capture(Factory(streams=[stream]))
    assert data["status"] == "partial"
    assert data["cancellation"] == exception.__name__
    assert stream.closed is True
    assert data["facts"] == []


def test_base64_expansion_counts_toward_closed_payload_budget():
    # Each wire response is within per-response limits and total wire <256 KiB;
    # the JSON/base64 representation must nevertheless not exceed that budget.
    fields = [(b"Content-Length", b"8192"), (b"X", b"x" * 3000)]
    response = _response(b"x" * 8192, fields=fields)
    factory = Factory(streams=[Stream(response=response) for _ in range(21)])
    data = _capture(factory)
    assert data["status"] == "partial"
    assert data["failure"] is not None
    assert len(canonical(data).encode("utf-8")) <= 262_144
    assert all(stream.closed for stream in factory.streams)


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_complete_forged_profile_comparison_still_does_not_establish_a_runtime(candidate):
    material, data = _profile_capture(candidate)
    _assert_untrusted(data)
    compared = _compare(data, material=material, candidate=candidate)
    assert compared["matches_expected_profile"] is True
    _assert_untrusted(compared)
    assert compared["applied"] is False


def test_bridge_lower_wire_bound_accepts_valid_headers_without_optional_spaces():
    material, requests = _controls_requests()
    streams = []
    for row in requests:
        expected = row["expected_after"]
        body = canonical(expected["body_json"]).encode("utf-8")
        wire = (
            f"HTTP/1.1 {expected['status_code']} \r\nContent-Length:{len(body)}\r\n"
            "X:a\r\nY:b\r\n\r\n"
        ).encode("ascii") + body
        streams.append(Stream(wire))
    data = _capture(Factory(streams=streams))
    assert data["status"] == "complete"
    compared = _compare(data, material=material)
    assert compared["matches_expected_profile"] is True
    _assert_untrusted(compared)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update(extra=True),
        lambda data: data.update(status="partial"),
        lambda data: data.update(request_count=True),
        lambda data: data.update(request_count=10**1000),
        lambda data: data.update(verified_fix=True),
        lambda data: data.update(execution_status="executed"),
        lambda data: data.update(close_status="unconfirmed"),
        lambda data: data["facts"].pop(),
        lambda data: data["facts"].reverse(),
        lambda data: data["facts"][0].update(status_code=True),
        lambda data: data["facts"][0].update(extra=True),
        lambda data: data["facts"][0].update(body_base64="not canonical="),
    ],
)
def test_host_bridge_rejects_forged_or_incomplete_capture_shapes(mutation):
    material, data = _profile_capture()
    mutation(data)
    with pytest.raises(ContractError):
        _compare(data, material=material)


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema_version":"1.0","schema_version":"1.0"}',
        '{"facts":' + "[" * 30 + "0" + "]" * 30 + "}",
        '{"facts":"' + "x" * 262_145 + '"}',
        '{"wire_bytes":NaN}',
        "null",
        "[]",
    ],
)
def test_bridge_bounds_json_and_rejects_duplicate_keys_before_importing_facts(raw):
    with pytest.raises(ContractError):
        relay.compare_generated_repair_relay_capture(
            raw, controls.build_generated_repair_controls(), candidate="after"
        )


def test_bridge_does_not_mutate_the_supplied_capture_or_the_maintained_controls():
    material, data = _profile_capture()
    original_data = copy.deepcopy(data)
    original_controls = material.payload_json
    _compare(data, material=material)
    assert data == original_data
    assert material.payload_json == original_controls
