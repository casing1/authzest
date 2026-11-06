"""Pure, bounded evaluation response contract, separate from product schemas.

One complete JSON object supplies only canonical answers. This contract does not
provide citations, explanations, provider calls, files, runners or target execution.
An invalid scenario never becomes a partial answer or a valid unknown response.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

SCHEMA_VERSION = "0.1"
KIND = "evaluation-comparison-response"
FORMATS = ("integer", "sorted-csv", "boolean", "policy", "unknown-or-boolean")
MAX_QUESTIONS = 6
MAX_ANSWER_CHARS = 512
MAX_RAW_BYTES = 64 * 1024
MAX_JSON_DEPTH = 16
ERROR_CODES = frozenset(
    {
        "missing-response",
        "invalid-type",
        "response-too-large",
        "invalid-utf8",
        "depth-limit",
        "duplicate-key",
        "non-finite-json",
        "invalid-json",
        "invalid-response-fields",
        "unsupported-schema-version",
        "invalid-response-kind",
        "task-id-mismatch",
        "request-id-mismatch",
        "invalid-answer-set",
        "invalid-answer-fields",
        "question-set-mismatch",
        "invalid-answer",
    }
)


class ContractError(ValueError):
    """An evaluator-owned response specification is invalid, not a bad response."""


class _DecodeError(ValueError):
    """A closed diagnostic produced by strict JSON parsing."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _slug(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,79}", value) is not None


@dataclass(frozen=True, slots=True)
class Question:
    """Public question identity and answer syntax, never a reference value."""

    id: str
    answer_format: str

    def __post_init__(self) -> None:
        _require(_slug(self.id), "invalid question id")
        _require(
            type(self.answer_format) is str and self.answer_format in FORMATS,
            "invalid answer format",
        )


@dataclass(frozen=True, slots=True)
class ResponseSpec:
    """One complete task; its fixed questions are not inferred from a response."""

    task_id: str
    request_id: str
    questions: tuple[Question, ...]

    def __post_init__(self) -> None:
        _require(
            type(self.task_id) is str
            and re.fullmatch(r"task-[0-9a-f]{64}", self.task_id) is not None,
            "invalid task id",
        )
        _require(
            type(self.request_id) is str
            and re.fullmatch(r"request-[0-9a-f]{64}", self.request_id) is not None,
            "invalid request id",
        )
        _require(
            type(self.questions) is tuple and 1 <= len(self.questions) <= MAX_QUESTIONS,
            "invalid question collection",
        )
        for question in self.questions:
            _require(type(question) is Question, "invalid question specification")
            question.__post_init__()
        _require(
            len({question.id for question in self.questions}) == len(self.questions),
            "duplicate question id",
        )


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


def _invalid(code: str) -> dict:
    return {"status": "invalid", "error": code, "records": None}


def _depth_bounded(raw: str) -> bool:
    depth = 0
    quoted = escaped = False
    for character in raw:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return False
        elif character in "]}":
            depth -= 1
    return True


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DecodeError("duplicate-key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise _DecodeError("non-finite-json")


def _float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise _DecodeError("non-finite-json")
    return result


def decode_response(spec: ResponseSpec, raw: str | None) -> dict:
    """Validate a whole JSON response and return ordered normalized answer records.

    Only an absent raw response is missing. Invalid or missing responses have no
    records; callers preserve this status rather than coercing it to abstention.
    Canonical string values are copied unchanged, never stripped, sorted or coerced.
    """
    _require(type(spec) is ResponseSpec, "invalid response specification")
    spec.__post_init__()
    if raw is None:
        return {"status": "missing", "error": "missing-response", "records": None}
    if type(raw) is not str:
        return _invalid("invalid-type")
    if len(raw) > MAX_RAW_BYTES:
        return _invalid("response-too-large")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError:
        return _invalid("invalid-utf8")
    if len(encoded) > MAX_RAW_BYTES:
        return _invalid("response-too-large")
    if not _depth_bounded(raw):
        return _invalid("depth-limit")
    try:
        response = json.loads(
            raw, object_pairs_hook=_unique, parse_constant=_constant, parse_float=_float
        )
    except _DecodeError as error:
        return _invalid(str(error))
    except (ValueError, RecursionError):
        return _invalid("invalid-json")
    if type(response) is not dict or set(response) != {
        "schema_version",
        "kind",
        "task_id",
        "request_id",
        "answers",
    }:
        return _invalid("invalid-response-fields")
    if response["schema_version"] != SCHEMA_VERSION:
        return _invalid("unsupported-schema-version")
    if response["kind"] != KIND:
        return _invalid("invalid-response-kind")
    if response["task_id"] != spec.task_id:
        return _invalid("task-id-mismatch")
    if response["request_id"] != spec.request_id:
        return _invalid("request-id-mismatch")
    answers = response["answers"]
    if type(answers) is not list:
        return _invalid("invalid-answer-set")
    if len(answers) != len(spec.questions):
        return _invalid("question-set-mismatch")
    questions = {question.id: question for question in spec.questions}
    validated = {}
    for answer in answers:
        if type(answer) is not dict or set(answer) != {"question_id", "answer"}:
            return _invalid("invalid-answer-fields")
        question_id = answer["question_id"]
        if type(question_id) is not str or question_id not in questions or question_id in validated:
            return _invalid("question-set-mismatch")
        value = answer["answer"]
        if not _answer(value, questions[question_id].answer_format):
            return _invalid("invalid-answer")
        validated[question_id] = value
    return {
        "status": "valid",
        "error": None,
        "records": [
            {"question_id": question.id, "answer": validated[question.id]}
            for question in spec.questions
        ],
    }
