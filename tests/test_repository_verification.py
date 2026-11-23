"""Pure offline comparisons of owned supplied declarations, not observed execution."""

import builtins
import io
import os
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner.repository_cases import build_repository_cases
from authzest.runner.repository_verification import (
    RepositoryPhaseCandidate,
    RepositoryVerificationPlan,
    build_repository_verification_plan,
    compare_repository_phase,
    decode_repository_phase_candidate,
    prepare_repository_observer_schedule,
    validate_repository_phase_candidate,
    validate_repository_verification_plan,
)
from helpers.repository_verification_data import (
    AFTER,
    SOURCE,
    TEST,
    case_data,
    inputs,
    phase_frame,
    plan_inputs,
)


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Comparison attempted filesystem, network, process or code execution")

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
    return compare_repository_phase(canonical(frame), *args, phase=phase)


def test_plan_binds_current_request_response_context_interface_and_all_materials():
    plan, request, response, cases = args = plan_inputs()
    data = plan.to_dict()
    assert validate_repository_verification_plan(*args) == plan
    assert data["request_identity"] == identity(request.to_dict())
    assert data["proposal_identity"] == identity(response)
    assert data["case_set"] == cases.to_dict()
    assert data["case_set_id"] == cases.case_set_id
    assert data["source"]["before_sha256"] != data["source"]["after_sha256"]
    assert data["test"]["path"].endswith("test_authzest_regression.py")
    assert all(text not in plan.payload_json for text in (SOURCE, AFTER, TEST))
    data.pop("plan_id")
    assert plan.plan_id == "repository-verification-plan-" + identity(data)
    with pytest.raises(FrozenInstanceError):
        plan.payload_json = "{}"


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_nonchange_responses_do_not_prepare_a_verification_plan(status):
    request, response, cases = inputs()
    response.update(status=status, proposal=None)
    assert build_repository_verification_plan(request, response, cases) is None


@pytest.mark.parametrize("field", ["model", "interface", "after", "test", "rationale", "case"])
def test_old_plan_rejected_against_changed_current_inputs_even_with_valid_new_data(field):
    plan, request, response, cases = args = plan_inputs()
    if field == "model":
        request, response, cases = inputs(model="another-offline-model")
    elif field == "interface":
        request, response, cases = inputs(app_attribute="another_app")
    elif field in {"after", "test"}:
        response["proposal"][field + "_text"] += "# changed\n"
    elif field == "rationale":
        response["rationale"] += " Changed."
    else:
        data = case_data(request)
        data["authorship"] += " Revised."
        cases = build_repository_cases(data)
    with pytest.raises(ContractError):
        validate_repository_verification_plan(plan, request, response, cases)
    assert plan.plan_id != build_repository_verification_plan(request, response, cases).plan_id
    assert args[0] is plan


@pytest.mark.parametrize(
    "field",
    [
        "selection_id",
        "interface_id",
        "source_sha256",
        "policy_sha256",
        "source_path",
        "policy_path",
    ],
)
def test_case_basis_must_match_current_capture_and_interface(field):
    request, response, _ = inputs()
    data = case_data(request)
    data["basis"][field] = (
        "other.py"
        if field == "source_path"
        else "other.md"
        if field == "policy_path"
        else "repository-test-interface-" + "f" * 64
        if field == "interface_id"
        else "f" * 64
    )
    cases = build_repository_cases(data)
    with pytest.raises(ContractError, match="current input/interface"):
        build_repository_verification_plan(request, response, cases)


def test_rehashing_tampered_plan_does_not_make_current_inputs_match():
    plan, request, response, cases = plan_inputs()
    data = plan.to_dict()
    data["test"]["sha256"] = "f" * 64
    data.pop("plan_id")
    data["plan_id"] = "repository-verification-plan-" + identity(data)
    with pytest.raises(ContractError):
        validate_repository_verification_plan(
            RepositoryVerificationPlan(canonical(data)), request, response, cases
        )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_model_observer_and_host_projection_keep_independent_answers_separate(phase):
    plan, request, response, cases = args = plan_inputs()
    schedule = prepare_repository_observer_schedule(*args, phase=phase)
    assert set(schedule) == {"kind", "schema_version", "plan_id", "phase", "requests"}
    assert len(schedule["requests"]) == 5
    assert all(
        set(item) == {"case_id", "method", "path", "headers"} for item in schedule["requests"]
    )
    assert "HOST_ONLY_EXPECTATION" not in canonical(schedule)
    assert "HOST_ONLY_EXPECTATION" not in request.payload_json
    assert "HOST_ONLY_EXPECTATION" in plan.payload_json
    assert all(
        t not in canonical(schedule)
        for t in (SOURCE, AFTER, TEST, "regression_reason", "authorship")
    )
    schedule["requests"][0]["path"] = "/forged"
    assert (
        prepare_repository_observer_schedule(*args, phase=phase)["requests"][0]["path"] != "/forged"
    )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_matching_supplied_data_remains_unverified_even_when_all_declared_criteria_match(phase):
    args = plan_inputs()
    frame = phase_frame(args[0], phase)
    result = compare(frame, args, phase)
    assert result["supplied_criteria_met"] is True
    assert result["counts"] == {"match": 5, "mismatch": 0, "error": 0, "invalid": 0}
    assert result["planned_cases"] == len(result["outcomes"]) == 5
    assert result["execution_status"] == "not-run"
    assert result["authorization_status"] == "unknown"
    assert result["evidence_basis"] == "supplied-unverified"
    assert result["verified_fix"] is result["live_evidence"] is result["writes_authorized"] is False
    # The synthetic frame claims an assertion while the inert test would raise RuntimeError.
    # Matching data therefore MUST NOT be accepted as executed test/source evidence.
    assert "RuntimeError" in TEST


def test_a_valid_mismatch_retains_all_cases_and_never_claims_a_fix():
    args = plan_inputs()
    frame = phase_frame(args[0], "after")
    frame["observations"][1]["response"] = deepcopy(
        args[0].to_dict()["case_set"]["cases"][1]["before"]
    )
    result = compare(frame, args, "after")
    assert result["counts"] == {"match": 4, "mismatch": 1, "error": 0, "invalid": 0}
    assert result["supplied_criteria_met"] is False
    assert result["outcomes"][1]["case_id"] == "other"


@pytest.mark.parametrize("value", [1, 1.0, "true", None, [], {}])
def test_strict_json_does_not_equate_true_with_integer_float_string_or_null(value):
    args = plan_inputs()
    frame = phase_frame(args[0], "after")
    frame["observations"][4]["response"]["body"]["value"]["ok"] = value
    result = compare(frame, args, "after")
    assert result["counts"]["mismatch"] == 1
    assert result["supplied_criteria_met"] is False


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("guest", ["T", "A", "B"])
@pytest.mark.parametrize("cleanup", ["unknown", "failed"])
def test_supplied_unknown_or_failed_cleanup_always_prevents_criteria(phase, guest, cleanup):
    args = plan_inputs()
    frame = phase_frame(args[0], phase)
    frame["cleanup"][guest] = cleanup
    result = compare(frame, args, phase)
    assert result["counts"]["match"] == 5
    assert result["cleanup_supplied_confirmed"] is result["supplied_criteria_met"] is False


@pytest.mark.parametrize("status", [301, 307, 500, 503])
def test_redirect_or_server_error_is_an_error_not_an_authorization_mismatch(status):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    frame["observations"][1]["response"]["status"] = status
    result = compare(frame, args)
    assert result["counts"]["error"] == 1
    assert result["outcomes"][1]["reason"] == "non-policy-http-status"
    assert result["supplied_criteria_met"] is False


@pytest.mark.parametrize(
    "code", ["timeout", "http-framing", "body-invalid", "setup-error", "transport-error"]
)
def test_transport_failures_are_recorded_without_losing_planned_denominator(code):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    frame["observations"][1].update(outcome="error", response=None, error_code=code)
    result = compare(frame, args)
    assert result["counts"] == {"match": 4, "mismatch": 0, "error": 1, "invalid": 0}
    assert len(result["outcomes"]) == result["planned_cases"] == 5
    assert result["supplied_before_differs_from_desired_after"] is False


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "unknown", "reordered", "empty", "extra", "phase", "binding", "plan"],
)
def test_malformed_or_mismatched_frames_make_every_planned_case_invalid(mutation):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    if mutation == "missing":
        frame["observations"].pop()
    elif mutation == "duplicate":
        frame["observations"][1]["case_id"] = "owner"
    elif mutation == "unknown":
        frame["observations"][1]["case_id"] = "unknown"
    elif mutation == "reordered":
        frame["observations"].reverse()
    elif mutation == "empty":
        frame["observations"] = []
    elif mutation == "extra":
        frame["observations"].append(deepcopy(frame["observations"][0]))
    elif mutation == "phase":
        frame["phase"] = "after"
    elif mutation == "binding":
        frame["binding"]["source_sha256"] = "f" * 64
    else:
        frame["plan_id"] = "wrong-plan"
    result = compare(frame, args)
    assert result["frame_status"] == "invalid-supplied"
    assert result["counts"] == {"match": 0, "mismatch": 0, "error": 0, "invalid": 5}
    assert result["planned_cases"] == len(result["outcomes"]) == 5
    assert result["supplied_criteria_met"] is False


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("not-json-private-sentinel", id="malformed-json"),
        pytest.param("{}", id="empty-object"),
        pytest.param("[]", id="array"),
        pytest.param("null", id="null"),
        pytest.param('"secret"', id="string"),
        # pytest exports node IDs in PYTEST_CURRENT_TEST; keep large inputs out of it
        # so the full byte-budget check can also run within Windows' environment limit.
        pytest.param(" " * 65537, id="over-byte-budget"),
    ],
)
def test_invalid_json_shape_and_byte_budget_are_redacted_and_preserve_all_cases(raw):
    args = plan_inputs()
    result = compare_repository_phase(raw, *args, phase="before")
    assert result["counts"]["invalid"] == 5 and not result["supplied_criteria_met"]
    assert "not-json-private-sentinel" not in canonical(result)
    assert '"secret"' not in canonical(result)
    assert all(
        c["reason"] in {"validation-json", "validation-shape", "validation-budget"}
        for c in result["outcomes"]
    )


def test_invalid_current_plan_is_not_swallowed_as_an_invalid_observation():
    args = plan_inputs()
    bad = RepositoryVerificationPlan("{}")
    with pytest.raises(ContractError):
        compare_repository_phase("not-json", bad, *args[1:], phase="before")


@pytest.mark.parametrize("phase", ["before", "after"])
def test_candidate_is_rebuilt_and_cannot_promote_its_flags_or_import_live_authority(phase):
    args = plan_inputs()
    candidate = decode_repository_phase_candidate(
        canonical(phase_frame(args[0], phase)), *args, phase=phase
    )
    assert validate_repository_phase_candidate(candidate, *args, phase=phase) == candidate
    data = candidate.to_dict()
    data["verified_fix"] = True
    with pytest.raises(ContractError):
        validate_repository_phase_candidate(
            RepositoryPhaseCandidate(canonical(data)), *args, phase=phase
        )
    assert not any(
        hasattr(candidate, name) for name in ("apply", "approve", "execute", "open", "resume")
    )
