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
    assert result["verification"] is None and result["verification_status"] == "not-run"
    assert result["verification_scope"] == "source-configuration"
    assert result["runtime_verification_status"] == "not-run"
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
        elif "'verify " in prompt:
            # This existing edit lifecycle test declines the new independent check.
            return ""
        else:
            assert "'restore " in prompt
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
    assert result["runtime_verification_status"] == "not-run"
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
        assert result["verification"] is None
    elif action == "restore":
        assert len(prompts) == 4 and result["restoration"]["restored"] is True
        assert result["verification"]["status"] == "not-run"
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
    assert "--check" not in help_text and "--command" not in help_text
    assert "--test" not in help_text
    assert "_configuration-worker" not in unstyle(runner.invoke(app, ["--help"]).stdout)
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
            "\n"  # Decline configuration verification independently.
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


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize(
    "choice",
    [
        "approve",
        "failed",
        "worker-error",
        "decline",
        "cancel",
        "eof",
        "keyboard",
        "wrong-plan",
        "apply-token",
        "share-token",
    ],
)
def test_configuration_check_requires_its_own_exact_choice_and_keeps_restore_available(
    tmp_path, monkeypatch, adapter_factory, choice
):
    from authzest.runner import fixture_check

    factory, calls = adapter_factory
    checks = []
    output = []
    prompts = []
    original = tmp_path / "main.py"
    original.write_text(FIXTURE_SOURCE, encoding="utf-8", newline="")

    async def fixed_check(source):
        checks.append(source)
        if choice == "worker-error":
            raise RuntimeError("SECRET-WORKER-STDERR")
        failed = choice == "failed"
        return fixture_check.VerificationOutcome(
            "failed" if failed else "passed",
            "check-failed" if failed else "debug-disabled",
            fixture_check.CHECK_ID,
            sha256(source).hexdigest(),
            fixture_check.WORKER_SHA256,
            1.0,
            0,
        )

    monkeypatch.setattr(fixture_check, "run_configuration_check", fixed_check)

    def read(prompt):
        prompts.append(prompt)
        if "'verify " not in prompt:
            return exact_choice(prompt)
        preview = json.loads(output[-1])
        assert exact_choice(prompt) == f"verify {preview['plan_id']}"
        assert preview["check_id"] == fixture_check.CHECK_ID
        assert preview["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
        assert checks == []  # Sharing and application did not authorize execution.
        if choice in ("approve", "failed", "worker-error"):
            return exact_choice(prompt)
        if choice == "eof":
            raise EOFError()
        if choice == "keyboard":
            raise KeyboardInterrupt()
        return {
            "decline": "",
            "cancel": "cancel",
            "wrong-plan": "verify plan-unrelated",
            "apply-token": exact_choice(prompts[1]),
            "share-token": exact_choice(prompts[0]),
        }[choice]

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL, read=read, emit=output.append, adapter_factory=factory, parent=tmp_path
        )
    )
    assert [prompt.split("'")[1].split()[0] for prompt in prompts] == [
        "share",
        "apply",
        "verify",
        "restore",
    ]
    assert len(calls) == 2  # Exactly one scripted draft, no provider or model retry.
    assert result["application"]["applied"] is True
    assert result["restoration"]["restored"] is True
    assert result["verification_scope"] == "source-configuration"
    assert result["runtime_verification_status"] == "not-run"
    assert result["verification"]["runtime_verification_status"] == "not-run"
    if choice in ("approve", "failed", "worker-error"):
        assert checks == [FIXTURE_AFTER.encode()]
        expected_status = "passed" if choice == "approve" else "failed"
        assert result["verification_status"] == expected_status
        assert result["verification"]["status"] == expected_status
        assert result["status"] == ("completed" if choice == "approve" else "verification-failed")
        assert result["exit_code"] == (0 if choice == "approve" else 1)
        if choice == "approve":
            assert (
                result["verification"]["source_sha256"]
                == sha256(FIXTURE_AFTER.encode()).hexdigest()
            )
    else:
        assert checks == []
        assert result["verification_status"] == result["verification"]["status"] == "not-run"
        assert result["status"] == "completed" and result["exit_code"] == 0
    workspace = Path(result["application"]["workspace"])
    assert workspace.joinpath("main.py").read_text() == FIXTURE_SOURCE
    assert original.read_text() == FIXTURE_SOURCE
    # A passed result describes the checked AFTER snapshot, not the now-restored file.
    if choice == "approve":
        assert (
            sha256(workspace.joinpath("main.py").read_bytes()).hexdigest()
            != result["verification"]["source_sha256"]
        )
    assert "SECRET-WORKER-STDERR" not in json.dumps(result) + "".join(output)


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("stage", ["verification_preview", "decide_verification", "verify"])
def test_local_verification_stage_exception_is_sanitized_and_does_not_skip_restore(
    tmp_path, monkeypatch, adapter_factory, stage
):
    factory, _ = adapter_factory

    def fail(*args, **kwargs):
        raise RuntimeError("SECRET-WORKER-STDERR")

    async def async_fail(*args, **kwargs):
        fail()

    monkeypatch.setattr(
        workflow.FixtureApplySession, stage, async_fail if stage == "verify" else fail
    )
    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=factory, parent=tmp_path
        )
    )
    assert result["status"] == "verification-failed" and result["exit_code"] == 1
    assert result["verification"]["reason"] == "verification-unavailable"
    assert result["verification_status"] == "failed"
    assert result["runtime_verification_status"] == "not-run"
    assert result["application"]["applied"] is True
    assert result["restoration"]["restored"] is True
    assert "SECRET-WORKER-STDERR" not in json.dumps(result)


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_stale_verification_source_is_not_checked_or_overwritten_on_restore(
    tmp_path, monkeypatch, adapter_factory
):
    from authzest.runner import fixture_check

    factory, _ = adapter_factory
    output = []

    async def forbidden(source):
        pytest.fail("Source changed after the application; no verification worker may start")

    monkeypatch.setattr(fixture_check, "run_configuration_check", forbidden)

    def read(prompt):
        if "'verify " in prompt:
            preview = next(item for item in map(json.loads, output) if "changes" in item)
            Path(preview["workspace"]).joinpath("main.py").write_text("# unapproved later edit\n")
        return exact_choice(prompt)

    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL, read=read, emit=output.append, adapter_factory=factory, parent=tmp_path
        )
    )
    assert result["verification_status"] == "failed"
    assert result["status"] == "application-failed" and result["exit_code"] == 1
    assert result["restoration"]["restored"] is False
    assert result["runtime_verification_status"] == "not-run"
    workspace = Path(result["application"]["workspace"])
    assert workspace.joinpath("main.py").read_text() == "# unapproved later edit\n"


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
@pytest.mark.parametrize("reason", ["expired", "precondition-failed", "journal-unavailable"])
def test_verification_prevented_by_failure_is_nonzero_even_when_worker_was_not_run(
    tmp_path, monkeypatch, adapter_factory, reason
):
    factory, _ = adapter_factory

    async def not_run(self):
        return {
            "status": "not-run",
            "reason": reason,
            "execution_attempted": False,
            "verification_scope": "source-configuration",
            "runtime_verification_status": "not-run",
        }

    monkeypatch.setattr(workflow.FixtureApplySession, "verify", not_run)
    result = asyncio.run(
        workflow.run_codex_fixture(
            MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=factory, parent=tmp_path
        )
    )
    assert result["status"] == "verification-failed" and result["exit_code"] == 1
    assert result["verification_status"] == "not-run"
    assert result["verification"]["execution_attempted"] is False
    assert result["restoration"]["restored"] is True


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_cli_renders_historical_configuration_pass_after_separately_confirmed_restore(
    tmp_path, monkeypatch, adapter_factory
):
    from authzest.runner import fixture_check

    factory, calls = adapter_factory
    request = build_fixture_request(MODEL)
    draft = fake_draft(request)
    checks = []
    previews = []
    answers = []
    real_workflow = workflow.run_codex_fixture

    async def fixed_check(source):
        checks.append(source)
        return fixture_check.VerificationOutcome(
            "passed",
            "debug-disabled",
            fixture_check.CHECK_ID,
            sha256(source).hexdigest(),
            fixture_check.WORKER_SHA256,
            1.0,
            0,
        )

    monkeypatch.setattr(fixture_check, "run_configuration_check", fixed_check)

    def read(prompt):
        if "'share " in prompt:
            answer = f"share {request.request_id}"
        elif "'apply " in prompt:
            answer = f"apply {draft.proposal.proposal_id}"
        elif "'verify " in prompt:
            preview = previews[-1]
            assert preview["kind"] == "fixture-configuration-verification-plan"
            answer = f"verify {preview['plan_id']}"
        else:
            answer = f"restore {draft.proposal.proposal_id}"
        assert f"'{answer}'" in prompt
        answers.append(answer)
        return answer

    async def offline_workflow(model, *, emit, **kwargs):
        def capture(text):
            previews.append(json.loads(text))
            emit(text)

        return await real_workflow(
            model, read=read, emit=capture, adapter_factory=factory, parent=tmp_path, **kwargs
        )

    monkeypatch.setattr(workflow, "run_codex_fixture", offline_workflow)
    result = runner.invoke(app, ["codex-fixture", "--model", MODEL])
    assert result.exit_code == 0, result.output
    marker = '{\n  "kind": "codex-owned-fixture-workflow"'
    summary = json.loads(result.stdout[result.stdout.rindex(marker) :])
    assert summary["verification_status"] == "passed"
    assert summary["verification_scope"] == "source-configuration"
    assert summary["runtime_verification_status"] == "not-run"
    assert summary["verification"]["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
    assert summary["restoration"]["restored"] is True
    assert [answer.split()[0] for answer in answers] == ["share", "apply", "verify", "restore"]
    assert checks == [FIXTURE_AFTER.encode()] and len(calls) == 2
    workspace = Path(summary["application"]["workspace"])
    journal = json.loads(workspace.joinpath("record.json").read_text())
    assert journal["verification_status"] == "passed" and journal["restored"] is True
    assert journal["verification"]["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
    assert workspace.joinpath("main.py").read_text() == FIXTURE_SOURCE


@pytest.mark.skipif(not supported(), reason="POSIX owned-fixture command")
def test_verification_cancellation_propagates_and_retains_truthful_applied_record(
    tmp_path, monkeypatch, adapter_factory
):
    from authzest.runner import fixture_check

    factory, _ = adapter_factory
    state = []

    async def waiting_check(source):
        assert source == FIXTURE_AFTER.encode()
        state.append("started")
        try:
            await asyncio.Event().wait()
        finally:
            state.append("finished")

    monkeypatch.setattr(fixture_check, "run_configuration_check", waiting_check)

    async def run():
        task = asyncio.create_task(
            workflow.run_codex_fixture(
                MODEL,
                read=exact_choice,
                emit=lambda _: None,
                adapter_factory=factory,
                parent=tmp_path,
            )
        )
        while not state:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert state == ["started", "finished"]
    workspace = next(tmp_path.iterdir())
    journal = json.loads(workspace.joinpath("record.json").read_text())
    assert journal["applied"] is True and journal["restored"] is False
    assert journal["verification_status"] == "failed"
    assert journal["verification"]["reason"] == "cancelled"
    assert journal["verification"]["execution_attempted"] is True
    assert journal["runtime_verification_status"] == "not-run"
    assert workspace.joinpath("main.py").read_text() == FIXTURE_AFTER


@pytest.mark.parametrize("exit_code", [0, 2])
def test_hidden_configuration_worker_dispatches_only_fixed_entry(monkeypatch, exit_code):
    from authzest.runner import _configuration_worker

    calls = []

    def worker_main():
        calls.append("fixed-worker")
        return exit_code

    monkeypatch.setattr(_configuration_worker, "worker_main", worker_main)
    result = runner.invoke(app, ["_configuration-worker"])
    assert result.exit_code == exit_code
    assert calls == ["fixed-worker"]


@pytest.mark.parametrize("argument", ["main.py", "--path=main.py", "--command=echo", "--yes"])
def test_hidden_worker_rejects_external_source_and_execution_options(monkeypatch, argument):
    from authzest.runner import _configuration_worker

    monkeypatch.setattr(
        _configuration_worker,
        "worker_main",
        lambda: pytest.fail("Arguments must be rejected before entering the fixed worker"),
    )
    assert runner.invoke(app, ["_configuration-worker", argument]).exit_code == 2


@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError])
def test_cli_interrupted_or_unknown_workflow_does_not_claim_verification_never_started(
    monkeypatch, failure
):
    async def fail(*args, **kwargs):
        raise failure("SECRET-LOCAL-EXCEPTION")

    monkeypatch.setattr(workflow, "run_codex_fixture", fail)
    result = runner.invoke(app, ["codex-fixture", "--model", MODEL])
    assert result.exit_code == (0 if failure is KeyboardInterrupt else 1)
    summary = json.loads(result.stdout)
    assert summary["status"] == ("cancelled" if failure is KeyboardInterrupt else "workflow-failed")
    assert summary["runtime_verification_status"] == "not-run"
    assert "verification_status" not in summary
    assert "retained workspace record" in summary["detail"]
    assert "SECRET-LOCAL-EXCEPTION" not in result.output
