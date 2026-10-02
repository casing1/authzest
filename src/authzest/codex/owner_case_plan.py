"""Offline case-label review and fixed-plan data, never an execution capability.

Only the packaged owner-policy request is supported. Model text stays data; no
filesystem, account, provider, process, policy import or case evaluation occurs.
Caller-recorded review is not authenticated maintainer approval. #80 must design
an executor and a separate exact-plan execution decision before anything runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Any

from .contracts import (
    MAX_JSON_BYTES,
    CodexAnalysisRequest,
    ContractError,
    _object,
    _text,
    canonical,
    decode,
    identity,
)
from .owner_policy_review import (
    OwnerPolicyReview,
    owner_policy_output_schema,
    owner_policy_prompt,
    validate_owner_policy_result,
)

OWNER_CASE_PLAN_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """Immutable JSON; direct construction is not validation or authority."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class OwnerCaseSet(_Snapshot):
    @property
    def case_set_id(self) -> str:
        return "owner-cases-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class OwnerCaseLabelReview(_Snapshot):
    @property
    def label_review_id(self) -> str:
        return "owner-label-review-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class OwnerPolicyPlan(_Snapshot):
    @property
    def plan_id(self) -> str:
        return "owner-policy-plan-" + identity(self.to_dict())


def _snapshot(data: dict, kind: type[_Snapshot]):
    raw = canonical(data)
    decode(raw)  # Apply the shared UTF-8 byte/depth/node budget to host metadata too.
    return kind(raw)


def _read(value: _Snapshot, kind: type[_Snapshot]) -> dict:
    if type(value) is not kind:
        raise ContractError("Unexpected owner-case artifact type", code="validation-shape")
    return decode(getattr(value, "payload_json", None))


def _match(raw: str, expected: _Snapshot):
    if canonical(decode(raw)) != expected.payload_json:
        raise ContractError("Owner-case artifact binding mismatch", code="validation-identity")
    return expected


def _origin(value: dict | None) -> dict:
    value = {"code_head": None, "date": None} if value is None else value
    _object(value, {"code_head", "date"})
    if value["code_head"] is not None and (
        type(value["code_head"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", value["code_head"])
    ):
        raise ContractError("Invalid declared origin commit", code="validation-shape")
    if value["date"] is not None:
        if type(value["date"]) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["date"]):
            raise ContractError("Invalid declared origin date", code="validation-shape")
        try:
            date.fromisoformat(value["date"])
        except ValueError as exc:
            raise ContractError("Invalid declared origin date", code="validation-shape") from exc
    return {**value, "authenticated": False}


def prepare_owner_case_set(
    draft: OwnerPolicyReview,
    request: CodexAnalysisRequest,
    *,
    origin: dict | None = None,
) -> OwnerCaseSet:
    """Bind exact model suggestions/evidence/source; do not approve or run them."""
    checked = validate_owner_policy_result(draft, request)
    payload = request.to_dict()
    data = checked.to_dict()
    evidence = payload["evidence"]
    sources = {
        item["data"]["path"]: item["data"]["text"] for item in evidence if item["kind"] == "source"
    }
    return _snapshot(
        {
            "schema_version": OWNER_CASE_PLAN_SCHEMA_VERSION,
            "kind": "owner-case-set",
            "request_id": request.request_id,
            "request_sha256": identity(payload),
            "draft_sha256": identity(data),
            "source_identity": data["source_identity"],
            "source_sha256": {
                path: sha256(text.encode()).hexdigest() for path, text in sources.items()
            },
            "model_identity": data["review"]["identity"],
            "prompt_sha256": sha256(owner_policy_prompt(request).encode()).hexdigest(),
            "output_schema_sha256": identity(owner_policy_output_schema(request)),
            "origin": _origin(origin),
            "evidence": evidence,
            "cases": data["cases"],
            "case_authorship": "model-authored",
            "label_review_status": "pending",
            "execution_status": "not-run",
            "authorization_status": "unknown",
        },
        OwnerCaseSet,
    )


def validate_owner_case_set(
    raw: str, draft: OwnerPolicyReview, request: CodexAnalysisRequest
) -> OwnerCaseSet:
    data = decode(raw)
    origin = _object(data.get("origin"), {"code_head", "date", "authenticated"})
    expected = prepare_owner_case_set(
        draft, request, origin={key: origin[key] for key in ("code_head", "date")}
    )
    return _match(raw, expected)


def _case_context(case_set, draft, request) -> OwnerCaseSet:
    _read(case_set, OwnerCaseSet)
    return validate_owner_case_set(case_set.payload_json, draft, request)


def review_owner_cases(
    case_set: OwnerCaseSet,
    draft: OwnerPolicyReview,
    request: CodexAnalysisRequest,
    *,
    decisions: dict,
    reviewer: str | None = None,
) -> OwnerCaseLabelReview:
    """Record caller choices against exact data, not authentic human/execution consent.

    Omitted cases remain pending. Each supplied decision has exactly decision,
    expected and reason. Approved labels must match; changed labels must differ.
    Declined/pending decisions carry no selected label. Original inputs/labels and
    model authorship are never overwritten by a caller's reviewed expectation.
    """
    checked = _case_context(case_set, draft, request)
    cases = checked.to_dict()["cases"]
    if type(decisions) is not dict or not set(decisions) <= {case["id"] for case in cases}:
        raise ContractError("Unknown case review identifiers", code="validation-shape")
    if reviewer is not None:
        _text(reviewer, 128)
    selected = []
    for case in cases:
        choice = decisions.get(
            case["id"], {"decision": "pending", "expected": None, "reason": None}
        )
        _object(choice, {"decision", "expected", "reason"})
        state = choice["decision"]
        if type(state) is not str or state not in {"pending", "approved", "changed", "declined"}:
            raise ContractError("Invalid case review decision", code="validation-shape")
        expected = choice["expected"]
        if state in {"approved", "changed"}:
            if type(expected) is not bool or (
                (expected == case["expected"]) != (state == "approved")
            ):
                raise ContractError("Case review label/decision mismatch", code="validation-shape")
        elif expected is not None:
            raise ContractError("Unreviewed case cannot select a label", code="validation-shape")
        if state == "pending":
            if choice["reason"] is not None:
                raise ContractError(
                    "Pending review cannot claim a review reason", code="validation-shape"
                )
        else:
            _text(choice["reason"])
        selected.append({"case_id": case["id"], "case_sha256": identity(case), **choice})
    states = {item["decision"] for item in selected}
    status = next(
        state for state in ("declined", "pending", "changed", "approved") if state in states
    )
    return _snapshot(
        {
            "schema_version": OWNER_CASE_PLAN_SCHEMA_VERSION,
            "kind": "owner-case-label-review",
            "case_set_id": checked.case_set_id,
            "case_authorship": "model-authored",
            "reviewer": reviewer,
            "reviewer_authenticated": False,
            "decisions": selected,
            "label_review_status": status,
            "all_labels_reviewed": states <= {"approved", "changed"},
            "execution_status": "not-run",
            "authorization_status": "unknown",
        },
        OwnerCaseLabelReview,
    )


def validate_owner_case_review(
    raw: str, case_set: OwnerCaseSet, draft: OwnerPolicyReview, request: CodexAnalysisRequest
) -> OwnerCaseLabelReview:
    data = decode(raw)
    # Require one decision per case in original order: duplicates, omissions and
    # reordering cannot silently collapse while reconstructing a dictionary.
    checked = _case_context(case_set, draft, request)
    decisions = data.get("decisions")
    cases = checked.to_dict()["cases"]
    if type(decisions) is not list or len(decisions) != len(cases):
        raise ContractError("Incomplete case review", code="validation-shape")
    choices = {}
    for case, item in zip(cases, decisions, strict=True):
        _object(item, {"case_id", "case_sha256", "decision", "expected", "reason"})
        if item["case_id"] != case["id"] or item["case_sha256"] != identity(case):
            raise ContractError("Case review input mismatch", code="validation-identity")
        choices[case["id"]] = {key: item[key] for key in ("decision", "expected", "reason")}
    expected = review_owner_cases(
        checked, draft, request, decisions=choices, reviewer=data.get("reviewer")
    )
    return _match(raw, expected)


def _recipe() -> dict:
    # Design data only. #80 must implement/review a pinned harness and bounds;
    # these proposed limits are NOT observations of enforced process isolation.
    return {
        "id": "owned-owner-policy-regression-v1",
        "version": "1.0",
        "status": "design-only; no executor or worker",
        "target": "exact packaged policy.py only",
        "entrypoint": "can_read_report",
        "input_mapping": (
            "null or fixed Principal/Report; scope array to frozenset; no normalization"
        ),
        "comparison": "exact bool observed against caller-reviewed expected",
        "model_text": "reason is display-only; never code or instructions",
        "proposed_limits": {
            "max_cases": 16,
            "max_scopes": 16,
            "max_identifier_characters": 128,
            "max_input_bytes": MAX_JSON_BYTES,
            "max_output_bytes": 16384,
            "timeout_seconds": 5,
        },
        "exclusions": [
            "main.py",
            "FastAPI/HTTP/auth/database",
            "arbitrary paths/code",
            "install hooks",
            "network/provider",
            "patch application",
        ],
    }


def prepare_owner_policy_plan(
    review: OwnerCaseLabelReview,
    case_set: OwnerCaseSet,
    draft: OwnerPolicyReview,
    request: CodexAnalysisRequest,
) -> OwnerPolicyPlan:
    """Preview exact policy bytes/cases/recipe; even reviewed plans cannot run."""
    _read(review, OwnerCaseLabelReview)
    checked = _case_context(case_set, draft, request)
    labels = validate_owner_case_review(review.payload_json, checked, draft, request)
    data = checked.to_dict()
    reviewed = labels.to_dict()
    policy = next(
        item
        for item in data["evidence"]
        if item["kind"] == "source" and item["data"]["path"] == "policy.py"
    )
    recipe = _recipe()
    return _snapshot(
        {
            "schema_version": OWNER_CASE_PLAN_SCHEMA_VERSION,
            "kind": "owner-policy-plan-preview",
            "case_set_id": checked.case_set_id,
            "label_review_id": labels.label_review_id,
            "request_id": data["request_id"],
            "source_identity": data["source_identity"],
            "source_sha256": data["source_sha256"],
            "policy_source": policy["data"]["text"],
            "policy_evidence_id": policy["id"],
            "cases": data["cases"],
            "label_review": reviewed,
            "harness_recipe": recipe,
            "harness_recipe_sha256": identity(recipe),
            "planning_status": "reviewed-preview"
            if reviewed["all_labels_reviewed"]
            else "blocked-" + reviewed["label_review_status"],
            "execution_available": False,
            "requires_separate_execution_approval": True,
            "execution_status": "not-run",
            "authorization_status": "unknown",
            "patch_application": "not-run",
            "provider_calls": 0,
            "limitations": [
                "Caller-recorded label review is not authenticated maintainer approval.",
                "Plan identity is a content digest, not execution or sharing authority.",
                "No executor, observed result or enforced process/sandbox limits exist here.",
                "Pure-policy cases do not establish authentication or HTTP authorization.",
                "Correct policy may require no change; do not invent a defect for a demo.",
            ],
        },
        OwnerPolicyPlan,
    )


def validate_owner_policy_plan(
    raw: str,
    review: OwnerCaseLabelReview,
    case_set: OwnerCaseSet,
    draft: OwnerPolicyReview,
    request: CodexAnalysisRequest,
) -> OwnerPolicyPlan:
    return _match(raw, prepare_owner_policy_plan(review, case_set, draft, request))
