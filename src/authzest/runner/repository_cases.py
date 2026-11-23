"""Pure supplied independent-case data; never approval or runtime evidence.

Authorship, assumptions and applicability are declarations, not authenticated
review. Hashes identify the supplied data. This codec performs no I/O, imports
no target, and cannot establish policy truth or authorize file operations.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from authzest.codex.contracts import (
    ContractError,
    _list,
    canonical,
    decode,
    identity,
)
from authzest.codex.contracts import (
    _object as _contract_object,
)
from authzest.codex.repository_proposal import _path

SCHEMA_VERSION = "1.0"
MAX_CASE_BYTES = 65_536
MAX_BODY_BYTES = 4096
MAX_BODY_DEPTH = 8
MAX_BODY_NODES = 128
MAX_JSON_INTEGER = (1 << 53) - 1
HEADER_NAMES = frozenset({"x-user", "x-user-id", "x-role"})
COVERAGE_ROLES = frozenset({"owner", "non-owner", "anonymous", "normal-use", "public"})
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


def _fail(message: str, code: str = "validation-shape") -> None:
    raise ContractError(message, code=code)


def _object(value: Any, fields: set[str]) -> dict:
    # Refuse oversized dictionaries before constructing a set of supplied keys.
    if type(value) is not dict or len(value) != len(fields):
        _fail("Unexpected independent-case object fields")
    return _contract_object(value, fields)


def _string(value: Any, limit: int, *, nonblank: bool = False) -> str:
    if type(value) is not str or len(value) > limit or nonblank and not value.strip():
        _fail("Invalid independent-case text", "validation-text")
    try:
        if len(value.encode("utf-8")) > limit:
            _fail("Independent-case text byte limit exceeded", "validation-budget")
    except UnicodeError:
        raise ContractError("Invalid independent-case Unicode", code="validation-text") from None
    return value


def _prose(value: Any, limit: int) -> str:
    text = _string(value, limit, nonblank=True)
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        _fail("Invalid independent-case prose", "validation-text")
    return text


def _case_id(value: Any) -> str:
    text = _string(value, 64, nonblank=True)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", text) is None:
        _fail("Invalid independent-case identifier", "validation-identity")
    return text


def _digest(value: Any) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail("Invalid independent-case digest", "validation-identity")
    return value


def _json_value(value: Any) -> None:
    # Bound each container before extending the work list; never walk an
    # unbounded supplied collection or stringify arbitrarily large integers.
    pending = [(value, 0)]
    visited = 0
    while pending:
        current, depth = pending.pop()
        visited += 1
        if depth > MAX_BODY_DEPTH or visited > MAX_BODY_NODES:
            _fail("Independent-case JSON structural limit exceeded", "validation-budget")
        kind = type(current)
        if current is None or kind is bool:
            continue
        if kind is str:
            _string(current, 1024)
        elif kind is int:
            if not -MAX_JSON_INTEGER <= current <= MAX_JSON_INTEGER:
                _fail("Independent-case integer exceeds the portable range", "validation-budget")
        elif kind is float:
            if not math.isfinite(current):
                _fail("Non-finite independent-case number", "validation-json")
        elif kind in (list, dict):
            if len(current) > MAX_BODY_NODES:
                _fail("Independent-case JSON collection limit exceeded", "validation-budget")
            if kind is dict:
                for key in current:
                    _string(key, 128)
                children = current.values()
            else:
                children = current
            pending.extend((child, depth + 1) for child in children)
        else:
            _fail("Independent-case value is not strict JSON", "validation-json")
    if len(canonical(value).encode("utf-8")) > MAX_BODY_BYTES:
        _fail("Independent-case JSON byte limit exceeded", "validation-budget")


def validate_repository_response_value(value: dict, *, expected: bool = True) -> dict:
    """Detach a bounded typed response; observed 3xx/5xx data is not policy proof."""
    if type(expected) is not bool:
        _fail("Expected-response mode must be boolean")
    response = _object(value, {"status", "body"})
    status = response["status"]
    if type(status) is not int or not 200 <= status <= 599:
        _fail("Invalid independent-case HTTP status")
    if expected and not (200 <= status <= 299 or 400 <= status <= 499):
        _fail("Unsupported expected HTTP status")
    body = response["body"]
    if type(body) is not dict or type(body.get("kind")) is not str:
        _fail("Invalid independent-case body")
    if body["kind"] == "empty":
        _object(body, {"kind"})
    elif body["kind"] == "json":
        _object(body, {"kind", "value"})
        if status in {204, 205, 304}:
            _fail("This HTTP status requires an empty body")
        _json_value(body["value"])
    else:
        _fail("Unsupported independent-case body kind")
    return decode(canonical({"response": response}))["response"]


def _request(value: Any) -> None:
    request = _object(value, {"method", "path", "headers"})
    if type(request["method"]) is not str or request["method"] != "GET":
        _fail("Only literal GET case requests are supported")
    path = _string(request["path"], 512, nonblank=True)
    if (
        re.fullmatch(r"/[A-Za-z0-9/_.-]*", path) is None
        or "//" in path
        or any(part in {".", ".."} for part in path.split("/"))
    ):
        _fail("Invalid independent-case relative GET path", "validation-identity")
    headers = request["headers"]
    if type(headers) is not dict or len(headers) > 3:
        _fail("Invalid independent-case synthetic headers")
    for name, value in headers.items():
        if type(name) is not str or name not in HEADER_NAMES:
            _fail("Unsupported independent-case header")
        if (
            type(value) is not str
            or re.fullmatch(r"test-[A-Za-z0-9][A-Za-z0-9_.-]{0,58}", value) is None
        ):
            _fail("Only bounded synthetic header values are supported")


def _payload(value: Any) -> dict:
    data = _object(value, _FIELDS)
    if data["schema_version"] != SCHEMA_VERSION or data["kind"] != "repository-independent-cases":
        _fail("Independent-case schema mismatch", "validation-identity")
    basis = _object(data["basis"], _BASIS_FIELDS)
    for name in ("selection_id", "source_sha256", "policy_sha256"):
        _digest(basis[name])
    interface_id = _string(basis["interface_id"], len("repository-test-interface-") + 64)
    if not interface_id.startswith("repository-test-interface-"):
        _fail("Invalid independent-case interface identity", "validation-identity")
    _digest(interface_id.removeprefix("repository-test-interface-"))
    _path(basis["source_path"], {".py"})
    _path(basis["policy_path"], {".md", ".txt"})
    _prose(data["authorship"], 256)
    assumptions = _list(data["assumptions"], 16)
    if not assumptions:
        _fail("Independent cases require explicit assumptions")
    for text in assumptions:
        _prose(text, 1024)
    cases = _list(data["cases"], 8)
    if len(cases) < 4:
        _fail("Independent cases require four to eight entries")
    ids = []
    for case in cases:
        _object(case, {"id", "request", "before", "after"})
        case_id = _case_id(case["id"])
        if case_id in ids:
            _fail("Duplicate independent-case identifier", "validation-duplicate")
        ids.append(case_id)
        _request(case["request"])
        validate_repository_response_value(case["before"])
        validate_repository_response_value(case["after"])
    regression = _case_id(data["regression_case_id"])
    if regression not in ids:
        _fail("Missing designated regression case", "validation-identity")
    _prose(data["regression_reason"], 1024)
    designated = cases[ids.index(regression)]
    if canonical(designated["before"]) == canonical(designated["after"]):
        _fail("Designated regression must declare a desired-policy mismatch")
    coverage = _object(data["coverage"], set(COVERAGE_ROLES))
    for role, declaration in coverage.items():
        _object(declaration, {"case_ids", "not_applicable_reason"})
        covered = _list(declaration["case_ids"], 8)
        for case_id in covered:
            _case_id(case_id)
        if len(set(covered)) != len(covered) or any(case_id not in ids for case_id in covered):
            _fail("Invalid independent-case coverage references", "validation-identity")
        reason = declaration["not_applicable_reason"]
        if covered:
            if reason is not None:
                _fail("Applicable coverage cannot also be not-applicable")
        else:
            if role == "normal-use":
                _fail("A normal-use control is required")
            _prose(reason, 1024)
    payload = decode(canonical(data))
    payload["case_set_id"] = "repository-case-set-" + identity(payload)
    if len(canonical(payload).encode("utf-8")) > MAX_CASE_BYTES:
        _fail("Independent-case document byte limit exceeded", "validation-budget")
    return payload


def _decode(raw: str) -> dict:
    if type(raw) is not str:
        _fail("Expected independent-case JSON", "validation-json")
    try:
        if len(raw) > MAX_CASE_BYTES or len(raw.encode("utf-8")) > MAX_CASE_BYTES:
            _fail("Independent-case document byte limit exceeded", "validation-budget")
    except UnicodeError:
        raise ContractError("Invalid independent-case Unicode", code="validation-text") from None
    return decode(raw)


@dataclass(frozen=True, slots=True)
class RepositoryCaseSet:
    """Detached declarations, never a reviewed-label or runtime capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return _decode(self.payload_json)

    @property
    def case_set_id(self) -> str:
        return self.to_dict()["case_set_id"]


def build_repository_cases(data: dict) -> RepositoryCaseSet:
    """Validate supplied case declarations and freeze their canonical identities."""
    return RepositoryCaseSet(canonical(_payload(data)))


def validate_repository_cases(cases: RepositoryCaseSet) -> RepositoryCaseSet:
    """Reconstruct the complete closed data contract; rehashing never grants authority."""
    if type(cases) is not RepositoryCaseSet:
        _fail("Expected independent-case set")
    data = _object(_decode(cases.payload_json), _FIELDS | {"case_set_id"})
    supplied_id = data.pop("case_set_id")
    expected = build_repository_cases(data)
    if type(supplied_id) is not str or supplied_id != expected.case_set_id:
        _fail("Independent-case identity mismatch", "validation-identity")
    return expected
