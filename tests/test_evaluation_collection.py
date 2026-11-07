"""Host receipt routing is not evidence of provider execution or fresh responses."""

from __future__ import annotations

import builtins
import copy
import json
import shutil
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from scripts import evaluation_collection as collector

EXPECTED_FIELDS = (
    "schema_version",
    "kind",
    "collection_id",
    "plan_id",
    "packet_set_id",
    "trial_id",
    "ordinal",
    "repetition",
    "task_id",
    "mode",
    "request_id",
    "message_sha256",
    "configuration_id",
    "invocation_id",
)


def config(**values: object) -> collector.planner.TrialConfig:
    return collector.planner.TrialConfig(
        **{
            "model": "proposed-model",
            "effort": "proposed-effort",
            "repetitions": 1,
            "timeout_seconds": 30,
            **values,
        }
    )


@pytest.fixture
def fixed(tmp_path: Path) -> Path:
    directory = tmp_path / collector.planner.comparison.reference.REFERENCE
    directory.mkdir(parents=True)
    shutil.copyfile(
        collector.ROOT / collector.planner.comparison.reference.REFERENCE / "tasks.json",
        directory / "tasks.json",
    )
    return tmp_path


@pytest.fixture
def session(fixed: Path) -> collector.CollectionSession:
    return collector.new_collection(fixed, config())


def inner(slot: collector.Slot, *, known_empty: bool = False) -> str:
    answers = [{"question_id": question.id, "answer": None} for question in slot.spec.questions]
    if known_empty:
        selected = next(
            question for question in slot.spec.questions if question.answer_format == "sorted-csv"
        )
        next(item for item in answers if item["question_id"] == selected.id)["answer"] = ""
    return json.dumps(
        {
            "schema_version": "0.1",
            "kind": "evaluation-comparison-response",
            "task_id": slot.spec.task_id,
            "request_id": slot.spec.request_id,
            "answers": answers,
        },
        ensure_ascii=False,
    )


def receipt(session, slot, *, status="completed", response_raw=...):
    return {
        "schema_version": "0.1",
        "kind": "evaluation-host-receipt",
        **session.binding(slot),
        "status": status,
        "response_raw": (inner(slot) if status == "completed" else None)
        if response_raw is ...
        else response_raw,
    }


def serialized(session, slot, **values):
    return json.dumps(receipt(session, slot, **values), ensure_ascii=False)


def all_submissions(session):
    return [
        (session.binding(slot)["invocation_id"], serialized(session, slot))
        for slot in session.slots
    ]


def assert_result(result, outcome, error):
    assert result["outcome"] == outcome
    assert result["error"] == error
    if outcome == "missing":
        assert result["records"] is None
    elif outcome != "valid":
        assert result["records"] == []


def test_new_namespaces_use_only_32_byte_nonce_entropy_while_plan_and_requests_stay_same(
    fixed, monkeypatch
):
    requests = []
    values = iter(("a" * 64, "b" * 64))

    def token_hex(length):
        requests.append(length)
        return next(values)

    monkeypatch.setattr(collector.secrets, "token_hex", token_hex)
    first = collector.new_collection(fixed, config())
    second = collector.new_collection(fixed, config())
    assert requests == [32, 32]
    assert first.plan_id == second.plan_id
    assert first.configuration_id == second.configuration_id
    assert first.packet_set_id == second.packet_set_id
    assert first.slots == second.slots
    assert first.collection_id != second.collection_id
    for left, right in zip(first.slots, second.slots, strict=True):
        assert first.binding(left)["request_id"] == second.binding(right)["request_id"]
        assert first.binding(left)["invocation_id"] != second.binding(right)["invocation_id"]


@pytest.mark.parametrize("repetitions", [1, 2, 3])
def test_all_expected_slots_and_group_denominators_survive_empty_collection(fixed, repetitions):
    session = collector.new_collection(fixed, config(repetitions=repetitions))
    result = collector.collect_receipts(session, [])
    assert result["planned_slots"] == len(session.slots) == 14 * repetitions
    assert result["question_opportunities"] == 42 * repetitions
    assert result["submission_count"] == 0
    assert len(result["observations"]) == 14 * repetitions
    assert len(result["groups"]) == 2 * repetitions
    assert result["unmatched"] == []
    for group in result["groups"]:
        assert group["planned_cases"] == 7
        assert group["question_opportunities"] == 21
        assert group["cases_by_outcome"]["missing"] == 7
        assert group["questions_by_outcome"]["missing"] == 21
        assert sum(group["cases_by_outcome"].values()) == 7
        assert sum(group["questions_by_outcome"].values()) == 21


def test_sessions_slots_specs_are_frozen_factory_metadata_not_saved_session_import(session):
    with pytest.raises(FrozenInstanceError):
        session.namespace_nonce = "c" * 64
    with pytest.raises(FrozenInstanceError):
        session.slots[0].ordinal = 2
    with pytest.raises(FrozenInstanceError):
        session.slots[0].spec.request_id = "request-" + "c" * 64
    with pytest.raises(collector.CollectionError, match="invalid-session"):
        collector.collect_receipts({}, [])
    with pytest.raises(collector.CollectionError, match="invalid-slot-count"):
        replace(session, slots=session.slots[:-1])


@pytest.mark.parametrize(
    "values",
    [{"model": "other-model"}, {"effort": "other-effort"}, {"timeout_seconds": 31}],
)
def test_replaced_configuration_cannot_reuse_the_original_configuration_identity(session, values):
    changed = replace(session.configuration, **values)
    with pytest.raises(collector.CollectionError, match="configuration-binding-mismatch"):
        replace(session, configuration=changed)


@pytest.mark.parametrize("field", EXPECTED_FIELDS)
@pytest.mark.parametrize("mutation", ["value", "type"])
def test_every_receipt_binding_field_requires_exact_value_and_type(session, field, mutation):
    slot = session.slots[0]
    value = receipt(session, slot)
    wanted = value[field]
    value[field] = (
        (wanted + 1 if type(wanted) is int else wanted + "changed")
        if mutation == "value"
        else (True if type(wanted) is int else None)
    )
    result = collector.decode_receipt(session, slot, json.dumps(value))
    assert_result(result, "invalid", "receipt-binding-mismatch")


def test_binding_dict_export_mutation_does_not_mutate_expected_session(session):
    slot = session.slots[0]
    original = session.binding(slot)
    changed = session.binding(slot)
    changed["invocation_id"] = "changed"
    assert session.binding(slot) == original


def test_invalid_session_slot_and_foreign_expected_metadata_are_not_accepted(session):
    with pytest.raises(collector.CollectionError, match="invalid-session"):
        collector.decode_receipt({}, session.slots[0], None)
    with pytest.raises(collector.CollectionError, match="invalid-slot"):
        collector.decode_receipt(session, {}, None)
    foreign = replace(session.slots[0], ordinal=42)
    with pytest.raises(collector.CollectionError, match="foreign-slot"):
        collector.decode_receipt(session, foreign, None)


@pytest.mark.parametrize("field", ["schema_version", "status", "response_raw", "invocation_id"])
def test_missing_receipt_fields_are_invalid_not_missing_or_partial_success(session, field):
    slot = session.slots[0]
    value = receipt(session, slot)
    del value[field]
    assert_result(
        collector.decode_receipt(session, slot, json.dumps(value)),
        "invalid",
        "invalid-receipt-fields",
    )


def test_extra_receipt_fields_are_not_accepted_as_execution_attestation(session):
    slot = session.slots[0]
    value = receipt(session, slot)
    value["provider_freshness_verified"] = True
    assert_result(
        collector.decode_receipt(session, slot, json.dumps(value)),
        "invalid",
        "invalid-receipt-fields",
    )


def test_missing_whole_receipt_and_completed_missing_inner_response_are_distinct(session):
    slot = session.slots[0]
    assert_result(collector.decode_receipt(session, slot, None), "missing", "missing-receipt")
    assert_result(
        collector.decode_receipt(session, slot, serialized(session, slot, response_raw=None)),
        "missing",
        "missing-response",
    )
    assert_result(
        collector.decode_receipt(session, slot, serialized(session, slot, response_raw="{}")),
        "invalid",
        "invalid-response-fields",
    )


def test_valid_null_answers_and_known_empty_csv_stay_distinct_not_correctness_claims(session):
    slot = next(
        slot
        for slot in session.slots
        if any(question.answer_format == "sorted-csv" for question in slot.spec.questions)
    )
    unknown = collector.decode_receipt(session, slot, serialized(session, slot))
    assert unknown["outcome"] == "valid"
    assert all(record["answer"] is None for record in unknown["records"])
    known = collector.decode_receipt(
        session, slot, serialized(session, slot, response_raw=inner(slot, known_empty=True))
    )
    assert known["outcome"] == "valid"
    assert sum(record["answer"] == "" for record in known["records"]) == 1
    assert sum(record["answer"] is None for record in known["records"]) == 2


def test_one_invalid_inner_answer_invalidates_the_whole_slot(session):
    slot = session.slots[0]
    value = json.loads(inner(slot))
    value["answers"][0]["question_id"] = "not-this-question"
    result = collector.decode_receipt(
        session, slot, serialized(session, slot, response_raw=json.dumps(value))
    )
    assert_result(result, "invalid", "question-set-mismatch")


@pytest.mark.parametrize("status", ["failed", "interrupted", "timeout"])
def test_reported_failures_require_no_inner_response_but_remain_failed_slots(session, status):
    slot = session.slots[0]
    assert_result(
        collector.decode_receipt(session, slot, serialized(session, slot, status=status)),
        status,
        "reported-" + status,
    )
    assert_result(
        collector.decode_receipt(
            session, slot, serialized(session, slot, status=status, response_raw=inner(slot))
        ),
        "invalid",
        "unexpected-failure-response",
    )


@pytest.mark.parametrize("status", [None, True, 1, "success", "missing", "COMPLETED", []])
def test_reported_status_is_a_closed_exact_string_set(session, status):
    slot = session.slots[0]
    assert_result(
        collector.decode_receipt(
            session, slot, serialized(session, slot, status=status, response_raw=None)
        ),
        "invalid",
        "invalid-reported-status",
    )


@pytest.mark.parametrize("response_raw", ["", False, 0])
def test_failed_receipt_accepts_only_none_not_other_falsey_response_values(session, response_raw):
    slot = session.slots[0]
    result = collector.decode_receipt(
        session, slot, serialized(session, slot, status="failed", response_raw=response_raw)
    )
    assert_result(result, "invalid", "unexpected-failure-response")


def test_old_whole_receipt_is_invalid_on_current_route_or_unmatched_on_old_route(fixed, session):
    current = collector.new_collection(fixed, config())
    old_slot, current_slot = session.slots[0], current.slots[0]
    old_raw = serialized(session, old_slot)
    assert_result(
        collector.decode_receipt(current, current_slot, old_raw),
        "invalid",
        "receipt-binding-mismatch",
    )
    old_routing = session.binding(old_slot)["invocation_id"]
    result = collector.collect_receipts(current, [(old_routing, old_raw)])
    assert result["batch_status"] == "routing-errors"
    assert len(result["unmatched"]) == 1
    assert all(item["outcome"] == "missing" for item in result["observations"])
    assert result["planned_slots"] == 14


def test_critical_counterexample_old_inner_json_rewrapped_in_current_metadata_can_validate(
    fixed, session
):
    current = collector.new_collection(fixed, config())
    old_inner = json.loads(serialized(session, session.slots[0]))["response_raw"]
    slot = current.slots[0]
    assert slot.spec.request_id == session.slots[0].spec.request_id
    current_raw = serialized(current, slot, response_raw=old_inner)
    assert collector.decode_receipt(current, slot, current_raw)["outcome"] == "valid"
    result = collector.collect_receipts(
        current, [(current.binding(slot)["invocation_id"], current_raw)]
    )
    assert result["observations"][0]["outcome"] == "valid"
    assert result["transport_provenance"] == "caller-supplied-unverified"
    assert result["provider_freshness_verified"] is False
    assert result["provider_calls_by_this_tool"] == 0
    assert any("rewrapped old inner JSON can pass" in line for line in result["limitations"])


def test_same_batch_can_be_validated_twice_without_a_persistent_one_use_claim(session):
    submissions = all_submissions(session)
    before = copy.deepcopy(submissions)
    first = collector.collect_receipts(session, submissions)
    second = collector.collect_receipts(session, submissions)
    assert first == second
    assert submissions == before
    assert first["duplicate_scope"] == "one-batch-only-no-persistent-one-use-enforcement"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("identical", [False, True])
def test_duplicate_receipts_invalidate_slot_with_no_first_or_last_wins(session, reverse, identical):
    slot = session.slots[0]
    key = session.binding(slot)["invocation_id"]
    values = [serialized(session, slot), serialized(session, slot) if identical else "not-json"]
    if reverse:
        values.reverse()
    result = collector.collect_receipts(session, [(key, raw) for raw in values])
    assert_result(result["observations"][0], "invalid", "duplicate-receipt")
    assert result["planned_slots"] == 14
    assert result["question_opportunities"] == 42
    assert len(result["unmatched"]) == 0
    assert sum(item["outcome"] == "missing" for item in result["observations"]) == 13


def test_unrouteable_submissions_remain_separate_errors_and_do_not_create_or_fill_slots(session):
    submissions = [
        ("unknown", "{}"),
        (None, "{}"),
        ["not-a-tuple", "{}"],
        (),
        ("too", "many", "parts"),
        None,
    ]
    result = collector.collect_receipts(session, submissions)
    assert result["unmatched"] == [
        {"submission_index": index, "error": "unmatched-routing-key"}
        for index in range(len(submissions))
    ]
    assert result["planned_slots"] == 14
    assert result["question_opportunities"] == 42
    assert all(item["outcome"] == "missing" for item in result["observations"])


def test_all_2n_duplicate_submissions_are_bounded_and_invalid_without_changing_n(session):
    once = all_submissions(session)
    result = collector.collect_receipts(session, once + once)
    assert result["submission_count"] == 2 * len(session.slots)
    assert len(result["observations"]) == len(session.slots)
    assert all(item["error"] == "duplicate-receipt" for item in result["observations"])
    with pytest.raises(collector.CollectionError, match="invalid-submission-count"):
        collector.collect_receipts(session, once + once + [once[0]])
    with pytest.raises(collector.CollectionError, match="invalid-submission-count"):
        collector.collect_receipts(session, ())


def test_aggregate_budget_is_encoded_utf8_even_for_unmatched_or_bad_individual_receipts(
    session, monkeypatch
):
    assert collector.MAX_BATCH_BYTES == 4 * 1024 * 1024
    monkeypatch.setattr(collector, "MAX_BATCH_BYTES", 12)
    assert collector.collect_receipts(session, [("unmatched", "é" * 6)])["submission_count"] == 1
    with pytest.raises(collector.CollectionError, match="batch-too-large"):
        collector.collect_receipts(session, [("unmatched", "é" * 7)])
    with pytest.raises(collector.CollectionError, match="batch-too-large"):
        collector.collect_receipts(session, [("a", "1234567"), ("b", "123456")])


def test_invalid_surrogates_still_consume_the_aggregate_byte_budget(session, monkeypatch):
    monkeypatch.setattr(collector, "MAX_BATCH_BYTES", 2)
    with pytest.raises(collector.CollectionError, match="batch-too-large"):
        collector.collect_receipts(session, [("unmatched", "\ud800")])


@pytest.mark.parametrize("raw", [b"{}", {}, [], True, 1, 1.5])
def test_receipt_raw_type_is_strict_and_nonstring_is_not_missing(session, raw):
    assert_result(
        collector.decode_receipt(session, session.slots[0], raw), "invalid", "invalid-receipt-type"
    )


@pytest.mark.parametrize(
    "raw,error",
    [
        ("", "invalid-receipt-json"),
        ("{} {}", "invalid-receipt-json"),
        ("[]", "invalid-receipt-fields"),
        ('{"a":1,"a":2}', "receipt-duplicate-key"),
        ('{"a":NaN}', "receipt-non-finite-json"),
        ('{"a":Infinity}', "receipt-non-finite-json"),
        ('{"a":1e309}', "receipt-non-finite-json"),
        ('"\ud800"', "invalid-receipt-utf8"),
    ],
)
def test_receipt_json_utf8_and_duplicates_are_strict(session, raw, error):
    assert_result(collector.decode_receipt(session, session.slots[0], raw), "invalid", error)


def test_deep_receipt_is_rejected_before_recursive_json_decode(session, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("depth limit must precede recursive decoder")

    monkeypatch.setattr(collector.json, "loads", forbidden)
    depth = collector.response.MAX_JSON_DEPTH + 1
    raw = "[" * depth + "]" * depth
    assert_result(
        collector.decode_receipt(session, session.slots[0], raw), "invalid", "receipt-depth-limit"
    )


def test_outer_receipt_byte_limit_accepts_exact_size_and_rejects_one_more(session, monkeypatch):
    slot = session.slots[0]
    raw = serialized(session, slot)
    monkeypatch.setattr(collector, "MAX_RECEIPT_BYTES", len(raw.encode("utf-8")))
    assert collector.decode_receipt(session, slot, raw)["outcome"] == "valid"
    assert_result(
        collector.decode_receipt(session, slot, raw + " "), "invalid", "receipt-too-large"
    )


def test_outer_receipt_limit_uses_utf8_bytes_not_python_character_count(session, monkeypatch):
    slot = next(
        slot
        for slot in session.slots
        if any(question.answer_format == "sorted-csv" for question in slot.spec.questions)
    )
    value = json.loads(inner(slot))
    value["answers"][0]["answer"] = "é"
    raw = serialized(session, slot, response_raw=json.dumps(value, ensure_ascii=False))
    assert len(raw.encode("utf-8")) > len(raw)
    monkeypatch.setattr(collector, "MAX_RECEIPT_BYTES", len(raw))
    assert_result(collector.decode_receipt(session, slot, raw), "invalid", "receipt-too-large")


def test_observation_flags_are_unverified_unmeasured_and_never_quality_scores(session):
    result = collector.collect_receipts(session, all_submissions(session))
    assert result["transport_provenance"] == "caller-supplied-unverified"
    assert result["model_availability"] == "unverified"
    for field in (
        "provider_freshness_verified",
        "model_quality_measured",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "live_benchmark_ready",
    ):
        assert result[field] is False
    for field in ("effective_model_observed", "provider_usage", "provider_latency_seconds"):
        assert result[field] is None
    assert result["provider_calls_by_this_tool"] == result["live_trials"] == 0
    assert result["target_execution"] == result["scoring_status"] == "not-run"
    assert "calculation" not in result


def test_only_pinned_tasks_are_read_then_batch_validation_is_completely_pure(fixed, monkeypatch):
    original_open = Path.open
    opened = []

    def task_only(path, *args, **kwargs):
        assert path == fixed / collector.planner.comparison.reference.REFERENCE / "tasks.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("no account/reference/manifest/scoring/provider/process/target I/O")

    monkeypatch.setattr(Path, "open", task_only)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(collector.planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(collector.planner.comparison.reference, "score_reference", forbidden)
    monkeypatch.setattr(collector.planner.comparison.FastAPIRouteParser, "parse_file", forbidden)
    monkeypatch.setattr(
        collector.planner.comparison.FastAPIRouteParser, "parse_repository", forbidden
    )
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    session = collector.new_collection(fixed, config())
    assert opened == ["tasks.json"]
    monkeypatch.setattr(Path, "open", forbidden)
    result = collector.collect_receipts(session, all_submissions(session))
    assert len(result["observations"]) == 14


@pytest.mark.parametrize("fault", [None, *collector.FAULTS])
def test_synthetic_dry_run_faults_retain_all_opportunities_without_live_calls(fixed, fault):
    result = collector.dry_run(fixed, config(), fault=fault)
    assert result["planned_slots"] == 14
    assert result["question_opportunities"] == 42
    assert result["response_origin"] == "synthetic-null-receipts-with-optional-fault"
    assert result["fault"] == fault
    expected = (
        "valid"
        if fault is None
        else "invalid"
        if fault in ("invalid", "duplicate", "stale")
        else "missing"
        if fault == "unmatched"
        else fault
    )
    assert result["observations"][0]["outcome"] == expected
    assert all(item["outcome"] == "valid" for item in result["observations"][1:])
    assert len(result["unmatched"]) == int(fault == "unmatched")
    assert result["provider_calls_by_this_tool"] == 0
    assert result["model_quality_measured"] is False


CLI_ARGS = [
    "--dry-run",
    "--model",
    "proposed-model",
    "--effort",
    "proposed-effort",
    "--repetitions",
    "1",
    "--timeout-seconds",
    "30",
]


@pytest.mark.parametrize(
    "flag", ["--dry-run", "--model", "--effort", "--repetitions", "--timeout-seconds"]
)
def test_all_cli_execution_mode_and_configuration_arguments_are_required(flag, capsys):
    args = CLI_ARGS.copy()
    index = args.index(flag)
    del args[index : index + (1 if flag == "--dry-run" else 2)]
    with pytest.raises(SystemExit) as error:
        collector.main(args)
    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


@pytest.mark.parametrize("fault", [None, *collector.FAULTS])
def test_json_cli_is_one_synthetic_observation_not_live_quality(fixed, monkeypatch, capsys, fault):
    monkeypatch.setattr(collector, "ROOT", fixed)
    args = [*CLI_ARGS, "--json", *(["--fault", fault] if fault else [])]
    assert collector.main(args) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert captured.err == ""
    assert len(captured.out.splitlines()) == 1
    assert result["kind"] == "offline-host-receipt-observation"
    assert result["planned_slots"] == 14
    assert result["fault"] == fault
    assert result["provider_freshness_verified"] is False


def test_human_cli_states_host_only_limit_and_retained_denominators(fixed, monkeypatch, capsys):
    monkeypatch.setattr(collector, "ROOT", fixed)
    assert collector.main(CLI_ARGS) == 0
    output = capsys.readouterr().out
    assert "SYNTHETIC HOST RECEIPTS ONLY" in output
    assert "14 slots / 42 question opportunities" in output
    assert "Schema-valid is NOT model correctness" in output
    assert "rewrapped old inner JSON can pass" in output
    assert "persistent one-use enforcement" in output


def test_cli_invalid_configuration_is_an_error_without_partial_observation(capsys):
    args = CLI_ARGS.copy()
    args[args.index("--repetitions") + 1] = "0"
    assert collector.main([*args, "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "kind": "offline-collection-error",
        "error": "invalid-repetitions",
        "execution_authorized": False,
        "provider_calls_by_this_tool": 0,
    }


def test_cli_rejects_arbitrary_receipt_paths_and_invalid_fault_values(capsys):
    for extra in (["--receipt", "private.json"], ["--fault", "arbitrary"]):
        with pytest.raises(SystemExit) as error:
            collector.main([*CLI_ARGS, *extra])
        assert error.value.code == 2
        assert capsys.readouterr().err
