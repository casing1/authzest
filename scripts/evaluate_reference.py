"""Check fixed reference values or calculate an explicitly synthetic unknown control.

This source-only development tool reads owned, fixed files as data. It never runs
embedded target source, calls a provider or establishes a live benchmark result.
The source-byte integrity checks assume a trusted process and stable owned checkout,
not runtime/memory authentication, adversarial filesystem changes or an OS sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path

from scripts import check_evaluation_candidate as candidate
from scripts import evaluation_metrics as metrics

ROOT = Path(__file__).resolve().parents[1]
METRICS_ROOT = Path(metrics.__file__).resolve().parents[1]
REFERENCE = "tests/fixtures/evaluation_reference/v1"
MAX_DOCUMENT_BYTES = 256 * 1024
TASK_SHA256 = "99ffd0a47f9f26c041f39669c29e8d0939aa8bdbb51861c2f18de81e34860094"
REFERENCE_SHA256 = "acc988e3586bd8841fc04865f061e7bdcfab203596df839a00343595f35db45b"
MANIFEST_SHA256 = "f963418e5d6e646523a6e7c966a711f0153ba5691b792e9f8fb6b9c63bae63dd"
METRICS_SHA256 = "bbe440f9286b0333824d5312b032f2cdd0877a549f3917caea1e994a50fb3a44"
CANDIDATE_SHA256 = "1a84d57c0ea80d9d4f5bf53c1a1676c08a8a66f8902354fb2424285b12bae938"


class ReferenceError(ValueError):
    """The fixed reference snapshot or its bindings do not match version v1."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReferenceError(message)


def _root(root: Path) -> Path:
    root = root.absolute()
    try:
        mode = root.lstat().st_mode
    except OSError as error:
        raise ReferenceError("cannot read reference root") from error
    _require(stat.S_ISDIR(mode) and not stat.S_ISLNK(mode), "non-directory reference root")
    return root


def _read(root: Path, relative: str) -> bytes:
    current = root
    try:
        parts = relative.split("/")
        for index, part in enumerate(parts):
            current /= part
            mode = current.lstat().st_mode
            _require(not stat.S_ISLNK(mode), "linked reference path")
            kind = stat.S_ISREG if index == len(parts) - 1 else stat.S_ISDIR
            _require(kind(mode), "non-regular reference path")
        with current.open("rb") as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
    except OSError as error:
        raise ReferenceError(f"cannot read fixed reference file: {relative}") from error
    _require(len(raw) <= MAX_DOCUMENT_BYTES, "reference document exceeds byte limit")
    return raw


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ReferenceError("non-finite JSON constant")


def _load(root: Path, filename: str, expected: str) -> dict:
    raw = _read(root, f"{REFERENCE}/{filename}")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ReferenceError(f"invalid reference JSON: {filename}") from error
    _require(hashlib.sha256(raw).hexdigest() == expected, f"fixed {filename} hash mismatch")
    _require(type(value) is dict, f"invalid {filename} object")
    return value


def reference_inputs(root: Path) -> list[dict]:
    """Project only pinned task data; do not open references, manifest or arithmetic."""
    tasks = _load(_root(root), "tasks.json", TASK_SHA256)
    try:
        return candidate.candidate_inputs(tasks)
    except candidate.CandidateError as error:
        raise ReferenceError(str(error)) from error


def _manifest(manifest: dict) -> None:
    expected = {
        "schema_version": "0.1",
        "kind": "evaluation-reference-freeze",
        "version": "v1",
        "status": "reference-values-fixed",
        "source_revision": "ee1b988a11d8ce561f6e155451ef6e40c6a5c318",
        "candidate_sha256": CANDIDATE_SHA256,
        "authorship": "assistant",
        "task_sha256": TASK_SHA256,
        "reference_sha256": REFERENCE_SHA256,
        "metrics_sha256": METRICS_SHA256,
        "metrics_schema_version": "0.1",
        "counts": {
            "cases": 7,
            "questions": 21,
            "answerable": 14,
            "required_unknown": 7,
            "development_cases": 3,
            "reserved_cases": 4,
        },
        "decision": {
            "value": "accepted-current-reference-values",
            "source": "direct-user-chat-confirmation",
            "recorded_by": "assistant",
            "recorded_date": "2026-11-06",
            "confirmation": "current-21-reference-values-confirmed",
            "scope": "current-21-reference-values",
            "identity_assurance": "not-authenticated-by-this-tool",
            "inspection_attestation": "not-collected",
            "independent_review_attested": False,
        },
        "live_benchmark_ready": False,
        "live_configuration_frozen": False,
        "live_execution_authorized": False,
    }
    _require(manifest == expected, "fixed manifest semantics mismatch")


def load_reference(root: Path) -> dict:
    """Return evaluator-only snapshot data and a separate fixed-value preflight.

    Historical proposal bytes retain pending-review metadata. The later manifest
    records a user decision, not authenticated identity, inspection, human
    authorship or independent review. No prompt/model/configuration is frozen.
    """
    root = _root(root)
    tasks = _load(root, "tasks.json", TASK_SHA256)
    try:
        candidate.candidate_inputs(tasks)
        references = _load(root, "references.json", REFERENCE_SHA256)
        archived = candidate.validate_candidate_documents(tasks, references)
    except candidate.CandidateError as error:
        raise ReferenceError(str(error)) from error
    manifest = _load(root, "manifest.json", MANIFEST_SHA256)
    _manifest(manifest)
    _require(archived["candidate_sha256"] == CANDIDATE_SHA256, "candidate identity mismatch")
    # Never import Python from a caller-supplied root. Both the selected recorded
    # copy and the normally imported, owned arithmetic source must match v1.
    for arithmetic_root in (root, _root(METRICS_ROOT)):
        arithmetic = _read(arithmetic_root, "scripts/evaluation_metrics.py")
        _require(
            hashlib.sha256(arithmetic).hexdigest() == METRICS_SHA256,
            "fixed metrics hash mismatch",
        )
    preflight = {
        "kind": "evaluation-reference-preflight",
        "schema_version": "0.1",
        "version": "v1",
        "status": "reference-values-fixed",
        "integrity": "matched",
        "candidate_sha256": CANDIDATE_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "authorship": "assistant",
        "decision": manifest["decision"],
        "archived_proposal_status": tasks["status"],
        "archived_reference_review_status": references["review_status"],
        "case_count": archived["case_count"],
        "question_count": archived["question_count"],
        "live_benchmark_ready": False,
        "live_configuration_frozen": False,
        "live_execution_authorized": False,
        "provider_calls_by_this_tool": 0,
        "target_execution": "not-run",
        "scoring_status": "not-run",
    }
    return {"preflight": preflight, "tasks": tasks, "references": references, "manifest": manifest}


def score_reference(root: Path, responses: dict[str, object]) -> dict:
    """Score caller-normalized records; no provider response parsing or model trial."""
    snapshot = load_reference(root)
    tasks, references = snapshot["tasks"], snapshot["references"]
    specs = tuple(
        metrics.CaseSpec(
            task["id"],
            task["proposed_split"],
            tuple(
                metrics.QuestionSpec(
                    question["id"],
                    question["family"],
                    question["answer_format"],
                    answer["expected"],
                )
                for question, answer in zip(task["questions"], reference["answers"], strict=True)
            ),
        )
        for task, reference in zip(tasks["cases"], references["cases"], strict=True)
    )
    try:
        calculation = metrics.score_cases(specs, responses)
    except metrics.MetricsError as error:
        raise ReferenceError(str(error)) from error
    return {
        **snapshot["preflight"],
        "kind": "evaluation-reference-calculation",
        "scoring_status": "calculated-offline",
        "response_origin": "caller-provided-normalized-records",
        "calculation": calculation,
    }


def all_unknown_control(root: Path) -> dict:
    """Stage null answers from task-only input before opening evaluator references.

    This invented arithmetic control is neither a static baseline nor evidence of
    model quality, model comparison or an actual model response.
    """
    responses = {
        case["case_id"]: [
            {"question_id": question["id"], "answer": None} for question in case["questions"]
        ]
        for case in reference_inputs(root)
    }
    return {
        **score_reference(root, responses),
        "response_origin": "synthetic-all-unknown-control",
        "model_quality_measured": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    parser.add_argument(
        "--control", action="store_true", help="calculate synthetic all-unknown control"
    )
    args = parser.parse_args(argv)
    try:
        result = all_unknown_control(ROOT) if args.control else load_reference(ROOT)["preflight"]
    except ReferenceError as error:
        failure = {
            "kind": "evaluation-reference-preflight",
            "status": "invalid",
            "error": str(error),
            "live_benchmark_ready": False,
            "provider_calls_by_this_tool": 0,
            "target_execution": "not-run",
        }
        print(json.dumps(failure) if args.json else str(error))
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    else:
        print(
            f"Fixed references v1: {result['case_count']} cases, "
            f"{result['question_count']} questions."
        )
        print(
            "Assistant-authored values fixed by recorded user decision; live benchmark NOT READY."
        )
        print("No provider calls or target execution. Archived proposal metadata is unchanged.")
        if args.control:
            overall = result["calculation"]["overall"]
            print("SYNTHETIC ALL-UNKNOWN CONTROL: not a static baseline or model-quality result.")
            for name in (
                "task_coverage",
                "answered_accuracy",
                "required_unknown_handling",
                "false_abstention",
                "invalid_responses",
            ):
                ratio = overall["metrics"][name]
                print(f"  {name}: {ratio['numerator']}/{ratio['denominator']} ({ratio['value']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
