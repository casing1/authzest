"""Scripted, owned JSONL children; no actual Codex/model or generated code runs."""

import asyncio
import os

import pytest

from authzest.codex import app_server
from authzest.codex.app_server import AppServerError, CodexAppServerAdapter
from authzest.codex.contracts import ContractError, canonical
from authzest.codex.diagnostics import FailureDiagnostic
from authzest.codex.fixture_draft import HOST_INSTRUCTIONS, build_fixture_request
from authzest.codex.generated_repair import STATUSES
from authzest.codex.generated_repair_transport import (
    GeneratedRepairTransportRequest,
    build_generated_repair_transport_request,
    prepare_generated_repair_transport_result,
)
from authzest.codex.owner_policy_repair_transport import build_owner_policy_repair_transport_request
from authzest.codex.owner_policy_review import build_owner_policy_request
from test_codex_app_server import adapter, assert_stopped
from test_codex_app_server import fake_factory as fake_factory
from test_generated_repair import draft
from test_generated_repair_transport import inner

pytestmark = pytest.mark.skipif(os.name != "posix", reason="App Server requires POSIX")


@pytest.fixture
def context():
    return build_generated_repair_transport_request("fixture-test-model")


@pytest.mark.parametrize("status", STATUSES)
def test_owned_jsonl_transport_sends_exact_prompt_schema_and_returns_validated_data(
    context, fake_factory, status
):
    response = draft(inner(context), status)
    fake = fake_factory(request=context, response=response)
    transport = adapter(context, fake)
    checked = asyncio.run(transport.generate_repair(context))
    assert checked == prepare_generated_repair_transport_result(
        canonical(response), context, usage={"input_tokens": 123, "output_tokens": 45}
    )
    assert transport.failure_diagnostic is None
    assert transport.warnings_seen == transport.retry_notifications_seen == 0
    assert fake.methods() == [
        "initialize",
        "initialized",
        "config/read",
        "initialize",
        "initialized",
        "config/read",
        "remoteControl/status/read",
        "account/read",
        "model/list",
        "thread/start",
        "turn/start",
    ]
    calls = {
        event["message"]["method"]: event["message"]["params"]
        for event in fake.events()
        if event["event"] == "request" and event["message"].get("method")
    }
    assert calls["turn/start"]["input"] == [{"type": "text", "text": context.to_dict()["prompt"]}]
    assert calls["turn/start"]["outputSchema"] == context.to_dict()["output_schema"]
    assert calls["turn/start"]["model"] == "fixture-test-model"
    assert calls["thread/start"]["baseInstructions"] == HOST_INSTRUCTIONS
    assert calls["thread/start"]["developerInstructions"] == HOST_INSTRUCTIONS
    assert calls["thread/start"]["allowProviderModelFallback"] is False
    assert calls["turn/start"]["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert len(fake.starts()) == 2
    assert_stopped(fake)


@pytest.mark.parametrize("mutation", ["wrong-type", "prompt", "model", "share-id"])
def test_request_type_integrity_and_exact_sharing_gate_fail_before_start(
    context, fake_factory, mutation
):
    request = context
    approved = context.request_id
    if mutation == "wrong-type":
        request = build_owner_policy_repair_transport_request("fixture-test-model")
    elif mutation == "share-id":
        approved = inner(context).request_id  # Inner content is not the transport approval ID.
    else:
        data = context.to_dict()
        if mutation == "prompt":
            data["prompt"] = "FAKE_SECRET_UNREVIEWED_PROMPT"
        else:
            data["config"]["model"] = "other-model"
        request = GeneratedRepairTransportRequest(canonical(data))
    fake = fake_factory(request=context, response=draft(inner(context)))
    transport = CodexAppServerAdapter(approved, executable=str(fake.executable), timeout_seconds=5)
    with pytest.raises((AppServerError, ContractError)):
        asyncio.run(transport.generate_repair(request))
    assert not fake.events()
    assert transport.consumed is False
    assert transport.failure_diagnostic == FailureDiagnostic(
        "request-validation", "request-invalid", "not-attempted"
    )


@pytest.mark.parametrize("case", ["happy", "wrong-turn"])
def test_transport_one_use_is_shared_with_all_existing_entry_points(context, fake_factory, case):
    fake = fake_factory(case, request=context, response=draft(inner(context)))
    transport = adapter(context, fake)
    if case == "happy":
        asyncio.run(transport.generate_repair(context))
    else:
        with pytest.raises(AppServerError):
            asyncio.run(transport.generate_repair(context))
    for method, request in (
        (transport.generate_repair, context),
        (transport.draft, build_fixture_request("fixture-test-model")),
        (transport.review_owner_policy, build_owner_policy_request("fixture-test-model")),
        (
            transport.recommend_owner_policy_repair,
            build_owner_policy_repair_transport_request("fixture-test-model"),
        ),
    ):
        with pytest.raises(AppServerError, match="fresh exact-request"):
            asyncio.run(method(request))
    assert fake.methods().count("turn/start") == 1
    assert len(fake.starts()) == 2
    assert_stopped(fake)


@pytest.mark.parametrize("mutation", ["syntax", "path", "uncertainty"])
def test_generated_response_validation_fails_without_leaking_source_or_granting_approval(
    context, fake_factory, mutation
):
    response = draft(inner(context), "unknown" if mutation == "uncertainty" else "proposed-change")
    if mutation == "syntax":
        response["proposal"]["test_text"] = "FAKE_SECRET_INVALID_PYTHON ("
    elif mutation == "path":
        response["proposal"]["source_path"] = "FAKE_SECRET_OTHER.py"
    else:
        response["uncertainties"] = []
    fake = fake_factory(request=context, response=response)
    transport = adapter(context, fake)
    with pytest.raises(AppServerError) as error:
        asyncio.run(transport.generate_repair(context))
    assert "FAKE_SECRET" not in str(error.value)
    assert transport.failure_diagnostic.stage == "response-validation"
    assert transport.failure_diagnostic.code.startswith("validation-")
    assert transport.failure_diagnostic.turn_start == "acknowledged"
    assert transport.warnings_seen is transport.retry_notifications_seen is None
    assert fake.methods().count("turn/start") == 1
    assert_stopped(fake)


def test_new_entry_point_only_delegates_exact_payload_to_existing_turn(context, monkeypatch):
    transport = CodexAppServerAdapter(context.request_id)
    expected = prepare_generated_repair_transport_result(
        canonical(draft(inner(context))), context, usage=None
    )
    calls = []

    async def turn(request, prompt, schema, validate):
        calls.append((request, prompt, schema))
        return validate(canonical(draft(inner(context))), None)

    monkeypatch.setattr(transport, "_turn", turn)
    checked = asyncio.run(transport.generate_repair(context))
    assert checked == expected
    assert calls == [(context, context.to_dict()["prompt"], context.to_dict()["output_schema"])]
    assert app_server.SUPPORTED_CODEX_VERSION == "0.153.0"
