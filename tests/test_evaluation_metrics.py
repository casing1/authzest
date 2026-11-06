"""Pure metric arithmetic uses invented examples, never pending reference labels."""

from __future__ import annotations

import builtins
import copy
import io
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from scripts import check_evaluation_candidate as checker
from scripts import evaluation_metrics as metrics


def question(
    identifier: str = "invented-count",
    family: str = "declaration",
    answer_format: str = "integer",
    expected: str | None = "2",
) -> metrics.QuestionSpec:
    return metrics.QuestionSpec(identifier, family, answer_format, expected)


def case(
    identifier: str = "invented-case",
    split: str = "development",
    questions: tuple[metrics.QuestionSpec, ...] | None = None,
) -> metrics.CaseSpec:
    return metrics.CaseSpec(
        identifier, split, questions if questions is not None else (question(),)
    )


def response(**answers: object) -> list[dict]:
    return [{"question_id": key, "answer": value} for key, value in answers.items()]


def assert_ratio(actual: dict, numerator: int, denominator: int) -> None:
    assert actual == {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def assert_group(actual: dict, **counts: int) -> None:
    assert actual["counts"] == counts
    expected_ratios = {
        "answered_accuracy": (counts["correct_answers"], counts["answered"]),
        "task_coverage": (counts["answered"], counts["questions"]),
        "correct_answer_yield": (counts["correct_answers"], counts["questions"]),
        "answerable_yield": (counts["correct_answers"], counts["answerable"]),
        "required_unknown_handling": (counts["correct_unknowns"], counts["required_unknown"]),
        "false_abstention": (counts["false_abstentions"], counts["answerable"]),
        "false_certainty": (counts["false_certainties"], counts["required_unknown"]),
        "invalid_responses": (counts["invalid_responses"], counts["cases"]),
    }
    assert set(actual["metrics"]) == set(expected_ratios)
    for name, (numerator, denominator) in expected_ratios.items():
        assert_ratio(actual["metrics"][name], numerator, denominator)


def test_mixed_outcomes_are_aggregated_by_question_not_mean_case_percentages():
    cases = (
        case(
            "invented-alpha",
            questions=(
                question("count"),
                question("access-intent", "policy-intent", "policy", "public"),
                question("live-state", "runtime-assurance", "unknown-or-boolean", None),
                question("scope-list", answer_format="sorted-csv", expected=""),
            ),
        ),
        case(
            "invented-beta",
            "reserved-evaluation",
            (
                question("declaration-flag", answer_format="boolean", expected="false"),
                question("access-intent", "policy-intent", "policy", "mixed"),
                question("live-state", "runtime-assurance", "unknown-or-boolean", None),
            ),
        ),
        case(
            "invented-gamma",
            "reserved-evaluation",
            (
                question("count", expected="3"),
                question("live-state", "runtime-assurance", "unknown-or-boolean", None),
            ),
        ),
        case(
            "invented-delta",
            questions=(question("access-intent", "policy-intent", "policy", "restricted"),),
        ),
    )
    responses = {
        "invented-alpha": response(
            count="2", **{"access-intent": "restricted", "live-state": "true", "scope-list": None}
        ),
        "invented-beta": response(
            **{"declaration-flag": "false", "access-intent": None, "live-state": None}
        ),
        # One duplicate invalidates the whole case, including an otherwise correct answer.
        "invented-gamma": response(count="3") + response(count="3"),
    }
    result = metrics.score_cases(cases, responses)
    assert result["kind"] == "offline-metric-calculation"
    assert result["schema_version"] == "0.1"
    assert result["calculation_only"] is True
    assert result["benchmark_ready"] is False
    assert result["reference_review_status"] == "not-assessed"
    assert_group(
        result["overall"],
        cases=4,
        invalid_responses=2,
        missing_responses=1,
        questions=10,
        answerable=7,
        required_unknown=3,
        answered=4,
        correct_answers=2,
        correct_unknowns=1,
        abstentions=3,
        false_abstentions=2,
        false_certainties=1,
        invalid_questions=3,
    )
    assert set(result["by_family"]) == {
        "declaration",
        "policy-intent",
        "runtime-assurance",
    }
    assert_group(
        result["by_family"]["declaration"],
        cases=3,
        invalid_responses=1,
        missing_responses=0,
        questions=4,
        answerable=4,
        required_unknown=0,
        answered=2,
        correct_answers=2,
        correct_unknowns=0,
        abstentions=1,
        false_abstentions=1,
        false_certainties=0,
        invalid_questions=1,
    )
    assert_group(
        result["by_family"]["policy-intent"],
        cases=3,
        invalid_responses=1,
        missing_responses=1,
        questions=3,
        answerable=3,
        required_unknown=0,
        answered=1,
        correct_answers=0,
        correct_unknowns=0,
        abstentions=1,
        false_abstentions=1,
        false_certainties=0,
        invalid_questions=1,
    )
    assert_group(
        result["by_family"]["runtime-assurance"],
        cases=3,
        invalid_responses=1,
        missing_responses=0,
        questions=3,
        answerable=0,
        required_unknown=3,
        answered=1,
        correct_answers=0,
        correct_unknowns=1,
        abstentions=1,
        false_abstentions=0,
        false_certainties=1,
        invalid_questions=1,
    )
    assert set(result["by_split"]) == {"development", "reserved-evaluation"}
    assert_group(
        result["by_split"]["development"],
        cases=2,
        invalid_responses=1,
        missing_responses=1,
        questions=5,
        answerable=4,
        required_unknown=1,
        answered=3,
        correct_answers=1,
        correct_unknowns=0,
        abstentions=1,
        false_abstentions=1,
        false_certainties=1,
        invalid_questions=1,
    )
    assert_group(
        result["by_split"]["reserved-evaluation"],
        cases=2,
        invalid_responses=1,
        missing_responses=0,
        questions=5,
        answerable=3,
        required_unknown=2,
        answered=1,
        correct_answers=1,
        correct_unknowns=1,
        abstentions=2,
        false_abstentions=1,
        false_certainties=0,
        invalid_questions=2,
    )
    assert [item["case_id"] for item in result["cases"]] == [item.id for item in cases]
    assert [item["response_valid"] for item in result["cases"]] == [True, True, False, False]
    assert [len(item["questions"]) for item in result["cases"]] == [4, 3, 2, 1]
    assert all(item["error"] is None for item in result["cases"][:2])
    assert [item["error"] for item in result["cases"][2:]] == [
        "question-set-mismatch",
        "missing-response",
    ]
    assert result["cases"][0]["questions"] == [
        {"question_id": "count", "family": "declaration", "outcome": "correct-answer"},
        {
            "question_id": "access-intent",
            "family": "policy-intent",
            "outcome": "wrong-answer",
        },
        {
            "question_id": "live-state",
            "family": "runtime-assurance",
            "outcome": "false-certainty",
        },
        {
            "question_id": "scope-list",
            "family": "declaration",
            "outcome": "false-abstention",
        },
    ]
    assert result["cases"][1]["questions"][2]["outcome"] == "correct-unknown"
    assert all(
        item["outcome"] == "invalid-response"
        for invalid_case in result["cases"][2:]
        for item in invalid_case["questions"]
    )


def test_known_empty_csv_is_an_answer_not_an_unknown_abstention():
    cases = (case(questions=(question(answer_format="sorted-csv", expected=""),)),)
    known = metrics.score_cases(cases, {"invented-case": response(**{"invented-count": ""})})
    abstained = metrics.score_cases(cases, {"invented-case": response(**{"invented-count": None})})
    assert known["overall"]["counts"]["answered"] == 1
    assert known["overall"]["counts"]["correct_answers"] == 1
    assert known["overall"]["counts"]["abstentions"] == 0
    assert abstained["overall"]["counts"]["answered"] == 0
    assert abstained["overall"]["counts"]["false_abstentions"] == 1
    assert abstained["overall"]["counts"]["correct_unknowns"] == 0
    assert_ratio(abstained["overall"]["metrics"]["answered_accuracy"], 0, 0)


def test_required_unknown_is_separate_from_correct_answer_credit_and_zero_denominators():
    cases = (
        case(questions=(question("live-state", "runtime-assurance", "unknown-or-boolean", None),)),
    )
    result = metrics.score_cases(cases, {"invented-case": response(**{"live-state": None})})
    counts = result["overall"]["counts"]
    assert counts["correct_answers"] == counts["answered"] == counts["answerable"] == 0
    assert counts["correct_unknowns"] == counts["abstentions"] == 1
    assert_ratio(result["overall"]["metrics"]["required_unknown_handling"], 1, 1)
    assert_ratio(result["overall"]["metrics"]["answered_accuracy"], 0, 0)
    assert_ratio(result["overall"]["metrics"]["answerable_yield"], 0, 0)
    assert_ratio(result["overall"]["metrics"]["false_abstention"], 0, 0)
    for group in (
        result["by_family"]["declaration"],
        result["by_family"]["policy-intent"],
        result["by_split"]["reserved-evaluation"],
    ):
        assert all(value == 0 for value in group["counts"].values())
        assert all(
            value == {"numerator": 0, "denominator": 0, "value": None}
            for value in group["metrics"].values()
        )
    assert result["unmeasured"] == {
        "citation_id_validity": None,
        "citation_semantic_support": None,
        "unsupported_claims": None,
        "human_review_seconds": None,
        "provider_usage": None,
        "latency_ms": None,
        "repeat_variation": None,
        "workflow_outcomes": None,
    }


@pytest.mark.parametrize(
    "answer_format,expected",
    [
        ("integer", "0"),
        ("integer", "27"),
        ("sorted-csv", ""),
        ("sorted-csv", "read,write"),
        ("boolean", "true"),
        ("boolean", "false"),
        ("policy", "public"),
        ("policy", "restricted"),
        ("policy", "mixed"),
        ("unknown-or-boolean", "true"),
        ("unknown-or-boolean", "false"),
    ],
)
def test_canonical_known_strings_are_not_normalized(answer_format, expected):
    cases = (case(questions=(question(answer_format=answer_format, expected=expected),)),)
    result = metrics.score_cases(cases, {"invented-case": response(**{"invented-count": expected})})
    assert result["cases"][0]["response_valid"] is True
    assert_ratio(result["overall"]["metrics"]["answered_accuracy"], 1, 1)


@pytest.mark.parametrize(
    "answer_format,invalid",
    [
        ("integer", ""),
        ("integer", " 2"),
        ("integer", "2 "),
        ("integer", "+2"),
        ("integer", "02"),
        ("integer", "-1"),
        ("integer", "2.0"),
        ("integer", "２"),
        ("integer", 2),
        ("integer", True),
        ("integer", False),
        ("integer", 2.0),
        ("integer", []),
        ("integer", {}),
        ("integer", "2" * 513),
        ("sorted-csv", "write,read"),
        ("sorted-csv", "read,read"),
        ("sorted-csv", "read, write"),
        ("sorted-csv", "read,"),
        ("sorted-csv", ",read"),
        ("sorted-csv", "read\nwrite"),
        ("sorted-csv", "read\x00write"),
        ("sorted-csv", "\ud800"),
        ("boolean", "True"),
        ("boolean", "1"),
        ("boolean", ""),
        ("boolean", True),
        ("policy", "PUBLIC"),
        ("policy", " public"),
        ("policy", "unknown"),
        ("policy", ""),
        ("unknown-or-boolean", "unknown"),
        ("unknown-or-boolean", "False"),
        ("unknown-or-boolean", ""),
    ],
)
def test_noncanonical_answers_invalidate_the_whole_response(answer_format, invalid):
    expected = {
        "integer": "2",
        "sorted-csv": "read,write",
        "boolean": "true",
        "policy": "public",
        "unknown-or-boolean": None,
    }[answer_format]
    cases = (
        case(
            questions=(
                question("otherwise-correct"),
                question("malformed", answer_format=answer_format, expected=expected),
            )
        ),
    )
    result = metrics.score_cases(
        cases,
        {"invented-case": response(**{"otherwise-correct": "2", "malformed": invalid})},
    )
    assert result["cases"][0]["response_valid"] is False
    assert result["cases"][0]["error"] == "invalid-answer"
    assert len(result["cases"][0]["questions"]) == 2
    counts = result["overall"]["counts"]
    assert counts["questions"] == counts["invalid_questions"] == 2
    assert counts["invalid_responses"] == 1
    assert counts["missing_responses"] == 0
    assert counts["answered"] == counts["correct_answers"] == counts["correct_unknowns"] == 0
    assert counts["abstentions"] == counts["false_abstentions"] == counts["false_certainties"] == 0


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {},
        "not a response",
        (),
        [None],
        ["invented-count"],
        [{"question_id": "invented-count"}],
        [{"answer": "2"}],
        [{"question_id": "invented-count", "answer": "2", "extra": None}],
        [{"question_id": "wrong-question", "answer": "2"}],
        [{"question_id": 1, "answer": "2"}],
        [{"question_id": "invented-count", "answer": "2"}] * 2,
        [
            {"question_id": "invented-count", "answer": "2"},
            {"question_id": "extra", "answer": "2"},
        ],
    ],
)
def test_malformed_response_retains_question_denominators_without_credit(raw):
    result = metrics.score_cases((case(),), {"invented-case": raw})
    item = result["cases"][0]
    assert item["case_id"] == "invented-case"
    assert item["split"] == "development"
    assert item["response_valid"] is False
    assert isinstance(item["error"], str) and item["error"]
    assert len(item["questions"]) == 1
    counts = result["overall"]["counts"]
    assert counts["questions"] == counts["answerable"] == counts["invalid_questions"] == 1
    assert counts["invalid_responses"] == 1
    assert counts["missing_responses"] == 0
    assert_ratio(result["overall"]["metrics"]["task_coverage"], 0, 1)
    assert_ratio(result["overall"]["metrics"]["answerable_yield"], 0, 1)


@pytest.mark.parametrize("responses", [{}, {"invented-case": None}])
def test_absent_or_null_case_response_is_missing_not_successful_abstention(responses):
    cases = (
        case(questions=(question("live-state", "runtime-assurance", "unknown-or-boolean", None),)),
    )
    result = metrics.score_cases(cases, responses)
    assert result["cases"][0]["error"] == "missing-response"
    counts = result["overall"]["counts"]
    assert counts["missing_responses"] == counts["invalid_responses"] == 1
    assert counts["required_unknown"] == counts["invalid_questions"] == 1
    assert counts["correct_unknowns"] == counts["abstentions"] == 0
    assert_ratio(result["overall"]["metrics"]["required_unknown_handling"], 0, 1)


def test_record_order_is_irrelevant_but_output_order_follows_the_specification():
    cases = (case(questions=(question("first"), question("second", expected="3"))),)
    ordered = metrics.score_cases(cases, {"invented-case": response(first="2", second="3")})
    reversed_records = metrics.score_cases(
        cases, {"invented-case": response(second="3", first="2")}
    )
    assert ordered == reversed_records


def test_policy_question_is_recognized_by_family_not_a_magic_question_id():
    cases = (
        case(
            questions=(
                question("not-the-word-policy", "policy-intent", "policy", "mixed"),
                question("policy", "declaration", "integer", "2"),
            )
        ),
    )
    result = metrics.score_cases(
        cases, {"invented-case": response(**{"not-the-word-policy": "mixed", "policy": "2"})}
    )
    assert result["by_family"]["policy-intent"]["counts"]["questions"] == 1
    assert result["by_family"]["policy-intent"]["counts"]["correct_answers"] == 1
    assert result["by_family"]["declaration"]["counts"]["correct_answers"] == 1


@pytest.mark.parametrize("numerator,denominator", [(0, 0), (0, 3), (2, 3), (3, 3)])
def test_ratio_has_exact_numerator_denominator_and_optional_value(numerator, denominator):
    assert_ratio(metrics.ratio(numerator, denominator), numerator, denominator)


@pytest.mark.parametrize(
    "numerator,denominator",
    [(True, 1), (0, False), (1.0, 2), (0, 2.0), ("0", 1), (0, None), (-1, 1), (0, -1), (2, 1)],
)
def test_ratio_rejects_nonintegers_negative_or_impossible_counts(numerator, denominator):
    with pytest.raises(metrics.MetricsError):
        metrics.ratio(numerator, denominator)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"id": "not a slug"},
        {"id": 1},
        {"family": "policy"},
        {"family": None},
        {"answer_format": "number"},
        {"answer_format": None},
        {"expected": 2},
        {"expected": True},
        {"expected": "02"},
        {"expected": ""},
        {"expected": " 2"},
        {"answer_format": "policy", "expected": "PUBLIC"},
        {"answer_format": "sorted-csv", "expected": "b,a"},
        {"answer_format": "boolean", "expected": "TRUE"},
    ],
)
def test_invalid_question_specification_is_a_caller_error(changes):
    with pytest.raises(metrics.MetricsError):
        metrics.score_cases((case(questions=(replace(question(), **changes),)),), {})


@pytest.mark.parametrize(
    "make_cases",
    [
        lambda: (),
        lambda: [],
        lambda: [case()],
        lambda: (None,),
        lambda: ({"id": "invented-case"},),
        lambda: (case(), case()),
        lambda: (case(identifier=""),),
        lambda: (case(identifier="not a slug"),),
        lambda: (case(identifier=True),),
        lambda: (case(split="held-out"),),
        lambda: (case(split=None),),
        lambda: (case(questions=()),),
        lambda: (case(questions=(question(), question())),),
        lambda: (case(questions=(None,)),),
        lambda: (replace(case(), questions=[question()]),),
        lambda: tuple(case(identifier=f"invented-{number}") for number in range(33)),
        lambda: (case(questions=tuple(question(f"invented-{number}") for number in range(17))),),
    ],
)
def test_invalid_case_manifest_is_a_caller_error(make_cases):
    with pytest.raises(metrics.MetricsError):
        metrics.score_cases(make_cases(), {})


def test_maximum_case_and_question_counts_are_accepted_without_truncation():
    questions = tuple(question(f"invented-{number}") for number in range(16))
    cases = tuple(case(f"invented-{number}", questions=questions) for number in range(32))
    responses = {sample.id: response(**{item.id: "2" for item in questions}) for sample in cases}
    result = metrics.score_cases(cases, responses)
    assert result["overall"]["counts"]["cases"] == 32
    assert result["overall"]["counts"]["questions"] == 512
    assert result["overall"]["counts"]["correct_answers"] == 512


def test_long_but_bounded_integer_strings_do_not_require_numeric_conversion():
    answer = "9" * 512
    cases = (case(questions=(question(expected=answer),)),)
    result = metrics.score_cases(cases, {"invented-case": response(**{"invented-count": answer})})
    assert result["overall"]["counts"]["correct_answers"] == 1


@pytest.mark.parametrize(
    "responses",
    [None, [], (), {"unknown-case": []}, {1: []}, {"invented-case": [], "unknown-case": []}],
)
def test_invalid_response_manifest_or_unknown_case_is_a_caller_error(responses):
    with pytest.raises(metrics.MetricsError):
        metrics.score_cases((case(),), responses)


def test_specifications_are_frozen_and_scoring_does_not_mutate_inputs_or_reuse_outputs():
    spec = question()
    sample = case()
    with pytest.raises(FrozenInstanceError):
        spec.expected = "3"
    with pytest.raises(FrozenInstanceError):
        sample.split = "reserved-evaluation"
    cases = (sample,)
    responses = {"invented-case": response(**{"invented-count": "2"})}
    before_cases = copy.deepcopy(cases)
    before_responses = copy.deepcopy(responses)
    result = metrics.score_cases(cases, responses)
    assert cases == before_cases
    assert responses == before_responses
    result["overall"]["counts"]["correct_answers"] = 123
    result["cases"].clear()
    fresh = metrics.score_cases(cases, responses)
    assert fresh["overall"]["counts"]["correct_answers"] == 1
    assert len(fresh["cases"]) == 1


def test_math_never_reads_candidate_files_calls_checkers_or_starts_processes(monkeypatch):
    cases = (case(),)
    responses = {"invented-case": response(**{"invented-count": "2"})}

    def forbidden(*args, **kwargs):
        pytest.fail("Synthetic metric math must not perform I/O or inspect candidate references")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(io, "open", forbidden)
        guard.setattr(Path, "open", forbidden)
        guard.setattr(Path, "read_text", forbidden)
        guard.setattr(Path, "read_bytes", forbidden)
        guard.setattr(checker, "public_inputs", forbidden)
        guard.setattr(checker, "check_candidate", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        result = metrics.score_cases(cases, responses)
    assert result["overall"]["counts"]["correct_answers"] == 1
