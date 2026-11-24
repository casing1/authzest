"""Owned scripted App Server peers; no account, model or target execution."""

import asyncio
import os

import pytest
from jsonschema import Draft202012Validator, ValidationError

from authzest.analyzer.repository_input import capture_repository
from authzest.codex import app_server
from authzest.codex.app_server import AppServerError, CodexAppServerAdapter
from authzest.codex.contracts import ContractError, canonical
from authzest.codex.diagnostics import FailureDiagnostic
from authzest.codex.fixture_draft import build_fixture_request
from authzest.codex.repository_http_proposal import (
    RepositoryHttpRequest,
    build_repository_http_request,
    validate_repository_http_response,
)
from authzest.codex.repository_proposal import (
    REPOSITORY_HOST_INSTRUCTIONS,
    build_repository_request,
)
from test_codex_app_server import adapter, assert_stopped
from test_codex_app_server import fake_factory as fake_factory
from test_codex_repository_proposal import calls_by_method
from test_codex_repository_proposal import repository_peer as repository_peer

pytestmark = pytest.mark.skipif(os.name != "posix", reason="App Server requires POSIX")

SOURCE = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    '@app.get("/notes/{note_id}")\n'
    "def read_note(note_id: str):\n"
    '    return {"id": note_id}\n'
)


@pytest.fixture
def http_context(tmp_path):
    (tmp_path / "service.py").write_text(SOURCE)
    (tmp_path / "policy.md").write_text("Only the specified note owner may read it.\n")
    return build_repository_http_request(
        capture_repository(tmp_path.resolve(), "service.py", "policy.md"), "http-test-model"
    )


@pytest.fixture
def context(http_context):
    """Supply the owned peer factory's existing generic request fixture."""
    return http_context


def http_response(request, status="proposed-change"):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "2.0",
        "kind": "repository-http-proposal",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Owned scripted data, not an observed authorization outcome.",
        "assumptions": ["Identity and policy require independent review."],
        "uncertainties": ["No target has run."],
        "limitations": ["The request and source remain unexecuted data."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": SOURCE + "\nowned_scripted_marker = True\n",
            "poc": {
                "method": "GET",
                "path": "/notes/one",
                "headers": [{"name": "x-user-id", "value": "test-other"}],
            },
        }
        if status == "proposed-change"
        else None,
    }


def test_provider_schema_accepts_all_statuses_and_rejects_extra_oracle_fields(http_context):
    schema = http_context.to_dict()["output_schema"]
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for status in ("proposed-change", "no-change", "unknown", "refused"):
        validator.validate(http_response(http_context, status))
    response = http_response(http_context)
    response["proposal"]["poc"]["expected_status"] = 403
    with pytest.raises(ValidationError):
        validator.validate(response)


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_http_payload_uses_external_context_and_exact_current_schema(
    http_context, repository_peer, status
):
    response = http_response(http_context, status)
    peer = repository_peer(request=http_context, response=response)
    transport = adapter(http_context, peer)
    result = asyncio.run(transport.suggest_repository_http(http_context))
    assert result == validate_repository_http_response(canonical(response), http_context)
    calls = calls_by_method(peer)
    thread, turn = calls["thread/start"], calls["turn/start"]
    assert turn["input"] == [{"type": "text", "text": http_context.to_dict()["prompt"]}]
    assert turn["outputSchema"] == http_context.to_dict()["output_schema"]
    assert turn["model"] == "http-test-model"
    assert turn["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert thread["baseInstructions"] == REPOSITORY_HOST_INSTRUCTIONS
    assert thread["developerInstructions"] == REPOSITORY_HOST_INSTRUCTIONS
    assert thread["allowProviderModelFallback"] is False
    assert thread["dynamicTools"] == thread["runtimeWorkspaceRoots"] == []
    assert peer.methods().count("turn/start") == 1
    assert len(peer.starts()) == 2
    assert transport.consumed and transport.failure_diagnostic is None
    assert app_server.SUPPORTED_CODEX_VERSION == "0.153.0"
    assert_stopped(peer)


@pytest.mark.parametrize("mutation", ["legacy-type", "prompt", "schema", "model", "share-id"])
def test_http_unreviewed_input_cannot_start_any_transport(http_context, monkeypatch, mutation):
    request, approved = http_context, http_context.request_id
    if mutation == "legacy-type":
        data = http_context.to_dict()
        from authzest.analyzer.repository_input import CapturedFile, RepositoryInput

        selection = data["selection"]
        snapshot = RepositoryInput(
            root=None,
            source=selection["source"],
            policy=selection["policy"],
            contexts=(),
            files=tuple(CapturedFile(**file) for file in selection["files"]),
        )
        request = build_repository_request(snapshot, "http-test-model")
    elif mutation == "share-id":
        approved = "other-request"
    else:
        data = http_context.to_dict()
        if mutation == "model":
            data["config"]["model"] = "other-model"
        elif mutation == "schema":
            data["output_schema"]["additionalProperties"] = True
        else:
            data["prompt"] = "FAKE_SECRET_UNREVIEWED_PROMPT"
        request = RepositoryHttpRequest(canonical(data))
    transport = CodexAppServerAdapter(approved)

    async def forbidden(*args, **kwargs):
        pytest.fail("Unreviewed request reached the transport")

    monkeypatch.setattr(transport, "_turn", forbidden)
    with pytest.raises((ContractError, AppServerError)) as error:
        asyncio.run(transport.suggest_repository_http(request))
    assert "FAKE_SECRET" not in str(error.value)
    assert not transport.consumed
    assert transport.failure_diagnostic == FailureDiagnostic(
        "request-validation", "request-invalid", "not-attempted"
    )


@pytest.mark.parametrize("method", ["suggest_repository", "draft"])
def test_legacy_entry_cannot_adopt_http_request(http_context, monkeypatch, method):
    transport = CodexAppServerAdapter(http_context.request_id)

    async def forbidden(*args, **kwargs):
        pytest.fail("HTTP request was adopted by a legacy transport entry")

    monkeypatch.setattr(transport, "_turn", forbidden)
    with pytest.raises((ContractError, AppServerError)):
        asyncio.run(getattr(transport, method)(http_context))
    assert not transport.consumed


@pytest.mark.parametrize("case", ["happy", "wrong-turn"])
def test_http_attempt_is_consumed_across_legacy_and_new_entries(
    http_context, repository_peer, case
):
    peer = repository_peer(case, request=http_context, response=http_response(http_context))
    transport = adapter(http_context, peer)
    if case == "happy":
        asyncio.run(transport.suggest_repository_http(http_context))
    else:
        with pytest.raises(AppServerError):
            asyncio.run(transport.suggest_repository_http(http_context))
    for method, request in (
        (transport.suggest_repository_http, http_context),
        (transport.draft, build_fixture_request("http-test-model")),
    ):
        with pytest.raises(AppServerError, match="fresh exact-request"):
            asyncio.run(method(request))
    assert peer.methods().count("turn/start") == 1
    assert_stopped(peer)


@pytest.mark.parametrize("mutation", ["expected-answer", "credential", "foreign-source", "syntax"])
def test_http_invalid_response_is_redacted_and_does_not_grant_authority(
    http_context, repository_peer, mutation
):
    response = http_response(http_context)
    proposal = response["proposal"]
    if mutation == "expected-answer":
        proposal["poc"]["expected_status"] = 403
    elif mutation == "credential":
        proposal["poc"]["headers"] = [{"name": "authorization", "value": "FAKE_SECRET_CREDENTIAL"}]
    elif mutation == "foreign-source":
        proposal["source_path"] = "FAKE_SECRET_OTHER.py"
    else:
        proposal["after_text"] = "FAKE_SECRET_INVALID_SYNTAX ("
    peer = repository_peer(request=http_context, response=response)
    transport = adapter(http_context, peer)
    with pytest.raises(AppServerError) as error:
        asyncio.run(transport.suggest_repository_http(http_context))
    assert "FAKE_SECRET" not in str(error.value)
    assert transport.failure_diagnostic.stage == "response-validation"
    assert transport.failure_diagnostic.turn_start == "acknowledged"
    assert peer.methods().count("turn/start") == 1
    assert_stopped(peer)


@pytest.mark.parametrize(
    "case",
    [
        "wrong-version",
        "new-mcp-second-pass",
        "tool-request",
        "settings:during-turn:extra-collaboration-instructions",
    ],
)
def test_http_entry_keeps_existing_protocol_and_tool_guards(http_context, repository_peer, case):
    peer = repository_peer(case, request=http_context, response=http_response(http_context))
    with pytest.raises(AppServerError):
        asyncio.run(adapter(http_context, peer).suggest_repository_http(http_context))
    assert peer.methods().count("turn/start") <= 1
    assert_stopped(peer)


def test_fixed_case_host_context_is_not_accepted_for_http_request(http_context, fake_factory):
    peer = fake_factory(request=http_context, response=http_response(http_context))
    transport = adapter(http_context, peer)
    with pytest.raises(AppServerError, match="configuration"):
        asyncio.run(transport.suggest_repository_http(http_context))
    assert "account/read" not in peer.methods()
    assert "turn/start" not in peer.methods()
    assert_stopped(peer)
