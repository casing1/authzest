"""Offline frame choices use public selected schema shapes, not a live provider."""

from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import json
import shutil
import socket
import subprocess
from pathlib import Path

import jsonschema
import pytest
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_trial_plan as planner

ROOT = Path(__file__).resolve().parents[1]
PROJECTION = ROOT / "tests/fixtures/evaluation_protocol/v0153/selected_request_params.json"
METHODS = (
    "initialize",
    "initialized",
    "config/read",
    "remoteControl/status/read",
    "account/read",
    "model/list",
    "thread/start",
    "turn/start",
)


def config(**values: object) -> planner.TrialConfig:
    return planner.TrialConfig(
        **{
            "model": "proposed-model",
            "effort": "high",
            "repetitions": 1,
            "timeout_seconds": 30,
            **values,
        }
    )


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.fixture
def fixed(tmp_path):
    relative = Path("tests/fixtures/evaluation_reference/v1/tasks.json")
    (tmp_path / relative).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / relative, tmp_path / relative)
    return tmp_path


@pytest.fixture
def candidate(fixed):
    return codec.prepare_candidate(fixed, config())


@pytest.fixture
def invocation(candidate):
    return candidate.invocations[0]


def frames(invocation, **values):
    return recipe.frames(
        invocation, **{"cwd": "/synthetic/empty", "thread_id": "thread-synthetic", **values}
    )


def assert_no_execution(value):
    for flag in (
        "runtime_observed",
        "provider_freshness_verified",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "live_benchmark_ready",
        "model_quality_measured",
    ):
        assert value[flag] is False
    assert value["provider_calls_by_this_tool"] == value["live_trials"] == 0
    assert value["target_execution"] == "not-run"
    assert value["transport_status"] == "not-implemented"


def test_descriptor_is_materialized_detached_and_explicitly_not_effective_config():
    first = recipe.descriptor(config())
    assert first["name"] == "evaluation-stdio-0.153.0-v1"
    assert first["codex_version"] == "0.153.0"
    assert first["configuration"] == {
        "model": "proposed-model",
        "effort": "high",
        "repetitions": 1,
        "timeout_seconds": 30,
    }
    process = first["process_config"]
    assert process["model"] == "proposed-model"
    assert process["model_reasoning_effort"] == "high"
    assert process["approvals_reviewer"] == "user"
    assert process["developer_instructions"] == codec.INSTRUCTIONS
    assert process["notify"] == []
    assert first["instructions"] == dict.fromkeys(
        ("base", "developer", "collaboration_developer"), codec.INSTRUCTIONS
    )
    assert_no_execution(first)
    first["process_config"]["notify"].append("changed")
    first["disabled_features"].append("changed")
    first["generated_schema_evidence"]["raw_document_sha256"].clear()
    assert recipe.descriptor(config())["process_config"]["notify"] == []
    assert "changed" not in recipe.descriptor(config())["disabled_features"]
    assert recipe.descriptor(config())["generated_schema_evidence"]["raw_document_sha256"]


def test_owned_config_is_immutable_and_copies_baseline_without_product_import():
    with pytest.raises(TypeError):
        recipe.CONFIG["model_provider"] = "changed"
    assert type(recipe.CONFIG["notify"]) is tuple
    assert type(recipe.DISABLED_FEATURES) is tuple
    # Inspect the baseline as syntax/data; never import or evaluate product adapter code.
    tree = ast.parse((ROOT / "src/authzest/codex/app_server.py").read_text())
    assignments = {
        node.targets[0].id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    features = tuple(ast.literal_eval(assignments["DISABLED_FEATURES"].args[0]))
    assert features == recipe.DISABLED_FEATURES
    source_config = assignments["CONFIG"]
    materialized = recipe.descriptor(config())["process_config"]
    for key, value in zip(source_config.keys, source_config.values, strict=True):
        if key is None or ast.literal_eval(key) == "developer_instructions":
            continue
        assert materialized[ast.literal_eval(key)] == ast.literal_eval(value)
    for feature in features:
        assert materialized[f"features.{feature}"] is False
    own_tree = ast.parse((ROOT / "scripts/evaluation_dispatch_recipe.py").read_text())
    imports = [node.module or "" for node in ast.walk(own_tree) if isinstance(node, ast.ImportFrom)]
    assert not any("app_server" in name for name in imports)


def test_recipe_hash_independently_binds_entire_materialized_descriptor():
    value = recipe.descriptor(config())
    expected_id = "dispatch-recipe-" + digest(canonical(value))
    assert recipe.recipe_id(config()) == expected_id
    assert recipe.recipe_id(config()) == recipe.recipe_id(config())


@pytest.mark.parametrize(
    "values",
    [{"model": "other-model"}, {"effort": "ultra"}, {"repetitions": 2}, {"timeout_seconds": 31}],
)
def test_every_configuration_dimension_rebinds_recipe_identity(values):
    assert recipe.recipe_id(config()) != recipe.recipe_id(config(**values))


@pytest.mark.parametrize("repetitions,maximum", [(1, 1880), (2, 3700), (3, 5520)])
def test_integer_nanosecond_limits_and_dispatch_window_formula(repetitions, maximum):
    selected = config(repetitions=repetitions, timeout_seconds=120)
    limits = recipe.descriptor(selected)["limits"]
    assert recipe.dispatch_window_seconds(selected) == maximum
    assert limits["dispatch_window_seconds"] == maximum
    assert limits["dispatch_window_ns"] == maximum * 1_000_000_000
    assert limits["confirmation_ttl_ns"] == 300_000_000_000
    assert limits["clock_skew_ns"] == 5_000_000_000
    assert limits["frame_bytes"] == 262_144
    assert limits["received_stream_bytes"] == 2_097_152
    assert limits["received_events"] == 4096
    assert limits["queued_notifications"] == 128
    assert limits["max_process_groups_per_slot"] == 2
    assert limits["cleanup_seconds_per_group"] == 5
    assert limits["planned_slots"] == 14 * repetitions
    assert limits["question_opportunities"] == 42 * repetitions
    assert limits["model_pages"] == 10
    assert limits["models_per_page"] == 100
    assert limits["model_entries"] == 1000


def test_profile_declares_fail_closed_settings_retries_context_and_clock_policies():
    descriptor = recipe.descriptor(config())
    wire = descriptor["wire_policy"]
    assert wire["remote_control"] == "explicit-status-read-disabled-required"
    assert wire["initial_reasoning_effort"] == "non-null-exact-report-required"
    assert (
        wire["complete_matching_settings_observation"] == "required-no-null-or-missing-substitution"
    )
    assert wire["surfaced_retry"] == "batch-fatal-no-application-retry"
    assert wire["hidden_retry_bound"] is None
    assert "warning" not in wire["allowed_events"]
    assert "error" not in wire["allowed_events"]
    assert descriptor["state_policy"]["ordering_policy"] == planner.ORDER_POLICY
    assert descriptor["state_policy"]["preview_anchor"] == "original-monotonic-and-wall-no-reanchor"
    assert descriptor["state_policy"]["reservation"] == "consumes-slot-before-process-start"
    assert (
        descriptor["state_policy"]["failure"] == "stop-on-first-nonvalid-null-answers-remain-valid"
    )


def test_exact_frame_sequence_ids_and_notification_omit_unsupported_empty_params(invocation):
    result = frames(invocation, first_rpc_id=19)
    assert [item["method"] for item in result["frame_candidates"]] == list(METHODS)
    requests = [item["message"] for item in result["frame_candidates"] if "id" in item["message"]]
    assert [message["id"] for message in requests] == list(range(19, 26))
    assert all(type(message["id"]) is int for message in requests)
    assert result["frame_candidates"][1]["message"] == {"method": "initialized"}
    remote = next(
        item["message"]
        for item in result["frame_candidates"]
        if item["method"] == "remoteControl/status/read"
    )
    assert remote["params"] is None  # Pinned ClientRequest permits null/omitted, not {}.
    assert result["candidate_scope"] == "single-generation-first-catalog-page-not-sent"
    assert_no_execution(result)


def test_turn_frame_uses_exact_codec_bytes_schema_and_explicit_effort(invocation):
    result = frames(invocation)
    parameters = result["parameters"]
    thread, turn = parameters["thread/start"], parameters["turn/start"]
    assert turn["input"] == [{"type": "text", "text": invocation.message_text}]
    assert turn["outputSchema"] == invocation.output_schema
    assert result["original_message_sha256"] == invocation.original_message_sha256
    assert result["message_sha256"] == invocation.message_sha256
    assert result["output_schema_sha256"] == invocation.output_schema_sha256
    assert thread["model"] == turn["model"] == invocation.session.configuration.model
    assert thread["config"]["model_reasoning_effort"] == turn["effort"] == "high"
    assert thread["allowProviderModelFallback"] is False
    assert thread["ephemeral"] is True
    assert thread["baseInstructions"] == thread["developerInstructions"] == codec.INSTRUCTIONS
    assert thread["cwd"] == turn["cwd"] == "/synthetic/empty"
    assert turn["collaborationMode"] == {
        "mode": "default",
        "settings": {
            "model": "proposed-model",
            "reasoning_effort": "high",
            "developer_instructions": codec.INSTRUCTIONS,
        },
    }
    assert turn["serviceTierForTurn"] == "default"
    assert turn["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    for key in ("environments", "runtimeWorkspaceRoots"):
        assert thread[key] == turn[key] == []
    assert thread["dynamicTools"] == thread["selectedCapabilityRoots"] == []
    assert thread["approvalsReviewer"] == turn["approvalsReviewer"] == "user"
    assert parameters["account/read"] == {"refreshToken": False}
    assert parameters["model/list"] == {"limit": 100, "includeHidden": False}


def test_full_frames_bind_canonical_jsonl_including_newline_and_utf8_bytes(invocation):
    result = frames(invocation, cwd="/synthetic/한국어")
    for frame in result["frame_candidates"]:
        assert frame["frame_text"] == canonical(frame["message"]) + "\n"
        assert frame["frame_text"].endswith("\n")
        assert frame["frame_sha256"] == digest(frame["frame_text"])
        assert frame["frame_bytes"] == len(frame["frame_text"].encode("utf-8"))
        assert frame["frame_bytes"] <= recipe.MAX_FRAME_BYTES
        assert json.loads(frame["frame_text"]) == frame["message"]
    assert any(
        frame["frame_bytes"] > len(frame["frame_text"]) for frame in result["frame_candidates"]
    )


def test_frames_exports_are_detached_and_never_mutate_invocation(invocation):
    original = invocation.to_dict()
    before = frames(invocation)
    saved = copy.deepcopy(before)
    before["parameters"]["thread/start"]["config"]["model_reasoning_effort"] = "changed"
    before["frame_candidates"][-1]["message"]["params"]["input"][0]["text"] = "changed"
    assert frames(invocation) == saved
    assert invocation.to_dict() == original


def test_used_request_parameters_match_self_authored_pinned_experimental_projection(invocation):
    projection = json.loads(PROJECTION.read_text())
    assert projection["kind"] == "self-authored-selected-request-parameter-projection"
    assert projection["experimental"] is True
    assert projection["codex_version"] == "0.153.0"
    assert "not complete" in projection["scope"]
    for path, raw_hash in projection["source_documents"].items():
        assert recipe.SCHEMA_HASHES[path] == raw_hash
    value = frames(invocation)
    for method, params in value["parameters"].items():
        if method == "initialized":
            continue
        schema = {**projection["schemas"][method], "$defs": projection["$defs"]}
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(params)
    assert projection["schemas"]["turn/start"]["properties"]["outputSchema"] == {}
    # Presence of arbitrary JSON outputSchema is not nested/provider compatibility.
    changed = copy.deepcopy(value["parameters"]["turn/start"])
    changed["outputSchema"] = "not a provider-compatible JSON schema"
    schema = {**projection["schemas"]["turn/start"], "$defs": projection["$defs"]}
    jsonschema.Draft202012Validator(schema).validate(changed)


def test_projection_preserves_null_remote_params_not_product_empty_object():
    projection = json.loads(PROJECTION.read_text())
    schema = projection["schemas"]["remoteControl/status/read"]
    jsonschema.Draft202012Validator(schema).validate(None)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate({})


def test_projection_selects_empty_complex_arrays_not_underconstrained_nonempty_items(invocation):
    projection = json.loads(PROJECTION.read_text())
    schema = {**projection["schemas"]["thread/start"], "$defs": projection["$defs"]}
    validator = jsonschema.Draft202012Validator(schema)
    for key in ("environments", "dynamicTools", "selectedCapabilityRoots"):
        changed = copy.deepcopy(frames(invocation)["parameters"]["thread/start"])
        changed[key] = [{}]
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(changed)


@pytest.mark.parametrize("value", [None, {}, True, 0])
def test_invalid_config_types_are_not_syntax_coerced(value):
    for function in (recipe.descriptor, recipe.recipe_id, recipe.dispatch_window_seconds):
        with pytest.raises(recipe.RecipeError, match="invalid-configuration"):
            function(value)


def test_tampered_frozen_config_is_revalidated():
    selected = config()
    object.__setattr__(selected, "timeout_seconds", True)
    with pytest.raises(recipe.RecipeError, match="invalid-configuration"):
        recipe.descriptor(selected)


@pytest.mark.parametrize(
    "cwd",
    [
        None,
        True,
        "relative",
        "/has/../parent",
        "/has/./part",
        "/two//parts",
        "/bad\\path",
        "/bad\npath",
        "/\ud800",
        "/" + "x" * 1024,
    ],
)
def test_cwd_is_only_a_strict_bounded_absolute_label(invocation, cwd):
    with pytest.raises(recipe.RecipeError, match="invalid-cwd-label"):
        frames(invocation, cwd=cwd)


@pytest.mark.parametrize("thread_id", [None, True, "", "has space", "bad/id", "x" * 129, "한글"])
def test_thread_label_is_a_strict_bounded_id_not_runtime_evidence(invocation, thread_id):
    with pytest.raises(recipe.RecipeError, match="invalid-thread-label"):
        frames(invocation, thread_id=thread_id)


@pytest.mark.parametrize("first_rpc_id", [True, None, "1", 1.0, 0, -1, 2**31 - 6])
def test_rpc_ids_are_exact_positive_bounded_ints_for_whole_candidate_sequence(
    invocation, first_rpc_id
):
    with pytest.raises(recipe.RecipeError, match="invalid-rpc-id"):
        frames(invocation, first_rpc_id=first_rpc_id)


def test_request_frame_size_is_checked_after_full_encoding_not_individual_codec_limits(
    invocation, monkeypatch
):
    original = frames(invocation)
    largest = max(frame["frame_bytes"] for frame in original["frame_candidates"])
    monkeypatch.setattr(recipe, "MAX_FRAME_BYTES", largest)
    assert frames(invocation)["frame_candidates"]
    monkeypatch.setattr(recipe, "MAX_FRAME_BYTES", largest - 1)
    with pytest.raises(recipe.RecipeError, match="frame-too-large"):
        frames(invocation)


def test_wrong_or_corrupted_owned_invocation_is_not_a_partial_frame_success(invocation):
    with pytest.raises(recipe.RecipeError, match="invalid-invocation"):
        frames({})
    changed = copy.copy(invocation)
    object.__setattr__(changed, "original_message", "{}")
    with pytest.raises(recipe.RecipeError, match="invalid-invocation"):
        frames(changed)


def test_frame_preparation_performs_no_filesystem_account_process_or_network_io(
    invocation, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "offline descriptor/frames cannot perform I/O, auth, processes or provider calls"
        )

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(planner, "build_trial_plan", forbidden)
    monkeypatch.setattr(codec, "prepare_candidate", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "score_reference", forbidden)
    assert recipe.descriptor(config())["process_config"]["model"] == "proposed-model"
    assert frames(invocation)["frame_candidates"]
