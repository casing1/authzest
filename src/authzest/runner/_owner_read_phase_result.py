"""Compare supplied owner-read guest captures without observing or executing a runtime.

The transport must first establish complete captures from its owned guests. This
module checks detached bytes only. Its result is retained history and provides
no runtime, patch, restoration or imported-decision authority.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

from authzest.codex.contracts import ContractError, canonical, decode
from authzest.owner_read_demo.checks import (
    compare_owner_read_observations,
    owner_read_controls,
)

MAX_CAPTURE_BYTES = 262_144
MAX_RESULT_BYTES = 524_288
_ROLES = ("test", "controls")
_CAPTURE_FIELDS = {"exit_code", "stdout", "stderr", "cleanup_confirmed"}
_GUEST_FIELDS = {"kind", "schema_version", "role", "source_sha256", "test_sha256"}
_REGRESSION_FIELDS = {
    "status",
    "pytest_exit",
    "collected",
    "setup",
    "call",
    "teardown",
    "requests",
    "response",
}


@dataclass(frozen=True, slots=True)
class OwnerReadPhaseResult:
    """Detached evidence, never an executable plan or a readiness capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return json.loads(self.payload_json)


def _digest(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _response(value: object) -> bool:
    if type(value) is not dict or value.keys() != {"status_code", "body"}:
        return False
    status, body = value["status_code"], value["body"]
    return (
        type(status) is int
        and 100 <= status <= 599
        and type(body) is dict
        and len(body) <= 8
        and all(
            type(key) is str and len(key) <= 64 and type(child) is str and len(child) <= 256
            for key, child in body.items()
        )
    )


def _regression(value: object) -> bool:
    if type(value) is not dict or value.keys() != _REGRESSION_FIELDS:
        return False
    if (
        any(type(value[key]) is not int for key in ("pytest_exit", "collected", "requests"))
        or value["collected"] != 1
        or value["requests"] != 1
        or value["setup"] != "passed"
        or value["teardown"] != "passed"
        or not _response(value["response"])
    ):
        return False
    return (value["status"], value["pytest_exit"], value["call"]) in (
        ("assertion-failed", 1, "failed"),
        ("passed", 0, "passed"),
    )


def _snapshot(value: dict) -> OwnerReadPhaseResult:
    raw = canonical(value)
    if len(raw.encode("utf-8")) > MAX_RESULT_BYTES:
        # No partial output is retained as a successful phase.
        value.update(status="failed", failure="result-budget-exceeded", captures={})
        raw = canonical(value)
    return OwnerReadPhaseResult(raw)


def validate_owner_read_phase(
    *,
    phase: str,
    plan_id: str,
    source_sha256: str,
    test_sha256: str,
    captures: dict,
) -> OwnerReadPhaseResult:
    """Compare two complete supplied captures against the maintained phase profile.

    Raw output from both guests shares a 256 KiB budget. Bounded raw captures are
    retained as base64 for private inspection even when parsing or matching fails.
    No path, process, Engine, provider or source artifact is accessed here.
    """
    result = {
        "schema_version": "1.0",
        "kind": "owner-read-phase-result",
        "provenance": "supplied-guest-captures",
        "phase": phase if type(phase) is str and phase in ("before", "after") else None,
        "plan_id": plan_id
        if type(plan_id) is str and re.fullmatch(r"[\x21-\x7e]{1,128}", plan_id)
        else None,
        "source_sha256": source_sha256 if _digest(source_sha256) else None,
        "test_sha256": test_sha256 if _digest(test_sha256) else None,
        "status": "failed",
        "failure": None,
        "cleanup_confirmed": False,
        "regression": None,
        "observations": None,
        "comparison": None,
        "captures": {},
    }
    if (
        result["phase"] is None
        or result["plan_id"] is None
        or not _digest(source_sha256)
        or not _digest(test_sha256)
    ):
        result["failure"] = "invalid-expected-identity"
        return _snapshot(result)
    if type(captures) is not dict or captures.keys() != set(_ROLES):
        result["failure"] = "invalid-capture-shape"
        return _snapshot(result)
    total = 0
    for role in _ROLES:
        capture = captures[role]
        if (
            type(capture) is not dict
            or capture.keys() != _CAPTURE_FIELDS
            or type(capture["exit_code"]) is not int
            or not -255 <= capture["exit_code"] <= 255
            or type(capture["stdout"]) is not bytes
            or type(capture["stderr"]) is not bytes
            or type(capture["cleanup_confirmed"]) is not bool
        ):
            result["failure"] = "invalid-capture-shape"
            return _snapshot(result)
        total += len(capture["stdout"]) + len(capture["stderr"])
    if total > MAX_CAPTURE_BYTES:
        result["failure"] = "capture-budget-exceeded"
        return _snapshot(result)
    for role in _ROLES:
        capture = captures[role]
        result["captures"][role] = {
            "exit_code": capture["exit_code"],
            "stdout_bytes": len(capture["stdout"]),
            "stderr_bytes": len(capture["stderr"]),
            "stdout_base64": base64.b64encode(capture["stdout"]).decode("ascii"),
            "stderr_base64": base64.b64encode(capture["stderr"]).decode("ascii"),
            "cleanup_confirmed": capture["cleanup_confirmed"],
        }
    result["cleanup_confirmed"] = all(captures[role]["cleanup_confirmed"] for role in _ROLES)
    if not result["cleanup_confirmed"]:
        result["failure"] = "cleanup-unconfirmed"
        return _snapshot(result)
    if any(captures[role]["exit_code"] != 0 or captures[role]["stderr"] for role in _ROLES):
        result["failure"] = "guest-failed"
        return _snapshot(result)

    records = {}
    try:
        for role in _ROLES:
            record = decode(captures[role]["stdout"].decode("utf-8"))
            field = "regression" if role == "test" else "observations"
            if record.keys() != _GUEST_FIELDS | {field}:
                raise ContractError("Invalid guest record fields")
            expected = {
                "kind": "owner-read-guest-observation",
                "schema_version": "1.0",
                "role": role,
                "source_sha256": source_sha256,
                "test_sha256": test_sha256,
            }
            if {key: record[key] for key in _GUEST_FIELDS} != expected:
                result["failure"] = "guest-identity-mismatch"
                return _snapshot(result)
            records[role] = record
    except (ContractError, UnicodeError):
        result["failure"] = "invalid-guest-json"
        return _snapshot(result)

    regression = records["test"]["regression"]
    observations = records["controls"]["observations"]
    comparison = compare_owner_read_observations(observations)
    if comparison["status"] != "compared":
        result["failure"] = "invalid-controls"
        return _snapshot(result)
    result.update(observations=observations, comparison=comparison)
    if not _regression(regression):
        result["failure"] = "pytest-lifecycle-error"
        return _snapshot(result)
    result["regression"] = regression
    before = phase == "before"
    archived = next(case for case in owner_read_controls() if case["case_id"] == "owner-archived")
    expected_regression = {
        "status": "assertion-failed" if before else "passed",
        "pytest_exit": 1 if before else 0,
        "collected": 1,
        "setup": "passed",
        "call": "failed" if before else "passed",
        "teardown": "passed",
        "requests": 1,
        "response": archived["before" if before else "intended"],
    }
    profile = "matches_before_profile" if before else "matches_intended_policy"
    if canonical(regression) != canonical(expected_regression) or comparison[profile] is not True:
        result.update(status="mismatch", failure="unexpected-observations")
    else:
        result.update(status="matched", failure=None)
    return _snapshot(result)
