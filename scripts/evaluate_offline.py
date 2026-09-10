"""Run the frozen owned fixture comparison with scripted mocks, never live providers."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from authzest.codex.contracts import (
    AdapterConfig,
    CodexAnalysisRequest,
    identity,
    prepare_request,
    validate_response,
)
from authzest.codex.evaluation import score_response, summarize_trials
from authzest.codex.mock import MockCodexAdapter, scripted_response
from authzest.models import ScanReport
from authzest.runner import ScanRunner
from authzest.runner.review import review_report

DATASET_ROOT = Path(__file__).resolve().parents[1] / "tests/fixtures/ai_evaluation/v1"


def corpus_identity() -> str:
    """Pin question/source/label/mock bytes; no timestamps, paths, or generated caches."""
    return identity(
        {
            path.relative_to(DATASET_ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(DATASET_ROOT.rglob("*"))
            if path.is_file() and path.suffix in (".py", ".json")
        }
    )


def prepare_case(case: dict[str, Any], mode: str) -> tuple[ScanReport, CodexAnalysisRequest]:
    """Only public questions, policy, source, and extracted facts enter this function."""
    case_root = DATASET_ROOT / case["id"]
    report = ScanRunner().run(case_root)
    request = prepare_request(
        report,
        registration_ids=tuple(
            route.to_dict(report.root)["registration_id"] for route in report.routes
        ),
        sources={"main.py": (case_root / "main.py").read_text(encoding="utf-8")},
        policies=tuple(case["policies"]),
        questions=tuple((question["id"], question["text"]) for question in case["questions"]),
        mode=mode,
        config=AdapterConfig(),
    )
    return report, request


def static_answers(report: ScanReport, request: CodexAnalysisRequest) -> dict[str, str | None]:
    """Source facts only. Policy interpretation and authorization verdicts abstain."""
    facts = {
        "route-count": str(len(report.routes)),
        "dependency-count": str(sum(len(route.effective_dependencies) for route in report.routes)),
        "declared-scopes": ",".join(
            sorted(
                {
                    scope
                    for route in report.routes
                    for dep in route.effective_dependencies
                    for scope in dep.scopes or ()
                }
            )
        ),
    }
    return {
        question["id"]: facts.get(question["id"]) or None
        for question in request.to_dict()["questions"]
    }


async def evaluate(repeats: int = 2) -> dict[str, Any]:
    if type(repeats) is not int or not 2 <= repeats <= 10:
        raise ValueError("Use 2 to 10 offline repetitions")
    dataset = json.loads((DATASET_ROOT / "dataset.json").read_text(encoding="utf-8"))
    scripts = json.loads((DATASET_ROOT / "mock_answers.json").read_text(encoding="utf-8"))
    trials = []
    # Stage all input and outputs before loading evaluator-only labels.
    for case in dataset["cases"]:
        for mode in ("static-only", "model-only", "evidence-plus-model"):
            report, request = prepare_case(
                case, "evidence-plus-model" if mode == "static-only" else mode
            )
            for repeat in range(repeats):
                if mode == "static-only":
                    raw = scripted_response(request, static_answers(report, request))
                    response = validate_response(raw, request)
                    provenance = {
                        "provider": None,
                        "model": None,
                        "usage": None,
                        "latency_ms": None,
                        "source_identity": request.to_dict()["source_identity"],
                    }
                else:
                    raw = scripted_response(request, scripts["cases"][case["id"]][mode])
                    result = await review_report(
                        report,
                        request,
                        approved_request_id=request.request_id,
                        adapter=MockCodexAdapter(raw),
                    )
                    response, provenance = result.response, result.provenance
                trials.append(
                    {
                        "case_id": case["id"],
                        "split": case["split"],
                        "mode": mode,
                        "repeat": repeat,
                        "request": request,
                        "response": response,
                        "raw": raw,
                        "provenance": provenance,
                    }
                )
    labels = json.loads((DATASET_ROOT / "labels.json").read_text(encoding="utf-8"))
    results = []
    for trial in trials:
        scores = score_response(
            labels["cases"][trial["case_id"]], trial["request"], trial["response"], raw=trial["raw"]
        )
        results.append(
            {
                key: value
                for key, value in trial.items()
                if key not in ("request", "response", "raw")
            }
            | {"scores": scores}
        )
    return {
        "kind": "offline-scripted-comparison",
        "live_provider_calls": 0,
        "dataset_version": dataset["version"],
        "corpus_sha256": corpus_identity(),
        "label_authorship": labels["authorship"],
        "label_review_status": labels["review_status"],
        "limitations": [
            "Mock scores validate the harness, not AI quality or advantage.",
            "Citation existence does not prove semantic support.",
            "Unsupported claims and human review time are unmeasured (null).",
            "Held-out cases are reserved for later prompt evaluation, not secret.",
            "No live model comparison or model-upgrade adoption is established.",
        ],
        "summary": summarize_trials(results),
        "trials": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=2, choices=range(2, 11))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(evaluate(args.repeats)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
