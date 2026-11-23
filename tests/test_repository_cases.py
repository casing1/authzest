"""Pure supplied cases are bounded data, not human approval or executed evidence."""

import builtins
import io
import os
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner.repository_cases import (
    MAX_JSON_INTEGER,
    RepositoryCaseSet,
    build_repository_cases,
    validate_repository_cases,
    validate_repository_response_value,
)


def response(status=200, value=None, *, empty=False):
    return {
        "status": status,
        "body": {"kind": "empty"} if empty else {"kind": "json", "value": value},
    }


def data():
    cases = [
        {
            "id": name,
            "request": {
                "method": "GET",
                "path": "/items/one" if name != "normal" else "/items/two",
                "headers": {} if name == "anonymous" else {"x-user": "test-" + name},
            },
            "before": response(200, {"id": "one"}),
            "after": response(200, {"id": "one"}),
        }
        for name in ("owner", "other", "anonymous", "normal")
    ]
    cases[1]["after"] = response(403, {"detail": "denied"})
    cases[2]["before"] = cases[2]["after"] = response(401, {"detail": "login"})
    return {
        "schema_version": "1.0",
        "kind": "repository-independent-cases",
        "basis": {
            "selection_id": "0" * 64,
            "interface_id": "repository-test-interface-" + "1" * 64,
            "source_path": "main.py",
            "source_sha256": "2" * 64,
            "policy_path": "policy.md",
            "policy_sha256": "3" * 64,
        },
        "authorship": "Owned assistant-authored synthetic test declarations.",
        "assumptions": ["Synthetic identity headers and in-memory data only."],
        "regression_case_id": "other",
        "regression_reason": "A non-owner read must be denied under the supplied intent.",
        "coverage": {
            "owner": {"case_ids": ["owner"], "not_applicable_reason": None},
            "non-owner": {"case_ids": ["other"], "not_applicable_reason": None},
            "anonymous": {"case_ids": ["anonymous"], "not_applicable_reason": None},
            "normal-use": {"case_ids": ["normal"], "not_applicable_reason": None},
            "public": {"case_ids": [], "not_applicable_reason": "No declared public resource."},
        },
        "cases": cases,
    }


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Case codec attempted filesystem, network, process or code execution")

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


def test_round_trip_identity_frozen_and_detached_declarations():
    source = data()
    cases = build_repository_cases(source)
    checked = validate_repository_cases(cases)
    assert checked == cases
    payload = cases.to_dict()
    supplied_id = payload.pop("case_set_id")
    assert supplied_id == "repository-case-set-" + identity(source)
    assert payload == source
    source["cases"][0]["after"]["body"]["value"]["id"] = "later edit"
    payload["coverage"]["owner"]["case_ids"].append("forged")
    assert cases.to_dict()["cases"][0]["after"]["body"]["value"] == {"id": "one"}
    assert cases.to_dict()["coverage"]["owner"]["case_ids"] == ["owner"]
    with pytest.raises(FrozenInstanceError):
        cases.payload_json = "{}"
    assert not any(hasattr(cases, name) for name in ("approve", "apply", "execute", "open"))


def test_authorship_and_applicability_are_data_not_review_or_source_provenance():
    supplied = data()
    supplied["authorship"] = "Claimed author, not authenticated."
    supplied["basis"]["selection_id"] = "f" * 64
    supplied["coverage"]["owner"] = {
        "case_ids": [],
        "not_applicable_reason": "Declared public app.",
    }
    supplied["coverage"]["public"] = {"case_ids": ["owner"], "not_applicable_reason": None}
    result = validate_repository_cases(build_repository_cases(supplied)).to_dict()
    assert result["authorship"] == supplied["authorship"]
    assert result["basis"]["selection_id"] == "f" * 64
    assert not {"approved", "verified", "live", "execution_status", "authorization_status"} & set(
        result
    )


@pytest.mark.parametrize(
    "extra", ["approved", "reviewed", "execution_status", "runtime", "setup", "case_set_id"]
)
def test_unknown_authority_setup_or_identity_fields_are_rejected(extra):
    supplied = data()
    supplied[extra] = True
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


@pytest.mark.parametrize(
    "missing",
    [
        "schema_version",
        "basis",
        "authorship",
        "assumptions",
        "coverage",
        "regression_reason",
        "regression_case_id",
    ],
)
def test_missing_required_case_metadata_is_rejected(missing):
    supplied = data()
    del supplied[missing]
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "1.1"),
        ("schema_version", True),
        ("kind", "verified-cases"),
        ("authorship", " "),
        ("authorship", "x" * 257),
        ("authorship", "bad\0text"),
        ("assumptions", []),
        ("assumptions", [""]),
        ("assumptions", ["x"] * 17),
        ("regression_reason", ""),
        ("regression_case_id", "missing"),
    ],
)
def test_invalid_metadata_and_versions(key, value):
    supplied = data()
    supplied[key] = value
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


@pytest.mark.parametrize(
    "key,value",
    [
        ("selection_id", "f" * 63),
        ("source_sha256", "A" * 64),
        ("policy_sha256", True),
        ("interface_id", "other-" + "0" * 64),
        ("interface_id", "repository-test-interface-" + "g" * 64),
        pytest.param(
            "interface_id",
            "repository-test-interface-" + "0" * 10_000,
            id="oversize-interface-id",
        ),
        ("source_path", "../main.py"),
        ("source_path", "/main.py"),
        ("policy_path", ".env"),
        ("policy_path", "policy.py"),
    ],
)
def test_invalid_basis_shapes(key, value):
    supplied = data()
    supplied["basis"][key] = value
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


def test_four_and_eight_case_bounds_and_repeated_identifiers():
    supplied = data()
    supplied["cases"] = supplied["cases"][:3]
    with pytest.raises(ContractError):
        build_repository_cases(supplied)
    supplied = data()
    for index in range(4):
        case = deepcopy(supplied["cases"][0])
        case["id"] = "extra-" + str(index)
        supplied["cases"].append(case)
    assert len(build_repository_cases(supplied).to_dict()["cases"]) == 8
    supplied["cases"].append(deepcopy(supplied["cases"][0]))
    with pytest.raises(ContractError):
        build_repository_cases(supplied)
    supplied = data()
    supplied["cases"][1]["id"] = "owner"
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


@pytest.mark.parametrize(
    "coverage",
    [
        {"case_ids": ["missing"], "not_applicable_reason": None},
        {"case_ids": ["owner", "owner"], "not_applicable_reason": None},
        {"case_ids": ["owner"], "not_applicable_reason": "both statuses are invalid"},
        {"case_ids": [], "not_applicable_reason": None},
        {"case_ids": [], "not_applicable_reason": ""},
        {"case_ids": [], "not_applicable_reason": True},
        {"case_ids": [], "not_applicable_reason": "x", "reviewed": True},
    ],
)
def test_bad_coverage_references_and_applicability(coverage):
    supplied = data()
    supplied["coverage"]["owner"] = coverage
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


def test_normal_use_cannot_be_waived_and_every_role_requires_a_declaration():
    supplied = data()
    supplied["coverage"]["normal-use"] = {"case_ids": [], "not_applicable_reason": "waived"}
    with pytest.raises(ContractError):
        build_repository_cases(supplied)
    supplied = data()
    del supplied["coverage"]["public"]
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


@pytest.mark.parametrize(
    "path",
    [
        "items/one",
        "//host/items",
        "https://host/items",
        "/items//one",
        "/items/../one",
        "/./items",
        "/items/.",
        "/items?x=1",
        "/items#fragment",
        "/%2f",
        "/items\\one",
        "/items\r\nHost:x",
        "/한글",
        "/" + "x" * 512,
    ],
)
def test_nonliteral_or_ambiguous_request_paths_are_rejected(path):
    supplied = data()
    supplied["cases"][0]["request"]["path"] = path
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


@pytest.mark.parametrize("path", ["/", "/health", "/items/A_0-1.v2", "/items/", "/" + "x" * 511])
def test_supported_literal_get_paths(path):
    supplied = data()
    supplied["cases"][0]["request"]["path"] = path
    assert build_repository_cases(supplied).to_dict()["cases"][0]["request"]["path"] == path


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "test-host"},
        {"host": "test-host"},
        {"authorization": "test-token"},
        {"cookie": "test-cookie"},
        {"content-length": "test-1"},
        {"proxy-authorization": "test-token"},
        {"x-user": "real-user"},
        {"X-User": "test-owner"},
        {"x-user": "test-"},
        {"x-user": "test-owner\n"},
        {"x-user": "test-한글"},
        {"x-user": "test-" + "x" * 60},
        {"x-unknown": "test-user"},
    ],
)
def test_only_closed_synthetic_headers_are_accepted(headers):
    supplied = data()
    supplied["cases"][0]["request"]["headers"] = headers
    with pytest.raises(ContractError):
        build_repository_cases(supplied)


def test_header_limits_and_request_unknown_fields():
    supplied = data()
    headers = {name: "test-" + "x" * 59 for name in ("x-user", "x-user-id", "x-role")}
    supplied["cases"][0]["request"]["headers"] = headers
    assert build_repository_cases(supplied).to_dict()["cases"][0]["request"]["headers"] == headers
    for name, value in [("method", "POST"), ("method", True), ("body", "script"), ("regex", ".*")]:
        edited = deepcopy(supplied)
        edited["cases"][0]["request"][name] = value
        with pytest.raises(ContractError):
            build_repository_cases(edited)


@pytest.mark.parametrize("status", [True, 200.0, 199, 300, 302, 500, 599, 600, "200"])
def test_expected_http_status_limits(status):
    with pytest.raises(ContractError):
        validate_repository_response_value(response(status, {}))


@pytest.mark.parametrize("status", [200, 299, 300, 302, 400, 499, 500, 599])
def test_observed_error_statuses_are_recordable_data_only(status):
    assert (
        validate_repository_response_value(response(status, {}), expected=False)["status"] == status
    )


@pytest.mark.parametrize("status", [204, 205, 304])
def test_no_content_statuses_require_empty_body_even_for_observed_data(status):
    with pytest.raises(ContractError, match="empty body"):
        validate_repository_response_value(response(status, None), expected=False)
    assert validate_repository_response_value(
        response(status, empty=True), expected=False
    ) == response(status, empty=True)


@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, 1, 1.0, "", [], {}, [None, True, 1, 1.0, "1"], {"한글": [True, 1, ""]}],
)
def test_strict_json_response_values_are_preserved_and_detached(value):
    original = response(200, value)
    result = validate_repository_response_value(original)
    assert canonical(result) == canonical(original)
    assert result is not original


@pytest.mark.parametrize("before,after", [(True, 1), (False, 0), (1, 1.0), (0, -0.0), ("1", 1)])
def test_designated_mismatch_uses_exact_json_types(before, after):
    supplied = data()
    supplied["cases"][1]["before"] = response(200, before)
    supplied["cases"][1]["after"] = response(200, after)
    assert build_repository_cases(supplied).case_set_id.startswith("repository-case-set-")
    supplied["cases"][1]["after"] = deepcopy(supplied["cases"][1]["before"])
    with pytest.raises(ContractError, match="mismatch"):
        build_repository_cases(supplied)


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        -float("inf"),
        MAX_JSON_INTEGER + 1,
        -MAX_JSON_INTEGER - 1,
        (1, 2),
        {1: "integer key"},
        "\ud800",
        "한" * 342,
        "x" * 1025,
        {"k" * 129: None},
    ],
)
def test_unsupported_json_and_text_ranges(value):
    with pytest.raises(ContractError):
        validate_repository_response_value(response(200, value))


def test_exact_json_byte_depth_and_node_boundaries():
    exact = ["x" * 1024, "x" * 1024, "x" * 1024, "x" * 1011]
    assert len(canonical(exact).encode()) == 4096
    assert validate_repository_response_value(response(200, exact))["body"]["value"] == exact
    exact[-1] += "x"
    with pytest.raises(ContractError):
        validate_repository_response_value(response(200, exact))
    depth = 0
    for _ in range(8):
        depth = [depth]
    validate_repository_response_value(response(200, depth))
    with pytest.raises(ContractError):
        validate_repository_response_value(response(200, [depth]))
    validate_repository_response_value(response(200, [0] * 127))
    with pytest.raises(ContractError):
        validate_repository_response_value(response(200, [0] * 128))
    with pytest.raises(ContractError):
        validate_repository_response_value(response(200, list(range(100_000))))


def test_case_document_budget_cannot_be_bypassed_by_individually_valid_bodies():
    supplied = data()
    for index in range(4):
        case = deepcopy(supplied["cases"][0])
        case["id"] = "extra-" + str(index)
        supplied["cases"].append(case)
    large = ["x" * 1000] * 4
    for case in supplied["cases"]:
        case["before"] = response(200, large)
        case["after"] = response(200, large)
    supplied["cases"][1]["after"]["status"] = 403
    supplied["assumptions"] = ["x" * 1024] * 16
    with pytest.raises(ContractError) as caught:
        build_repository_cases(supplied)
    assert caught.value.code == "validation-budget"


def test_duplicate_raw_json_and_nonfinite_raw_json_are_rejected():
    cases = build_repository_cases(data())
    duplicate = cases.payload_json.replace('"status":200', '"status":200,"status":200', 1)
    with pytest.raises(ContractError):
        validate_repository_cases(RepositoryCaseSet(duplicate))
    nonfinite = cases.payload_json.replace('"status":200', '"status":NaN', 1)
    with pytest.raises(ContractError):
        validate_repository_cases(RepositoryCaseSet(nonfinite))
    with pytest.raises(ContractError):
        RepositoryCaseSet(" " * 65_537).to_dict()


def test_tampering_identity_or_rehashing_missing_coverage_never_skips_validation():
    cases = build_repository_cases(data())
    supplied = cases.to_dict()
    supplied["case_set_id"] = "repository-case-set-" + "f" * 64
    with pytest.raises(ContractError):
        validate_repository_cases(RepositoryCaseSet(canonical(supplied)))
    supplied = cases.to_dict()
    supplied.pop("case_set_id")
    del supplied["coverage"]["anonymous"]
    supplied["case_set_id"] = "repository-case-set-" + identity(supplied)
    with pytest.raises(ContractError):
        validate_repository_cases(RepositoryCaseSet(canonical(supplied)))
    with pytest.raises(ContractError):
        validate_repository_cases(cases.to_dict())
