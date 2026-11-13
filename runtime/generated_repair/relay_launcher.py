"""Fixed B entry source; only guarded main selects actual socket/time/stdout APIs.

Host timeout and container cleanup remain authoritative. A guest-local remaining
duration is only a deadline snapshot, not a fresh host phase or runtime evidence.
"""

from __future__ import annotations

import json
import math
import re
from enum import IntEnum
from types import CoroutineType

SCRIPT_PATH = "/opt/authzest-guest/relay_launcher.py"


def parse_remaining_ms(text: str) -> int:
    if (
        type(text) is not str
        or len(text) > 5
        or re.fullmatch(r"[1-9][0-9]*", text) is None
        or int(text) > 40000
    ):
        raise ValueError("guest-duration")
    return int(text)


def capture_relay(remaining_ms, *, codec, socket_factory, af_inet, sock_stream, clock):
    """Use explicit trusted collaborators; no module default can open a socket."""
    if type(remaining_ms) is not int or not 1 <= remaining_ms <= 40000:
        raise ValueError("guest-duration")
    for value, expected in ((af_inet, 2), (sock_stream, 1)):
        if not (type(value) is int or isinstance(value, IntEnum)) or int.__int__(value) != expected:
            raise ValueError("guest-address-family")
    last = None

    def now():
        nonlocal last
        value = clock()
        if type(value) is CoroutineType:
            value.close()
            raise ValueError("guest-clock")
        if (
            type(value) not in (int, float)
            or not 0 <= value <= 2**48
            or not math.isfinite(value)
            or last is not None
            and value < last
        ):
            raise ValueError("guest-clock")
        last = float(value)
        return last

    deadline = now() + remaining_ms / 1000

    def remaining():
        value = deadline - now()
        if value <= 0:
            raise TimeoutError("guest-deadline")
        return value

    def sync_none(value):
        if type(value) is CoroutineType:
            value.close()
        if value is not None:
            raise ValueError("guest-socket-return")

    class OwnedStream:
        """Own the raw socket before connection; never reconnect or resend."""

        def __init__(self, raw):
            self.raw = raw
            self.attempted = self.sent = self.closed = False

        def settimeout(self, supplied):
            sync_none(self.raw.settimeout(min(supplied, remaining())))

        def sendall(self, data):
            if self.attempted or self.closed:
                raise ValueError("guest-send-reused")
            self.attempted = True
            sync_none(self.raw.settimeout(remaining()))
            remaining()
            sync_none(self.raw.connect(("127.0.0.1", 8765)))
            remaining()
            # Connection time is charged; do not reuse its older socket timeout.
            sync_none(self.raw.settimeout(remaining()))
            remaining()
            sync_none(self.raw.sendall(data))
            self.sent = True

        def recv(self, count):
            if not self.sent or self.closed:
                raise ValueError("guest-receive-state")
            return self.raw.recv(count)

        def close(self):
            if self.closed:
                raise ValueError("guest-close-reused")
            self.closed = True
            return self.raw.close()

    seen_raw = []

    def factory(host, port, timeout):
        if (host, port) != ("127.0.0.1", 8765) or timeout <= 0:
            raise ValueError("guest-target")
        # No post-allocation action can fail before codec takes wrapper ownership.
        raw = socket_factory(af_inet, sock_stream)
        if type(raw) is CoroutineType:
            raw.close()
            raise ValueError("guest-socket-contract")
        if raw is None or any(raw is previous for previous in seen_raw):
            raise ValueError("guest-socket-contract")
        seen_raw.append(raw)
        return OwnedStream(raw)

    return codec.capture_fixed_http(stream_factory=factory, phase_deadline=deadline, clock=now)


def emit_capture(capture, write) -> int:
    """Write bounded raw JSON, not a pass certificate or cleanup attestation."""
    raw = capture.payload_json
    if type(raw) is not str or len(raw) > 262144:
        raise ValueError("guest-output-budget")
    try:
        encoded = raw.encode("utf-8")
        data = json.loads(raw)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("guest-output-json") from exc
    if len(encoded) > 262144:
        raise ValueError("guest-output-budget")
    if (
        type(data) is not dict
        or type(data.get("status")) is not str
        or data["status"] not in {"complete", "partial"}
    ):
        raise ValueError("guest-output-status")
    written = write(encoded)
    if type(written) is CoroutineType:
        written.close()
    if type(written) is not int or written != len(encoded):
        raise ValueError("guest-output-incomplete")
    return 0 if data["status"] == "complete" else 1


def _script_main() -> int:
    import os
    import sys

    if __file__ != SCRIPT_PATH or sys.platform != "linux":
        return 64
    sys.path.insert(0, "/opt/authzest-guest")
    from _guest_common import entry_allowed, prepare_environment

    if not entry_allowed(
        "B",
        script_path=__file__,
        argv=sys.argv,
        platform=sys.platform,
        isolated=sys.flags.isolated,
        dont_write_bytecode=sys.dont_write_bytecode,
        uid=os.getuid(),
        gid=os.getgid(),
    ):
        return 64
    prepare_environment(os.environ, sys.path)
    import socket
    import time

    import _generated_repair_http as codec

    result = capture_relay(
        parse_remaining_ms(sys.argv[1]),
        codec=codec,
        socket_factory=socket.socket,
        af_inet=socket.AF_INET,
        sock_stream=socket.SOCK_STREAM,
        clock=time.monotonic,
    )
    code = emit_capture(result, sys.stdout.buffer.write)
    sys.stdout.buffer.flush()
    return code


if __name__ == "__main__":
    raise SystemExit(_script_main())
