"""Closed, owned pipe fixture; never Codex, a model, or a policy worker.

The fixture has no grandchildren, network access code, or filesystem writes. Its
private fragment-release input is test synchronization, not an app-server RPC.
"""

from __future__ import annotations

import json
import os
import signal
import sys

MODES = frozenset(
    {
        "success",
        "fragmented",
        "coalesced",
        "truncated",
        "malformed",
        "invalid-utf8",
        "warning",
        "foreign",
        "duplicate",
        "request-error",
        "eof",
        "nonzero",
        "wait",
        "ignore-term",
        "broken-pipe",
    }
)
INITIALIZED = {
    "id": 1,
    "result": {
        "codexHome": "/synthetic/codex-home",
        "platformFamily": "unix",
        "platformOs": "synthetic",
        "userAgent": "authzest-fake/0.153.0",
    },
}
RESULT = {"id": 2, "result": {"config": {"fixture_label": "한글"}, "origins": {}}}


def frame(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def send(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def expect(method: str, request_id: int | None = None) -> None:
    raw = sys.stdin.buffer.readline(8193)
    if len(raw) > 8192 or not raw.endswith(b"\n"):
        raise SystemExit(64)
    request = json.loads(raw)
    if request.get("method") != method or request.get("id") != request_id:
        raise SystemExit(64)


def ready(state: str) -> bytes:
    return frame(
        {
            "method": "thread/status/changed",
            "params": {"threadId": "synthetic-" + state, "status": {"type": "idle"}},
        }
    )


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in MODES or os.name != "posix":
        return 64
    if not sys.flags.isolated or not sys.flags.no_site or os.listdir("."):
        return 64
    if "HOME" in os.environ or "CODEX_HOME" in os.environ:
        return 64
    # Last-resort lifetime bound if a test runner disappears; not an OS sandbox.
    signal.alarm(7)
    mode = sys.argv[1]
    if mode == "ignore-term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    sys.stderr.write("OWNED_FIXTURE_STDERR_MUST_NOT_BE_CAPTURED\n")
    sys.stderr.flush()
    expect("initialize", 1)
    send(frame(INITIALIZED))
    expect("initialized")
    expect("config/read", 2)
    payload = frame(RESULT)

    if mode == "fragmented":
        split = payload.index("한".encode()) + 1
        send(payload[:split])
        # The parent must observe the incomplete UTF-8 fragment before release.
        if sys.stdin.buffer.readline(64) != b"fixture-release-fragment\n":
            return 64
        send(payload[split:])
    elif mode == "coalesced":
        send(ready("coalesced") + payload)
    elif mode == "truncated":
        send(b'{"id":2,"result":{}')
    elif mode == "malformed":
        send(b'{"id":2,\n')
    elif mode == "invalid-utf8":
        send(b'{"id":2,"result":{"value":"\xff"}}\n')
    elif mode == "warning":
        send(frame({"method": "configWarning", "params": {"summary": "PRIVATE_FIXTURE_TEXT"}}))
    elif mode == "foreign":
        send(frame({"id": 3, "result": {"fixture": True}}))
    elif mode == "duplicate":
        send(payload + payload)
    elif mode == "request-error":
        send(frame({"id": 2, "error": {"code": -32000, "message": "PRIVATE_FIXTURE_TEXT"}}))
    elif mode == "eof":
        return 0
    elif mode in {"wait", "ignore-term", "broken-pipe"}:
        if mode == "broken-pipe":
            os.close(sys.stdin.fileno())
        send(ready(mode))
        while True:
            signal.pause()
    else:
        send(payload)
    return 7 if mode == "nonzero" else 0


if __name__ == "__main__":
    raise SystemExit(main())
