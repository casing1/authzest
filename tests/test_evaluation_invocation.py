"""Invocation envelopes bind offline content, not provider origin or live execution."""

from __future__ import annotations

import builtins
import copy
import hashlib
import json
import shutil
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import jsonschema
import pytest
from scripts import evaluation_collection as collector
from scripts import evaluation_invocation as codec
from scripts import evaluation_trial_plan as planner


def config(**values: object) -> planner.TrialConfig:
    return planner.TrialConfig(
        **{
            "model": "proposed-model",
            "effort": "proposed-effort",
            "repetitions": 1,
            "timeout_seconds": 30,
            **values,
        }
    )


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture
def fixed(tmp_path: Path) -> Path:
    relative = Path("tests/fixtures/evaluation_reference/v1")
    directory = tmp_path / relative
    directory.mkdir(parents=True)
    shutil.copyfile(codec.ROOT / relative / "tasks.json", directory / "tasks.json")
    return tmp_path


@pytest.fixture
def candidate(fixed: Path):
    return codec.prepare_candidate(fixed, config())


def inner(invocation) -> dict:
    spec = invocation.slot.spec
    return {
        "schema_version": "0.1",
        "kind": "evaluation-comparison-response",
        "task_id": spec.task_id,
        "request_id": spec.request_id,
        "answers": [{"question_id": question.id, "answer": None} for question in spec.questions],
    }


def outer(invocation) -> dict:
    return {
        "schema_version": "0.2",
        "kind": "evaluation-invocation-response",
        "invocation_id": invocation.invocation_id,
        "response": inner(invocation),
    }


def decode(invocation, value: object):
    return codec.decode_response(invocation, json.dumps(value, ensure_ascii=False))


def assert_invalid(result):
    assert result["status"] == "invalid"
    assert type(result["error"]) is str and result["error"]
    assert result["records"] == []


def assert_host_only(result):
    assert result["provider_freshness_verified"] is False
    assert result["runtime_observed"] is False
    assert result["transport_provenance"] == "caller-supplied-unverified"
    for field in ("sharing_authorized", "execution_authorized", "model_quality_measured"):
        assert result[field] is False
    assert result["scoring_status"] == "not-run"


@pytest.mark.parametrize("repetitions", [1, 2, 3])
def test_prepared_candidate_keeps_every_expected_invocation_slot(fixed, repetitions):
    candidate = codec.prepare_candidate(fixed, config(repetitions=repetitions))
    assert type(candidate.invocations) is tuple
    assert len(candidate.invocations) == 14 * repetitions
    assert (
        len({invocation.invocation_id for invocation in candidate.invocations}) == 14 * repetitions
    )
    assert tuple(invocation.slot for invocation in candidate.invocations) == candidate.session.slots
    assert all(invocation.session == candidate.session for invocation in candidate.invocations)
    assert len({invocation.slot.spec.request_id for invocation in candidate.invocations}) == 14


def test_original_packets_final_messages_and_schema_hashes_are_bound_independently(
    fixed, candidate
):
    plan = planner.build_trial_plan(fixed, config())
    messages = {
        (packet["task_id"], packet["mode"]): packet["message_text"] for packet in plan["packets"]
    }
    for invocation in candidate.invocations:
        original = messages[invocation.slot.spec.task_id, invocation.slot.mode]
        assert invocation.original_message == original
        assert invocation.original_message_sha256 == digest(original)
        assert invocation.original_message_sha256 == invocation.slot.message_sha256
        assert invocation.message_sha256 == digest(invocation.message_text)
        assert invocation.message_sha256 != invocation.original_message_sha256
        assert invocation.output_schema_sha256 == digest(canonical(invocation.output_schema))
        expected = {
            "recipe_id": codec.RECIPE_ID,
            "collection_id": candidate.session.collection_id,
            "trial_id": invocation.slot.trial_id,
            "configuration_id": candidate.session.configuration_id,
        }
        assert invocation.invocation_id == "eval-invocation-v2-" + digest(canonical(expected))
        assert invocation.to_dict()["host_binding"] == candidate.session.binding(invocation.slot)
        assert invocation.invocation_id in invocation.message_text
        message = json.loads(invocation.message_text)
        assert set(message) == {"schema_version", "kind", "invocation_id", "instructions", "task"}
        assert message["schema_version"] == "0.2"
        assert message["kind"] == "evaluation-invocation-input"
        assert message["task"] == json.loads(original)


def test_candidate_identity_binds_recipe_namespace_configuration_and_every_invocation(candidate):
    expected = {
        "recipe_id": codec.RECIPE_ID,
        "collection_id": candidate.session.collection_id,
        "original_plan_id": candidate.session.plan_id,
        "configuration": {
            "model": "proposed-model",
            "effort": "proposed-effort",
            "repetitions": 1,
            "timeout_seconds": 30,
        },
        "invocations": [item.to_dict() for item in candidate.invocations],
    }
    assert candidate.candidate_id == "invocation-candidate-v2-" + digest(canonical(expected))


def test_fresh_candidates_share_original_request_content_not_invocation_envelope_identity(fixed):
    first = codec.prepare_candidate(fixed, config())
    second = codec.prepare_candidate(fixed, config())
    assert first.session.plan_id == second.session.plan_id
    assert first.session.collection_id != second.session.collection_id
    assert first.candidate_id != second.candidate_id
    for left, right in zip(first.invocations, second.invocations, strict=True):
        assert left.original_message == right.original_message
        assert left.slot.spec.request_id == right.slot.spec.request_id
        assert left.invocation_id != right.invocation_id
        assert left.message_sha256 != right.message_sha256
        assert left.output_schema_sha256 != right.output_schema_sha256


def test_reconstruction_of_owned_session_needs_no_new_nonce_and_preserves_candidate(
    fixed, candidate, monkeypatch
):
    def no_new_entropy(*args, **kwargs):
        pytest.fail("reconstruction of an existing collection must not mint a new namespace")

    monkeypatch.setattr(collector.secrets, "token_hex", no_new_entropy)
    rebuilt = codec.candidate_from_collection(fixed, candidate.session)
    assert rebuilt == candidate
    assert rebuilt.candidate_id == candidate.candidate_id
    assert rebuilt.to_dict() == candidate.to_dict()


def test_candidate_invocations_are_frozen_and_exports_and_schemas_are_copies(candidate):
    invocation = candidate.invocations[0]
    with pytest.raises(FrozenInstanceError):
        invocation.original_message = "changed"
    with pytest.raises(FrozenInstanceError):
        candidate.invocations = ()
    before = copy.deepcopy(invocation.output_schema)
    exported = invocation.output_schema
    exported["injected"] = True
    exported["properties"]["invocation_id"]["enum"][0] = "changed"
    assert invocation.output_schema == before
    item_export = invocation.to_dict()
    item_export["injected"] = True
    assert "injected" not in invocation.to_dict()
    batch_export = candidate.to_dict()
    batch_export["injected"] = True
    batch_export["invocations"][0]["output_schema"]["properties"]["invocation_id"]["enum"][0] = (
        "changed"
    )
    assert "injected" not in candidate.to_dict()
    assert candidate.to_dict()["invocations"][0]["output_schema"] == before


def test_recipe_is_immutable_and_export_mutation_does_not_change_recipe_identity(candidate):
    original = dict(codec.RECIPE)
    with pytest.raises(TypeError):
        codec.RECIPE["instructions"] = "changed"
    exported = candidate.to_dict()["recipe"]
    exported["instructions"] = "changed"
    assert dict(codec.RECIPE) == original
    assert candidate.to_dict()["recipe"] == original
    expected_id = "invocation-recipe-v2-" + digest(canonical(original))
    assert expected_id == codec.RECIPE_ID


def test_output_schema_is_valid_json_schema_and_exact_outer_response_matches(candidate):
    for invocation in candidate.invocations:
        jsonschema.Draft202012Validator.check_schema(invocation.output_schema)
        validator = jsonschema.Draft202012Validator(invocation.output_schema)
        validator.validate(outer(invocation))
        changed = outer(invocation)
        changed["invocation_id"] = "invocation-" + "0" * 64
        assert list(validator.iter_errors(changed))
        changed = outer(invocation)
        changed["extra"] = True
        assert list(validator.iter_errors(changed))


@pytest.mark.parametrize("bad_csv", ["z,a", "a,a", " a", "a\nb"])
def test_shaping_schema_is_not_the_authoritative_canonical_csv_validator(candidate, bad_csv):
    invocation = next(
        item
        for item in candidate.invocations
        if any(question.answer_format == "sorted-csv" for question in item.slot.spec.questions)
    )
    value = outer(invocation)
    selected = next(
        question
        for question in invocation.slot.spec.questions
        if question.answer_format == "sorted-csv"
    )
    next(record for record in value["response"]["answers"] if record["question_id"] == selected.id)[
        "answer"
    ] = bad_csv
    jsonschema.Draft202012Validator(invocation.output_schema).validate(value)
    result = decode(invocation, value)
    assert_invalid(result)
    assert result["error"] == "inner-invalid-answer"
    assert_host_only(result)


def test_shaping_schema_does_not_establish_unique_question_coverage(candidate):
    invocation = candidate.invocations[0]
    value = outer(invocation)
    value["response"]["answers"][1] = value["response"]["answers"][0].copy()
    jsonschema.Draft202012Validator(invocation.output_schema).validate(value)
    assert_invalid(decode(invocation, value))


def test_valid_outer_envelope_preserves_raw_text_and_separate_canonical_inner(candidate):
    invocation = candidate.invocations[0]
    value = outer(invocation)
    raw = "  " + json.dumps(value, indent=2) + "\n"
    result = codec.decode_response(invocation, raw)
    assert result["status"] == "valid"
    assert result["error"] is None
    assert result["raw_received_text"] == raw
    assert result["inner_canonical_json"] == canonical(value["response"])
    assert result["inner_canonical_json"] != raw
    assert all(record["answer"] is None for record in result["records"])
    assert_host_only(result)


def test_null_unknown_and_known_empty_csv_are_not_coerced_or_scored(candidate):
    invocation = next(
        item
        for item in candidate.invocations
        if any(question.answer_format == "sorted-csv" for question in item.slot.spec.questions)
    )
    value = outer(invocation)
    selected = next(
        question
        for question in invocation.slot.spec.questions
        if question.answer_format == "sorted-csv"
    )
    next(record for record in value["response"]["answers"] if record["question_id"] == selected.id)[
        "answer"
    ] = ""
    result = decode(invocation, value)
    assert result["status"] == "valid"
    assert sum(record["answer"] == "" for record in result["records"]) == 1
    assert sum(record["answer"] is None for record in result["records"]) == 2
    assert json.loads(result["inner_canonical_json"]) == value["response"]
    assert_host_only(result)


def test_only_absent_outer_raw_is_missing_not_null_inner_or_missing_fields(candidate):
    invocation = candidate.invocations[0]
    result = codec.decode_response(invocation, None)
    assert result["status"] == "missing"
    assert result["records"] is None
    assert result["raw_received_text"] is None
    assert result["inner_canonical_json"] is None
    assert_host_only(result)
    value = outer(invocation)
    value["response"] = None
    assert_invalid(decode(invocation, value))
    del value["response"]
    assert_invalid(decode(invocation, value))


@pytest.mark.parametrize("field", ["schema_version", "kind", "invocation_id", "response"])
def test_every_outer_field_is_required_and_whole_envelope_is_rejected(candidate, field):
    invocation = candidate.invocations[0]
    value = outer(invocation)
    del value[field]
    assert_invalid(decode(invocation, value))


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "0.1"),
        ("schema_version", 0.2),
        ("kind", "evaluation-comparison-response"),
        ("kind", None),
        ("invocation_id", True),
        ("invocation_id", []),
        ("invocation_id", "invocation-" + "0" * 64),
        ("response", "{}"),
        ("response", []),
        ("response", False),
    ],
)
def test_outer_types_version_kind_and_exact_invocation_id_are_strict(candidate, field, value):
    invocation = candidate.invocations[0]
    envelope = outer(invocation)
    envelope[field] = value
    assert_invalid(decode(invocation, envelope))


@pytest.mark.parametrize(
    "field", ["extra", "model", "configuration_id", "provider_freshness_verified"]
)
def test_extra_outer_fields_cannot_add_execution_claims(candidate, field):
    invocation = candidate.invocations[0]
    value = outer(invocation)
    value[field] = True
    assert_invalid(decode(invocation, value))


def test_inner_contract_still_rejects_partial_answers_aliases_and_noncanonical_values(candidate):
    invocation = candidate.invocations[0]
    original = outer(invocation)
    for mutation in ("partial", "duplicate", "extra", "wrong-task", "wrong-request", "bad-answer"):
        value = copy.deepcopy(original)
        response = value["response"]
        if mutation == "partial":
            response["answers"].pop()
        elif mutation == "duplicate":
            response["answers"][1] = response["answers"][0].copy()
        elif mutation == "extra":
            response["explanation"] = "not part of 0.1"
        elif mutation == "wrong-task":
            response["task_id"] = "task-" + "0" * 64
        elif mutation == "wrong-request":
            response["request_id"] = "request-" + "0" * 64
        else:
            response["answers"][0]["answer"] = True
        result = decode(invocation, value)
        assert_invalid(result)
        assert result["inner_canonical_json"] == canonical(value["response"])


def test_old_whole_envelope_is_invalid_but_old_inner_rewrapped_can_validate(fixed, candidate):
    current = codec.prepare_candidate(fixed, config())
    old_invocation, new_invocation = candidate.invocations[0], current.invocations[0]
    old_value = outer(old_invocation)
    assert_invalid(decode(new_invocation, old_value))
    rewrapped = outer(new_invocation)
    rewrapped["response"] = old_value["response"]
    result = decode(new_invocation, rewrapped)
    assert result["status"] == "valid"
    assert_host_only(result)
    assert old_invocation.slot.spec.request_id == new_invocation.slot.spec.request_id
    assert old_invocation.invocation_id != new_invocation.invocation_id


def test_revalidating_identical_envelope_is_allowed_and_not_a_replay_ledger(candidate):
    invocation = candidate.invocations[0]
    raw = json.dumps(outer(invocation))
    first = codec.decode_response(invocation, raw)
    second = codec.decode_response(invocation, raw)
    assert first == second
    assert first["status"] == "valid"
    assert_host_only(second)


@pytest.mark.parametrize("raw", [b"{}", {}, [], True, 1, 1.5])
def test_nonstring_raw_is_invalid_and_not_retained(candidate, raw):
    result = codec.decode_response(candidate.invocations[0], raw)
    assert_invalid(result)
    assert result["raw_received_text"] is None
    assert result["inner_canonical_json"] is None


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{} {}",
        "[]",
        "null",
        '{"a":1,"a":2}',
        '{"a":NaN}',
        '{"a":Infinity}',
        '{"a":1e309}',
        "```json\n{}\n```",
    ],
)
def test_invalid_json_shape_duplicates_nonfinite_and_fences_fail_without_repair(candidate, raw):
    result = codec.decode_response(candidate.invocations[0], raw)
    assert_invalid(result)
    assert result["raw_received_text"] == raw
    assert result["inner_canonical_json"] is None


def test_nested_duplicate_inner_json_key_is_not_hidden_by_outer_object(candidate):
    invocation = candidate.invocations[0]
    raw = json.dumps(outer(invocation)).replace(
        '"answer": null', '"answer": null, "answer": null', 1
    )
    assert_invalid(codec.decode_response(invocation, raw))


def test_unpaired_utf8_surrogates_and_oversized_raw_are_not_retained(candidate):
    invocation = candidate.invocations[0]
    assert codec.MAX_RAW_BYTES == 64 * 1024
    for raw in ('"\ud800"', "x" * (codec.MAX_RAW_BYTES + 1), "é" * (codec.MAX_RAW_BYTES // 2 + 1)):
        result = codec.decode_response(invocation, raw)
        assert_invalid(result)
        assert result["raw_received_text"] is None


def test_escaped_unpaired_inner_surrogate_keeps_outer_raw_not_invalid_canonical_text(candidate):
    invocation = candidate.invocations[0]
    value = outer(invocation)
    value["response"]["answers"][0]["answer"] = "\ud800"
    raw = json.dumps(value, ensure_ascii=True)
    result = codec.decode_response(invocation, raw)
    assert_invalid(result)
    assert result["error"] == "inner-invalid-utf8"
    assert result["raw_received_text"] == raw
    assert result["inner_canonical_json"] is None


def test_exact_raw_utf8_byte_limit_is_accepted_but_one_more_byte_is_not(candidate):
    invocation = candidate.invocations[0]
    raw = json.dumps(outer(invocation))
    padded = raw + " " * (codec.MAX_RAW_BYTES - len(raw.encode("utf-8")))
    assert codec.decode_response(invocation, padded)["status"] == "valid"
    result = codec.decode_response(invocation, padded + " ")
    assert_invalid(result)
    assert result["raw_received_text"] is None


def test_small_numeric_exponent_input_cannot_retain_oversized_canonical_inner(candidate):
    invocation = candidate.invocations[0]
    raw = (
        '{"schema_version":"0.2","kind":"evaluation-invocation-response",'
        '"invocation_id":'
        + json.dumps(invocation.invocation_id)
        + ',"response":{"expanded":['
        + ",".join(["1e15"] * 4000)
        + "]}}"
    )
    assert len(raw.encode("utf-8")) < codec.MAX_RAW_BYTES
    assert len(canonical(json.loads(raw)["response"]).encode("utf-8")) > codec.MAX_RAW_BYTES
    result = codec.decode_response(invocation, raw)
    assert_invalid(result)
    assert result["error"] == "inner-response-too-large"
    assert result["raw_received_text"] == raw
    assert result["inner_canonical_json"] is None


def test_deeply_nested_response_is_invalid_and_bounded_raw_is_still_preserved(candidate):
    raw = "[" * 17 + "]" * 17
    result = codec.decode_response(candidate.invocations[0], raw)
    assert_invalid(result)
    assert result["raw_received_text"] == raw


def test_independent_session_plan_packet_identity_replacements_are_rejected(fixed, candidate):
    for field, prefix in (("plan_id", "trial-plan-"), ("packet_set_id", "packet-set-")):
        changed = replace(candidate.session, **{field: prefix + "0" * 64})
        with pytest.raises(ValueError):
            codec.candidate_from_collection(fixed, changed)


def test_invocation_rejects_changed_packet_content_or_other_task_slot(candidate):
    invocation = candidate.invocations[0]
    value = json.loads(invocation.original_message)
    value["instructions"] += " changed packet"
    with pytest.raises(ValueError):
        replace(invocation, original_message=canonical(value))
    with pytest.raises(ValueError):
        replace(invocation, slot=candidate.invocations[-1].slot)


def test_reconstruction_rejects_changed_question_spec_even_if_host_schedule_ids_still_match(
    fixed, candidate
):
    original = candidate.session.slots[0]
    questions = list(original.spec.questions)
    questions[0] = replace(questions[0], id="changed-question")
    modified = replace(original, spec=replace(original.spec, questions=tuple(questions)))
    session = replace(candidate.session, slots=(modified, *candidate.session.slots[1:]))
    with pytest.raises(codec.InvocationError, match="task-spec-mismatch"):
        codec.candidate_from_collection(fixed, session)


@pytest.mark.parametrize("constant", ["MAX_MESSAGE_BYTES", "MAX_SCHEMA_BYTES"])
def test_final_message_and_schema_sizes_are_checked_when_invocation_is_built(
    candidate, monkeypatch, constant
):
    invocation = candidate.invocations[0]
    monkeypatch.setattr(codec, constant, 1)
    with pytest.raises(codec.InvocationError, match="invocation-.*-too-large"):
        codec.Invocation(invocation.session, invocation.slot, invocation.original_message)


def test_invalid_owned_invocation_is_not_misclassified_as_bad_provider_text():
    with pytest.raises(codec.InvocationError, match="invalid-invocation"):
        codec.decode_response({}, "{}")


def test_slot_is_revalidated_even_when_bool_integer_equality_would_match_expected_slot(candidate):
    invocation = candidate.invocations[0]
    malformed = copy.copy(invocation.slot)
    object.__setattr__(malformed, "ordinal", True)
    assert malformed == invocation.slot  # Python dataclass equality alone cannot reject True == 1.
    assert type(invocation.slot.ordinal) is int
    with pytest.raises(codec.InvocationError, match="invalid-slot"):
        codec.Invocation(invocation.session, malformed, invocation.original_message)


def test_candidate_rejects_mixed_sessions_or_missing_expected_invocations(fixed, candidate):
    other = codec.prepare_candidate(fixed, config())
    with pytest.raises(ValueError):
        replace(candidate, session=other.session)
    with pytest.raises(ValueError):
        replace(candidate, invocations=candidate.invocations[:-1])


@pytest.mark.parametrize("repetitions", [1, 2, 3])
@pytest.mark.parametrize("fault", [None, "missing", "invalid", "stale"])
def test_synthetic_dry_run_preserves_all_mode_repeat_denominators(fixed, repetitions, fault):
    candidate = codec.prepare_candidate(fixed, config(repetitions=repetitions))
    result = codec.dry_run(candidate, fault=fault)
    assert result["planned_slots"] == 14 * repetitions
    assert result["question_opportunities"] == 42 * repetitions
    assert len(result["groups"]) == 2 * repetitions
    for group in result["groups"]:
        assert group["planned_cases"] == 7
        assert group["question_opportunities"] == 21
        assert sum(group["cases_by_status"].values()) == 7
        assert sum(group["questions_by_status"].values()) == 21
        observed = [
            item
            for item in result["observations"]
            if (item["repetition"], item["mode"]) == (group["repetition"], group["mode"])
        ]
        assert sum(item["question_count"] for item in observed) == 21
    assert result["provider_freshness_verified"] is False
    assert result["provider_calls_by_this_tool"] == result["live_trials"] == 0
    assert result["model_quality_measured"] is False
    assert result["scoring_status"] == "not-run"
    assert result["target_execution"] == "not-run"
    expected = "valid" if fault is None else "missing" if fault == "missing" else "invalid"
    assert result["observations"][0]["status"] == expected
    assert all(item["status"] == "valid" for item in result["observations"][1:])


def test_preparation_reads_tasks_only_and_decoding_is_pure_without_account_or_target_io(
    fixed, monkeypatch
):
    original_open = Path.open
    opened = []

    def task_only(path, *args, **kwargs):
        assert path == fixed / "tests/fixtures/evaluation_reference/v1/tasks.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "offline codec cannot access accounts, references, providers or target execution"
        )

    monkeypatch.setattr(Path, "open", task_only)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "score_reference", forbidden)
    monkeypatch.setattr(planner.comparison.FastAPIRouteParser, "parse_file", forbidden)
    monkeypatch.setattr(planner.comparison.FastAPIRouteParser, "parse_repository", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    candidate = codec.prepare_candidate(fixed, config())
    assert opened and set(opened) == {"tasks.json"}
    monkeypatch.setattr(Path, "open", forbidden)
    invocation = candidate.invocations[0]
    assert decode(invocation, outer(invocation))["status"] == "valid"
    assert codec.dry_run(candidate)["planned_slots"] == 14


CLI_ARGS = [
    "--model",
    "proposed-model",
    "--effort",
    "proposed-effort",
    "--repetitions",
    "1",
    "--timeout-seconds",
    "30",
]


@pytest.mark.parametrize("index", [0, 2, 4, 6])
def test_four_cli_configuration_arguments_are_required(index, capsys):
    with pytest.raises(SystemExit) as error:
        codec.main(CLI_ARGS[:index] + CLI_ARGS[index + 2 :])
    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


def test_cli_json_is_a_single_offline_preview_without_live_execution(fixed, monkeypatch, capsys):
    monkeypatch.setattr(codec, "ROOT", fixed)
    assert codec.main([*CLI_ARGS, "--json"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert captured.err == ""
    assert len(captured.out.splitlines()) == 1
    assert "candidate_id" in result


def test_cli_full_messages_and_default_summary_are_distinct(fixed, monkeypatch, capsys):
    monkeypatch.setattr(codec, "ROOT", fixed)
    assert codec.main(CLI_ARGS) == 0
    summary = capsys.readouterr().out
    assert "APPLICATION MESSAGE CANDIDATE:" not in summary
    assert '"kind":"evaluation-invocation-input"' not in summary
    assert "UNVERIFIED" in summary
    assert "NOT enforced by this codec" in summary
    assert codec.main([*CLI_ARGS, "--show-messages"]) == 0
    messages = capsys.readouterr().out
    assert messages.count("APPLICATION MESSAGE CANDIDATE:") == 14
    assert messages.count("OUTPUT SHAPING SCHEMA CANDIDATE:") == 14
    assert len(messages) > len(summary)


@pytest.mark.parametrize("fault", [None, "missing", "invalid", "stale"])
def test_cli_synthetic_dry_run_has_no_live_or_quality_claims(fixed, monkeypatch, capsys, fault):
    monkeypatch.setattr(codec, "ROOT", fixed)
    args = [*CLI_ARGS, "--dry-run", "--json", *(["--fault", fault] if fault else [])]
    assert codec.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["planned_slots"] == 14
    assert result["question_opportunities"] == 42
    assert result["provider_freshness_verified"] is False


def test_cli_requires_dry_run_for_faults_and_excludes_conflicting_outputs(capsys):
    for extra in (
        ["--fault", "missing"],
        ["--json", "--show-messages"],
        ["--live"],
        ["--file", "private.json"],
    ):
        with pytest.raises(SystemExit) as error:
            codec.main([*CLI_ARGS, *extra])
        assert error.value.code == 2
        assert capsys.readouterr().err


def test_cli_bad_config_is_error_without_partial_candidate(capsys):
    args = CLI_ARGS.copy()
    args[args.index("--repetitions") + 1] = "0"
    assert codec.main([*args, "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert "error" in result
    assert "candidate_id" not in result
    assert result["kind"] == "offline-invocation-error"
    assert result["execution_authorized"] is False
    assert result["provider_calls_by_this_tool"] == 0
