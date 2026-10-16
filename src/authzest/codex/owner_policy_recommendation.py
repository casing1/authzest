"""Offline recommendation data for one registered synthetic policy.

There is no provider, filesystem, process, policy evaluation or patch capability.
Only no-change/unknown results are supported; shape is not semantic validation,
model provenance, authenticated approval or evidence of endpoint authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .contracts import (
    ContractError,
    _list,
    _object,
    _text,
    _unique,
    canonical,
    decode,
    identity,
)
from .owner_policy_review import OWNER_POLICY_SOURCE

OWNER_POLICY_RECOMMENDATION_SCHEMA_VERSION = "1.0"
OWNER_POLICY_RECOMMENDATION_CRITERIA = (
    "Allow a report read only for an already trusted principal whose authenticated value "
    "is exactly true, whose scopes contain the literal reports:read value, and whose "
    "subject exactly matches a trusted report owner. Deny missing or malformed "
    "principal/report context, blank identifiers or malformed scopes. Do not normalize "
    "identifiers. There is no administrator, wildcard or ownership exception. This pure "
    "predicate does not authenticate inputs or prove HTTP enforcement."
)
# Policy-only criteria above are deliberately separate from historical review text.
# Immutable tuples avoid a mutable shared assumptions/registry object between calls.
_ASSUMPTIONS = (
    (
        "trusted-principal",
        "The caller supplies an already trusted principal; constructing a dataclass does "
        "not authenticate identity, scopes or authentication claims.",
    ),
    (
        "trusted-ownership",
        "Report ownership and report identity come from a trusted lookup, not "
        "request-supplied claims.",
    ),
    (
        "synthetic-pure-policy",
        "Only the maintained synthetic pure predicate is in scope; HTTP, "
        "authentication-provider, database and endpoint enforcement are not evaluated.",
    ),
)
_REQUEST_FIELDS = {
    "schema_version",
    "kind",
    "scenario_id",
    "source",
    "criteria",
    "assumptions",
    "registry",
}
_RESULT_FIELDS = {
    "schema_version",
    "request_id",
    "status",
    "rationale",
    "evidence_ids",
    "assumptions",
    "uncertainties",
    "expected_effects",
    "limitations",
    "change_pair_id",
}


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """Detached immutable JSON data; direct construction is not validation."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class OwnerPolicyRecommendationRequest(_Snapshot):
    @property
    def request_id(self) -> str:
        return "owner-recommendation-request-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class OwnerPolicyRecommendation(_Snapshot):
    @property
    def recommendation_id(self) -> str:
        return "owner-recommendation-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class OwnerPolicyRecommendationPreview(_Snapshot):
    """Output-only data, never accepted as an approval or execution input."""


def _snapshot(data: dict, kind: type[_Snapshot]):
    raw = canonical(data)
    decode(raw)  # Host metadata/snapshots must satisfy the full shared budget, too.
    return kind(raw)


def _read(value: _Snapshot, kind: type[_Snapshot]) -> str:
    if type(value) is not kind:
        raise ContractError("Unexpected recommendation artifact type", code="validation-shape")
    raw = getattr(value, "payload_json", None)
    decode(raw)
    return raw


def _registered_payload() -> dict:
    # This logical path is display data. Never resolve/open/import/evaluate it.
    source = {
        "path": "policy.py",
        "text": _text(OWNER_POLICY_SOURCE, 32_768),
        "sha256": sha256(OWNER_POLICY_SOURCE.encode("utf-8")).hexdigest(),
    }
    criteria = {
        "text": _text(OWNER_POLICY_RECOMMENDATION_CRITERIA),
        "sha256": sha256(OWNER_POLICY_RECOMMENDATION_CRITERIA.encode("utf-8")).hexdigest(),
    }
    return {
        "schema_version": OWNER_POLICY_RECOMMENDATION_SCHEMA_VERSION,
        "kind": "owner-policy-recommendation-request",
        "scenario_id": "owned-report-read-policy-v1",
        "source": {**source, "evidence_id": "owner-recommendation-source-" + identity(source)},
        "criteria": {
            **criteria,
            "evidence_id": "owner-recommendation-criteria-" + identity(criteria),
        },
        "assumptions": [{"id": key, "text": text} for key, text in _ASSUMPTIONS],
        "registry": {"version": "empty-v1", "pairs": []},
    }


def _request_shape(data: dict) -> None:
    _object(data, _REQUEST_FIELDS)
    for field in ("schema_version", "kind", "scenario_id"):
        _text(data[field], 128)
    source = _object(data["source"], {"path", "text", "sha256", "evidence_id"})
    _text(source["text"], 32_768)
    for field in ("path", "sha256", "evidence_id"):
        _text(source[field], 128)
    criteria = _object(data["criteria"], {"text", "sha256", "evidence_id"})
    _text(criteria["text"])
    for field in ("sha256", "evidence_id"):
        _text(criteria[field], 128)
    assumptions = _list(data["assumptions"], 3)
    if len(assumptions) != 3:
        raise ContractError("Invalid fixed assumptions", code="validation-shape")
    for assumption in assumptions:
        _object(assumption, {"id", "text"})
        _text(assumption["id"], 128)
        _text(assumption["text"])
    registry = _object(data["registry"], {"version", "pairs"})
    _text(registry["version"], 128)
    _list(registry["pairs"], 0)


def build_owner_policy_recommendation_request() -> OwnerPolicyRecommendationRequest:
    """Snapshot registered constants only, with no caller source or model option."""
    data = _registered_payload()
    _request_shape(data)
    return _snapshot(data, OwnerPolicyRecommendationRequest)


def validate_owner_policy_recommendation_request(raw: str) -> OwnerPolicyRecommendationRequest:
    """Rebuild and compare every field; old or forged snapshots are never trusted."""
    data = decode(raw)
    _request_shape(data)
    expected = build_owner_policy_recommendation_request()
    if canonical(data) != expected.payload_json:
        raise ContractError("Registered request binding mismatch", code="validation-identity")
    return expected


def _request_context(request: OwnerPolicyRecommendationRequest) -> OwnerPolicyRecommendationRequest:
    return validate_owner_policy_recommendation_request(
        _read(request, OwnerPolicyRecommendationRequest)
    )


def _text_list(value: Any, *, minimum: int) -> None:
    values = _list(value, 32)
    if len(values) < minimum:
        raise ContractError("Missing recommendation explanation", code="validation-shape")
    for item in values:
        _text(item)


def validate_owner_policy_recommendation(
    raw: str, request: OwnerPolicyRecommendationRequest
) -> OwnerPolicyRecommendation:
    """Validate caller/scripted data, not model origin or semantic correctness."""
    checked = _request_context(request)
    context = checked.to_dict()
    data = decode(raw)
    _object(data, _RESULT_FIELDS)
    if _text(data["schema_version"], 128) != OWNER_POLICY_RECOMMENDATION_SCHEMA_VERSION:
        raise ContractError("Unsupported recommendation schema", code="validation-shape")
    if _text(data["request_id"], 128) != checked.request_id:
        raise ContractError("Recommendation request mismatch", code="validation-identity")
    status = _text(data["status"], 128)
    if status not in {"no-change", "unknown"}:
        raise ContractError("Unsupported recommendation status", code="validation-status")
    _text(data["rationale"])
    evidence = _list(data["evidence_ids"], 2)
    for item in evidence:
        _text(item, 128)
    _unique(evidence)
    if set(evidence) != {context["source"]["evidence_id"], context["criteria"]["evidence_id"]}:
        raise ContractError("Recommendation evidence mismatch", code="validation-evidence")
    for field in ("assumptions", "expected_effects", "limitations"):
        _text_list(data[field], minimum=1)
    _text_list(data["uncertainties"], minimum=1 if status == "unknown" else 0)
    if data["change_pair_id"] is not None:
        raise ContractError("No registered change pair", code="validation-shape")
    return _snapshot(data, OwnerPolicyRecommendation)


def prepare_owner_policy_recommendation_preview(
    recommendation: OwnerPolicyRecommendation, request: OwnerPolicyRecommendationRequest
) -> OwnerPolicyRecommendationPreview:
    """Revalidate and display detached data; never approve, run, render or apply it."""
    checked_request = _request_context(request)
    checked_result = validate_owner_policy_recommendation(
        _read(recommendation, OwnerPolicyRecommendation), checked_request
    )
    payload = checked_request.to_dict()
    return _snapshot(
        {
            "schema_version": OWNER_POLICY_RECOMMENDATION_SCHEMA_VERSION,
            "kind": "owner-policy-recommendation-preview",
            "request_id": checked_request.request_id,
            "recommendation_id": checked_result.recommendation_id,
            "request": payload,
            "recommendation": checked_result.to_dict(),
            "source_sha256": payload["source"]["sha256"],
            "criteria_sha256": payload["criteria"]["sha256"],
            "registry_version": payload["registry"]["version"],
            "changes": [],
            "diffs": [],
            "provider_calls": 0,
            "execution_status": "not-run",
            "patch_application": "not-run",
            "restoration_status": "not-run",
            "authorization_status": "unknown",
            "provenance": {"kind": "caller-supplied-data", "authenticated": False},
        },
        OwnerPolicyRecommendationPreview,
    )
