"""HTTP-only comparisons of supplied observations, never live phase evidence.

The plan binds current proposal data to independent expectations without a
generated pytest or T role. Hashes and supplied cleanup declarations are not
provider provenance, reviewed policy truth, runtime measurements or decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import (
    ContractError,
    _list,
    canonical,
    contract_failure_code,
    decode,
    identity,
)
from authzest.codex.repository_http_proposal import (
    RepositoryHttpRequest,
    validate_repository_http_request,
    validate_repository_http_response,
)
from authzest.runner.repository_cases import _object, validate_repository_response_value
from authzest.runner.repository_http_cases import (
    RepositoryHttpCaseSet,
    validate_repository_http_cases,
)

SCHEMA_VERSION = "2.0"
MAX_PHASE_BYTES = 65_536
_PHASES = ("before", "after")
_ERRORS = ("timeout", "http-framing", "body-invalid", "setup-error", "transport-error")
_INERT = {
    "evidence_basis": "supplied-unverified",
    "execution_status": "not-run",
    "authorization_status": "unknown",
    "verified_fix": False,
    "live_evidence": False,
    "writes_authorized": False,
}


def _fail(message: str, code: str = "validation-shape") -> None:
    raise ContractError(message, code=code)


def _phase(value: str) -> None:
    if type(value) is not str or value not in _PHASES:
        _fail("Unsupported HTTP observation phase")


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RepositoryHttpVerificationPlan:
    """Detached HTTP material/case declarations, never runtime or file authority."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return self.to_dict()["plan_id"]


@dataclass(frozen=True, slots=True)
class RepositoryHttpPhaseCandidate:
    """Supplied typed HTTP observations, not a live executor's phase result."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


def build_repository_http_verification_plan(
    request: RepositoryHttpRequest, response: dict, cases: RepositoryHttpCaseSet | None
) -> RepositoryHttpVerificationPlan | None:
    """Bind a proposed repair to independent cases without executing any artifact.

    A validated no-change/unknown/refused response returns ``None`` and may omit
    cases. A proposed change requires an exact HTTP case set, never ``None``.
    """
    checked = validate_repository_http_request(request)
    context = checked.to_dict()
    response = validate_repository_http_response(canonical(response), checked)
    if response["status"] != "proposed-change":
        return None
    case_set = validate_repository_http_cases(cases).to_dict()
    selection = context["selection"]
    source, policy = selection["files"]
    expected_basis = {
        "selection_id": identity(selection),
        "interface_id": context["http_interface"]["interface_id"],
        "source_path": source["path"],
        "source_sha256": source["sha256"],
        "policy_path": policy["path"],
        "policy_sha256": policy["sha256"],
    }
    if case_set["basis"] != expected_basis:
        _fail("HTTP cases differ from current input/interface", "validation-identity")
    proposal = response["proposal"]
    poc = proposal["poc"]
    normalized_poc = {
        "method": poc["method"],
        "path": poc["path"],
        "headers": {row["name"]: row["value"] for row in poc["headers"]},
    }
    regression_id = case_set["regression_case_id"]
    designated = next(case for case in case_set["cases"] if case["id"] == regression_id)
    if canonical(normalized_poc) != canonical(designated["request"]):
        _fail("HTTP PoC is not covered by the designated case", "validation-evidence")
    payload = {
        "kind": "repository-http-verification-plan",
        "schema_version": SCHEMA_VERSION,
        "request_id": checked.request_id,
        "request_identity": identity(context),
        "proposal_identity": identity(response),
        "basis": expected_basis,
        "source": {
            "path": source["path"],
            "before_sha256": source["sha256"],
            "after_sha256": _hash(proposal["after_text"]),
        },
        "http_interface": context["http_interface"],
        "case_set_id": case_set["case_set_id"],
        "case_set": case_set,
        "poc_sha256": identity(poc),
        "poc_request": normalized_poc,
        "designated_regression_case_id": regression_id,
        "requirements": {
            "case_review": "supplied-unverified-not-authenticated-approval",
            "material_identity": "declared-current-inputs-not-staged-runtime-measurements",
            "runtime_images": "not-reviewed-or-started",
            "transport": "typed-data-only-not-raw-http-framing",
        },
        **_INERT,
    }
    payload["plan_id"] = "repository-http-verification-plan-" + identity(payload)
    result = RepositoryHttpVerificationPlan(canonical(payload))
    result.to_dict()
    return result


def validate_repository_http_verification_plan(
    plan: RepositoryHttpVerificationPlan,
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet,
) -> RepositoryHttpVerificationPlan:
    if type(plan) is not RepositoryHttpVerificationPlan:
        _fail("Expected an HTTP verification plan")
    expected = build_repository_http_verification_plan(request, response, cases)
    if expected is None or canonical(plan.to_dict()) != expected.payload_json:
        _fail("HTTP verification plan mismatch", "validation-identity")
    return expected


def prepare_repository_http_observer_schedule(
    plan: RepositoryHttpVerificationPlan,
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet,
    *,
    phase: str,
) -> dict:
    """Project requests only, excluding policy, source and expected answers."""
    _phase(phase)
    data = validate_repository_http_verification_plan(plan, request, response, cases).to_dict()
    return {
        "kind": "repository-http-observer-schedule",
        "schema_version": SCHEMA_VERSION,
        "plan_id": data["plan_id"],
        "phase": phase,
        "requests": [
            {"case_id": case["id"], **case["request"]} for case in data["case_set"]["cases"]
        ],
    }


def _binding(plan: dict, phase: str) -> dict:
    return {
        "source_sha256": plan["source"][phase + "_sha256"],
        "interface_id": plan["http_interface"]["interface_id"],
        "case_set_id": plan["case_set_id"],
        "poc_sha256": plan["poc_sha256"],
    }


def _frame(raw: str, plan: dict, phase: str) -> dict:
    if type(raw) is not str:
        _fail("Expected supplied HTTP phase JSON", "validation-json")
    try:
        if len(raw) > MAX_PHASE_BYTES or len(raw.encode("utf-8")) > MAX_PHASE_BYTES:
            _fail("Supplied HTTP phase byte limit exceeded", "validation-budget")
    except UnicodeError:
        raise ContractError("Invalid supplied HTTP phase Unicode", code="validation-text") from None
    frame = _object(
        decode(raw),
        {"kind", "schema_version", "plan_id", "phase", "binding", "observations", "cleanup"},
    )
    if (
        frame["kind"] != "repository-http-supplied-phase"
        or frame["schema_version"] != SCHEMA_VERSION
        or frame["plan_id"] != plan["plan_id"]
        or frame["phase"] != phase
        or frame["binding"] != _binding(plan, phase)
    ):
        _fail("Supplied HTTP phase identity mismatch", "validation-identity")
    observations = _list(frame["observations"], 8)
    expected = plan["case_set"]["cases"]
    if len(observations) != len(expected):
        _fail("Supplied HTTP phase must retain every planned case", "validation-evidence")
    aborted = False
    for item, case in zip(observations, expected, strict=True):
        _object(item, {"case_id", "outcome", "response", "error_code"})
        if item["case_id"] != case["id"]:
            _fail("Supplied HTTP case order/identity mismatch", "validation-identity")
        outcome = item["outcome"]
        if aborted:
            if (
                outcome != "not-dispatched"
                or item["response"] is not None
                or item["error_code"] != "phase-aborted"
            ):
                _fail("Aborted HTTP phase must retain an undispatched suffix")
        elif outcome == "response":
            if item["error_code"] is not None:
                _fail("HTTP response cannot also contain a transport error")
            validate_repository_response_value(item["response"], expected=False)
        elif outcome == "error":
            if (
                item["response"] is not None
                or type(item["error_code"]) is not str
                or item["error_code"] not in _ERRORS
            ):
                _fail("Invalid supplied HTTP transport error")
            aborted = True
        else:
            _fail("Unsupported supplied HTTP observation outcome")
    cleanup = _object(frame["cleanup"], {"A", "B"})
    if any(
        type(value) is not str or value not in ("confirmed", "unknown", "failed")
        for value in cleanup.values()
    ):
        _fail("Unsupported supplied HTTP cleanup state")
    return frame


def _candidate(frame: dict, plan: dict, phase: str) -> RepositoryHttpPhaseCandidate:
    return RepositoryHttpPhaseCandidate(
        canonical(
            {
                "kind": "repository-http-phase-candidate",
                "schema_version": SCHEMA_VERSION,
                "plan_id": plan["plan_id"],
                "phase": phase,
                "frame": frame,
                **_INERT,
            }
        )
    )


def decode_repository_http_phase_candidate(
    raw: str,
    plan: RepositoryHttpVerificationPlan,
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet,
    *,
    phase: str,
) -> RepositoryHttpPhaseCandidate:
    _phase(phase)
    data = validate_repository_http_verification_plan(plan, request, response, cases).to_dict()
    return _candidate(_frame(raw, data, phase), data, phase)


def validate_repository_http_phase_candidate(
    candidate: RepositoryHttpPhaseCandidate,
    plan: RepositoryHttpVerificationPlan,
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet,
    *,
    phase: str,
) -> RepositoryHttpPhaseCandidate:
    if type(candidate) is not RepositoryHttpPhaseCandidate:
        _fail("Expected a supplied HTTP phase candidate")
    supplied = candidate.to_dict()
    if "frame" not in supplied:
        _fail("Missing supplied HTTP phase frame")
    expected = decode_repository_http_phase_candidate(
        canonical(supplied["frame"]), plan, request, response, cases, phase=phase
    )
    if canonical(supplied) != expected.payload_json:
        _fail("Supplied HTTP phase candidate mismatch", "validation-identity")
    return expected


def compare_repository_http_phase(
    raw: str,
    plan: RepositoryHttpVerificationPlan,
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet,
    *,
    phase: str,
) -> dict:
    """Compare supplied data; even all matching criteria remain unverified."""
    _phase(phase)
    data = validate_repository_http_verification_plan(plan, request, response, cases).to_dict()
    planned = data["case_set"]["cases"]
    regression_id = data["case_set"]["regression_case_id"]
    invalid_code = None
    try:
        frame = _frame(raw, data, phase)
    except ContractError as exc:
        frame = None
        invalid_code = contract_failure_code(exc)
    outcomes = []
    desired_mismatch = None
    if frame is None:
        outcomes = [
            {"case_id": case["id"], "outcome": "invalid", "reason": invalid_code}
            for case in planned
        ]
    else:
        for case, observed in zip(planned, frame["observations"], strict=True):
            if observed["outcome"] == "not-dispatched":
                outcome, reason = "not-dispatched", "phase-aborted"
            elif observed["outcome"] == "error":
                outcome, reason = "error", observed["error_code"]
            elif not (
                200 <= observed["response"]["status"] < 300
                or 400 <= observed["response"]["status"] < 500
            ):
                outcome, reason = "error", "non-policy-http-status"
            elif canonical(observed["response"]) == canonical(case[phase]):
                outcome, reason = "match", "matches-supplied-" + phase
            else:
                outcome, reason = "mismatch", "differs-from-supplied-" + phase
            outcomes.append({"case_id": case["id"], "outcome": outcome, "reason": reason})
            if phase == "before" and case["id"] == regression_id:
                desired_mismatch = (
                    observed["outcome"] == "response"
                    and outcome == "match"
                    and canonical(observed["response"]) != canonical(case["after"])
                )
    counts = {
        name: sum(case["outcome"] == name for case in outcomes)
        for name in ("match", "mismatch", "error", "not-dispatched", "invalid")
    }
    cleanup = frame is not None and all(value == "confirmed" for value in frame["cleanup"].values())
    return {
        "kind": "repository-http-supplied-comparison",
        "schema_version": SCHEMA_VERSION,
        "plan_id": data["plan_id"],
        "phase": phase,
        "binding": _binding(data, phase),
        "frame_status": "valid-supplied" if frame is not None else "invalid-supplied",
        "planned_cases": len(planned),
        "outcomes": outcomes,
        "counts": counts,
        "designated_regression_case_id": regression_id,
        "supplied_before_differs_from_desired_after": desired_mismatch,
        "cleanup_supplied_confirmed": cleanup,
        "supplied_criteria_met": (
            counts["match"] == len(planned)
            and cleanup
            and (phase == "after" or desired_mismatch is True)
        ),
        **_INERT,
    }
