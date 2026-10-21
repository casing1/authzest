"""Registered synthetic repair-pair data and a host-generated diff, never execution.

The deliberately incorrect before source is inert test-only text. Nothing here
imports/evaluates it, calls a provider, opens a path, applies a patch or approves
an action. A recorded maintainer review is provenance, not an authenticated token.
Existing S1 requests and the fixed policy worker are not extended by this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import unified_diff
from hashlib import sha256
from typing import Any

from .contracts import ContractError, _list, _object, _text, _unique, canonical, decode, identity
from .owner_policy_recommendation import build_owner_policy_recommendation_request

REPAIR_PAIR_SCHEMA_VERSION = "1.0"
REPAIR_PAIR_REGISTRY_VERSION = "owned-synthetic-v1"
DIFF_RECIPE_VERSION = "unified-v1-context-3"
_S1_REQUEST_ID = (
    "owner-recommendation-request-56213e7526d3e3d483a342695027761bed08251e70701cbccf010e80d830a8e4"
)
_BEFORE_SHA256 = "54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950"
_AFTER_SHA256 = "faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04"
_CASES_SHA256 = "96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3"
# Pinned below from the exact reviewed bytes/criteria/assumptions/cases, not a caller setting.
_CONTENT_SHA256 = "2cbbc004b46ac2bc65b98c3e3b4b3e1e5919dd3d1b35920871372432c23203fb"
_REVIEW_RECORD_SHA256 = "3540dd3578ee838b1bfb34f3c02019286716b47664ec942da46e8dac25d4b7e8"
_WARNING = "# INTENTIONALLY INCORRECT TEST-ONLY: ownership comparison deliberately omitted.\n"
_CORRECT_RETURN = '    return subject == owner_id and "reports:read" in scopes\n'
_INCORRECT_RETURN = '    return "reports:read" in scopes\n'
# Original authorship remains assistant-authored; the exact expectations were
# separately accepted on 2026-10-19. These data are not observations or an evaluation set.
_CASE_ENVELOPE = r"""{"cases":[
{
  "case_id":"owner-control",
  "principal":{"subject":"alice","authenticated":true,"scopes":["reports:read"]},
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"allow"
},
{
  "case_id":"non-owner",
  "principal":{"subject":"bob","authenticated":true,"scopes":["reports:read"]},
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"deny"
},
{
  "case_id":"missing-read-scope",
  "principal":{"subject":"alice","authenticated":true,"scopes":[]},
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"deny"
},
{
  "case_id":"unauthenticated-owner",
  "principal":{"subject":"alice","authenticated":false,"scopes":["reports:read"]},
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"deny"
},
{
  "case_id":"missing-principal",
  "principal":null,
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"deny"
},
{
  "case_id":"missing-report",
  "principal":{"subject":"alice","authenticated":true,"scopes":["reports:read"]},
  "report":null,
  "expected":"deny"
},
{
  "case_id":"wildcard-is-not-read",
  "principal":{"subject":"alice","authenticated":true,"scopes":["reports:*"]},
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"deny"
},
{
  "case_id":"exact-owner-no-normalization",
  "principal":{"subject":" alice","authenticated":true,"scopes":["reports:read"]},
  "report":{"report_id":"report-001","owner_id":"alice"},
  "expected":"deny"
}
]}"""


@dataclass(frozen=True, slots=True)
class _Snapshot:
    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class OwnerPolicyRepairPair(_Snapshot):
    """Immutable data wrapper; direct construction grants no validation or authority."""

    @property
    def pair_id(self) -> str:
        return "owner-repair-pair-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class OwnerPolicyRepairPairPreview(_Snapshot):
    """Output-only inspectable data, never an input to an approval or patch service."""


def _snapshot(data: dict, kind: type[_Snapshot]):
    raw = canonical(data)
    decode(raw)  # Include complete host metadata and diff in the shared budget.
    return kind(raw)


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _digest(value: Any) -> None:
    if not re.fullmatch(r"[a-f0-9]{64}", _text(value, 64)):
        raise ContractError("Invalid content digest", code="validation-identity")


def _source_shape(value: Any) -> None:
    source = _object(value, {"text", "sha256"})
    _text(source["text"], 32_768)
    _digest(source["sha256"])


def _content_shape(value: Any) -> None:
    data = _object(
        value,
        {
            "version",
            "scenario_id",
            "path",
            "before",
            "after",
            "criteria",
            "assumptions",
            "cases",
            "cases_sha256",
        },
    )
    for field in ("version", "scenario_id", "path"):
        _text(data[field], 128)
    for field in ("before", "after", "criteria"):
        _source_shape(data[field])
    _text(data["criteria"]["text"])
    assumptions = _list(data["assumptions"], 3)
    if len(assumptions) != 3:
        raise ContractError("Invalid fixed assumptions", code="validation-shape")
    for item in assumptions:
        _object(item, {"id", "text"})
        _text(item["id"], 128)
        _text(item["text"])
    cases = _list(data["cases"], 8)
    if len(cases) != 8:
        raise ContractError("Invalid fixed case set", code="validation-shape")
    case_ids = []
    for case in cases:
        _object(case, {"case_id", "principal", "report", "expected"})
        case_ids.append(_text(case["case_id"], 128))
        if _text(case["expected"], 8) not in {"allow", "deny"}:
            raise ContractError("Unsupported expectation", code="validation-status")
        if case["principal"] is not None:
            principal = _object(case["principal"], {"subject", "authenticated", "scopes"})
            _text(principal["subject"], 128)
            if type(principal["authenticated"]) is not bool:
                raise ContractError("Invalid authentication datum", code="validation-shape")
            scopes = _list(principal["scopes"], 16)
            for scope in scopes:
                _text(scope, 128)
            _unique(scopes)
        if case["report"] is not None:
            report = _object(case["report"], {"report_id", "owner_id"})
            _text(report["report_id"], 128)
            _text(report["owner_id"], 128)
    _unique(case_ids)
    _digest(data["cases_sha256"])


def _provenance_shape(value: Any) -> None:
    provenance = _object(value, {"kind", "authenticated"})
    _text(provenance["kind"], 128)
    if provenance["authenticated"] is not False:
        raise ContractError("Not authenticated approval", code="validation-shape")


def _shape(data: dict) -> None:
    _object(data, {"schema_version", "kind", "registry_version", "content", "review_binding"})
    for field in ("schema_version", "kind", "registry_version"):
        _text(data[field], 128)
    _content_shape(data["content"])
    binding = _object(
        data["review_binding"], {"content_sha256", "review_record_sha256", "review_record"}
    )
    _digest(binding["content_sha256"])
    _digest(binding["review_record_sha256"])
    record = _object(
        binding["review_record"],
        {
            "schema_version",
            "kind",
            "design_head",
            "decision_date",
            "decision",
            "content_sha256",
            "cases_sha256",
            "record_url",
            "provenance",
        },
    )
    for field in ("schema_version", "kind", "design_head", "decision_date", "decision"):
        _text(record[field], 128)
    _text(record["record_url"], 512)
    for field in ("content_sha256", "cases_sha256"):
        _digest(record[field])
    _provenance_shape(record["provenance"])


def _registered_content() -> dict:
    request = build_owner_policy_recommendation_request()
    if request.request_id != _S1_REQUEST_ID:
        raise ContractError("Reviewed S1 context changed", code="validation-identity")
    context = request.to_dict()
    after = context["source"]["text"]
    if after.count(_CORRECT_RETURN) != 1:
        raise ContractError("Reviewed source changed", code="validation-identity")
    before = _WARNING + after.replace(_CORRECT_RETURN, _INCORRECT_RETURN, 1)
    envelope = decode(_CASE_ENVELOPE)
    _object(envelope, {"cases"})
    cases = envelope["cases"]
    if (
        _hash_text(before) != _BEFORE_SHA256
        or _hash_text(after) != _AFTER_SHA256
        or identity(cases) != _CASES_SHA256
    ):
        raise ContractError("Reviewed source or cases changed", code="validation-identity")
    return {
        "version": "test-only-v1",
        "scenario_id": "synthetic-owner-omission-v1",
        "path": "policy.py",  # Display label only; never resolve/open it.
        "before": {"text": before, "sha256": _BEFORE_SHA256},
        "after": {"text": after, "sha256": _AFTER_SHA256},
        "criteria": {key: context["criteria"][key] for key in ("text", "sha256")},
        "assumptions": context["assumptions"],
        "cases": cases,
        "cases_sha256": _CASES_SHA256,
    }


def _registered_payload() -> dict:
    content = _registered_content()
    content_hash = identity(content)
    if content_hash != _CONTENT_SHA256:
        raise ContractError("Reviewed content changed", code="validation-identity")
    # Separate record -> content, then registry -> both hashes. No self-referential hash.
    record = {
        "schema_version": "1.0",
        "kind": "recorded-owner-policy-pair-review",
        "design_head": "35ebe17d96c07540cf2753f2e53625d138ded0aa",
        "decision_date": "2026-10-19",
        "decision": "accept-scenario-and-case-expectations",
        "content_sha256": content_hash,
        "cases_sha256": _CASES_SHA256,
        "record_url": "https://github.com/casing1/authzest/pull/100#issuecomment-6258235318",
        "provenance": {"kind": "recorded-maintainer-chat", "authenticated": False},
    }
    record_hash = identity(record)
    if record_hash != _REVIEW_RECORD_SHA256:
        raise ContractError("Recorded review changed", code="validation-identity")
    return {
        "schema_version": REPAIR_PAIR_SCHEMA_VERSION,
        "kind": "owner-policy-repair-pair",
        "registry_version": REPAIR_PAIR_REGISTRY_VERSION,
        "content": content,
        "review_binding": {
            "content_sha256": content_hash,
            "review_record_sha256": record_hash,
            "review_record": record,
        },
    }


def build_owner_policy_repair_pair() -> OwnerPolicyRepairPair:
    """Build the one registered manifest, with no source/path/registry options."""
    data = _registered_payload()
    _shape(data)
    return _snapshot(data, OwnerPolicyRepairPair)


def validate_owner_policy_repair_pair(raw: str) -> OwnerPolicyRepairPair:
    """Compare every supplied field against the complete current registered context."""
    data = decode(raw)
    _shape(data)
    expected = build_owner_policy_repair_pair()
    if canonical(data) != expected.payload_json:
        raise ContractError("Registered pair binding mismatch", code="validation-identity")
    return expected


def prepare_owner_policy_repair_pair_preview(
    pair: OwnerPolicyRepairPair,
) -> OwnerPolicyRepairPairPreview:
    """Derive one diff as output data, never approve/apply/run/render that data."""
    if type(pair) is not OwnerPolicyRepairPair:
        raise ContractError("Unexpected pair artifact type", code="validation-shape")
    checked = validate_owner_policy_repair_pair(getattr(pair, "payload_json", None))
    payload = checked.to_dict()
    content = payload["content"]
    diff = "".join(
        unified_diff(
            content["before"]["text"].splitlines(keepends=True),
            content["after"]["text"].splitlines(keepends=True),
            fromfile="a/policy.py",
            tofile="b/policy.py",
            n=3,
            lineterm="\n",
        )
    )
    return _snapshot(
        {
            "schema_version": REPAIR_PAIR_SCHEMA_VERSION,
            "kind": "owner-policy-repair-pair-preview",
            "pair_id": checked.pair_id,
            "pair": payload,
            "recipe_version": DIFF_RECIPE_VERSION,
            "diff": diff,
            "diff_sha256": _hash_text(diff),
            "provider_calls": 0,
            "execution_status": "not-run",
            "patch_application": "not-run",
            "restoration_status": "not-run",
            "authorization_status": "unknown",
            "comparison_status": "not-evaluated",
            "observations": {"before": None, "after": None},
            "provenance": {"kind": "registered-test-only-template", "authenticated": False},
        },
        OwnerPolicyRepairPairPreview,
    )
