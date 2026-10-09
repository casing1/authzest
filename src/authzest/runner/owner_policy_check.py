"""Separately approved, one-attempt check of one registered owned pure policy.

Preparation is offline. The live coordinator—not a serialized receipt—records a
fresh caller choice for the exact plan. It is not an authenticated approval service.
Only the maintained embedded policy can run, with synthetic data, in a bounded
stdlib child. These controls are not an OS/network sandbox or HTTP/auth assurance.
"""

from __future__ import annotations

import asyncio
import math
import os
import signal
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from authzest.codex.contracts import ContractError, _object, canonical, decode, identity
from authzest.codex.owner_case_plan import (
    OwnerCaseLabelReview,
    OwnerCaseSet,
    OwnerPolicyPlan,
    validate_owner_policy_plan,
)
from authzest.codex.owner_policy_review import OWNER_POLICY_SOURCE
from authzest.runner._owner_policy_worker import (
    CHECK_ID,
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    WORKER_SHA256,
    WORKER_SOURCE,
)

POLICY_SHA256 = "faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04"
TIMEOUT_SECONDS = 5.0
MAX_CLEANUP_SECONDS = 1.0
MAX_DECISION_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class _Snapshot:
    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class OwnerPolicyCheckPlan(_Snapshot):
    @property
    def check_plan_id(self) -> str:
        return self.to_dict()["check_plan_id"]


@dataclass(frozen=True, slots=True)
class OwnerPolicyCheckResult(_Snapshot):
    pass


@dataclass(frozen=True, slots=True)
class WorkerTransport:
    output: bytes
    exit_code: int | None
    reason: str | None
    cleanup_status: str


def _snapshot(data: dict, kind):
    raw = canonical(data)
    decode(raw)
    return kind(raw)


def _recipe() -> dict:
    return {
        "id": CHECK_ID,
        "version": "1.1",
        "target": "registered embedded policy.py only",
        "mapping_version": "nullable-fixed-dataclasses-exact-v1",
        "comparison_version": "observed-bool-to-reviewed-bool-v1",
        "worker_sha256": WORKER_SHA256,
        "policy_source_sha256": POLICY_SHA256,
        "platform": "POSIX non-frozen Python source only",
        "attempt_limit": 1,
        "max_decision_seconds": MAX_DECISION_SECONDS,
        "max_cases": 16,
        "max_scopes": 16,
        "max_identifier_characters": 128,
        "max_input_bytes": MAX_INPUT_BYTES,
        "max_output_bytes": MAX_OUTPUT_BYTES,
        "timeout_seconds": TIMEOUT_SECONDS,
        "cleanup_timeout_seconds": MAX_CLEANUP_SECONDS,
        "environment": "fixed minimal environment and fresh private temporary cwd",
        "confinement": "bounded trusted child, not an OS/network sandbox",
        "exclusions": [
            "caller paths/source/code",
            "main.py/FastAPI/HTTP/auth/database",
            "model/reviewer text in worker input",
            "install hooks",
            "network/provider",
            "patch application",
            "automatic retries",
        ],
    }


def prepare_owner_policy_check(offline_plan, labels, case_set, draft, request):
    """Revalidate the complete exact context; prepare data, never an execution token.

    The ID hashes bindings only; the wire plan_id is derived from that ID, avoiding a
    self-referential digest. Complete artifacts, original model labels/reasons, reviewed
    labels and recipe remain bound even though only input data goes to the child.
    """
    if (
        type(offline_plan) is not OwnerPolicyPlan
        or type(labels) is not OwnerCaseLabelReview
        or type(case_set) is not OwnerCaseSet
    ):
        raise ContractError("Unexpected owner-policy check context", code="validation-shape")
    checked = validate_owner_policy_plan(
        offline_plan.payload_json, labels, case_set, draft, request
    ).to_dict()
    if (
        checked["policy_source"] != OWNER_POLICY_SOURCE
        or sha256(OWNER_POLICY_SOURCE.encode()).hexdigest() != POLICY_SHA256
        or checked["source_sha256"]["policy.py"] != POLICY_SHA256
        or sha256(WORKER_SOURCE.encode()).hexdigest() != WORKER_SHA256
    ):
        raise ContractError("Unregistered policy or worker", code="validation-identity")
    cases = [
        {
            "id": case["id"],
            "case_sha256": identity(case),
            "principal": case["principal"],
            "report": case["report"],
        }
        for case in checked["cases"]
    ]
    recipe = _recipe()
    bindings = {
        "offline_plan_id": offline_plan.plan_id,
        "offline_plan": checked,
        "case_set_id": case_set.case_set_id,
        "label_review_id": labels.label_review_id,
        "request_id": request.request_id,
        "request_sha256": identity(request.to_dict()),
        "draft_sha256": identity(draft.to_dict()),
        "source_identity": checked["source_identity"],
        "source_sha256": checked["source_sha256"],
        "recipe": recipe,
        "recipe_sha256": identity(recipe),
        "input_cases": cases,
        "input_sha256": identity(cases),
    }
    plan_id = "owner-policy-check-" + identity(bindings)
    wire = {
        "schema_version": "1.0",
        "check_id": CHECK_ID,
        "plan_id": plan_id,
        "policy_source_sha256": POLICY_SHA256,
        "worker_sha256": WORKER_SHA256,
        "input_sha256": bindings["input_sha256"],
        "cases": cases,
    }
    if len(canonical(wire).encode()) > MAX_INPUT_BYTES:
        raise ContractError("Worker input exceeds budget", code="validation-budget")
    return _snapshot(
        {
            "schema_version": "1.0",
            "kind": "owner-policy-check-plan",
            "check_plan_id": plan_id,
            "bindings": bindings,
            "worker_input": wire,
            "planning_status": "requires-fresh-execution-decision"
            if checked["label_review"]["all_labels_reviewed"]
            else "blocked-label-review",
            "requires_separate_execution_approval": True,
            "execution_status": "not-run",
            "authorization_status": "unknown",
            "provider_calls": 0,
            "patch_application": "not-run",
        },
        OwnerPolicyCheckPlan,
    )


def _finite(value) -> float:
    try:
        valid = type(value) in {int, float} and math.isfinite(value) and 0 <= value <= 1e12
    except OverflowError:
        valid = False
    if not valid:
        raise ContractError("Invalid decision clock or lifetime", code="validation-shape")
    return float(value)


class OwnerPolicyCheckSession:
    """Trusted live workflow; imported JSON/direct helper calls cannot grant consent.

    One run consumes this session even on a declined/expired/stale/failed attempt.
    New valid choices may replace a pending choice only before that consumption.
    """

    def __init__(self, offline_plan, labels, case_set, draft, request, *, clock=monotonic):
        if not callable(clock):
            raise ContractError("Invalid decision clock", code="validation-shape")
        self._clock: Callable[[], float] = clock
        self._created = _finite(clock())
        self._plan = prepare_owner_policy_check(offline_plan, labels, case_set, draft, request)
        self._decision: _Snapshot | None = None
        self._used = False
        self._invalidated = False
        self.last_result: OwnerPolicyCheckResult | None = None

    @property
    def plan(self) -> OwnerPolicyCheckPlan:
        return self._plan

    def decide(self, choice, *, plan_id, lifetime_seconds=MAX_DECISION_SECONDS) -> _Snapshot:
        if self._used:
            raise ContractError("Owner-policy check attempt already consumed")
        if self._invalidated:
            raise ContractError("Owner-policy check session invalidated; prepare a fresh session")
        previous = self._decision.to_dict() if self._decision else None
        # Fail closed on every unsuccessful choice, including invalid replacements.
        # Clearing a choice must not allow the same session to acquire a new approval.
        self._invalidated = True
        self._decision = None
        now = _finite(self._clock())
        if previous is not None and (
            previous["choice"] != "pending"
            or not previous["created_at"] <= now < previous["expires_at"]
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
            raise ContractError("Execution choice is for another plan", code="validation-identity")
        duration = _finite(lifetime_seconds)
        if (
            not 0 < duration <= MAX_DECISION_SECONDS
            or now < self._created
            or not now < now + duration <= 1e12
        ):
            raise ContractError("Invalid execution decision time", code="validation-shape")
        self._decision = _snapshot(
            {
                "kind": "live-owner-policy-execution-choice",
                "plan_id": plan_id,
                "choice": choice,
                "created_at": now,
                "expires_at": now + duration,
                "reviewer_authenticated": False,
                "purpose": "one-fixed-policy-check",
            },
            _Snapshot,
        )
        self._invalidated = False
        return self._decision

    def _result(self, reason, *, observed=None, transport=None, attempted=False, retain=True):
        data = self._plan.to_dict()
        labels = data["bindings"]["offline_plan"]["label_review"]["decisions"]
        cases = [
            {
                "id": choice["case_id"],
                "case_sha256": choice["case_sha256"],
                "expected": choice["expected"],
                "observed": observed[index] if observed is not None else None,
                "result": ("passed" if observed[index] is choice["expected"] else "failed")
                if observed is not None
                else "unknown",
            }
            for index, choice in enumerate(labels)
        ]
        status = (
            "not-run"
            if observed is None
            else ("passed" if all(row["result"] == "passed" for row in cases) else "failed")
        )
        result = _snapshot(
            {
                "schema_version": "1.0",
                "kind": "owner-policy-check-result",
                "check_plan_id": data["check_plan_id"],
                "status": status,
                "reason": reason,
                "cases": cases,
                "source_identity": data["bindings"]["source_identity"],
                "source_sha256": data["bindings"]["source_sha256"],
                "worker_sha256": data["worker_input"]["worker_sha256"],
                "input_sha256": data["worker_input"]["input_sha256"],
                "execution_status": "completed"
                if observed is not None
                else ("attempted" if attempted else "not-run"),
                "cleanup_status": transport.cleanup_status
                if transport
                else ("unconfirmed" if attempted else "not-needed"),
                "exit_code": transport.exit_code if transport else None,
                "authorization_status": "unknown",
                "provider_calls": 0,
                "patch_application": "not-run",
            },
            OwnerPolicyCheckResult,
        )
        if retain:
            self.last_result = result
        return result

    async def run(self, offline_plan, labels, case_set, draft, request):
        # Synchronous before any await: concurrent calls cannot share an attempt.
        if self._used:
            return self._result("attempt-already-consumed", retain=False)
        self._used = True
        if self._invalidated:
            return self._result("execution-decision-invalidated")
        try:
            current = prepare_owner_policy_check(offline_plan, labels, case_set, draft, request)
            if current.payload_json != self._plan.payload_json:
                return self._result("stale-plan")
        except (ContractError, TypeError, AttributeError, UnicodeError):
            return self._result("invalid-context")
        if not current.to_dict()["bindings"]["offline_plan"]["label_review"]["all_labels_reviewed"]:
            return self._result("labels-not-reviewed")
        if self._decision is None:
            return self._result("execution-decision-pending")
        decision = self._decision.to_dict()
        if decision["choice"] != "approved":
            return self._result("execution-decision-" + decision["choice"])
        try:
            now = _finite(self._clock())
        except ContractError:
            return self._result("invalid-decision-time")
        if not decision["created_at"] <= now < decision["expires_at"]:
            return self._result("expired-or-invalid-decision-time")
        if os.name != "posix" or getattr(sys, "frozen", False):
            return self._result("unsupported-platform")
        try:
            transport = await _run_worker(current)
        except asyncio.CancelledError:
            self._result("cancelled", attempted=True)
            raise
        except (OSError, ValueError, TypeError):
            return self._result("worker-process-error", attempted=True)
        if (
            type(transport) is not WorkerTransport
            or type(transport.output) is not bytes
            or (transport.exit_code is not None and type(transport.exit_code) is not int)
            or type(transport.cleanup_status) is not str
            or transport.cleanup_status not in {"confirmed", "unconfirmed", "not-needed"}
            or (transport.reason is not None and type(transport.reason) is not str)
        ):
            return self._result("invalid-worker-transport", attempted=True)
        if transport.cleanup_status == "not-needed":
            if (
                transport.reason == "worker-process-error"
                and transport.exit_code is None
                and not transport.output
            ):
                # No child exists: preserve startup failure, not a cleanup failure.
                return self._result("worker-process-error", transport=transport)
            return self._result("invalid-worker-transport", transport=transport, attempted=True)
        if transport.cleanup_status != "confirmed":
            return self._result("cleanup-unconfirmed", transport=transport, attempted=True)
        if transport.reason is not None:
            # A closed host transport vocabulary, never child text or exception output.
            reason = (
                transport.reason
                if transport.reason
                in {"timeout", "output-limit", "worker-process-error", "cleanup-unconfirmed"}
                else "worker-process-error"
            )
            return self._result(reason, transport=transport, attempted=True)
        if transport.exit_code != 0:
            return self._result("worker-exit-error", transport=transport, attempted=True)
        try:
            observed = _validated_output(transport.output, current)
        except (ContractError, UnicodeError, ValueError, TypeError, RecursionError):
            return self._result("invalid-worker-output", transport=transport, attempted=True)
        mismatch = any(
            value is not choice["expected"]
            for value, choice in zip(
                observed,
                current.to_dict()["bindings"]["offline_plan"]["label_review"]["decisions"],
                strict=True,
            )
        )
        return self._result(
            "case-mismatch" if mismatch else "cases-match",
            observed=observed,
            transport=transport,
            attempted=True,
        )


def _validated_output(raw: bytes, plan: OwnerPolicyCheckPlan) -> list[bool]:
    if not raw or len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("Invalid output size")
    data = decode(raw.decode("utf-8"))
    expected = plan.to_dict()["worker_input"]
    _object(data, set(expected))
    if any(data[key] != expected[key] for key in expected if key != "cases"):
        raise ValueError("Worker identity mismatch")
    rows = data["cases"]
    if type(rows) is not list or len(rows) != len(expected["cases"]):
        raise ValueError("Worker case count mismatch")
    observed = []
    for original, row in zip(expected["cases"], rows, strict=True):
        _object(row, {"id", "case_sha256", "observed"})
        if (
            row["id"] != original["id"]
            or row["case_sha256"] != original["case_sha256"]
            or type(row["observed"]) is not bool
        ):
            raise ValueError("Worker observation mismatch")
        observed.append(row["observed"])
    return observed


class _OutputLimitError(ValueError):
    pass


async def _exchange(process, source: bytes) -> bytes:
    if type(source) is not bytes or len(source) > MAX_INPUT_BYTES:
        raise ValueError("Invalid input size")
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


async def _stop(process) -> None:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await asyncio.wait_for(process.wait(), timeout=MAX_CLEANUP_SECONDS)


async def _cleanup(process) -> str:
    # Repeated cancellation cannot abandon the bounded reaper or replace the
    # original cancellation with a cleanup error. The reaper owns its 1s deadline.
    task = asyncio.create_task(_stop(process))
    cancelled = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            cancelled = exc
        except (OSError, TimeoutError):
            break
    status = "confirmed"
    try:
        task.result()
    except (OSError, TimeoutError, asyncio.CancelledError):
        status = "unconfirmed"
    if cancelled is not None:
        raise cancelled
    return status


def _environment(directory: Path) -> dict[str, str]:
    # Trusted stdlib subprocess. No account/HOME/provider/proxy/Python injection.
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


async def _run_worker(plan: OwnerPolicyCheckPlan) -> WorkerTransport:
    """One fixed child with an embedded maintained policy copy; no caller source file.

    The fresh temp workspace is never a copy/import of a caller repository. In-flight
    launch/cancellation or unsuccessful cleanup cannot attest that no descendant remains.
    """
    raw = b""
    reason = None
    exit_code = None
    cleanup_status = "not-needed"
    process = None
    try:
        with TemporaryDirectory(prefix="authzest-owner-policy-check-") as temporary:
            directory = Path(temporary).resolve()
            try:
                async with asyncio.timeout(TIMEOUT_SECONDS):
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-I",
                        "-S",
                        "-c",
                        WORKER_SOURCE,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        cwd=directory,
                        env=_environment(directory),
                        start_new_session=True,
                        limit=MAX_OUTPUT_BYTES + 1,
                    )
                    cleanup_status = "unconfirmed"
                    raw = await _exchange(
                        process, canonical(plan.to_dict()["worker_input"]).encode()
                    )
                    exit_code = await process.wait()
            finally:
                if process is not None:
                    cleanup_status = await _cleanup(process)
                    exit_code = process.returncode
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        reason = "timeout"
    except _OutputLimitError:
        reason = "output-limit"
    except (OSError, ValueError, TypeError):
        reason = "worker-process-error"
    return WorkerTransport(raw, exit_code, reason, cleanup_status)
