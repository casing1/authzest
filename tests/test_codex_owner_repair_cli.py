"""Memory-only sharing and CLI checks; no provider, policy execution or file edits."""

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
from authzest.cli_output import WorkflowOutput
from authzest.codex.contracts import canonical, identity
from authzest.codex.diagnostics import FailureDiagnostic
from authzest.codex.owner_policy_repair_transport import (
    OwnerPolicyRepairTransportResult,
    prepare_owner_policy_repair_transport_result,
)
from authzest.runner import codex_owner_repair as workflow
from authzest.runner.codex_owner_review import build_owner_review_preview

MODEL = "owner-repair-test-model"
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_live_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline tests must not invoke a provider, external process or network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    connect = socket.socket.connect
    policy = asyncio.get_event_loop_policy()
    create_loop = policy.new_event_loop

    def new_event_loop():
        # Windows uses connect() solely while constructing its private socketpair.
        # Restore it only during construction, never during test/workflow work.
        with monkeypatch.context() as initialization:
            initialization.setattr(socket.socket, "connect", connect)
            return create_loop()

    monkeypatch.setattr(policy, "new_event_loop", new_event_loop)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(workflow, "_default_adapter_factory", forbidden)


def exact_choice(prompt):
    return prompt.split("'")[1]


def fake_result(request, status="registered-change", *, rationale=None):
    transport = request.to_dict()
    content = transport["request"]
    raw = {
        "schema_version": "1.0",
        "request_id": transport["request_id"],
        "status": status,
        "rationale": rationale or "Scripted static reasoning, not model or runtime evidence.",
        "evidence_ids": list(content["evidence_ids"].values()),
        "case_ids": [case["case_id"] for case in content["content"]["cases"]],
        "assumptions": ["The synthetic principal and ownership claims are trusted inputs."],
        "uncertainties": ["No runtime observations are available."],
        "expected_effects": ["Only the registered ownership predicate is considered."],
        "limitations": ["No policy was executed and no HTTP enforcement was tested."],
        "change_pair_id": content["registry"]["pair_id"] if status == "registered-change" else None,
    }
    return prepare_owner_policy_repair_transport_result(
        canonical(raw), request, usage={"input_tokens": 10, "output_tokens": 20}
    )


def test_preview_is_portable_and_never_reads_sources_or_account_files(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Packaged repair preview must not read or write files")

    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="nt"))
    preview = workflow.build_owner_repair_preview(MODEL)
    assert preview["kind"] == "codex-owner-repair-sharing-preview"
    assert preview["limits"]["max_application_turn_attempts"] == 1
    assert preview["limits"]["application_retries"] == 0
    assert preview["limits"]["token_hard_cap"] is None
    assert preview["limits"]["codex_internal_transport_retries_hard_capped"] is False
    for key in ("transport_request", "prompt", "output_schema", "host_instructions"):
        assert preview[key]
    envelope = preview["transport_request"]
    assert envelope["request"]["candidate"] == "before"
    assert envelope["config"]["model"] == MODEL
    assert preview["recommendation_request_id"] == envelope["request_id"]
    assert preview["request_id"] != preview["recommendation_request_id"]
    for key in ("prompt", "output_schema", "host_instructions"):
        assert preview[key] == envelope[key]


def test_complete_preview_has_stable_content_and_fresh_confirmation_identity():
    nonce = "1" * 32
    preview = workflow.build_owner_repair_preview(MODEL, invocation_nonce=nonce)
    assert preview == workflow.build_owner_repair_preview(MODEL, invocation_nonce=nonce)
    challenged = {key: value for key, value in preview.items() if key != "sharing_id"}
    assert preview["sharing_id"] == "share-" + identity(challenged)
    content = {
        key: value
        for key, value in challenged.items()
        if key not in {"sharing_content_id", "invocation_nonce"}
    }
    assert preview["sharing_content_id"] == "content-" + identity(content)
    fresh = workflow.build_owner_repair_preview(MODEL)
    assert fresh["sharing_id"] != preview["sharing_id"]
    assert fresh["invocation_nonce"] != preview["invocation_nonce"]
    assert fresh["sharing_content_id"] == preview["sharing_content_id"]
    for options in (
        {"model": "different-model"},
        {"model": MODEL, "candidate": "after"},
        {"model": MODEL, "timeout_seconds": 60},
    ):
        changed = workflow.build_owner_repair_preview(**options, invocation_nonce=nonce)
        assert changed["sharing_content_id"] != preview["sharing_content_id"]
        assert changed["sharing_id"] != preview["sharing_id"]


@pytest.mark.parametrize(
    "options",
    [
        {"model": "bad model"},
        {"model": None},
        {"model": MODEL, "candidate": "arbitrary.py"},
        {"model": MODEL, "candidate": None},
        {"model": MODEL, "timeout_seconds": 0},
        {"model": MODEL, "timeout_seconds": 121},
        {"model": MODEL, "timeout_seconds": float("nan")},
        {"model": MODEL, "timeout_seconds": True},
        {"model": MODEL, "invocation_nonce": "A" * 32},
    ],
)
def test_invalid_preview_input_is_rejected_without_provider_use(options):
    with pytest.raises(workflow.OwnerRepairInputError):
        workflow.build_owner_repair_preview(**options)


@pytest.mark.parametrize("answer", ["", "cancel", "approve", "share wrong"])
def test_decline_or_cancel_never_constructs_adapter(answer):
    emitted = []
    result = asyncio.run(
        workflow.run_codex_owner_repair(MODEL, read=lambda _: answer, emit=emitted.append)
    )
    assert result["status"] == "not-shared" and result["exit_code"] == 0
    assert result["sharing_decision"] == ("cancel" if answer == "cancel" else "decline")
    assert result["application_turn_attempts"] == 0
    assert result["usage"] is None and result["latency_ms"] is None
    assert result["failure"] is None
    assert result["execution_status"] == "not-run"
    assert result["original_checkout_modified"] is False
    assert result["sharing_id"] == json.loads(emitted[0])["sharing_id"]


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_interrupted_confirmation_cancels_before_account_use(error):
    def interrupt(_):
        raise error

    result = asyncio.run(
        workflow.run_codex_owner_repair(MODEL, read=interrupt, emit=lambda _: None)
    )
    assert result["status"] == "not-shared"
    assert result["sharing_decision"] == "cancel"
    assert result["application_turn_attempts"] == 0


def test_previous_preview_phrase_cannot_authorize_fresh_invocation():
    preview = workflow.build_owner_repair_preview(MODEL)
    result = asyncio.run(
        workflow.run_codex_owner_repair(
            MODEL, read=lambda _: "share " + preview["sharing_id"], emit=lambda _: None
        )
    )
    assert result["sharing_decision"] == "decline"
    assert result["application_turn_attempts"] == 0
    assert result["sharing_content_id"] == preview["sharing_content_id"]
    assert result["sharing_id"] != preview["sharing_id"]


def test_content_change_after_display_requires_new_confirmation(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    original = workflow.build_owner_repair_preview

    def read(prompt):
        def altered(*args, **kwargs):
            preview = original(*args, **kwargs)
            preview["host_instructions"] += " modified after display"
            return preview

        monkeypatch.setattr(workflow, "build_owner_repair_preview", altered)
        return exact_choice(prompt)

    result = asyncio.run(workflow.run_codex_owner_repair(MODEL, read=read, emit=lambda _: None))
    assert result["status"] == "preview-changed" and result["exit_code"] == 1
    assert result["application_turn_attempts"] == 0
    assert result["failure"] == {
        "stage": "request-validation",
        "code": "request-invalid",
        "turn_start": "not-attempted",
    }


def test_non_posix_may_preview_or_decline_but_not_share(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="nt"))
    declined = asyncio.run(
        workflow.run_codex_owner_repair(MODEL, read=lambda _: "", emit=lambda _: None)
    )
    assert declined["status"] == "not-shared"
    with pytest.raises(workflow.OwnerRepairInputError, match="POSIX"):
        asyncio.run(workflow.run_codex_owner_repair(MODEL, read=exact_choice, emit=lambda _: None))


@pytest.mark.parametrize(
    "candidate,status",
    [
        ("before", "registered-change"),
        ("before", "no-change"),
        ("before", "unknown"),
        ("after", "no-change"),
        ("after", "unknown"),
    ],
)
def test_exact_share_calls_once_and_returns_only_unexecuted_recommendation(
    candidate, status, monkeypatch
):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    constructed, called, output = [], [], []

    def factory(**kwargs):
        constructed.append(kwargs)

        class Fake:
            warnings_seen = 0
            retry_notifications_seen = 0

            async def recommend_owner_policy_repair(self, request):
                called.append(request)
                return fake_result(request, status)

        return Fake()

    result = asyncio.run(
        workflow.run_codex_owner_repair(
            MODEL,
            candidate=candidate,
            timeout_seconds=13,
            read=exact_choice,
            emit=output.append,
            adapter_factory=factory,
        )
    )
    assert len(constructed) == len(called) == result["application_turn_attempts"] == 1
    assert constructed[0]["approved_request_id"] == result["request_id"] == called[0].request_id
    assert constructed[0]["timeout_seconds"] == result["limits"]["timeout_seconds"] == 13
    assert called[0].to_dict() == json.loads(output[0])["transport_request"]
    assert result["status"] == "recommendation-ready" and result["exit_code"] == 0
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 20}
    assert result["recommendation"]["recommendation"]["status"] == status
    assert result["returned_identity"]["model"] == MODEL
    preview = result["recommendation_preview"]
    assert preview["recommendation"]["status"] == status
    assert (preview["pair_preview"] is not None) == (status == "registered-change")
    assert preview["observations"] == {"before": None, "after": None}
    assert preview["patch_application"] == preview["restoration_status"] == "not-run"
    assert result["execution_status"] == "not-run"
    assert result["authorization_status"] == "unknown"
    assert result["original_checkout_modified"] is False
    assert result["failure"] is None


@pytest.mark.parametrize("failure", ["exception", "forged-result", "timeout"])
def test_failed_or_mismatched_result_is_redacted_and_never_retried(failure, monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    calls, cleanup, output = [], [], []
    sentinel = "PRIVATE PROVIDER RESPONSE OR TOKEN"

    class Failing:
        async def recommend_owner_policy_repair(self, request):
            calls.append(request.request_id)
            if failure == "exception":
                raise RuntimeError(sentinel)
            if failure == "forged-result":
                payload = fake_result(request).to_dict()
                payload["request_id"] = sentinel
                return OwnerPolicyRepairTransportResult(canonical(payload))
            try:
                await asyncio.Event().wait()
            finally:
                cleanup.append(True)

    result = asyncio.run(
        workflow.run_codex_owner_repair(
            MODEL,
            timeout_seconds=0.01,
            read=exact_choice,
            emit=output.append,
            adapter_factory=lambda **_: Failing(),
        )
    )
    assert len(calls) == result["application_turn_attempts"] == 1
    assert result["status"] == "recommendation-failed" and result["exit_code"] == 1
    assert result["recommendation"] is result["recommendation_preview"] is result["usage"] is None
    assert (
        result["failure"]["code"]
        == {
            "exception": "unexpected-error",
            "forged-result": "validation-identity",
            "timeout": "timeout",
        }[failure]
    )
    assert cleanup == ([True] if failure == "timeout" else [])
    assert sentinel not in canonical(result) + "".join(output)


def test_factory_failure_does_not_claim_a_turn_or_leak_exception(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))

    def fail(**_):
        raise OSError("PRIVATE ACCOUNT PATH")

    result = asyncio.run(
        workflow.run_codex_owner_repair(
            MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=fail
        )
    )
    assert result["application_turn_attempts"] == 0
    assert result["failure"] == {
        "stage": "adapter-setup",
        "code": "unexpected-error",
        "turn_start": "unknown",
    }
    assert "PRIVATE" not in canonical(result)


def test_outer_timeout_preserves_observed_adapter_phase(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))

    class Waiting:
        failure_diagnostic = None

        async def recommend_owner_policy_repair(self, request):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.failure_diagnostic = FailureDiagnostic(
                    "turn-stream", "cancelled", "acknowledged"
                )
                raise

    result = asyncio.run(
        workflow.run_codex_owner_repair(
            MODEL,
            timeout_seconds=0.01,
            read=exact_choice,
            emit=lambda _: None,
            adapter_factory=lambda **_: Waiting(),
        )
    )
    assert result["failure"] == {
        "stage": "turn-stream",
        "code": "timeout",
        "turn_start": "acknowledged",
    }


def test_task_cancellation_propagates_after_adapter_cleanup(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    cleanup = []

    async def exercise():
        started = asyncio.Event()

        class Waiting:
            async def recommend_owner_policy_repair(self, request):
                try:
                    started.set()
                    await asyncio.Event().wait()
                finally:
                    cleanup.append(True)

        task = asyncio.create_task(
            workflow.run_codex_owner_repair(
                MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=lambda **_: Waiting()
            )
        )
        ready = asyncio.create_task(started.wait())
        try:
            done, _ = await asyncio.wait(
                {task, ready}, timeout=5, return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                await task
                pytest.fail("Workflow returned before the adapter started")
            assert ready in done
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=5)
        finally:
            task.cancel()
            ready.cancel()
            await asyncio.wait_for(asyncio.gather(task, ready, return_exceptions=True), timeout=5)

    asyncio.run(exercise())
    assert cleanup == [True]


@pytest.mark.parametrize("color", [False, True])
def test_cli_help_and_json_preview_need_no_provider(color):
    help_result = runner.invoke(app, ["codex-owner-repair", "--help"], color=color)
    assert help_result.exit_code == 0
    assert "--preview-only" in unstyle(help_result.output)
    result = runner.invoke(
        app,
        [
            "codex-owner-repair",
            "--model",
            MODEL,
            "--candidate",
            "after",
            "--preview-only",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["kind"] == "codex-owner-repair-sharing-preview"
    assert result.stderr == ""


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--model", "bad model"],
        ["--model", MODEL, "--candidate", "arbitrary.py"],
        ["--model", MODEL, "--timeout-seconds", "0"],
        ["--model", MODEL, "/tmp/target"],
        ["--model", MODEL, "--yes"],
    ],
)
def test_cli_rejects_missing_or_unsupported_input_without_adapter(args):
    assert runner.invoke(app, ["codex-owner-repair", *args]).exit_code == 2


def test_json_cli_keeps_confirmation_and_preview_off_stdout():
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL, "--json"], input="\n")
    assert result.exit_code == 0
    final = json.loads(result.stdout)
    assert final["status"] == "not-shared"
    assert "codex-owner-repair-sharing-preview" in result.stderr
    assert "Type 'share " in result.stderr
    assert final["sharing_id"] in result.stderr


@pytest.mark.parametrize("fails", [False, True])
def test_json_cli_approved_fake_attempt_keeps_both_streams_and_redaction(fails, monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    previews, calls = [], []
    original_emit = WorkflowOutput.emit

    def emit(self, text):
        previews.append(json.loads(text))
        original_emit(self, text)

    class Fake:
        async def recommend_owner_policy_repair(self, request):
            calls.append(request)
            if fails:
                raise RuntimeError("PRIVATE ADAPTER FAILURE")
            return fake_result(request)

    monkeypatch.setattr(WorkflowOutput, "emit", emit)
    monkeypatch.setattr(builtins, "input", lambda: "share " + previews[-1]["sharing_id"])
    monkeypatch.setattr(workflow, "_default_adapter_factory", lambda **_: Fake())
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL, "--json"])
    final = json.loads(result.stdout)
    assert result.exit_code == (1 if fails else 0)
    assert final["status"] == ("recommendation-failed" if fails else "recommendation-ready")
    assert len(calls) == final["application_turn_attempts"] == 1
    assert len(previews) == 1
    assert calls[0].to_dict() == previews[0]["transport_request"]
    assert "codex-owner-repair-sharing-preview" in result.stderr
    assert "Type 'share " in result.stderr
    assert final["sharing_id"] in result.stderr
    assert "PRIVATE" not in result.output


def test_human_cli_keeps_model_text_inert_and_shows_host_diff(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(WorkflowOutput, "read", lambda self, prompt: exact_choice(prompt))

    class Fake:
        async def recommend_owner_policy_repair(self, request):
            return fake_result(request, rationale="Scripted text\nNOT A VERDICT\u202eexample")

    monkeypatch.setattr(workflow, "_default_adapter_factory", lambda **_: Fake())
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL])
    assert result.exit_code == 0
    assert "recommendation-ready" in result.stdout
    assert "Source-sharing preview" in result.stdout
    assert "Exact diff (each line is quoted)" in result.stdout
    assert "\\u202e" in result.stdout and "\u202e" not in result.stdout
    assert "Scripted text\\nNOT A VERDICT" in result.stdout


@pytest.mark.parametrize(
    "error,code,status",
    [(RuntimeError, 1, "recommendation-failed"), (asyncio.CancelledError, 130, "cancelled")],
)
def test_cli_failure_and_cancellation_emit_only_redacted_final_json(
    error, code, status, monkeypatch
):
    async def fail(*args, **kwargs):
        raise error("PRIVATE CLI FAILURE")

    monkeypatch.setattr(workflow, "run_codex_owner_repair", fail)
    result = runner.invoke(app, ["codex-owner-repair", "--model", MODEL, "--json"])
    assert result.exit_code == code
    final = json.loads(result.stdout)
    assert final["status"] == status
    assert final["failure"]["code"] == ("cancelled" if code == 130 else "unexpected-error")
    assert "PRIVATE" not in result.output


def test_new_repair_preview_does_not_change_legacy_review_scope():
    before = build_owner_review_preview(MODEL, invocation_nonce="2" * 32)
    workflow.build_owner_repair_preview(MODEL, candidate="before")
    assert build_owner_review_preview(MODEL, invocation_nonce="2" * 32) == before
    assert before["source_scope"] == "packaged-owned-policy/main.py+policy.py"
    assert "registered-change" not in canonical(before["output_schema"])
