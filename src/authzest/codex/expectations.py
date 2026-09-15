"""Pure, caller-authored expectations bound to proposal and baseline evidence.

This is not a test generator, an executor, an approval, or an observed result.
"""

import re
from dataclasses import dataclass
from typing import Any

from .contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    _integer,
    _list,
    _object,
    _text,
    _unique,
    canonical,
    decode,
    identity,
)
from .proposals import ValidatedProposal, content_hash, validate_proposal

EXPECTATION_SCHEMA_VERSION = "1.0"
_SPEC_FIELDS = {
    "id",
    "source_evidence_id",
    "route_evidence_id",
    "policy_evidence_ids",
    "observation",
    "expected",
    "limitations",
}
_BINDING_FIELDS = {"path", "baseline_registration_id", "before_sha256", "after_sha256"}
_OBSERVATIONS = {"policy-intent", "dependency-declarations", "scope-declarations"}


@dataclass(frozen=True, slots=True)
class ValidatedExpectationManifest:
    """Immutable structural artifact; consumers must revalidate even this wrapper."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def manifest_id(self) -> str:
        return "expectation-" + identity(self.to_dict())


def _context(request, review, proposal):
    request = CodexAnalysisRequest(request.payload_json)
    # This revalidates the review too; a wrapper is not a trust boundary.
    proposal = validate_proposal(proposal.payload_json, request, review)
    data = request.to_dict()
    return (
        request,
        proposal,
        {item["id"]: item for item in data["evidence"]},
        {change["path"]: change for change in proposal.to_dict()["changes"]},
    )


def _evidence(evidence, reference, kind):
    item = evidence.get(_text(reference, 128))
    if item is None or item["kind"] != kind:
        raise ContractError("Missing or wrong-kind expectation evidence")
    return item["data"]


def _bindings(item, evidence, changes):
    source = _evidence(evidence, item["source_evidence_id"], "source")
    route = _evidence(evidence, item["route_evidence_id"], "route")
    policies = [_text(ref, 128) for ref in _list(item["policy_evidence_ids"], 16)]
    _unique(policies)
    if not policies:
        raise ContractError("Expectation needs an explicit policy reference")
    for ref in policies:
        _evidence(evidence, ref, "policy")
    path = source["path"]
    if route["file"] != path or path not in changes:
        raise ContractError("Expectation must bind the route's changed source")
    return {
        "path": path,
        "baseline_registration_id": route["registration_id"],
        "before_sha256": content_hash(source["text"]),
        "after_sha256": content_hash(changes[path]["after_text"]),
    }


def _expected(item):
    observation = _text(item["observation"], 64)
    if observation not in _OBSERVATIONS:
        raise ContractError("Unsupported expectation observation")
    expected = item["expected"]
    if observation == "policy-intent":
        _object(expected, {"intent"})
        if _text(expected["intent"], 32) not in {"public", "restricted", "unspecified"}:
            raise ContractError("Unsupported policy intent")
    elif observation == "dependency-declarations":
        _object(expected, {"count"})
        if _integer(expected["count"]) > 256:
            raise ContractError("Expectation dependency count exceeds limit")
    else:
        _object(expected, {"scopes"})
        _unique([_text(scope, 256) for scope in _list(expected["scopes"], 32)])
    limitations = [_text(text) for text in _list(item["limitations"], 16)]
    if not limitations:
        raise ContractError("Expectation needs explicit limitations")


def validate_expectation_manifest(
    raw: str,
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    proposal: ValidatedProposal,
) -> ValidatedExpectationManifest:
    """Validate supplied artifact relationships, not policy truth or test outcomes."""
    request, proposal, evidence, changes = _context(request, review, proposal)
    data = decode(raw)
    _object(
        data,
        {
            "schema_version",
            "request_id",
            "review_id",
            "proposal_id",
            "source_identity",
            "expectations",
        },
    )
    if (
        data["schema_version"] != EXPECTATION_SCHEMA_VERSION
        or data["request_id"] != request.request_id
        or data["review_id"] != proposal.to_dict()["review_id"]
        or data["proposal_id"] != proposal.proposal_id
        or data["source_identity"] != request.to_dict()["source_identity"]
    ):
        raise ContractError("Expectation identity does not match supplied artifacts")
    items = _list(data["expectations"], 32)
    if not items:
        raise ContractError("Expectation manifest must not be empty")
    ids = []
    observations = set()
    for item in items:
        _object(item, _SPEC_FIELDS | _BINDING_FIELDS)
        item_id = _text(item["id"], 64)
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", item_id):
            raise ContractError("Invalid expectation identifier")
        ids.append(item_id)
        bindings = _bindings(item, evidence, changes)
        if any(item[key] != value for key, value in bindings.items()):
            raise ContractError("Stale or inconsistent expectation binding")
        _expected(item)
        key = (item["baseline_registration_id"], item["observation"])
        if key in observations:
            raise ContractError("Duplicate registration observation")
        observations.add(key)
    _unique(ids)
    return ValidatedExpectationManifest(canonical(data))


def prepare_expectation_manifest(
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    proposal: ValidatedProposal,
    *,
    expectations: list[dict[str, Any]],
) -> ValidatedExpectationManifest:
    """Package caller-authored specs; derive bindings without reading or executing files."""
    request, proposal, evidence, changes = _context(request, review, proposal)
    items = []
    for spec in _list(expectations, 32):
        _object(spec, _SPEC_FIELDS)
        items.append(spec | _bindings(spec, evidence, changes))
    return validate_expectation_manifest(
        canonical(
            {
                "schema_version": EXPECTATION_SCHEMA_VERSION,
                "request_id": request.request_id,
                "review_id": proposal.to_dict()["review_id"],
                "proposal_id": proposal.proposal_id,
                "source_identity": request.to_dict()["source_identity"],
                "expectations": items,
            }
        ),
        request,
        review,
        proposal,
    )


def expectation_preview(
    manifest: ValidatedExpectationManifest,
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    proposal: ValidatedProposal,
) -> dict[str, Any]:
    """Return detached draft data; no observations, approval or execution are produced."""
    manifest = validate_expectation_manifest(manifest.payload_json, request, review, proposal)
    data = manifest.to_dict()
    for item in data["expectations"]:
        item["basis"] = (
            "caller-policy-interpretation"
            if item["observation"] == "policy-intent"
            else "source-declaration-target"
        )
    return data | {
        "manifest_id": manifest.manifest_id,
        "status": "draft",
        "verification_status": "not-run",
        "observed": None,
        "authorization_verdict": "unknown",
        "limitations": [
            "References bind supplied snapshots, not semantic support or filesystem freshness.",
            "Policy citations are not approval; declarations do not establish enforcement.",
            "Registration identity refers to baseline source, not post-patch identity.",
            "Expectations may cover only part of the proposal and have not been checked.",
            "No approval or executor consumes this manifest; existing decisions do not bind it.",
        ],
    }
