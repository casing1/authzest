"""Offline trial candidates bind explicit content without authorizing live work."""

from __future__ import annotations

import builtins
import copy
import hashlib
import json
import shutil
import socket
import subprocess
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path

import pytest
from scripts import evaluation_trial_plan as planner


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def identity(prefix: str, value: object) -> str:
    return prefix + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def config(**values: object) -> planner.TrialConfig:
    return planner.TrialConfig(
        **{
            "model": "proposed-model",
            "effort": "proposed-effort",
            "repetitions": 2,
            "timeout_seconds": 30,
            **values,
        }
    )


@pytest.fixture
def fixed(tmp_path: Path) -> Path:
    directory = tmp_path / planner.comparison.reference.REFERENCE
    directory.mkdir(parents=True)
    shutil.copyfile(
        planner.ROOT / planner.comparison.reference.REFERENCE / "tasks.json",
        directory / "tasks.json",
    )
    return tmp_path


def rebind_request(task: dict, mode: str) -> None:
    wrapper = task["packets"][mode]
    payload = wrapper["payload"]
    bound = {key: value for key, value in payload.items() if key != "request_id"}
    wrapper["request_id"] = payload["request_id"] = identity(
        "request-", {"mode": mode, "payload": bound}
    )


def mocked_packets(fixed: Path, monkeypatch) -> dict:
    comparison_plan = planner.comparison.build_plan(fixed)
    monkeypatch.setattr(
        planner.comparison, "build_plan", lambda root: copy.deepcopy(comparison_plan)
    )
    return comparison_plan


@pytest.mark.parametrize("repetitions", [1, 2, 3])
def test_every_planned_slot_and_opportunity_is_preserved_without_live_execution(fixed, repetitions):
    plan = planner.build_trial_plan(fixed, config(repetitions=repetitions))
    assert plan["kind"] == "offline-evaluation-trial-plan"
    assert plan["schema_version"] == "0.1"
    assert plan["status"] == "candidate-not-live-frozen"
    assert plan["case_count"] == 7
    assert plan["questions_per_mode_repetition"] == 21
    assert plan["modes"] == ["model-only", "evidence-assisted"]
    assert len(plan["packets"]) == 14
    assert len(plan["schedule"]) == 14 * repetitions
    assert plan["budget"] == {
        "planned_authzest_attempts": 14 * repetitions,
        "planned_question_opportunities": 42 * repetitions,
        "nominal_adapter_timeout_sum_seconds": 14 * repetitions * 30,
        "wall_clock_hard_cap_seconds": None,
        "token_or_credit_hard_cap": None,
        "codex_internal_retry_bound": None,
    }
    assert (
        plan["failure_policy"]
        == "retain-every-planned-slot-no-replacement-required-not-implemented"
    )
    assert plan["context_policy"] == "fresh-context-per-slot-required-not-implemented"
    assert plan["attempt_policy"] == "one-attempt-per-slot-no-authzest-retry-or-model-fallback"
    assert plan["transport_status"] == "not-implemented"
    assert plan["provider_calls_by_this_tool"] == 0
    assert plan["live_trials"] == 0
    assert plan["responses_collected"] == 0
    assert plan["scoring_status"] == "not-run"
    assert plan["target_execution"] == "not-run"
    for flag in (
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "live_benchmark_ready",
        "model_quality_measured",
        "citation_support_measured",
        "repeat_variation_measured",
        "wire_or_effective_context_verified",
    ):
        assert plan[flag] is False
    assert plan["model_availability"] == "unverified"
    assert plan["effort_support"] == "unverified"
    assert plan["evaluation_independence"] == "not-established-public-developed-tasks"
    assert plan["static_baseline"] == "separate-deterministic-observation-not-a-provider-trial"


def test_ids_independently_bind_configuration_packets_and_whole_candidate(fixed):
    selected = config()
    plan = planner.build_trial_plan(fixed, selected)
    expected_config = {
        "policy_version": planner.POLICY_VERSION,
        "values": asdict(selected),
        "order_policy": planner.ORDER_POLICY,
        "context_policy": planner.CONTEXT_POLICY,
        "attempt_policy": planner.ATTEMPT_POLICY,
        "failure_policy": planner.FAILURE_POLICY,
    }
    assert plan["configuration_id"] == identity("trial-config-", expected_config)
    assert plan["packet_set_id"] == identity("packet-set-", plan["packets"])
    assert plan["plan_id"] == identity(
        "trial-plan-", {key: value for key, value in plan.items() if key != "plan_id"}
    )
    for slot in plan["schedule"]:
        assert slot["trial_id"] == identity(
            "trial-", {key: value for key, value in slot.items() if key != "trial_id"}
        )


def test_message_bytes_hashes_and_content_exactly_match_existing_payloads(fixed):
    source_plan = planner.comparison.build_plan(fixed)
    original = {
        (task["task_id"], mode): task["packets"][mode]["payload"]
        for task in source_plan["tasks"]
        for mode in planner.AI_MODES
    }
    plan = planner.build_trial_plan(fixed, config())
    for packet in plan["packets"]:
        text = packet["message_text"]
        encoded = text.encode("utf-8")
        payload = json.loads(text)
        assert payload == original[packet["task_id"], packet["mode"]]
        assert text == canonical(payload)
        assert packet["message_sha256"] == hashlib.sha256(encoded).hexdigest()
        assert packet["message_bytes"] == len(encoded)
        assert packet["message_bytes"] <= planner.MAX_MESSAGE_BYTES
        assert packet["request_id"] == payload["request_id"]
        assert "mode" not in payload
        assert "configuration_id" not in payload
        assert "repetition" not in payload
    first_payload = json.loads(plan["packets"][0]["message_text"])
    assert (
        plan["common_prompt_sha256"]
        == hashlib.sha256(first_payload["instructions"].encode("utf-8")).hexdigest()
    )
    assert plan["answer_contract_descriptor_id"] == identity(
        "contract-", first_payload["answer_contract"]
    )
    assert "answer_contract_id" not in plan
    assert any(
        "descriptor, not validator implementation bytes" in item for item in plan["limitations"]
    )


def test_slots_alternate_first_mode_by_case_and_repetition_without_claiming_randomization(fixed):
    plan = planner.build_trial_plan(fixed, config(repetitions=3))
    task_ids = sorted({packet["task_id"] for packet in plan["packets"]})
    expected = []
    for repeat in range(3):
        for index, task_id in enumerate(task_ids):
            order = (
                ("model-only", "evidence-assisted")
                if (index + repeat) % 2 == 0
                else ("evidence-assisted", "model-only")
            )
            expected.extend((repeat + 1, task_id, mode) for mode in order)
    assert [
        (slot["repetition"], slot["task_id"], slot["mode"]) for slot in plan["schedule"]
    ] == expected
    assert [slot["ordinal"] for slot in plan["schedule"]] == list(range(1, 43))
    assert len({slot["trial_id"] for slot in plan["schedule"]}) == 42
    assert any("order is not random" in item for item in plan["limitations"])


def test_repetitions_reuse_message_request_ids_but_never_trial_ids_or_freshness_claims(fixed):
    plan = planner.build_trial_plan(fixed, config(repetitions=3))
    for packet in plan["packets"]:
        matching = [
            slot
            for slot in plan["schedule"]
            if (slot["task_id"], slot["mode"]) == (packet["task_id"], packet["mode"])
        ]
        assert len(matching) == 3
        assert {slot["request_id"] for slot in matching} == {packet["request_id"]}
        assert {slot["message_sha256"] for slot in matching} == {packet["message_sha256"]}
        assert len({slot["trial_id"] for slot in matching}) == 3
    limits = " ".join(plan["limitations"])
    assert "not consent tokens or response-freshness proof" in limits
    assert "does not bind model/configuration/repetition or fresh invocations" in limits
    assert "Fresh isolated contexts" in limits
    assert "not enforced here" in limits


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "other-model"),
        ("effort", "other-effort"),
        ("timeout_seconds", 31),
        ("repetitions", 3),
    ],
)
def test_config_changes_rebind_plan_and_trial_identity_not_message_or_request_ids(
    fixed, field, value
):
    before = planner.build_trial_plan(fixed, config())
    after = planner.build_trial_plan(fixed, replace(config(), **{field: value}))
    assert before["configuration_id"] != after["configuration_id"]
    assert before["plan_id"] != after["plan_id"]
    assert before["packets"] == after["packets"]
    assert before["packet_set_id"] == after["packet_set_id"]
    assert {slot["trial_id"] for slot in before["schedule"]}.isdisjoint(
        slot["trial_id"] for slot in after["schedule"]
    )


@pytest.mark.parametrize(
    "constant",
    ["POLICY_VERSION", "ORDER_POLICY", "CONTEXT_POLICY", "ATTEMPT_POLICY", "FAILURE_POLICY"],
)
def test_scheduling_and_attempt_policy_versions_are_bound_not_untracked_comments(
    fixed, monkeypatch, constant
):
    before = planner.build_trial_plan(fixed, config())
    monkeypatch.setattr(planner, constant, "changed-policy-for-test")
    after = planner.build_trial_plan(fixed, config())
    assert before["configuration_id"] != after["configuration_id"]
    assert before["plan_id"] != after["plan_id"]
    assert before["packets"] == after["packets"]


def test_repeated_build_is_deterministic_and_exported_mutation_does_not_change_future_plan(fixed):
    before = planner.build_trial_plan(fixed, config())
    assert planner.build_trial_plan(fixed, config()) == before
    saved_id = before["plan_id"]
    before["schedule"][0]["request_id"] = "changed"
    before["packets"][0]["message_text"] = "changed"
    assert planner.build_trial_plan(fixed, config())["plan_id"] == saved_id


@pytest.mark.parametrize(
    "values,error",
    [
        ({"model": ""}, "invalid-model-label"),
        ({"model": "has space"}, "invalid-model-label"),
        ({"model": "a" * 81}, "invalid-model-label"),
        ({"model": None}, "invalid-model-label"),
        ({"model": []}, "invalid-model-label"),
        ({"effort": "UPPER"}, "invalid-effort-label"),
        ({"effort": "a" * 21}, "invalid-effort-label"),
        ({"effort": None}, "invalid-effort-label"),
        ({"repetitions": True}, "invalid-repetitions"),
        ({"repetitions": 1.0}, "invalid-repetitions"),
        ({"repetitions": "1"}, "invalid-repetitions"),
        ({"repetitions": 0}, "invalid-repetitions"),
        ({"repetitions": 4}, "invalid-repetitions"),
        ({"timeout_seconds": True}, "invalid-timeout"),
        ({"timeout_seconds": 1.0}, "invalid-timeout"),
        ({"timeout_seconds": "30"}, "invalid-timeout"),
        ({"timeout_seconds": 0}, "invalid-timeout"),
        ({"timeout_seconds": 121}, "invalid-timeout"),
    ],
)
def test_config_is_explicit_strict_and_bounded(values, error):
    with pytest.raises(planner.TrialPlanError, match=f"^{error}$"):
        config(**values)


def test_config_labels_are_only_syntax_checked_and_not_model_discovery(fixed):
    selected = config(
        model="Unverified.future-model_9", effort="future-effort", timeout_seconds=120
    )
    result = planner.build_trial_plan(fixed, selected)
    assert result["model_availability"] == "unverified"
    assert result["effort_support"] == "unverified"
    assert result["configuration"] == asdict(selected)
    assert config(model="a" * 80, effort="a" * 20, timeout_seconds=1).timeout_seconds == 1


def test_frozen_config_is_revalidated_at_plan_boundary(fixed):
    selected = config()
    with pytest.raises(FrozenInstanceError):
        selected.repetitions = 3
    object.__setattr__(selected, "repetitions", False)
    with pytest.raises(planner.TrialPlanError, match="invalid-repetitions"):
        planner.build_trial_plan(fixed, selected)
    with pytest.raises(planner.TrialPlanError, match="invalid-configuration"):
        planner.build_trial_plan(fixed, {})


def test_only_pinned_task_file_is_opened_no_accounts_references_scoring_process_or_network(
    fixed, monkeypatch
):
    original_open = Path.open
    opened = []

    def task_only(path, *args, **kwargs):
        assert path == fixed / planner.comparison.reference.REFERENCE / "tasks.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "offline planner cannot read accounts/references, score, execute or contact providers"
        )

    monkeypatch.setattr(Path, "open", task_only)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "score_reference", forbidden)
    monkeypatch.setattr(planner.comparison.FastAPIRouteParser, "parse_file", forbidden)
    monkeypatch.setattr(planner.comparison.FastAPIRouteParser, "parse_repository", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    plan = planner.build_trial_plan(fixed, config())
    assert opened == ["tasks.json"]
    assert len(plan["packets"]) == 14


@pytest.mark.parametrize(
    "field", ["task_id", "payload-task-id", "request_id", "payload-request-id"]
)
def test_changed_or_stale_task_request_binding_fails_before_plan_output(fixed, monkeypatch, field):
    mutated = mocked_packets(fixed, monkeypatch)
    task = mutated["tasks"][0]
    wrapper = task["packets"]["model-only"]
    if field == "task_id":
        task["task_id"] = "task-" + "0" * 64
    elif field == "payload-task-id":
        wrapper["payload"]["task_id"] = "task-" + "0" * 64
    elif field == "request_id":
        wrapper["request_id"] = "request-" + "0" * 64
    else:
        wrapper["payload"]["request_id"] = "request-" + "0" * 64
    with pytest.raises(planner.TrialPlanError, match="binding-mismatch"):
        planner.build_trial_plan(fixed, config())


def test_changed_instruction_with_stale_request_is_rejected(fixed, monkeypatch):
    mutated = mocked_packets(fixed, monkeypatch)
    mutated["tasks"][0]["packets"]["model-only"]["payload"]["instructions"] += " Changed."
    with pytest.raises(planner.TrialPlanError, match="request-binding-mismatch"):
        planner.build_trial_plan(fixed, config())


def test_rebound_but_inconsistent_common_prompt_is_rejected(fixed, monkeypatch):
    mutated = mocked_packets(fixed, monkeypatch)
    task = mutated["tasks"][0]
    for mode in planner.AI_MODES:
        task["packets"][mode]["payload"]["instructions"] += " Changed one pair only."
        rebind_request(task, mode)
    with pytest.raises(planner.TrialPlanError, match="inconsistent-common-contract"):
        planner.build_trial_plan(fixed, config())


@pytest.mark.parametrize(
    "mode,evidence",
    [
        ("model-only", [{}]),
        ("evidence-assisted", []),
        ("evidence-assisted", [{}, {}]),
        ("evidence-assisted", {}),
    ],
)
def test_invalid_mode_evidence_shape_is_not_a_valid_message(fixed, monkeypatch, mode, evidence):
    mutated = mocked_packets(fixed, monkeypatch)
    task = mutated["tasks"][0]
    task["packets"][mode]["payload"]["evidence"] = evidence
    rebind_request(task, mode)
    with pytest.raises(planner.TrialPlanError, match="invalid-mode-evidence"):
        planner.build_trial_plan(fixed, config())


@pytest.mark.parametrize("field", sorted(planner.REFERENCE_FIELDS))
def test_evaluator_fields_cannot_leak_even_nested_in_evidence(fixed, monkeypatch, field):
    mutated = mocked_packets(fixed, monkeypatch)
    task = mutated["tasks"][0]
    task["packets"]["evidence-assisted"]["payload"]["evidence"][0]["extra"] = {field: "private"}
    rebind_request(task, "evidence-assisted")
    with pytest.raises(planner.TrialPlanError, match="evaluator-metadata-in-message"):
        planner.build_trial_plan(fixed, config())


@pytest.mark.parametrize(
    "value,error", [("\ud800", "invalid-packet-utf8"), (float("nan"), "invalid-packet-json")]
)
def test_invalid_utf8_or_nonfinite_packet_fails_with_closed_diagnostic(
    fixed, monkeypatch, value, error
):
    mutated = mocked_packets(fixed, monkeypatch)
    task = mutated["tasks"][0]
    task["packets"]["model-only"]["payload"]["instructions"] = value
    with pytest.raises(planner.TrialPlanError, match=f"^{error}$"):
        planner.build_trial_plan(fixed, config())


def test_message_size_limit_is_enforced_before_an_oversized_candidate_is_returned(
    fixed, monkeypatch
):
    monkeypatch.setattr(planner, "MAX_MESSAGE_BYTES", 1)
    with pytest.raises(planner.TrialPlanError, match="message-too-large"):
        planner.build_trial_plan(fixed, config())


def test_unicode_application_messages_bind_utf8_bytes_not_character_counts(fixed, monkeypatch):
    mutated = mocked_packets(fixed, monkeypatch)
    for task in mutated["tasks"]:
        for mode in planner.AI_MODES:
            task["packets"][mode]["payload"]["instructions"] += " 한국어 메시지."
            rebind_request(task, mode)
    plan = planner.build_trial_plan(fixed, config())
    for packet in plan["packets"]:
        assert "한국어 메시지" in packet["message_text"]
        assert packet["message_bytes"] == len(packet["message_text"].encode("utf-8"))
        assert packet["message_bytes"] > len(packet["message_text"])
    # A character-count-only implementation would incorrectly accept every packet.
    monkeypatch.setattr(
        planner, "MAX_MESSAGE_BYTES", max(len(packet["message_text"]) for packet in plan["packets"])
    )
    with pytest.raises(planner.TrialPlanError, match="message-too-large"):
        planner.build_trial_plan(fixed, config())


@pytest.mark.parametrize(
    "failure", ["wrong-count", "duplicate-task-id", "missing-mode", "nonobject-payload"]
)
def test_malformed_comparison_plan_is_not_silently_reduced_or_partially_scheduled(
    fixed, monkeypatch, failure
):
    mutated = mocked_packets(fixed, monkeypatch)
    if failure == "wrong-count":
        mutated["tasks"].pop()
    elif failure == "duplicate-task-id":
        mutated["tasks"][1]["task_id"] = mutated["tasks"][0]["task_id"]
    elif failure == "missing-mode":
        del mutated["tasks"][0]["packets"]["model-only"]
    else:
        mutated["tasks"][0]["packets"]["model-only"]["payload"] = []
    with pytest.raises(planner.TrialPlanError):
        planner.build_trial_plan(fixed, config())


CLI_ARGS = [
    "--model",
    "proposed-model",
    "--effort",
    "proposed-effort",
    "--repetitions",
    "2",
    "--timeout-seconds",
    "30",
]


@pytest.mark.parametrize("index", [0, 2, 4, 6])
def test_all_four_cli_configuration_arguments_are_required(index, capsys):
    args = CLI_ARGS[:index] + CLI_ARGS[index + 2 :]
    with pytest.raises(SystemExit) as error:
        planner.main(args)
    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


def test_json_cli_is_one_complete_offline_plan_not_messages_or_prose(fixed, monkeypatch, capsys):
    monkeypatch.setattr(planner, "ROOT", fixed)
    assert planner.main([*CLI_ARGS, "--json"]) == 0
    captured = capsys.readouterr()
    plan = json.loads(captured.out)
    assert captured.err == ""
    assert plan == planner.build_trial_plan(fixed, config())
    assert len(captured.out.splitlines()) == 1


def test_default_human_summary_hides_full_messages_but_states_limits(fixed, monkeypatch, capsys):
    monkeypatch.setattr(planner, "ROOT", fixed)
    assert planner.main(CLI_ARGS) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "OFFLINE CANDIDATE ONLY" in captured.out
    assert "UNVERIFIED" in captured.out
    assert "NOT a wall-clock/usage cap" in captured.out
    assert "NEVER provider input" in captured.out
    assert "APPLICATION MESSAGE CANDIDATE:" not in captured.out
    assert '"kind":"evaluation-comparison-input"' not in captured.out


def test_show_messages_prints_every_exact_application_candidate_not_just_a_sample(
    fixed, monkeypatch, capsys
):
    monkeypatch.setattr(planner, "ROOT", fixed)
    expected = planner.build_trial_plan(fixed, config())
    assert planner.main([*CLI_ARGS, "--show-messages"]) == 0
    output = capsys.readouterr().out
    assert output.count("APPLICATION MESSAGE CANDIDATE:") == 14
    for packet in expected["packets"]:
        assert packet["message_text"] in output
        assert packet["message_sha256"] in output
        assert str(packet["message_bytes"]) in output


def test_json_and_human_full_message_modes_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as error:
        planner.main([*CLI_ARGS, "--json", "--show-messages"])
    assert error.value.code == 2
    assert "not allowed" in capsys.readouterr().err


@pytest.mark.parametrize("json_output", [True, False])
def test_cli_bad_config_is_exit_one_not_partial_plan_or_live_attempt(json_output, capsys):
    args = [*CLI_ARGS]
    args[5] = "0"
    assert planner.main([*args, *(["--json"] if json_output else [])]) == 1
    captured = capsys.readouterr()
    if json_output:
        result = json.loads(captured.out)
        assert result == {
            "kind": "offline-evaluation-trial-plan-error",
            "error": "invalid-repetitions",
            "execution_authorized": False,
            "provider_calls_by_this_tool": 0,
        }
    else:
        assert captured.out.strip() == "invalid-repetitions"
    assert captured.err == ""


def test_cli_missing_fixed_task_is_an_error_without_reference_or_account_lookup(
    fixed, monkeypatch, capsys
):
    monkeypatch.setattr(planner, "ROOT", fixed)
    (fixed / planner.comparison.reference.REFERENCE / "tasks.json").unlink()
    assert planner.main([*CLI_ARGS, "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["kind"] == "offline-evaluation-trial-plan-error"
    assert result["provider_calls_by_this_tool"] == 0
    assert "plan_id" not in result
