"""HTTP source-only layout data must never create, execute or authorize files."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest
from tests.helpers.repository_http_verification_data import AFTER, POLICY, SOURCE, inputs

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.repository_copy_plan import RepositoryCopyPlan
from authzest.codex.repository_http_copy_plan import (
    RepositoryHttpCopyPlan,
    prepare_repository_http_copy_plan,
    validate_repository_http_copy_plan,
)
from authzest.codex.repository_proposal import RepositoryProposalRequest
from authzest.runner.repository_cases import RepositoryCaseSet
from authzest.runner.repository_http_cases import RepositoryHttpCaseSet
from authzest.runner.repository_http_verification import build_repository_http_verification_plan
from test_repository_copy_plan import no_effects  # noqa: F401 -- shared no-effects guard


def test_exact_source_only_layout_and_full_http_case_correspondence():
    request, response, cases = inputs()
    plan = prepare_repository_http_copy_plan(request, response, cases)
    data = plan.to_dict()
    expected = [
        ("selected-source", "project/app.py", SOURCE, "app.py"),
        ("policy-snapshot", "evidence/policy.txt", POLICY, "policy.md"),
        ("source-before", "evidence/source.before", SOURCE, "app.py"),
        ("source-after", "evidence/source.after", AFTER, "app.py"),
    ]
    assert data["files"] == [
        {
            "role": role,
            "workspace_path": path,
            "origin_relative_path": origin,
            "utf8_bytes": len(text.encode()),
            "sha256": sha256(text.encode()).hexdigest(),
        }
        for role, path, text, origin in expected
    ]
    verification = build_repository_http_verification_plan(request, response, cases)
    assert data["schema_version"] == data["layout_version"] == "2.0"
    assert data["kind"] == "repository-http-copy-plan"
    assert data["request_id"] == request.request_id
    assert data["request_identity"] == identity(request.to_dict())
    assert data["response_identity"] == identity(response)
    assert data["verification_plan_id"] == verification.plan_id
    assert data["case_set_id"] == cases.case_set_id
    assert data["source_transition"] == {
        "workspace_path": "project/app.py",
        "before_sha256": sha256(SOURCE.encode()).hexdigest(),
        "after_sha256": sha256(AFTER.encode()).hexdigest(),
        "restore_sha256": sha256(SOURCE.encode()).hexdigest(),
    }
    assert data["material_utf8_bytes"] == sum(len(row[2].encode()) for row in expected)
    assert data["journal"]["workspace_path"] == "record.json"
    assert data["journal"]["authority"] == "none"
    assert len(data["diff_identities"]) == 1
    assert data["diff_identities"][0]["path"] == "app.py"
    assert "generated_test" not in data
    assert data["effects"]["workspace"] == "not-created"
    assert data["effects"]["execution"] == "not-run"
    assert data["effects"]["writes_authorized"] is False
    assert data["effects"]["verified_fix"] is False
    assert validate_repository_http_copy_plan(plan, request, response, cases) == plan
    data["files"][0]["sha256"] = "0" * 64
    assert plan.to_dict()["files"][0]["sha256"] != "0" * 64
    with pytest.raises(FrozenInstanceError):
        plan.payload_json = "{}"


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_valid_nonproposal_requires_no_cases_and_creates_no_plan(status):
    request, response, _ = inputs()
    response.update(status=status, proposal=None)
    assert prepare_repository_http_copy_plan(request, response, None) is None


@pytest.mark.parametrize(
    "field",
    [
        "kind",
        "schema_version",
        "layout_version",
        "request_id",
        "request_identity",
        "response_identity",
        "verification_plan_id",
        "case_set_id",
        "files",
        "material_utf8_bytes",
        "material_max_utf8_bytes",
        "source_transition",
        "diff_identities",
        "journal",
        "requirements",
        "effects",
        "plan_id",
    ],
)
def test_every_copy_binding_is_rebuilt_even_if_supplied_plan_hash_is_replaced(field):
    request, response, cases = inputs()
    data = prepare_repository_http_copy_plan(request, response, cases).to_dict()
    data[field] = None
    data["plan_id"] = "repository-http-copy-plan-" + identity(data)
    with pytest.raises(ContractError):
        validate_repository_http_copy_plan(
            RepositoryHttpCopyPlan(canonical(data)), request, response, cases
        )


def test_response_metadata_and_independent_cases_are_not_just_repair_byte_bindings():
    request, response, cases = inputs()
    original = prepare_repository_http_copy_plan(request, response, cases)
    changed = deepcopy(response)
    changed["rationale"] += " New untrusted explanation."
    assert prepare_repository_http_copy_plan(request, changed, cases).plan_id != original.plan_id
    with pytest.raises(ContractError):
        validate_repository_http_copy_plan(original, request, changed, cases)
    data = cases.to_dict()
    data.pop("case_set_id")
    data["authorship"] = "A different supplied declaration, not authenticated review."
    from authzest.runner.repository_http_cases import build_repository_http_cases

    other_cases = build_repository_http_cases(data)
    assert (
        prepare_repository_http_copy_plan(request, response, other_cases).plan_id
        != original.plan_id
    )
    with pytest.raises(ContractError):
        validate_repository_http_copy_plan(original, request, response, other_cases)


@pytest.mark.parametrize("kind", ["old-plan", "dict", "text", "none"])
def test_saved_or_old_copy_objects_are_not_adopted(kind):
    request, response, cases = inputs()
    plan = prepare_repository_http_copy_plan(request, response, cases)
    supplied = {
        "old-plan": RepositoryCopyPlan(plan.payload_json),
        "dict": plan.to_dict(),
        "text": plan.payload_json,
        "none": None,
    }[kind]
    with pytest.raises(ContractError):
        validate_repository_http_copy_plan(supplied, request, response, cases)


def test_old_request_and_test_case_types_cannot_be_silently_converted():
    request, response, cases = inputs()
    with pytest.raises(ContractError):
        prepare_repository_http_copy_plan(
            RepositoryProposalRequest(request.payload_json), response, cases
        )
    with pytest.raises(ContractError):
        prepare_repository_http_copy_plan(request, response, RepositoryCaseSet(cases.payload_json))


def test_uncovered_model_poc_never_produces_a_copy_layout():
    request, response, cases = inputs()
    response["proposal"]["poc"]["path"] = "/items/unreviewed"
    with pytest.raises(ContractError):
        prepare_repository_http_copy_plan(request, response, cases)


def test_corrupt_current_cases_are_refused_instead_of_dropping_the_oracle():
    request, response, cases = inputs()
    data = cases.to_dict()
    data["cases"].pop()
    with pytest.raises(ContractError):
        prepare_repository_http_copy_plan(request, response, RepositoryHttpCaseSet(canonical(data)))
