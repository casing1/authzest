"""Private fixed Engine metadata reads over one explicit Unix socket.

This is not the generated-code executor. It invokes no CLI, plugin, subprocess,
proxy or helper, and creates no guest. Callers own current decisions and the
original phase/setup deadlines. Path observations do not attest the peer or make
connect atomic against a hostile local writer. Synchronous OS calls/close have
no universal preemption guarantee. No production entry point calls this module.
"""

from __future__ import annotations

import inspect
import math
import os
import re
import socket
import stat
import sys
import time
from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import canonical
from authzest.runner._generated_repair_runtime_profile import (
    RuntimeProfile,
    validate_runtime_profile,
)

MAX_WIRE_BYTES = 262_144
MAX_BODY_BYTES = 65_536
MAX_HEADER_BYTES = 16_384
_OPERATIONS = ("version", "info", "image-T", "image-A", "image-B")
_TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


@dataclass(slots=True)
class WireBudget:
    """One caller-owned cumulative raw response budget, including framing."""

    used: int = 0


@dataclass(frozen=True, slots=True)
class EngineResponse:
    operation: str
    body: bytes
    wire_bytes: int
    endpoint_identity: dict


class EngineHTTPError(RuntimeError):
    """A metadata request failed; its effect/cleanup disposition is explicit."""

    def __init__(self, diagnostic: dict):
        super().__init__("Fixed Engine metadata observation failed")
        self.diagnostic = dict(diagnostic)


class _Failure(ValueError):
    pass


class _Clock:
    def __init__(self, deadline):
        if type(deadline) not in {int, float} or not math.isfinite(deadline):
            raise _Failure("invalid-deadline")
        self.deadline, self.last = float(deadline), None
        if self.remaining() > 10.000001:
            raise _Failure("setup-budget-exceeds-ten-seconds")

    def remaining(self) -> float:
        now = time.monotonic()
        if (
            type(now) not in {int, float}
            or not math.isfinite(now)
            or (self.last is not None and now < self.last)
        ):
            raise _Failure("invalid-or-reversing-clock")
        self.last = now
        remaining = self.deadline - now
        if remaining <= 0:
            raise _Failure("original-deadline-expired")
        return remaining


def _identity(value) -> list[int]:
    return [
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    ]


def _endpoint_identity(path: str) -> dict:
    """Inspect no-follow names; this is neither peer authentication nor CAS."""
    parts = path.split("/")
    if not path.startswith("/") or len(parts) > 33:
        raise _Failure("unsupported-endpoint-depth")
    parents = []
    for index in range(1, len(parts)):
        parent = "/" if index == 1 else "/".join(parts[:index])
        value = os.lstat(parent)
        if (
            not stat.S_ISDIR(value.st_mode)
            or value.st_uid not in {0, os.geteuid()}
            or (value.st_mode & 0o022 and not value.st_mode & stat.S_ISVTX)
        ):
            raise _Failure("unsupported-endpoint-parent")
        parents.append([parent, _identity(value)[:5]])
    value = os.lstat(path)
    if (
        not stat.S_ISSOCK(value.st_mode)
        or value.st_uid not in {0, os.geteuid()}
        or value.st_mode & 0o002
    ):
        raise _Failure("unsupported-endpoint-file")
    return {
        "socket_identity": _identity(value),
        "parent_chain_sha256": sha256(
            canonical({"socket_path": path, "parents": parents}).encode("utf-8")
        ).hexdigest(),
    }


def _budget(budget: WireBudget) -> None:
    if type(budget) is not WireBudget or type(budget.used) is not int:
        raise _Failure("invalid-wire-budget")
    if not 0 <= budget.used <= MAX_WIRE_BYTES:
        raise _Failure("wire-budget-exhausted")


def _set_timeout(connection, clock: _Clock) -> None:
    result = connection.settimeout(clock.remaining())
    if result is not None:
        if inspect.iscoroutine(result):
            result.close()
        raise _Failure("timeout-configuration-unconfirmed")
    clock.remaining()


class _Reader:
    def __init__(self, connection, clock: _Clock, budget: WireBudget):
        self.connection, self.clock, self.budget = connection, clock, budget
        self.buffer = bytearray()
        self.eof, self.last_used = False, budget.used

    def fill(self, maximum=4096) -> None:
        if self.eof:
            return
        _budget(self.budget)
        if self.budget.used != self.last_used:
            raise _Failure("wire-budget-changed-during-read")
        maximum = min(maximum, 4096, MAX_WIRE_BYTES - self.budget.used + 1)
        _set_timeout(self.connection, self.clock)
        chunk = self.connection.recv(maximum)
        if type(chunk) is not bytes:
            if inspect.iscoroutine(chunk):
                chunk.close()
            raise _Failure("invalid-receive-result")
        self.budget.used += len(chunk)
        self.last_used = self.budget.used
        self.clock.remaining()
        if len(chunk) > maximum or self.budget.used > MAX_WIRE_BYTES:
            raise _Failure("raw-wire-limit-exceeded")
        if chunk:
            self.buffer.extend(chunk)
        else:
            self.eof = True

    def exact(self, count: int) -> bytes:
        while len(self.buffer) < count:
            if self.eof:
                raise _Failure("truncated-response")
            self.fill(min(4096, count - len(self.buffer)))
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def line(self, limit: int) -> bytes:
        if limit < 0:
            raise _Failure("header-limit-exceeded")
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                if newline == 0 or self.buffer[newline - 1] != 13:
                    raise _Failure("non-crlf-response-line")
                if newline - 1 > limit:
                    raise _Failure("response-line-limit-exceeded")
                return self.exact(newline + 1)[:-2]
            if len(self.buffer) > limit + 1:
                raise _Failure("response-line-limit-exceeded")
            if self.eof:
                raise _Failure("truncated-response-line")
            self.fill(min(4096, limit + 2 - len(self.buffer)))

    def end(self) -> None:
        if self.buffer:
            raise _Failure("extra-response-bytes")
        self.fill(1)
        if not self.eof:
            raise _Failure("extra-response-bytes")


def _response(reader: _Reader) -> bytes:
    status = reader.line(MAX_HEADER_BYTES - 2)
    total = len(status) + 2
    if re.fullmatch(rb"HTTP/1\.[01] 200(?: [\x20-\x7e]*)?", status) is None:
        raise _Failure("unsupported-http-status")
    headers = {}
    while True:
        line = reader.line(MAX_HEADER_BYTES - total - 2)
        total += len(line) + 2
        if not line:
            break
        if len(headers) >= 32 or line.startswith((b" ", b"\t")) or b":" not in line:
            raise _Failure("unsupported-http-header")
        key, value = line.split(b":", 1)
        if _TOKEN.fullmatch(key) is None or any(byte < 32 and byte != 9 for byte in value):
            raise _Failure("invalid-http-header")
        if any(byte > 126 for byte in value):
            raise _Failure("invalid-http-header")
        key, value = key.lower(), value.strip(b" \t").lower()
        if key in headers:
            raise _Failure("duplicate-http-header")
        headers[key] = value
    if (
        re.fullmatch(
            rb'application/json(?:\s*;\s*charset=(?:utf-8|"utf-8"))?',
            headers.get(b"content-type", b""),
        )
        is None
    ):
        raise _Failure("unsupported-content-type")
    if headers.get(b"content-encoding") not in {None, b"identity"} or b"upgrade" in headers:
        raise _Failure("unsupported-http-encoding")
    if b"upgrade" in headers.get(b"connection", b""):
        raise _Failure("unsupported-http-upgrade")
    length, transfer = headers.get(b"content-length"), headers.get(b"transfer-encoding")
    if length is not None and transfer is not None:
        raise _Failure("ambiguous-http-framing")
    if length is not None:
        if re.fullmatch(rb"[0-9]{1,6}", length) is None or int(length) > MAX_BODY_BYTES:
            raise _Failure("invalid-content-length")
        body = reader.exact(int(length))
    elif transfer is not None:
        if transfer != b"chunked":
            raise _Failure("unsupported-transfer-encoding")
        chunks, size = [], 0
        while True:
            line = reader.line(32)
            if re.fullmatch(rb"[0-9A-Fa-f]{1,32}", line) is None:
                raise _Failure("invalid-chunk-size")
            count = int(line, 16)
            if not count:
                if reader.line(0):
                    raise _Failure("unsupported-http-trailer")
                break
            if count > MAX_BODY_BYTES - size:
                raise _Failure("body-limit-exceeded")
            chunks.append(reader.exact(count))
            size += count
            if reader.exact(2) != b"\r\n":
                raise _Failure("invalid-chunk-terminator")
        body = b"".join(chunks)
    else:
        chunks, size = [], 0
        while reader.buffer or not reader.eof:
            if not reader.buffer:
                reader.fill(min(4096, MAX_BODY_BYTES - size + 1))
            chunk = bytes(reader.buffer)
            reader.buffer.clear()
            if len(chunk) > MAX_BODY_BYTES - size:
                raise _Failure("body-limit-exceeded")
            chunks.append(chunk)
            size += len(chunk)
        body = b"".join(chunks)
    reader.end()
    return body


def read_engine(
    profile: RuntimeProfile,
    operation: str,
    *,
    deadline: float,
    budget: WireBudget,
    before_connect=None,
) -> EngineResponse:
    """Read one fixed metadata document once; no readiness or execution authority.

    A future coordinator must provide the original shared setup/phase deadline and
    current decision checks. The optional synchronous hook is coordination, not
    consent. All body/framing bytes consume the supplied cumulative wire budget.
    """
    return _read_fixed(
        profile,
        operation,
        bootstrap=False,
        deadline=deadline,
        budget=budget,
        before_connect=before_connect,
    )


def _bootstrap_endpoint(endpoint):
    if type(endpoint) is not str or not endpoint.startswith("unix://"):
        raise _Failure("invalid-bootstrap-endpoint")
    path = endpoint[7:]
    if (
        not 1 < len(path) <= 512
        or re.fullmatch(r"/[A-Za-z0-9._/-]+", path, re.ASCII) is None
        or any(part in {"", ".", ".."} for part in path[1:].split("/"))
    ):
        raise _Failure("invalid-bootstrap-endpoint")
    return endpoint


def read_engine_bootstrap(
    endpoint: str,
    operation: str,
    *,
    deadline: float,
    budget: WireBudget,
    before_connect=None,
) -> EngineResponse:
    """Read only version or fixed API1.51 info, without inventing a full profile.

    The caller must check version's advertised range before requesting info.
    No image lookup, expected daemon identity or readiness is represented here.
    """
    return _read_fixed(
        endpoint,
        operation,
        bootstrap=True,
        deadline=deadline,
        budget=budget,
        before_connect=before_connect,
    )


def _read_fixed(subject, operation, *, bootstrap, deadline, budget, before_connect):
    diagnostic = {
        "operation": operation
        if type(operation) is str and operation in _OPERATIONS
        else "invalid",
        "contact_attempted": False,
        "connection_status": "not-attempted",
        "request_status": "not-attempted",
        "socket_acquisition": "not-attempted",
        "socket_cleanup": "not-needed",
        "bytes_received": 0,
    }
    connection = None
    primary = cleanup_failure = None
    response = pin = clock = None
    start_used = 0
    valid_handle = False
    try:
        clock = _Clock(deadline)
        _budget(budget)
        start_used = budget.used
        if start_used == MAX_WIRE_BYTES:
            raise _Failure("wire-budget-exhausted")
        if os.name != "posix" or getattr(sys, "frozen", False) or not hasattr(socket, "AF_UNIX"):
            raise _Failure("unsupported-platform")
        if type(operation) is not str:
            raise _Failure("invalid-runtime-request")
        if bootstrap:
            if operation not in {"version", "info"}:
                raise _Failure("invalid-bootstrap-operation")
            path = _bootstrap_endpoint(subject)[7:]
            target = "/version" if operation == "version" else "/v1.51/info"
        else:
            if type(subject) is not RuntimeProfile:
                raise _Failure("invalid-runtime-request")
            data = validate_runtime_profile(subject.payload_json).to_dict()
            if operation not in _OPERATIONS:
                raise _Failure("invalid-runtime-request")
            path = data["engine"]["endpoint"][7:]
            target = "/version" if operation == "version" else "/v" + data["engine"]["api_version"]
            if operation == "info":
                target += "/info"
            elif operation.startswith("image-"):
                target += "/images/" + data["images"][operation[-1]]["image_id"] + "/json"
        if before_connect is not None and (
            not callable(before_connect) or inspect.iscoroutinefunction(before_connect)
        ):
            raise _Failure("invalid-preconnect-hook")
        pin = _endpoint_identity(path)
        clock.remaining()
        if before_connect is not None:
            result = before_connect()
            if result is not None:
                if inspect.iscoroutine(result):
                    result.close()
                raise _Failure("preconnect-hook-not-confirmed")
        clock.remaining()
        if _endpoint_identity(path) != pin:
            raise _Failure("endpoint-changed-before-connect")
        if budget.used != start_used:
            raise _Failure("wire-budget-changed-before-connect")
        clock.remaining()
        diagnostic["socket_acquisition"] = "attempted-unconfirmed"
        diagnostic["socket_cleanup"] = "unconfirmed"
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if inspect.iscoroutine(connection) or not all(
            callable(getattr(connection, name, None))
            for name in ("settimeout", "connect", "sendall", "recv", "close")
        ):
            raise _Failure("socket-acquisition-unconfirmed")
        valid_handle = True
        diagnostic["socket_acquisition"] = "handle-returned"
        _set_timeout(connection, clock)
        diagnostic["contact_attempted"] = True
        diagnostic["connection_status"] = "attempted-unconfirmed"
        result = connection.connect(path)
        if result is not None:
            if inspect.iscoroutine(result):
                result.close()
            raise _Failure("connect-result-unconfirmed")
        diagnostic["connection_status"] = "connected"
        clock.remaining()
        request = (
            "GET " + target + " HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        _set_timeout(connection, clock)
        diagnostic["request_status"] = "attempted-unconfirmed"
        result = connection.sendall(request)
        if result is not None:
            if inspect.iscoroutine(result):
                result.close()
            raise _Failure("send-result-unconfirmed")
        diagnostic["request_status"] = "sent"
        clock.remaining()
        body = _response(_Reader(connection, clock, budget))
        clock.remaining()
        response = EngineResponse(operation, body, budget.used - start_used, pin)
    except BaseException as exc:
        primary = exc
    finally:
        if connection is not None:
            try:
                result = connection.close()
                if result is not None:
                    if inspect.iscoroutine(result):
                        result.close()
                    raise _Failure("socket-close-unconfirmed")
                if valid_handle:
                    diagnostic["socket_cleanup"] = "confirmed"
            except BaseException as exc:
                cleanup_failure = exc
                diagnostic["socket_cleanup"] = "unconfirmed"
                if primary is None:
                    primary = exc
                elif not isinstance(exc, Exception) and isinstance(primary, Exception):
                    exc.engine_http_primary_failure = primary
                    primary = exc
        if pin is not None:
            try:
                if _endpoint_identity(path) != pin:
                    raise _Failure("endpoint-changed-after-close")
                clock.remaining()
            except BaseException as exc:
                if primary is None:
                    primary = exc
                elif not isinstance(exc, Exception) and isinstance(primary, Exception):
                    exc.engine_http_primary_failure = primary
                    primary = exc
        if type(budget) is WireBudget and type(budget.used) is int:
            diagnostic["bytes_received"] = max(0, budget.used - start_used)
    if cleanup_failure is not None:
        if primary is None:
            primary = cleanup_failure
        elif not isinstance(cleanup_failure, Exception) and isinstance(primary, Exception):
            cleanup_failure.engine_http_primary_failure = primary
            primary = cleanup_failure
    if primary is not None:
        diagnostic["reason"] = str(primary) if type(primary) is _Failure else "operation-failed"
        diagnostic["cleanup_failure"] = cleanup_failure is not None
        if not isinstance(primary, Exception):
            primary.engine_http_observation = diagnostic
            raise primary
        raise EngineHTTPError(diagnostic) from primary
    return response
