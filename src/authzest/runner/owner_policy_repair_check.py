"""Separately consented checks of one registered synthetic candidate at a time.

Preparation and validation are offline data operations. A live in-process session
owns a terminal, expiring, single-use decision, not an authenticated capability.
Embedded after is a control, never verification that a workspace patch was applied.
"""

from __future__ import annotations

import asyncio
import math
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from authzest.codex.contracts import ContractError, _object, canonical, decode, identity
from authzest.codex.owner_policy_repair_pair import (
    build_owner_policy_repair_pair,
    validate_owner_policy_repair_pair,
)
from authzest.runner._owner_policy_repair_transport import (
    MAX_CLEANUP_SECONDS,
    TIMEOUT_SECONDS,
    WorkerTransport,
)
from authzest.runner._owner_policy_repair_transport import run_worker as _run_worker
from authzest.runner._owner_policy_repair_worker import (
    CHECK_ID,
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    WORKER_SHA256,
    WORKER_SOURCE,
)

MAX_DECISION_SECONDS = 300.0
RECIPE_VERSION = "1.0"
_REASONS = {
    "attempt-already-consumed",
    "execution-decision-invalidated",
    "stale-plan",
    "invalid-context",
    "execution-decision-pending",
    "execution-decision-declined",
    "execution-decision-cancelled",
    "expired-or-invalid-decision-time",
    "invalid-decision-time",
    "unsupported-platform",
    "worker-input-error",
    "worker-process-error",
    "worker-exit-error",
    "timeout",
    "output-limit",
    "cleanup-unconfirmed",
    "invalid-worker-transport",
    "invalid-worker-output",
    "cancelled",
    "cases-match",
    "case-mismatch",
}
_TRANSPORT_REASONS = {
    None,
    "worker-input-error",
    "worker-process-error",
    "worker-exit-error",
    "timeout",
    "output-limit",
    "cleanup-unconfirmed",
    "cancelled",
}
_PREFLIGHT_REASONS = {
    "attempt-already-consumed",
    "execution-decision-invalidated",
    "stale-plan",
    "invalid-context",
    "execution-decision-pending",
    "execution-decision-declined",
    "execution-decision-cancelled",
    "expired-or-invalid-decision-time",
    "invalid-decision-time",
    "unsupported-platform",
    "worker-input-error",
}
_PLAN_FIELDS = {
    "schema_version",
    "kind",
    "check_plan_id",
    "candidate",
    "bindings",
    "worker_input",
    "planning_status",
    "requires_separate_execution_approval",
    "execution_status",
    "authorization_status",
    "provider_calls",
    "patch_application",
    "restoration_status",
}
_RESULT_FIELDS = {
    "schema_version",
    "kind",
    "check_plan",
    "check_plan_id",
    "candidate",
    "status",
    "reason",
    "execution_status",
    "comparison_status",
    "cases",
    "launch_status",
    "child_cleanup_status",
    "workspace_cleanup_status",
    "cleanup_status",
    "exit_code",
    "authorization_status",
    "provider_calls",
    "patch_application",
    "restoration_status",
    "provenance",
}


@dataclass(frozen=True, slots=True)
class _Snapshot:
    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class OwnerPolicyRepairCheckPlan(_Snapshot):
    @property
    def check_plan_id(self) -> str:
        return self.to_dict()["check_plan_id"]


@dataclass(frozen=True, slots=True)
class OwnerPolicyRepairCheckResult(_Snapshot):
    """Host-recorded data; direct construction does not attest execution."""


def _snapshot(data: dict, kind):
    raw = canonical(data)
    decode(raw)
    return kind(raw)


def _recipe() -> dict:
    return {
        "id": CHECK_ID,
        "version": RECIPE_VERSION,
        "implementation_version": "repair-check-coordinator-v1",
        "mapping_version": "registered-eight-nullable-dataclasses-exact-v1",
        "protocol_version": "1.0",
        "comparison_version": "observed-bool-to-reviewed-allow-deny-v1",
        "target": "one registered embedded policy candidate; not an applied file",
        "platform": "POSIX non-frozen Python source only",
        "worker_sha256": WORKER_SHA256,
        "launch": ["trusted sys.executable", "-I", "-S", "-c", "pinned WORKER_SOURCE"],
        "attempt_limit": 1,
        "max_decision_seconds": MAX_DECISION_SECONDS,
        "case_count": 8,
        "max_scopes": 16,
        "max_identifier_characters": 128,
        "max_input_bytes": MAX_INPUT_BYTES,
        "max_output_bytes": MAX_OUTPUT_BYTES,
        "max_depth": 32,
        "max_nodes": 8192,
        "timeout_seconds": TIMEOUT_SECONDS,
        "cleanup_timeout_seconds": MAX_CLEANUP_SECONDS,
        "environment": {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": "fresh private temporary cwd",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
            "NO_COLOR": "1",
            "TERM": "dumb",
        },
        "cleanup": "separate child and workspace status; no observations until both confirmed",
        "filesystem_deadline_hard_capped": False,
        "confinement": "trusted child, not an OS/network sandbox or CPU/memory hard cap",
        "exclusions": [
            "caller source/paths/cases/commands",
            "model/reviewer prose in child input",
            "FastAPI/HTTP/auth/database",
            "provider/network/install hooks",
            "automatic before-to-after execution",
            "patch application/restoration/applied-file verification",
            "automatic retry/model fallback",
        ],
    }


def prepare_owner_policy_repair_check(candidate: str) -> OwnerPolicyRepairCheckPlan:
    """Prepare one complete fixed plan; no path reads, child or policy evaluation."""
    if type(candidate) is not str or candidate not in {"before", "after"}:
        raise ContractError("Expected exactly before or after", code="validation-shape")
    pair = build_owner_policy_repair_pair()
    pair = validate_owner_policy_repair_pair(pair.payload_json)
    data = pair.to_dict()
    content = data["content"]
    if sha256(WORKER_SOURCE.encode("utf-8")).hexdigest() != WORKER_SHA256:
        raise ContractError("Registered worker changed", code="validation-identity")
    cases = []
    for case in content["cases"]:
        row = {key: case[key] for key in ("case_id", "principal", "report")}
        cases.append({**row, "input_sha256": identity(row)})
    recipe = _recipe()
    bindings = {
        "pair": data,
        "pair_id": pair.pair_id,
        "candidate": candidate,
        "source": content[candidate],
        "cases": content["cases"],
        "worker_source": WORKER_SOURCE,
        "worker_sha256": WORKER_SHA256,
        "recipe": recipe,
        "recipe_sha256": identity(recipe),
        "input_cases": cases,
        "input_sha256": identity(cases),
    }
    plan_id = "owner-repair-check-" + identity(bindings)
    wire = {
        "schema_version": "1.0",
        "check_id": CHECK_ID,
        "plan_id": plan_id,
        "candidate": candidate,
        "policy_source_sha256": content[candidate]["sha256"],
        "worker_sha256": WORKER_SHA256,
        "input_sha256": bindings["input_sha256"],
        "cases": cases,
    }
    if len(canonical(wire).encode("utf-8")) > MAX_INPUT_BYTES:
        raise ContractError("Worker input exceeds budget", code="validation-budget")
    return _snapshot(
        {
            "schema_version": "1.0",
            "kind": "owner-policy-repair-check-plan",
            "check_plan_id": plan_id,
            "candidate": candidate,
            "bindings": bindings,
            "worker_input": wire,
            "planning_status": "requires-fresh-execution-decision",
            "requires_separate_execution_approval": True,
            "execution_status": "not-run",
            "authorization_status": "unknown",
            "provider_calls": 0,
            "patch_application": "not-run",
            "restoration_status": "not-run",
        },
        OwnerPolicyRepairCheckPlan,
    )


def validate_owner_policy_repair_check_plan(raw: str) -> OwnerPolicyRepairCheckPlan:
    data = _object(decode(raw), _PLAN_FIELDS)
    expected = prepare_owner_policy_repair_check(data["candidate"])
    if canonical(data) != expected.payload_json:
        raise ContractError("Repair check plan mismatch", code="validation-identity")
    return expected


def _finite(value) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ContractError("Invalid finite decision time", code="validation-shape")
    return float(value)


def _transport_valid(value) -> bool:
    if type(value) is not WorkerTransport:
        return False
    if (
        type(value.output) is not bytes
        or (value.exit_code is not None and type(value.exit_code) is not int)
        or (value.reason is not None and type(value.reason) is not str)
        or value.reason not in _TRANSPORT_REASONS
        or type(value.launch_status) is not str
        or value.launch_status not in {"not-attempted", "no-child", "ambiguous", "started"}
    ):
        return False
    for field in ("child_cleanup_status", "workspace_cleanup_status"):
        status = getattr(value, field)
        if type(status) is not str or status not in {"not-needed", "confirmed", "unconfirmed"}:
            return False
    if value.launch_status != "not-attempted" and value.workspace_cleanup_status == "not-needed":
        return False
    if value.launch_status in {"not-attempted", "no-child"}:
        return (
            value.child_cleanup_status == "not-needed"
            and value.exit_code is None
            and not value.output
        )
    if value.launch_status == "ambiguous":
        return (
            value.child_cleanup_status == "unconfirmed"
            and value.exit_code is None
            and not value.output
        )
    return value.child_cleanup_status != "not-needed" and (
        value.child_cleanup_status != "confirmed" or type(value.exit_code) is int
    )


def _cleanup_status(transport: WorkerTransport) -> str:
    statuses = {transport.child_cleanup_status, transport.workspace_cleanup_status}
    if "unconfirmed" in statuses:
        return "unconfirmed"
    return "not-needed" if statuses == {"not-needed"} else "confirmed"


def _unknown_transport() -> WorkerTransport:
    return WorkerTransport(
        b"", None, "worker-process-error", "unconfirmed", "unconfirmed", "ambiguous"
    )


def _diagnostics_match_reason(reason: str, transport: WorkerTransport) -> bool:
    """Reject impossible lifecycle claims, without authenticating a host record."""
    if reason in _PREFLIGHT_REASONS:
        return (
            transport.launch_status == "not-attempted"
            and transport.child_cleanup_status == "not-needed"
            and transport.workspace_cleanup_status == "not-needed"
            and transport.exit_code is None
        )
    if reason == "cleanup-unconfirmed":
        return _cleanup_status(transport) == "unconfirmed"
    completed_child = (
        transport.launch_status == "started"
        and transport.child_cleanup_status == "confirmed"
        and transport.workspace_cleanup_status == "confirmed"
        and type(transport.exit_code) is int
    )
    if reason in {"invalid-worker-output", "cases-match", "case-mismatch"}:
        return completed_child and transport.exit_code == 0
    if reason == "worker-exit-error":
        return completed_child and transport.exit_code != 0
    if reason == "output-limit":
        return completed_child
    if reason == "timeout":
        return transport.launch_status in {"started", "no-child"} and (
            _cleanup_status(transport) == "confirmed"
        )
    # Cancellation can interrupt cleanup; unexpected transport exceptions are
    # intentionally ambiguous. Neither category can publish observations.
    return True


def _result_data(plan, reason, *, observed=None, transport=None):
    if reason not in _REASONS:
        raise ContractError("Unexpected check reason")
    data = plan.to_dict()
    transport = transport or WorkerTransport(
        b"", None, None, "not-needed", "not-needed", "not-attempted"
    )
    rows = []
    for index, case in enumerate(data["bindings"]["cases"]):
        value = observed[index] if observed is not None else None
        rows.append(
            {
                "case_id": case["case_id"],
                "input_sha256": data["bindings"]["input_cases"][index]["input_sha256"],
                "expected": case["expected"],
                "observed": value,
                "result": "unknown"
                if value is None
                else ("passed" if value is (case["expected"] == "allow") else "failed"),
            }
        )
    status = (
        "not-run"
        if observed is None
        else ("passed" if all(row["result"] == "passed" for row in rows) else "failed")
    )
    return {
        "schema_version": "1.0",
        "kind": "owner-policy-repair-check-result",
        "check_plan": data,
        "check_plan_id": data["check_plan_id"],
        "candidate": data["candidate"],
        "status": status,
        "reason": reason,
        "execution_status": "completed"
        if observed is not None
        else ("attempted" if transport.launch_status in {"started", "ambiguous"} else "not-run"),
        "comparison_status": "not-evaluated" if observed is None else status,
        "cases": rows,
        "launch_status": transport.launch_status,
        "child_cleanup_status": transport.child_cleanup_status,
        "workspace_cleanup_status": transport.workspace_cleanup_status,
        "cleanup_status": _cleanup_status(transport),
        "exit_code": transport.exit_code,
        "authorization_status": "unknown",
        "provider_calls": 0,
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "provenance": {
            "kind": "in-process-host-record",
            "authenticated": False,
            "scope": "registered synthetic control observation; not applied-file verification",
        },
    }


def _validated_output(raw: bytes, plan: OwnerPolicyRepairCheckPlan) -> list[bool]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_OUTPUT_BYTES:
        raise ContractError("Invalid worker output size", code="validation-budget")
    data = decode(raw.decode("utf-8"))
    expected = plan.to_dict()["worker_input"]
    _object(data, set(expected))
    for key in expected:
        if key != "cases" and canonical(data[key]) != canonical(expected[key]):
            raise ContractError("Worker identity mismatch", code="validation-identity")
    rows = data["cases"]
    if type(rows) is not list or len(rows) != 8:
        raise ContractError("Unexpected worker case count", code="validation-shape")
    observations = []
    for row, original in zip(rows, expected["cases"], strict=True):
        _object(row, {"case_id", "input_sha256", "observed"})
        if (
            row["case_id"] != original["case_id"]
            or row["input_sha256"] != original["input_sha256"]
            or type(row["observed"]) is not bool
        ):
            raise ContractError("Worker case mismatch", code="validation-identity")
        observations.append(row["observed"])
    return observations


class OwnerPolicyRepairCheckSession:
    """One live current-state decision; imported records never authorize a run."""

    def __init__(self, candidate: str, *, clock=monotonic):
        if not callable(clock):
            raise ContractError("Invalid decision clock", code="validation-shape")
        self._clock: Callable[[], float] = clock
        self._last_clock = _finite(clock())
        self._plan = prepare_owner_policy_repair_check(candidate)
        self._decision: _Snapshot | None = None
        self._used = False
        self._invalidated = False
        self.last_result: OwnerPolicyRepairCheckResult | None = None

    @property
    def plan(self) -> OwnerPolicyRepairCheckPlan:
        return self._plan

    def _time(self) -> float:
        try:
            now = _finite(self._clock())
        except Exception as exc:
            raise ContractError("Invalid decision clock", code="validation-shape") from exc
        if now < self._last_clock:
            raise ContractError("Decision clock moved backwards", code="validation-shape")
        self._last_clock = now
        return now

    def decide(self, choice, *, plan_id, lifetime_seconds=MAX_DECISION_SECONDS):
        if self._used:
            raise ContractError("Repair check attempt already consumed")
        if self._invalidated:
            raise ContractError("Repair check session invalidated")
        previous = self._decision.to_dict() if self._decision else None
        self._invalidated = True
        self._decision = None
        now = self._time()
        if previous is not None and (
            previous["choice"] != "pending" or not now < previous["expires_at"]
        ):
            raise ContractError("Only a current pending choice can be replaced")
        if type(choice) is not str or choice not in {
            "pending",
            "approved",
            "declined",
            "cancelled",
        }:
            raise ContractError("Invalid execution choice", code="validation-shape")
        if type(plan_id) is not str or plan_id != self._plan.check_plan_id:
            raise ContractError("Execution choice for another plan", code="validation-identity")
        duration = _finite(lifetime_seconds)
        expires = _finite(now + duration)
        if not 0 < duration <= MAX_DECISION_SECONDS or not expires > now:
            raise ContractError("Invalid decision lifetime", code="validation-shape")
        self._decision = _snapshot(
            {
                "kind": "live-owner-repair-execution-choice",
                "plan_id": plan_id,
                "choice": choice,
                "created_at": now,
                "expires_at": expires,
                "reviewer_authenticated": False,
                "purpose": "one-registered-candidate-check",
            },
            _Snapshot,
        )
        self._invalidated = False
        return self._decision

    def _result(self, reason, *, observed=None, transport=None, retain=True):
        result = _snapshot(
            _result_data(self._plan, reason, observed=observed, transport=transport),
            OwnerPolicyRepairCheckResult,
        )
        if retain:
            self.last_result = result
        return result

    async def run(self) -> OwnerPolicyRepairCheckResult:
        if self._used:
            return self._result("attempt-already-consumed", retain=False)
        self._used = True  # Consume before any await, including failed preflight.
        if self._invalidated:
            return self._result("execution-decision-invalidated")
        try:
            current = prepare_owner_policy_repair_check(self._plan.to_dict()["candidate"])
            if current.payload_json != self._plan.payload_json:
                return self._result("stale-plan")
        except (ContractError, TypeError, AttributeError, UnicodeError, KeyError):
            return self._result("invalid-context")
        if self._decision is None:
            return self._result("execution-decision-pending")
        choice = self._decision.to_dict()
        if choice["choice"] != "approved":
            return self._result("execution-decision-" + choice["choice"])
        try:
            now = self._time()
        except ContractError:
            self._invalidated = True
            return self._result("invalid-decision-time")
        if not choice["created_at"] <= now < choice["expires_at"]:
            self._invalidated = True
            return self._result("expired-or-invalid-decision-time")
        if os.name != "posix" or getattr(sys, "frozen", False):
            return self._result("unsupported-platform")
        try:
            transport = await _run_worker(current.to_dict()["worker_input"])
        except asyncio.CancelledError as exc:
            transport = getattr(exc, "worker_transport", None)
            if not _transport_valid(transport):
                transport = _unknown_transport()
            self._result("cancelled", transport=transport)
            raise
        except Exception:
            return self._result("worker-process-error", transport=_unknown_transport())
        if not _transport_valid(transport):
            return self._result("invalid-worker-transport", transport=_unknown_transport())
        if _cleanup_status(transport) == "unconfirmed":
            return self._result("cleanup-unconfirmed", transport=transport)
        if transport.reason is not None:
            if not _diagnostics_match_reason(transport.reason, transport):
                return self._result("invalid-worker-transport", transport=_unknown_transport())
            return self._result(transport.reason, transport=transport)
        if (
            transport.launch_status != "started"
            or transport.child_cleanup_status != "confirmed"
            or transport.workspace_cleanup_status != "confirmed"
        ):
            return self._result("invalid-worker-transport", transport=transport)
        if transport.exit_code != 0:
            return self._result("worker-exit-error", transport=transport)
        try:
            observed = _validated_output(transport.output, current)
        except (ContractError, UnicodeError, ValueError, TypeError, RecursionError):
            return self._result("invalid-worker-output", transport=transport)
        expected = [case["expected"] == "allow" for case in current.to_dict()["bindings"]["cases"]]
        return self._result(
            "cases-match" if observed == expected else "case-mismatch",
            observed=observed,
            transport=transport,
        )


def validate_owner_policy_repair_check_result(raw: str) -> OwnerPolicyRepairCheckResult:
    """Revalidate current bindings and record consistency, never attest its origin."""
    data = _object(decode(raw), _RESULT_FIELDS)
    plan = validate_owner_policy_repair_check_plan(canonical(data["check_plan"]))
    reason = data["reason"]
    if type(reason) is not str or reason not in _REASONS:
        raise ContractError("Unexpected repair check result reason", code="validation-shape")
    rows = data["cases"]
    if type(rows) is not list or len(rows) != 8:
        raise ContractError("Invalid result cases", code="validation-shape")
    observations = []
    for row in rows:
        _object(row, {"case_id", "input_sha256", "expected", "observed", "result"})
        if row["observed"] is not None and type(row["observed"]) is not bool:
            raise ContractError("Invalid observation", code="validation-shape")
        observations.append(row["observed"])
    observed = observations if reason in {"cases-match", "case-mismatch"} else None
    transport = WorkerTransport(
        b"",
        data["exit_code"],
        None,
        data["child_cleanup_status"],
        data["workspace_cleanup_status"],
        data["launch_status"],
    )
    if not _transport_valid(transport):
        raise ContractError("Invalid result transport", code="validation-shape")
    if not _diagnostics_match_reason(reason, transport):
        raise ContractError("Result reason contradicts lifecycle", code="validation-shape")
    if observed is not None:
        if any(value is None for value in observed) or (
            transport.launch_status != "started"
            or transport.exit_code != 0
            or transport.child_cleanup_status != "confirmed"
            or transport.workspace_cleanup_status != "confirmed"
        ):
            raise ContractError("Incomplete successful observation", code="validation-shape")
        expected = [case["expected"] == "allow" for case in plan.to_dict()["bindings"]["cases"]]
        if (observed == expected) != (reason == "cases-match"):
            raise ContractError("Comparison reason mismatch", code="validation-identity")
    expected_data = _result_data(plan, reason, observed=observed, transport=transport)
    if canonical(data) != canonical(expected_data):
        raise ContractError("Repair result mismatch", code="validation-identity")
    return _snapshot(expected_data, OwnerPolicyRepairCheckResult)
