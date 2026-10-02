"""Offline owner-policy sharing, cancellation and portable CLI boundaries."""

import asyncio
import json
import socket
import subprocess
from types import SimpleNamespace

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.codex.diagnostics import VALIDATION_CODES, FailureDiagnostic
from authzest.codex.mock import scripted_response
from authzest.codex.owner_policy_review import OwnerPolicyReview, validate_owner_policy_draft
from authzest.runner import codex_owner_review as workflow

MODEL = "owner-review-test-model"
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
        # Windows' stdlib loop initializes its private socketpair with connect().
        # Permit only loop construction, before any test coroutine can run;
        # all connections made by workflow/test code still fail below.
        with monkeypatch.context() as initialization:
            initialization.setattr(socket.socket, "connect", connect)
            return create_loop()

    monkeypatch.setattr(policy, "new_event_loop", new_event_loop)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(workflow, "_default_adapter_factory", forbidden)


def exact_choice(prompt):
    return prompt.split("'")[1]


def test_network_guard_still_blocks_connections_inside_async_work():
    async def attempt():
        with (
            socket.socket() as client,
            pytest.raises(pytest.fail.Exception, match="must not invoke"),
        ):
            client.connect(("127.0.0.1", 9))

    asyncio.run(attempt())


def fake_review(request):
    payload = request.to_dict()
    answers = {question["id"]: None for question in payload["questions"]}
    raw = {
        "answers": decode(scripted_response(request, answers))["answers"],
        "cases": [
            {
                "id": "missing-context",
                "principal": None,
                "report": None,
                "expected": False,
                "reason": "Missing context should be denied; scripted, not model-evaluated.",
                "evidence_ids": [item["id"] for item in payload["evidence"]],
            }
        ],
    }
    for answer in raw["answers"]:
        answer["evidence_ids"] = [item["id"] for item in payload["evidence"]]
    return validate_owner_policy_draft(
        canonical(raw), request, usage={"input_tokens": 10, "output_tokens": 20}
    )


@pytest.fixture
def fake_adapter(monkeypatch):
    # Test the workflow's supported-platform branch on every CI OS; no real child.
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    calls = []

    def factory(**kwargs):
        calls.append(("constructed", kwargs))

        class Fake:
            warnings_seen = 0
            retry_notifications_seen = 0

            async def review_owner_policy(self, request):
                calls.append(("review", request.request_id))
                return fake_review(request)

        return Fake()

    return factory, calls


@pytest.mark.parametrize("timeout", [0, -1, 121, float("nan"), float("inf"), True, "120", None])
def test_invalid_timeout_before_payload_preparation(timeout, monkeypatch):
    monkeypatch.setattr(workflow, "build_owner_policy_request", lambda *_: pytest.fail("No input"))
    with pytest.raises(workflow.OwnerReviewInputError, match="Timeout"):
        workflow.build_owner_review_preview(MODEL, timeout_seconds=timeout)


@pytest.mark.parametrize("model", ["", "bad\nmodel", "white space", None, 1])
def test_invalid_model_before_payload_preparation(model, monkeypatch):
    monkeypatch.setattr(workflow, "build_owner_policy_request", lambda *_: pytest.fail("No input"))
    with pytest.raises(workflow.OwnerReviewInputError, match="model identifier"):
        workflow.build_owner_review_preview(model)


def test_preview_content_is_stable_portable_and_binds_all_shared_content(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="nt"))
    nonce = "1" * 32
    preview = workflow.build_owner_review_preview(MODEL, invocation_nonce=nonce)
    assert preview == workflow.build_owner_review_preview(MODEL, invocation_nonce=nonce)
    sharing_id = preview.pop("sharing_id")
    assert sharing_id == "share-" + identity(preview)
    content = {
        k: v for k, v in preview.items() if k not in {"sharing_content_id", "invocation_nonce"}
    }
    assert preview["sharing_content_id"] == "content-" + identity(content)
    request = preview["request"]
    assert {item["data"]["path"] for item in request["evidence"] if item["kind"] == "source"} == {
        "main.py",
        "policy.py",
    }
    assert preview["prompt"].endswith(canonical(request))
    assert request["config"]["model"] == MODEL
    assert request["config"]["temperature"] is None
    assert preview["limits"]["application_retries"] == 0
    assert preview["limits"]["token_hard_cap"] is None
    assert preview["limits"]["codex_internal_transport_retries_hard_capped"] is False
    assert (
        workflow.build_owner_review_preview(MODEL, timeout_seconds=60, invocation_nonce=nonce)[
            "sharing_id"
        ]
        != sharing_id
    )
    assert (
        workflow.build_owner_review_preview("another-model", invocation_nonce=nonce)["sharing_id"]
        != sharing_id
    )


def test_fresh_previews_keep_payload_identity_but_change_confirmation():
    first = workflow.build_owner_review_preview(MODEL)
    second = workflow.build_owner_review_preview(MODEL)
    assert first["invocation_nonce"] != second["invocation_nonce"]
    assert first["sharing_id"] != second["sharing_id"]
    assert first["sharing_content_id"] == second["sharing_content_id"]
    for key in ("request_id", "request", "prompt", "host_instructions", "output_schema", "limits"):
        assert first[key] == second[key]
    assert "invocation_nonce" not in first["request"]


@pytest.mark.parametrize("nonce", [True, 1, "", "1" * 31, "1" * 33, "A" * 32, "é" * 32, []])
def test_invalid_reconstruction_nonce_stops_before_payload_preparation(nonce, monkeypatch):
    monkeypatch.setattr(workflow, "build_owner_policy_request", lambda *_: pytest.fail("No input"))
    with pytest.raises(workflow.OwnerReviewInputError, match="invocation nonce"):
        workflow.build_owner_review_preview(MODEL, invocation_nonce=nonce)


def test_old_approved_phrase_cannot_construct_an_adapter_in_a_new_invocation(fake_adapter):
    factory, calls = fake_adapter
    outputs = []
    first = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=exact_choice, emit=outputs.append, adapter_factory=factory
        )
    )
    assert first["status"] == "draft-ready" and len(calls) == 2
    calls.clear()
    second = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL,
            read=lambda _: f"share {first['sharing_id']}",
            emit=outputs.append,
            adapter_factory=factory,
        )
    )
    assert second["status"] == "not-shared" and second["sharing_decision"] == "decline"
    assert second["application_turn_attempts"] == 0 and calls == []
    assert first["sharing_content_id"] == second["sharing_content_id"]
    assert first["request_id"] == second["request_id"]
    assert first["invocation_nonce"] != second["invocation_nonce"]


def test_each_workflow_generates_one_challenge_and_revalidates_that_same_challenge(
    fake_adapter, monkeypatch
):
    factory, calls = fake_adapter
    generated = []

    def nonce(size):
        assert size == 16
        generated.append(size)
        return "2" * 32

    monkeypatch.setattr(workflow.secrets, "token_hex", nonce)
    output = []
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=exact_choice, emit=output.append, adapter_factory=factory
        )
    )
    preview = json.loads(output[0])
    assert generated == [16]
    assert result["invocation_nonce"] == preview["invocation_nonce"] == "2" * 32
    assert result["sharing_id"] == preview["sharing_id"]
    assert result["sharing_content_id"] == preview["sharing_content_id"]
    assert result["status"] == "draft-ready" and len(calls) == 2


@pytest.mark.parametrize("answer", ["", "cancel", "approve", "share wrong", " share wrong"])
def test_decline_has_no_adapter_or_account_use(answer, fake_adapter):
    factory, calls = fake_adapter
    output = []
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=lambda _: answer, emit=output.append, adapter_factory=factory
        )
    )
    assert calls == []
    assert result["status"] == "not-shared" and result["exit_code"] == 0
    assert result["application_turn_attempts"] == 0
    assert result["usage"] is None and result["draft"] is None
    assert result["latency_ms"] is None
    assert result["failure"] is None
    assert result["original_checkout_modified"] is False
    assert result["execution_status"] == "not-run"
    assert result["sharing_id"] == json.loads(output[0])["sharing_id"]


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_prompt_interruption_never_shares(error):
    def interrupt(_):
        raise error

    result = asyncio.run(
        workflow.run_codex_owner_review(MODEL, read=interrupt, emit=lambda _: None)
    )
    assert result["sharing_decision"] == "cancel"
    assert result["application_turn_attempts"] == 0


def test_request_id_is_not_complete_sharing_confirmation(fake_adapter):
    factory, calls = fake_adapter
    preview = workflow.build_owner_review_preview(MODEL)
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL,
            read=lambda _: "share " + preview["request_id"],
            emit=lambda _: None,
            adapter_factory=factory,
        )
    )
    assert result["sharing_decision"] == "decline" and calls == []


def test_exact_share_produces_draft_not_verification(fake_adapter):
    factory, calls = fake_adapter
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=factory
        )
    )
    assert len(calls) == 2 and result["application_turn_attempts"] == 1
    assert calls[0][1]["approved_request_id"] == result["request_id"]
    assert result["status"] == "draft-ready"
    assert result["failure"] is None
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 20}
    assert result["draft"]["case_review_status"] == "unreviewed"
    assert result["draft"]["execution_status"] == "not-run"
    assert result["authorization_status"] == "unknown"
    assert result["original_checkout_modified"] is False
    assert "proposal" not in result and "application" not in result


def test_non_posix_can_decline_but_cannot_start_adapter(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="nt"))
    result = asyncio.run(
        workflow.run_codex_owner_review(MODEL, read=lambda _: "", emit=lambda _: None)
    )
    assert result["status"] == "not-shared"
    with pytest.raises(workflow.OwnerReviewInputError, match="POSIX"):
        asyncio.run(workflow.run_codex_owner_review(MODEL, read=exact_choice, emit=lambda _: None))


def test_changed_preview_requires_fresh_decision(monkeypatch, fake_adapter):
    factory, calls = fake_adapter
    original = workflow.build_owner_review_preview

    def read(prompt):
        def changed(*args, **kwargs):
            preview = original(*args, **kwargs)
            preview["host_instructions"] += " altered"
            return preview

        monkeypatch.setattr(workflow, "build_owner_review_preview", changed)
        return exact_choice(prompt)

    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=read, emit=lambda _: None, adapter_factory=factory
        )
    )
    assert result["status"] == "preview-changed"
    assert result["exit_code"] == 1 and calls == []
    assert result["failure"] == {
        "stage": "request-validation",
        "code": "request-invalid",
        "turn_start": "not-attempted",
    }


@pytest.mark.parametrize("failure", ["error", "forged", "timeout"])
def test_failed_review_redacts_output_and_does_not_retry(failure, monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    calls = []
    cleaned = []
    sentinel = "PRIVATE PROVIDER ERROR"

    class BadAdapter:
        async def review_owner_policy(self, request):
            calls.append(request.request_id)
            if failure == "error":
                raise RuntimeError(sentinel)
            if failure == "forged":
                payload = fake_review(request).to_dict()
                payload["execution_status"] = "passed"
                return OwnerPolicyReview(canonical(payload))
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.append(True)

    output = []
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL,
            timeout_seconds=0.01,
            read=exact_choice,
            emit=output.append,
            adapter_factory=lambda **_: BadAdapter(),
        )
    )
    assert result["status"] == "review-failed" and result["exit_code"] == 1
    assert len(calls) == 1 and result["draft"] is None and result["usage"] is None
    assert sentinel not in canonical(result) + "".join(output)
    assert cleaned == ([True] if failure == "timeout" else [])
    assert result["failure"] == {
        "stage": "result-validation" if failure == "forged" else "unknown",
        "code": {
            "error": "unexpected-error",
            "forged": "validation-identity",
            "timeout": "timeout",
        }[failure],
        "turn_start": "unknown",
    }


def test_adapter_factory_failure_reports_setup_without_raw_detail(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))

    def fail(**_):
        raise OSError("PRIVATE FACTORY PATH AND TOKEN")

    result = asyncio.run(
        workflow.run_codex_owner_review(
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


@pytest.mark.parametrize("snapshot", ["typed", "dict", "poisoned-property", "forged"])
def test_failure_snapshot_is_revalidated_and_never_leaks_details(snapshot, monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    sentinel = "PRIVATE AUTH TOKEN OR PROVIDER RESPONSE"
    calls = []

    class Failing:
        @property
        def failure_diagnostic(self):
            if snapshot == "poisoned-property":
                raise RuntimeError(sentinel)
            if snapshot == "dict":
                return {"stage": sentinel, "code": sentinel, "turn_start": sentinel}
            diagnostic = FailureDiagnostic("turn-stream", "protocol-rejected", "acknowledged")
            if snapshot == "forged":
                object.__setattr__(diagnostic, "stage", sentinel)
            return diagnostic

        async def review_owner_policy(self, request):
            calls.append(request.request_id)
            raise RuntimeError(sentinel)

    output = []
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=exact_choice, emit=output.append, adapter_factory=lambda **_: Failing()
        )
    )
    assert len(calls) == 1
    assert result["failure"] == (
        {"stage": "turn-stream", "code": "protocol-rejected", "turn_start": "acknowledged"}
        if snapshot == "typed"
        else {"stage": "unknown", "code": "unexpected-error", "turn_start": "unknown"}
    )
    assert result["draft"] is None and result["usage"] is None
    assert result["provider_warning_count"] is None
    assert result["provider_retry_notification_count"] is None
    assert sentinel not in canonical(result) + "".join(output)


def test_outer_timeout_preserves_adapter_phase_but_not_cancelled_code(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    calls = []

    class Waiting:
        failure_diagnostic = None

        async def review_owner_policy(self, request):
            calls.append(request.request_id)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.failure_diagnostic = FailureDiagnostic(
                    "turn-stream", "cancelled", "acknowledged"
                )
                raise

    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL,
            timeout_seconds=0.01,
            read=exact_choice,
            emit=lambda _: None,
            adapter_factory=lambda **_: Waiting(),
        )
    )
    assert len(calls) == 1
    assert result["status"] == "review-failed" and result["exit_code"] == 1
    assert result["failure"] == {
        "stage": "turn-stream",
        "code": "timeout",
        "turn_start": "acknowledged",
    }


def test_runner_validation_ignores_stale_adapter_diagnostic(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))

    class Forged:
        failure_diagnostic = FailureDiagnostic("turn-stream", "turn-failed", "acknowledged")

        async def review_owner_policy(self, request):
            return OwnerPolicyReview("PRIVATE INVALID OUTPUT")

    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=lambda **_: Forged()
        )
    )
    assert result["failure"] == {
        "stage": "result-validation",
        "code": "validation-json",
        "turn_start": "unknown",
    }
    assert "PRIVATE" not in canonical(result)


@pytest.mark.parametrize("code", sorted(VALIDATION_CODES))
def test_runner_exports_only_fixed_host_rule_not_exception_text(code, fake_adapter, monkeypatch):
    factory, calls = fake_adapter

    def reject(*_):
        raise ContractError("PRIVATE PROVIDER OUTPUT", code=code)

    monkeypatch.setattr(workflow, "validate_owner_policy_result", reject)
    output = []
    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL, read=exact_choice, emit=output.append, adapter_factory=factory
        )
    )
    assert len(calls) == 2
    assert result["failure"] == {
        "stage": "result-validation",
        "code": code,
        "turn_start": "unknown",
    }
    assert result["draft"] is None and result["usage"] is None
    assert result["execution_status"] == "not-run" and result["authorization_status"] == "unknown"
    assert "PRIVATE" not in canonical(result) + "".join(output)


def test_historical_v1_sharing_approval_does_not_cover_v2(fake_adapter):
    factory, calls = fake_adapter
    historical = "share-eb98405cadcdc6234501d513dec8be6c37f1e4c06a50438b260ab40d38c481a7"
    result = asyncio.run(
        workflow.run_codex_owner_review(
            "gpt-6-astra",
            read=lambda _: f"share {historical}",
            emit=lambda _: None,
            adapter_factory=factory,
        )
    )
    assert result["sharing_id"] != historical
    assert result["status"] == "not-shared" and calls == []


def test_outer_deadline_does_not_replace_an_earlier_failure(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))

    class SlowCleanup:
        failure_diagnostic = FailureDiagnostic("turn-stream", "protocol-rejected", "acknowledged")

        async def review_owner_policy(self, request):
            # The transport saved the primary failure before awaiting cleanup.
            await asyncio.Event().wait()

    result = asyncio.run(
        workflow.run_codex_owner_review(
            MODEL,
            timeout_seconds=0.01,
            read=exact_choice,
            emit=lambda _: None,
            adapter_factory=lambda **_: SlowCleanup(),
        )
    )
    assert result["failure"] == {
        "stage": "turn-stream",
        "code": "protocol-rejected",
        "turn_start": "acknowledged",
    }


def test_task_cancellation_propagates(monkeypatch):
    monkeypatch.setattr(workflow, "os", SimpleNamespace(name="posix"))
    cleaned = []

    async def exercise():
        started = asyncio.Event()

        class Waiting:
            async def review_owner_policy(self, request):
                try:
                    started.set()
                    await asyncio.Event().wait()
                finally:
                    cleaned.append(True)

        task = asyncio.create_task(
            workflow.run_codex_owner_review(
                MODEL, read=exact_choice, emit=lambda _: None, adapter_factory=lambda **_: Waiting()
            )
        )
        startup = asyncio.create_task(started.wait())
        try:
            done, _ = await asyncio.wait(
                {task, startup}, timeout=5, return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                await task  # Surface an early setup error instead of waiting forever.
                pytest.fail("Workflow returned before the fake adapter started")
            assert startup in done, "Fake adapter did not start within five seconds"
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=5)
        finally:
            for pending in (task, startup):
                pending.cancel()
            await asyncio.wait_for(asyncio.gather(task, startup, return_exceptions=True), timeout=5)

    asyncio.run(exercise())
    assert cleaned == [True]


@pytest.mark.parametrize("color", [False, True])
def test_cli_help_and_preview_work_without_provider(color):
    help_result = runner.invoke(app, ["codex-owner-review", "--help"], color=color)
    assert help_result.exit_code == 0 and "--preview-only" in unstyle(help_result.output)
    result = runner.invoke(
        app, ["codex-owner-review", "--model", MODEL, "--preview-only", "--json"]
    )
    assert result.exit_code == 0
    preview = json.loads(result.output)
    assert preview["kind"] == "codex-owner-review-sharing-preview"
    assert preview["request"]["config"]["model"] == MODEL


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--model", "bad model"],
        ["--model", MODEL, "--timeout-seconds", "0"],
        ["--model", MODEL, "/tmp/target"],
        ["--model", MODEL, "--yes"],
    ],
)
def test_cli_invalid_options_exit_two(args):
    assert runner.invoke(app, ["codex-owner-review", *args]).exit_code == 2


def test_cli_decline_and_eof_do_not_share():
    for user_input in ("\n", "cancel\n", ""):
        result = runner.invoke(app, ["codex-owner-review", "--model", MODEL], input=user_input)
        assert result.exit_code == 0
        assert '"status": "not-shared"' in result.output


@pytest.mark.parametrize(
    "error,code,status",
    [(RuntimeError, 1, "review-failed"), (asyncio.CancelledError, 130, "cancelled")],
)
def test_cli_failure_and_cancellation_are_redacted(error, code, status, monkeypatch):
    async def fail(*args, **kwargs):
        raise error("PRIVATE CLI ERROR")

    monkeypatch.setattr(workflow, "run_codex_owner_review", fail)
    result = runner.invoke(app, ["codex-owner-review", "--model", MODEL, "--json"])
    assert result.exit_code == code
    assert json.loads(result.output)["status"] == status
    assert json.loads(result.output)["failure"] == {
        "stage": "unknown",
        "code": "cancelled" if code == 130 else "unexpected-error",
        "turn_start": "unknown",
    }
    assert "PRIVATE CLI ERROR" not in result.output
