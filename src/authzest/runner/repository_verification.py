"""Pure comparisons of supplied external observations, never live phase evidence.

Typed frames and hashes bind declarations, not provider/observer provenance,
human review, staged filesystem bytes, cleanup or runtime execution. This module
has no launcher, file session, network, original-write or approval interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import (
    ContractError,
    _integer,
    _list,
    _object,
    canonical,
    contract_failure_code,
    decode,
    identity,
)
from authzest.codex.repository_test_interface import (
    RepositoryTestRequest,
    validate_repository_test_request,
    validate_repository_test_response,
)
from authzest.runner.repository_cases import (
    RepositoryCaseSet,
    validate_repository_cases,
    validate_repository_response_value,
)

MAX_PHASE_BYTES = 65_536
_PHASES = ("before", "after")
_ERRORS = ("timeout", "http-framing", "body-invalid", "setup-error", "transport-error")
_COUNTS = ("collected", "passed", "failed", "errors", "skipped", "xfailed", "xpassed")
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
        _fail("Unsupported observation phase")


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RepositoryVerificationPlan:
    """Detached host-only case/material declarations, not runtime or write authority."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return self.to_dict()["plan_id"]


@dataclass(frozen=True, slots=True)
class RepositoryPhaseCandidate:
    """A supplied typed observation frame; it is not a live executor's phase result."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


def build_repository_verification_plan(
    request: RepositoryTestRequest, response: dict, cases: RepositoryCaseSet
) -> RepositoryVerificationPlan | None:
    checked = validate_repository_test_request(request)
    context = checked.to_dict()
    response = validate_repository_test_response(canonical(response), checked)
    case_set = validate_repository_cases(cases).to_dict()
    selection = context["selection"]
    source, policy = selection["files"][:2]
    expected_basis = {
        "selection_id": identity(selection),
        "interface_id": context["test_interface"]["interface_id"],
        "source_path": source["path"],
        "source_sha256": source["sha256"],
        "policy_path": policy["path"],
        "policy_sha256": policy["sha256"],
    }
    if case_set["basis"] != expected_basis:
        _fail("Independent cases differ from current input/interface", "validation-identity")
    if response["status"] != "proposed-change":
        return None
    proposal = response["proposal"]
    payload = {
        "kind": "repository-verification-plan",
        "schema_version": "1.0",
        "request_id": checked.request_id,
        "base_request_id": context["base_request_id"],
        "request_identity": identity(context),
        "proposal_identity": identity(response),
        "basis": expected_basis,
        "source": {
            "path": source["path"],
            "before_sha256": source["sha256"],
            "after_sha256": _hash(proposal["after_text"]),
        },
        "test": {"path": proposal["test_path"], "sha256": _hash(proposal["test_text"])},
        "test_interface": context["test_interface"],
        "case_set_id": cases.case_set_id,
        "case_set": case_set,
        "requirements": {
            "case_review": "supplied-unverified-not-authenticated-approval",
            "material_identity": "declared-current-inputs-not-staged-runtime-measurements",
            "runtime_images": "not-reviewed-or-started",
            "transport": "typed-data-only-not-raw-http-framing",
        },
        **_INERT,
    }
    payload["plan_id"] = "repository-verification-plan-" + identity(payload)
    result = RepositoryVerificationPlan(canonical(payload))
    result.to_dict()
    return result


def validate_repository_verification_plan(
    plan: RepositoryVerificationPlan,
    request: RepositoryTestRequest,
    response: dict,
    cases: RepositoryCaseSet,
) -> RepositoryVerificationPlan:
    if type(plan) is not RepositoryVerificationPlan:
        _fail("Expected an external verification plan")
    expected = build_repository_verification_plan(request, response, cases)
    if expected is None or canonical(plan.to_dict()) != expected.payload_json:
        _fail("External verification plan mismatch", "validation-identity")
    return expected


def prepare_repository_observer_schedule(
    plan: RepositoryVerificationPlan,
    request: RepositoryTestRequest,
    response: dict,
    cases: RepositoryCaseSet,
    *,
    phase: str,
) -> dict:
    """Project only requests, never host-only answers, policy, source or test bytes."""
    _phase(phase)
    data = validate_repository_verification_plan(plan, request, response, cases).to_dict()
    return {
        "kind": "repository-observer-schedule",
        "schema_version": "1.0",
        "plan_id": data["plan_id"],
        "phase": phase,
        "requests": [
            {"case_id": case["id"], **case["request"]} for case in data["case_set"]["cases"]
        ],
    }


def _binding(plan: dict, phase: str) -> dict:
    return {
        "source_sha256": plan["source"][phase + "_sha256"],
        "test_sha256": plan["test"]["sha256"],
        "interface_id": plan["test_interface"]["interface_id"],
    }


def _frame(raw: str, plan: dict, phase: str) -> dict:
    if type(raw) is not str:
        _fail("Expected supplied phase JSON", "validation-json")
    try:
        if len(raw) > MAX_PHASE_BYTES or len(raw.encode("utf-8")) > MAX_PHASE_BYTES:
            _fail("Supplied phase byte limit exceeded", "validation-budget")
    except UnicodeError:
        raise ContractError("Invalid supplied phase Unicode", code="validation-text") from None
    frame = _object(
        decode(raw),
        {
            "kind",
            "schema_version",
            "plan_id",
            "phase",
            "binding",
            "observations",
            "pytest",
            "cleanup",
        },
    )
    if (
        frame["kind"] != "repository-supplied-phase"
        or frame["schema_version"] != "1.0"
        or frame["plan_id"] != plan["plan_id"]
        or frame["phase"] != phase
        or frame["binding"] != _binding(plan, phase)
    ):
        _fail("Supplied phase identity mismatch", "validation-identity")
    observations = _list(frame["observations"], 8)
    expected = plan["case_set"]["cases"]
    if len(observations) != len(expected):
        _fail("Supplied phase must retain every planned case", "validation-evidence")
    for item, case in zip(observations, expected, strict=True):
        _object(item, {"case_id", "outcome", "response", "error_code"})
        if item["case_id"] != case["id"]:
            _fail("Supplied phase case order/identity mismatch", "validation-identity")
        if item["outcome"] == "response":
            if item["error_code"] is not None:
                _fail("Response cannot also contain a transport error")
            validate_repository_response_value(item["response"], expected=False)
        elif item["outcome"] == "error":
            if (
                item["response"] is not None
                or type(item["error_code"]) is not str
                or item["error_code"] not in _ERRORS
            ):
                _fail("Invalid supplied transport error")
        else:
            _fail("Unsupported supplied observation outcome")
    pytest = _object(frame["pytest"], {*_COUNTS, "exit_code", "failure_kind"})
    for name in _COUNTS:
        _integer(pytest[name], 0)
        if pytest[name] > 128:
            _fail("Supplied pytest count exceeds limit", "validation-budget")
    if pytest["exit_code"] is not None:
        _integer(pytest["exit_code"], 0)
        if pytest["exit_code"] > 5:
            _fail("Unsupported supplied pytest exit status")
    if type(pytest["failure_kind"]) is not str or pytest["failure_kind"] not in (
        "none",
        "assertion",
        "other",
    ):
        _fail("Unsupported supplied pytest failure kind")
    cleanup = _object(frame["cleanup"], {"T", "A", "B"})
    if any(
        type(v) is not str or v not in ("confirmed", "unknown", "failed") for v in cleanup.values()
    ):
        _fail("Unsupported supplied cleanup state")
    return frame


def _candidate(frame: dict, plan: dict, phase: str) -> RepositoryPhaseCandidate:
    return RepositoryPhaseCandidate(
        canonical(
            {
                "kind": "repository-phase-candidate",
                "schema_version": "1.0",
                "plan_id": plan["plan_id"],
                "phase": phase,
                "frame": frame,
                **_INERT,
            }
        )
    )


def decode_repository_phase_candidate(
    raw: str,
    plan: RepositoryVerificationPlan,
    request: RepositoryTestRequest,
    response: dict,
    cases: RepositoryCaseSet,
    *,
    phase: str,
) -> RepositoryPhaseCandidate:
    _phase(phase)
    data = validate_repository_verification_plan(plan, request, response, cases).to_dict()
    return _candidate(_frame(raw, data, phase), data, phase)


def validate_repository_phase_candidate(
    candidate: RepositoryPhaseCandidate,
    plan: RepositoryVerificationPlan,
    request: RepositoryTestRequest,
    response: dict,
    cases: RepositoryCaseSet,
    *,
    phase: str,
) -> RepositoryPhaseCandidate:
    if type(candidate) is not RepositoryPhaseCandidate:
        _fail("Expected a supplied phase candidate")
    supplied = candidate.to_dict()
    if "frame" not in supplied:
        _fail("Missing supplied phase frame")
    expected = decode_repository_phase_candidate(
        canonical(supplied["frame"]), plan, request, response, cases, phase=phase
    )
    if canonical(supplied) != expected.payload_json:
        _fail("Supplied phase candidate mismatch", "validation-identity")
    return expected


def _pytest_criteria(data: dict, phase: str) -> bool:
    if data["collected"] == 0 or any(
        data[k] != 0 for k in ("errors", "skipped", "xfailed", "xpassed")
    ):
        return False
    if phase == "before":
        return (
            data["failed"] == 1
            and data["passed"] == data["collected"] - 1
            and data["exit_code"] == 1
            and data["failure_kind"] == "assertion"
        )
    return (
        data["passed"] == data["collected"]
        and data["failed"] == 0
        and data["exit_code"] == 0
        and data["failure_kind"] == "none"
    )


def compare_repository_phase(
    raw: str,
    plan: RepositoryVerificationPlan,
    request: RepositoryTestRequest,
    response: dict,
    cases: RepositoryCaseSet,
    *,
    phase: str,
) -> dict:
    """Compare provided data; even matching supplied criteria is never runtime proof."""
    _phase(phase)
    data = validate_repository_verification_plan(plan, request, response, cases).to_dict()
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
            {"case_id": c["id"], "outcome": "invalid", "reason": invalid_code} for c in planned
        ]
    else:
        for case, observed in zip(planned, frame["observations"], strict=True):
            if observed["outcome"] == "error":
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
        k: sum(c["outcome"] == k for c in outcomes)
        for k in ("match", "mismatch", "error", "invalid")
    }
    pytest_criteria = frame is not None and _pytest_criteria(frame["pytest"], phase)
    cleanup = frame is not None and all(v == "confirmed" for v in frame["cleanup"].values())
    return {
        "kind": "repository-supplied-comparison",
        "schema_version": "1.0",
        "plan_id": data["plan_id"],
        "phase": phase,
        "binding": _binding(data, phase),
        "frame_status": "valid-supplied" if frame is not None else "invalid-supplied",
        "planned_cases": len(planned),
        "outcomes": outcomes,
        "counts": counts,
        "designated_regression_case_id": regression_id,
        "supplied_before_differs_from_desired_after": desired_mismatch,
        "auxiliary_pytest_criteria_met": pytest_criteria,
        "cleanup_supplied_confirmed": cleanup,
        "supplied_criteria_met": (
            counts["match"] == len(planned)
            and pytest_criteria
            and cleanup
            and (phase == "after" or desired_mismatch is True)
        ),
        **_INERT,
    }
