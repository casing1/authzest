"""Explicit fixed-fixture package diagnostic, not a user-file verification API.

No paths, commands, credentials or approval receipts are accepted. This diagnostic
executes only the maintained AFTER fixture through the normal runtime child.
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict
from hashlib import sha256

from authzest.codex.fixture_draft import FIXTURE_AFTER

KIND = "owned-fixture-runtime-smoke"
SCHEMA_VERSION = "1.0"


async def run_runtime_smoke() -> dict:
    """Check the bundled normal fixture; never invoke Codex or accept user source."""
    source = FIXTURE_AFTER.encode("utf-8")
    result = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "verification_scope": "owned-fixture-runtime",
        "source_sha256": sha256(source).hexdigest(),
        "status": "unsupported",
        "reason": "unsupported-platform",
        "exit_code": 2,
        "runtime_verification_status": "not-run",
        "runtime": None,
    }
    if os.name != "posix":
        return result

    # Imports stay after the platform guard. Missing optional dependencies cannot
    # turn an unsupported platform into an attempted worker or a false success.
    try:
        from authzest.runner import fixture_runtime

        outcome = asdict(await fixture_runtime.run_runtime_check(source))
        if outcome.get("status") == "not-run" and outcome.get("reason") == (
            "runtime-dependency-unavailable"
        ):
            return {
                **result,
                "status": "failed",
                "reason": "runtime-dependency-unavailable",
                "exit_code": 1,
            }
        if (
            set(outcome)
            != {
                "status",
                "reason",
                "check_id",
                "source_sha256",
                "worker_sha256",
                "elapsed_ms",
                "exit_code",
                "runtime_evidence",
            }
            or outcome["status"] != "passed"
            or outcome["reason"] != "runtime-check-passed"
            or outcome["check_id"] != fixture_runtime.CHECK_ID
            or outcome["source_sha256"] != result["source_sha256"]
            or outcome["worker_sha256"] != fixture_runtime.WORKER_SHA256
            or type(outcome["exit_code"]) is not int
            or outcome["exit_code"] != 0
            or type(outcome["elapsed_ms"]) not in (int, float)
            or not math.isfinite(outcome["elapsed_ms"])
            or outcome["elapsed_ms"] < 0
            or not fixture_runtime.validate_runtime_evidence(outcome["runtime_evidence"], source)
        ):
            raise ValueError("Unconfirmed fixed runtime result")
    except Exception:
        # Execution may already have started. Do not invent a not-run result or
        # expose exception/output details when the outcome cannot be validated.
        result.pop("runtime_verification_status")
        return {**result, "status": "failed", "reason": "runtime-check-unconfirmed", "exit_code": 1}
    return {
        **result,
        "status": "passed",
        "reason": "runtime-check-passed",
        "exit_code": 0,
        "runtime_verification_status": "passed",
        "runtime": outcome,
    }
