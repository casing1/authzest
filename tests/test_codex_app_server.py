import asyncio
import json
import os
import signal
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex import app_server
from authzest.codex.app_server import CONFIG, AppServerError, CodexAppServerAdapter
from authzest.codex.contracts import canonical, validate_response
from authzest.codex.fixture_draft import (
    FIXTURE_AFTER,
    FIXTURE_SOURCE,
    build_fixture_request,
    validate_fixture_draft,
)
from test_fixture_draft import response_data

pytestmark = pytest.mark.skipif(os.name != "posix", reason="App Server transport requires POSIX")

NON_NULL_ENDPOINT_OVERRIDES = [
    pytest.param("", id="empty-string"),
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
    pytest.param(0, id="zero"),
    pytest.param({}, id="empty-object"),
    pytest.param([], id="empty-array"),
    pytest.param("https://api.openai.com/v1", id="api-url"),
    pytest.param("https://chatgpt.com/backend-api", id="chatgpt-url"),
    pytest.param("https://FAKE_SECRET_ENDPOINT.example.invalid/path", id="other-url"),
]


@dataclass
class Fake:
    executable: Path
    log: Path

    def events(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def methods(self):
        return [
            event["message"].get("method") for event in self.events() if event["event"] == "request"
        ]

    def starts(self):
        return [event for event in self.events() if event["event"] == "start"]


@pytest.fixture
def context():
    return build_fixture_request("fixture-test-model")


def nested_config():
    result = {}
    for key, value in CONFIG.items():
        current = result
        parts = key.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


@pytest.mark.parametrize("present", [False, True], ids=["missing", "null"])
@pytest.mark.parametrize("require_disabled_mcp", [False, True], ids=["discovery", "generation"])
def test_no_explicit_model_endpoint_is_valid_config(present, require_disabled_mcp):
    config = nested_config()
    assert "openai_base_url" not in config
    if present:
        config["openai_base_url"] = None
    assert app_server._check_config(config, require_disabled_mcp=require_disabled_mcp) == ()


@pytest.mark.parametrize("value", NON_NULL_ENDPOINT_OVERRIDES)
def test_every_non_null_model_endpoint_override_is_rejected(value):
    config = nested_config()
    config["openai_base_url"] = value
    with pytest.raises(AppServerError) as error:
        app_server._check_config(config, require_disabled_mcp=True)
    assert str(error.value) == "A model endpoint override is unsupported for ChatGPT login"


@pytest.fixture
def fake_factory(tmp_path, context):
    count = 0
    children = []

    def create(case="happy", *, endpoint_overrides=None):
        nonlocal count
        count += 1
        directory = tmp_path / str(count)
        directory.mkdir()
        executable = directory / "fake-codex"
        log = directory / "events.jsonl"
        settings = {
            "case": case,
            "log": str(log),
            "config": nested_config(),
            "endpoint_overrides": endpoint_overrides or {},
            "model": context.to_dict()["config"]["model"],
            "raw": canonical(response_data(context)),
        }
        helper = Path(__file__).parent / "helpers/fake_codex_server.py"
        executable.write_text(
            f"#!{sys.executable} -S\n"
            + helper.read_text().replace("SETTINGS = {}", f"SETTINGS = {settings!r}", 1)
        )
        executable.chmod(0o700)
        fake = Fake(executable, log)
        children.append(fake)
        return fake

    yield create
    # Failing assertions must not leave the test's own dedicated process group alive.
    for fake in children:
        for started in fake.starts():
            with suppress(ProcessLookupError):
                os.killpg(started["pid"], signal.SIGKILL)


def adapter(context, fake, **kwargs):
    return CodexAppServerAdapter(
        context.request_id, executable=str(fake.executable), timeout_seconds=5, **kwargs
    )


def assert_stopped(fake):
    for event in fake.starts():
        with pytest.raises(ProcessLookupError):
            os.kill(event["pid"], 0)
        assert not Path(event["cwd"]).exists()


def assert_descendant_stopped(fake):
    pid = next(event["pid"] for event in fake.events() if event["event"] == "descendant")
    status = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    )
    # Orphans may briefly be zombies until their new parent reaps them, but may not run.
    assert not status.stdout.strip() or status.stdout.strip().startswith("Z")


@pytest.mark.parametrize("endpoint_overrides", [{}, {1: None, 2: None}], ids=["missing", "null"])
def test_actual_jsonl_subprocess_draft_has_two_preflight_passes_and_one_turn(
    context, fake_factory, endpoint_overrides
):
    fake = fake_factory(endpoint_overrides=endpoint_overrides)
    transport = adapter(context, fake)
    result = asyncio.run(transport.draft(context))
    assert transport.warnings_seen == 0
    assert transport.retry_notifications_seen == 0
    assert result.proposal.to_dict()["changes"][0]["after_text"] == FIXTURE_AFTER
    assert result.review.to_dict()["usage"] == {"input_tokens": 123, "output_tokens": 45}
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
    starts = fake.starts()
    assert len(starts) == 2
    assert all(
        not argument.startswith("openai_base_url=")
        for event in starts
        for argument in event["arguments"]
    )
    assert all("suppress_unstable_features_warning=true" in event["arguments"] for event in starts)
    assert "mcp_servers.inherited-server.enabled=false" not in starts[0]["arguments"]
    assert "mcp_servers.inherited-server.enabled=false" in starts[1]["arguments"]
    calls = {
        event["message"]["method"]: event["message"]["params"]
        for event in fake.events()
        if event["event"] == "request"
    }
    assert calls["account/read"] == {"refreshToken": False}
    assert calls["thread/start"]["ephemeral"] is True
    assert calls["thread/start"]["allowProviderModelFallback"] is False
    assert calls["thread/start"]["environments"] == []
    assert calls["thread/start"]["dynamicTools"] == []
    assert calls["turn/start"]["environments"] == []
    assert calls["turn/start"]["serviceTierForTurn"] == "default"
    assert calls["turn/start"]["outputSchema"]["additionalProperties"] is False
    assert_stopped(fake)


@pytest.mark.parametrize("generation", [1, 2], ids=["discovery", "generation"])
@pytest.mark.parametrize("value", NON_NULL_ENDPOINT_OVERRIDES)
def test_inherited_model_endpoint_fails_each_preflight_before_thread_and_turn(
    context, fake_factory, generation, value
):
    overrides = {1: None, 2: None}
    overrides[generation] = value
    fake = fake_factory(endpoint_overrides=overrides)
    transport = adapter(context, fake)
    with pytest.raises(AppServerError) as error:
        asyncio.run(transport.draft(context))
    assert str(error.value) == "A model endpoint override is unsupported for ChatGPT login"
    assert fake.methods() == ["initialize", "initialized", "config/read"] * generation
    assert "thread/start" not in fake.methods()
    assert "turn/start" not in fake.methods()
    assert len(fake.starts()) == generation
    assert transport.warnings_seen is None
    assert transport.retry_notifications_seen is None
    assert_stopped(fake)


def test_review_adapter_protocol_does_not_extend_review_json(context, fake_factory):
    fake = fake_factory()
    raw = asyncio.run(adapter(context, fake).analyze(context))
    review = validate_response(raw, context).to_dict()
    assert set(review) == {"schema_version", "request_id", "identity", "answers", "usage"}
    assert "FAKE_SECRET_PROFILE" not in raw
    assert_stopped(fake)


def test_missing_usage_remains_unknown_not_zero(context, fake_factory):
    fake = fake_factory("missing-usage")
    result = asyncio.run(adapter(context, fake).draft(context))
    assert result.review.to_dict()["usage"] is None


def test_secret_environment_values_are_not_forwarded(context, fake_factory, monkeypatch):
    fake = fake_factory()
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "HTTPS_PROXY", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        monkeypatch.setenv(key, "fake-sensitive-value")
    asyncio.run(adapter(context, fake).draft(context))
    for started in fake.starts():
        assert "HOME" in started["environment_keys"]
        assert not set(started["environment_keys"]) & {
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "HTTPS_PROXY",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
        }
    assert "fake-sensitive-value" not in fake.log.read_text()


def test_exact_sharing_decision_required_before_starting_any_child(context, fake_factory):
    fake = fake_factory()
    transport = CodexAppServerAdapter("request-different", executable=str(fake.executable))
    with pytest.raises(AppServerError, match="fresh exact-request"):
        asyncio.run(transport.draft(context))
    assert not fake.log.exists()


@pytest.mark.parametrize("case", ["happy", "rpc-error"])
def test_adapter_is_single_use_after_success_or_failure(context, fake_factory, case):
    fake = fake_factory(case)
    transport = adapter(context, fake)
    if case == "happy":
        asyncio.run(transport.draft(context))
    else:
        with pytest.raises(AppServerError):
            asyncio.run(transport.draft(context))
    starts = len(fake.starts())
    with pytest.raises(AppServerError, match="fresh exact-request"):
        asyncio.run(transport.draft(context))
    assert len(fake.starts()) == starts


@pytest.mark.parametrize("timeout", [0, -1, 121, float("inf"), float("nan"), True, "120", None])
def test_invalid_timeout_rejected(timeout):
    with pytest.raises(AppServerError, match="finite timeout"):
        CodexAppServerAdapter("request-not-started", timeout_seconds=timeout)


@pytest.mark.parametrize(
    "case",
    [
        "wrong-version",
        "wrong-rpc-id",
        "boolean-rpc-id",
        "rpc-error",
        "bad-config",
        "unstable-warning-enabled",
        "unstable-warning-string",
        "unstable-warning-missing",
        "missing-config",
        "external-context",
        "invalid-mcp-name",
        "too-many-mcp-servers",
        "mcp-still-enabled",
        "new-mcp-second-pass",
        "api-key-auth",
        "remote-enabled",
        "remote-result-enabled",
        "missing-auth",
        "malformed-auth",
        "missing-model",
        "duplicate-model",
        "unsupported-effort",
        "thread-model",
        "thread-provider",
        "thread-approval",
        "thread-sandbox",
        "thread-network",
        "thread-cwd",
        "thread-instructions",
        "thread-roots",
        "thread-id",
        "thread-history",
        "thread-notification-history",
        "malformed",
        "duplicate-json-key",
        "invalid-unicode",
        "partial-eof",
        "oversized",
        "pending-overflow",
        "early-event",
        "missing-notification-method",
    ],
)
def test_invalid_preflight_fails_before_turn_without_exposing_provider_details(
    context, fake_factory, case
):
    fake = fake_factory(case)
    with pytest.raises(AppServerError) as error:
        asyncio.run(adapter(context, fake).draft(context))
    assert "turn/start" not in fake.methods()
    assert "FAKE_SECRET" not in str(error.value)
    assert_stopped(fake)


@pytest.mark.parametrize("case", ["early-tool-request", "tool-request"])
def test_server_capability_request_is_explicitly_denied(context, fake_factory, monkeypatch, case):
    fake = fake_factory(case)
    original = app_server._Session.send
    sent = []

    async def capture(self, message):
        sent.append(message)
        await original(self, message)

    monkeypatch.setattr(app_server._Session, "send", capture)
    with pytest.raises(AppServerError, match="unsupported capability"):
        asyncio.run(adapter(context, fake).draft(context))
    assert {"id": "server-tool", "error": {"code": -32601, "message": "Denied"}} in sent
    if case == "early-tool-request":
        assert "turn/start" not in fake.methods()
    assert_stopped(fake)


@pytest.mark.parametrize(
    "case",
    [
        "unexpected-event",
        "unexpected-response",
        "thread-notification-id",
        "completed-turn-id",
        "wrong-thread",
        "wrong-turn",
        "tool-item",
        "memory-item",
        "interaction-item",
        "bad-final-json",
        "bad-final-source",
        "non-string-final",
        "missing-final",
        "ambiguous-final",
        "repeated-final",
        "negative-usage",
        "boolean-usage",
        "null-usage",
        "failed-turn",
        "interrupted-turn",
        "final-tool-item",
        "turn-result-tool",
    ],
)
def test_bad_turn_or_model_output_is_rejected_and_child_reaped(context, fake_factory, case):
    fake = fake_factory(case)
    with pytest.raises(AppServerError) as error:
        asyncio.run(adapter(context, fake).draft(context))
    assert fake.methods().count("turn/start") == 1
    assert "FAKE_SECRET" not in str(error.value)
    assert_stopped(fake)


@pytest.mark.parametrize(
    "case,limit,value",
    [("stream-bytes", "MAX_STREAM_BYTES", 30000), ("stream-events", "MAX_EVENTS", 20)],
)
def test_stream_aggregate_and_event_budgets(context, fake_factory, monkeypatch, case, limit, value):
    monkeypatch.setattr(app_server, limit, value)
    fake = fake_factory(case)
    with pytest.raises(AppServerError, match="oversized Codex stream"):
        asyncio.run(adapter(context, fake).draft(context))
    assert_stopped(fake)


@pytest.mark.parametrize("case", ["hang", "infinite-output", "descendant"])
def test_wall_clock_budget_terminates_actual_child(context, fake_factory, case):
    fake = fake_factory(case)
    transport = CodexAppServerAdapter(
        context.request_id, executable=str(fake.executable), timeout_seconds=2
    )
    with pytest.raises(AppServerError):
        asyncio.run(transport.draft(context))
    assert "turn/start" in fake.methods()
    assert_stopped(fake)
    if case == "descendant":
        assert_descendant_stopped(fake)


def test_cancellation_reaps_wrapper_and_descendant(context, fake_factory):
    fake = fake_factory("descendant")

    async def cancel():
        task = asyncio.create_task(adapter(context, fake).draft(context))
        try:
            async with asyncio.timeout(5):
                while not any(event["event"] == "descendant" for event in fake.events()):
                    await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

    asyncio.run(cancel())
    assert_stopped(fake)
    assert_descendant_stopped(fake)


def cli_process(fake, tmp_path, answer):
    """Exercise the real CLI and real adapter, resolving only this test's fake codex."""
    executable = fake.executable.with_name("codex")
    fake.executable.rename(executable)
    fake.executable = executable
    temporary_root = tmp_path / "private-cli-fixtures"
    temporary_root.mkdir()
    environment = {
        **os.environ,
        "PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", ""),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(temporary_root),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "authzest.cli",
            "codex-fixture",
            "--model",
            "fixture-test-model",
            "--timeout-seconds",
            "5",
        ],
        cwd=tmp_path,
        env=environment,
        input=answer,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    marker = '{\n  "kind": "codex-owned-fixture-workflow"'
    summary = json.loads(result.stdout[result.stdout.rindex(marker) :])
    return result, summary, temporary_root


@pytest.mark.parametrize("case", ["happy", "retry:partial-reset"])
def test_real_cli_share_draft_apply_restore_uses_only_exact_decisions(
    context, fake_factory, tmp_path, case
):
    fake = fake_factory(case)
    original = tmp_path / "main.py"
    original.write_text(FIXTURE_SOURCE, encoding="utf-8")
    original_hash = sha256(original.read_bytes()).hexdigest()
    maintained = Path(__file__).parent / "fixtures/proposal_demo/main.py"
    maintained_hash = sha256(maintained.read_bytes()).hexdigest()
    draft = validate_fixture_draft(
        canonical(response_data(context)), context, usage={"input_tokens": 123, "output_tokens": 45}
    )
    # These exact known fixture identities are precomputed; no generic prompt auto-approval.
    answers = (
        f"share {context.request_id}\n"
        f"apply {draft.proposal.proposal_id}\n"
        "\n"  # Configuration verification requires its own explicit approval.
        f"restore {draft.proposal.proposal_id}\n"
    )
    process, summary, temporary_root = cli_process(fake, tmp_path, answers)
    assert process.returncode == 0, process.stderr
    assert summary["status"] == "completed"
    assert summary["sharing_decision"] == "approve"
    assert summary["application_turn_attempts"] == 1
    assert summary["provider_retry_notification_count"] == (0 if case == "happy" else 1)
    assert summary["application"]["status"] == "applied"
    assert summary["application"]["applied"] is True
    assert summary["restoration"]["status"] == "restored"
    assert summary["restoration"]["restored"] is True
    assert summary["original_checkout_modified"] is False
    assert summary["verification_status"] == "not-run"
    assert summary["verification"]["status"] == "not-run"
    assert summary["runtime_verification_status"] == "not-run"
    assert summary["usage"] == {"input_tokens": 123, "output_tokens": 45}
    assert fake.methods().count("turn/start") == 1
    workspace = Path(summary["application"]["workspace"])
    assert workspace.parent == temporary_root
    assert workspace != tmp_path
    assert workspace.joinpath("main.py").read_bytes() == FIXTURE_SOURCE.encode()
    assert workspace.joinpath("after.txt").read_bytes() == FIXTURE_AFTER.encode()
    journal = json.loads(workspace.joinpath("record.json").read_text())
    assert journal["applied"] is True and journal["restored"] is True
    assert journal["before_sha256"] == original_hash
    assert sha256(original.read_bytes()).hexdigest() == original_hash
    assert sha256(maintained.read_bytes()).hexdigest() == maintained_hash
    assert "FAKE_SECRET_PROFILE" not in process.stdout + process.stderr
    assert_stopped(fake)


def test_real_cli_declined_sharing_starts_no_codex_process(context, fake_factory, tmp_path):
    fake = fake_factory()
    process, summary, temporary_root = cli_process(fake, tmp_path, "\n")
    assert process.returncode == 0, process.stderr
    assert summary["request_id"] == context.request_id
    assert summary["status"] == "not-shared"
    assert summary["sharing_decision"] == "decline"
    assert summary["application_turn_attempts"] == 0
    assert summary["application"] is None
    assert summary["restoration"] is None
    assert summary["verification_status"] == "not-run"
    assert not fake.log.exists()
    assert list(temporary_root.iterdir()) == []


@pytest.mark.parametrize(
    "method",
    [
        "account/rateLimits/updated",
        "model/verification",
        "model/safetyBuffering/updated",
        "turn/moderationMetadata",
    ],
)
@pytest.mark.parametrize("stage", ["before-response", "during-turn"])
def test_known_read_only_metadata_preserves_output_usage_and_proposal(
    context, fake_factory, method, stage
):
    fake = fake_factory(f"metadata:{method}:{stage}:valid")
    draft = asyncio.run(adapter(context, fake).draft(context))
    expected = validate_fixture_draft(
        canonical(response_data(context)), context, usage={"input_tokens": 123, "output_tokens": 45}
    )
    assert draft.review.payload_json == expected.review.payload_json
    assert draft.proposal.proposal_id == expected.proposal.proposal_id
    assert draft.proposal.to_dict()["changes"][0]["after_text"] == FIXTURE_AFTER
    assert fake.methods().count("turn/start") == 1
    assert_stopped(fake)


@pytest.mark.parametrize(
    "method", ["model/verification", "model/safetyBuffering/updated", "turn/moderationMetadata"]
)
@pytest.mark.parametrize("stage", ["before-response", "during-turn"])
@pytest.mark.parametrize(
    "mutation", ["wrong-thread", "wrong-turn", "missing-thread", "missing-turn"]
)
def test_scoped_metadata_requires_exact_thread_and_turn_identity(
    context, fake_factory, method, stage, mutation
):
    fake = fake_factory(f"metadata:{method}:{stage}:{mutation}")
    with pytest.raises(AppServerError, match="identity mismatch"):
        asyncio.run(adapter(context, fake).draft(context))
    assert fake.methods().count("turn/start") == 1
    assert_stopped(fake)


@pytest.mark.parametrize("method", ["configWarning", "guardianWarning", "error", "unknownWarning"])
@pytest.mark.parametrize("stage", ["before-response", "during-turn"])
def test_unrecognized_warnings_remain_fail_closed(context, fake_factory, method, stage):
    fake = fake_factory(f"unrecognized-warning:{method}:{stage}")
    with pytest.raises(AppServerError) as error:
        asyncio.run(adapter(context, fake).draft(context))
    assert "FAKE_SECRET_WARNING" not in str(error.value)
    assert fake.methods().count("turn/start") == (0 if stage == "before-response" else 1)
    assert_stopped(fake)


def test_metadata_cannot_substitute_for_a_final_answer(context, fake_factory):
    fake = fake_factory("metadata-only")
    with pytest.raises(AppServerError, match="Missing or ambiguous Codex final output"):
        asyncio.run(adapter(context, fake).draft(context))
    assert_stopped(fake)


def test_ignored_quota_metadata_still_consumes_stream_budget(context, fake_factory, monkeypatch):
    monkeypatch.setattr(app_server, "MAX_EVENTS", 20)
    fake = fake_factory("quota-burst")
    with pytest.raises(AppServerError, match="oversized Codex stream"):
        asyncio.run(adapter(context, fake).draft(context))
    assert "turn/start" not in fake.methods()
    assert_stopped(fake)


@pytest.mark.parametrize("stage", ["before-thread-response", "before-turn-response", "during-turn"])
@pytest.mark.parametrize("effort", ["same-effort", "null-effort", "same-collaboration"])
def test_unchanged_settings_notifications_preserve_the_bound_draft(
    context, fake_factory, stage, effort
):
    fake = fake_factory(f"settings:{stage}:{effort}")
    draft = asyncio.run(adapter(context, fake).draft(context))
    expected = validate_fixture_draft(
        canonical(response_data(context)), context, usage={"input_tokens": 123, "output_tokens": 45}
    )
    assert draft.review.payload_json == expected.review.payload_json
    assert draft.proposal.proposal_id == expected.proposal.proposal_id
    assert fake.methods().count("turn/start") == 1
    assert_stopped(fake)


@pytest.mark.parametrize("stage", ["before-thread-response", "before-turn-response", "during-turn"])
@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-model",
        "wrong-provider",
        "wrong-cwd",
        "wrong-policy",
        "wrong-reviewer",
        "wrong-sandbox",
        "enabled-network",
        "wrong-effort",
        "wrong-thread",
        "missing-settings",
        "null-settings",
        "missing-sandbox",
        "missing-model",
        "wrong-collaboration-mode",
        "wrong-collaboration-model",
        "wrong-collaboration-effort",
        "extra-collaboration-instructions",
        "missing-collaboration-mode",
        "missing-collaboration-settings",
    ],
)
def test_changed_or_incomplete_thread_settings_fail_closed(context, fake_factory, stage, mutation):
    fake = fake_factory(f"settings:{stage}:{mutation}")
    with pytest.raises(
        AppServerError, match="settings update|boundary|identity mismatch|collaboration context"
    ) as error:
        asyncio.run(adapter(context, fake).draft(context))
    assert "FAKE_SECRET" not in str(error.value)
    # A queued pre-thread-response change must be rejected before the generation RPC.
    assert fake.methods().count("turn/start") == (0 if stage == "before-thread-response" else 1)
    assert_stopped(fake)


@pytest.mark.parametrize("stage", ["before-thread-response", "before-turn-response", "during-turn"])
@pytest.mark.parametrize("scope", ["scoped", "unscoped", "null-thread", "maximum-message"])
def test_generic_warnings_are_counted_without_altering_authoritative_results(
    context, fake_factory, stage, scope
):
    fake = fake_factory(f"warning:{stage}:{scope}")
    transport = adapter(context, fake)
    draft = asyncio.run(transport.draft(context))
    expected = validate_fixture_draft(
        canonical(response_data(context)), context, usage={"input_tokens": 123, "output_tokens": 45}
    )
    assert transport.warnings_seen == 1
    assert draft.review.payload_json == expected.review.payload_json
    assert draft.proposal.proposal_id == expected.proposal.proposal_id
    assert "FAKE_SECRET_WARNING" not in draft.review.payload_json + draft.proposal.payload_json
    assert fake.methods().count("turn/start") == 1
    assert_stopped(fake)


@pytest.mark.parametrize("stage", ["before-thread-response", "before-turn-response", "during-turn"])
@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-thread",
        "non-string-thread",
        "missing-message",
        "empty-message",
        "non-string-message",
        "null-message",
        "overlong-message",
        "extra-properties",
        "non-object",
    ],
)
def test_malformed_or_unrelated_warning_metadata_is_rejected(
    context, fake_factory, stage, mutation
):
    fake = fake_factory(f"warning:{stage}:{mutation}")
    with pytest.raises(AppServerError) as error:
        asyncio.run(adapter(context, fake).draft(context))
    assert "FAKE_SECRET_WARNING" not in str(error.value)
    assert fake.methods().count("turn/start") == (0 if stage == "before-thread-response" else 1)
    assert_stopped(fake)


def test_warning_metadata_cannot_substitute_for_final_model_output(context, fake_factory):
    fake = fake_factory("warning-only")
    with pytest.raises(AppServerError, match="Missing or ambiguous Codex final output"):
        asyncio.run(adapter(context, fake).draft(context))
    assert_stopped(fake)


def test_informational_warnings_still_consume_stream_budget(context, fake_factory, monkeypatch):
    monkeypatch.setattr(app_server, "MAX_EVENTS", 20)
    fake = fake_factory("warning-burst")
    with pytest.raises(AppServerError, match="oversized Codex stream"):
        asyncio.run(adapter(context, fake).draft(context))
    assert "turn/start" not in fake.methods()
    assert_stopped(fake)


@pytest.mark.parametrize("budget", ["bytes", "events"])
def test_two_preflight_sessions_share_one_stream_budget(context, fake_factory, monkeypatch, budget):
    fake = fake_factory()
    if budget == "events":
        monkeypatch.setattr(app_server, "MAX_EVENTS", 3)
    else:
        discovery_config = nested_config()
        discovery_config["mcp_servers"] = {"inherited-server": {"enabled": True}}
        discovery_responses = [
            {"id": 1, "result": {"userAgent": "authzest/0.153.0"}},
            {"id": 2, "result": {"config": discovery_config}},
        ]
        first_session_bytes = sum(
            len((json.dumps(message) + "\n").encode()) for message in discovery_responses
        )
        # Enough for either session's initial metadata independently, not both combined.
        monkeypatch.setattr(app_server, "MAX_STREAM_BYTES", first_session_bytes + 100)
    with pytest.raises(AppServerError, match="oversized Codex stream"):
        asyncio.run(adapter(context, fake).draft(context))
    assert len(fake.starts()) == 2
    assert fake.methods() == [
        "initialize",
        "initialized",
        "config/read",
        "initialize",
        "initialized",
        "config/read",
    ]
    assert_stopped(fake)


def test_warning_count_includes_discovery_and_generation_sessions(context, fake_factory):
    fake = fake_factory("warning-per-session")
    transport = adapter(context, fake)
    result = asyncio.run(transport.draft(context))
    assert transport.warnings_seen == 2
    assert result.review.to_dict()["usage"] == {"input_tokens": 123, "output_tokens": 45}
    assert_stopped(fake)


@pytest.mark.parametrize("stage", ["before-turn-response", "during-turn"])
def test_observed_stream_disconnect_notice_recovers_only_with_fresh_same_turn_output(
    context, fake_factory, stage
):
    fake = fake_factory(f"stream-disconnected:{stage}")
    transport = adapter(context, fake)
    draft = asyncio.run(transport.draft(context))
    injected = next(
        event["message"] for event in fake.events() if event["event"] == "injected-error"
    )
    assert injected["params"]["willRetry"] is True
    assert set(injected["params"]["error"]["codexErrorInfo"]) == {"responseStreamDisconnected"}
    assert "FAKE_SECRET_ERROR_DETAIL" not in draft.review.payload_json + draft.proposal.payload_json
    assert transport.retry_notifications_seen == 1
    assert draft.review.to_dict()["usage"] == {"input_tokens": 123, "output_tokens": 45}
    assert draft.proposal.to_dict()["changes"][0]["after_text"] == FIXTURE_AFTER
    assert fake.methods().count("turn/start") == 1
    assert len(fake.starts()) == 2
    assert transport.consumed is True
    assert_stopped(fake)


@pytest.mark.parametrize(
    "scenario",
    [
        "connection-failed",
        "missing-http-status",
        "partial-reset",
        "no-refreshed-usage",
        "three-notices",
    ],
)
def test_bounded_retry_notices_reset_old_results_without_starting_another_turn(
    context, fake_factory, scenario
):
    fake = fake_factory(f"retry:{scenario}")
    transport = adapter(context, fake)
    draft = asyncio.run(transport.draft(context))
    assert transport.retry_notifications_seen == (3 if scenario == "three-notices" else 1)
    assert draft.proposal.to_dict()["changes"][0]["after_text"] == FIXTURE_AFTER
    expected_usage = (
        None if scenario == "no-refreshed-usage" else {"input_tokens": 123, "output_tokens": 45}
    )
    assert draft.review.to_dict()["usage"] == expected_usage
    assert fake.methods().count("turn/start") == 1 and len(fake.starts()) == 2
    assert transport.consumed is True
    assert_stopped(fake)


@pytest.mark.parametrize(
    "scenario",
    [
        "fatal-flag",
        "string-flag",
        "wrong-thread",
        "wrong-turn-before-response",
        "other-error",
        "extra-error-field",
        "extra-info-variant",
        "extra-params",
        "misalignment",
        "boolean-http",
        "unauthorized-http",
        "rate-limit-http",
        "non-string-message",
        "long-message",
        "long-details",
    ],
)
def test_fatal_malformed_or_unrelated_retry_notices_are_rejected(context, fake_factory, scenario):
    fake = fake_factory(f"retry:{scenario}")
    transport = adapter(context, fake)
    with pytest.raises(AppServerError):
        asyncio.run(transport.draft(context))
    assert transport.retry_notifications_seen is None
    assert fake.methods().count("turn/start") == 1 and len(fake.starts()) == 2
    assert_stopped(fake)


@pytest.mark.parametrize(
    "scenario",
    [
        "four-notices",
        "no-fresh-final",
        "old-final-replay",
        "bad-final-source",
        "failed-turn",
        "eof",
        "timeout",
        "tool-request",
        "before-turn-dispatch",
    ],
)
def test_retry_does_not_relax_completion_capability_or_lifecycle_boundaries(
    context, fake_factory, scenario
):
    fake = fake_factory(f"retry:{scenario}")
    transport = CodexAppServerAdapter(
        context.request_id, executable=str(fake.executable), timeout_seconds=2
    )
    with pytest.raises(AppServerError):
        asyncio.run(transport.draft(context))
    assert transport.retry_notifications_seen is None
    assert fake.methods().count("turn/start") == (0 if scenario == "before-turn-dispatch" else 1)
    assert len(fake.starts()) == 2
    assert_stopped(fake)


@pytest.mark.parametrize(
    "scenario",
    [
        "queued-terminal-before-error",
        "missing-start-turn-id",
        "missing-final-turn-id",
        "missing-usage-turn-id",
    ],
)
def test_retry_cannot_hide_queued_recovery_or_accept_unscoped_turn_evidence(
    context, fake_factory, scenario
):
    fake = fake_factory(f"retry:{scenario}")
    transport = adapter(context, fake)
    with pytest.raises(AppServerError):
        asyncio.run(transport.draft(context))
    assert transport.retry_notifications_seen is None
    assert fake.methods().count("turn/start") == 1
    assert len(fake.starts()) == 2
    assert_stopped(fake)
