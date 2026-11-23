"""Owned scripted peers and inert files; no account, model or generated-code run."""

import asyncio
import copy
import os

import pytest

import test_codex_app_server as peer_tests
from authzest.analyzer.repository_input import capture_repository
from authzest.codex import app_server
from authzest.codex.app_server import AppServerError, CodexAppServerAdapter
from authzest.codex.contracts import ContractError, canonical
from authzest.codex.diagnostics import FailureDiagnostic
from authzest.codex.fixture_draft import HOST_INSTRUCTIONS, build_fixture_request
from authzest.codex.repository_proposal import (
    REPOSITORY_HOST_INSTRUCTIONS,
    STATUSES,
    RepositoryProposalRequest,
    build_repository_request,
    validate_repository_response,
)
from test_codex_app_server import adapter, assert_stopped
from test_codex_app_server import fake_factory as fake_factory

pytestmark = pytest.mark.skipif(os.name != "posix", reason="App Server requires POSIX")

SOURCE = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    '@app.get("/reports/{report_id}")\n'
    "def read_report(report_id: str):\n"
    '    return {"id": report_id}\n'
)


@pytest.fixture
def context(tmp_path):
    root = tmp_path.resolve()
    (root / "service.py").write_text(SOURCE)
    (root / "policy.md").write_text("A reader must own the requested report.\n")
    return build_repository_request(
        capture_repository(root, "service.py", "policy.md"), "external-test-model"
    )


def response_data(request, status="proposed-change"):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted transport data, not an observed authorization result.",
        "assumptions": ["Test setup and identity handling require human review."],
        "uncertainties": ["Authentication and deployment have not been inspected."],
        "limitations": ["No source or proposed test has been executed."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": SOURCE.replace('return {"id": report_id}', 'return {"id": "denied"}'),
            "test_path": request.to_dict()["test_path"],
            "test_text": (
                "def test_regression(client):\n"
                "    assert client.get('/reports/7').status_code == 403\n"
            ),
        }
        if status == "proposed-change"
        else None,
    }


@pytest.fixture
def repository_peer(fake_factory, monkeypatch):
    original_config = peer_tests.nested_config

    def selected_config():
        config = original_config()
        config["developer_instructions"] = REPOSITORY_HOST_INSTRUCTIONS
        return config

    monkeypatch.setattr(peer_tests, "nested_config", selected_config)
    return fake_factory


def calls_by_method(fake):
    return {
        event["message"]["method"]: event["message"]["params"]
        for event in fake.events()
        if event["event"] == "request" and event["message"].get("method")
    }


@pytest.mark.parametrize("status", STATUSES)
def test_external_snapshot_uses_exact_payload_and_dedicated_host_context(
    context, repository_peer, status, tmp_path
):
    response = response_data(context, status)
    fake = repository_peer(request=context, response=response)
    transport = adapter(context, fake)
    assert asyncio.run(transport.suggest_repository(context)) == validate_repository_response(
        canonical(response), context
    )
    calls = calls_by_method(fake)
    assert calls["turn/start"]["input"] == [{"type": "text", "text": context.to_dict()["prompt"]}]
    assert calls["turn/start"]["outputSchema"] == context.to_dict()["output_schema"]
    assert calls["turn/start"]["model"] == "external-test-model"
    assert calls["thread/start"]["baseInstructions"] == REPOSITORY_HOST_INSTRUCTIONS
    assert calls["thread/start"]["developerInstructions"] == REPOSITORY_HOST_INSTRUCTIONS
    assert calls["thread/start"]["allowProviderModelFallback"] is False
    assert calls["thread/start"]["dynamicTools"] == []
    assert calls["thread/start"]["runtimeWorkspaceRoots"] == []
    assert calls["turn/start"]["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    for start in fake.starts():
        assert (
            "developer_instructions=" + canonical(REPOSITORY_HOST_INSTRUCTIONS)
            in start["arguments"]
        )
        assert start["cwd"] != str(tmp_path.resolve())
    assert fake.methods().count("turn/start") == 1
    assert fake.methods().count("config/read") == 2
    assert len(fake.starts()) == 2
    assert transport.consumed and transport.failure_diagnostic is None
    assert transport.warnings_seen == transport.retry_notifications_seen == 0
    assert_stopped(fake)


def test_external_method_only_delegates_checked_payload_and_validator(context, monkeypatch):
    transport = CodexAppServerAdapter(context.request_id)
    response = response_data(context)
    calls = []

    async def turn(request, prompt, schema, validate):
        calls.append((request, prompt, schema))
        return validate(canonical(response), None)

    monkeypatch.setattr(transport, "_turn", turn)
    assert asyncio.run(transport.suggest_repository(context)) == response
    assert calls == [(context, context.to_dict()["prompt"], context.to_dict()["output_schema"])]
    assert app_server.SUPPORTED_CODEX_VERSION == "0.153.0"


@pytest.mark.parametrize("mutation", ["type", "prompt", "model", "instructions", "share-id"])
def test_unreviewed_external_request_never_starts_transport(context, monkeypatch, mutation):
    request, approved = context, context.request_id
    if mutation == "type":
        request = build_fixture_request("external-test-model")
    elif mutation == "share-id":
        approved = "another-request"
    else:
        data = context.to_dict()
        if mutation == "model":
            data["config"]["model"] = "another-model"
        else:
            data["host_instructions" if mutation == "instructions" else "prompt"] = (
                "FAKE_SECRET_UNREVIEWED_TEXT"
            )
        request = RepositoryProposalRequest(canonical(data))
    transport = CodexAppServerAdapter(approved)

    async def forbidden(*args, **kwargs):
        pytest.fail("Invalid input must fail before any transport")

    monkeypatch.setattr(transport, "_turn", forbidden)
    with pytest.raises((AppServerError, ContractError)) as error:
        asyncio.run(transport.suggest_repository(request))
    assert "FAKE_SECRET" not in str(error.value)
    assert transport.consumed is False
    assert transport.failure_diagnostic == FailureDiagnostic(
        "request-validation", "request-invalid", "not-attempted"
    )


@pytest.mark.parametrize("case", ["happy", "wrong-turn"])
def test_external_transport_is_single_use_across_existing_entry_points(
    context, repository_peer, case
):
    fake = repository_peer(case, request=context, response=response_data(context))
    transport = adapter(context, fake)
    if case == "happy":
        asyncio.run(transport.suggest_repository(context))
    else:
        with pytest.raises(AppServerError):
            asyncio.run(transport.suggest_repository(context))
    for method, request in (
        (transport.suggest_repository, context),
        (transport.draft, build_fixture_request("external-test-model")),
    ):
        with pytest.raises(AppServerError, match="fresh exact-request"):
            asyncio.run(method(request))
    assert fake.methods().count("turn/start") == 1
    assert len(fake.starts()) == 2
    assert_stopped(fake)


@pytest.mark.parametrize("mutation", ["request", "source", "syntax"])
def test_invalid_generated_data_is_redacted_and_never_becomes_file_authority(
    context, repository_peer, mutation
):
    response = response_data(context)
    if mutation == "request":
        response["request_id"] = "FAKE_SECRET_WRONG_REQUEST"
    elif mutation == "source":
        response["proposal"]["source_path"] = "FAKE_SECRET_OTHER.py"
    else:
        response["proposal"]["test_text"] = "FAKE_SECRET_INVALID_PYTHON ("
    fake = repository_peer(request=context, response=response)
    transport = adapter(context, fake)
    with pytest.raises(AppServerError) as error:
        asyncio.run(transport.suggest_repository(context))
    assert "FAKE_SECRET" not in str(error.value)
    assert transport.failure_diagnostic.stage == "response-validation"
    assert transport.failure_diagnostic.code.startswith("validation-")
    assert transport.failure_diagnostic.turn_start == "acknowledged"
    assert transport.warnings_seen is transport.retry_notifications_seen is None
    assert fake.methods().count("turn/start") == 1
    assert_stopped(fake)


@pytest.mark.parametrize("stage", ["before-thread-response", "before-turn-response", "during-turn"])
def test_external_context_remains_bound_in_settings_notifications(context, repository_peer, stage):
    fake = repository_peer(
        f"settings:{stage}:same-collaboration", request=context, response=response_data(context)
    )
    assert asyncio.run(adapter(context, fake).suggest_repository(context)) == response_data(context)
    assert_stopped(fake)


@pytest.mark.parametrize(
    "case",
    [
        "new-mcp-second-pass",
        "wrong-version",
        "tool-request",
        "settings:before-thread-response:extra-collaboration-instructions",
        "settings:during-turn:extra-collaboration-instructions",
    ],
)
def test_external_request_retains_existing_process_protocol_guards(context, repository_peer, case):
    fake = repository_peer(case, request=context, response=response_data(context))
    with pytest.raises(AppServerError) as error:
        asyncio.run(adapter(context, fake).suggest_repository(context))
    assert "FAKE_SECRET" not in str(error.value)
    assert fake.methods().count("turn/start") <= 1
    assert_stopped(fake)


def test_legacy_fixture_instructions_cannot_satisfy_external_config(context, fake_factory):
    fake = fake_factory(request=context, response=response_data(context))
    transport = adapter(context, fake)
    with pytest.raises(AppServerError, match="configuration"):
        asyncio.run(transport.suggest_repository(context))
    assert transport.failure_diagnostic == FailureDiagnostic(
        "configuration", "configuration-rejected", "not-attempted"
    )
    assert "account/read" not in fake.methods()
    assert "turn/start" not in fake.methods()
    assert_stopped(fake)


def test_instruction_selection_keeps_legacy_configuration_unchanged():
    before = copy.deepcopy(app_server.CONFIG)
    assert app_server._configuration() == before
    assert before["developer_instructions"] == HOST_INSTRUCTIONS == app_server.BASE_INSTRUCTIONS
    external = app_server._configuration(repository_proposal=True)
    assert external == {**before, "developer_instructions": REPOSITORY_HOST_INSTRUCTIONS}
    assert before == app_server.CONFIG
    assert app_server._configuration() == before


@pytest.mark.parametrize("external", [False, True], ids=["legacy", "external"])
def test_settings_cannot_switch_between_legacy_and_external_instruction_sets(external):
    session = app_server._Session(None, repository_proposal=external)
    expected = {
        "threadId": "owned-test-thread",
        "model": "external-test-model",
        "modelProvider": "openai",
        "cwd": "/owned-test-cwd",
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        "effort": "low",
    }
    session.thread_boundary = expected
    params = {
        "threadId": expected["threadId"],
        "threadSettings": {
            **{key: value for key, value in expected.items() if key != "threadId"},
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "collaborationMode": {
                "mode": "default",
                "settings": {
                    "model": expected["model"],
                    "reasoning_effort": expected["effort"],
                    "developer_instructions": (
                        HOST_INSTRUCTIONS if external else REPOSITORY_HOST_INSTRUCTIONS
                    ),
                },
            },
        },
    }
    with pytest.raises(AppServerError, match="collaboration context"):
        session.check_settings(params)


@pytest.mark.parametrize("mode", [None, 1, "external", "FAKE_SECRET_INSTRUCTIONS"])
def test_instruction_selector_never_accepts_arbitrary_caller_text(mode):
    with pytest.raises(AppServerError, match="request context") as error:
        app_server._configuration(repository_proposal=mode)
    assert "FAKE_SECRET" not in str(error.value)
