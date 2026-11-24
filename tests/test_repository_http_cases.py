"""Pure HTTP-oracle declarations; no claimed human approval or target execution."""

import builtins
import io
import os
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner.repository_cases import RepositoryCaseSet, validate_repository_cases
from authzest.runner.repository_http_cases import (
    RepositoryHttpCaseSet,
    build_repository_http_cases,
    validate_repository_http_cases,
)
from helpers.repository_http_verification_data import case_data, inputs, response_value


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP case declarations attempted an external effect")

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


def data():
    request, _, _ = inputs()
    return case_data(request)


def test_new_case_identity_is_exact_frozen_and_detached():
    supplied = data()
    cases = build_repository_http_cases(supplied)
    assert validate_repository_http_cases(cases) == cases
    assert cases.case_set_id == "repository-http-case-set-" + identity(supplied)
    payload = cases.to_dict()
    payload.pop("case_set_id")
    assert payload == supplied
    supplied["cases"][0]["after"]["body"]["value"]["id"] = "later"
    payload["coverage"]["owner"]["case_ids"].append("forged")
    assert cases.to_dict()["cases"][0]["after"]["body"]["value"] == {"id": "one"}
    assert cases.to_dict()["coverage"]["owner"]["case_ids"] == ["owner"]
    with pytest.raises(FrozenInstanceError):
        cases.payload_json = "{}"
    assert not any(hasattr(cases, name) for name in ("execute", "approve", "apply", "resume"))


def test_old_test_interface_case_type_and_new_http_type_are_mutually_closed():
    cases = build_repository_http_cases(data())
    with pytest.raises(ContractError):
        validate_repository_cases(cases)
    with pytest.raises(ContractError):
        validate_repository_http_cases(RepositoryCaseSet(cases.payload_json))
    legacy_shape = cases.to_dict()
    legacy_shape["schema_version"] = "1.0"
    legacy_shape["kind"] = "repository-independent-cases"
    legacy_shape["basis"]["interface_id"] = "repository-test-interface-" + "0" * 64
    legacy_shape["case_set_id"] = "repository-case-set-" + "0" * 64
    with pytest.raises(ContractError):
        validate_repository_http_cases(RepositoryHttpCaseSet(canonical(legacy_shape)))
    with pytest.raises(ContractError):
        validate_repository_http_cases(cases.to_dict())


def test_authorship_and_basis_remain_unverified_supplied_data():
    supplied = data()
    supplied["authorship"] = "Claimed independent reviewer; this is not authenticated."
    supplied["basis"]["selection_id"] = "f" * 64
    payload = build_repository_http_cases(supplied).to_dict()
    assert payload["authorship"] == supplied["authorship"]
    assert payload["basis"]["selection_id"] == "f" * 64
    assert not {"approved", "reviewed", "verified_fix", "live_evidence"} & payload.keys()


@pytest.mark.parametrize("role", ["owner", "non-owner", "normal-use"])
def test_ownership_and_normal_controls_cannot_be_waived(role):
    supplied = data()
    supplied["coverage"][role] = {"case_ids": [], "not_applicable_reason": "Claimed waiver."}
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


@pytest.mark.parametrize("role", ["anonymous", "public"])
def test_optional_coverage_requires_an_explicit_not_applicable_reason(role):
    supplied = data()
    supplied["coverage"][role] = {"case_ids": [], "not_applicable_reason": "Reviewed assumption."}
    assert (
        build_repository_http_cases(supplied).to_dict()["coverage"][role]
        == supplied["coverage"][role]
    )
    supplied["coverage"][role]["not_applicable_reason"] = ""
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


@pytest.mark.parametrize(
    "case",
    ["missing-role", "foreign-case", "duplicate-reference", "both-states", "extra-approval"],
)
def test_coverage_cannot_drop_a_role_or_invent_case_authority(case):
    supplied = data()
    if case == "missing-role":
        del supplied["coverage"]["public"]
    elif case == "foreign-case":
        supplied["coverage"]["owner"]["case_ids"] = ["missing"]
    elif case == "duplicate-reference":
        supplied["coverage"]["owner"]["case_ids"] = ["owner", "owner"]
    elif case == "both-states":
        supplied["coverage"]["owner"]["not_applicable_reason"] = "Also not applicable."
    else:
        supplied["coverage"]["owner"]["approved"] = True
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("interface_id", "repository-test-interface-" + "1" * 64, id="old-interface"),
        pytest.param("interface_id", "repository-http-interface-" + "A" * 64, id="bad-digest"),
        pytest.param("selection_id", True, id="boolean-selection"),
        pytest.param("source_path", "src/app.py", id="nested-source"),
        pytest.param("source_path", "__init__.py", id="package-source"),
        pytest.param("source_path", "class.py", id="keyword-source"),
        pytest.param("source_path", "앱.py", id="non-ascii-source"),
        pytest.param("policy_path", ".env", id="hidden-policy"),
        pytest.param("policy_path", "../policy.md", id="parent-policy"),
        pytest.param("source_sha256", "f" * 63, id="short-source-digest"),
    ],
)
def test_basis_is_http_specific_and_single_file(field, value):
    supplied = data()
    supplied["basis"][field] = value
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


@pytest.mark.parametrize(
    "field", ["approved", "test_interface", "pytest", "runtime", "case_set_id"]
)
def test_extra_execution_and_old_test_fields_are_rejected(field):
    supplied = data()
    supplied[field] = True
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


@pytest.mark.parametrize("case", ["three", "nine", "duplicate", "unknown-regression", "unchanged"])
def test_case_count_identity_and_meaningful_designated_change(case):
    supplied = data()
    if case == "three":
        supplied["cases"] = supplied["cases"][:3]
    elif case == "nine":
        for index in range(4):
            row = deepcopy(supplied["cases"][0])
            row["id"] = "extra-" + str(index)
            supplied["cases"].append(row)
    elif case == "duplicate":
        supplied["cases"][1]["id"] = "owner"
    elif case == "unknown-regression":
        supplied["regression_case_id"] = "missing"
    else:
        supplied["cases"][1]["after"] = deepcopy(supplied["cases"][1]["before"])
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


def test_eight_cases_are_retained_without_changing_required_controls():
    supplied = data()
    for index in range(3):
        row = deepcopy(supplied["cases"][0])
        row["id"] = "extra-" + str(index)
        supplied["cases"].append(row)
    assert len(build_repository_http_cases(supplied).to_dict()["cases"]) == 8


@pytest.mark.parametrize("before,after", [(True, 1), (False, 0), (1, 1.0), (0, -0.0), ("1", 1)])
def test_designated_difference_preserves_json_types(before, after):
    supplied = data()
    supplied["cases"][1]["before"] = response_value(200, before)
    supplied["cases"][1]["after"] = response_value(200, after)
    assert build_repository_http_cases(supplied).case_set_id.startswith("repository-http-case-set-")


@pytest.mark.parametrize(
    "case", ["method", "url", "traversal", "credential", "real-header", "extra-request", "bad-body"]
)
def test_http_requests_and_expected_values_keep_the_existing_bounded_profile(case):
    supplied = data()
    row = supplied["cases"][0]
    if case == "method":
        row["request"]["method"] = "POST"
    elif case == "url":
        row["request"]["path"] = "https://example.invalid/items"
    elif case == "traversal":
        row["request"]["path"] = "/items/../private"
    elif case == "credential":
        row["request"]["headers"] = {"authorization": "test-token"}
    elif case == "real-header":
        row["request"]["headers"] = {"x-user": "real-user"}
    elif case == "extra-request":
        row["request"]["body"] = "script"
    else:
        row["after"] = response_value(200, [0] * 128)
    with pytest.raises(ContractError):
        build_repository_http_cases(supplied)


def test_overall_document_budget_is_not_just_per_body_limits():
    supplied = data()
    for index in range(3):
        row = deepcopy(supplied["cases"][0])
        row["id"] = "extra-" + str(index)
        supplied["cases"].append(row)
    for row in supplied["cases"]:
        row["before"] = response_value(200, ["x" * 1000] * 4)
        row["after"] = response_value(200, ["x" * 1000] * 4)
    supplied["cases"][1]["after"]["status"] = 403
    supplied["assumptions"] = ["x" * 1024] * 16
    with pytest.raises(ContractError) as error:
        build_repository_http_cases(supplied)
    assert error.value.code == "validation-budget"


@pytest.mark.parametrize(
    "case", ["duplicate-json", "nonfinite-json", "forged-id", "rehash-bad-role"]
)
def test_raw_or_rehashed_input_cannot_bypass_validation(case):
    cases = build_repository_http_cases(data())
    raw = cases.payload_json
    if case == "duplicate-json":
        raw = raw.replace('"status":200', '"status":200,"status":200', 1)
    elif case == "nonfinite-json":
        raw = raw.replace('"status":200', '"status":NaN', 1)
    else:
        payload = cases.to_dict()
        payload.pop("case_set_id")
        if case == "rehash-bad-role":
            del payload["coverage"]["anonymous"]
        payload["case_set_id"] = "repository-http-case-set-" + (
            identity(payload) if case == "rehash-bad-role" else "f" * 64
        )
        raw = canonical(payload)
    with pytest.raises(ContractError):
        validate_repository_http_cases(RepositoryHttpCaseSet(raw))
