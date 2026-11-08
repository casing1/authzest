"""Selected synthetic declarations, never real login, model access or fresh sessions."""

from __future__ import annotations

import builtins
import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts import evaluation_session_semantics as session
from scripts import evaluation_trial_plan as planner


def configuration(**values):
    return planner.TrialConfig(
        **{
            "model": "requested-model",
            "effort": "high",
            "repetitions": 1,
            "timeout_seconds": 30,
            **values,
        }
    )


def boundary():
    return common.Boundary(configuration(), "/synthetic/empty", "thread-synthetic")


def initialize():
    return {
        "userAgent": "codex_cli_rs/0.153.0 (synthetic)",
        "codexHome": "/private/synthetic",
        "platformFamily": "unix",
        "platformOs": "linux",
    }


def remote():
    return {
        "installationId": "private-installation",
        "serverName": "private-server",
        "status": "disabled",
    }


def account():
    return {
        "requiresOpenaiAuth": True,
        "account": {"type": "chatgpt", "email": "private@example.test", "planType": "plus"},
    }


def model(name="requested-model", identity=None):
    return {
        "id": identity or name,
        "model": name,
        "displayName": "Private display",
        "description": "Private description",
        "hidden": False,
        "isDefault": False,
        "defaultReasoningEffort": "low",
        "supportedReasoningEfforts": [
            {"reasoningEffort": value, "description": "private"} for value in ("low", "high")
        ],
    }


def pages():
    return [{"data": [model()], "nextCursor": None}]


def sandbox():
    return {"type": "readOnly", "networkAccess": False}


def thread_start():
    expected = boundary()
    return {
        "model": expected.configuration.model,
        "modelProvider": "openai",
        "cwd": expected.cwd,
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        "sandbox": sandbox(),
        "reasoningEffort": expected.configuration.effort,
        "instructionSources": [],
        "runtimeWorkspaceRoots": [],
        "thread": {
            "cliVersion": "0.153.0",
            "createdAt": 1,
            "updatedAt": 2,
            "cwd": expected.cwd,
            "ephemeral": True,
            "id": expected.thread_id,
            "modelProvider": "openai",
            "preview": "",
            "projectId": None,
            "sessionId": "distinct-session-synthetic",
            "source": "appServer",
            "status": {"type": "idle"},
            "turns": [],
        },
    }


def settings():
    expected = boundary()
    return {
        "threadId": expected.thread_id,
        "threadSettings": {
            "model": expected.configuration.model,
            "modelProvider": "openai",
            "cwd": expected.cwd,
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "sandboxPolicy": sandbox(),
            "effort": expected.configuration.effort,
            "collaborationMode": {
                "mode": "default",
                "settings": {
                    "model": expected.configuration.model,
                    "reasoning_effort": expected.configuration.effort,
                    "developer_instructions": codec.INSTRUCTIONS,
                },
            },
        },
    }


CASES = (
    ("initialize", initialize, session.check_initialize),
    ("remote", remote, session.check_remote),
    ("account", account, session.check_account),
    ("catalog", pages, lambda value: session.check_catalog(value, configuration())),
    ("thread-start", thread_start, lambda value: session.check_thread_start(value, boundary())),
    ("settings", settings, lambda value: session.check_settings(value, boundary())),
)


@pytest.mark.parametrize("name,factory,validate", CASES)
def test_valid_candidates_are_detached_redacted_matches_not_runtime_or_authentication(
    name, factory, validate
):
    candidate = factory()
    before = copy.deepcopy(candidate)
    result = validate(candidate)
    assert candidate == before
    assert result["check"] == name
    assert result["supplied_fields_match"] is True
    for key in (
        "runtime_observed",
        "provider_freshness_verified",
        "authenticated",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "ready_for_live_trial",
        "accepted_trial",
        "transport_implemented",
        "target_executed",
    ):
        assert result[key] is False
    assert result["actual_model_calls"] == 0
    encoded = json.dumps(result)
    for secret in (
        "private",
        "requested-model",
        "thread-synthetic",
        "distinct-session",
        "/synthetic",
        "example.test",
        "sha256",
        "userAgent",
    ):
        assert secret not in encoded
    result["check"] = "changed"
    assert validate(candidate)["check"] == name


@pytest.mark.parametrize("name,factory,validate", CASES)
def test_malformed_top_levels_are_closed_errors_never_partial_matches(name, factory, validate):
    for value in (None, True, 0, "private", {}, []):
        with pytest.raises(common.SemanticError):
            validate(value)


def test_initialize_requires_all_generated_selected_fields_and_unsupported_fields_fail():
    for field in initialize():
        candidate = initialize()
        del candidate[field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_initialize(candidate)
    candidate = initialize()
    candidate["privateExtra"] = None
    with pytest.raises(common.SemanticError, match="unsupported-fields"):
        session.check_initialize(candidate)


@pytest.mark.parametrize(
    "agent", ["codex/0.152.0", "codex/0.153.00", "0.153.0", "codex/0.153.0suffix"]
)
def test_initialize_pinned_version_token_not_prefix_or_unversioned_claim(agent):
    candidate = initialize()
    candidate["userAgent"] = agent
    with pytest.raises(common.SemanticError, match="version-mismatch"):
        session.check_initialize(candidate)


def test_initialize_is_source_posix_only_without_reading_or_echoing_home():
    candidate = initialize()
    candidate["platformOs"] = "macos"
    session.check_initialize(candidate)
    for key, value in (
        ("platformFamily", "windows"),
        ("platformOs", "windows"),
        ("codexHome", "relative-private"),
    ):
        candidate = initialize()
        candidate[key] = value
        with pytest.raises(common.SemanticError):
            session.check_initialize(candidate)


@pytest.mark.parametrize("status", ["connecting", "connected", "errored", None, {}, 0])
def test_remote_requires_explicit_disabled_status_not_missing_notification(status):
    candidate = remote()
    candidate["status"] = status
    with pytest.raises(common.SemanticError, match="remote-not-disabled"):
        session.check_remote(candidate)


def test_remote_requires_generated_metadata_and_refuses_nonnull_environment_subset():
    for field in remote():
        candidate = remote()
        del candidate[field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_remote(candidate)
    candidate = remote()
    candidate["environmentId"] = None
    session.check_remote(candidate)
    candidate["environmentId"] = "private-environment"
    with pytest.raises(common.SemanticError, match="unsupported-context"):
        session.check_remote(candidate)


@pytest.mark.parametrize("requires_auth", [True, False])
def test_auth_requirement_bool_is_not_login_authentication_or_entitlement(requires_auth):
    candidate = account()
    candidate["requiresOpenaiAuth"] = requires_auth
    assert session.check_account(candidate)["authenticated"] is False


@pytest.mark.parametrize("plan", [None, [], {}, 0, True, "invented-private-plan"])
def test_account_plan_malformed_containers_are_semantic_errors_not_typeerrors(plan):
    candidate = account()
    candidate["account"]["planType"] = plan
    with pytest.raises(common.SemanticError, match="unsupported-plan-declaration"):
        session.check_account(candidate)


def test_account_requires_chatgpt_shaped_declaration_and_exact_bool_not_truthiness():
    for value in (None, {}, {"type": "apiKey"}, {"type": "amazonBedrock"}):
        candidate = account()
        candidate["account"] = value
        with pytest.raises(common.SemanticError):
            session.check_account(candidate)
    for value in (None, 0, "true", []):
        candidate = account()
        candidate["requiresOpenaiAuth"] = value
        with pytest.raises(common.SemanticError, match="invalid-auth-requirement"):
            session.check_account(candidate)
    candidate = account()
    candidate["account"]["email"] = None
    session.check_account(candidate)


def test_catalog_requested_effort_is_explicit_not_default_and_id_is_not_an_alias():
    candidate = pages()
    assert candidate[0]["data"][0]["defaultReasoningEffort"] != configuration().effort
    result = session.check_catalog(candidate, configuration())
    assert result["pages_count"] == result["models_count"] == 1
    candidate[0]["data"][0]["model"] = "different-model"
    with pytest.raises(common.SemanticError, match="model-not-advertised"):
        session.check_catalog(candidate, configuration())


def test_catalog_empty_or_missing_fields_in_any_model_are_not_silently_skipped():
    for field in model():
        candidate = pages()
        del candidate[0]["data"][0][field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_catalog(candidate, configuration())
    candidate = pages()
    candidate[0]["data"].append(None)
    with pytest.raises(common.SemanticError):
        session.check_catalog(candidate, configuration())


@pytest.mark.parametrize("field", ["id", "model"])
def test_catalog_duplicate_identity_or_selector_is_ambiguous_even_across_pages(field):
    first, second = model(), model("different", "other-id")
    second[field] = first[field]
    candidate = [{"data": [first], "nextCursor": "cursor"}, {"data": [second], "nextCursor": None}]
    with pytest.raises(common.SemanticError, match="duplicate-model"):
        session.check_catalog(candidate, configuration())


def test_catalog_supplied_cursor_uniqueness_and_terminal_null_not_actual_request_chain():
    candidate = [
        {"data": [model()], "nextCursor": "cursor-a"},
        {"data": [], "nextCursor": "cursor-b"},
        {"data": [], "nextCursor": None},
    ]
    result = session.check_catalog(candidate, configuration())
    assert result["pages_count"] == 3 and result["runtime_observed"] is False
    candidate[1]["nextCursor"] = "cursor-a"
    with pytest.raises(common.SemanticError, match="catalog-cursor-cycle"):
        session.check_catalog(candidate, configuration())
    candidate[1]["nextCursor"] = "cursor-b"
    candidate[-1]["nextCursor"] = "not-complete"
    with pytest.raises(common.SemanticError, match="incomplete-catalog"):
        session.check_catalog(candidate, configuration())


def test_catalog_page_count_and_size_limits_exact_10_by_100():
    candidate = [
        {
            "data": [model(f"model-{page}-{index}") for index in range(100)],
            "nextCursor": f"cursor-{page}" if page < 9 else None,
        }
        for page in range(10)
    ]
    candidate[0]["data"][0] = model()
    result = session.check_catalog(candidate, configuration())
    assert result["pages_count"] == 10 and result["models_count"] == 1000
    candidate[-1]["data"].append(model("extra"))
    with pytest.raises(common.SemanticError, match="invalid-catalog-page"):
        session.check_catalog(candidate, configuration())
    with pytest.raises(common.SemanticError, match="invalid-catalog-pages"):
        session.check_catalog([{"data": [], "nextCursor": None}] * 11, configuration())


def test_catalog_requires_strict_page_list_and_explicit_completion_fields():
    for candidate in (tuple(pages()), [], [{"data": []}], [{"data": [], "nextCursor": None}]):
        with pytest.raises(common.SemanticError):
            session.check_catalog(candidate, configuration())


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("hidden", True, "hidden-model"),
        ("hidden", 0, "hidden-model"),
        ("isDefault", 0, "invalid-model-metadata"),
        ("supportedReasoningEfforts", [], "invalid-effort-options"),
        ("defaultReasoningEffort", "unsupported", "invalid-effort-default"),
    ],
)
def test_catalog_hidden_and_malformed_required_metadata_refused(field, value, code):
    candidate = pages()
    candidate[0]["data"][0][field] = value
    with pytest.raises(common.SemanticError, match=code):
        session.check_catalog(candidate, configuration())


def test_catalog_requires_requested_advertised_effort_and_unique_well_formed_options():
    candidate = pages()
    candidate[0]["data"][0]["supportedReasoningEfforts"].pop()
    with pytest.raises(common.SemanticError, match="effort-not-advertised"):
        session.check_catalog(candidate, configuration())
    candidate = pages()
    candidate[0]["data"][0]["supportedReasoningEfforts"] *= 2
    with pytest.raises(common.SemanticError, match="duplicate-effort-option"):
        session.check_catalog(candidate, configuration())
    for malformed in (None, {}, {"reasoningEffort": []}, {"reasoningEffort": "high"}):
        candidate = pages()
        candidate[0]["data"][0]["supportedReasoningEfforts"] = [malformed]
        with pytest.raises(common.SemanticError):
            session.check_catalog(candidate, configuration())


def test_catalog_nullable_complex_fields_are_narrow_subset_not_ignored_unknown_context():
    for field in (
        "availabilityNux",
        "defaultServiceTier",
        "modelSpecialty",
        "multiAgentVersion",
        "upgrade",
        "upgradeInfo",
    ):
        candidate = pages()
        candidate[0]["data"][0][field] = None
        session.check_catalog(candidate, configuration())
        candidate[0]["data"][0][field] = {}
        with pytest.raises(common.SemanticError, match="unsupported-context"):
            session.check_catalog(candidate, configuration())


def test_catalog_generated_modalities_include_audio_but_require_unique_text_support():
    candidate = pages()
    candidate[0]["data"][0]["inputModalities"] = ["text", "image", "audio"]
    session.check_catalog(candidate, configuration())
    for value in (["image"], ["text", "text"], [[]], None, ["invented"]):
        candidate[0]["data"][0]["inputModalities"] = value
        with pytest.raises(common.SemanticError, match="invalid-model-metadata"):
            session.check_catalog(candidate, configuration())


def test_thread_start_requires_all_fields_without_defaulting_missing_empty_or_effort():
    for field in thread_start():
        candidate = thread_start()
        del candidate[field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_thread_start(candidate, boundary())
    for field in thread_start()["thread"]:
        candidate = thread_start()
        del candidate["thread"][field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_thread_start(candidate, boundary())


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "other"),
        ("modelProvider", "other"),
        ("cwd", "/elsewhere"),
        ("approvalPolicy", "never"),
        ("approvalsReviewer", "auto_review"),
        ("reasoningEffort", None),
        ("reasoningEffort", "medium"),
    ],
)
def test_thread_start_exact_negotiated_boundary(field, value):
    candidate = thread_start()
    candidate[field] = value
    with pytest.raises(common.SemanticError, match="boundary-mismatch"):
        session.check_thread_start(candidate, boundary())


def test_thread_start_no_history_parent_fork_instruction_root_or_named_profile():
    for field in ("instructionSources", "runtimeWorkspaceRoots"):
        candidate = thread_start()
        candidate[field] = ["private-path"]
        with pytest.raises(common.SemanticError, match="unexpected-thread-context"):
            session.check_thread_start(candidate, boundary())
    for field in ("forkedFromId", "parentThreadId", "path", "agentRole", "gitInfo", "extra"):
        candidate = thread_start()
        candidate["thread"][field] = None
        session.check_thread_start(candidate, boundary())
        candidate["thread"][field] = "private-context"
        with pytest.raises(common.SemanticError, match="unsupported-context"):
            session.check_thread_start(candidate, boundary())
    candidate = thread_start()
    candidate["activePermissionProfile"] = {"id": ":workspace"}
    with pytest.raises(common.SemanticError, match="unsupported-context"):
        session.check_thread_start(candidate, boundary())


@pytest.mark.parametrize(
    "field,value",
    [
        ("ephemeral", False),
        ("ephemeral", 1),
        ("source", "cli"),
        ("source", {"subAgent": {}}),
        ("status", {"type": "active", "activeFlags": []}),
        ("preview", "previous history"),
        ("turns", [{}]),
        ("projectId", "private-project"),
        ("cliVersion", "0.152.0"),
        ("sessionId", "invalid/id"),
        ("id", "foreign-thread"),
    ],
)
def test_thread_start_rejects_unexpected_root_session_declarations(field, value):
    candidate = thread_start()
    candidate["thread"][field] = value
    with pytest.raises(common.SemanticError):
        session.check_thread_start(candidate, boundary())


def test_distinct_session_id_is_not_forced_equal_to_thread_or_freshness_proof():
    candidate = thread_start()
    assert candidate["thread"]["sessionId"] != boundary().thread_id
    assert session.check_thread_start(candidate, boundary())["provider_freshness_verified"] is False


def test_thread_timestamps_are_int_not_bool_and_not_runtime_wall_clock_observation():
    for field, value in (
        ("createdAt", True),
        ("updatedAt", 0),
        ("createdAt", -1),
        ("updatedAt", 2**63),
    ):
        candidate = thread_start()
        candidate["thread"][field] = value
        with pytest.raises(common.SemanticError):
            session.check_thread_start(candidate, boundary())


def test_thread_and_settings_sandbox_requires_explicit_false_not_missing_or_zero():
    for factory, key, validate in (
        (thread_start, "sandbox", session.check_thread_start),
        (settings, "sandboxPolicy", session.check_settings),
    ):
        for value in (
            {"type": "readOnly"},
            {"type": "readOnly", "networkAccess": 0},
            {"type": "readOnly", "networkAccess": True},
            {"type": "dangerFullAccess"},
        ):
            candidate = factory()
            target = candidate if key == "sandbox" else candidate["threadSettings"]
            target[key] = value
            with pytest.raises(common.SemanticError):
                validate(candidate, boundary())


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "other"),
        ("modelProvider", "other"),
        ("cwd", "/elsewhere"),
        ("approvalPolicy", "never"),
        ("approvalsReviewer", "auto_review"),
        ("effort", None),
        ("effort", "medium"),
    ],
)
def test_settings_must_match_explicit_boundary_without_nullable_effort(field, value):
    candidate = settings()
    candidate["threadSettings"][field] = value
    with pytest.raises(common.SemanticError, match="boundary-mismatch"):
        session.check_settings(candidate, boundary())


def test_settings_requires_every_selected_field_and_matching_thread_identity():
    for field in settings()["threadSettings"]:
        candidate = settings()
        del candidate["threadSettings"][field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_settings(candidate, boundary())
    candidate = settings()
    candidate["threadId"] = "foreign"
    with pytest.raises(common.SemanticError, match="thread-id-mismatch"):
        session.check_settings(candidate, boundary())


def test_collaboration_requires_nonnull_same_model_effort_and_common_instructions():
    for field in ("model", "reasoning_effort", "developer_instructions"):
        for value in (None, "different", {}, 0):
            candidate = settings()
            candidate["threadSettings"]["collaborationMode"]["settings"][field] = value
            with pytest.raises(common.SemanticError, match="collaboration-mismatch"):
                session.check_settings(candidate, boundary())
        candidate = settings()
        del candidate["threadSettings"]["collaborationMode"]["settings"][field]
        with pytest.raises(common.SemanticError, match="missing-selected-fields"):
            session.check_settings(candidate, boundary())


def test_settings_unreviewed_optional_context_must_be_null_and_multiagent_mode_fixed():
    for field in ("activePermissionProfile", "personality", "summary", "serviceTier"):
        candidate = settings()
        candidate["threadSettings"][field] = None
        session.check_settings(candidate, boundary())
        candidate["threadSettings"][field] = "private"
        with pytest.raises(common.SemanticError, match="unsupported-context"):
            session.check_settings(candidate, boundary())
    candidate = settings()
    candidate["threadSettings"]["multiAgentMode"] = "proactive"
    with pytest.raises(common.SemanticError, match="unsupported-multi-agent-mode"):
        session.check_settings(candidate, boundary())


def test_boundary_and_configuration_objects_are_revalidated_without_coercion():
    for value in (None, {}, True):
        with pytest.raises(common.SemanticError, match="invalid-boundary"):
            session.check_settings(settings(), value)
        with pytest.raises(common.SemanticError, match="invalid-configuration"):
            session.check_catalog(pages(), value)
    expected = boundary()
    object.__setattr__(expected.configuration, "timeout_seconds", True)
    with pytest.raises(common.SemanticError, match="invalid-configuration"):
        session.check_thread_start(thread_start(), expected)
    forged = object.__new__(planner.TrialConfig)
    with pytest.raises(common.SemanticError, match="invalid-configuration"):
        session.check_catalog(pages(), forged)


def test_all_entrypoints_reject_bounded_adversarial_input_before_semantic_interpretation():
    for name, factory, validate in CASES:
        for bad in ("\ud800private", float("nan"), b"private", ("private",)):
            candidate = factory()
            target = candidate[0] if name == "catalog" else candidate
            target["private"] = bad
            with pytest.raises(common.SemanticError) as error:
                validate(candidate)
            assert "private" not in repr(error.value)
        candidate = factory()
        target = candidate[0] if name == "catalog" else candidate
        target["private"] = target
        with pytest.raises(common.SemanticError, match="cyclic-input"):
            validate(candidate)


def test_large_and_deep_candidates_are_rejected_without_echo_or_partial_success():
    candidate = initialize()
    candidate["userAgent"] = "private" * common.MAX_BYTES
    with pytest.raises(common.SemanticError, match="input-too-large"):
        session.check_initialize(candidate)
    nested = None
    for _ in range(common.MAX_DEPTH + 1):
        nested = [nested]
    candidate = remote()
    candidate["private"] = nested
    with pytest.raises(common.SemanticError, match="input-too-deep"):
        session.check_remote(candidate)


def test_all_entrypoints_perform_no_io_process_account_network_or_reference_access(monkeypatch):
    candidates = [(factory(), validate) for _, factory, validate in CASES]

    def forbidden(*args, **kwargs):
        pytest.fail("selected semantic checks cannot access external state or reference answers")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(planner, "build_trial_plan", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "score_reference", forbidden)
    for candidate, validate in candidates:
        assert validate(candidate)["runtime_observed"] is False
