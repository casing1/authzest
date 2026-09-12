"""One live-session, explicitly approved change in a fresh owned-fixture copy only."""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    canonical,
)
from authzest.codex.proposals import (
    ValidatedProposal,
    proposal_preview,
    source_snapshots,
    validate_proposal,
)
from authzest.runner._fixture_workspace import CommittedWriteError, FixtureWorkspace, WorkspaceError
from authzest.runner.approval import ProposalDecision, assess_decision, record_decision


@dataclass(frozen=True)
class FixtureResult:
    status: str
    proposal_id: str
    workspace: str
    applied: bool = False
    restored: bool | None = False
    verification_status: str = "not-run"
    error: str | None = None
    verification_scope: str = "source-configuration"
    runtime_verification_status: str = "not-run"


class FixtureApplySession:
    """Caller-owned fixture data only; not authentication, restart recovery or an OS sandbox.

    The latest in-process decision is used once. No external receipt is accepted and no
    existing directory can be resumed. close() preserves all files for manual inspection.
    """

    def __init__(
        self,
        proposal: ValidatedProposal,
        request: CodexAnalysisRequest,
        review: ValidatedResponse,
        *,
        parent: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        runtime_check: bool = False,
    ):
        if type(runtime_check) is not bool:
            raise ContractError("Runtime check selection must be an explicit boolean")
        self._runtime_check = runtime_check
        self._proposal = validate_proposal(proposal.payload_json, request, review)
        sources = source_snapshots(request)
        changes = self._proposal.to_dict()["changes"]
        if (
            set(sources) != {"main.py"}
            or len(changes) != 1
            or changes[0]["path"] != "main.py"
            or request.to_dict()["source_revision"] is not None
        ):
            raise ContractError("Fixture application supports only main.py without a Git revision")
        self._request, self._review, self._clock = request, review, clock
        self._before = sources["main.py"].encode("utf-8")
        self._after = changes[0]["after_text"].encode("utf-8")
        self._decision: ProposalDecision | None = None
        self._consumed = False
        self._generation = 0
        self._phase = "prepared"
        self._applied = False
        self._restored: bool | None = False
        self._restore_used = False
        self._restore_choice: str | None = None
        self._events: list[dict] = []
        self._verification_decision: str | None = None
        self._verification_plan: dict | None = None
        self._verification_used = False
        self._verification_running = False
        self._verification_blocked = False
        self._verification: dict | None = None
        self._workspace = FixtureWorkspace(self._before, self._after, parent=parent)
        try:
            self._original = self._workspace.read_main()
            self._current = self._original
            self._record("prepared")
        except BaseException:
            self.close()
            raise

    @property
    def workspace(self) -> Path:
        return self._workspace.path

    def close(self) -> None:
        self._workspace.close()

    def preview(self) -> dict:
        return {
            **proposal_preview(self._proposal, self._request, self._review),
            "workspace": str(self.workspace),
            "scope": "fresh-owned-fixture-copy/main.py",
            "original_checkout_modified": False,
        }

    def _record(self, event: str) -> None:
        self._events.append({"event": event, "generation": self._generation})
        data = {
            "schema_version": "1.2" if self._runtime_check else "1.1",
            "proposal": self.preview(),
            "phase": self._phase,
            "decision": self._decision.to_dict() if self._decision else None,
            "decision_consumed": self._consumed,
            "restore_choice": self._restore_choice,
            "events": self._events,
            "before_sha256": sha256(self._before).hexdigest(),
            "after_sha256": sha256(self._after).hexdigest(),
            "applied": self._applied,
            "restored": self._restored,
            "verification_status": self._verification_status(),
            "verification_scope": self._verification_scope(),
            "runtime_verification_status": self._runtime_status(),
            "verification": self._verification,
            "verification_plan": self._verification_plan,
            "verification_decision": (
                json.loads(self._verification_decision) if self._verification_decision else None
            ),
            "verification_decision_consumed": self._verification_used,
            "restart_supported": False,
        }
        self._workspace.write_record(canonical(data).encode("utf-8"))

    def _result(self, status: str, error: str | None = None) -> FixtureResult:
        return FixtureResult(
            status,
            self._proposal.proposal_id,
            str(self.workspace),
            self._applied,
            self._restored,
            verification_status=self._verification_status(),
            error=error,
            verification_scope=self._verification_scope(),
            runtime_verification_status=self._runtime_status(),
        )

    def _verification_scope(self) -> str:
        return "owned-fixture-runtime" if self._runtime_check else "source-configuration"

    def _runtime_status(self) -> str:
        return self._verification_status() if self._runtime_check else "not-run"

    def _checker(self):
        if self._runtime_check:
            from authzest.runner import fixture_runtime

            return fixture_runtime
        from authzest.runner import fixture_check

        return fixture_check

    def _verification_status(self) -> str:
        return self._verification["status"] if self._verification else "not-run"

    def verification_preview(self) -> dict:
        """Describe the selected fixed check; selection is not permission to start a worker."""
        if (
            self._phase != "applied"
            or self._verification_running
            or self._verification_used
            or self._verification_blocked
        ):
            raise WorkspaceError("Verification requires an unused, applied fixture session")
        return self._verification_payload()

    def _verification_payload(self) -> dict:
        from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE

        fixture_check = self._checker()

        if self._phase != "applied":
            raise WorkspaceError("Verification requires the applied fixture")
        if sha256(fixture_check.WORKER_SOURCE.encode()).hexdigest() != fixture_check.WORKER_SHA256:
            raise WorkspaceError("Checker identity changed")
        current = self._workspace.read_main()
        if current != self._current:
            raise WorkspaceError("Applied fixture state changed")
        if self._before != FIXTURE_SOURCE.encode() or self._after != FIXTURE_AFTER.encode():
            raise WorkspaceError("Only the exact maintained configuration fixture is supported")
        data = {
            "kind": (
                "fixture-runtime-verification-plan"
                if self._runtime_check
                else "fixture-configuration-verification-plan"
            ),
            "schema_version": "1.0",
            "proposal_id": self._proposal.proposal_id,
            "workspace": str(self.workspace),
            "path": "main.py",
            "source_text": current.data.decode("utf-8"),
            "source_sha256": sha256(current.data).hexdigest(),
            "file_identity": list(current.identity),
            "check_id": fixture_check.CHECK_ID,
            "worker_source": fixture_check.WORKER_SOURCE,
            "worker_sha256": fixture_check.WORKER_SHA256,
            "timeout_seconds": fixture_check.TIMEOUT_SECONDS,
            "max_cleanup_seconds": fixture_check.MAX_CLEANUP_SECONDS,
            "max_input_bytes": fixture_check.MAX_INPUT_BYTES,
            "max_output_bytes": fixture_check.MAX_OUTPUT_BYTES,
            "max_worker_attempts": 1,
            "verification_scope": self._verification_scope(),
            "runtime_verification_status": "not-run",
            "limitations": (
                "Fixed source configuration check only; no source import/execution, "
                "regression-test execution or security-fix verification. A separate process, "
                "not an OS/network sandbox. No model-proposed command is executed. "
                "Caller-entered decisions are not authenticated human approval."
            ),
        }
        if self._runtime_check:
            data["expected_checks"] = {
                "debug": False,
                "method": "GET",
                "path": "/health",
                "health_status": 200,
                "health_body": {"status": "ok"},
            }
            data["limitations"] = (
                "Runs only the byte-identical bundled owned fixture constant, never arbitrary "
                "input code or a source path. Observes app.debug and one in-process ASGI "
                "health response; no TCP/UDP listener or HTTP client, no exploit reproduction. "
                "Internal event-loop IPC and framework threads may be used. Trusted installed "
                "Python/FastAPI dependencies and site startup hooks are not sandboxed. "
                "A separate process is not OS/network confinement or executable attestation. "
                "No generated commands/tests, installs or model calls. Does not establish "
                "authorization correctness, general application compatibility or a verified "
                "security fix. Caller-entered decisions are not authenticated human approval."
            )
        return {**data, "plan_id": "verification-" + sha256(canonical(data).encode()).hexdigest()}

    def decide_verification(
        self, choice: str, plan_id: str, *, valid_for_seconds: float = 300
    ) -> dict:
        """Latest in-memory decision, bound to the displayed plan, consumed at most once."""
        if choice not in ("approve", "decline", "cancel"):
            raise ContractError("Explicit verification choice required")
        now = self._clock()
        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
            or not 0 <= now <= 1e12
            or type(valid_for_seconds) not in (int, float)
            or not math.isfinite(valid_for_seconds)
            or not 0 < valid_for_seconds <= 300
        ):
            raise ContractError(
                "Verification decision requires a finite lifetime up to 300 seconds"
            )
        preview = self.verification_preview()
        if type(plan_id) is not str or plan_id != preview["plan_id"]:
            raise ContractError("Verification plan changed; review a fresh preview")
        decision = {
            "purpose": self._verification_scope() + "-verification",
            "plan_id": plan_id,
            "choice": choice,
            "created_at": now,
            "expires_at": now + valid_for_seconds,
        }
        self._verification_decision = canonical(decision)
        self._verification_plan = preview
        try:
            self._record("verification-decision-recorded")
        except (OSError, WorkspaceError):
            self._verification_blocked = True
            raise
        return decision

    def _save_verification(self, result: dict) -> dict:
        result = {
            **result,
            "runtime_verification_status": result["status"] if self._runtime_check else "not-run",
        }
        self._verification = {**result, "journal_status": "recorded"}
        try:
            self._record("verification-" + result["reason"])
        except (OSError, WorkspaceError):
            self._verification_blocked = True
            self._verification = {
                **result,
                "status": "failed" if result["execution_attempted"] else "not-run",
                "reason": "journal-unavailable",
                "journal_status": "unconfirmed",
            }
            self._verification["runtime_verification_status"] = self._runtime_status()
            # Replacement may have committed before fsync failed. Best-effort correction
            # prevents a stale passed record when writes recover; no durability claim is
            # made if this second write also fails. Retained files are not a restart receipt.
            with suppress(OSError, WorkspaceError):
                self._record("verification-journal-unavailable")
        return dict(self._verification)

    async def verify(self) -> dict:
        """Run the approved fixed check once, retaining its historical checked-content result."""
        fixture_check = self._checker()

        result = {
            "status": "not-run",
            "reason": "pending",
            "plan_id": None,
            "proposal_id": self._proposal.proposal_id,
            "check_id": fixture_check.CHECK_ID,
            "source_sha256": sha256(self._after).hexdigest(),
            "worker_sha256": fixture_check.WORKER_SHA256,
            "elapsed_ms": None,
            "exit_code": None,
            "execution_attempted": False,
            "verification_scope": self._verification_scope(),
            "runtime_verification_status": "not-run",
        }
        if self._runtime_check:
            result["runtime_evidence"] = None
        if self._verification_used:
            return {**result, "reason": "decision-consumed"}
        if self._verification_blocked or self._phase != "applied":
            return {**result, "reason": "verification-unavailable"}
        if self._verification_decision is None:
            return result
        decision = json.loads(self._verification_decision)
        result["plan_id"] = decision["plan_id"]
        if decision["choice"] != "approve":
            self._verification_used = True
            reason = "declined" if decision["choice"] == "decline" else "cancelled"
            return self._save_verification({**result, "reason": reason})
        try:
            preview = self.verification_preview()
            if preview["plan_id"] != decision["plan_id"]:
                raise WorkspaceError("Verification plan changed")
            self._verification_used = True
            self._record("verification-intent")
            # Recheck after the journal write, immediately before handing immutable bytes off.
            if self._verification_payload()["plan_id"] != preview["plan_id"]:
                raise WorkspaceError("Verification plan changed before execution")
            current = self._workspace.read_main()
            if current != self._current:
                raise WorkspaceError("Applied fixture changed before verification")
            now = self._clock()
            if type(now) not in (int, float) or not math.isfinite(now):
                raise WorkspaceError("Verification clock unavailable")
            if now < decision["created_at"] or now >= decision["expires_at"]:
                return self._save_verification({**result, "reason": "expired"})
        except (OSError, WorkspaceError, ContractError):
            self._verification_used = True
            return self._save_verification({**result, "reason": "precondition-failed"})
        self._verification_running = True
        try:
            result["execution_attempted"] = True
            check = (
                fixture_check.run_runtime_check
                if self._runtime_check
                else fixture_check.run_configuration_check
            )
            outcome = asdict(await check(current.data))
            expected_fields = {
                "status",
                "reason",
                "check_id",
                "source_sha256",
                "worker_sha256",
                "elapsed_ms",
                "exit_code",
            }
            if self._runtime_check:
                expected_fields.add("runtime_evidence")
            if (
                set(outcome) != expected_fields
                or outcome["status"] not in ("passed", "failed", "not-run")
                or outcome["source_sha256"] != preview["source_sha256"]
                or outcome["worker_sha256"] != preview["worker_sha256"]
                or outcome["check_id"] != preview["check_id"]
                or type(outcome["elapsed_ms"]) not in (int, float)
                or not math.isfinite(outcome["elapsed_ms"])
                or outcome["elapsed_ms"] < 0
                or (outcome["exit_code"] is not None and type(outcome["exit_code"]) is not int)
                or (
                    outcome["status"] == "passed"
                    and (
                        outcome["reason"]
                        != ("runtime-check-passed" if self._runtime_check else "debug-disabled")
                        or type(outcome["exit_code"]) is not int
                        or outcome["exit_code"] != 0
                    )
                )
                or (
                    self._runtime_check
                    and (
                        outcome["status"] == "passed" or outcome.get("runtime_evidence") is not None
                    )
                    and not fixture_check.validate_runtime_evidence(
                        outcome.get("runtime_evidence"), current.data
                    )
                )
            ):
                result.update(status="failed", reason="invalid-check-result")
            else:
                result.update(outcome)
            if self._workspace.read_main() != current:
                result.update(status="failed", reason="source-changed-during-check")
            return self._save_verification(result)
        except asyncio.CancelledError:
            self._save_verification({**result, "status": "failed", "reason": "cancelled"})
            raise
        except Exception:
            return self._save_verification({**result, "status": "failed", "reason": "check-failed"})
        finally:
            self._verification_running = False

    def decide(self, choice: str, *, valid_for_seconds: float = 300) -> ProposalDecision:
        if self._phase != "prepared":
            raise WorkspaceError("This session no longer accepts application decisions")
        decision = record_decision(
            self._proposal,
            self._request,
            self._review,
            choice,
            now=self._clock(),
            valid_for_seconds=valid_for_seconds,
        )
        self._decision, self._consumed = decision, False
        self._generation += 1
        try:
            self._record("decision-recorded")
        except (OSError, WorkspaceError):
            self._phase = "failed"
            self._consumed = True
            raise
        return decision

    def _eligibility(self) -> str:
        current = self._workspace.read_main()
        if current != self._original:
            return "stale-source"
        return assess_decision(
            self._proposal,
            self._request,
            self._review,
            self._decision,
            current_sources={"main.py": current.data.decode("utf-8")},
            now=self._clock(),
        ).reason

    def _apply_guard(self) -> None:
        reason = self._eligibility()
        if reason != "approved":
            raise WorkspaceError("Application precondition: " + reason)

    def _failure(self, status: str, exc: Exception) -> FixtureResult:
        self._phase = "failed"
        try:
            self._record(status)
        except (OSError, WorkspaceError):
            status += "-journal-unavailable"
        # Exception messages and paths are not treated as authoritative verification evidence.
        return self._result(status, type(exc).__name__)

    def apply(self) -> FixtureResult:
        if self._phase != "prepared":
            return self._result("session-finished")
        if self._consumed:
            return self._result("decision-consumed")
        if self._decision is None:
            return self._result("pending")
        self._consumed = True
        try:
            self._record("application-attempt")
            reason = self._eligibility()
            if reason != "approved":
                self._record(reason)
                return self._result(reason)
            self._phase = "applying"
            self._record("application-intent")
            self._current = self._workspace.replace_main(
                self._original, self._after, guard=self._apply_guard
            )
            self._applied, self._phase = True, "applied"
            self._record("applied")
            return self._result("applied")
        except CommittedWriteError as exc:
            self._applied = True
            return self._failure("applied-state-unconfirmed", exc)
        except (OSError, WorkspaceError, ContractError) as exc:
            return self._failure("applied-audit-failed" if self._applied else "not-applied", exc)

    def restoration_preview(self) -> dict:
        return {
            "proposal_id": self._proposal.proposal_id,
            "workspace": str(self.workspace),
            "path": "main.py",
            "from_text": self._after.decode("utf-8"),
            "to_text": self._before.decode("utf-8"),
            "from_sha256": sha256(self._after).hexdigest(),
            "to_sha256": sha256(self._before).hexdigest(),
            "verification_status": self._verification_status(),
            "verification_scope": self._verification_scope(),
            "runtime_verification_status": self._runtime_status(),
        }

    def restore(self, choice: str) -> FixtureResult:
        if choice not in ("approve", "decline", "cancel"):
            raise ContractError("Explicit restoration choice required")
        if self._phase != "applied" or self._restore_used or self._verification_running:
            return self._result("restoration-unavailable")
        self._restore_choice = choice
        try:
            if choice != "approve":
                self._record("restoration-" + choice)
                return self._result("restoration-" + choice)
            self._restore_used = True
            self._record("restoration-intent")
            self._workspace.replace_main(self._current, self._before, guard=lambda: None)
            self._restored, self._phase = True, "restored"
            self._record("restored")
            return self._result("restored")
        except CommittedWriteError as exc:
            self._restored = None
            return self._failure("restoration-state-unconfirmed", exc)
        except (OSError, WorkspaceError) as exc:
            return self._failure("restored-audit-failed" if self._restored else "not-restored", exc)
