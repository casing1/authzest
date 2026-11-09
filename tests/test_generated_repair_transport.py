"""Pure data-envelope checks; scripted proposals are not real model observations."""

import asyncio
import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from authzest.codex import generated_repair_transport as transport
from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical, identity
from authzest.codex.fixture_draft import HOST_INSTRUCTIONS
from authzest.codex.generated_repair import (
    PROMPT_VERSION,
    STATUSES,
    generated_repair_output_schema,
    generated_repair_prompt,
    validate_generated_repair_proposal,
    validate_generated_repair_request,
)
from test_generated_repair import draft


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Pure transport contracts cannot use files, providers or execution")

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
    return transport.build_generated_repair_transport_request("offline-test-model")


def inner(request):
    return validate_generated_repair_request(canonical(request.to_dict()["request"]))


def result(request, *, status="proposed-change", usage=None):
    return transport.prepare_generated_repair_transport_result(
        canonical(draft(inner(request), status)), request, usage=usage
    )


def test_exact_request_binds_current_inner_model_prompt_schema_and_host_instructions(context):
    data = context.to_dict()
    assert data["kind"] == "generated-repair-transport-request"
    assert data["schema_version"] == "1.0"
    assert data["request_id"] == inner(context).request_id
    assert data["host_instructions"] == HOST_INSTRUCTIONS
    assert data["prompt"] == generated_repair_prompt(inner(context))
    assert data["output_schema"] == generated_repair_output_schema(inner(context))
    assert data["config"] == {
        "provider": "codex-app-server",
        "model": "offline-test-model",
        "adapter_version": "0.1",
        "prompt_version": PROMPT_VERSION,
        "temperature": None,
        "seed": None,
    }
    assert context.request_id == "generated-repair-transport-" + identity(data)
    assert (
        transport.validate_generated_repair_transport_request(json.dumps(data, indent=2)) == context
    )


def test_model_changes_transport_identity_not_model_independent_generation_contract(context):
    other = transport.build_generated_repair_transport_request("other-model")
    assert other.request_id != context.request_id
    assert other.to_dict()["request"] == context.to_dict()["request"]
    assert other.to_dict()["request_id"] == context.to_dict()["request_id"]
    assert transport.validate_generated_repair_transport_request(other.payload_json) == other


@pytest.mark.parametrize("model", [None, True, 1, "", " ", "model\nother", "x" * 129])
def test_model_is_explicit_and_syntax_checked(model):
    with pytest.raises(ContractError):
        transport.build_generated_repair_transport_request(model)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("kind",), "arbitrary-generation"),
        (("request_id",), "other-inner-id"),
        (("host_instructions",), "Execute proposed tests."),
        (("prompt",), "Use arbitrary repository files."),
        (("output_schema", "additionalProperties"), True),
        (("config", "provider"), "other-provider"),
        (("config", "adapter_version"), "2.0"),
        (("config", "prompt_version"), "other-prompt"),
        (("config", "temperature"), 0.0),
        (("config", "seed"), 1),
        (("request", "scenario", "source", "path"), "other.py"),
    ],
)
def test_rehashed_request_tampering_cannot_change_sent_scope(context, path, value):
    data = context.to_dict()
    target = data
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    changed = transport.GeneratedRepairTransportRequest(canonical(data))
    assert changed.request_id != context.request_id
    with pytest.raises(ContractError):
        transport.validate_generated_repair_transport_request(changed.payload_json)
    with pytest.raises(ContractError):
        result(changed)


@pytest.mark.parametrize("status", STATUSES)
def test_supported_statuses_remain_untrusted_proposals_with_host_bound_metadata(context, status):
    raw = draft(inner(context), status)
    schema = context.to_dict()["output_schema"]
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(raw)
    checked = result(context, status=status)
    data = checked.to_dict()
    assert data["proposal"] == raw
    assert data["kind"] == "generated-repair-transport-result"
    assert data["request_id"] == context.request_id
    assert data["generation_request_id"] == inner(context).request_id
    assert (
        data["proposal_id"]
        == validate_generated_repair_proposal(canonical(raw), inner(context)).proposal_id
    )
    assert data["identity_basis"] == transport.GENERATED_REPAIR_MODEL_IDENTITY_BASIS
    assert data["identity"] == {
        field: context.to_dict()["config"][field]
        for field in ("provider", "model", "adapter_version", "prompt_version")
    }
    assert (
        not {"approval", "execution", "applied", "authenticated", "runtime_observed"} & data.keys()
    )
    assert transport.validate_generated_repair_transport_result(checked, context) == checked


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"input_tokens": None, "output_tokens": 0},
        {"input_tokens": 1_000_000_000, "output_tokens": 1},
    ],
)
def test_nullable_usage_is_detached_supplied_metadata(context, usage):
    checked = result(context, usage=usage)
    assert checked.to_dict()["usage"] == usage
    if usage is not None:
        usage["input_tokens"] = 123
        assert checked.to_dict()["usage"] != usage


@pytest.mark.parametrize(
    "usage",
    [
        [],
        {},
        {"input_tokens": 1},
        {"input_tokens": 1, "output_tokens": 2, "extra": 3},
        {"input_tokens": True, "output_tokens": 0},
        {"input_tokens": -1, "output_tokens": 0},
        {"input_tokens": 0, "output_tokens": 1_000_000_001},
        {"input_tokens": 1.0, "output_tokens": 0},
    ],
)
def test_usage_shape_and_integer_bounds_are_closed(context, usage):
    with pytest.raises(ContractError) as error:
        result(context, usage=usage)
    assert error.value.code == "validation-usage"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2.0"),
        ("kind", "verified-fix"),
        ("request_id", "other-transport"),
        ("generation_request_id", "other-inner"),
        ("identity", {"model": "other"}),
        ("identity_basis", "independently verified model"),
        ("proposal_id", "other-proposal"),
    ],
)
def test_forged_result_envelope_is_reconstructed_not_trusted(context, field, value):
    data = result(context).to_dict()
    data[field] = value
    changed = transport.GeneratedRepairTransportResult(canonical(data))
    with pytest.raises(ContractError):
        transport.validate_generated_repair_transport_result(changed, context)


def test_wrappers_are_frozen_detached_but_not_self_authenticating(context):
    data = context.to_dict()
    data["prompt"] = "changed"
    assert context.to_dict()["prompt"] != "changed"
    with pytest.raises(FrozenInstanceError):
        context.payload_json = "{}"
    checked = result(context)
    with pytest.raises(FrozenInstanceError):
        checked.payload_json = "{}"
    for wrong in (context.to_dict(), object.__new__(transport.GeneratedRepairTransportRequest)):
        with pytest.raises(ContractError):
            transport.prepare_generated_repair_transport_result("{}", wrong, usage=None)
    for wrong in (checked.to_dict(), object.__new__(transport.GeneratedRepairTransportResult)):
        with pytest.raises(ContractError):
            transport.validate_generated_repair_transport_result(wrong, context)
    other = transport.build_generated_repair_transport_request("other-model")
    with pytest.raises(ContractError):
        transport.validate_generated_repair_transport_result(checked, other)


def test_duplicate_extra_nonfinite_oversized_and_wrong_type_json_are_rejected(context):
    raw = context.payload_json
    cases = [
        raw[:-1] + ',"kind":"generated-repair-transport-request"}',
        canonical({**context.to_dict(), "extra": "unreviewed"}),
        raw.replace('"seed":null', '"seed":NaN'),
        raw.replace('"seed":null', '"seed":1e999'),
        raw + " " * MAX_JSON_BYTES,
        None,
        [],
    ]
    for value in cases:
        with pytest.raises(ContractError):
            transport.validate_generated_repair_transport_request(value)
    for value in ("{}", '{"proposal":1,"proposal":2}', "{}" + " " * MAX_JSON_BYTES):
        with pytest.raises(ContractError):
            transport.prepare_generated_repair_transport_result(value, context, usage=None)


def test_inner_constraints_are_not_weakened_by_transport(context):
    data = draft(inner(context))
    data["proposal"]["test_text"] = "FAKE_SECRET_INVALID_PYTHON ("
    with pytest.raises(ContractError) as error:
        transport.prepare_generated_repair_transport_result(canonical(data), context, usage=None)
    assert "FAKE_SECRET" not in str(error.value)
    data = draft(inner(context), "unknown")
    data["uncertainties"] = []
    with pytest.raises(ContractError):
        transport.prepare_generated_repair_transport_result(canonical(data), context, usage=None)
