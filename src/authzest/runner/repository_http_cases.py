"""Independent HTTP-only case declarations, never human approval or live evidence.

Cases describe supplied policy expectations. Their authorship and coverage fields
are not authenticated review, and content identities grant no run/write authority.
This codec does not read files, call a provider or import/execute a target app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from authzest.codex.contracts import ContractError, _list, canonical, identity
from authzest.codex.repository_http_proposal import validate_repository_http_options
from authzest.codex.repository_proposal import _path
from authzest.runner.repository_cases import (
    COVERAGE_ROLES,
    MAX_CASE_BYTES,
    _case_id,
    _decode,
    _digest,
    _object,
    _prose,
    _request,
    _string,
    validate_repository_response_value,
)

SCHEMA_VERSION = "2.0"
KIND = "repository-http-independent-cases"
_FIELDS = {
    "schema_version",
    "kind",
    "basis",
    "authorship",
    "assumptions",
    "regression_case_id",
    "regression_reason",
    "coverage",
    "cases",
}
_BASIS_FIELDS = {
    "selection_id",
    "interface_id",
    "source_path",
    "source_sha256",
    "policy_path",
    "policy_sha256",
}
_REQUIRED_COVERAGE = frozenset({"owner", "non-owner", "normal-use"})


def _fail(message: str, code: str = "validation-shape") -> None:
    raise ContractError(message, code=code)


def _payload(value: Any) -> dict:
    data = _object(value, _FIELDS)
    if data["schema_version"] != SCHEMA_VERSION or data["kind"] != KIND:
        _fail("HTTP independent-case schema mismatch", "validation-identity")
    basis = _object(data["basis"], _BASIS_FIELDS)
    for name in ("selection_id", "source_sha256", "policy_sha256"):
        _digest(basis[name])
    prefix = "repository-http-interface-"
    interface_id = _string(basis["interface_id"], len(prefix) + 64)
    if not interface_id.startswith(prefix):
        _fail("Invalid HTTP independent-case interface", "validation-identity")
    _digest(interface_id.removeprefix(prefix))
    validate_repository_http_options(basis["source_path"])
    _path(basis["policy_path"], {".md", ".txt"})
    _prose(data["authorship"], 256)
    assumptions = _list(data["assumptions"], 16)
    if not assumptions:
        _fail("HTTP independent cases require explicit assumptions")
    for text in assumptions:
        _prose(text, 1024)
    cases = _list(data["cases"], 8)
    if len(cases) < 4:
        _fail("HTTP independent cases require four to eight entries")
    ids = []
    for case in cases:
        _object(case, {"id", "request", "before", "after"})
        case_id = _case_id(case["id"])
        if case_id in ids:
            _fail("Duplicate HTTP independent-case identifier", "validation-duplicate")
        ids.append(case_id)
        _request(case["request"])
        validate_repository_response_value(case["before"])
        validate_repository_response_value(case["after"])
    regression = _case_id(data["regression_case_id"])
    if regression not in ids:
        _fail("Missing designated HTTP regression case", "validation-identity")
    _prose(data["regression_reason"], 1024)
    designated = cases[ids.index(regression)]
    if canonical(designated["before"]) == canonical(designated["after"]):
        _fail("Designated HTTP regression needs a desired-policy mismatch")
    coverage = _object(data["coverage"], set(COVERAGE_ROLES))
    for role, declaration in coverage.items():
        _object(declaration, {"case_ids", "not_applicable_reason"})
        covered = _list(declaration["case_ids"], 8)
        for case_id in covered:
            _case_id(case_id)
        if len(set(covered)) != len(covered) or any(case_id not in ids for case_id in covered):
            _fail("Invalid HTTP independent-case coverage references", "validation-identity")
        reason = declaration["not_applicable_reason"]
        if covered:
            if reason is not None:
                _fail("Applicable HTTP coverage cannot also be not-applicable")
        else:
            if role in _REQUIRED_COVERAGE:
                _fail("Owner, non-owner and normal-use HTTP coverage are required")
            _prose(reason, 1024)
    payload = _decode(canonical(data))
    payload["case_set_id"] = "repository-http-case-set-" + identity(payload)
    if len(canonical(payload).encode("utf-8")) > MAX_CASE_BYTES:
        _fail("HTTP independent-case byte limit exceeded", "validation-budget")
    return payload


@dataclass(frozen=True, slots=True)
class RepositoryHttpCaseSet:
    """Detached HTTP policy declarations, not approval, execution or write authority."""

    payload_json: str

    def to_dict(self) -> dict:
        return _decode(self.payload_json)

    @property
    def case_set_id(self) -> str:
        return self.to_dict()["case_set_id"]


def build_repository_http_cases(data: dict) -> RepositoryHttpCaseSet:
    """Validate closed HTTP-only declarations and freeze the supplied data."""
    return RepositoryHttpCaseSet(canonical(_payload(data)))


def validate_repository_http_cases(cases: RepositoryHttpCaseSet) -> RepositoryHttpCaseSet:
    """Rebuild exact HTTP data; no old test-interface case type is adopted."""
    if type(cases) is not RepositoryHttpCaseSet:
        _fail("Expected HTTP independent-case set")
    data = _object(_decode(cases.payload_json), _FIELDS | {"case_set_id"})
    supplied_id = data.pop("case_set_id")
    expected = build_repository_http_cases(data)
    if type(supplied_id) is not str or supplied_id != expected.case_set_id:
        _fail("HTTP independent-case identity mismatch", "validation-identity")
    return expected
