"""Scripted pure-data application contracts; never policy or provider execution."""

import asyncio
import builtins
import io
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex import owner_policy_file_repair as contract
from authzest.codex import owner_policy_repair_recommendation as recommendation_contract
from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical, identity

APPLICATION_FIELDS = {
    "schema_version",
    "kind",
    "request_id",
    "recommendation_id",
    "request",
    "recommendation",
    "pair_preview",
    "status",
    "provider_calls",
    "execution_status",
    "patch_application",
    "restoration_status",
    "authorization_status",
    "comparison_status",
    "provenance",
}


@pytest.fixture(autouse=True)
def forbid_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("File application contracts must remain pure data")

    original_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn", "openai", "httpx", "requests"}:
            forbidden()
        if name.startswith(("authzest.runner", "authzest.codex.app_server")):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    for name in ("open", "compile", "eval", "exec"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes", "mkdir", "unlink"):
        monkeypatch.setattr(Path, name, forbidden)
    for name in ("open", "system", "mkdir", "remove", "rename", "replace"):
        monkeypatch.setattr(os, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def scripted_result(request, status):
    context = request.to_dict()
    data = {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted inert data, not a model response or maintainer decision.",
        "evidence_ids": list(context["evidence_ids"].values()),
        "case_ids": [case["case_id"] for case in context["content"]["cases"]],
        "assumptions": ["Inputs of the synthetic policy are already trusted."],
        "uncertainties": ["No policy has been executed."],
        "expected_effects": ["The registered change is expected to check ownership."],
        "limitations": ["Data validation is not execution, approval or verified authorization."],
        "change_pair_id": context["registry"]["pair_id"] if status == "registered-change" else None,
    }
    return recommendation_contract.validate_owner_policy_repair_recommendation(
        canonical(data), request
    )


def application(candidate="before", status="registered-change"):
    request = recommendation_contract.build_owner_policy_repair_recommendation_request(candidate)
    result = scripted_result(request, status)
    return contract.prepare_owner_policy_file_repair(request, result)


def mutate(data, path, value):
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


@pytest.mark.parametrize(
    ("candidate", "status"),
    [
        ("before", "registered-change"),
        ("before", "no-change"),
        ("before", "unknown"),
        ("after", "no-change"),
        ("after", "unknown"),
    ],
)
def test_complete_application_reuses_host_preview_without_granting_authority(candidate, status):
    request = recommendation_contract.build_owner_policy_repair_recommendation_request(candidate)
    result = scripted_result(request, status)
    snapshot = contract.prepare_owner_policy_file_repair(request, result)
    expected_preview = recommendation_contract.prepare_owner_policy_repair_recommendation_preview(
        result, request
    ).to_dict()
    data = snapshot.to_dict()
    assert set(data) == APPLICATION_FIELDS
    assert data["schema_version"] == contract.FILE_REPAIR_APPLICATION_SCHEMA_VERSION == "1.0"
    assert data["kind"] == "owner-policy-file-repair-application"
    assert data["request_id"] == request.request_id
    assert data["recommendation_id"] == result.recommendation_id
    assert data["request"] == request.to_dict()
    assert data["recommendation"] == result.to_dict()
    assert data["pair_preview"] == expected_preview["pair_preview"]
    assert data["status"] == status
    assert data["provider_calls"] == 0 and type(data["provider_calls"]) is int
    assert (
        data["execution_status"]
        == data["patch_application"]
        == data["restoration_status"]
        == "not-run"
    )
    assert data["authorization_status"] == "unknown"
    assert data["comparison_status"] == "not-evaluated"
    assert data["provenance"] == {"kind": "caller-supplied-data", "authenticated": False}
    assert snapshot.application_id == "owner-file-application-" + identity(data)
    assert (data["pair_preview"] is None) == (status != "registered-change")
    assert contract.validate_owner_policy_file_repair(snapshot.payload_json) == snapshot
    assert contract.validate_owner_policy_file_repair(json.dumps(data, indent=2)) == snapshot


def test_snapshot_is_frozen_slotted_detached_and_content_identified():
    snapshot = application()
    assert not hasattr(snapshot, "__dict__")
    with pytest.raises(FrozenInstanceError):
        snapshot.payload_json = "{}"
    detached = snapshot.to_dict()
    detached["request"]["content"]["cases"].clear()
    detached["pair_preview"].clear()
    assert len(snapshot.to_dict()["request"]["content"]["cases"]) == 8
    assert snapshot.to_dict()["pair_preview"]
    assert application() == snapshot
    assert application(status="no-change").application_id != snapshot.application_id


@pytest.mark.parametrize("field", sorted(APPLICATION_FIELDS))
def test_every_application_field_is_required(field):
    data = application().to_dict()
    del data[field]
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(canonical(data))


@pytest.mark.parametrize(
    "field", ["path", "source", "decision", "session", "application_id", "observations"]
)
def test_no_extra_data_or_imported_authority_is_accepted(field):
    data = application().to_dict()
    data[field] = "untrusted"
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(canonical(data))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "1.1"),
        (("kind",), "owner-policy-repair-recommendation-preview"),
        (("request_id",), "stale"),
        (("recommendation_id",), "stale"),
        (("request",), None),
        (("recommendation",), []),
        (("status",), "no-change"),
        (("provider_calls",), False),
        (("provider_calls",), 0.0),
        (("provider_calls",), 1),
        (("execution_status",), "completed"),
        (("patch_application",), "applied"),
        (("restoration_status",), "restored"),
        (("authorization_status",), "passed"),
        (("comparison_status",), "passed"),
        (("provenance", "kind"), "provider"),
        (("provenance", "authenticated"), True),
        (("provenance", "authenticated"), 0),
        (("request", "candidate"), "after"),
        (("request", "content", "path"), "../policy.py"),
        (("request", "content", "before", "text"), "raise RuntimeError('inert data')\n"),
        (("request", "content", "cases", 1, "expected"), "allow"),
        (("request", "registry", "review_record_sha256"), "0" * 64),
        (("recommendation", "request_id"), "stale"),
        (("recommendation", "case_ids"), ["unregistered-case"]),
        (("recommendation", "evidence_ids"), []),
        (("recommendation", "change_pair_id"), "unregistered-pair"),
        (("recommendation", "status"), "applied"),
        (("pair_preview",), None),
        (("pair_preview", "pair_id"), "unregistered-pair"),
        (("pair_preview", "diff"), "Caller-supplied diff is not a registered patch."),
        (("pair_preview", "diff_sha256"), "0" * 64),
        (("pair_preview", "pair", "content", "after", "text"), "pass\n"),
        (("pair_preview", "comparison_status"), "passed"),
        (("pair_preview", "observations", "before"), [True] * 8),
    ],
)
def test_imported_payload_revalidates_nested_data_and_exact_host_metadata(path, value):
    data = application().to_dict()
    mutate(data, path, value)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(canonical(data))


@pytest.mark.parametrize("status", ["no-change", "unknown"])
def test_non_change_application_never_accepts_a_pair_preview(status):
    data = application(status=status).to_dict()
    data["pair_preview"] = application().to_dict()["pair_preview"]
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(canonical(data))


@pytest.mark.parametrize("target", ["request", "recommendation"])
@pytest.mark.parametrize("kind", ["dict", "wrong-wrapper", "subclass", "forged", "malformed"])
def test_preparer_requires_exact_revalidated_original_wrappers(target, kind):
    request = recommendation_contract.build_owner_policy_repair_recommendation_request()
    result = scripted_result(request, "registered-change")
    original = request if target == "request" else result
    if kind == "dict":
        replacement = original.to_dict()
    elif kind == "wrong-wrapper":
        replacement = contract.OwnerPolicyFileRepairApplication(original.payload_json)
    elif kind == "subclass":

        class Subclass(type(original)):
            def to_dict(self):
                pytest.fail("Subclass methods must not run")

        replacement = Subclass(original.payload_json)
    elif kind == "forged":
        data = original.to_dict()
        data["extra"] = "constructed wrappers grant no trust"
        replacement = type(original)(canonical(data))
    else:
        replacement = type(original)(None)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_file_repair(
            replacement if target == "request" else request,
            replacement if target == "recommendation" else result,
        )


def test_before_recommendation_cannot_be_replayed_into_after_application():
    before = recommendation_contract.build_owner_policy_repair_recommendation_request()
    after = recommendation_contract.build_owner_policy_repair_recommendation_request("after")
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_file_repair(after, scripted_result(before, "no-change"))


def test_rehashed_changed_source_is_still_rejected():
    data = application().to_dict()
    before = data["request"]["content"]["before"]
    before["text"] += "# Caller-owned unregistered inert data.\n"
    before["sha256"] = sha256(before["text"].encode("utf-8")).hexdigest()
    data["request"]["registry"]["content_sha256"] = identity(data["request"]["content"])
    data["request_id"] = "owner-repair-request-" + identity(data["request"])
    data["recommendation"]["request_id"] = data["request_id"]
    data["recommendation_id"] = "owner-repair-recommendation-" + identity(data["recommendation"])
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(canonical(data))


def test_current_registration_is_rebuilt_not_cached(monkeypatch):
    snapshot = application()
    monkeypatch.setattr(
        recommendation_contract,
        "_INSTRUCTIONS",
        recommendation_contract._INSTRUCTIONS + "\nMaintained instruction update.\n",
    )
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(snapshot.payload_json)


def test_untrusted_explanation_remains_data_and_does_not_change_host_diff():
    request = recommendation_contract.build_owner_policy_repair_recommendation_request()
    original = scripted_result(request, "registered-change")
    data = original.to_dict()
    data["rationale"] = "__import__('os').system('DO_NOT_EXECUTE'); open('/not-an-input')"
    changed = recommendation_contract.OwnerPolicyRepairRecommendation(canonical(data))
    first = contract.prepare_owner_policy_file_repair(request, original)
    second = contract.prepare_owner_policy_file_repair(request, changed)
    assert second.to_dict()["recommendation"]["rationale"] == data["rationale"]
    assert second.to_dict()["pair_preview"] == first.to_dict()["pair_preview"]
    assert second.application_id != first.application_id


@pytest.mark.parametrize("option", ["source", "path", "registry", "callback", "model", "decision"])
def test_preparer_accepts_no_filesystem_provider_or_decision_options(option):
    request = recommendation_contract.build_owner_policy_repair_recommendation_request()
    with pytest.raises(TypeError):
        contract.prepare_owner_policy_file_repair(
            request, scripted_result(request, "registered-change"), **{option: None}
        )


@pytest.mark.parametrize(
    "raw",
    [None, {}, b"{}", "[]", "null", "{}", '{"x":0,"x":1}', '{"x":NaN}', "x" * (MAX_JSON_BYTES + 1)],
)
def test_validator_rejects_invalid_json_objects_and_budget_overflow(raw):
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(raw)


def test_nested_duplicate_fields_do_not_get_canonicalized_away():
    raw = application().payload_json
    raw = raw.replace('"authenticated":false', '"authenticated":false,"authenticated":false', 1)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(raw)


def test_hand_constructed_application_is_not_already_validated():
    wrapper = contract.OwnerPolicyFileRepairApplication('{"decision":"approved"}')
    assert wrapper.to_dict() == {"decision": "approved"}
    with pytest.raises(ContractError):
        contract.validate_owner_policy_file_repair(wrapper.payload_json)
