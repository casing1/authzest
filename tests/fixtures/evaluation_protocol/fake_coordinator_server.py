"""Closed test peer: bounded canned RPC exchange, never Codex or a launcher.

The first stdin line is a private test bootstrap, not an app-server frame. It
contains only expected JSON requests and canned replies, never code or paths.
No descendants, sockets, files, account/config reads or provider calls are used.
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
        "nonzero",
        "malformed",
        "ack-malformed",
        "truncated",
        "eof",
        "stall",
        "ignore-term",
        "broken-pipe",
    }
)
LIMIT = 2 * 1024 * 1024


def read_line() -> object:
    raw = sys.stdin.buffer.readline(LIMIT + 1)
    if not raw or len(raw) > LIMIT or not raw.endswith(b"\n"):
        raise ValueError("invalid-test-input")
    return json.loads(raw)


def frame(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def output(raw: bytes, mode: str) -> None:
    # Writes may coalesce in an OS pipe. Tests separately bound read chunk sizes.
    stride = 7 if mode == "fragmented" else max(1, len(raw))
    for offset in range(0, len(raw), stride):
        view = memoryview(raw[offset : offset + stride])
        while view:
            view = view[os.write(1, view) :]


def wait_for_signal() -> None:
    while True:
        signal.pause()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        return 64
    # Test-only orphan backstop if the parent disappears before its 5s watchdog
    # and bounded cleanup run. Not a production process or syscall time bound.
    signal.alarm(7)
    mode = sys.argv[1]
    bootstrap = read_line()
    if type(bootstrap) is not dict or set(bootstrap) != {"steps"}:
        return 65
    steps = bootstrap["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= 20:
        return 65
    os.write(2, b"OWNED_COORDINATOR_STDERR_MUST_NOT_ESCAPE\n")
    for index, step in enumerate(steps):
        if type(step) is not dict or set(step) != {"request", "replies"}:
            return 65
        if read_line() != step["request"]:
            return 66
        replies = step["replies"]
        if type(replies) is not list or len(replies) > 12:
            return 65
        raw = b"".join(frame(value) for value in replies)
        if mode == "broken-pipe" and index == 0:
            # Closing stdin precedes the valid initialization response, giving
            # the host an exact readiness boundary before its next failed write.
            os.close(0)
            output(raw, mode)
            wait_for_signal()
        if index == len(steps) - 1:
            if mode == "ack-malformed":
                payload = frame(replies[0]) + b"{invalid}\n"
                if len(payload) > 4096:
                    return 65
                # One bounded write; pipe readers may still observe fragments.
                return 0 if os.write(1, payload) == len(payload) else 68
            if mode == "malformed":
                output(b"{invalid-json\n", mode)
                return 0
            if mode == "truncated":
                output(raw[:-1], mode)
                return 0
            if mode == "eof":
                return 0
            if mode in ("stall", "ignore-term"):
                if mode == "ignore-term":
                    signal.signal(signal.SIGTERM, signal.SIG_IGN)
                # Ack + settings + turn/started synchronize timeout/cancellation.
                output(b"".join(frame(value) for value in replies[:3]), mode)
                wait_for_signal()
        output(raw, mode)
    # Any extra client request fails the exact sequence, instead of being ignored.
    if sys.stdin.buffer.read(1) != b"":
        return 67
    return 9 if mode == "nonzero" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, BrokenPipeError):
        raise SystemExit(68) from None
