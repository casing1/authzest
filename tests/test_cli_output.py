"""Offline presentation/stream contracts; output is never permission or executable text."""

import asyncio
import builtins
import json
import socket
import subprocess
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from authzest.cli import app
from authzest.cli_output import WorkflowOutput, format_record, format_sharing_preview, section
from authzest.codex.contracts import canonical, decode
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.codex.mock import scripted_response
from authzest.codex.owner_policy_review import OwnerPolicyReview, validate_owner_policy_draft
from authzest.runner import codex_fixture, codex_owner_review, fixture_check, fixture_demo
from authzest.runner._fixture_workspace import supported

MODEL = "offline-output-test-model"
NONCE = "1" * 32
runner = CliRunner()


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Presentation tests must not use a real provider, child or network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    policy = asyncio.get_event_loop_policy()
    new_loop = policy.new_event_loop
    connect = socket.socket.connect

    def initialize_loop():
        with monkeypatch.context() as initialization:
            initialization.setattr(socket.socket, "connect", connect)
            return new_loop()

    monkeypatch.setattr(policy, "new_event_loop", initialize_loop)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(codex_owner_review, "_default_adapter_factory", forbidden)
    monkeypatch.setattr(codex_fixture, "_default_adapter_factory", forbidden)
    monkeypatch.setattr(codex_owner_review.secrets, "token_hex", lambda size: NONCE)


def test_complete_sharing_envelope_is_recoverable_without_summary_loss():
    preview = codex_owner_review.build_owner_review_preview(MODEL, invocation_nonce=NONCE)
    text = format_sharing_preview(preview)
    complete = text.split("review every field before consent)\n", 1)[1]
    assert json.loads(complete) == preview
    assert all(
        key in complete
        for key in (
            "request",
            "host_instructions",
            "prompt",
            "output_schema",
            "limits",
            "invocation_nonce",
            "sharing_id",
            "sharing_content_id",
            "prompt_sha256",
            "output_schema_sha256",
        )
    )
    assert text.isascii() and "no approval implied" in text


def test_terminal_controls_keys_bidi_and_diff_are_quoted_not_executed():
    untrusted = "\x1b[2J\u202e검토\n$(do-not-run)"
    diff = "--- a/main.py\n+++ b/main.py\n+" + untrusted + "\n"
    text = section("Changes", {untrusted: untrusted, "diff": diff})
    assert text.isascii() and "\x1b" not in text and "\u202e" not in text
    assert "\\u001b" in text and "\\u202e" in text
    assert all(json.dumps(line, ensure_ascii=True) in text for line in diff.split("\n"))


def test_missing_observations_are_unknown_without_fabricated_not_run_or_pass():
    text = format_record({"status": "workflow-failed", "usage": None, "verification": None})
    assert '"usage": null (unknown; not reported)' in text
    assert "Verification result\nnull" in text
    assert "not-run" not in text and '"status": "passed"' not in text
    assert "not an authorization/security pass" in text


def test_prompt_uses_stderr_and_preserves_exact_answer(monkeypatch, capsys):
    answer = " share wrong "
    monkeypatch.setattr(builtins, "input", lambda: answer)
    assert WorkflowOutput(True).read("Type 'share exact' to confirm: ") == answer
    streams = capsys.readouterr()
    assert streams.out == "" and streams.err == "Type 'share exact' to confirm: "


@pytest.mark.parametrize("as_json", [False, True])
def test_offline_preview_default_and_json_are_complete(as_json):
    args = ["codex-owner-review", "--model", MODEL, "--preview-only"]
    result = runner.invoke(app, args + (["--json"] if as_json else []))
    assert result.exit_code == 0 and result.stderr == ""
    expected = codex_owner_review.build_owner_review_preview(MODEL, invocation_nonce=NONCE)
    if as_json:
        assert json.loads(result.stdout) == expected
    else:
        assert result.stdout.startswith("Source-sharing preview")
        assert (
            json.loads(result.stdout.split("review every field before consent)\n", 1)[1])
            == expected
        )


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("choice", ["approve", "decline", "cancel", "stale"])
def test_real_owner_workflow_streams_consent_cases_and_unknown_usage(monkeypatch, as_json, choice):
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)

        class Fake:
            async def review_owner_policy(self, request):
                payload = request.to_dict()
                answers = decode(
                    scripted_response(
                        request, {question["id"]: None for question in payload["questions"]}
                    )
                )["answers"]
                evidence = [item["id"] for item in payload["evidence"]]
                for answer in answers:
                    answer["evidence_ids"] = evidence
                return validate_owner_policy_draft(
                    canonical(
                        {
                            "answers": answers,
                            "cases": [
                                {
                                    "id": "missing-context",
                                    "principal": None,
                                    "report": None,
                                    "expected": False,
                                    "reason": "Draft only; missing context must be reviewed",
                                    "evidence_ids": evidence,
                                }
                            ],
                        }
                    ),
                    request,
                    usage=None,
                )

        return Fake()

    monkeypatch.setattr(codex_owner_review, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(codex_owner_review, "_default_adapter_factory", factory)
    preview = codex_owner_review.build_owner_review_preview(MODEL, invocation_nonce=NONCE)
    answer = {
        "approve": f"share {preview['sharing_id']}",
        "decline": "",
        "cancel": "cancel",
        "stale": "share stale-identity",
    }[choice]
    result = runner.invoke(
        app,
        ["codex-owner-review", "--model", MODEL] + (["--json"] if as_json else []),
        input=answer + "\n",
    )
    assert result.exit_code == 0 and len(calls) == (1 if choice == "approve" else 0)
    assert result.stdout.isascii() and result.stderr.isascii()
    assert "\x1b" not in result.output and "\u202e" not in result.output
    if as_json:
        final = json.loads(result.stdout)  # One object, no prompt or preview prefix.
        assert final["execution_status"] == "not-run" and final["authorization_status"] == "unknown"
        assert final["usage"] is None
        assert final["status"] == ("draft-ready" if choice == "approve" else "not-shared")
        assert json.loads(result.stderr.split("\nType 'share ", 1)[0]) == preview
        if choice == "approve":
            assert final["draft"]["case_review_status"] == "unreviewed"
            assert final["draft"]["case_authorship"] == "model-authored"
            assert final["draft"]["cases"][0]["expected"] is False
    else:
        assert "Complete sharing envelope" in result.stdout
        assert "Workflow result" in result.stdout and "unknown; not reported" in result.stdout
        if choice == "approve":
            assert '"case_review_status": "unreviewed"' in result.stdout
            assert '"case_authorship": "model-authored"' in result.stdout
            assert '"expected": false' in result.stdout
    assert "Type 'share " in result.stderr and "Type 'share " not in result.stdout


@pytest.mark.parametrize(
    "command,module",
    [
        ("codex-owner-review", codex_owner_review),
        ("codex-fixture", codex_fixture),
        ("fixture-demo", fixture_demo),
    ],
)
@pytest.mark.parametrize("failure,exit_code", [(RuntimeError, 1), (asyncio.CancelledError, 130)])
@pytest.mark.parametrize("as_json", [False, True])
def test_failure_and_cancellation_never_expose_exception_text(
    monkeypatch,
    command,
    module,
    failure,
    exit_code,
    as_json,
):
    async def fail(*args, **kwargs):
        raise failure("PRIVATE OUTPUT / \x1b[31m")

    function = {
        "codex-owner-review": "run_codex_owner_review",
        "codex-fixture": "run_codex_fixture",
        "fixture-demo": "run_fixture_demo",
    }[command]
    monkeypatch.setattr(module, function, fail)
    args = [command] + ([] if command == "fixture-demo" else ["--model", MODEL])
    result = runner.invoke(app, args + (["--json"] if as_json else []))
    assert result.exit_code == exit_code and "PRIVATE OUTPUT" not in result.output
    if as_json:
        assert json.loads(result.stdout)["status"] != "completed"
        assert result.stderr == ""
    else:
        assert (
            "Workflow result" in result.stdout
            and "not an authorization/security pass" in result.stdout
        )


@pytest.mark.parametrize("command", ["codex-owner-review", "codex-fixture"])
def test_invalid_command_input_has_one_json_failure_on_stdout(command):
    result = runner.invoke(app, [command, "--model", "bad model", "--json"])
    assert result.exit_code == 2 and result.stderr == ""
    assert json.loads(result.stdout)["status"] == "invalid-input"


@pytest.mark.parametrize("as_json", [False, True])
def test_owner_cli_rejects_invalid_provider_draft_without_leaking_or_inventing_usage(
    monkeypatch, as_json
):
    calls = []

    class Invalid:
        async def review_owner_policy(self, request):
            calls.append(request.request_id)
            return OwnerPolicyReview("PRIVATE INVALID MODEL CONTENT / \x1b[2J")

    monkeypatch.setattr(codex_owner_review, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(codex_owner_review, "_default_adapter_factory", lambda **_: Invalid())
    preview = codex_owner_review.build_owner_review_preview(MODEL, invocation_nonce=NONCE)
    result = runner.invoke(
        app,
        ["codex-owner-review", "--model", MODEL] + (["--json"] if as_json else []),
        input=f"share {preview['sharing_id']}\n",
    )
    assert result.exit_code == 1 and calls == [preview["request_id"]]
    assert "PRIVATE INVALID MODEL" not in result.output and "\x1b" not in result.output
    if as_json:
        final = json.loads(result.stdout)
        assert final["status"] == "review-failed" and final["draft"] is None
        assert final["usage"] is None and final["authorization_status"] == "unknown"
        assert final["execution_status"] == "not-run"
        assert final["failure"]["code"] == "validation-json"
        assert final["failure"]["stage"] == "result-validation"
    else:
        assert '"usage": null (unknown; not reported)' in result.stdout
        assert '"code": "validation-json"' in result.stdout
        assert "Redacted failure diagnostic" in result.stdout


@pytest.mark.skipif(not supported(), reason="POSIX copy workflow")
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("choice", ["approve", "skip-verify", "decline", "cancel"])
def test_readable_mock_copy_flow_preserves_separate_decisions_and_record(
    monkeypatch, tmp_path, as_json, choice
):
    prompts = []
    checks = []
    original_read = WorkflowOutput.read
    original_run = fixture_demo.run_fixture_demo

    def read(self, prompt):
        prompts.append(prompt)
        return original_read(self, prompt)

    def answer():
        prompt = prompts[-1]
        if "'apply " in prompt and choice in {"decline", "cancel"}:
            return "" if choice == "decline" else "cancel"
        if "'verify " in prompt and choice == "skip-verify":
            return ""
        return prompt.split("'")[1]  # Test-owned responses, not authenticated consent.

    async def isolated(**kwargs):
        return await original_run(**kwargs, parent=tmp_path)

    async def fixed_check(source):
        assert source == FIXTURE_AFTER.encode()
        checks.append(source)
        return fixture_check.VerificationOutcome(
            "passed",
            "debug-disabled",
            fixture_check.CHECK_ID,
            sha256(source).hexdigest(),
            fixture_check.WORKER_SHA256,
            0.0,
            0,
        )  # Scripted outcome: no worker, application or model is executed.

    monkeypatch.setattr(WorkflowOutput, "read", read)
    monkeypatch.setattr(builtins, "input", answer)
    monkeypatch.setattr(fixture_demo, "run_fixture_demo", isolated)
    monkeypatch.setattr(fixture_check, "run_configuration_check", fixed_check)
    result = runner.invoke(app, ["fixture-demo"] + (["--json"] if as_json else []))
    assert result.exit_code == 0
    assert len(prompts) == (3 if choice in {"approve", "skip-verify"} else 1)
    assert len(checks) == (1 if choice == "approve" else 0)
    assert all(prompt in result.stderr for prompt in prompts)
    assert all(prompt not in result.stdout for prompt in prompts)
    workspaces = list(tmp_path.iterdir())
    assert len(workspaces) == 1
    record = json.loads(workspaces[0].joinpath("record.json").read_text())
    assert workspaces[0].joinpath("main.py").read_text() == FIXTURE_SOURCE
    if as_json:
        final = json.loads(result.stdout)
        assert Path(final["workspace"]) == workspaces[0]
        assert final["live_provider_calls"] == 0 and final["simulated_draft"] is True
        assert final["draft_provenance"] == "caller-authored-mock"
        assert final["decisions_authenticated"] is False
        if choice in {"approve", "skip-verify"}:
            assert final["application"]["status"] == "applied"
            assert final["restoration"]["status"] == "restored"
            assert final["verification"]["status"] == (
                "passed" if choice == "approve" else "not-run"
            )
        else:
            assert final["application"]["status"] == (
                "declined" if choice == "decline" else "cancelled"
            )
            assert final["verification"] is final["restoration"] is None
        assert final["runtime_verification_status"] == "not-run"
    else:
        assert '"draft_provenance": "caller-authored-mock"' in result.stdout
        assert (
            "Workflow result" in result.stdout
            and "Exact diff (each line is quoted)" in result.stdout
        )
        assert "not an authorization/security pass" in result.stdout
    assert record["applied"] == record["restored"] == (choice in {"approve", "skip-verify"})
