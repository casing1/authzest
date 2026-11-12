"""Request-only HTTP relay primitives, with no network or process implementation.

This stdlib-only module may later be image-owned. Its fixed inputs contain no
oracle answers. An explicitly injected, trusted, already-connected stream is the
only I/O seam; callbacks are not sandboxed or preemptible. Captured data never
establishes execution, isolation, authentication, or permission to change files.
"""

from __future__ import annotations

import base64
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
MAX_BODY_BYTES = 8192
MAX_CAPTURE_BYTES = 262_144
MAX_RECV_CALLS = MAX_CAPTURE_BYTES + 21
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


@dataclass(frozen=True, slots=True)
class FixedRequest:
    request_id: str
    path: str
    headers: tuple[tuple[str, str], ...]


def fixed_requests() -> tuple[FixedRequest, ...]:
    """The maintained twenty-one request inputs, not expected response labels."""
    requests = []

    def add(case_id: str, pairs: tuple[tuple[str | None, str], ...]) -> None:
        for number, (actor, document) in enumerate(pairs, 1):
            requests.append(
                FixedRequest(
                    f"{case_id}/{number}",
                    f"/documents/{document}",
                    () if actor is None else (("x-demo-actor", actor),),
                )
            )

    for actor in ("alice", "bob"):
        add(f"owner-{actor}", ((actor, f"doc-{actor}"),))
    for actor, document in (("alice", "doc-bob"), ("bob", "doc-alice")):
        add(f"cross-owner-{actor}", ((actor, document),))
    for label, actor in (
        ("missing-actor", None),
        ("empty-actor", ""),
        ("unknown-actor", "mallory"),
    ):
        for document in ("doc-alice", "doc-bob", "missing"):
            add(f"{label}-{document}", ((actor, document),))
    for actor in ("alice", "bob"):
        add(f"missing-document-{actor}", ((actor, "missing"),))
    for actor, own, other in (("alice", "doc-alice", "doc-bob"), ("bob", "doc-bob", "doc-alice")):
        add(f"normal-sequence-{actor}", ((actor, own), (actor, other), (actor, own)))
    return tuple(requests)


def encode_request(request: FixedRequest) -> bytes:
    """Encode only a current maintained GET, with no caller-selected endpoint."""
    if (
        type(request) is not FixedRequest
        or type(request.request_id) is not str
        or type(request.path) is not str
        or type(request.headers) is not tuple
        or any(
            type(pair) is not tuple
            or len(pair) != 2
            or any(type(value) is not str for value in pair)
            for pair in request.headers
        )
        or request not in fixed_requests()
    ):
        raise HTTPProfileError("request-identity")
    lines = [
        f"GET {request.path} HTTP/1.1",
        f"Host: {HOST}:{PORT}",
        "Connection: close",
        "Accept-Encoding: identity",
    ]
    lines.extend(f"{name}: {value}" for name, value in request.headers)
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


class HTTPResponseParser:
    """Incremental, deliberately narrow HTTP/1.1 Content-Length response profile.

    This is not a general HTTP client. EOF is supplied only through ``finish``.
    Informational/no-content/not-modified responses, upgrades, transfer coding,
    compression, ambiguous lengths and all bytes after the framed body fail.
    Both wire and normalized complete header blocks obey the same byte limit.
    """

    def __init__(self, request_id: str) -> None:
        if type(request_id) is not str or request_id not in {
            row.request_id for row in fixed_requests()
        }:
            raise HTTPProfileError("request-identity")
        self._request_id = request_id
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
        if len(lengths) != 1 or not _LENGTH.fullmatch(lengths[0]):
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
            if self._status in {204, 304}:
                self._fail("http-bodyless-status")
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
            "request_id": self._request_id,
            "status_code": self._status,
            "headers": [list(pair) for pair in self._headers],
            "body_base64": base64.b64encode(self._body).decode("ascii"),
        }


@dataclass(frozen=True, slots=True)
class RelayCapture:
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
        remaining = self.tick()
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


def capture_fixed_http(*, stream_factory, phase_deadline: float, clock) -> RelayCapture:
    """Capture through explicit trusted streams; never open a socket by default.

    One fresh connection and explicit EOF are required per request. The same
    original absolute deadline is checked around every collaborator call; no
    timeout or request renews it. Cleanup is always attempted even after expiry.
    Callbacks can block: this is not a universal wall-clock or sandbox guarantee.
    ``call_count`` counts recv calls (bounded by wire bytes plus twenty-one EOFs);
    timeout setup and fixed factory/send/close overhead are separately finite.
    """
    facts: list[dict] = []
    wire_bytes = calls = fact_bytes = 0
    failure = close_failure = cancellation = failed_index = None
    close_status = "not-needed"
    if not callable(stream_factory):
        raise HTTPProfileError("invalid-configuration")
    # Invalid initial configuration is a programming error, before dispatch.
    guard = _CaptureClock(clock, phase_deadline)
    seen_streams = []
    current_index = 0
    try:
        for current_index, request in enumerate(fixed_requests()):
            stream = None
            try:
                timeout = guard.tick()

                def acquire(current_timeout=timeout):
                    nonlocal stream
                    # Retain ownership BEFORE the post-callback clock check.
                    value = stream_factory(HOST, PORT, current_timeout)
                    if type(value) is CoroutineType:
                        value.close()
                        raise HTTPProfileError("factory-contract")
                    stream = value
                    if stream is None or any(stream is previous for previous in seen_streams):
                        raise HTTPProfileError("factory-contract")
                    seen_streams.append(stream)
                    return stream

                guard.call("factory", acquire)
                close_status = "unconfirmed"
                parser = HTTPResponseParser(request.request_id)
                timeout = guard.tick()
                if guard.call("settimeout", stream.settimeout, timeout) is not None:
                    raise HTTPProfileError("settimeout-contract")
                if guard.call("send", stream.sendall, encode_request(request)) is not None:
                    raise HTTPProfileError("send-contract")
                while True:
                    if calls >= MAX_RECV_CALLS:
                        raise HTTPProfileError("receive-call-budget")
                    timeout = guard.tick()
                    if guard.call("settimeout", stream.settimeout, timeout) is not None:
                        raise HTTPProfileError("settimeout-contract")
                    maximum = min(4096, MAX_CAPTURE_BYTES - wire_bytes + 1)
                    calls += 1
                    chunk = guard.call("receive", stream.recv, maximum)
                    if type(chunk) is not bytes or len(chunk) > maximum:
                        raise HTTPProfileError("receive-contract")
                    if not chunk:
                        fact = parser.finish()
                        encoded = json.dumps(fact, ensure_ascii=True, separators=(",", ":"))
                        if fact_bytes + len(encoded) + 1 > MAX_CAPTURE_BYTES - 4096:
                            raise HTTPProfileError("capture-budget")
                        guard.tick()
                        facts.append(fact)
                        fact_bytes += len(encoded) + 1
                        break
                    if len(chunk) > MAX_CAPTURE_BYTES - wire_bytes:
                        raise HTTPProfileError("wire-budget")
                    wire_bytes += len(chunk)
                    parser.feed(chunk)
            except BaseException as exc:
                if isinstance(exc, HTTPProfileError):
                    failure = exc.code
                    cancellation = exc.cancellation
                elif not isinstance(exc, Exception):
                    cancellation = (
                        type(exc).__name__
                        if isinstance(exc, (KeyboardInterrupt, SystemExit))
                        else "BaseException"
                    )
                    failure = "capture-cancelled"
                else:
                    failure = "stream-contract"
                failed_index = current_index
            finally:
                if stream is not None:
                    # Expiry or a failed clock cannot suppress owned-stream cleanup.
                    try:
                        guard.tick(cleanup=True)
                    except HTTPProfileError as exc:
                        if failure is None:
                            failure, failed_index = exc.code, current_index
                        if cancellation is None:
                            cancellation = exc.cancellation
                    cleanup_error = None
                    try:
                        answer = stream.close()
                        if type(answer) is CoroutineType:
                            answer.close()
                        if answer is not None:
                            cleanup_error = "close-contract"
                    except BaseException as exc:
                        cleanup_error = "close-failed"
                        if not isinstance(exc, Exception) and cancellation is None:
                            cancellation = (
                                type(exc).__name__
                                if isinstance(exc, (KeyboardInterrupt, SystemExit))
                                else "BaseException"
                            )
                    try:
                        guard.tick(cleanup=True)
                    except HTTPProfileError as exc:
                        if failure is None:
                            failure, failed_index = exc.code, current_index
                        if cancellation is None:
                            cancellation = exc.cancellation
                    if cleanup_error is not None:
                        close_failure = cleanup_error
                        close_status = "unconfirmed"
                        if failure is None:
                            failure, failed_index = "cleanup-unconfirmed", current_index
                    else:
                        close_status = "closed"
                    try:
                        guard.tick()
                    except HTTPProfileError as exc:
                        if failure is None:
                            failure, failed_index = exc.code, current_index
                        if cancellation is None:
                            cancellation = exc.cancellation
            if failure is not None:
                break
        guard.tick()
    except BaseException as exc:
        if failure is None:
            failure = exc.code if isinstance(exc, HTTPProfileError) else "capture-cancelled"
            failed_index = current_index
        if not isinstance(exc, Exception):
            cancellation = (
                type(exc).__name__
                if isinstance(exc, (KeyboardInterrupt, SystemExit))
                else "BaseException"
            )
        elif isinstance(exc, HTTPProfileError) and cancellation is None:
            cancellation = exc.cancellation
    payload = {
        "schema_version": "1.0",
        "kind": "generated-repair-relay-capture",
        "status": "complete" if failure is None and len(facts) == 21 else "partial",
        "request_count": 21,
        "facts": facts,
        "failure": failure,
        "failed_request_index": failed_index,
        "wire_bytes": wire_bytes,
        "call_count": calls,
        "close_status": close_status,
        "close_failure": close_failure,
        "cancellation": cancellation,
        "provenance": "caller-supplied-unverified",
        "execution_status": "not-established",
        "authorization_status": "unknown",
        "verified_fix": False,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    try:
        # Serialization time is not allowed to turn a late capture into complete.
        guard.tick()
    except HTTPProfileError as exc:
        payload["status"] = "partial"
        if payload["failure"] is None:
            payload["failure"] = exc.code
            payload["failed_request_index"] = current_index
        if payload["cancellation"] is None:
            payload["cancellation"] = exc.cancellation
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return RelayCapture(encoded)
