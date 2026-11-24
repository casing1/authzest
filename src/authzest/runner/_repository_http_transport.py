"""Closed HTTP-PoC schedules using the unchanged bounded HTTP wire primitives.

The 2.0 entry accepts no test-interface aliases or old plan IDs. It performs no
I/O by default: a trusted caller must inject every connected stream and clock.
Facts and own-stream close observations remain unverified data, not target,
container, policy, authentication, isolation or original-write authority.

The old repository HTTP parser and clock are intentionally shared unchanged;
this explicit new loop keeps its distinct schedule and result identities closed.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from types import CoroutineType

if __package__:
    from . import _repository_http as _wire
else:  # Trusted image-owned import; no target files are visible to the observer.
    import repository_http as _wire

HTTPProfileError = _wire.HTTPProfileError
HTTPResponseParser = _wire.HTTPResponseParser
decode_response_fact = _wire.decode_response_fact
HOST = _wire.HOST
PORT = _wire.PORT
MAX_SCHEDULE_BYTES = _wire.MAX_SCHEDULE_BYTES
MAX_CAPTURE_BYTES = _wire.MAX_CAPTURE_BYTES
MAX_RECV_CALLS = _wire.MAX_RECV_CALLS
MAX_WIRE_BYTES = _wire.MAX_WIRE_BYTES
_canonical = _wire._canonical
_load_json = _wire._load_json
_shape = _wire._shape
_case_id = _wire._case_id
_encode_request = _wire._encode_request
_CaptureClock = _wire._CaptureClock
_cancellation = _wire._cancellation


@dataclass(frozen=True, slots=True)
class RepositoryHttpCapture:
    """Detached raw data, never a fresh host-phase capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return _load_json(self.payload_json)


def validate_http_observer_schedule(raw: str | dict) -> dict:
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
        or data["schema_version"] != "2.0"
        or type(data["kind"]) is not str
        or data["kind"] != "repository-http-observer-schedule"
        or type(data["phase"]) is not str
        or data["phase"] not in {"before", "after"}
    ):
        raise HTTPProfileError("schedule-identity")
    plan_id = data["plan_id"]
    if (
        type(plan_id) is not str
        or len(plan_id) != len("repository-http-verification-plan-") + 64
        or re.fullmatch(r"repository-http-verification-plan-[0-9a-f]{64}", plan_id) is None
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


def encode_http_observer_request(schedule: dict, case_id: str) -> bytes:
    """Encode one literal current request; no endpoint comes from input data."""
    data = validate_http_observer_schedule(schedule)
    _case_id(case_id)
    request = next((row for row in data["requests"] if row["case_id"] == case_id), None)
    if request is None:
        raise HTTPProfileError("case-identity")
    return _encode_request(request)


def capture_repository_http_poc(
    schedule: str | dict, *, stream_factory, phase_deadline: float, clock
) -> RepositoryHttpCapture:
    """Observe a supplied schedule with fresh explicit streams and one deadline.

    No default collaborator opens a socket. Stop after the first error, keeping
    a record for every planned case, including undispatched suffix entries.
    Every acquired stream is closed even after deadline or clock failure. Close
    facts concern owned streams only, never Engine/container cleanup. Trusted
    callbacks can block; this is no hard preemption, sandbox, or live evidence.
    """
    data = validate_http_observer_schedule(schedule)
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
        "schema_version": "2.0",
        "kind": "repository-http-raw-capture",
        "schedule_id": "repository-http-observer-schedule-"
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
    return RepositoryHttpCapture(encoded)
