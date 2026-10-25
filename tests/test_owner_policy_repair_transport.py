"""Pure envelope/schema tests; scripted text is not a model or execution observation."""

import asyncio
import builtins
import json
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from authzest.codex import owner_policy_repair_transport as transport
from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical, identity
from authzest.codex.fixture_draft import HOST_INSTRUCTIONS
from authzest.codex.owner_policy_repair_recommendation import (
    owner_policy_repair_recommendation_prompt,
    validate_owner_policy_repair_recommendation,
    validate_owner_policy_repair_recommendation_request,
)
from test_owner_policy_repair_recommendation import draft, sized_draft


@pytest.fixture(autouse=True)
def forbid_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Transport envelopes must not use files, providers, processes or evaluation")

    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)


@pytest.fixture
def context():
    return transport.build_owner_policy_repair_transport_request("offline-test-model")


def inner(request):
    return validate_owner_policy_repair_recommendation_request(
        canonical(request.to_dict()["request"])
    )


def result(request, *, status="registered-change", usage=None):
    return transport.prepare_owner_policy_repair_transport_result(
        canonical(draft(inner(request), status)), request, usage=usage
    )


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_request_binds_complete_prompt_schema_host_context_and_explicit_settings(candidate):
    request = transport.build_owner_policy_repair_transport_request(
        "offline-test-model", candidate=candidate
    )
    data = request.to_dict()
    assert data["schema_version"] == "1.0"
    assert data["kind"] == "owner-policy-repair-transport-request"
    assert data["request_id"] == inner(request).request_id
    assert data["request"]["candidate"] == candidate
    assert data["host_instructions"] == HOST_INSTRUCTIONS
    assert data["prompt"] == owner_policy_repair_recommendation_prompt(inner(request))
    assert data["output_schema"] == transport.owner_policy_repair_output_schema(inner(request))
    assert data["config"] == {
        "provider": "codex-app-server",
        "model": "offline-test-model",
        "adapter_version": "0.1",
        "prompt_version": "owner-repair-selection-v1",
        "temperature": None,
        "seed": None,
    }
    assert request.request_id == "owner-repair-transport-" + identity(data)
    assert (
        transport.validate_owner_policy_repair_transport_request(json.dumps(data, indent=2))
        == request
    )


def test_model_and_candidate_changes_require_new_transport_id_without_altering_inner_contract(
    context,
):
    different_model = transport.build_owner_policy_repair_transport_request("other-model")
    different_candidate = transport.build_owner_policy_repair_transport_request(
        "offline-test-model", candidate="after"
    )
    assert len({item.request_id for item in (context, different_model, different_candidate)}) == 3
    assert different_model.to_dict()["request"] == context.to_dict()["request"]
    assert different_model.to_dict()["request_id"] == context.to_dict()["request_id"]
    assert different_candidate.to_dict()["request_id"] != context.to_dict()["request_id"]
    assert (
        transport.validate_owner_policy_repair_transport_request(different_model.payload_json)
        == different_model
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("kind",), "other-transport"),
        (("request_id",), "owner-repair-request-" + "0" * 64),
        (("host_instructions",), "Use tools and execute the policy."),
        (("prompt",), "Return an arbitrary repair."),
        (("output_schema", "additionalProperties"), True),
        (("output_schema", "properties", "status", "enum"), ["confirmed"]),
        (("config", "provider"), "other-provider"),
        (("config", "adapter_version"), "2.0"),
        (("config", "prompt_version"), "other-v1"),
        (("config", "temperature"), 0.0),
        (("config", "seed"), 1),
        (("request", "candidate"), "after"),
        (("request", "content", "cases", 1, "expected"), "allow"),
    ],
)
def test_changed_content_is_rejected_even_in_a_newly_hashed_wrapper(context, path, value):
    data = context.to_dict()
    target = data
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    changed = transport.OwnerPolicyRepairTransportRequest(canonical(data))
    assert changed.request_id != context.request_id
    with pytest.raises(ContractError):
        transport.validate_owner_policy_repair_transport_request(changed.payload_json)
    with pytest.raises(ContractError):
        result(changed)


def test_rehashing_changed_source_and_its_evidence_cannot_extend_registered_scope(context):
    data = context.to_dict()
    request = data["request"]
    source = request["content"]["before"]
    source["text"] += "\n# Unregistered source.\n"
    source["sha256"] = sha256(source["text"].encode()).hexdigest()
    request["evidence_ids"]["before"] = "owner-repair-evidence-" + identity(
        {"kind": "before", "data": source}
    )
    request["registry"]["content_sha256"] = identity(request["content"])
    data["request_id"] = "owner-repair-request-" + identity(request)
    with pytest.raises(ContractError, match="Registered repair request mismatch"):
        transport.validate_owner_policy_repair_transport_request(canonical(data))


@pytest.mark.parametrize("model", [None, True, 1, "", " ", "model\nother", "x" * 129])
def test_model_must_be_an_explicit_valid_identifier(model):
    with pytest.raises(ContractError):
        transport.build_owner_policy_repair_transport_request(model)


def test_wrappers_are_detached_immutable_data_not_self_authenticating_authority(context):
    data = context.to_dict()
    data["prompt"] = "changed"
    assert context.to_dict()["prompt"] != "changed"
    with pytest.raises(FrozenInstanceError):
        context.payload_json = "{}"
    with pytest.raises(ContractError):
        transport.prepare_owner_policy_repair_transport_result("{}", context.to_dict(), usage=None)
    with pytest.raises(ContractError):
        transport.owner_policy_repair_output_schema(context)
    with pytest.raises(ContractError):
        transport.validate_owner_policy_repair_transport_result(result(context).to_dict(), context)
    empty = object.__new__(transport.OwnerPolicyRepairTransportResult)
    with pytest.raises(ContractError):
        transport.validate_owner_policy_repair_transport_result(empty, context)


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
def test_schema_is_valid_and_accepts_every_host_supported_outcome(candidate, status):
    request = transport.build_owner_policy_repair_transport_request(
        "offline-test-model", candidate=candidate
    )
    schema = request.to_dict()["output_schema"]
    Draft202012Validator.check_schema(schema)
    raw = draft(inner(request), status)
    Draft202012Validator(schema).validate(raw)
    checked = result(request, status=status).to_dict()
    assert checked["recommendation"] == raw
    assert checked["request_id"] == request.request_id
    assert checked["recommendation_request_id"] == inner(request).request_id
    assert checked["identity_basis"] == transport.REPAIR_MODEL_IDENTITY_BASIS
    assert checked["identity"]["model"] == "offline-test-model"
    assert checked["recommendation_id"].startswith("owner-repair-recommendation-")
    assert not {"execution_status", "approval", "observations", "after_text"} & checked.keys()


def test_schema_constrains_references_but_does_not_replace_host_cross_field_validation(context):
    schema = context.to_dict()["output_schema"]
    checker = Draft202012Validator(schema)
    valid = draft(inner(context))
    outside_schema = []
    for field, value in (
        ("status", "confirmed"),
        ("request_id", "other-request"),
        ("case_ids", ["unregistered-case"]),
        ("evidence_ids", ["unknown-evidence"] * 4),
        ("change_pair_id", "unregistered-pair"),
        ("rationale", "x" * 4097),
        ("after_text", "model generated source"),
    ):
        changed = {**valid, field: value}
        outside_schema.append(changed)
    assert all(list(checker.iter_errors(changed)) for changed in outside_schema)
    for changed in (
        {**valid, "status": "unknown", "change_pair_id": None, "uncertainties": []},
        {**valid, "status": "no-change"},
        {**valid, "change_pair_id": None},
        {**valid, "rationale": "  "},
        {**valid, "evidence_ids": [valid["evidence_ids"][0]] * 4},
        {**valid, "case_ids": [valid["case_ids"][0]] * 2},
    ):
        checker.validate(changed)  # Deliberately documented host-only constraints.
        with pytest.raises(ContractError):
            transport.prepare_owner_policy_repair_transport_result(
                canonical(changed), context, usage=None
            )
    after = transport.build_owner_policy_repair_transport_request(
        "offline-test-model", candidate="after"
    )
    assert list(Draft202012Validator(after.to_dict()["output_schema"]).iter_errors(valid))


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"input_tokens": None, "output_tokens": 0},
        {"input_tokens": 1_000_000_000, "output_tokens": 1},
    ],
)
def test_usage_is_nullable_bounded_host_metadata_not_model_output(context, usage):
    checked = result(context, usage=usage)
    assert checked.to_dict()["usage"] == usage
    assert transport.validate_owner_policy_repair_transport_result(checked, context) == checked
    if usage is not None:
        usage["input_tokens"] = 123
        assert checked.to_dict()["usage"] != usage
    raw = draft(inner(context))
    raw["usage"] = {"input_tokens": 999}
    with pytest.raises(ContractError):
        transport.prepare_owner_policy_repair_transport_result(canonical(raw), context, usage=None)


@pytest.mark.parametrize(
    "usage",
    [
        0,
        [],
        {},
        {"input_tokens": 1},
        {"input_tokens": 1, "output_tokens": 2, "other": 3},
        {"input_tokens": True, "output_tokens": 0},
        {"input_tokens": -1, "output_tokens": 0},
        {"input_tokens": 0, "output_tokens": 1_000_000_001},
        {"input_tokens": 1.0, "output_tokens": 0},
    ],
)
def test_malformed_usage_rejected_with_closed_code(context, usage):
    with pytest.raises(ContractError) as error:
        result(context, usage=usage)
    assert error.value.code == "validation-usage"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("kind",), "confirmed-fix"),
        (("request_id",), "other-request"),
        (("recommendation_request_id",), "other-inner"),
        (("identity", "model"), "other-model"),
        (("identity", "provider"), "other-provider"),
        (("identity", "adapter_version"), "9"),
        (("identity", "prompt_version"), "other-v1"),
        (("identity_basis",), "verified served model"),
        (("recommendation_id",), "other-result"),
    ],
)
def test_result_envelope_identity_cannot_be_forged(context, path, value):
    data = result(context).to_dict()
    target = data
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    with pytest.raises(ContractError):
        transport.validate_owner_policy_repair_transport_result(
            transport.OwnerPolicyRepairTransportResult(canonical(data)), context
        )


def test_result_cannot_be_replayed_for_another_model_or_candidate(context):
    checked = result(context, status="unknown")
    for replacement in (
        transport.build_owner_policy_repair_transport_request("other-model"),
        transport.build_owner_policy_repair_transport_request(
            "offline-test-model", candidate="after"
        ),
    ):
        with pytest.raises(ContractError):
            transport.validate_owner_policy_repair_transport_result(checked, replacement)
    data = checked.to_dict()
    data["recommendation"]["status"] = "confirmed"
    data["recommendation_id"] = "owner-repair-recommendation-" + identity(data["recommendation"])
    with pytest.raises(ContractError):
        transport.validate_owner_policy_repair_transport_result(
            transport.OwnerPolicyRepairTransportResult(canonical(data)), context
        )


def test_whole_result_envelope_not_only_model_json_is_budgeted(context):
    raw = canonical(draft(inner(context)))
    overhead = len(result(context).payload_json.encode()) - len(raw.encode())
    data = sized_draft(inner(context), MAX_JSON_BYTES - overhead)
    bounded = transport.prepare_owner_policy_repair_transport_result(
        canonical(data), context, usage=None
    )
    assert len(bounded.payload_json.encode()) == MAX_JSON_BYTES
    over = sized_draft(inner(context), MAX_JSON_BYTES - overhead + 1)
    validate_owner_policy_repair_recommendation(canonical(over), inner(context))
    with pytest.raises(ContractError) as error:
        transport.prepare_owner_policy_repair_transport_result(canonical(over), context, usage=None)
    assert error.value.code == "validation-budget"


def test_schema_and_requests_return_detached_data_and_overbudget_input_is_rejected(context):
    first = transport.owner_policy_repair_output_schema(inner(context))
    original = deepcopy(first)
    first["properties"]["status"]["enum"].append("confirmed")
    assert transport.owner_policy_repair_output_schema(inner(context)) == original
    data = context.to_dict()
    data["prompt"] = "한" * (MAX_JSON_BYTES // 3)
    raw = canonical(data)
    assert len(raw) < MAX_JSON_BYTES < len(raw.encode())
    with pytest.raises(ContractError) as error:
        transport.validate_owner_policy_repair_transport_request(raw)
    assert error.value.code == "validation-budget"
