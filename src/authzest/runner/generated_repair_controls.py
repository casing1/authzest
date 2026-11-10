"""Maintained HTTP controls and DATA-ONLY comparisons for one synthetic scenario.

No application, generated test, process, provider or filesystem is accessed here.
Caller-supplied facts are not authenticated observations or runtime approval. The
demo actor header is fixture input, not authentication. These independently
maintained controls do not change the generation prompt's pending policy review.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any, Literal

from authzest.codex.contracts import ContractError, _object, canonical, decode, identity

SCENARIO_ID = "owned-fastapi-document-ownership-v1"
MAX_BODY_BYTES = 8192
MAX_HEADER_COUNT = 32
MAX_HEADER_BYTES = 4096
MAX_JSON_DEPTH = 16
_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z", re.ASCII)

# Assistant-authored maintained constants, independent of any generated test or
# repair. Tests compare these literals with the public source as inert text.
_DOCUMENTS = (
    ("doc-alice", "alice", "Alice's synthetic document"),
    ("doc-bob", "bob", "Bob's synthetic document"),
)


def _bounded_decode(raw: str) -> dict[str, Any]:
    """Bound nesting before the shared duplicate-key/size/finite JSON decoder."""
    if type(raw) is not str:
        raise ContractError("Expected JSON text", code="validation-json")
    # A small lexical prepass bounds nesting before json.loads allocates a tree.
    # Strings and escaped delimiters are never interpreted as structure.
    if len(raw) > 262_144:
        raise ContractError("JSON size limit exceeded", code="validation-budget")
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ContractError("JSON nesting limit exceeded", code="validation-budget")
        elif char in "]}":
            depth -= 1
    return decode(raw)


def _payload(document: tuple[str, str, str]) -> dict[str, str]:
    document_id, owner, body = document
    return {"id": document_id, "owner": owner, "body": body}


def _controls_payload() -> dict[str, Any]:
    cases = []

    def add_case(case_id: str, category: str, inputs: list[tuple[str | None, str]]) -> None:
        requests = []
        documents = {row[0]: row for row in _DOCUMENTS}
        for number, (actor, document_id) in enumerate(inputs, start=1):
            document = documents.get(document_id)
            if actor not in {"alice", "bob"}:
                before = after = {
                    "status_code": 401,
                    "body_json": {"detail": "Unknown demo actor"},
                }
            elif document is None:
                before = after = {
                    "status_code": 404,
                    "body_json": {"detail": "Document not found"},
                }
            else:
                before = {"status_code": 200, "body_json": _payload(document)}
                after = (
                    before
                    if actor == document[1]
                    else {"status_code": 403, "body_json": {"detail": "Forbidden"}}
                )
            requests.append(
                {
                    "request_id": f"{case_id}/{number}",
                    "method": "GET",
                    "path": f"/documents/{document_id}",
                    "headers": [] if actor is None else [["x-demo-actor", actor]],
                    "expected_before": before,
                    "expected_after": after,
                    "protected_plaintext_markers": (
                        list(document)
                        if document is not None
                        and actor in {"alice", "bob"}
                        and actor != document[1]
                        else []
                    ),
                }
            )
        cases.append({"case_id": case_id, "category": category, "requests": requests})

    for document_id, owner, _ in _DOCUMENTS:
        add_case(f"owner-{owner}", "owner", [(owner, document_id)])
    for actor, other in (("alice", "doc-bob"), ("bob", "doc-alice")):
        add_case(f"cross-owner-{actor}", "cross-owner", [(actor, other)])
    for label, actor in (
        ("missing-actor", None),
        ("empty-actor", ""),
        ("unknown-actor", "mallory"),
    ):
        for document_id in ("doc-alice", "doc-bob", "missing"):
            add_case(f"{label}-{document_id}", label, [(actor, document_id)])
    for actor in ("alice", "bob"):
        add_case(f"missing-document-{actor}", "missing-document", [(actor, "missing")])
    for actor, own, other in (
        ("alice", "doc-alice", "doc-bob"),
        ("bob", "doc-bob", "doc-alice"),
    ):
        add_case(
            f"normal-sequence-{actor}",
            "normal-sequence",
            [(actor, own), (actor, other), (actor, own)],
        )
    return {
        "schema_version": "1.0",
        "kind": "generated-repair-controls",
        "scenario_id": SCENARIO_ID,
        "authorship": "assistant",
        "review": "maintainer-accepted-offline-design",
        "runtime_approval": "not-granted",
        "actor_identity": "caller-controlled-fixture-header-not-authentication",
        "case_count": 17,
        "request_count": 21,
        "cases": cases,
        "limits": {
            "response_body_bytes": MAX_BODY_BYTES,
            "response_header_count": MAX_HEADER_COUNT,
            "response_header_bytes": MAX_HEADER_BYTES,
            "response_header_byte_accounting": (
                "UTF-8 name/value bytes + colon-space and CRLF per field + final CRLF"
            ),
            "json_depth": MAX_JSON_DEPTH,
        },
        "limitations": [
            "One maintained synthetic scenario, not arbitrary FastAPI policy or authentication.",
            "Expected bodies are exact maintained JSON values, independent of generated tests.",
            "Disclosure checks cover only listed case-insensitive literal plaintext markers, "
            "not encoded, transformed, timing or other side channels.",
            "A matched before profile is data consistent with the intended defect, not proof "
            "that any application or generated defensive test ran.",
            "A matched after profile is not an independently verified repair "
            "or execution approval.",
            "Observed fact ordering must represent the declared requests; input JSON cannot "
            "prove sequencing, target identity, isolation, cleanup or provenance.",
        ],
    }


def _checked_controls(raw: str) -> dict[str, Any]:
    data = _bounded_decode(raw)
    # Canonical JSON comparison distinguishes booleans/numbers as well as shape,
    # ordering, all constants and unknown fields; caller hashes are not trusted.
    if canonical(data) != canonical(_controls_payload()):
        raise ContractError("Maintained HTTP controls mismatch", code="validation-identity")
    return data


@dataclass(frozen=True, slots=True)
class GeneratedRepairControls:
    """Immutable, revalidated maintained controls; not an approval capability."""

    payload_json: str

    def __post_init__(self) -> None:
        _checked_controls(self.payload_json)

    @property
    def controls_id(self) -> str:
        return "generated-repair-controls-" + identity(_checked_controls(self.payload_json))

    def to_dict(self) -> dict[str, Any]:
        return _checked_controls(self.payload_json)


def build_generated_repair_controls() -> GeneratedRepairControls:
    """Build only maintained input data; do not read or execute source files."""
    return GeneratedRepairControls(canonical(_controls_payload()))


def validate_generated_repair_controls(raw: str) -> GeneratedRepairControls:
    """Accept exactly the current closed controls, not a self-consistent forgery."""
    return GeneratedRepairControls(canonical(_checked_controls(raw)))


@dataclass(frozen=True, slots=True)
class GeneratedRepairControlsComparison:
    """Immutable data comparison, explicitly not execution evidence or a fix claim."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return _bounded_decode(self.payload_json)


def _body_bytes(value: Any) -> bytes:
    if type(value) is not str or len(value) > ((MAX_BODY_BYTES + 2) // 3) * 4:
        raise ContractError("HTTP body size or shape mismatch", code="validation-budget")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ContractError("Invalid HTTP body encoding", code="validation-shape") from exc
    if len(raw) > MAX_BODY_BYTES or base64.b64encode(raw).decode("ascii") != value:
        raise ContractError("Non-canonical or oversized HTTP body", code="validation-budget")
    return raw


def _headers(value: Any) -> list[list[str]]:
    if type(value) is not list or len(value) > MAX_HEADER_COUNT:
        raise ContractError("HTTP header count mismatch", code="validation-budget")
    # Account for the complete represented HTTP header block, including its
    # terminating empty line; response status-line bytes are not headers.
    size = 2
    for pair in value:
        if type(pair) is not list or len(pair) != 2 or any(type(part) is not str for part in pair):
            raise ContractError("Invalid HTTP header shape", code="validation-shape")
        name, content = pair
        # Cheap character-count lower bound before regex, character scanning or
        # UTF-8 allocation. A single huge field cannot walk the whole JSON budget.
        if len(name) + len(content) + 4 > MAX_HEADER_BYTES - size:
            raise ContractError("HTTP header byte limit exceeded", code="validation-budget")
        if not _HEADER_NAME.fullmatch(name) or any(
            ord(char) < 32 and char != "\t" or 127 <= ord(char) <= 159 for char in content
        ):
            raise ContractError("Invalid HTTP header text", code="validation-text")
        size += len(name.encode("utf-8")) + len(content.encode("utf-8")) + 4
        if size > MAX_HEADER_BYTES:
            raise ContractError("HTTP header byte limit exceeded", code="validation-budget")
    return value


def _body_matches(body: bytes, expected: dict[str, Any]) -> bool:
    try:
        actual = _bounded_decode(body.decode("utf-8"))
    except (ContractError, UnicodeError):
        return False
    return canonical(actual) == canonical(expected)


def compare_generated_repair_observations(
    raw: str,
    controls: GeneratedRepairControls,
    *,
    candidate: Literal["before", "after"],
) -> GeneratedRepairControlsComparison:
    """Compare unverified HTTP fact data without running or authorizing anything.

    All twenty-one facts are required in maintained order. A before match needs
    the exact intended cross-owner disclosure profile, not any failing response.
    Facts may be forged by their caller; no success result is runtime evidence.
    """
    if type(candidate) is not str or candidate not in {"before", "after"}:
        raise ContractError("Explicit HTTP candidate required", code="validation-shape")
    if type(controls) is not GeneratedRepairControls:
        raise ContractError("Maintained HTTP controls required", code="validation-shape")
    checked = validate_generated_repair_controls(controls.payload_json)
    control_data = checked.to_dict()
    data = _bounded_decode(raw)
    _object(data, {"schema_version", "kind", "controls_id", "candidate", "facts"})
    if (
        data["schema_version"] != "1.0"
        or data["kind"] != "generated-repair-http-facts"
        or data["controls_id"] != checked.controls_id
        or data["candidate"] != candidate
    ):
        raise ContractError("HTTP fact identity mismatch", code="validation-identity")
    facts = data["facts"]
    requests = [request for case in control_data["cases"] for request in case["requests"]]
    if type(facts) is not list or len(facts) != len(requests):
        raise ContractError("Complete HTTP fact set required", code="validation-shape")
    comparisons = {}
    for fact, request in zip(facts, requests, strict=True):
        _object(fact, {"request_id", "status_code", "headers", "body_base64"})
        if fact["request_id"] != request["request_id"]:
            raise ContractError("HTTP fact order or identity mismatch", code="validation-identity")
        status = fact["status_code"]
        if type(status) is not int or not 100 <= status <= 599:
            raise ContractError("Invalid HTTP status", code="validation-shape")
        headers = _headers(fact["headers"])
        body = _body_bytes(fact["body_base64"])
        expected = request[f"expected_{candidate}"]
        reasons = []
        if status != expected["status_code"]:
            reasons.append("status-code-mismatch")
        if not _body_matches(body, expected["body_json"]):
            reasons.append("body-json-mismatch")
        if candidate == "after" and request["protected_plaintext_markers"]:
            visible = (
                body.lower()
                + b"\n"
                + b"\n".join(
                    (name + ":" + content).encode("utf-8").lower() for name, content in headers
                )
            )
            if any(
                marker.encode("utf-8").lower() in visible
                for marker in request["protected_plaintext_markers"]
            ):
                reasons.append("protected-plaintext-marker")
        comparisons[request["request_id"]] = {
            "request_id": request["request_id"],
            "matches": not reasons,
            "reasons": reasons,
        }
    cases = [
        {
            "case_id": case["case_id"],
            "matches": all(comparisons[row["request_id"]]["matches"] for row in case["requests"]),
            "requests": [comparisons[row["request_id"]] for row in case["requests"]],
        }
        for case in control_data["cases"]
    ]
    matched = all(case["matches"] for case in cases)
    return GeneratedRepairControlsComparison(
        canonical(
            {
                "schema_version": "1.0",
                "kind": "generated-repair-controls-comparison",
                "controls_id": checked.controls_id,
                "observations_id": "generated-repair-http-facts-" + identity(data),
                "candidate": candidate,
                "status": "data-only",
                "comparison_status": "matches-expected-profile" if matched else "profile-mismatch",
                "matches_expected_profile": matched,
                "expected_profile": (
                    "intended-before-defect"
                    if candidate == "before"
                    else "repaired-policy-controls"
                ),
                "case_count": len(cases),
                "request_count": len(requests),
                "matching_case_count": sum(case["matches"] for case in cases),
                "matching_request_count": sum(row["matches"] for row in comparisons.values()),
                "cases": cases,
                "provenance": "caller-supplied-unverified",
                "authorization_status": "unknown",
                "execution_status": "not-established",
                "verified_fix": False,
                "applied": False,
                "provider_calls": 0,
                "limitations": control_data["limitations"],
            }
        )
    )
