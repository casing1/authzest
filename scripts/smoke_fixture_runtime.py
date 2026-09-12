"""Check a trusted native parent's fixed offline runtime diagnostic, not user files.

This gate is separate from the source-inventory release smoke. Its controller uses
only the standard library and never imports AuthZest or its optional dependencies.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path

# Isolated `python -I scripts/...` omits the checkout from sys.path. Add only this
# script's own trusted checkout to reuse stdlib-only artifact helpers, not core.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.smoke_release import (  # noqa: E402
    SmokeError,
    child_environment,
    run_command,
    select_artifact,
    selected_binary,
)

CHECKOUT = Path(__file__).resolve().parents[1]
CHECK_ID = "owned-fixture-runtime-debug-health-v1"
AFTER_SHA256 = "e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe"
MAX_SUMMARY_BYTES = 16384


def expected_worker_hash() -> str:
    """Hash the checkout's literal worker text without importing/executing it."""
    path = CHECKOUT / "src" / "authzest" / "runner" / "_runtime_worker.py"
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = [
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "WORKER_SOURCE"
    ]
    if len(values) != 1:
        raise SmokeError("Expected one fixed WORKER_SOURCE literal in this checkout.")
    value = values[0]
    if (
        not isinstance(value, ast.Call)
        or not isinstance(value.func, ast.Attribute)
        or value.func.attr != "lstrip"
        or value.args
        or value.keywords
        or not isinstance(value.func.value, ast.Constant)
        or type(value.func.value.value) is not str
    ):
        raise SmokeError("Unsupported worker source declaration; review its fixed identity.")
    return hashlib.sha256(value.func.value.value.lstrip().encode("utf-8")).hexdigest()


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate summary field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Invalid summary number")


def validate_summary(text: str, worker_hash: str, *, posix: bool) -> dict:
    """Require exact AFTER evidence, or the declared unsupported-platform boundary."""
    if len(text.encode("utf-8")) > MAX_SUMMARY_BYTES:
        raise SmokeError("Runtime summary exceeds its size limit.")
    try:
        payload = json.loads(text, object_pairs_hook=_object, parse_constant=_invalid_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise SmokeError("Runtime diagnostic must emit one valid JSON summary.") from exc
    expected = {
        "kind": "owned-fixture-runtime-smoke",
        "schema_version": "1.0",
        "verification_scope": "owned-fixture-runtime",
        "source_sha256": AFTER_SHA256,
        "status": "passed" if posix else "unsupported",
        "reason": "runtime-check-passed" if posix else "unsupported-platform",
        "exit_code": 0 if posix else 2,
        "runtime_verification_status": "passed" if posix else "not-run",
    }
    if type(payload) is not dict or set(payload) != {*expected, "runtime"}:
        raise SmokeError("Runtime summary fields do not match the diagnostic contract.")
    for key, value in expected.items():
        if type(payload[key]) is not type(value) or payload[key] != value:
            raise SmokeError(f"Runtime summary has an unexpected {key}.")
    runtime = payload["runtime"]
    if not posix:
        if runtime is not None:
            raise SmokeError("Unsupported platforms must not report a worker result.")
        return payload
    expected_runtime = {
        "status": "passed",
        "reason": "runtime-check-passed",
        "check_id": CHECK_ID,
        "source_sha256": AFTER_SHA256,
        "worker_sha256": worker_hash,
        "exit_code": 0,
    }
    if type(runtime) is not dict or set(runtime) != {
        *expected_runtime,
        "elapsed_ms",
        "runtime_evidence",
    }:
        raise SmokeError("Runtime result fields do not match the fixed worker contract.")
    for key, value in expected_runtime.items():
        if type(runtime[key]) is not type(value) or runtime[key] != value:
            raise SmokeError(f"Runtime result has an unexpected {key}.")
    elapsed = runtime["elapsed_ms"]
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise SmokeError("Runtime elapsed time is invalid.")
    evidence = runtime["runtime_evidence"]
    if (
        type(evidence) is not dict
        or set(evidence) != {"debug", "health_status", "health_body", "dependency_versions"}
        or evidence["debug"] is not False
        or type(evidence["health_status"]) is not int
        or evidence["health_status"] != 200
        or type(evidence["health_body"]) is not dict
        or evidence["health_body"] != {"status": "ok"}
    ):
        raise SmokeError("Fixed runtime observations did not match the normal fixture.")
    versions = evidence["dependency_versions"]
    if (
        type(versions) is not dict
        or set(versions) != {"python", "fastapi", "starlette", "pydantic"}
        or not all(
            type(value) is str and re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,79}", value)
            for value in versions.values()
        )
    ):
        raise SmokeError("Runtime dependency version observations are invalid.")
    return payload


def smoke_runtime(
    binary: Path, timeout: float = 45, *, artifact_digest: str | None = None
) -> list[dict]:
    """Invoke only the actual native parent, never a standalone internal worker."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise SmokeError("Timeout must be finite and positive.")
    binary = selected_binary(binary)
    worker_hash = expected_worker_hash()
    results = []
    with tempfile.TemporaryDirectory(prefix="authzest-runtime-smoke-") as temporary:
        workspace = Path(temporary).resolve()
        bin_directory, cwd = workspace / "bin", workspace / "working"
        bin_directory.mkdir()
        cwd.mkdir()
        copied = bin_directory / ("authzest.exe" if binary.suffix.lower() == ".exe" else "authzest")
        shutil.copy2(binary, copied)
        if artifact_digest is not None:
            if hashlib.sha256(copied.read_bytes()).hexdigest() != artifact_digest:
                raise SmokeError("Copied artifact no longer matches the verified checksum.")
            copied.chmod(copied.stat().st_mode | stat.S_IXUSR)
        environment = child_environment(bin_directory)
        binaries = [copied] if artifact_digest is not None else [binary, copied]
        for executable in binaries:
            output = run_command(
                executable,
                ["_runtime-smoke"],
                0 if os.name == "posix" else 2,
                cwd,
                environment,
                timeout,
            )
            results.append(validate_summary(output, worker_hash, posix=os.name == "posix"))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--binary", type=Path, help="Exact trusted native AuthZest binary.")
    selection.add_argument(
        "--artifact-dir", type=Path, help="One platform's asset/checksum directory."
    )
    parser.add_argument(
        "--timeout", type=float, default=45, help="Outer command timeout (default: 45)."
    )
    arguments = parser.parse_args()
    try:
        binary, digest = (
            select_artifact(arguments.artifact_dir)
            if arguments.artifact_dir
            else (arguments.binary, None)
        )
        results = smoke_runtime(binary, arguments.timeout, artifact_digest=digest)
    except (SmokeError, OSError, ValueError, SyntaxError) as exc:
        raise SystemExit(f"Fixed runtime smoke failed: {exc}") from exc
    print(f"Fixed runtime smoke passed: {len(results)} native parent checks.")
    print(
        "Only the owned AFTER fixture; no Codex, user source, TCP/UDP listener or client traffic."
    )
    print("Windows checks unsupported/not-run behavior, not runtime feature support.")
    print("Reported versions are observations, not dependency attestation or broad compatibility.")


if __name__ == "__main__":
    main()
