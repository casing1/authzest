"""Bounded runtime evidence for exact bundled fixtures, not general target execution."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import fixture_check
from authzest.runner._runtime_worker import (
    CHECK_ID,
    MAX_INPUT_BYTES,
    WORKER_SHA256,
    WORKER_SOURCE,
)

TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_BYTES = fixture_check.MAX_OUTPUT_BYTES
MAX_CLEANUP_SECONDS = fixture_check.MAX_CLEANUP_SECONDS


@dataclass(frozen=True, slots=True)
class RuntimeOutcome:
    """Observed fixed-fixture behavior, not dependency attestation or a verified fix."""

    status: str
    reason: str
    check_id: str
    source_sha256: str | None
    worker_sha256: str
    elapsed_ms: float
    exit_code: int | None
    runtime_evidence: dict | None


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "_runtime-worker"]
    # FastAPI is an optional installed dependency. Unlike the stdlib-only static
    # worker, -I without -S permits trusted interpreter/site startup and packages.
    return [sys.executable, "-I", "-c", WORKER_SOURCE]


def validate_runtime_evidence(evidence: object, source: bytes) -> bool:
    """Validate exact observations and bounded reported versions, not their provenance."""
    if type(source) is not bytes or source not in (
        FIXTURE_SOURCE.encode("utf-8"),
        FIXTURE_AFTER.encode("utf-8"),
    ):
        return False
    if type(evidence) is not dict or set(evidence) != {
        "debug",
        "health_status",
        "health_body",
        "dependency_versions",
    }:
        return False
    if (
        type(evidence["debug"]) is not bool
        or evidence["debug"] is not (source == FIXTURE_SOURCE.encode("utf-8"))
        or type(evidence["health_status"]) is not int
        or evidence["health_status"] != 200
        or type(evidence["health_body"]) is not dict
        or evidence["health_body"] != {"status": "ok"}
    ):
        return False
    versions = evidence["dependency_versions"]
    return (
        type(versions) is dict
        and set(versions) == {"python", "fastapi", "starlette", "pydantic"}
        and all(
            type(value) is str and re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,79}", value) is not None
            for value in versions.values()
        )
    )


def _validated_output(raw: bytes, source: bytes) -> tuple[str, str, dict | None]:
    payload = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=fixture_check._object,
        parse_constant=fixture_check._invalid_constant,
    )
    if type(payload) is not dict or set(payload) != {
        "schema_version",
        "check_id",
        "source_sha256",
        "status",
        "reason",
        "runtime_evidence",
    }:
        raise ValueError("Unexpected runtime worker fields")
    if (
        payload["schema_version"] != "1.0"
        or payload["check_id"] != CHECK_ID
        or payload["source_sha256"] != sha256(source).hexdigest()
    ):
        raise ValueError("Runtime worker identity mismatch")
    status, reason, evidence = payload["status"], payload["reason"], payload["runtime_evidence"]
    if (status, reason) == ("not-run", "runtime-dependency-unavailable") and evidence is None:
        return status, reason, None
    expected = (
        ("passed", "runtime-check-passed")
        if source == FIXTURE_AFTER.encode("utf-8")
        else ("failed", "debug-enabled")
    )
    if (status, reason) != expected or not validate_runtime_evidence(evidence, source):
        raise ValueError("Runtime observations do not match the maintained fixture")
    return status, reason, evidence


async def run_runtime_check(source: bytes) -> RuntimeOutcome:
    """Run one approved-by-caller fixed probe, with no automatic install or retry.

    Only exact bundled fixture constants execute. ASGI uses in-memory messages,
    not a TCP/UDP server or client; the event loop may use internal IPC. Trusted
    installed/bundled dependencies are outside an OS/network sandbox guarantee.
    Startup/I/O is bounded to five seconds, with separate one-second group cleanup.
    """
    started = perf_counter()
    digest = (
        sha256(source).hexdigest()
        if type(source) is bytes and len(source) <= MAX_INPUT_BYTES
        else None
    )
    exit_code = None

    def result(status: str, reason: str, evidence: dict | None = None) -> RuntimeOutcome:
        return RuntimeOutcome(
            status,
            reason,
            CHECK_ID,
            digest,
            WORKER_SHA256,
            (perf_counter() - started) * 1000,
            exit_code,
            evidence,
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
        with TemporaryDirectory(prefix="authzest-runtime-check-") as temporary:
            directory = Path(temporary).resolve()
            try:
                async with asyncio.timeout(TIMEOUT_SECONDS):
                    process = await asyncio.create_subprocess_exec(
                        *_command(),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        cwd=directory,
                        env=fixture_check._environment(directory),
                        start_new_session=True,
                        limit=MAX_OUTPUT_BYTES + 1,
                    )
                    raw = await fixture_check._exchange(process, source)
                    exit_code = await process.wait()
            finally:
                if process is not None:
                    await fixture_check._stop(process)
                    exit_code = process.returncode
    except TimeoutError:
        return result("failed", "timeout")
    except fixture_check._OutputLimitError:
        return result("failed", "output-limit")
    except (OSError, ValueError):
        return result("failed", "worker-process-error")
    if exit_code != 0:
        return result("failed", "worker-exit-error")
    try:
        status, reason, evidence = _validated_output(raw, source)
    except (UnicodeError, ValueError, TypeError):
        return result("failed", "invalid-worker-output")
    return result(status, reason, evidence)
