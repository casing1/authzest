"""Strict supplied-frame refusal with pure owned data, never runtime observations."""

import builtins
import io
import os
import socket
import subprocess
from copy import deepcopy

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.codex.repository_test_interface import RepositoryTestRequest
from authzest.runner.repository_cases import RepositoryCaseSet, build_repository_cases
from authzest.runner.repository_verification import (
    MAX_PHASE_BYTES,
    RepositoryPhaseCandidate,
    build_repository_verification_plan,
    compare_repository_phase,
    decode_repository_phase_candidate,
    validate_repository_phase_candidate,
)
from helpers.repository_verification_data import case_data, phase_frame, plan_inputs


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Supplied-frame codec attempted a filesystem/network/process effect")

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


def assert_invalid_frame(raw, args, phase="before"):
    with pytest.raises(ContractError):
        decode_repository_phase_candidate(raw, *args, phase=phase)
    result = compare_repository_phase(raw, *args, phase=phase)
    expected_ids = [case["id"] for case in args[3].to_dict()["cases"]]
    assert result["frame_status"] == "invalid-supplied"
    assert result["planned_cases"] == len(result["outcomes"]) == len(expected_ids)
    assert [item["case_id"] for item in result["outcomes"]] == expected_ids
    assert result["counts"] == {
        "match": 0,
        "mismatch": 0,
        "error": 0,
        "invalid": len(expected_ids),
    }
    assert result["supplied_criteria_met"] is False
    assert result["auxiliary_pytest_criteria_met"] is False
    assert result["cleanup_supplied_confirmed"] is False
    assert result["verified_fix"] is result["live_evidence"] is False
    assert result["writes_authorized"] is False
    assert result["evidence_basis"] == "supplied-unverified"
    return result


@pytest.mark.parametrize(
    "field", ["collected", "passed", "failed", "errors", "skipped", "xfailed", "xpassed"]
)
@pytest.mark.parametrize("value", [True, 1.0, -1, 129, "1", None])
def test_pytest_counts_have_exact_integer_type_and_closed_range(field, value):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    frame["pytest"][field] = value
    assert_invalid_frame(canonical(frame), args)


@pytest.mark.parametrize("value", [True, 0.0, -1, 6, "1", {}, []])
def test_supplied_pytest_exit_status_does_not_coerce_types_or_unknown_codes(value):
    args = plan_inputs()
    frame = phase_frame(args[0], "after")
    frame["pytest"]["exit_code"] = value
    assert_invalid_frame(canonical(frame), args, "after")


@pytest.mark.parametrize("phase", ["before", "after"])
def test_exact_upper_count_bound_is_only_supplied_consistency_not_execution(phase):
    args = plan_inputs()
    frame = phase_frame(args[0], phase)
    frame["pytest"].update(collected=128, passed=127 if phase == "before" else 128)
    result = compare_repository_phase(canonical(frame), *args, phase=phase)
    assert result["supplied_criteria_met"] is True
    assert result["verified_fix"] is result["live_evidence"] is False
    assert result["execution_status"] == "not-run"


@pytest.mark.parametrize(
    "phase,changes",
    [
        ("before", {"failure_kind": "other"}),
        ("before", {"failure_kind": "none"}),
        ("before", {"collected": 0, "failed": 0}),
        ("before", {"passed": 1}),
        ("before", {"collected": 2}),
        ("before", {"exit_code": None}),
        ("before", {"exit_code": 0}),
        ("before", {"errors": 1}),
        ("before", {"skipped": 1}),
        ("before", {"xfailed": 1}),
        ("before", {"xpassed": 1}),
        ("after", {"failure_kind": "assertion"}),
        ("after", {"failure_kind": "other"}),
        ("after", {"collected": 0, "passed": 0}),
        ("after", {"collected": 2}),
        ("after", {"failed": 1}),
        ("after", {"exit_code": None}),
        ("after", {"exit_code": 1}),
        ("after", {"errors": 1}),
        ("after", {"skipped": 1}),
        ("after", {"xfailed": 1}),
        ("after", {"xpassed": 1}),
    ],
)
def test_valid_supplied_counts_or_failure_labels_cannot_hide_auxiliary_failure(phase, changes):
    args = plan_inputs()
    frame = phase_frame(args[0], phase)
    frame["pytest"].update(changes)
    # An ordinary failed test may be RuntimeError rather than AssertionError;
    # neither its count nor a caller's failure label authenticates the cause.
    decode_repository_phase_candidate(canonical(frame), *args, phase=phase)
    result = compare_repository_phase(canonical(frame), *args, phase=phase)
    assert result["frame_status"] == "valid-supplied"
    assert result["counts"]["match"] == result["planned_cases"] == 5
    assert result["cleanup_supplied_confirmed"] is True
    assert result["auxiliary_pytest_criteria_met"] is False
    assert result["supplied_criteria_met"] is result["verified_fix"] is False


@pytest.mark.parametrize(
    "section", ["frame", "pytest", "cleanup", "binding", "observation", "response", "body"]
)
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_every_frame_layer_has_a_closed_required_field_set(section, mutation):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    objects = {
        "frame": frame,
        "pytest": frame["pytest"],
        "cleanup": frame["cleanup"],
        "binding": frame["binding"],
        "observation": frame["observations"][0],
        "response": frame["observations"][0]["response"],
        "body": frame["observations"][0]["response"]["body"],
    }
    target = objects[section]
    if mutation == "missing":
        target.pop(next(iter(target)))
    else:
        target["PRIVATE_UNKNOWN_FIELD"] = "not an approval"
    result = assert_invalid_frame(canonical(frame), args)
    assert "PRIVATE_UNKNOWN_FIELD" not in canonical(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "response-and-error",
        "error-and-response",
        "error-without-code",
        "unknown-error",
        "response-null",
        "unknown-outcome",
    ],
)
def test_observation_response_error_arms_are_mutually_exclusive(mutation):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    item = frame["observations"][0]
    if mutation == "response-and-error":
        item["error_code"] = "timeout"
    elif mutation == "error-and-response":
        item.update(outcome="error", error_code="timeout")
    elif mutation == "error-without-code":
        item.update(outcome="error", response=None)
    elif mutation == "unknown-error":
        item.update(outcome="error", response=None, error_code="PRIVATE_UNSUPPORTED_ERROR")
    elif mutation == "response-null":
        item["response"] = None
    else:
        item["outcome"] = "PRIVATE_UNSUPPORTED_OUTCOME"
    result = assert_invalid_frame(canonical(frame), args)
    assert "PRIVATE_UNSUPPORTED" not in canonical(result)


@pytest.mark.parametrize("raw_value", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_nonfinite_values_inside_response_json_invalidate_the_whole_frame(raw_value):
    args = plan_inputs()
    raw = canonical(phase_frame(args[0], "before"))
    assert '"ok":true' in raw
    raw = raw.replace('"ok":true', '"ok":' + raw_value, 1)
    assert_invalid_frame(raw, args)


@pytest.mark.parametrize("scope", ["frame", "binding", "pytest", "response-json"])
def test_duplicate_raw_keys_at_nested_levels_never_become_last_value_wins(scope):
    args = plan_inputs()
    frame = phase_frame(args[0], "before")
    raw = canonical(frame)
    if scope == "frame":
        needle = '"phase":"before"'
        duplicate = needle + "," + needle
    elif scope == "binding":
        needle = '"test_sha256":' + canonical(frame["binding"]["test_sha256"])
        duplicate = needle + "," + needle
    elif scope == "pytest":
        needle = '"collected":1'
        duplicate = needle + "," + needle
    else:
        needle = '"ok":true'
        duplicate = '"ok":false,' + needle
    assert needle in raw
    assert_invalid_frame(raw.replace(needle, duplicate, 1), args)


def test_exact_raw_phase_byte_boundary_and_utf8_budget_use_bytes_not_characters():
    args = plan_inputs()
    raw = canonical(phase_frame(args[0], "before"))
    exact = raw + " " * (MAX_PHASE_BYTES - len(raw.encode()))
    assert len(exact.encode()) == MAX_PHASE_BYTES
    assert compare_repository_phase(exact, *args, phase="before")["supplied_criteria_met"] is True
    result = assert_invalid_frame(exact + " ", args)
    assert all(item["reason"] == "validation-budget" for item in result["outcomes"])
    frame = phase_frame(args[0], "before")
    frame["observations"][-1]["response"]["body"]["value"] = {"ok": "é"}
    encoded = canonical(frame)
    character_bound = encoded + " " * (MAX_PHASE_BYTES - len(encoded))
    assert len(character_bound) == MAX_PHASE_BYTES < len(character_bound.encode())
    result = assert_invalid_frame(character_bound, args)
    assert result["counts"]["invalid"] == 5


@pytest.mark.parametrize("phase", [None, True, [], "BEFORE", "later"])
def test_invalid_explicit_phase_is_not_downgraded_to_bad_observation_data(phase):
    args = plan_inputs()
    with pytest.raises(ContractError):
        compare_repository_phase("not-json", *args, phase=phase)


@pytest.mark.parametrize("changed", ["request", "response", "cases"])
def test_invalid_current_inputs_are_not_masked_by_malformed_frame_fallback(changed):
    plan, request, response, cases = plan_inputs()
    if changed == "request":
        data = request.to_dict()
        data["host_instructions"] += " tampered"
        request = RepositoryTestRequest(canonical(data))
    elif changed == "response":
        response = deepcopy(response)
        response["request_id"] = "not-current"
    else:
        data = cases.to_dict()
        data["cases"][0]["request"]["path"] = "/changed"
        cases = RepositoryCaseSet(canonical(data))
    with pytest.raises(ContractError):
        compare_repository_phase("not-json", plan, request, response, cases, phase="before")


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("field", ["source_sha256", "test_sha256", "interface_id"])
def test_candidate_nested_binding_corruption_cannot_be_promoted_by_outer_metadata(phase, field):
    args = plan_inputs()
    candidate = decode_repository_phase_candidate(
        canonical(phase_frame(args[0], phase)), *args, phase=phase
    )
    data = candidate.to_dict()
    data["frame"]["binding"][field] = (
        "repository-test-interface-" + "f" * 64 if field == "interface_id" else "f" * 64
    )
    with pytest.raises(ContractError):
        validate_repository_phase_candidate(
            RepositoryPhaseCandidate(canonical(data)), *args, phase=phase
        )


def test_integer_and_float_responses_remain_distinct_below_other_json_containers():
    _, request, response, _ = plan_inputs()
    data = case_data(request)
    data["cases"][0]["before"]["body"]["value"] = {"nested": [{"count": 1}]}
    data["cases"][0]["after"]["body"]["value"] = {"nested": [{"count": 1}]}
    cases = build_repository_cases(data)
    plan = build_repository_verification_plan(request, response, cases)
    frame = phase_frame(plan, "after")
    frame["observations"][0]["response"]["body"]["value"] = {"nested": [{"count": 1.0}]}
    result = compare_repository_phase(
        canonical(frame), plan, request, response, cases, phase="after"
    )
    assert result["frame_status"] == "valid-supplied"
    assert result["counts"] == {"match": 4, "mismatch": 1, "error": 0, "invalid": 0}
    assert result["supplied_criteria_met"] is result["verified_fix"] is False
