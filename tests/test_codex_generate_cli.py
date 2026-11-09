"""Memory-only workflow/CLI tests, not live generation or a validated repair."""

import asyncio
import builtins
import io
import json
import os
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.contracts import canonical, identity
from authzest.codex.diagnostics import FailureDiagnostic
from authzest.codex.generated_repair_transport import (
    GeneratedRepairTransportResult,
    prepare_generated_repair_transport_result,
)
from authzest.runner import codex_generated_repair as workflow
from test_generated_repair import draft
from test_generated_repair_transport import inner

MODEL = "offline-generation-test-model"
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_live_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline generation tests cannot start providers, processes or network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    connect = socket.socket.connect
    policy = asyncio.get_event_loop_policy()
    create_loop = policy.new_event_loop

    def new_event_loop():
        # Windows constructs a private socketpair while initializing its loop.
        with monkeypatch.context() as initialization:
            initialization.setattr(socket.socket, "connect", connect)
            return create_loop()

    monkeypatch.setattr(policy, "new_event_loop", new_event_loop)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(workflow, "_default_adapter_factory", forbidden)
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))


def exact_choice(prompt):
    return prompt.split("'")[1]


def fake_result(request, status="proposed-change", *, controls=False):
    raw = draft(inner(request), status)
    if controls:
        # C0 ESC is rejected by the contract; C1 CSI/bidi still need escaping.
        raw["rationale"] = "untrusted \u009b31m rationale \u202e"
        if raw["proposal"]:
            raw["proposal"]["after_text"] += "# untrusted \u009b31m source \u202e\n"
            raw["proposal"]["test_text"] += "# untrusted \u009b31m test \u202e\n"
    return prepare_generated_repair_transport_result(
        canonical(raw), request, usage={"input_tokens": 10, "output_tokens": 20}
    )


def run(**kwargs):
    return asyncio.run(workflow.run_codex_generated_repair(MODEL, emit=lambda _: None, **kwargs))


def assert_no_execution(result):
    assert result["applied"] is result["original_checkout_modified"] is False
    assert result["execution_status"] == result["patch_application"] == "not-run"
    assert result["restoration_status"] == "not-run"
    assert result["authorization_status"] == "unknown"


def test_portable_preview_is_complete_without_source_account_or_file_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Generation preview may not consult files or an account")

    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="nt"))
    value = workflow.build_generated_repair_sharing_preview(MODEL)
    envelope = value["transport_request"]
    assert value["kind"] == "codex-generated-repair-sharing-preview"
    assert envelope["config"]["model"] == MODEL
    assert value["generation_request_id"] == envelope["request_id"]
    for name in ("prompt", "output_schema", "host_instructions"):
        assert value[name] == envelope[name]
    assert value["limits"]["max_application_turn_attempts"] == 1
    assert value["limits"]["application_retries"] == 0
    assert value["limits"]["token_hard_cap"] is None
    assert value["limits"]["codex_internal_transport_retries_hard_capped"] is False
    assert "after-template" in value["source_scope"]
    assert envelope["request"]["scenario"]["policy_review"] == "pending-maintainer-review"


def test_fresh_challenge_binds_every_displayed_field_model_timeout_and_nonce():
    preview = workflow.build_generated_repair_sharing_preview(MODEL, invocation_nonce="1" * 32)
    assert preview == workflow.build_generated_repair_sharing_preview(
        MODEL, invocation_nonce="1" * 32
    )
    challenged = {key: value for key, value in preview.items() if key != "sharing_id"}
    assert preview["sharing_id"] == "share-" + identity(challenged)
    content = {
        key: value
        for key, value in challenged.items()
        if key not in {"sharing_content_id", "invocation_nonce"}
    }
    assert preview["sharing_content_id"] == "content-" + identity(content)
    fresh = workflow.build_generated_repair_sharing_preview(MODEL)
    assert fresh["sharing_content_id"] == preview["sharing_content_id"]
    assert fresh["sharing_id"] != preview["sharing_id"]
    for options in ({"model": "other-model"}, {"model": MODEL, "timeout_seconds": 1}):
        changed = workflow.build_generated_repair_sharing_preview(**options)
        assert changed["sharing_content_id"] != preview["sharing_content_id"]


@pytest.mark.parametrize("value", [None, True, "", " ", "bad\nmodel", "x" * 129])
def test_invalid_models_are_closed_input_errors(value):
    with pytest.raises(workflow.GeneratedRepairInputError):
        workflow.build_generated_repair_sharing_preview(value)


@pytest.mark.parametrize("value", [True, "1", 0, -1, 121, float("inf"), float("nan")])
def test_invalid_timeout_is_rejected(value):
    with pytest.raises(workflow.GeneratedRepairInputError):
        workflow.build_generated_repair_sharing_preview(MODEL, timeout_seconds=value)


@pytest.mark.parametrize("nonce", [1, "", "A" * 32, "1" * 31])
def test_invalid_nonce_is_rejected(nonce):
    with pytest.raises(workflow.GeneratedRepairInputError):
        workflow.build_generated_repair_sharing_preview(MODEL, invocation_nonce=nonce)


@pytest.mark.parametrize(
    "answer,decision", [("", "decline"), ("yes", "decline"), ("cancel", "cancel")]
)
def test_decline_cancel_never_constructs_adapter(answer, decision):
    result = run(read=lambda _: answer)
    assert result["status"] == "not-shared"
    assert result["sharing_decision"] == decision
    assert result["application_turn_attempts"] == 0
    assert result["generation"] is result["proposal_preview"] is result["usage"] is None
    assert_no_execution(result)


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_input_interruption_cancels_without_call(error):
    def read(_):
        raise error

    assert run(read=read)["sharing_decision"] == "cancel"


def test_old_phrase_does_not_authorize_a_fresh_invocation():
    old = workflow.build_generated_repair_sharing_preview(MODEL)
    result = run(read=lambda _: "share " + old["sharing_id"])
    assert result["status"] == "not-shared" and result["application_turn_attempts"] == 0


@pytest.mark.parametrize(
    "field", ["prompt", "output_schema", "host_instructions", "limits", "transport_request"]
)
def test_displayed_content_change_rejected_before_adapter(monkeypatch, field):
    original = workflow.build_generated_repair_sharing_preview
    calls = 0

    def altered(*args, **kwargs):
        nonlocal calls
        calls += 1
        value = original(*args, **kwargs)
        if calls == 2:
            value[field] = None
        return value

    monkeypatch.setattr(workflow, "build_generated_repair_sharing_preview", altered)
    result = run(read=exact_choice)
    assert result["status"] == "preview-changed"
    assert result["failure"]["turn_start"] == "not-attempted"
    assert result["application_turn_attempts"] == 0
    assert_no_execution(result)


def test_non_posix_preview_decline_portable_but_active_share_rejected(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="nt"))
    assert run(read=lambda _: "")["status"] == "not-shared"
    with pytest.raises(workflow.GeneratedRepairInputError, match="POSIX"):
        run(read=exact_choice)


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_exact_share_calls_once_and_preserves_distinct_proposal_status_without_authority(status):
    calls = []

    class Adapter:
        warnings_seen = 2
        retry_notifications_seen = 1

        def __init__(self, **kwargs):
            calls.append(kwargs)

        async def generate_repair(self, request):
            calls.append(request.request_id)
            return fake_result(request, status)

    result = run(read=exact_choice, adapter_factory=Adapter)
    assert len(calls) == 2
    assert calls[0] == {"approved_request_id": result["request_id"], "timeout_seconds": 120}
    assert calls[1] == result["request_id"]
    assert result["status"] == "generation-ready"
    assert result["proposal_status"] == result["proposal_preview"]["status"] == status
    assert len(result["proposal_preview"]["changes"]) == (2 if status == "proposed-change" else 0)
    assert result["proposal_preview"]["python_validation"] == "ast-parse-only"
    assert result["proposal_preview"]["provider_calls_made_by_this_function"] == 0
    assert result["application_turn_attempts"] == 1
    assert "local adapter calls" in result["attempt_count_basis"]
    assert result["returned_identity"]["model"] == MODEL
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 20}
    assert result["provider_warning_count"] == 2
    assert result["provider_retry_notification_count"] == 1
    assert_no_execution(result)


@pytest.mark.parametrize(
    "case",
    [
        "factory",
        "adapter",
        "timeout",
        "wrong-type",
        "stale-result",
        "bad-proposal",
        "stale-source",
        "oversized",
        "escape-control",
    ],
)
def test_failures_are_redacted_with_no_partial_generation_or_retries(case):
    attempts = []

    class Adapter:
        failure_diagnostic = FailureDiagnostic("turn-start", "transport-error", "attempted")

        def __init__(self, **kwargs):
            attempts.append("factory")
            if case == "factory":
                raise ValueError("FAKE_SECRET_ACCOUNT")

        async def generate_repair(self, request):
            attempts.append("adapter")
            if case == "adapter":
                raise ValueError("FAKE_SECRET_PROVIDER")
            if case == "timeout":
                await asyncio.sleep(1)
            if case == "wrong-type":
                return {"FAKE_SECRET": True}
            data = fake_result(request).to_dict()
            if case == "stale-result":
                data["request_id"] = "FAKE_SECRET_STALE"
            elif case == "stale-source":
                data["proposal"]["proposal"]["before_sha256"] = "0" * 64
            elif case == "oversized":
                data["proposal"]["proposal"]["test_text"] = "#" + "x" * 16_384
            elif case == "escape-control":
                data["proposal"]["rationale"] = "FAKE_SECRET\x1b[31m"
            else:
                data["proposal"]["proposal"]["source_path"] = "FAKE_SECRET_OTHER.py"
            return GeneratedRepairTransportResult(canonical(data))

    result = run(read=exact_choice, adapter_factory=Adapter, timeout_seconds=0.03)
    assert result["status"] == "generation-failed" and result["exit_code"] == 1
    assert attempts == (["factory"] if case == "factory" else ["factory", "adapter"])
    assert result["application_turn_attempts"] == (0 if case == "factory" else 1)
    assert result["generation"] is result["proposal_preview"] is result["usage"] is None
    assert result["returned_identity"] is result["provider_warning_count"] is None
    assert "FAKE_SECRET" not in json.dumps(result)
    assert_no_execution(result)


def test_external_cancellation_propagates_without_retry():
    class Adapter:
        def __init__(self, **kwargs):
            pass

        async def generate_repair(self, request):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        run(read=exact_choice, adapter_factory=Adapter)


@pytest.mark.parametrize("color", [False, True])
def test_cli_help_documents_explicit_model_and_preview_without_approval_flags(color):
    result = runner.invoke(app, ["codex-generate", "--help"], color=color)
    text = unstyle(result.stdout)
    assert result.exit_code == 0
    for flag in ("--model", "--timeout-seconds", "--preview-only", "--json"):
        assert flag in text
    assert "--apply" not in text and "--yes" not in text


def test_cli_preview_json_is_one_complete_document_without_interaction():
    result = runner.invoke(app, ["codex-generate", "--model", MODEL, "--preview-only", "--json"])
    assert result.exit_code == 0 and not result.stderr
    value = json.loads(result.stdout)
    assert value["kind"] == "codex-generated-repair-sharing-preview"
    assert value["transport_request"]["config"]["model"] == MODEL


def test_cli_decline_json_stdout_is_one_result_with_full_preview_and_prompt_on_stderr():
    result = runner.invoke(app, ["codex-generate", "--model", MODEL, "--json"], input="\n")
    assert result.exit_code == 0
    value = json.loads(result.stdout)
    assert value["status"] == "not-shared" and value["application_turn_attempts"] == 0
    assert "codex-generated-repair-sharing-preview" in result.stderr
    assert "REQUEST_JSON" in result.stderr and "Type 'share " in result.stderr


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_mock_generation_escapes_model_source_test_rationale_and_keeps_one_json(
    monkeypatch, as_json
):
    async def scripted(model, **kwargs):
        class Adapter:
            def __init__(self, **options):
                pass

            async def generate_repair(self, request):
                return fake_result(request, controls=True)

        return await original(model, **{**kwargs, "read": exact_choice}, adapter_factory=Adapter)

    original = workflow.run_codex_generated_repair
    monkeypatch.setattr(workflow, "run_codex_generated_repair", scripted)
    args = ["codex-generate", "--model", MODEL] + (["--json"] if as_json else [])
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert (
        "\x1b" not in result.stdout
        and "\u009b" not in result.stdout
        and "\u202e" not in result.stdout
    )
    assert "\\u009b" in result.stdout and "\\u202e" in result.stdout
    if as_json:
        value = json.loads(result.stdout)
        assert value["status"] == "generation-ready"
        assert "REQUEST_JSON" in result.stderr
    else:
        assert "Locally composed generated-source diff" in result.stdout
        assert "Exact diff (each line is quoted)" in result.stdout
        assert "ast-parse-only" in result.stdout and "not-assessed" in result.stdout


@pytest.mark.parametrize("case", ["input", "unexpected", "cancelled"])
def test_cli_errors_are_redacted_single_json(monkeypatch, case):
    async def fail(*args, **kwargs):
        if case == "input":
            raise workflow.GeneratedRepairInputError("Closed input error")
        if case == "cancelled":
            raise asyncio.CancelledError
        raise RuntimeError("FAKE_SECRET_PROVIDER_PAYLOAD")

    monkeypatch.setattr(workflow, "run_codex_generated_repair", fail)
    result = runner.invoke(app, ["codex-generate", "--model", MODEL, "--json"])
    assert result.exit_code == {"input": 2, "unexpected": 1, "cancelled": 130}[case]
    value = json.loads(result.stdout)
    assert (
        value["status"]
        == {"input": "invalid-input", "unexpected": "generation-failed", "cancelled": "cancelled"}[
            case
        ]
    )
    assert "FAKE_SECRET" not in result.stdout + result.stderr


@pytest.mark.parametrize("flag", ["--yes", "--apply", "--file-workflow", "--path"])
def test_no_bypass_arbitrary_repo_or_application_cli_option(flag):
    result = runner.invoke(app, ["codex-generate", "--model", MODEL, flag])
    assert result.exit_code == 2
