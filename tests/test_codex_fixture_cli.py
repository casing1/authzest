"""Offline command/workflow tests: no Codex child or provider connection is permitted."""

import asyncio
import json
import socket
import subprocess
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.contracts import ValidatedResponse, canonical, decode
from authzest.codex.fixture_draft import (
    FIXTURE_AFTER,
    FIXTURE_SOURCE,
    FixtureDraft,
    build_fixture_request,
    validate_fixture_draft,
)
from authzest.codex.mock import scripted_response
from authzest.codex.proposals import ValidatedProposal, prepare_proposal
from authzest.runner import codex_fixture as workflow
from authzest.runner._fixture_workspace import supported

MODEL = "fixture-test-model"
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_live_transport(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("This test must not spawn Codex, another process or a network connection")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def fake_draft(request):
    response = {
        "answers": decode(scripted_response(request, {"review": None}))["answers"],
        "after_text": FIXTURE_AFTER,
        "reason": "Offline scripted fixture change; not a live model judgment.",
        "uncertainties": ["No source execution or verified fix."],
        "side_effects": ["Debug diagnostics would be disabled."],
    }
    return validate_fixture_draft(
        canonical(response), request, usage={"input_tokens": 101, "output_tokens": 45}
    )


@pytest.fixture
def adapter_factory():
    calls = []

    def factory(**kwargs):
        calls.append(("constructed", kwargs))

        class FakeAdapter:
            async def draft(self, request):
                calls.append(("draft", request.request_id))
                return fake_draft(request)

        return FakeAdapter()

    return factory, calls


def exact_choice(prompt):
    return prompt.split("'")[1]


@pytest.mark.parametrize("value", [0, -1, 121, float("nan"), float("inf"), True, None, "120"])
def test_invalid_timeout_rejected_before_any_side_effect(value, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration must not prepare a fixture, prompt or adapter")

    monkeypatch.setattr(workflow, "build_fixture_request", forbidden)
    with pytest.raises(workflow.FixtureInputError, match="Timeout"):
        asyncio.run(
            workflow.run_codex_fixture(
                MODEL,
                timeout_seconds=value,
                read=forbidden,
                emit=forbidden,
                adapter_factory=forbidden,
            )
        )


@pytest.mark.parametrize("model", ["", "bad\nmodel", "white space", None, 1])
def test_invalid_model_rejected_before_any_side_effect(model, monkeypatch):
    monkeypatch.setattr(
        workflow, "build_fixture_request", lambda *a: pytest.fail("No fixture before validation")
    )
    with pytest.raises(workflow.FixtureInputError, match="model identifier"):
        asyncio.run(workflow.run_codex_fixture(model))


def test_non_posix_fails_before_preparing_fixture(monkeypatch):
    monkeypatch.setattr(workflow, "supported", lambda: False)
    monkeypatch.setattr(
        workflow,
        "build_fixture_request",
        lambda *a: pytest.fail("No fixture on unsupported platform"),
    )
    with pytest.raises(workflow.FixtureInputError, match="POSIX"):
        asyncio.run(workflow.run_codex_fixture(MODEL))


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("answer", ["", "cancel", "approve", "share wrong", " share wrong"])
def test_denial_never_constructs_adapter_or_apply_workspace(tmp_path, adapter_factory, answer):
    factory, calls = adapter_factory
    output = []
    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            read=lambda _: answer,
            emit=output.append,
            adapter_factory=factory,
            parent=tmp_path,
        )
    )
    assert calls == [] and list(tmp_path.iterdir()) == []
    assert result["status"] == "not-shared" and result["exit_code"] == 0
    assert result["application_turn_attempts"] == 0
    assert result["application"] is None and result["returned_identity"] is None
    assert result["usage"] is None and result["latency_ms"] is None
    assert result["provider_warning_count"] is None
    assert result["provider_retry_notification_count"] is None
    preview = json.loads(output[0])
    assert preview["request_id"] == result["request_id"]
    assert preview["request"]["config"]["model"] == MODEL
    assert preview["request"]["config"]["temperature"] is None
    assert preview["request"]["source_revision"] is None
    assert preview["prompt"].endswith(canonical(preview["request"]))
    assert preview["prompt_sha256"] == sha256(preview["prompt"].encode()).hexdigest()
    assert (
        preview["output_schema_sha256"]
        == sha256(canonical(preview["output_schema"]).encode()).hexdigest()
    )
    assert preview["limits"]["max_response_bytes"] == 262_144
    assert preview["limits"]["timeout_seconds"] == 120
    assert preview["limits"]["max_application_turn_attempts"] == 1
    assert preview["limits"]["application_retries"] == 0
    assert preview["limits"]["max_accepted_retry_notifications"] == 3
    assert preview["limits"]["codex_internal_transport_retries_hard_capped"] is False
    assert preview["limits"]["token_hard_cap"] is None
    assert preview["limits"]["dollar_hard_cap"] is None
    assert preview["limits_sha256"] == sha256(canonical(preview["limits"]).encode()).hexdigest()
    assert result["limits_sha256"] == preview["limits_sha256"]


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
def test_sharing_interruption_is_cancel_without_adapter(adapter_factory, interrupt):
    factory, calls = adapter_factory

    def read(_):
        raise interrupt()

    result = asyncio.run(
        workflow.run_codex_fixture(MODEL, read=read, emit=lambda _: None, adapter_factory=factory)
    )
    assert calls == []
    assert result["sharing_decision"] == "cancel" and result["exit_code"] == 0


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize(
    "action", ["decline", "cancel", "apply", "restore", "edit-before-apply", "edit-before-restore"]
)
def test_full_fake_workflow_has_separate_choices_and_preserves_original(
    tmp_path, adapter_factory, action
):
    factory, calls = adapter_factory
    original = tmp_path / "main.py"
    original.write_text(FIXTURE_SOURCE, encoding="utf-8", newline="")
    output = []
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        if "'share " in prompt:
            assert len(output) == 1
            assert json.loads(output[0])["kind"] == "codex-fixture-sharing-preview"
            assert calls == []
            return exact_choice(prompt)
        preview = next(item for item in map(json.loads, output) if "changes" in item)
        assert preview["changes"][0]["diff"]
        workspace = Path(preview["workspace"])
        assert workspace.parent == tmp_path
        if "'apply " in prompt:
            if action == "decline":
                return ""
            if action == "cancel":
                raise EOFError()
            if action == "edit-before-apply":
                (workspace / "main.py").write_text("# later user edit\n")
        else:
            assert json.loads(output[-1])["from_text"] == FIXTURE_AFTER
            if action == "apply":
                return ""
            if action == "edit-before-restore":
                (workspace / "main.py").write_text("# later user edit\n")
        return exact_choice(prompt)

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            timeout_seconds=30,
            read=read,
            emit=output.append,
            adapter_factory=factory,
            parent=tmp_path,
        )
    )
    assert calls == [
        ("constructed", {"approved_request_id": result["request_id"], "timeout_seconds": 30}),
        ("draft", result["request_id"]),
    ]
    assert original.read_text() == FIXTURE_SOURCE
    assert result["application_turn_attempts"] == 1
    assert result["returned_identity"]["model"] == MODEL
    assert result["usage"] == {"input_tokens": 101, "output_tokens": 45}
    assert result["provider_warning_count"] is None  # This fake exposes no warning counter.
    assert result["provider_retry_notification_count"] is None
    assert result["original_checkout_modified"] is False
    assert result["verification_status"] == "not-run"
    assert result["latency_ms"] >= 0
    changed = Path(result["application"]["workspace"]) / "main.py"
    if action.startswith("edit-"):
        assert changed.read_text() == "# later user edit\n"
        assert result["exit_code"] == 1
    elif action == "apply":
        assert changed.read_text() == FIXTURE_AFTER
        assert result["restoration"]["status"] == "restoration-decline"
    else:
        assert changed.read_text() == FIXTURE_SOURCE
    if action in ("decline", "cancel", "edit-before-apply"):
        assert len(prompts) == 2 and result["restoration"] is None
    elif action == "restore":
        assert len(prompts) == 3 and result["restoration"]["restored"] is True
    if not action.startswith("edit-"):
        assert result["exit_code"] == 0


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize(
    "failure", ["constructor", "transport", "review", "proposal", "other-change"]
)
def test_failures_and_invalid_drafts_are_sanitized_and_never_create_copy(tmp_path, failure):
    output = []
    calls = []

    def factory(**kwargs):
        calls.append("constructed")
        if failure == "constructor":
            raise RuntimeError("SECRET-PROVIDER-STDERR")

        class FakeAdapter:
            async def draft(self, request):
                calls.append("draft")
                if failure == "transport":
                    raise RuntimeError("SECRET-PROVIDER-STDERR")
                result = fake_draft(request)
                if failure == "review":
                    return SimpleNamespace(
                        review=ValidatedResponse('{"secret":"SECRET-PROVIDER-STDERR"}'),
                        proposal=result.proposal,
                    )
                if failure == "proposal":
                    return FixtureDraft(result.review, ValidatedProposal("{}"))
                changed = prepare_proposal(
                    request,
                    result.review,
                    replacements={"main.py": FIXTURE_AFTER + "# unapproved extra change\n"},
                    rationale="A structurally valid but out-of-scope draft.",
                    uncertainties=("Unverified.",),
                    side_effects=(),
                    checks=("fixture-static-inventory",),
                    expectations=("Preserve routes.",),
                )
                return FixtureDraft(result.review, changed)

        return FakeAdapter()

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL, read=exact_choice, emit=output.append, adapter_factory=factory, parent=tmp_path
        )
    )
    assert result["status"] == "draft-failed" and result["exit_code"] == 1
    assert result["application"] is None and result["returned_identity"] is None
    assert result["provider_warning_count"] is None
    assert result["provider_retry_notification_count"] is None
    assert list(tmp_path.iterdir()) == []
    assert calls.count("draft") <= 1 and len(output) == 1
    assert "SECRET-PROVIDER-STDERR" not in json.dumps(result) + "".join(output)


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("interrupt", ["timeout", "cancel"])
def test_waiting_adapter_is_cancelled_without_application(tmp_path, interrupt):
    state = []

    class WaitingAdapter:
        async def draft(self, request):
            state.append("started")
            try:
                await asyncio.Event().wait()
            finally:
                state.append("finished")

    async def run():
        task = asyncio.create_task(
            workflow.run_codex_fixture(
                MODEL,
                timeout_seconds=0.01 if interrupt == "timeout" else 10,
                read=exact_choice,
                emit=lambda _: None,
                adapter_factory=lambda **kwargs: WaitingAdapter(),
                parent=tmp_path,
            )
        )
        if interrupt == "cancel":
            while not state:
                await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await task
            assert result["status"] == "draft-failed" and result["exit_code"] == 1

    asyncio.run(run())
    assert state == ["started", "finished"]
    assert list(tmp_path.iterdir()) == []


def test_cli_command_requires_model_and_does_not_expose_broad_options(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    help_result = runner.invoke(app, ["codex-fixture", "--help"])
    assert help_result.exit_code == 0
    help_text = unstyle(help_result.stdout)
    assert "--model" in help_text and "--timeout-seconds" in help_text
    assert "--yes" not in help_text and "--api-key" not in help_text
    assert "--path" not in help_text
    assert runner.invoke(app, ["codex-fixture"]).exit_code == 2
    assert runner.invoke(app, ["codex-fixture", "--model", MODEL, "."]).exit_code == 2


@pytest.mark.parametrize("value", ["0", "-1", "121", "nan", "inf"])
def test_cli_invalid_timeout_is_usage_error(value):
    result = runner.invoke(app, ["codex-fixture", "--model", MODEL, f"--timeout-seconds={value}"])
    assert result.exit_code == 2


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_cli_denial_does_not_construct_adapter(monkeypatch):
    monkeypatch.setattr(
        workflow, "_default_adapter_factory", lambda **kw: pytest.fail("Sharing was declined")
    )
    result = runner.invoke(app, ["codex-fixture", "--model", MODEL], input="\n")
    assert result.exit_code == 0
    assert '"status": "not-shared"' in result.stdout
    assert '"application_turn_attempts": 0' in result.stdout
    assert '"provider_warning_count": null' in result.stdout


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_cli_full_fake_cycle_uses_exact_sharing_and_separate_edit_decisions(
    tmp_path, monkeypatch, adapter_factory
):
    factory, calls = adapter_factory
    request = build_fixture_request(MODEL)
    draft = fake_draft(request)
    session_type = workflow.FixtureApplySession

    def private_session(*args, **kwargs):
        return session_type(*args, **{**kwargs, "parent": tmp_path})

    monkeypatch.setattr(workflow, "FixtureApplySession", private_session)
    monkeypatch.setattr(workflow, "_default_adapter_factory", factory)
    result = runner.invoke(
        app,
        ["codex-fixture", "--model", MODEL],
        input=(
            f"share {request.request_id}\napply {draft.proposal.proposal_id}\n"
            f"restore {draft.proposal.proposal_id}\n"
        ),
    )
    assert result.exit_code == 0, result.output
    assert '"status": "completed"' in result.stdout
    assert '"verification_status": "not-run"' in result.stdout
    assert '"restored": true' in result.stdout
    assert len(calls) == 2
    workspace = next(tmp_path.iterdir())
    assert (workspace / "main.py").read_text() == FIXTURE_SOURCE
    assert (workspace / "record.json").exists()


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_cli_transport_failure_is_generic_and_nonzero(monkeypatch):
    request = build_fixture_request(MODEL)

    def fail(**kwargs):
        raise RuntimeError("SECRET-PROVIDER-STDERR")

    monkeypatch.setattr(workflow, "_default_adapter_factory", fail)
    result = runner.invoke(
        app, ["codex-fixture", "--model", MODEL], input=f"share {request.request_id}\n"
    )
    assert result.exit_code == 1
    assert '"status": "draft-failed"' in result.stdout
    assert '"provider_warning_count": null' in result.stdout
    assert "SECRET-PROVIDER-STDERR" not in result.output


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize(
    "warning_count,expected",
    [
        (0, 0),
        (5, 5),
        (4096, 4096),
        (None, None),
        (True, None),
        (False, None),
        (-1, None),
        (4097, None),
        ("5", None),
        (1.5, None),
    ],
)
def test_runner_reports_only_valid_bounded_provider_warning_counts(
    tmp_path, warning_count, expected
):
    request = build_fixture_request(MODEL)
    answers = iter([f"share {request.request_id}", ""])

    class WarningAdapter:
        warnings_seen = warning_count

        async def draft(self, request):
            return fake_draft(request)

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            read=lambda _: next(answers),
            emit=lambda _: None,
            adapter_factory=lambda **kwargs: WarningAdapter(),
            parent=tmp_path,
        )
    )
    assert result["provider_warning_count"] == expected
    assert result["status"] == "completed"
    assert result["application"]["status"] == "declined"
    assert result["usage"] == {"input_tokens": 101, "output_tokens": 45}
    assert result["verification_status"] == "not-run"


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("warning_count", [0, 7])
def test_failed_runner_does_not_report_partial_provider_warning_counts(tmp_path, warning_count):
    request = build_fixture_request(MODEL)

    class FailingAdapter:
        warnings_seen = warning_count

        async def draft(self, request):
            raise RuntimeError("SECRET-PROVIDER-STDERR")

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            read=lambda _: f"share {request.request_id}",
            emit=lambda _: None,
            adapter_factory=lambda **kwargs: FailingAdapter(),
            parent=tmp_path,
        )
    )
    assert result["status"] == "draft-failed"
    assert result["provider_warning_count"] is None
    assert result["usage"] is None and result["application"] is None
    assert list(tmp_path.iterdir()) == []
    assert "SECRET-PROVIDER-STDERR" not in json.dumps(result)


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("warning_count", [0, 7, None])
def test_cli_renders_provider_warning_count_without_inventing_usage(
    tmp_path, monkeypatch, warning_count
):
    request = build_fixture_request(MODEL)
    session_type = workflow.FixtureApplySession

    class WarningAdapter:
        warnings_seen = warning_count

        async def draft(self, request):
            return fake_draft(request)

    monkeypatch.setattr(workflow, "_default_adapter_factory", lambda **kwargs: WarningAdapter())
    monkeypatch.setattr(
        workflow,
        "FixtureApplySession",
        lambda *args, **kwargs: session_type(*args, **{**kwargs, "parent": tmp_path}),
    )
    result = runner.invoke(
        app, ["codex-fixture", "--model", MODEL], input=f"share {request.request_id}\n\n"
    )
    assert result.exit_code == 0, result.output
    marker = '{\n  "kind": "codex-owned-fixture-workflow"'
    summary = json.loads(result.stdout[result.stdout.rindex(marker) :])
    assert summary["provider_warning_count"] == warning_count
    assert summary["usage"] == {"input_tokens": 101, "output_tokens": 45}
    assert summary["application"]["status"] == "declined"
    assert summary["verification_status"] == "not-run"


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize(
    "count,expected", [(0, 0), (2, 2), (3, 3), (None, None), (-1, None), (True, None), (4, None)]
)
def test_cli_retry_notification_summary_is_bounded(tmp_path, monkeypatch, count, expected):
    request = build_fixture_request(MODEL)
    session_type = workflow.FixtureApplySession

    class RetryAdapter:
        retry_notifications_seen = count

        async def draft(self, request):
            return fake_draft(request)

    monkeypatch.setattr(workflow, "_default_adapter_factory", lambda **kwargs: RetryAdapter())
    monkeypatch.setattr(
        workflow,
        "FixtureApplySession",
        lambda *args, **kwargs: session_type(*args, **{**kwargs, "parent": tmp_path}),
    )
    result = runner.invoke(
        app, ["codex-fixture", "--model", MODEL], input=f"share {request.request_id}\n\n"
    )
    assert result.exit_code == 0, result.output
    marker = '{\n  "kind": "codex-owned-fixture-workflow"'
    summary = json.loads(result.stdout[result.stdout.rindex(marker) :])
    assert summary["provider_retry_notification_count"] == expected
    assert summary["limits"]["max_accepted_retry_notifications"] == 3
    assert summary["limits"]["application_retries"] == 0
    assert summary["limits"]["codex_internal_transport_retries_hard_capped"] is False
    assert summary["usage"] == {"input_tokens": 101, "output_tokens": 45}
    assert summary["application"]["status"] == "declined"
    assert summary["verification_status"] == "not-run"


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_failed_retry_summary_does_not_expose_partial_count(tmp_path):
    request = build_fixture_request(MODEL)

    class FailedRetryAdapter:
        retry_notifications_seen = 2

        async def draft(self, request):
            raise RuntimeError("SECRET-PROVIDER-STDERR")

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL,
            read=lambda _: f"share {request.request_id}",
            emit=lambda _: None,
            adapter_factory=lambda **kwargs: FailedRetryAdapter(),
            parent=tmp_path,
        )
    )
    assert result["status"] == "draft-failed"
    assert result["provider_retry_notification_count"] is None
    assert result["usage"] is None and result["application"] is None
    assert list(tmp_path.iterdir()) == []
    assert "SECRET-PROVIDER-STDERR" not in json.dumps(result)
