"""Evaluator-only scoring. Expected labels must never enter adapter requests."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    decode,
    validate_response,
)


def ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def score_response(
    expected: dict[str, str | None],
    request: CodexAnalysisRequest,
    response: ValidatedResponse | None,
    *,
    raw: str | None = None,
    unsupported_claims: int | None = None,
    human_review_seconds: float | None = None,
) -> dict[str, Any]:
    """Exact task labels and structural citations; semantic support needs human review.

    Invalid responses earn no task credit. Unknown is reported separately from accuracy,
    so a static baseline cannot achieve perfect accuracy merely by abstaining.
    """
    payload = request.to_dict()
    if set(expected) != {item["id"] for item in payload["questions"]}:
        raise ValueError("Evaluation labels must match the question set")
    if response is not None:
        response = validate_response(response.payload_json, request)
    answers = response.to_dict()["answers"] if response else []
    answered = [answer for answer in answers if answer["status"] == "hypothesis"]
    correct = sum(answer["answer"] == expected[answer["question_id"]] for answer in answered)
    unknown_expected = sum(value is None for value in expected.values())
    unknown_correct = sum(
        answer["status"] == "unknown" and expected[answer["question_id"]] is None
        for answer in answers
    )
    policy_answers = [answer for answer in answered if answer["question_id"] == "policy"]
    if unsupported_claims is not None and (
        type(unsupported_claims) is not int or not 0 <= unsupported_claims <= len(answers)
    ):
        raise ValueError("Invalid human unsupported-claim count")
    if human_review_seconds is not None:
        import math

        if (
            type(human_review_seconds) not in (int, float)
            or not math.isfinite(human_review_seconds)
            or human_review_seconds < 0
        ):
            raise ValueError("Invalid measured review duration")
    citations: list[Any] = []
    if raw is not None:
        try:
            candidates = decode(raw).get("answers", [])
            if type(candidates) is list:
                for candidate in candidates:
                    if type(candidate) is dict and type(candidate.get("evidence_ids")) is list:
                        citations.extend(candidate["evidence_ids"])
        except ContractError:
            pass
    elif response:
        citations = [ref for answer in answers for ref in answer["evidence_ids"]]
    allowed = {item["id"] for item in payload["evidence"]}
    valid = sum(type(ref) is str and ref in allowed for ref in citations)
    return {
        "contract_valid": response is not None,
        "task_accuracy": ratio(correct, len(answered)),
        "task_coverage": ratio(len(answered), len(expected)),
        "unknown_handling": ratio(unknown_correct, unknown_expected),
        "abstentions": sum(answer["status"] == "unknown" for answer in answers),
        "policy_agreement": ratio(
            sum(answer["answer"] == expected["policy"] for answer in policy_answers),
            len(policy_answers),
        ),
        "source_reference_validity": ratio(valid, len(citations)),
        "unsupported_claims": unsupported_claims,
        "human_review_seconds": human_review_seconds,
        "answers": {answer["question_id"]: answer["answer"] for answer in answers},
    }


def summarize_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate denominators and repeated-output variation by mode, not model quality."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        grouped[trial["mode"]].append(trial)
    summary = {}
    for mode, members in grouped.items():
        metrics = {}
        for metric in (
            "task_accuracy",
            "task_coverage",
            "unknown_handling",
            "policy_agreement",
            "source_reference_validity",
        ):
            metrics[metric] = ratio(
                sum(item["scores"][metric]["numerator"] for item in members),
                sum(item["scores"][metric]["denominator"] for item in members),
            )
        by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in members:
            by_case[item["case_id"]].append(item["scores"]["answers"])
        comparisons = sum(max(0, len(items) - 1) for items in by_case.values())
        changed = sum(item != items[0] for items in by_case.values() for item in items[1:])
        summary[mode] = {
            **metrics,
            "trials": len(members),
            "invalid_responses": sum(not item["scores"]["contract_valid"] for item in members),
            "repeated_output_change": ratio(changed, comparisons),
            "unsupported_claims": (
                sum(item["scores"]["unsupported_claims"] for item in members)
                if all(item["scores"]["unsupported_claims"] is not None for item in members)
                else None
            ),
            "human_review_seconds": (
                sum(item["scores"]["human_review_seconds"] for item in members)
                if all(item["scores"]["human_review_seconds"] is not None for item in members)
                else None
            ),
            "human_scored_trials": sum(
                item["scores"]["unsupported_claims"] is not None for item in members
            ),
        }
    return summary
