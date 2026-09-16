import builtins
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from scripts.evaluate_offline import DATASET_ROOT, prepare_case

from authzest.codex import preview as bundle_contract
from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    ContractError,
    canonical,
    validate_response,
)
from authzest.codex.expectations import prepare_expectation_manifest
from authzest.codex.mock import MockCodexAdapter, scripted_response
from authzest.codex.preview import (
    PREVIEW_SCHEMA_VERSION,
    ValidatedPreviewBundle,
    prepare_preview_bundle,
    preview_bundle,
    validate_preview_bundle,
)
from authzest.codex.proposals import prepare_proposal
from authzest.runner import ScanRunner


@pytest.fixture
def artifacts():
    cases = json.loads((DATASET_ROOT / "dataset.json").read_text(encoding="utf-8"))["cases"]
    case = next(case for case in cases if case["id"] == "public")
    assert case["split"] == "development"
    _, request = prepare_case(case, "evidence-plus-model")
    review = validate_response(
        scripted_response(request, {question["id"]: None for question in case["questions"]}),
        request,
    )
    evidence = {item["kind"]: item for item in request.to_dict()["evidence"]}
    source = evidence["source"]["data"]
    proposal = prepare_proposal(
        request,
        review,
        replacements={source["path"]: source["text"] + "# Caller-authored preview example.\n"},
        rationale="Display a harmless caller-authored draft with its evidence.",
        uncertainties=("No runtime behavior has been checked.",),
        side_effects=(),
        checks=("fixture-static-inventory",),
        expectations=("Review declared intent; enforcement remains unknown.",),
    )
    manifest = prepare_expectation_manifest(
        request,
        review,
        proposal,
        expectations=[
            {
                "id": "public-intent",
                "source_evidence_id": evidence["source"]["id"],
                "route_evidence_id": evidence["route"]["id"],
                "policy_evidence_ids": [evidence["policy"]["id"]],
                "observation": "policy-intent",
                "expected": {"intent": "public"},
                "limitations": ["Caller interpretation does not prove public runtime behavior."],
            }
        ],
    )
    return request, review, proposal, manifest


def test_round_trip_and_complete_detached_preview(artifacts):
    bundle = prepare_preview_bundle(*artifacts)
    assert validate_preview_bundle(json.dumps(bundle.to_dict(), indent=2)) == bundle
    preview = preview_bundle(bundle)
    request, review, proposal, manifest = artifacts
    assert PREVIEW_SCHEMA_VERSION == preview["schema_version"] == "1.0"
    assert preview["bundle_id"] == bundle.bundle_id
    assert bundle.bundle_id.startswith("preview-")
    assert preview["status"] == "draft" and preview["applied"] is False
    assert preview["verification_status"] == "not-run"
    assert preview["authorization_verdict"] == "unknown"
    assert preview["request"] == {
        key: value for key, value in request.to_dict().items() if key != "evidence"
    } | {"request_id": request.request_id}
    assert preview["evidence"] == request.to_dict()["evidence"]
    assert preview["review"] == review.to_dict()
    assert preview["proposal"]["proposal_id"] == proposal.proposal_id
    assert "+# Caller-authored preview example." in preview["proposal"]["changes"][0]["diff"]
    assert preview["expectations"]["manifest_id"] == manifest.manifest_id
    assert preview["expectations"]["observed"] is None
    assert preview["limitations"]
    preview["evidence"].clear()
    preview["proposal"]["changes"].clear()
    bundle.to_dict()["manifest"]["expectations"].clear()
    assert preview_bundle(bundle)["evidence"]
    with pytest.raises(FrozenInstanceError):
        bundle.payload_json = "{}"


@pytest.mark.parametrize("field", ["request", "review", "proposal", "manifest"])
@pytest.mark.parametrize("value", [None, [], "not an object"])
def test_nested_artifacts_must_be_objects(artifacts, field, value):
    data = prepare_preview_bundle(*artifacts).to_dict()
    data[field] = value
    with pytest.raises(ContractError):
        validate_preview_bundle(canonical(data))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("command",), "unsupported"),
        (("request", "source_identity"), "0" * 64),
        (("review", "request_id"), "request-stale"),
        (("proposal", "review_id"), "0" * 64),
        (("manifest", "proposal_id"), "proposal-stale"),
        (("manifest", "expectations", 0, "source_evidence_id"), "ev-missing"),
        (("manifest", "expectations", 0, "after_sha256"), "0" * 64),
    ],
)
def test_invalid_fields_identities_and_references_are_rejected(artifacts, path, value):
    data = prepare_preview_bundle(*artifacts).to_dict()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ContractError):
        validate_preview_bundle(canonical(data))


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema_version":"1.0","schema_version":"1.0"}',
        '{"request":{"x":1,"x":2}}',
        '{"request":NaN}',
        '{"request":Infinity}',
        '{"request":"' + "\\ud800" + '"}',
        '{"request":' + "[" * 40 + "0" + "]" * 40 + "}",
        " " * (MAX_JSON_BYTES + 1),
        '{"request":"' + "가" * (MAX_JSON_BYTES // 3 + 1) + '"}',
    ],
)
def test_existing_strict_aggregate_json_budget_is_preserved(raw):
    with pytest.raises(ContractError):
        validate_preview_bundle(raw)


def test_display_output_is_not_an_input_bundle_and_forged_wrapper_is_rejected(artifacts):
    bundle = prepare_preview_bundle(*artifacts)
    with pytest.raises(ContractError):
        validate_preview_bundle(canonical(preview_bundle(bundle)))
    with pytest.raises(ContractError):
        preview_bundle(ValidatedPreviewBundle("{}"))


def test_changed_expectation_changes_bundle_identity_without_approval(artifacts):
    original = prepare_preview_bundle(*artifacts)
    data = original.to_dict()
    data["manifest"]["expectations"][0]["expected"]["intent"] = "restricted"
    changed = validate_preview_bundle(canonical(data))
    assert changed.bundle_id != original.bundle_id
    assert preview_bundle(changed)["status"] == "draft"
    assert preview_bundle(changed)["expectations"]["manifest_id"] != artifacts[3].manifest_id


def test_prepare_validate_and_preview_perform_no_io(artifacts, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure preview unexpectedly attempted I/O or analysis")

    for target, name in [
        (builtins, "open"),
        (os, "open"),
        (os, "read"),
        (Path, "open"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (socket, "socket"),
        (subprocess, "Popen"),
        (subprocess, "run"),
        (MockCodexAdapter, "analyze"),
        (ScanRunner, "run"),
    ]:
        monkeypatch.setattr(target, name, forbidden)
    bundle = prepare_preview_bundle(*artifacts)
    assert validate_preview_bundle(bundle.payload_json) == bundle
    assert preview_bundle(bundle)["verification_status"] == "not-run"


@pytest.mark.parametrize("error", [KeyError, TypeError, OverflowError])
def test_nested_validation_errors_use_the_bundle_error_contract(artifacts, monkeypatch, error):
    raw = prepare_preview_bundle(*artifacts).payload_json

    def malformed(_):
        raise error("Untrusted nested data must not appear in the contract message")

    monkeypatch.setattr(bundle_contract, "_artifacts", malformed)
    with pytest.raises(ContractError, match="^Invalid preview artifact structure$"):
        validate_preview_bundle(raw)
