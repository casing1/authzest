import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from scripts.evaluate_offline import DATASET_ROOT, prepare_case

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    canonical,
    identity,
    validate_response,
)
from authzest.codex.expectations import (
    EXPECTATION_SCHEMA_VERSION,
    ValidatedExpectationManifest,
    expectation_preview,
    prepare_expectation_manifest,
    validate_expectation_manifest,
)
from authzest.codex.mock import MockCodexAdapter, scripted_response
from authzest.codex.proposals import ValidatedProposal, content_hash, prepare_proposal

# Explicit caller-authored targets, not evaluation labels or generated test results.
TARGETS = {
    "public": ("policy-intent", {"intent": "public"}),
    "ordinary-di": ("dependency-declarations", {"count": 1}),
    "security-scope": ("scope-declarations", {"scopes": ["reports:read"]}),
}


def make_proposal(request, review, suffix="# Caller-authored expectation example.\n"):
    source = next(
        item["data"] for item in request.to_dict()["evidence"] if item["kind"] == "source"
    )
    return prepare_proposal(
        request,
        review,
        replacements={source["path"]: source["text"] + suffix},
        rationale="Link a harmless caller-authored draft to source evidence.",
        uncertainties=("No runtime behavior has been checked.",),
        side_effects=(),
        checks=("fixture-static-inventory",),
        expectations=("Review declaration targets separately from enforcement.",),
    )


def make_context(case_id="public"):
    cases = json.loads((DATASET_ROOT / "dataset.json").read_text(encoding="utf-8"))["cases"]
    case = next(case for case in cases if case["id"] == case_id)
    assert case["split"] == "development"
    _, request = prepare_case(case, "evidence-plus-model")
    review = validate_response(
        scripted_response(request, {question["id"]: None for question in case["questions"]}),
        request,
    )
    evidence = {item["kind"]: item for item in request.to_dict()["evidence"]}
    observation, expected = TARGETS[case_id]
    spec = {
        "id": "review-target",
        "source_evidence_id": evidence["source"]["id"],
        "route_evidence_id": evidence["route"]["id"],
        "policy_evidence_ids": [evidence["policy"]["id"]],
        "observation": observation,
        "expected": json.loads(canonical(expected)),
        "limitations": ["Declarations and caller policy interpretation do not prove enforcement."],
    }
    return request, review, make_proposal(request, review), spec


@pytest.fixture
def context():
    return make_context()


def manifest(context, spec=None):
    request, review, proposal, default_spec = context
    return prepare_expectation_manifest(
        request, review, proposal, expectations=[default_spec if spec is None else spec]
    )


@pytest.mark.parametrize("case_id", TARGETS)
def test_development_targets_round_trip_without_claiming_results(case_id):
    context = make_context(case_id)
    request, review, proposal, spec = context
    artifact = manifest(context)
    assert (
        validate_expectation_manifest(artifact.payload_json, request, review, proposal) == artifact
    )
    payload = artifact.to_dict()
    assert payload["schema_version"] == EXPECTATION_SCHEMA_VERSION == "1.0"
    assert payload["request_id"] == request.request_id
    assert payload["review_id"] == identity(review.to_dict())
    assert payload["proposal_id"] == proposal.proposal_id
    assert payload["source_identity"] == request.to_dict()["source_identity"]
    item = payload["expectations"][0]
    source = next(e["data"] for e in request.to_dict()["evidence"] if e["kind"] == "source")
    route = next(e["data"] for e in request.to_dict()["evidence"] if e["kind"] == "route")
    assert item["path"] == source["path"] == route["file"]
    assert item["baseline_registration_id"] == route["registration_id"]
    assert item["before_sha256"] == content_hash(source["text"])
    assert item["after_sha256"] == content_hash(proposal.to_dict()["changes"][0]["after_text"])
    assert item["expected"] == spec["expected"]
    preview = expectation_preview(artifact, request, review, proposal)
    assert preview["manifest_id"] == "expectation-" + identity(payload)
    assert preview["status"] == "draft" and preview["verification_status"] == "not-run"
    assert preview["observed"] is None and preview["authorization_verdict"] == "unknown"
    assert preview["limitations"] and item["limitations"]
    expected_basis = (
        "caller-policy-interpretation" if case_id == "public" else "source-declaration-target"
    )
    assert preview["expectations"][0]["basis"] == expected_basis
    assert "basis" not in item and "observed" not in payload


def test_immutable_payload_detached_preview_and_canonical_identity(context):
    request, review, proposal, spec = context
    artifact = manifest(context)
    original_id = artifact.manifest_id
    spec["expected"]["intent"] = "restricted"
    artifact.to_dict()["expectations"].clear()
    preview = expectation_preview(artifact, request, review, proposal)
    preview["expectations"][0]["expected"]["intent"] = "restricted"
    assert artifact.manifest_id == original_id
    assert artifact.to_dict()["expectations"][0]["expected"] == {"intent": "public"}
    assert (
        validate_expectation_manifest(
            json.dumps(artifact.to_dict(), indent=2), request, review, proposal
        ).manifest_id
        == original_id
    )
    with pytest.raises(FrozenInstanceError):
        artifact.payload_json = "{}"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "another-target"),
        ("expected", {"intent": "restricted"}),
        ("limitations", ["Different caveat."]),
    ],
)
def test_material_target_changes_change_identity(context, field, value):
    original = manifest(context)
    context[3][field] = value
    assert manifest(context).manifest_id != original.manifest_id


@pytest.mark.parametrize(
    ("case_id", "expected"),
    [
        ("public", {"intent": "restricted"}),
        ("ordinary-di", {"count": 256}),
        ("security-scope", {"scopes": ["future:declaration"]}),
    ],
)
def test_future_targets_are_not_compared_to_baseline_or_promoted_to_truth(case_id, expected):
    context = make_context(case_id)
    context[3]["expected"] = expected
    preview = expectation_preview(manifest(context), *context[:3])
    assert preview["expectations"][0]["expected"] == expected
    assert preview["observed"] is None and preview["authorization_verdict"] == "unknown"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("request_id",), "request-stale"),
        (("review_id",), "0" * 64),
        (("proposal_id",), "proposal-stale"),
        (("source_identity",), "0" * 64),
        (("expectations",), []),
        (("command",), "not supported"),
        (("status",), "approved"),
        (("observed",), "pass"),
        (("expectations", 0, "id"), "Invalid"),
        (("expectations", 0, "id"), "a" * 65),
        (("expectations", 0, "path"), "other.py"),
        (("expectations", 0, "baseline_registration_id"), "route-" + "0" * 64),
        (("expectations", 0, "before_sha256"), "0" * 64),
        (("expectations", 0, "after_sha256"), "0" * 64),
        (("expectations", 0, "source_evidence_id"), "ev-missing"),
        (("expectations", 0, "route_evidence_id"), "ev-missing"),
        (("expectations", 0, "policy_evidence_ids"), []),
        (("expectations", 0, "policy_evidence_ids"), ["ev-missing"]),
        (("expectations", 0, "observation"), "execute-command"),
        (("expectations", 0, "expected"), {"intent": "verified"}),
        (("expectations", 0, "expected"), {"intent": "public", "observed": "pass"}),
        (("expectations", 0, "limitations"), []),
        (("expectations", 0, "limitations"), [" "]),
        (("expectations", 0, "limitations"), ["caveat"] * 17),
        (("expectations", 0, "command"), "not supported"),
        (("expectations", 0, "basis"), "proven-enforcement"),
    ],
)
def test_invalid_manifest_fields_and_bindings_are_rejected(context, path, value):
    data = manifest(context).to_dict()
    target = data
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    with pytest.raises(ContractError):
        validate_expectation_manifest(canonical(data), *context[:3])


@pytest.mark.parametrize(
    "field", ["source_evidence_id", "route_evidence_id", "policy_evidence_ids"]
)
def test_same_request_wrong_kind_references_are_rejected(context, field):
    spec = context[3]
    spec[field] = (
        [spec["source_evidence_id"]]
        if field == "policy_evidence_ids"
        else spec["policy_evidence_ids"][0]
    )
    with pytest.raises(ContractError):
        manifest(context)


@pytest.mark.parametrize(
    "field", ["source_evidence_id", "route_evidence_id", "policy_evidence_ids"]
)
def test_foreign_correct_kind_evidence_is_rejected(context, field):
    context[3][field] = make_context("ordinary-di")[3][field]
    with pytest.raises(ContractError):
        manifest(context)


@pytest.mark.parametrize("mismatch", ["unchanged-source", "other-route-source"])
def test_selected_source_must_match_route_and_proposed_change(context, mismatch):
    request, _, _, spec = context
    data = request.to_dict()
    source = next(item["data"] for item in data["evidence"] if item["kind"] == "source")
    extra = {"kind": "source", "data": {"path": "other.py", "text": source["text"]}}
    extra["id"] = "ev-" + identity(extra)
    data["evidence"].insert(0, extra)
    data["source_identity"] = identity(
        {
            item["data"]["path"]: item["data"]["text"]
            for item in data["evidence"]
            if item["kind"] == "source"
        }
    )
    request = CodexAnalysisRequest(canonical(data))
    review = validate_response(
        scripted_response(request, {q["id"]: None for q in data["questions"]}), request
    )
    proposal = make_proposal(request, review)  # Only other.py is changed.
    if mismatch == "other-route-source":
        spec["source_evidence_id"] = extra["id"]
    with pytest.raises(ContractError):
        prepare_expectation_manifest(request, review, proposal, expectations=[spec])


@pytest.mark.parametrize(
    "mutation", ["duplicate-id", "duplicate-observation", "duplicate-policy", "too-many"]
)
def test_duplicates_and_item_limits_are_rejected(context, mutation):
    data = manifest(context).to_dict()
    item = data["expectations"][0]
    second = json.loads(canonical(item))
    if mutation == "duplicate-policy":
        item["policy_evidence_ids"] *= 2
    elif mutation == "too-many":
        data["expectations"] *= 33
    else:
        if mutation == "duplicate-id":
            second.update(observation="dependency-declarations", expected={"count": 0})
        else:
            second["id"] = "another-id"
        data["expectations"].append(second)
    with pytest.raises(ContractError):
        validate_expectation_manifest(canonical(data), *context[:3])


@pytest.mark.parametrize(
    ("observation", "expected"),
    [("dependency-declarations", {"count": value}) for value in (True, -1, 257, 1.0, "1")]
    + [
        ("scope-declarations", {"scopes": value})
        for value in ("scope", [""], [True], ["a", "a"], ["x" * 257], [str(i) for i in range(33)])
    ],
)
def test_typed_expectation_limits(context, observation, expected):
    context[3].update(observation=observation, expected=expected)
    with pytest.raises(ContractError):
        manifest(context)


def test_preparer_rejects_binding_overrides_and_preview_is_not_a_manifest(context):
    artifact = manifest(context)
    with pytest.raises(ContractError):
        validate_expectation_manifest(
            canonical(expectation_preview(artifact, *context[:3])), *context[:3]
        )
    context[3]["after_sha256"] = "0" * 64
    with pytest.raises(ContractError):
        manifest(context)


@pytest.mark.parametrize("changed", ["policy", "source", "review", "proposal"])
def test_changed_inputs_invalidate_the_previous_manifest(context, changed):
    request, review, proposal, _ = context
    original = manifest(context)
    if changed in {"policy", "source"}:
        data = request.to_dict()
        evidence = next(item for item in data["evidence"] if item["kind"] == changed)
        if changed == "policy":
            evidence["data"] += " Additional caller policy."
        else:
            evidence["data"]["text"] += "# Changed baseline snapshot.\n"
            data["source_identity"] = identity(
                {
                    item["data"]["path"]: item["data"]["text"]
                    for item in data["evidence"]
                    if item["kind"] == "source"
                }
            )
        evidence["id"] = "ev-" + identity({"kind": evidence["kind"], "data": evidence["data"]})
        request = CodexAnalysisRequest(canonical(data))
    if changed != "proposal":
        review = validate_response(
            scripted_response(
                request, {q["id"]: "Changed review." for q in request.to_dict()["questions"]}
            ),
            request,
        )
    proposal = make_proposal(request, review, suffix="# Different caller-authored draft.\n")
    with pytest.raises(ContractError):
        validate_expectation_manifest(original.payload_json, request, review, proposal)


@pytest.mark.parametrize("wrapper", ["manifest", "review", "proposal"])
def test_preview_revalidates_forged_wrappers(context, wrapper):
    request, review, proposal, _ = context
    artifact = manifest(context)
    if wrapper == "manifest":
        artifact = ValidatedExpectationManifest("{}")
    elif wrapper == "review":
        review = ValidatedResponse("{}")
    else:
        proposal = ValidatedProposal("{}")
    with pytest.raises(ContractError):
        expectation_preview(artifact, request, review, proposal)


def test_preparation_validation_and_preview_have_no_io_or_provider_calls(context, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Expectation artifacts must remain offline and non-executing")

    for method in ("read_text", "read_bytes", "write_text", "write_bytes", "open"):
        monkeypatch.setattr(Path, method, forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(MockCodexAdapter, "analyze", forbidden)
    artifact = manifest(context)
    assert validate_expectation_manifest(artifact.payload_json, *context[:3]) == artifact
    assert expectation_preview(artifact, *context[:3])["verification_status"] == "not-run"
