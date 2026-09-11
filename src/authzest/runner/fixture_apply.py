"""One live-session, explicitly approved change in a fresh owned-fixture copy only."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
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
    ):
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
            "schema_version": "1.0",
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
            "verification_status": "not-run",
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
            error=error,
        )

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
            "verification_status": "not-run",
        }

    def restore(self, choice: str) -> FixtureResult:
        if choice not in ("approve", "decline", "cancel"):
            raise ContractError("Explicit restoration choice required")
        if self._phase != "applied" or self._restore_used:
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
