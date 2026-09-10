import asyncio
import json
import socket
import subprocess
from pathlib import Path

import pytest
from scripts.evaluate_offline import (
    DATASET_ROOT,
    corpus_identity,
    evaluate,
    prepare_case,
    static_answers,
)

from authzest.codex.contracts import ContractError, ValidatedResponse, canonical, validate_response
from authzest.codex.evaluation import score_response, summarize_trials
from authzest.codex.mock import MockCodexAdapter, scripted_response

CORPUS_SHA256 = "63483449c430a4592c49cdb3e17fd600625df7bc999761bc5e1fab761006505d"


def public_case():
    return json.loads((DATASET_ROOT / "dataset.json").read_text(encoding="utf-8"))["cases"][0]


def test_frozen_corpus_and_expected_static_facts():
    assert corpus_identity() == CORPUS_SHA256
    dataset = json.loads((DATASET_ROOT / "dataset.json").read_text(encoding="utf-8"))
    labels = json.loads((DATASET_ROOT / "labels.json").read_text(encoding="utf-8"))
    assert labels["authorship"] == "assistant-authored reference labels; not human-authored"
    assert "approved-by-maintainer" in labels["review_status"]
    assert [case["split"] for case in dataset["cases"]].count("held-out") == 3
    for case in dataset["cases"]:
        report, request = prepare_case(case, "evidence-plus-model")
        answers = static_answers(report, request)
        for key, value in answers.items():
            if key != "policy":
                assert value == labels["cases"][case["id"]][key]
        if case["id"] == "repeated-mount":
            assert (
                len({route.to_dict(report.root)["registration_id"] for route in report.routes}) == 2
            )
        if case["id"] == "dynamic-prefix":
            assert report.analysis_status == "partial"


def test_modes_share_exact_source_policy_questions_and_config():
    _, direct = prepare_case(public_case(), "model-only")
    _, assisted = prepare_case(public_case(), "evidence-plus-model")
    left, right = direct.to_dict(), assisted.to_dict()
    assert left["source_identity"] == right["source_identity"]
    assert left["questions"] == right["questions"]
    assert left["config"] == right["config"]
    assert left["evidence"] == [
        item for item in right["evidence"] if item["kind"] in ("source", "policy")
    ]
    assert "expected" not in canonical(left) and "review_status" not in canonical(right)


def test_full_evaluation_is_offline_and_labels_load_after_all_adapter_calls(monkeypatch):
    calls = []
    original_read = Path.read_text
    original_analyze = MockCodexAdapter.analyze

    def read(path, *args, **kwargs):
        if path.name == "labels.json":
            assert len(calls) == 24
        return original_read(path, *args, **kwargs)

    async def analyze(self, request):
        calls.append(request)
        assert "authorship" not in request.payload_json
        assert "mock_answers" not in request.payload_json
        return await original_analyze(self, request)

    def forbidden(*args, **kwargs):
        pytest.fail("Offline evaluation must not use a subprocess or network")

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(MockCodexAdapter, "analyze", analyze)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = asyncio.run(evaluate())
    assert result["kind"] == "offline-scripted-comparison"
    assert result["live_provider_calls"] == 0 and len(result["trials"]) == 36
    assert result["corpus_sha256"] == CORPUS_SHA256
    for mode, summary in result["summary"].items():
        assert summary["trials"] == 12
        assert summary["invalid_responses"] == 0
        assert summary["repeated_output_change"]["value"] == 0
        assert summary["unsupported_claims"] is None
        assert summary["human_review_seconds"] is None
        assert summary["human_scored_trials"] == 0
        if mode == "static-only":
            assert summary["task_coverage"]["value"] == 0.4
            assert summary["policy_agreement"]["value"] is None
    assert all(trial["provenance"]["usage"] is None for trial in result["trials"])


def test_wrong_answer_and_abstention_are_not_success():
    _, request = prepare_case(public_case(), "model-only")
    expected = {"route-count": "1", "policy": "public"}
    raw = scripted_response(request, {"route-count": "9", "policy": None})
    scores = score_response(expected, request, validate_response(raw, request))
    assert scores["task_accuracy"] == {"numerator": 0, "denominator": 1, "value": 0.0}
    assert scores["task_coverage"]["value"] == 0.5
    assert scores["unknown_handling"]["value"] is None
    abstained = scripted_response(request, dict.fromkeys(expected))
    scores = score_response(expected, request, validate_response(abstained, request))
    assert scores["task_accuracy"]["value"] is None
    assert scores["task_coverage"]["value"] == 0


def test_invalid_citations_have_denominators_but_no_task_credit():
    _, request = prepare_case(public_case(), "model-only")
    raw = json.loads(scripted_response(request, {"route-count": "1", "policy": "public"}))
    raw["answers"][0]["evidence_ids"] = ["ev-missing"]
    scores = score_response(
        {"route-count": "1", "policy": "public"}, request, None, raw=canonical(raw)
    )
    assert scores["source_reference_validity"]["value"] == 0.5
    assert scores["task_coverage"]["value"] == 0
    assert scores["contract_valid"] is False


def test_schema_validation_does_not_prove_prose_and_manual_scores_are_explicit():
    _, request = prepare_case(public_case(), "model-only")
    expected = {"route-count": "1", "policy": "public"}
    raw = json.loads(scripted_response(request, expected))
    raw["answers"][0]["explanation"] = "Unjustified certainty in free-form prose."
    response = validate_response(canonical(raw), request)
    scores = score_response(
        expected, request, response, unsupported_claims=1, human_review_seconds=12.5
    )
    assert scores["unsupported_claims"] == 1 and scores["human_review_seconds"] == 12.5
    summary = summarize_trials([{"mode": "model-only", "case_id": "public", "scores": scores}])
    assert summary["model-only"]["unsupported_claims"] == 1
    assert summary["model-only"]["human_review_seconds"] == 12.5
    assert summary["model-only"]["repeated_output_change"]["value"] is None


def test_repeated_variation_and_missing_human_measurements():
    _, request = prepare_case(public_case(), "model-only")
    expected = {"route-count": "1", "policy": "public"}
    trials = []
    for answer in ("1", "2", "1"):
        raw = scripted_response(request, {"route-count": answer, "policy": "public"})
        scores = score_response(expected, request, validate_response(raw, request))
        trials.append({"mode": "model-only", "case_id": "public", "scores": scores})
    summary = summarize_trials(trials)["model-only"]
    assert summary["repeated_output_change"]["value"] == 0.5
    assert summary["unsupported_claims"] is None


def test_human_can_flag_misleading_prose_even_when_answer_abstains():
    _, request = prepare_case(public_case(), "model-only")
    expected = {"route-count": "1", "policy": "public"}
    raw = scripted_response(request, dict.fromkeys(expected))
    scores = score_response(
        expected, request, validate_response(raw, request), unsupported_claims=2
    )
    assert scores["unsupported_claims"] == 2


def test_evaluator_revalidates_response_instead_of_trusting_dataclass():
    _, request = prepare_case(public_case(), "model-only")
    with pytest.raises(ContractError):
        score_response({"route-count": "1", "policy": "public"}, request, ValidatedResponse("{}"))


@pytest.mark.parametrize("count", [0, 1, 11, True])
def test_invalid_repeat_count(count):
    with pytest.raises(ValueError):
        asyncio.run(evaluate(count))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"unsupported_claims": True},
        {"unsupported_claims": 9},
        {"human_review_seconds": -1},
        {"human_review_seconds": float("nan")},
    ],
)
def test_invalid_human_measurements(kwargs):
    _, request = prepare_case(public_case(), "model-only")
    with pytest.raises(ValueError):
        score_response({"route-count": "1", "policy": "public"}, request, None, **kwargs)
