"""Scheduled request-only HTTP primitives, with no default network implementation.

This stdlib-only module may later be image-owned. Its supplied request schedule contains no
oracle answers. An explicitly injected, trusted, already-connected stream is the
only I/O seam; callbacks are not sandboxed or preemptible. Captured data never
establishes execution, isolation, authentication, or permission to change files.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from dataclasses import dataclass
from types import CoroutineType

HOST = "127.0.0.1"
PORT = 8765
MAX_STATUS_BYTES = 512
MAX_HEADER_BYTES = 4096
MAX_HEADER_COUNT = 32
MAX_BODY_BYTES = 4096
MAX_SCHEDULE_BYTES = 16_384
MAX_CAPTURE_BYTES = 131_072
MAX_WIRE_BYTES = 8 * (MAX_STATUS_BYTES + MAX_HEADER_BYTES + MAX_BODY_BYTES)
MAX_RECV_CALLS = MAX_WIRE_BYTES + 8
MAX_BODY_NODES = 128
MAX_BODY_DEPTH = 8
MAX_JSON_INTEGER = (1 << 53) - 1
_MAX_RESPONSE_BYTES = MAX_STATUS_BYTES + MAX_HEADER_BYTES + MAX_BODY_BYTES
_NAME = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
_STATUS = re.compile(rb"HTTP/1\.1 ([2-5][0-9]{2}) ([\x20-\x7e]*)\Z")
_LENGTH = re.compile(r"0|[1-9][0-9]*\Z")


class HTTPProfileError(ValueError):
    """A bounded, non-sensitive failure code; never includes response text."""

    def __init__(self, code: str, *, cancellation: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.cancellation = cancellation


def _canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HTTPProfileError("json-duplicate-key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise HTTPProfileError("json-nonfinite")


def _load_json(raw: str):
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HTTPProfileError("json-invalid") from exc


def _shape(value, fields):
    if type(value) is not dict or len(value) != len(fields) or set(value) != fields:
        raise HTTPProfileError("schedule-shape")
    return value


def _case_id(value):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 64
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is None
    ):
        raise HTTPProfileError("case-identity")
    return value


def validate_observer_schedule(raw: str | dict) -> dict:
    """Detach four to eight bounded request inputs; never admit expected answers."""
    if type(raw) is str:
        if len(raw) > MAX_SCHEDULE_BYTES:
            raise HTTPProfileError("schedule-budget")
        try:
            if len(raw.encode("utf-8")) > MAX_SCHEDULE_BYTES:
                raise HTTPProfileError("schedule-budget")
        except UnicodeError as exc:
            raise HTTPProfileError("schedule-unicode") from exc
        raw = _load_json(raw)
    data = _shape(raw, {"schema_version", "kind", "plan_id", "phase", "requests"})
    if (
        type(data["schema_version"]) is not str
        or data["schema_version"] != "1.0"
        or type(data["kind"]) is not str
        or data["kind"] != "repository-observer-schedule"
        or type(data["phase"]) is not str
        or data["phase"] not in {"before", "after"}
    ):
        raise HTTPProfileError("schedule-identity")
    plan_id = data["plan_id"]
    if (
        type(plan_id) is not str
        or len(plan_id) != len("repository-verification-plan-") + 64
        or re.fullmatch(r"repository-verification-plan-[0-9a-f]{64}", plan_id) is None
    ):
        raise HTTPProfileError("schedule-identity")
    requests = data["requests"]
    if type(requests) is not list or not 4 <= len(requests) <= 8:
        raise HTTPProfileError("schedule-count")
    seen = set()
    for request in requests:
        _shape(request, {"case_id", "method", "path", "headers"})
        case_id = _case_id(request["case_id"])
        if case_id in seen:
            raise HTTPProfileError("case-duplicate")
        seen.add(case_id)
        if type(request["method"]) is not str or request["method"] != "GET":
            raise HTTPProfileError("request-method")
        path = request["path"]
        if (
            type(path) is not str
            or not 1 <= len(path) <= 512
            or re.fullmatch(r"/[A-Za-z0-9/_.-]*", path) is None
            or "//" in path
            or any(part in {".", ".."} for part in path.split("/"))
        ):
            raise HTTPProfileError("request-path")
        headers = request["headers"]
        if type(headers) is not dict or len(headers) > 3:
            raise HTTPProfileError("request-headers")
        for name, value in headers.items():
            if type(name) is not str or name not in {"x-user", "x-user-id", "x-role"}:
                raise HTTPProfileError("request-headers")
            if (
                type(value) is not str
                or not 6 <= len(value) <= 64
                or re.fullmatch(r"test-[A-Za-z0-9][A-Za-z0-9_.-]{0,58}", value) is None
            ):
                raise HTTPProfileError("request-headers")
    encoded = _canonical(data)
    if len(encoded.encode("utf-8")) > MAX_SCHEDULE_BYTES:
        raise HTTPProfileError("schedule-budget")
    return _load_json(encoded)


def encode_repository_request(schedule: dict, case_id: str) -> bytes:
    """Encode one current scheduled GET with a fixed endpoint and framing."""
    data = validate_observer_schedule(schedule)
    _case_id(case_id)
    request = next((row for row in data["requests"] if row["case_id"] == case_id), None)
    if request is None:
        raise HTTPProfileError("case-identity")
    return _encode_request(request)


def _encode_request(request: dict) -> bytes:
    lines = [
        f"GET {request['path']} HTTP/1.1",
        f"Host: {HOST}:{PORT}",
        "Connection: close",
        "Accept-Encoding: identity",
    ]
    lines.extend(f"{name}: {value}" for name, value in sorted(request["headers"].items()))
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


class HTTPResponseParser:
    """Incremental, deliberately narrow HTTP/1.1 Content-Length response profile.

    This is not a general HTTP client. EOF is supplied only through ``finish``.
    Informational responses, upgrades, transfer coding,
    compression, ambiguous lengths and all bytes after the framed body fail.
    Both wire and normalized complete header blocks obey the same byte limit.
    """

    def __init__(self, request_id: str) -> None:
        self._request_id = _case_id(request_id)
        self._pending = bytearray()
        self._body = bytearray()
        self._headers: list[list[str]] = []
        self._status = None
        self._length = None
        self._header_bytes = self._normalized_header_bytes = 2
        self._wire_bytes = 0
        self._headers_done = self._finished = self._failed = False

    def _fail(self, code: str) -> None:
        self._failed = True
        raise HTTPProfileError(code)

    def _line(self, limit: int, code: str) -> bytes | None:
        marker = self._pending.find(b"\r\n")
        if marker < 0:
            if len(self._pending) >= limit:
                self._fail(code)
            # A final CR may be the first byte of a split CRLF, never a bare LF.
            if b"\n" in self._pending or b"\r" in self._pending[:-1]:
                self._fail("http-line-ending")
            return None
        if marker + 2 > limit:
            self._fail(code)
        line = bytes(self._pending[:marker])
        del self._pending[: marker + 2]
        if b"\r" in line or b"\n" in line:
            self._fail("http-line-ending")
        return line

    def _header(self, line: bytes) -> None:
        self._header_bytes += len(line) + 2
        if self._header_bytes > MAX_HEADER_BYTES or len(self._headers) >= MAX_HEADER_COUNT:
            self._fail("http-header-budget")
        name, separator, value = line.partition(b":")
        if (
            not separator
            or not _NAME.fullmatch(name)
            or any(byte < 32 or byte > 126 for byte in value)
        ):
            self._fail("http-header-syntax")
        content = value.strip(b" ").decode("ascii")
        field = name.decode("ascii")
        self._normalized_header_bytes += len(name) + len(content) + 4
        if self._normalized_header_bytes > MAX_HEADER_BYTES:
            self._fail("http-header-budget")
        self._headers.append([field, content])

    def _framing(self) -> None:
        fields: dict[str, list[str]] = {}
        for name, value in self._headers:
            fields.setdefault(name.lower(), []).append(value)
        if "transfer-encoding" in fields:
            self._fail("http-transfer-coding")
        if "upgrade" in fields or any(
            token.strip().lower() == "upgrade"
            for value in fields.get("connection", [])
            for token in value.split(",")
        ):
            self._fail("http-upgrade")
        coding = fields.get("content-encoding", [])
        if coding and (len(coding) != 1 or coding[0].lower() != "identity"):
            self._fail("http-content-coding")
        lengths = fields.get("content-length", [])
        if self._status in {204, 205, 304}:
            if lengths not in ([], ["0"]):
                self._fail("http-bodyless-status")
            self._length = 0
            return
        if len(lengths) != 1 or len(lengths[0]) > 4 or not _LENGTH.fullmatch(lengths[0]):
            self._fail("http-content-length")
        if len(lengths[0]) > 4 or int(lengths[0]) > MAX_BODY_BYTES:
            self._fail("http-body-budget")
        self._length = int(lengths[0])

    def feed(self, chunk: bytes) -> None:
        if self._finished or self._failed:
            self._fail("http-parser-terminal")
        if type(chunk) is not bytes or not chunk:
            self._fail("http-chunk-contract")
        if len(chunk) > _MAX_RESPONSE_BYTES - self._wire_bytes:
            self._fail("http-response-budget")
        self._wire_bytes += len(chunk)
        self._pending.extend(chunk)
        if self._status is None:
            line = self._line(MAX_STATUS_BYTES, "http-status-budget")
            if line is None:
                return
            match = _STATUS.fullmatch(line)
            if match is None:
                self._fail("http-status-syntax")
            self._status = int(match[1])
        while not self._headers_done:
            line = self._line(MAX_HEADER_BYTES - self._header_bytes + 2, "http-header-budget")
            if line is None:
                return
            if line:
                self._header(line)
            else:
                self._headers_done = True
                self._framing()
        if len(self._pending) > self._length - len(self._body):
            self._fail("http-trailing-bytes")
        self._body.extend(self._pending)
        self._pending.clear()

    def finish(self) -> dict:
        """Accept EOF only after one completely framed, bounded response."""
        if self._failed or self._finished:
            self._fail("http-parser-terminal")
        if not self._headers_done or len(self._body) != self._length:
            self._fail("http-truncated")
        self._finished = True
        return {
            "status_code": self._status,
            "headers": [list(pair) for pair in self._headers],
            "body_base64": base64.b64encode(self._body).decode("ascii"),
        }


@dataclass(frozen=True, slots=True)
class RepositoryRelayCapture:
    """Immutable unverified data, not an importable execution capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return json.loads(self.payload_json)


class _CaptureClock:
    def __init__(self, callback, deadline: float) -> None:
        if not callable(callback) or type(deadline) not in (int, float):
            raise HTTPProfileError("invalid-configuration")
        if not 0 < deadline <= 2**48 or not math.isfinite(deadline):
            raise HTTPProfileError("invalid-configuration")
        self.callback = callback
        self.deadline = float(deadline)
        self.last = None
        remaining = self.tick(cleanup=True)
        if remaining > 40:
            raise HTTPProfileError("invalid-configuration")

    def tick(self, *, cleanup: bool = False) -> float:
        try:
            value = self.callback()
        except BaseException as exc:
            cancellation = (
                type(exc).__name__
                if isinstance(exc, (KeyboardInterrupt, SystemExit))
                else "BaseException"
                if not isinstance(exc, Exception)
                else None
            )
            raise HTTPProfileError("clock-failed", cancellation=cancellation) from exc
        if type(value) is CoroutineType:
            value.close()
            raise HTTPProfileError("clock-invalid")
        if (
            type(value) not in (int, float)
            or not 0 <= value <= 2**48
            or not math.isfinite(value)
            or self.last is not None
            and value < self.last
        ):
            raise HTTPProfileError("clock-invalid")
        self.last = float(value)
        if value >= self.deadline and not cleanup:
            raise HTTPProfileError("deadline-expired")
        return self.deadline - value

    def call(self, operation: str, callback, *args):
        self.tick()
        failure = None
        try:
            answer = callback(*args)
            if type(answer) is CoroutineType:
                # A failing post-call clock must not leak an async result.
                answer.close()
                failure = HTTPProfileError(operation + "-contract")
        except BaseException as exc:
            failure = exc
        post_failure = None
        try:
            self.tick()
        except HTTPProfileError as exc:
            if failure is None:
                raise
            post_failure = exc
        if failure is not None:
            if not isinstance(failure, Exception):
                raise failure
            cancellation = None if post_failure is None else post_failure.cancellation
            if isinstance(failure, HTTPProfileError):
                raise HTTPProfileError(
                    operation + "-contract", cancellation=cancellation
                ) from failure
            raise HTTPProfileError(operation + "-failed", cancellation=cancellation) from failure
        return answer


def _validate_json_value(value) -> None:
    pending = [(value, 0)]
    visited = 0
    while pending:
        current, depth = pending.pop()
        visited += 1
        if depth > MAX_BODY_DEPTH or visited > MAX_BODY_NODES:
            raise HTTPProfileError("body-budget")
        kind = type(current)
        if current is None or kind is bool:
            continue
        if kind is str:
            try:
                if len(current) > 1024 or len(current.encode("utf-8")) > 1024:
                    raise HTTPProfileError("body-budget")
            except UnicodeError as exc:
                raise HTTPProfileError("body-invalid") from exc
        elif kind is int:
            if not -MAX_JSON_INTEGER <= current <= MAX_JSON_INTEGER:
                raise HTTPProfileError("body-budget")
        elif kind is float:
            if not math.isfinite(current):
                raise HTTPProfileError("body-invalid")
        elif kind in (dict, list):
            if len(current) > MAX_BODY_NODES:
                raise HTTPProfileError("body-budget")
            if kind is dict:
                for key in current:
                    try:
                        if len(key) > 128 or len(key.encode("utf-8")) > 128:
                            raise HTTPProfileError("body-budget")
                    except UnicodeError as exc:
                        raise HTTPProfileError("body-invalid") from exc
                children = current.values()
            else:
                children = current
            pending.extend((child, depth + 1) for child in children)
        else:
            raise HTTPProfileError("body-invalid")
    if len(_canonical(value).encode("utf-8")) > MAX_BODY_BYTES:
        raise HTTPProfileError("body-budget")


def decode_response_fact(fact: dict) -> dict:
    """Pure replay of raw framing and typed JSON; never a policy comparison.

    Reconstruct the bounded normalized response before decoding its JSON body.
    The empty wire body has kind ``empty``. Any JSON root is permitted, with
    duplicate keys, nonfinite values and unsupported portable numbers rejected.
    Raw headers remain in the capture; this function makes no header-leak claim.
    """
    if (
        type(fact) is not dict
        or len(fact) != 3
        or set(fact) != {"status_code", "headers", "body_base64"}
    ):
        raise HTTPProfileError("fact-shape")
    status = fact["status_code"]
    if type(status) is not int or not 200 <= status <= 599:
        raise HTTPProfileError("fact-status")
    headers = fact["headers"]
    if type(headers) is not list or len(headers) > MAX_HEADER_COUNT:
        raise HTTPProfileError("fact-headers")
    normalized = []
    header_bytes = 2
    for pair in headers:
        if type(pair) is not list or len(pair) != 2:
            raise HTTPProfileError("fact-headers")
        name, value = pair
        if (
            type(name) is not str
            or type(value) is not str
            or len(name) > MAX_HEADER_BYTES
            or len(value) > MAX_HEADER_BYTES
        ):
            raise HTTPProfileError("fact-headers")
        try:
            line = (name + ": " + value + "\r\n").encode("ascii")
        except UnicodeError as exc:
            raise HTTPProfileError("fact-headers") from exc
        if "\r" in name + value or "\n" in name + value:
            raise HTTPProfileError("fact-headers")
        header_bytes += len(line)
        if header_bytes > MAX_HEADER_BYTES:
            raise HTTPProfileError("fact-headers")
        normalized.append(line)
    encoded = fact["body_base64"]
    if type(encoded) is not str or len(encoded) > ((MAX_BODY_BYTES + 2) // 3) * 4:
        raise HTTPProfileError("fact-body")
    try:
        body = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError) as exc:
        raise HTTPProfileError("fact-body") from exc
    if len(body) > MAX_BODY_BYTES or base64.b64encode(body).decode("ascii") != encoded:
        raise HTTPProfileError("fact-body")
    parser = HTTPResponseParser("fact-replay")
    parser.feed(f"HTTP/1.1 {status} OK\r\n".encode() + b"".join(normalized) + b"\r\n" + body)
    if parser.finish() != fact:
        raise HTTPProfileError("fact-normalization")
    if not body:
        return {"status": status, "body": {"kind": "empty"}}
    try:
        value = _load_json(body.decode("utf-8"))
        _validate_json_value(value)
    except (HTTPProfileError, UnicodeError) as exc:
        raise HTTPProfileError("body-invalid") from exc
    return {"status": status, "body": {"kind": "json", "value": value}}


def _cancellation(exc):
    return (
        type(exc).__name__
        if isinstance(exc, (KeyboardInterrupt, SystemExit))
        else "BaseException"
        if not isinstance(exc, Exception)
        else None
    )


def capture_repository_http(
    schedule: str | dict, *, stream_factory, phase_deadline: float, clock
) -> RepositoryRelayCapture:
    """Observe a supplied schedule with fresh explicit streams and one deadline.

    No default collaborator opens a socket. Stop after the first error, keeping
    a record for every planned case, including undispatched suffix entries.
    Every acquired stream is closed even after deadline or clock failure. Close
    facts concern owned streams only, never Engine/container cleanup. Trusted
    callbacks can block; this is no hard preemption, sandbox, or live evidence.
    """
    data = validate_observer_schedule(schedule)
    if not callable(stream_factory):
        raise HTTPProfileError("invalid-configuration")
    guard = _CaptureClock(clock, phase_deadline)
    records = [
        {
            "case_id": request["case_id"],
            "dispatch_status": "not-dispatched",
            "fact": None,
            "error_code": None,
            "close_status": "not-acquired",
            "close_failure": None,
        }
        for request in data["requests"]
    ]
    wire_bytes = calls = 0
    failure = cancellation = None
    seen_streams = []
    for request, record in zip(data["requests"], records, strict=True):
        stream = None
        try:
            timeout = guard.tick()
            record["dispatch_status"] = "error"

            def acquire(current_timeout=timeout, current_record=record):
                nonlocal stream
                value = stream_factory(HOST, PORT, current_timeout)
                if type(value) is CoroutineType:
                    value.close()
                    raise HTTPProfileError("factory-contract")
                if value is None or any(value is previous for previous in seen_streams):
                    # An alias is not a fresh acquisition. Its previous owner
                    # has already closed it; never close or claim it twice.
                    raise HTTPProfileError("factory-contract")
                stream = value
                current_record["close_status"] = "unconfirmed"
                seen_streams.append(stream)
                return stream

            guard.call("factory", acquire)
            parser = HTTPResponseParser(request["case_id"])
            timeout = guard.tick()
            if guard.call("settimeout", stream.settimeout, timeout) is not None:
                raise HTTPProfileError("settimeout-contract")
            if guard.call("send", stream.sendall, _encode_request(request)) is not None:
                raise HTTPProfileError("send-contract")
            while True:
                if calls >= MAX_RECV_CALLS:
                    raise HTTPProfileError("receive-call-budget")
                timeout = guard.tick()
                if guard.call("settimeout", stream.settimeout, timeout) is not None:
                    raise HTTPProfileError("settimeout-contract")
                maximum = min(4096, MAX_WIRE_BYTES - wire_bytes + 1)
                calls += 1
                chunk = guard.call("receive", stream.recv, maximum)
                if type(chunk) is not bytes or len(chunk) > maximum:
                    raise HTTPProfileError("receive-contract")
                if not chunk:
                    record["fact"] = parser.finish()
                    decode_response_fact(record["fact"])
                    guard.tick()
                    record["dispatch_status"] = "response"
                    break
                if len(chunk) > MAX_WIRE_BYTES - wire_bytes:
                    raise HTTPProfileError("wire-budget")
                wire_bytes += len(chunk)
                parser.feed(chunk)
        except BaseException as exc:
            failure = exc.code if isinstance(exc, HTTPProfileError) else "stream-contract"
            cancellation = (
                exc.cancellation if isinstance(exc, HTTPProfileError) else _cancellation(exc)
            )
            if cancellation is not None and not isinstance(exc, HTTPProfileError):
                failure = "capture-cancelled"
            record["error_code"] = failure
            # Expiry before acquisition was never a dispatched request.
            if record["dispatch_status"] != "not-dispatched":
                record["dispatch_status"] = "error"
        finally:
            if stream is not None:
                for cleanup_phase in ("before", "after"):
                    try:
                        guard.tick(cleanup=True)
                    except HTTPProfileError as exc:
                        if failure is None:
                            failure = record["error_code"] = exc.code
                        if cancellation is None:
                            cancellation = exc.cancellation
                    if cleanup_phase == "before":
                        try:
                            answer = stream.close()
                            if type(answer) is CoroutineType:
                                answer.close()
                            if answer is not None:
                                record["close_failure"] = "close-contract"
                        except BaseException as exc:
                            record["close_failure"] = "close-failed"
                            if cancellation is None:
                                cancellation = _cancellation(exc)
                if record["close_failure"] is None:
                    record["close_status"] = "closed"
                elif failure is None:
                    failure = record["error_code"] = "cleanup-unconfirmed"
                try:
                    guard.tick()
                except HTTPProfileError as exc:
                    if failure is None:
                        failure = record["error_code"] = exc.code
                    if cancellation is None:
                        cancellation = exc.cancellation
        if failure is not None:
            if record["dispatch_status"] == "response":
                record["dispatch_status"] = "error"
            break
    payload = {
        "schema_version": "1.0",
        "kind": "repository-http-capture",
        "schedule_id": "repository-observer-schedule-"
        + hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest(),
        "plan_id": data["plan_id"],
        "phase": data["phase"],
        "planned_count": len(records),
        "status": "complete" if failure is None else "partial",
        "records": records,
        "failure": failure,
        "wire_bytes": wire_bytes,
        "recv_calls": calls,
        "cancellation": cancellation,
        "provenance": "caller-supplied-unverified",
        "execution_status": "not-established",
        "authorization_status": "unknown",
        "verified_fix": False,
    }
    encoded = _canonical(payload)
    try:
        guard.tick()
    except HTTPProfileError as exc:
        payload["status"] = "partial"
        if payload["failure"] is None:
            payload["failure"] = exc.code
        if payload["cancellation"] is None:
            payload["cancellation"] = exc.cancellation
        encoded = _canonical(payload)
    if len(encoded.encode("utf-8")) > MAX_CAPTURE_BYTES:
        raise HTTPProfileError("capture-budget")
    return RepositoryRelayCapture(encoded)
