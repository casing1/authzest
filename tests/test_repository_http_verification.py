"""Supplied HTTP comparison is bounded data, never an executed verification."""

import builtins
import io
import os
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner.repository_http_cases import build_repository_http_cases
from authzest.runner.repository_http_verification import (
    RepositoryHttpPhaseCandidate,
    RepositoryHttpVerificationPlan,
    build_repository_http_verification_plan,
    compare_repository_http_phase,
    decode_repository_http_phase_candidate,
    prepare_repository_http_observer_schedule,
    validate_repository_http_phase_candidate,
    validate_repository_http_verification_plan,
)
from authzest.runner.repository_verification import (
    RepositoryPhaseCandidate,
    RepositoryVerificationPlan,
    validate_repository_verification_plan,
)
from helpers.repository_http_verification_data import (
    AFTER,
    POLICY,
    SOURCE,
    case_data,
    inputs,
    phase_frame,
    plan_inputs,
)


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP verification data attempted an external effect")

    for owner, names in (
        (builtins, ("open", "eval", "exec")),
        (io, ("open",)),
        (os, ("open", "system", "fork", "execv", "execve", "posix_spawn")),
        (socket, ("socket", "create_connection")),
        (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
    ):
        for name in names:
            if hasattr(owner, name):
                monkeypatch.setattr(owner, name, forbidden)


def compare(frame, args, phase="before"):
    return compare_repository_http_phase(canonical(frame), *args, phase=phase)


def assert_inert(result):
    assert result["evidence_basis"] == "supplied-unverified"
    assert result["execution_status"] == "not-run"
    assert result["authorization_status"] == "unknown"
    assert result["verified_fix"] is result["live_evidence"] is result["writes_authorized"] is False


def counts(*, match=0, mismatch=0, error=0, undispatched=0, invalid=0):
    return {
        "match": match,
        "mismatch": mismatch,
        "error": error,
        "not-dispatched": undispatched,
        "invalid": invalid,
    }


def abort_suffix(frame, index, code="transport-error"):
    frame["observations"][index].update(outcome="error", response=None, error_code=code)
    for row in frame["observations"][index + 1 :]:
        row.update(outcome="not-dispatched", response=None, error_code="phase-aborted")


def test_plan_binds_full_current_artifacts_without_old_test_material():
    plan, request, response, cases = args = plan_inputs()
    data = plan.to_dict()
    assert validate_repository_http_verification_plan(*args) == plan
    assert data["request_identity"] == identity(request.to_dict())
    assert data["proposal_identity"] == identity(response)
    assert data["case_set"] == cases.to_dict()
    assert data["case_set_id"] == cases.case_set_id
    assert data["poc_sha256"] == identity(response["proposal"]["poc"])
    assert data["poc_request"] == cases.to_dict()["cases"][1]["request"]
    assert data["source"]["before_sha256"] != data["source"]["after_sha256"]
    assert data["http_interface"] == request.to_dict()["http_interface"]
    assert not {"test", "test_interface", "base_request_id", "pytest"} & data.keys()
    assert all(text not in plan.payload_json for text in (SOURCE, AFTER, POLICY))
    data.pop("plan_id")
    assert plan.plan_id == "repository-http-verification-plan-" + identity(data)
    assert_inert(plan.to_dict())
    with pytest.raises(FrozenInstanceError):
        plan.payload_json = "{}"


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_valid_nonchange_needs_no_case_document_and_never_prepares_a_plan(status):
    request, response, cases = inputs()
    response.update(status=status, proposal=None)
    assert build_repository_http_verification_plan(request, response, None) is None
    assert build_repository_http_verification_plan(request, response, cases) is None
    response["request_id"] = "wrong-request"
    with pytest.raises(ContractError):
        build_repository_http_verification_plan(request, response, None)


def test_proposed_change_requires_a_valid_independent_case_document():
    request, response, cases = inputs()
    for candidate in (None, {}, cases.to_dict()):
        with pytest.raises(ContractError):
            build_repository_http_verification_plan(request, response, candidate)


@pytest.mark.parametrize("field", ["path", "header", "missing-header"])
def test_model_poc_must_match_the_designated_request_without_inventing_labels(field):
    request, response, cases = inputs()
    baseline = cases.payload_json
    if field == "path":
        response["proposal"]["poc"]["path"] = "/items/not-reviewed"
    elif field == "header":
        response["proposal"]["poc"]["headers"][0]["value"] = "test-unreviewed"
    else:
        response["proposal"]["poc"]["headers"] = []
    with pytest.raises(ContractError, match="not covered") as error:
        build_repository_http_verification_plan(request, response, cases)
    assert error.value.code == "validation-evidence"
    assert cases.payload_json == baseline


def test_header_array_order_normalizes_for_coverage_but_full_response_identity_still_changes():
    request, response, _ = inputs()
    data = case_data(request)
    data["cases"][1]["request"]["headers"]["x-role"] = "test-reader"
    cases = build_repository_http_cases(data)
    response["proposal"]["poc"]["headers"].append({"name": "x-role", "value": "test-reader"})
    first = build_repository_http_verification_plan(request, response, cases)
    reverse = deepcopy(response)
    reverse["proposal"]["poc"]["headers"].reverse()
    second = build_repository_http_verification_plan(request, reverse, cases)
    assert first.to_dict()["poc_request"] == second.to_dict()["poc_request"]
    assert first.to_dict()["poc_sha256"] != second.to_dict()["poc_sha256"]
    assert first.plan_id != second.plan_id


def test_duplicate_model_header_is_rejected_before_normalization_can_hide_it():
    request, response, cases = inputs()
    response["proposal"]["poc"]["headers"] *= 2
    with pytest.raises(ContractError):
        build_repository_http_verification_plan(request, response, cases)


@pytest.mark.parametrize(
    "field", ["model", "interface", "after", "rationale", "assumption", "case-author", "case-value"]
)
def test_old_plan_cannot_match_changed_current_data_even_when_new_inputs_are_valid(field):
    plan, request, response, cases = plan_inputs()
    if field == "model":
        request, response, cases = inputs(model="another-model")
    elif field == "interface":
        request, response, cases = inputs(app_attribute="another_app")
    elif field == "after":
        response["proposal"]["after_text"] += "# inert changed proposal\n"
    elif field == "rationale":
        response["rationale"] += " Changed."
    elif field == "assumption":
        response["assumptions"].append("A new declared assumption.")
    else:
        data = case_data(request)
        if field == "case-author":
            data["authorship"] += " Revised."
        else:
            data["cases"][0]["after"]["body"]["value"]["id"] = "changed"
        cases = build_repository_http_cases(data)
    with pytest.raises(ContractError):
        validate_repository_http_verification_plan(plan, request, response, cases)
    assert plan.plan_id != build_repository_http_verification_plan(request, response, cases).plan_id


@pytest.mark.parametrize(
    "field",
    [
        "selection_id",
        "interface_id",
        "source_path",
        "source_sha256",
        "policy_path",
        "policy_sha256",
    ],
)
def test_case_basis_is_checked_against_current_capture_and_interface(field):
    request, response, _ = inputs()
    data = case_data(request)
    data["basis"][field] = (
        "other.py"
        if field == "source_path"
        else "other.md"
        if field == "policy_path"
        else "repository-http-interface-" + "f" * 64
        if field == "interface_id"
        else "f" * 64
    )
    cases = build_repository_http_cases(data)
    with pytest.raises(ContractError, match="current input/interface"):
        build_repository_http_verification_plan(request, response, cases)


@pytest.mark.parametrize(
    "field", ["source", "poc_sha256", "case_set", "http_interface", "verified_fix"]
)
def test_rehashing_supplied_plan_cannot_change_current_correspondence(field):
    plan, request, response, cases = plan_inputs()
    data = plan.to_dict()
    if field == "source":
        data[field]["after_sha256"] = "f" * 64
    elif field == "case_set":
        data[field]["authorship"] = "Forged reviewer."
    elif field == "http_interface":
        data[field]["app_attribute"] = "different"
    elif field == "verified_fix":
        data[field] = True
    else:
        data[field] = "f" * 64
    data.pop("plan_id")
    data["plan_id"] = "repository-http-verification-plan-" + identity(data)
    with pytest.raises(ContractError):
        validate_repository_http_verification_plan(
            RepositoryHttpVerificationPlan(canonical(data)), request, response, cases
        )


def test_new_plan_and_phase_candidate_cannot_be_adopted_as_old_test_interface_types():
    plan, request, response, cases = args = plan_inputs()
    with pytest.raises(ContractError):
        validate_repository_verification_plan(plan, request, response, cases)
    with pytest.raises(ContractError):
        validate_repository_http_verification_plan(
            RepositoryVerificationPlan(plan.payload_json), request, response, cases
        )
    frame = phase_frame(plan, "before")
    candidate = decode_repository_http_phase_candidate(canonical(frame), *args, phase="before")
    with pytest.raises(ContractError):
        validate_repository_http_phase_candidate(
            RepositoryPhaseCandidate(candidate.payload_json), *args, phase="before"
        )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_schedule_contains_the_complete_request_denominator_and_no_oracle_or_code(phase):
    plan, request, response, cases = args = plan_inputs()
    schedule = prepare_repository_http_observer_schedule(*args, phase=phase)
    assert set(schedule) == {"schema_version", "kind", "plan_id", "phase", "requests"}
    assert schedule["schema_version"] == "2.0"
    assert schedule["kind"] == "repository-http-observer-schedule"
    assert schedule["plan_id"] == plan.plan_id
    assert schedule["phase"] == phase
    assert len(schedule["requests"]) == len(cases.to_dict()["cases"]) == 5
    assert [row["case_id"] for row in schedule["requests"]] == [
        row["id"] for row in cases.to_dict()["cases"]
    ]
    assert all(set(row) == {"case_id", "method", "path", "headers"} for row in schedule["requests"])
    assert "HOST_ONLY_EXPECTATION" not in request.payload_json
    assert "HOST_ONLY_EXPECTATION" not in canonical(schedule)
    assert "HOST_ONLY_EXPECTATION" in plan.payload_json
    assert all(text not in canonical(schedule) for text in (SOURCE, AFTER, POLICY, "authorship"))
    schedule["requests"][0]["path"] = "/changed"
    assert (
        prepare_repository_http_observer_schedule(*args, phase=phase)["requests"][0]["path"]
        != "/changed"
    )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_all_matching_supplied_observations_remain_not_run_and_unverified(phase):
    args = plan_inputs()
    frame = phase_frame(args[0], phase)
    result = compare(frame, args, phase)
    assert result["counts"] == counts(match=5)
    assert result["supplied_criteria_met"] is True
    assert result["planned_cases"] == len(result["outcomes"]) == 5
    assert not {"pytest", "auxiliary_pytest_criteria_met", "test_sha256"} & result.keys()
    assert_inert(result)
    assert "MUST NEVER EXECUTE" in SOURCE


def test_after_regression_still_exposing_before_data_is_a_mismatch():
    args = plan_inputs()
    frame = phase_frame(args[0], "after")
    frame["observations"][1]["response"] = deepcopy(
        args[0].to_dict()["case_set"]["cases"][1]["before"]
    )
    result = compare(frame, args, "after")
    assert result["counts"] == counts(match=4, mismatch=1)
    assert result["outcomes"][1]["case_id"] == "other"
    assert not result["supplied_criteria_met"]
    assert_inert(result)


@pytest.mark.parametrize("value", [1, 1.0, "true", None, [], {}])
def test_response_comparison_does_not_equate_boolean_integer_float_or_other_json(value):
    args = plan_inputs()
    frame = phase_frame(args[0], "after")
    frame["observations"][4]["response"]["body"]["value"]["ok"] = value
    result = compare(frame, args, "after")
    assert result["counts"] == counts(match=4, mismatch=1)
    assert not result["supplied_criteria_met"]


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("guest", ["A", "B"])
@pytest.mark.parametrize("cleanup", ["unknown", "failed"])
def test_uncertain_or_failed_cleanup_keeps_complete_case_data_but_prevents_criteria(
    phase, guest, cleanup
):
    args = plan_inputs()
    frame = phase_frame(args[0], phase)
    frame["cleanup"][guest] = cleanup
    result = compare(frame, args, phase)
    assert result["counts"] == counts(match=5)
    assert result["cleanup_supplied_confirmed"] is result["supplied_criteria_met"] is False
    assert_inert(result)


@pytest.mark.parametrize("status", [301, 307, 500, 503])
def test_redirects_and_server_errors_are_not_authorization_reproduction(status):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    frame["observations"][1]["response"]["status"] = status
    result = compare(frame, args)
    assert result["counts"] == counts(match=4, error=1)
    assert result["outcomes"][1]["reason"] == "non-policy-http-status"
    assert result["supplied_before_differs_from_desired_after"] is False


@pytest.mark.parametrize(
    "code", ["timeout", "http-framing", "body-invalid", "setup-error", "transport-error"]
)
@pytest.mark.parametrize("index", [0, 1, 4], ids=["first", "regression", "last"])
def test_first_transport_error_retains_an_undispatched_suffix_and_full_denominator(code, index):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    abort_suffix(frame, index, code)
    result = compare(frame, args)
    assert result["counts"] == counts(match=index, error=1, undispatched=4 - index)
    assert len(result["outcomes"]) == result["planned_cases"] == 5
    assert not result["supplied_criteria_met"]
    assert_inert(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "foreign",
        "reordered",
        "empty",
        "extra",
        "phase",
        "binding",
        "plan",
        "old-kind",
        "pytest",
        "T-cleanup",
    ],
)
def test_malformed_or_old_mode_frames_invalidate_every_planned_case(mutation):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    if mutation == "missing":
        frame["observations"].pop()
    elif mutation == "duplicate":
        frame["observations"][1]["case_id"] = "owner"
    elif mutation == "foreign":
        frame["observations"][1]["case_id"] = "missing"
    elif mutation == "reordered":
        frame["observations"].reverse()
    elif mutation == "empty":
        frame["observations"] = []
    elif mutation == "extra":
        frame["observations"].append(deepcopy(frame["observations"][0]))
    elif mutation == "phase":
        frame["phase"] = "after"
    elif mutation == "binding":
        frame["binding"]["case_set_id"] = "repository-http-case-set-" + "f" * 64
    elif mutation == "plan":
        frame["plan_id"] = "repository-verification-plan-" + "f" * 64
    elif mutation == "old-kind":
        frame["kind"] = "repository-supplied-phase"
    elif mutation == "pytest":
        frame["pytest"] = {"passed": 1}
    else:
        frame["cleanup"]["T"] = "confirmed"
    result = compare(frame, args)
    assert result["frame_status"] == "invalid-supplied"
    assert result["counts"] == counts(invalid=5)
    assert len(result["outcomes"]) == result["planned_cases"] == 5
    assert not result["supplied_criteria_met"]
    assert_inert(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "response-after-error",
        "second-error",
        "wrong-suffix-code",
        "suffix-response",
        "unprompted-suffix",
    ],
)
def test_aborted_phase_cannot_resume_dispatch_or_hide_planned_suffix(mutation):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    abort_suffix(frame, 1)
    row = frame["observations"][2]
    if mutation == "response-after-error":
        row.update(
            outcome="response",
            response=deepcopy(frame["observations"][0]["response"]),
            error_code=None,
        )
    elif mutation == "second-error":
        row.update(outcome="error", error_code="timeout")
    elif mutation == "wrong-suffix-code":
        row["error_code"] = "timeout"
    elif mutation == "suffix-response":
        row["response"] = deepcopy(frame["observations"][0]["response"])
    else:
        frame["observations"][1].update(
            outcome="response",
            response=deepcopy(frame["observations"][0]["response"]),
            error_code=None,
        )
    assert compare(frame, args)["counts"] == counts(invalid=5)


@pytest.mark.parametrize("cleanup", [True, False, None, "verified", 1])
def test_cleanup_is_closed_three_state_data_not_a_boolean_or_authority_token(cleanup):
    args = plan_inputs()
    frame = phase_frame(args[0], "after")
    frame["cleanup"]["A"] = cleanup
    assert compare(frame, args, "after")["counts"] == counts(invalid=5)


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("PRIVATE_FAKE_INVALID_JSON", id="bad-json"),
        pytest.param("{}", id="empty-object"),
        pytest.param("[]", id="array"),
        pytest.param("null", id="null"),
        pytest.param(" " * 65537, id="over-budget"),
    ],
)
def test_invalid_raw_input_is_redacted_and_keeps_all_cases(raw):
    args = plan_inputs()
    result = compare_repository_http_phase(raw, *args, phase="before")
    assert result["counts"] == counts(invalid=5)
    assert "PRIVATE_FAKE" not in canonical(result)
    assert_inert(result)


def test_duplicate_and_nonfinite_raw_json_cannot_become_typed_evidence():
    args = plan_inputs()
    raw = canonical(phase_frame(args[0], "before"))
    for bad in (
        raw.replace('"status":200', '"status":200,"status":200', 1),
        raw.replace('"status":200', '"status":NaN', 1),
    ):
        assert compare_repository_http_phase(bad, *args, phase="before")["counts"] == counts(
            invalid=5
        )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_supplied_candidate_revalidates_flags_without_promoting_saved_json(phase):
    args = plan_inputs()
    candidate = decode_repository_http_phase_candidate(
        canonical(phase_frame(args[0], phase)), *args, phase=phase
    )
    assert validate_repository_http_phase_candidate(candidate, *args, phase=phase) == candidate
    assert_inert(candidate.to_dict())
    payload = candidate.to_dict()
    payload["frame"]["cleanup"]["A"] = "failed"
    assert candidate.to_dict()["frame"]["cleanup"]["A"] == "confirmed"
    payload = candidate.to_dict()
    payload["verified_fix"] = True
    with pytest.raises(ContractError):
        validate_repository_http_phase_candidate(
            RepositoryHttpPhaseCandidate(canonical(payload)), *args, phase=phase
        )
    with pytest.raises(FrozenInstanceError):
        candidate.payload_json = "{}"
    assert not any(hasattr(candidate, name) for name in ("apply", "execute", "approve", "resume"))


def test_bad_current_plan_is_not_swallowed_as_a_bad_observation():
    args = plan_inputs()
    with pytest.raises(ContractError):
        compare_repository_http_phase(
            "not-json", RepositoryHttpVerificationPlan("{}"), *args[1:], phase="before"
        )
