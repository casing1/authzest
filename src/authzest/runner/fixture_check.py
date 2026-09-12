"""Bounded child-process static check, not app execution or an OS/network sandbox."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner._configuration_worker import (
    CHECK_ID,
    MAX_INPUT_BYTES,
    WORKER_SHA256,
    WORKER_SOURCE,
)

TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_BYTES = 4096
MAX_CLEANUP_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    """Host-validated static evidence, never a runtime/security-fix verdict.

    worker_sha256 identifies the fixed checker text, not an attested executable.
    """

    status: str
    reason: str
    check_id: str
    source_sha256: str | None
    worker_sha256: str
    elapsed_ms: float
    exit_code: int | None


class _OutputLimitError(ValueError):
    pass


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "_configuration-worker"]
    return [sys.executable, "-I", "-S", "-c", WORKER_SOURCE]


def _environment(directory: Path) -> dict[str, str]:
    # No account, HOME, provider, Python injection, proxy, or ambient tool settings.
    # This is a reduced environment for trusted code, not network/OS confinement.
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(directory),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }


async def _stop(process: asyncio.subprocess.Process) -> None:
    # Every child has its own session/group, including frozen bootloader children.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await asyncio.wait_for(process.wait(), timeout=MAX_CLEANUP_SECONDS)


async def _exchange(process: asyncio.subprocess.Process, source: bytes) -> bytes:
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(source)
    await process.stdin.drain()
    process.stdin.close()
    output = bytearray()
    while True:
        chunk = await process.stdout.read(min(1024, MAX_OUTPUT_BYTES + 1 - len(output)))
        if not chunk:
            return bytes(output)
        output.extend(chunk)
        if len(output) > MAX_OUTPUT_BYTES:
            raise _OutputLimitError


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate worker field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Invalid worker number")


def _validated_output(raw: bytes, source: bytes) -> tuple[str, str]:
    payload = json.loads(
        raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_invalid_constant
    )
    expected_status, expected_reason = (
        ("passed", "debug-disabled")
        if source == FIXTURE_AFTER.encode("utf-8")
        else ("failed", "debug-enabled")
    )
    expected = {
        "schema_version": "1.0",
        "check_id": CHECK_ID,
        "source_sha256": sha256(source).hexdigest(),
        "status": expected_status,
        "reason": expected_reason,
    }
    if type(payload) is not dict or payload != expected:
        raise ValueError("Worker output does not match the exact fixed check")
    return expected_status, expected_reason


async def run_configuration_check(source: bytes) -> VerificationOutcome:
    """Inspect exact maintained bytes in a disposable process; never read source paths.

    The caller owns separate approval and before/after file-state checks. No approval
    is inferred here. The five-second deadline covers startup and I/O; process-group
    kill/reap has a separate bounded one-second cleanup allowance. Cancellation is
    propagated after cleanup. No retry, shell, import/exec of input, or model call.
    """
    started = perf_counter()
    digest = (
        sha256(source).hexdigest()
        if type(source) is bytes and len(source) <= MAX_INPUT_BYTES
        else None
    )
    exit_code = None

    def result(status: str, reason: str) -> VerificationOutcome:
        return VerificationOutcome(
            status,
            reason,
            CHECK_ID,
            digest,
            WORKER_SHA256,
            (perf_counter() - started) * 1000,
            exit_code,
        )

    if type(source) is not bytes or source not in (
        FIXTURE_SOURCE.encode("utf-8"),
        FIXTURE_AFTER.encode("utf-8"),
    ):
        return result("not-run", "invalid-source")
    if len(source) > MAX_INPUT_BYTES or os.name != "posix":
        return result("not-run", "unsupported-platform-or-input")

    process = None
    try:
        with TemporaryDirectory(prefix="authzest-configuration-check-") as temporary:
            directory = Path(temporary).resolve()
            try:
                async with asyncio.timeout(TIMEOUT_SECONDS):
                    process = await asyncio.create_subprocess_exec(
                        *_command(),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        cwd=directory,
                        env=_environment(directory),
                        start_new_session=True,
                        limit=MAX_OUTPUT_BYTES + 1,
                    )
                    raw = await _exchange(process, source)
                    exit_code = await process.wait()
            finally:
                if process is not None:
                    await _stop(process)
                    exit_code = process.returncode
    except TimeoutError:
        return result("failed", "timeout")
    except _OutputLimitError:
        return result("failed", "output-limit")
    except (OSError, ValueError):
        return result("failed", "worker-process-error")
    if exit_code != 0:
        return result("failed", "worker-exit-error")
    try:
        status, reason = _validated_output(raw, source)
    except (UnicodeError, ValueError, TypeError):
        return result("failed", "invalid-worker-output")
    return result(status, reason)
