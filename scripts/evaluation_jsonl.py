"""Pure bounded JSONL framing and serial RPC envelopes, never a transport.

No stream, process, account, configuration, clock or provider is accessed. Returned
frames/results/notifications are bounded private in-memory data, not public logs.
Allowed notification names are only envelope checks: payload semantics, actual
thread/turn completion, provenance and accepted trials are deliberately unverified.
"""

from __future__ import annotations

import json
import math

from scripts import evaluation_dispatch_recipe as recipe

POLICY_VERSION = "offline-jsonl-envelope-v1"
MAX_FRAME_BYTES = recipe.MAX_FRAME_BYTES  # Includes the terminating LF (also in CRLF).
MAX_STREAM_BYTES = recipe.MAX_STREAM_BYTES
MAX_EVENTS = recipe.MAX_EVENTS
MAX_PENDING_NOTIFICATIONS = recipe.MAX_PENDING
MAX_REQUEST_ID = recipe.MAX_RPC_ID
MAX_DEPTH = 32
MAX_NODES = 65_536
MAX_INTEGER_BITS = 4096
ALLOWED_NOTIFICATION_METHODS = frozenset(recipe.ALLOWED_EVENTS)


class JsonlError(ValueError):
    """Closed redacted code, never raw JSON, private keys or server error text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise JsonlError(code)


def _flags() -> dict:
    return {
        "runtime_observed": False,
        "provider_freshness_verified": False,
        "notification_semantics_verified": False,
        "full_protocol_conformance_verified": False,
        "accepted_trial": False,
        "sharing_authorized": False,
        "execution_authorized": False,
        "live_configuration_frozen": False,
        "live_benchmark_ready": False,
        "provider_calls_by_this_tool": 0,
        "target_execution": "not-run",
        "transport_status": "not-implemented",
    }


class Budget:
    """Single-owner shared accepted-byte/event/queued-notification counters.

    Share this object between sequential framers/inboxes, not their RPC ID namespace.
    A receive failure poisons every sharer. This is not persistent/adversarial-state
    protection; no reset/resume API or application-process lifetime claim is supplied.
    """

    __slots__ = ("_bytes", "_events", "_queued", "_failure")

    def __init__(self):
        self._bytes = self._events = self._queued = 0
        self._failure: str | None = None

    def _alive(self) -> None:
        _require(self._failure is None, "terminal-budget")

    def _fail(self, code: str) -> None:
        if self._failure is None:
            self._failure = code
        raise JsonlError(code)

    def _charge_bytes(self, amount: int) -> None:
        if self._bytes + amount > MAX_STREAM_BYTES:
            self._fail("stream-too-large")
        self._bytes += amount

    def _charge_event(self) -> None:
        if self._events >= MAX_EVENTS:
            self._fail("too-many-events")
        self._events += 1

    def _enqueue(self) -> None:
        if self._queued >= MAX_PENDING_NOTIFICATIONS:
            self._fail("too-many-notifications")
        self._queued += 1

    def snapshot(self) -> dict:
        return {
            "policy_version": POLICY_VERSION,
            "stream_bytes": self._bytes,
            "events": self._events,
            "queued_notifications": self._queued,
            "terminal": self._failure is not None,
            "failure_code": self._failure,
            **_flags(),
        }


def _shared(value: Budget | None) -> Budget:
    _require(value is None or type(value) is Budget, "invalid-budget")
    return Budget() if value is None else value


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate-json-key")
        result[key] = value
    return result


def _integer(raw: str) -> int:
    _require(len(raw) <= 1300, "integer-too-large")
    value = int(raw)
    _require(value.bit_length() <= MAX_INTEGER_BITS, "integer-too-large")
    return value


def _float(raw: str) -> float:
    value = float(raw)
    _require(math.isfinite(value), "nonfinite-json")
    return value


def _constant(raw: str) -> None:
    raise JsonlError("nonfinite-json")


def _raw_depth(raw: bytes) -> None:
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            _require(depth <= MAX_DEPTH, "json-too-deep")
        elif byte in (93, 125):
            depth -= 1
            _require(depth >= 0, "invalid-json")


def _values(value: dict) -> None:
    # Parsing has already bounded raw bytes, depth and integers. This iterative walk
    # additionally bounds decoded nodes and rejects escaped lone surrogates in keys.
    stack: list[object] = [value]
    nodes = 0
    while stack:
        node = stack.pop()
        nodes += 1
        _require(nodes <= MAX_NODES, "too-many-json-nodes")
        if type(node) is str:
            _require(
                not any(0xD800 <= ord(character) <= 0xDFFF for character in node),
                "invalid-utf8",
            )
        elif type(node) is dict:
            _require(nodes + len(stack) + 2 * len(node) <= MAX_NODES, "too-many-json-nodes")
            for key, child in node.items():
                stack.extend((key, child))
        elif type(node) is list:
            _require(nodes + len(stack) + len(node) <= MAX_NODES, "too-many-json-nodes")
            stack.extend(node)


def _decode(raw: bytes) -> dict:
    _require(raw.strip() != b"", "blank-frame")
    _require(not raw.startswith(b"\xef\xbb\xbf"), "utf8-bom")
    _raw_depth(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise JsonlError("invalid-utf8") from None
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_float,
            parse_constant=_constant,
        )
    except (json.JSONDecodeError, RecursionError, OverflowError):
        raise JsonlError("invalid-json") from None
    _require(type(value) is dict, "nonobject-json")
    _values(value)
    return value


class JsonlDecoder:
    """Incremental UTF-8 JSONL bytes; LF is mandatory, CRLF is JSON whitespace."""

    __slots__ = ("_budget", "_buffer", "_finished")

    def __init__(self, budget: Budget | None = None):
        self._budget = _shared(budget)
        self._buffer = bytearray()
        self._finished = False

    @property
    def budget(self) -> Budget:
        return self._budget

    def feed(self, chunk: bytes) -> tuple[dict, ...]:
        self.budget._alive()
        _require(not self._finished, "decoder-finished")
        _require(type(chunk) is bytes, "invalid-bytes")
        self.budget._charge_bytes(len(chunk))
        output = []
        start = 0
        while start < len(chunk):
            newline = chunk.find(b"\n", start)
            end = len(chunk) if newline < 0 else newline + 1
            if len(self._buffer) + end - start > MAX_FRAME_BYTES:
                self.budget._fail("frame-too-large")
            self._buffer.extend(chunk[start:end])
            if newline >= 0:
                self.budget._charge_event()
                try:
                    value = _decode(bytes(self._buffer[:-1]))
                except JsonlError as error:
                    self._buffer.clear()
                    self.budget._fail(error.code)
                self._buffer.clear()
                output.append(value)
            start = end
        return tuple(output)

    def finish(self) -> None:
        self.budget._alive()
        _require(not self._finished, "decoder-finished")
        if self._buffer:
            self.budget._fail("truncated-frame")
        self._finished = True


class RpcInbox:
    """One serial pending positive integer RPC, with private notification envelopes."""

    __slots__ = ("_budget", "_decoder", "_pending", "_last", "_completed", "_result", "_queue")

    def __init__(self, budget: Budget | None = None):
        self._budget = _shared(budget)
        self._decoder = JsonlDecoder(self.budget)
        self._pending: int | None = None
        self._last = 0
        self._completed: set[int] = set()
        self._result: dict | None = None
        self._queue: list[dict] = []

    @property
    def budget(self) -> Budget:
        return self._budget

    def arm(self, request_id: int) -> None:
        self.budget._alive()
        _require(not self._decoder._finished, "decoder-finished")
        _require(
            type(request_id) is int and 1 <= request_id <= MAX_REQUEST_ID,
            "invalid-request-id",
        )
        _require(self._pending is None, "request-already-pending")
        _require(self._result is None, "result-not-consumed")
        _require(request_id > self._last, "nonincreasing-request-id")
        self._pending = self._last = request_id

    def _accept(self, frame: dict) -> None:
        keys = set(frame)
        if "method" in frame:
            if "id" in frame:
                self.budget._fail("server-request-rejected")
            if (
                keys != {"method", "params"}
                or type(frame["method"]) is not str
                or frame["method"] not in ALLOWED_NOTIFICATION_METHODS
                or type(frame["params"]) is not dict
            ):
                self.budget._fail("notification-rejected")
            self.budget._enqueue()
            self._queue.append(frame)
            return
        if keys not in ({"id", "result"}, {"id", "error"}):
            self.budget._fail("invalid-envelope")
        identity = frame["id"]
        if type(identity) is not int or not 1 <= identity <= MAX_REQUEST_ID:
            self.budget._fail("invalid-response-id")
        if identity in self._completed:
            self.budget._fail("duplicate-response")
        if identity != self._pending:
            self.budget._fail("response-id-mismatch")
        if "error" in frame:
            self.budget._fail("rpc-error")
        if type(frame["result"]) is not dict:
            self.budget._fail("invalid-result")
        self._result = frame["result"]
        self._completed.add(identity)
        self._pending = None

    def feed(self, chunk: bytes) -> None:
        for frame in self._decoder.feed(chunk):
            self._accept(frame)

    def finish(self) -> None:
        self._decoder.finish()
        if self._pending is not None:
            self.budget._fail("missing-response")

    def take_result(self) -> dict | None:
        self.budget._alive()
        result, self._result = self._result, None
        return result

    def drain_notifications(self) -> tuple[dict, ...]:
        self.budget._alive()
        result = tuple(self._queue)
        self.budget._queued -= len(result)
        self._queue.clear()
        return result

    def snapshot(self) -> dict:
        return {
            **self.budget.snapshot(),
            "pending_requests": int(self._pending is not None),
            "result_ready": self._result is not None,
            "retired_responses": len(self._completed),
            "local_queued_notifications": len(self._queue),
            "decoder_finished": self._decoder._finished,
        }
