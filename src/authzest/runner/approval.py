"""Pure in-memory decision checks. No file writes, process execution or permission UI."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    _object,
    canonical,
    decode,
)
from authzest.codex.proposals import ValidatedProposal, source_snapshots, validate_proposal

DecisionChoice = Literal["approve", "decline", "cancel"]


def _time(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1e12:
        raise ContractError("Expected finite nonnegative decision time")
    return value


@dataclass(frozen=True, slots=True)
class ProposalDecision:
    """Caller-authored decision, NOT a signed identity or one-use execution token."""

    payload_json: str

    def __post_init__(self) -> None:
        data = _object(
            decode(self.payload_json),
            {"schema_version", "proposal_id", "choice", "purpose", "created_at", "expires_at"},
        )
        if (
            data["schema_version"] != "1.0"
            or data["purpose"] != "patch-application"
            or data["choice"] not in ("approve", "decline", "cancel")
        ):
            raise ContractError("Invalid decision schema, purpose or choice")
        if type(data["proposal_id"]) is not str or not re.fullmatch(
            r"proposal-[a-f0-9]{64}", data["proposal_id"]
        ):
            raise ContractError("Invalid proposal identity")
        duration = _time(data["expires_at"]) - _time(data["created_at"])
        if not 0 < duration <= 3600:
            raise ContractError("Decision must expire within one hour")

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class ApprovalAssessment:
    eligible: bool
    reason: str
    proposal_id: str
    applied: bool = False
    verification_status: str = "not-run"


def record_decision(
    proposal: ValidatedProposal,
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    choice: DecisionChoice,
    *,
    now: float,
    valid_for_seconds: float = 300,
) -> ProposalDecision:
    """Record an explicit caller choice, never infer consent from provider output."""
    proposal = validate_proposal(proposal.payload_json, request, review)
    _time(now)
    _time(valid_for_seconds)
    return ProposalDecision(
        canonical(
            {
                "schema_version": "1.0",
                "proposal_id": proposal.proposal_id,
                "choice": choice,
                "purpose": "patch-application",
                "created_at": now,
                "expires_at": now + valid_for_seconds,
            }
        )
    )


def assess_decision(
    proposal: ValidatedProposal,
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    decision: ProposalDecision | None,
    *,
    current_sources: dict[str, str],
    now: float,
    current_revision: str | None = None,
) -> ApprovalAssessment:
    """Check the supplied current state, not disk state or TOCTOU atomicity.

    The future application service must use the latest decision, re-read selected regular
    files without following links, invalidate consumed/revoked approvals, and apply atomically.
    Eligibility here grants neither source sharing nor verification execution.
    """
    proposal = validate_proposal(proposal.payload_json, request, review)
    _time(now)

    def result(reason: str) -> ApprovalAssessment:
        return ApprovalAssessment(reason == "approved", reason, proposal.proposal_id)

    if decision is None:
        return result("pending")
    decision = ProposalDecision(decision.payload_json)
    data = decision.to_dict()
    if data["proposal_id"] != proposal.proposal_id:
        return result("stale-proposal")
    if data["choice"] != "approve":
        return result("declined" if data["choice"] == "decline" else "cancelled")
    if now < data["created_at"]:
        return result("clock-before-decision")
    if now >= data["expires_at"]:
        return result("expired")
    selected = source_snapshots(request)
    if any(
        type(current_sources.get(path)) is not str or current_sources[path] != text
        for path, text in selected.items()
    ):
        return result("stale-source")
    revision = request.to_dict()["source_revision"]
    if revision is not None and current_revision != revision:
        return result("stale-source")
    return result("approved")
