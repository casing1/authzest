"""Candidate-independent metric arithmetic for synthetic unit tests, not a benchmark.

No file loader, provider contract, scanner, CLI or execution path is supplied. Callers
provide explicit evaluator-only specs and normalized answer records; this helper cannot
establish label approval, provenance, semantic support or a completed model trial.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FAMILIES = ("declaration", "policy-intent", "runtime-assurance")
SPLITS = ("development", "reserved-evaluation")
FORMATS = ("integer", "sorted-csv", "boolean", "policy", "unknown-or-boolean")
MAX_CASES = 32
MAX_QUESTIONS = 16
MAX_ANSWER_CHARS = 512


class MetricsError(ValueError):
    """Invalid evaluator specifications or response manifest, not an incorrect answer."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MetricsError(message)


def _slug(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,79}", value) is not None


def _answer(value: object, answer_format: str) -> bool:
    if value is None:
        return True
    if (
        type(value) is not str
        or len(value) > MAX_ANSWER_CHARS
        or not all(character.isprintable() for character in value)
    ):
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    if answer_format == "integer":
        return re.fullmatch(r"0|[1-9][0-9]*", value) is not None
    if answer_format in ("boolean", "unknown-or-boolean"):
        return value in ("true", "false")
    if answer_format == "policy":
        return value in ("public", "restricted", "mixed")
    parts = value.split(",") if value else []
    return parts == sorted(set(parts)) and all(part and part == part.strip() for part in parts)


@dataclass(frozen=True, slots=True)
class QuestionSpec:
    """Evaluator-only reference; constructing it is not reference review or approval."""

    id: str
    family: str
    answer_format: str
    expected: str | None

    def __post_init__(self) -> None:
        _require(_slug(self.id), "invalid question id")
        _require(type(self.family) is str and self.family in FAMILIES, "invalid question family")
        _require(
            type(self.answer_format) is str and self.answer_format in FORMATS,
            "invalid answer format",
        )
        _require(_answer(self.expected, self.answer_format), "invalid reference answer")


@dataclass(frozen=True, slots=True)
class CaseSpec:
    """One planned scenario; the plan, not successful responses, fixes denominators."""

    id: str
    split: str
    questions: tuple[QuestionSpec, ...]

    def __post_init__(self) -> None:
        _require(_slug(self.id), "invalid case id")
        _require(type(self.split) is str and self.split in SPLITS, "invalid split")
        _require(
            type(self.questions) is tuple and 1 <= len(self.questions) <= MAX_QUESTIONS,
            "invalid question collection",
        )
        for question in self.questions:
            _require(type(question) is QuestionSpec, "invalid question specification")
            question.__post_init__()
        _require(
            len({question.id for question in self.questions}) == len(self.questions),
            "duplicate question id",
        )


def ratio(numerator: int, denominator: int) -> dict:
    """A fixed denominator of zero is not applicable, never perfect accuracy."""
    _require(
        type(numerator) is int and type(denominator) is int and 0 <= numerator <= denominator,
        "invalid ratio counts",
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


_COUNT_KEYS = (
    "cases",
    "invalid_responses",
    "missing_responses",
    "questions",
    "answerable",
    "required_unknown",
    "answered",
    "correct_answers",
    "correct_unknowns",
    "abstentions",
    "false_abstentions",
    "false_certainties",
    "invalid_questions",
)


def _empty_counts() -> dict[str, int]:
    return dict.fromkeys(_COUNT_KEYS, 0)


def _add(destination: dict, source: dict) -> None:
    for key in _COUNT_KEYS:
        destination[key] += source[key]


def _group(counts: dict) -> dict:
    return {
        "counts": counts,
        "metrics": {
            "answered_accuracy": ratio(counts["correct_answers"], counts["answered"]),
            "task_coverage": ratio(counts["answered"], counts["questions"]),
            "correct_answer_yield": ratio(counts["correct_answers"], counts["questions"]),
            "answerable_yield": ratio(counts["correct_answers"], counts["answerable"]),
            "required_unknown_handling": ratio(
                counts["correct_unknowns"], counts["required_unknown"]
            ),
            "false_abstention": ratio(counts["false_abstentions"], counts["answerable"]),
            "false_certainty": ratio(counts["false_certainties"], counts["required_unknown"]),
            "invalid_responses": ratio(counts["invalid_responses"], counts["cases"]),
        },
    }


def _response(case: CaseSpec, response: object) -> tuple[dict, str | None]:
    if response is None:
        return {}, "missing-response"
    if type(response) is not list:
        return {}, "invalid-response-shape"
    if len(response) != len(case.questions):
        return {}, "question-set-mismatch"
    questions = {question.id: question for question in case.questions}
    answers = {}
    for item in response:
        if (
            type(item) is not dict
            or not all(type(key) is str for key in item)
            or set(item) != {"question_id", "answer"}
        ):
            return {}, "invalid-response-shape"
        question_id = item["question_id"]
        if type(question_id) is not str or question_id not in questions or question_id in answers:
            return {}, "question-set-mismatch"
        if not _answer(item["answer"], questions[question_id].answer_format):
            return {}, "invalid-answer"
        answers[question_id] = item["answer"]
    return answers, None


def _outcome(question: QuestionSpec, answers: dict, valid: bool) -> str:
    if not valid:
        return "invalid-response"
    actual = answers[question.id]
    if actual is None:
        return "correct-unknown" if question.expected is None else "false-abstention"
    if question.expected is None:
        return "false-certainty"
    return "correct-answer" if actual == question.expected else "wrong-answer"


def _counts(questions: tuple, outcomes: dict, *, valid: bool, missing: bool) -> dict:
    counts = _empty_counts()
    if not questions:
        return counts
    counts["cases"] = 1
    counts["invalid_responses"] = int(not valid)
    counts["missing_responses"] = int(missing)
    counts["questions"] = len(questions)
    counts["answerable"] = sum(question.expected is not None for question in questions)
    counts["required_unknown"] = len(questions) - counts["answerable"]
    counts["invalid_questions"] = 0 if valid else len(questions)
    for question in questions:
        outcome = outcomes[question.id]
        counts["answered"] += outcome in ("correct-answer", "wrong-answer", "false-certainty")
        counts["correct_answers"] += outcome == "correct-answer"
        counts["correct_unknowns"] += outcome == "correct-unknown"
        counts["abstentions"] += outcome in ("correct-unknown", "false-abstention")
        counts["false_abstentions"] += outcome == "false-abstention"
        counts["false_certainties"] += outcome == "false-certainty"
    return counts


def score_cases(cases: tuple[CaseSpec, ...], responses: dict[str, object]) -> dict:
    """Calculate synthetic-test metrics without loading a corpus or approving labels.

    Each response is a complete list of exactly {question_id, answer} records, not a
    provider response schema. None or an absent case is a missing response. Bad records
    invalidate the whole scenario; its planned questions remain in every denominator.
    Unknown case IDs are manifest errors, not silently discarded extra trials.
    """
    _require(type(cases) is tuple and 1 <= len(cases) <= MAX_CASES, "invalid case collection")
    for case in cases:
        _require(type(case) is CaseSpec, "invalid case specification")
        case.__post_init__()
    case_ids = {case.id for case in cases}
    _require(len(case_ids) == len(cases), "duplicate case id")
    _require(
        type(responses) is dict
        and len(responses) <= len(cases)
        and all(type(key) is str and key in case_ids for key in responses),
        "invalid response manifest",
    )
    overall = _empty_counts()
    families = {family: _empty_counts() for family in FAMILIES}
    splits = {split: _empty_counts() for split in SPLITS}
    results = []
    for case in cases:
        response = responses.get(case.id)
        answers, error = _response(case, response)
        valid, missing = error is None, response is None
        outcomes = {question.id: _outcome(question, answers, valid) for question in case.questions}
        counts = _counts(case.questions, outcomes, valid=valid, missing=missing)
        _add(overall, counts)
        _add(splits[case.split], counts)
        for family in FAMILIES:
            selected = tuple(question for question in case.questions if question.family == family)
            _add(families[family], _counts(selected, outcomes, valid=valid, missing=missing))
        results.append(
            {
                "case_id": case.id,
                "split": case.split,
                "response_valid": valid,
                "error": error,
                **_group(counts),
                "questions": [
                    {
                        "question_id": question.id,
                        "family": question.family,
                        "outcome": outcomes[question.id],
                    }
                    for question in case.questions
                ],
            }
        )
    return {
        "kind": "offline-metric-calculation",
        "schema_version": "0.1",
        "calculation_only": True,
        "reference_review_status": "not-assessed",
        "benchmark_ready": False,
        "overall": _group(overall),
        "by_family": {key: _group(value) for key, value in families.items()},
        "by_split": {key: _group(value) for key, value in splits.items()},
        "cases": results,
        "unmeasured": dict.fromkeys(
            (
                "citation_id_validity",
                "citation_semantic_support",
                "unsupported_claims",
                "human_review_seconds",
                "provider_usage",
                "latency_ms",
                "repeat_variation",
                "workflow_outcomes",
            )
        ),
    }
