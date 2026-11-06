"""Evaluation answer normalization is strict, complete, pure and separately versioned."""

from __future__ import annotations

import builtins
import copy
import io
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from scripts import evaluation_metrics as metrics
from scripts import evaluation_response as contract

TASK_ID = "task-" + "a1" * 32
REQUEST_ID = "request-" + "b2" * 32


def spec(*questions: contract.Question) -> contract.ResponseSpec:
    return contract.ResponseSpec(
        TASK_ID, REQUEST_ID, questions or (contract.Question("scope-list", "sorted-csv"),)
    )


def document(**values: object) -> dict:
    return {
        "schema_version": "0.1",
        "kind": "evaluation-comparison-response",
        "task_id": TASK_ID,
        "request_id": REQUEST_ID,
        "answers": [{"question_id": "scope-list", "answer": ""}],
        **values,
    }


def decode(value: dict, selected: contract.ResponseSpec | None = None) -> dict:
    return contract.decode_response(selected or spec(), json.dumps(value))


def assert_invalid(result: dict, error: str) -> None:
    assert error in contract.ERROR_CODES
    assert result == {"status": "invalid", "error": error, "records": None}


def test_empty_csv_is_known_and_only_null_is_unknown():
    known = decode(document())
    assert known == {
        "status": "valid",
        "error": None,
        "records": [{"question_id": "scope-list", "answer": ""}],
    }
    unknown = decode(document(answers=[{"question_id": "scope-list", "answer": None}]))
    assert unknown["records"] == [{"question_id": "scope-list", "answer": None}]
    assert contract.decode_response(spec(), None) == {
        "status": "missing",
        "error": "missing-response",
        "records": None,
    }


def test_complete_answers_are_reordered_to_spec_without_modifying_values_or_input():
    selected = spec(
        contract.Question("count", "integer"),
        contract.Question("intent", "policy"),
        contract.Question("assurance", "unknown-or-boolean"),
    )
    value = document(
        answers=[
            {"question_id": "assurance", "answer": None},
            {"question_id": "intent", "answer": "public"},
            {"question_id": "count", "answer": "2"},
        ]
    )
    before = copy.deepcopy(value)
    result = decode(value, selected)
    assert value == before
    assert result == {
        "status": "valid",
        "error": None,
        "records": [
            {"question_id": "count", "answer": "2"},
            {"question_id": "intent", "answer": "public"},
            {"question_id": "assurance", "answer": None},
        ],
    }


@pytest.mark.parametrize(
    "answer_format,value",
    [
        ("integer", "0"),
        ("integer", "42"),
        ("integer", "9" * 512),
        ("sorted-csv", ""),
        ("sorted-csv", "alpha,beta"),
        ("sorted-csv", "а,я"),
        ("sorted-csv", "left hand,right hand"),
        ("boolean", "true"),
        ("boolean", "false"),
        ("unknown-or-boolean", "true"),
        ("unknown-or-boolean", "false"),
        ("policy", "public"),
        ("policy", "restricted"),
        ("policy", "mixed"),
    ],
)
def test_canonical_answers_are_copied_without_coercion(answer_format, value):
    selected = spec(contract.Question("scope-list", answer_format))
    result = decode(document(answers=[{"question_id": "scope-list", "answer": value}]), selected)
    assert result["status"] == "valid"
    assert result["records"][0]["answer"] == value


@pytest.mark.parametrize("answer_format", contract.FORMATS)
def test_null_is_valid_abstention_for_every_format(answer_format):
    selected = spec(contract.Question("scope-list", answer_format))
    result = decode(document(answers=[{"question_id": "scope-list", "answer": None}]), selected)
    assert result["status"] == "valid"
    assert result["records"][0]["answer"] is None


@pytest.mark.parametrize(
    "answer_format,value",
    [
        ("integer", "01"),
        ("integer", "-1"),
        ("integer", "+1"),
        ("integer", "1.0"),
        ("integer", " 1"),
        ("integer", "1 "),
        ("integer", "１"),
        ("integer", 1),
        ("integer", True),
        ("integer", "1" * 513),
        ("sorted-csv", "beta,alpha"),
        ("sorted-csv", "alpha,alpha"),
        ("sorted-csv", "alpha, beta"),
        ("sorted-csv", "alpha,"),
        ("sorted-csv", ",alpha"),
        ("sorted-csv", " "),
        ("sorted-csv", "alpha\nbeta"),
        ("sorted-csv", "\x00"),
        ("sorted-csv", "\ud800"),
        ("sorted-csv", []),
        ("sorted-csv", {}),
        ("boolean", True),
        ("boolean", "True"),
        ("boolean", "yes"),
        ("unknown-or-boolean", "unknown"),
        ("unknown-or-boolean", "null"),
        ("policy", "PUBLIC"),
        ("policy", " public"),
        ("policy", "private"),
        ("policy", 0),
    ],
)
def test_noncanonical_answers_are_not_repaired_or_made_unknown(answer_format, value):
    selected = spec(contract.Question("scope-list", answer_format))
    result = decode(document(answers=[{"question_id": "scope-list", "answer": value}]), selected)
    assert_invalid(result, "invalid-answer")


def test_one_bad_answer_invalidates_whole_case_instead_of_partial_recovery():
    selected = spec(contract.Question("count", "integer"), contract.Question("intent", "policy"))
    result = decode(
        document(
            answers=[
                {"question_id": "count", "answer": "3"},
                {"question_id": "intent", "answer": "PUBLIC"},
            ]
        ),
        selected,
    )
    assert_invalid(result, "invalid-answer")


@pytest.mark.parametrize("field", ["schema_version", "kind", "task_id", "request_id", "answers"])
def test_missing_top_level_fields_fail_the_whole_case(field):
    value = document()
    del value[field]
    assert_invalid(decode(value), "invalid-response-fields")


@pytest.mark.parametrize("field", ["citations", "explanation", "confidence", "extra"])
def test_contract_does_not_implicitly_add_citations_or_explanations(field):
    assert_invalid(decode(document(**{field: []})), "invalid-response-fields")


@pytest.mark.parametrize(
    "values,error",
    [
        ({"schema_version": "1.0"}, "unsupported-schema-version"),
        ({"schema_version": 0.1}, "unsupported-schema-version"),
        ({"schema_version": None}, "unsupported-schema-version"),
        ({"kind": "product-result"}, "invalid-response-kind"),
        ({"kind": []}, "invalid-response-kind"),
        ({"task_id": "task-" + "b" * 64}, "task-id-mismatch"),
        ({"task_id": TASK_ID.upper()}, "task-id-mismatch"),
        ({"task_id": None}, "task-id-mismatch"),
        ({"task_id": {}}, "task-id-mismatch"),
        ({"request_id": "request-" + "c" * 64}, "request-id-mismatch"),
        ({"request_id": REQUEST_ID.upper()}, "request-id-mismatch"),
        ({"request_id": None}, "request-id-mismatch"),
        ({"request_id": {}}, "request-id-mismatch"),
        ({"answers": None}, "invalid-answer-set"),
        ({"answers": {}}, "invalid-answer-set"),
        ({"answers": "unknown"}, "invalid-answer-set"),
    ],
)
def test_response_schema_and_task_identity_are_exact(values, error):
    assert_invalid(decode(document(**values)), error)


@pytest.mark.parametrize(
    "answers,error",
    [
        ([], "question-set-mismatch"),
        ([{"question_id": "wrong", "answer": None}], "question-set-mismatch"),
        ([{"question_id": None, "answer": None}], "question-set-mismatch"),
        ([{"question_id": [], "answer": None}], "question-set-mismatch"),
        ([{"question_id": "scope-list", "answer": None}] * 2, "question-set-mismatch"),
        ([{"question_id": "scope-list"}], "invalid-answer-fields"),
        ([{"answer": None}], "invalid-answer-fields"),
        ([{"question_id": "scope-list", "answer": None, "extra": 1}], "invalid-answer-fields"),
        ([None], "invalid-answer-fields"),
        ([[]], "invalid-answer-fields"),
    ],
)
def test_answer_records_are_exact_complete_and_known(answers, error):
    assert_invalid(decode(document(answers=answers)), error)


def test_duplicate_question_ids_are_rejected_even_when_list_length_matches():
    selected = spec(contract.Question("count", "integer"), contract.Question("intent", "policy"))
    result = decode(
        document(
            answers=[
                {"question_id": "count", "answer": "1"},
                {"question_id": "count", "answer": "2"},
            ]
        ),
        selected,
    )
    assert_invalid(result, "question-set-mismatch")


@pytest.mark.parametrize("raw", [b"{}", bytearray(b"{}"), {}, [], 0, True, 1.5])
def test_nonstring_raw_responses_are_invalid_not_missing(raw):
    assert_invalid(contract.decode_response(spec(), raw), "invalid-type")


@pytest.mark.parametrize("raw", ["", " ", "{", "```json\n{}\n```", "{} {}", "[]", "null", "42"])
def test_raw_response_requires_one_complete_json_object(raw):
    result = contract.decode_response(spec(), raw)
    expected = "invalid-response-fields" if raw in ("[]", "null", "42") else "invalid-json"
    assert_invalid(result, expected)


@pytest.mark.parametrize(
    "raw",
    [
        '{"answers":[],"answers":[]}',
        '{"answers":[{"answer":null,"answer":null}]}',
        '{"task_id":"x","task_\\u0069d":"y"}',
    ],
)
def test_duplicate_json_keys_are_rejected_at_every_depth(raw):
    assert_invalid(contract.decode_response(spec(), raw), "duplicate-key")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e309", "-1e309"])
def test_nonfinite_json_values_are_rejected_without_escaping_to_results(constant):
    assert_invalid(
        contract.decode_response(spec(), '{"extra":' + constant + "}"), "non-finite-json"
    )


def test_raw_unpaired_surrogate_is_not_encodable_utf8():
    assert_invalid(contract.decode_response(spec(), '"\ud800"'), "invalid-utf8")


def test_escaped_surrogate_answer_is_not_accepted_as_canonical_text():
    raw = json.dumps(document()).replace('"answer": ""', '"answer": "\\udfff"')
    assert_invalid(contract.decode_response(spec(), raw), "invalid-answer")


def test_raw_byte_limit_counts_utf8_bytes_not_only_python_characters():
    raw = "é" * (contract.MAX_RAW_BYTES // 2 + 1)
    assert len(raw) <= contract.MAX_RAW_BYTES
    assert_invalid(contract.decode_response(spec(), raw), "response-too-large")


def test_raw_character_limit_rejects_before_encoding(monkeypatch):
    monkeypatch.setattr(contract, "MAX_RAW_BYTES", 4)
    assert_invalid(contract.decode_response(spec(), "x" * 5), "response-too-large")


def test_exact_raw_byte_limit_is_allowed_but_one_more_byte_is_not():
    raw = json.dumps(document())
    padded = raw + " " * (contract.MAX_RAW_BYTES - len(raw))
    assert contract.decode_response(spec(), padded)["status"] == "valid"
    assert_invalid(contract.decode_response(spec(), padded + " "), "response-too-large")


def test_depth_bound_is_checked_before_the_json_decoder(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("too-deep input must be rejected before recursive JSON decoding")

    monkeypatch.setattr(json, "loads", forbidden)
    raw = "[" * (contract.MAX_JSON_DEPTH + 1) + "]" * (contract.MAX_JSON_DEPTH + 1)
    assert_invalid(contract.decode_response(spec(), raw), "depth-limit")


def test_depth_scanner_ignores_brackets_and_escaped_quotes_inside_strings():
    # These are legal canonical CSV values, not nested JSON containers.
    value = '["' + "[" * 20 + '\\"' + "]" * 20
    result = decode(document(answers=[{"question_id": "scope-list", "answer": value}]))
    assert result["status"] == "valid"
    assert result["records"][0]["answer"] == value


@pytest.mark.parametrize("identifier", ["", "Upper", "with space", "a" * 81, None, [], "é"])
def test_question_identifiers_are_fixed_bounded_slugs(identifier):
    with pytest.raises(contract.ContractError, match="invalid question id"):
        contract.Question(identifier, "integer")


@pytest.mark.parametrize("answer_format", [None, [], "number", "INTEGER"])
def test_question_answer_formats_are_a_closed_set(answer_format):
    with pytest.raises(contract.ContractError, match="invalid answer format"):
        contract.Question("count", answer_format)


@pytest.mark.parametrize("task_id", [None, [], "task-a", "task-" + "A" * 64, "task-" + "g" * 64])
def test_response_spec_requires_exact_task_digest_identity(task_id):
    with pytest.raises(contract.ContractError, match="invalid task id"):
        contract.ResponseSpec(task_id, REQUEST_ID, (contract.Question("count", "integer"),))


@pytest.mark.parametrize(
    "request_id", [None, [], "request-a", "request-" + "A" * 64, "request-" + "g" * 64]
)
def test_response_spec_requires_exact_request_digest_identity(request_id):
    with pytest.raises(contract.ContractError, match="invalid request id"):
        contract.ResponseSpec(TASK_ID, request_id, (contract.Question("count", "integer"),))


def test_same_task_cannot_reuse_another_mode_or_stale_instruction_response():
    questions = (contract.Question("scope-list", "sorted-csv"),)
    # The task is intentionally shared, but each exact instruction/evidence request differs.
    current = contract.ResponseSpec(TASK_ID, REQUEST_ID, questions)
    another_mode = contract.ResponseSpec(TASK_ID, "request-" + "c3" * 32, questions)
    changed_instruction = contract.ResponseSpec(TASK_ID, "request-" + "d4" * 32, questions)
    changed_evidence = contract.ResponseSpec(TASK_ID, "request-" + "e5" * 32, questions)
    raw = json.dumps(document())
    assert contract.decode_response(current, raw)["status"] == "valid"
    for changed_request in (another_mode, changed_instruction, changed_evidence):
        assert_invalid(contract.decode_response(changed_request, raw), "request-id-mismatch")


@pytest.mark.parametrize(
    "questions", [(), [], (None,), ("count",), (contract.Question("a", "integer"),) * 7]
)
def test_response_spec_requires_one_to_six_actual_questions(questions):
    with pytest.raises(contract.ContractError, match="invalid question"):
        contract.ResponseSpec(TASK_ID, REQUEST_ID, questions)


def test_response_spec_rejects_duplicate_questions_and_is_frozen():
    question = contract.Question("count", "integer")
    with pytest.raises(contract.ContractError, match="duplicate question id"):
        contract.ResponseSpec(TASK_ID, REQUEST_ID, (question, question))
    selected = spec(question)
    with pytest.raises(FrozenInstanceError):
        selected.task_id = "changed"
    with pytest.raises(FrozenInstanceError):
        question.id = "changed"


def test_decode_revalidates_evaluator_owned_spec_and_raises_on_corruption():
    selected = spec()
    object.__setattr__(selected, "questions", ())
    with pytest.raises(contract.ContractError, match="invalid question collection"):
        contract.decode_response(selected, None)
    with pytest.raises(contract.ContractError, match="invalid response specification"):
        contract.decode_response({}, None)


@pytest.mark.parametrize("answer_format", contract.FORMATS)
@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "0",
        "01",
        "true",
        "false",
        "public",
        "mixed",
        "a,b",
        "b,a",
        "a,a",
        " a",
        0,
        True,
        [],
        "\ud800",
    ],
)
def test_answer_acceptance_matches_unchanged_frozen_metric_contract(answer_format, value):
    selected = spec(contract.Question("scope-list", answer_format))
    normalized = decode(
        document(answers=[{"question_id": "scope-list", "answer": value}]), selected
    )
    assert (normalized["status"] == "valid") == metrics._answer(value, answer_format)


def test_success_and_failure_do_not_touch_files_processes_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure response normalization cannot perform I/O, process or network calls")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert decode(document())["status"] == "valid"
    assert_invalid(contract.decode_response(spec(), "{}"), "invalid-response-fields")
    assert contract.decode_response(spec(), None)["status"] == "missing"
