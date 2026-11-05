"""Inspect an unapproved evaluation draft as data, never execute or benchmark it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "tests/fixtures/evaluation_candidate/draft"
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 32 * 1024
FAMILIES = {"declaration", "policy-intent", "runtime-assurance"}
FORMATS = {"integer", "sorted-csv", "boolean", "policy", "unknown-or-boolean"}


class CandidateError(ValueError):
    """Draft data, reference bindings or source ranges are invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CandidateError(message)


def _keys(value: object, keys: set[str], context: str) -> None:
    _require(type(value) is dict and set(value) == keys, f"invalid {context} fields")


def _text(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 2048
        and bool(value.strip())
        and all(character.isprintable() for character in value)
    )


def _slug(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,79}", value) is not None


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise CandidateError("non-finite JSON constant")


def _load(root: Path, filename: str) -> dict:
    current = root
    try:
        parts = f"{CANDIDATE}/{filename}".split("/")
        for index, part in enumerate(parts):
            current = current / part
            mode = current.lstat().st_mode
            _require(not stat.S_ISLNK(mode), "linked candidate path")
            expected = stat.S_ISREG if index == len(parts) - 1 else stat.S_ISDIR
            _require(expected(mode), "non-regular candidate path")
        with current.open("rb") as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
    except OSError as error:
        raise CandidateError(f"cannot read candidate {filename}") from error
    _require(len(raw) <= MAX_DOCUMENT_BYTES, "candidate document exceeds byte limit")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise CandidateError(f"invalid candidate JSON: {filename}") from error


def _identity(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sources(value: object) -> None:
    _require(type(value) is dict and 1 <= len(value) <= 4, "invalid virtual source count")
    for path, content in value.items():
        _require(
            type(path) is str
            and len(path) <= 160
            and re.fullmatch(r"(?:[A-Za-z_][A-Za-z0-9_-]*/)*[A-Za-z_][A-Za-z0-9_-]*\.py", path)
            is not None,
            "invalid virtual source path",
        )
        _require(type(content) is str and bool(content) and "\x00" not in content, "invalid source")
        try:
            _require(len(content.encode("utf-8")) <= MAX_SOURCE_BYTES, "virtual source too large")
        except UnicodeError as error:
            raise CandidateError("invalid virtual source UTF-8") from error


def _inputs(tasks: object) -> list[dict]:
    _keys(tasks, {"schema_version", "kind", "status", "authorship", "cases"}, "task document")
    _require(tasks["schema_version"] == "0.1", "unsupported draft schema")
    _require(tasks["kind"] == "evaluation-candidate-tasks", "invalid task kind")
    _require(tasks["status"] == "draft-not-frozen", "candidate cannot claim a freeze")
    _require(tasks["authorship"] == "assistant", "candidate authorship must remain explicit")
    _require(type(tasks["cases"]) is list and 1 <= len(tasks["cases"]) <= 12, "invalid case count")
    inputs = []
    ids = set()
    for case in tasks["cases"]:
        _keys(case, {"id", "proposed_split", "sources", "policies", "questions"}, "case")
        _require(_slug(case["id"]) and case["id"] not in ids, "invalid or duplicate case id")
        ids.add(case["id"])
        _require(
            type(case["proposed_split"]) is str
            and case["proposed_split"] in {"development", "reserved-evaluation"},
            "invalid proposed split",
        )
        _sources(case["sources"])
        _require(
            type(case["policies"]) is list
            and 1 <= len(case["policies"]) <= 8
            and all(_text(policy) for policy in case["policies"]),
            "invalid policies",
        )
        _require(
            type(case["questions"]) is list and 1 <= len(case["questions"]) <= 6,
            "invalid question count",
        )
        questions = set()
        for question in case["questions"]:
            _keys(question, {"id", "family", "text", "answer_format"}, "question")
            _require(
                _slug(question["id"]) and question["id"] not in questions,
                "invalid or duplicate question id",
            )
            questions.add(question["id"])
            _require(
                type(question["family"]) is str and question["family"] in FAMILIES,
                "invalid question family",
            )
            _require(_text(question["text"]), "invalid question text")
            _require(
                type(question["answer_format"]) is str and question["answer_format"] in FORMATS,
                "invalid answer format",
            )
        # Projection, not a benchmark request or authorization to share this data.
        inputs.append(
            {
                "case_id": case["id"],
                "sources": case["sources"],
                "policies": case["policies"],
                "questions": case["questions"],
            }
        )
    return inputs


def public_inputs(root: Path) -> list[dict]:
    """Read only task/source data; never open references or include proposed splits."""
    return _inputs(_load(root.resolve(), "tasks.json"))


def _answer(value: object, answer_format: str) -> bool:
    if value is None:
        return True
    if type(value) is not str or len(value) > 512 or not all(c.isprintable() for c in value):
        return False
    if answer_format == "integer":
        return re.fullmatch(r"0|[1-9][0-9]*", value) is not None
    if answer_format in {"boolean", "unknown-or-boolean"}:
        return value in {"true", "false"}
    if answer_format == "policy":
        return value in {"public", "restricted", "mixed"}
    parts = value.split(",") if value else []
    return parts == sorted(set(parts)) and all(part and part == part.strip() for part in parts)


def _references(references: object, inputs: list[dict]) -> None:
    _keys(
        references,
        {
            "schema_version",
            "kind",
            "authorship",
            "review_status",
            "reviewer",
            "review_record",
            "cases",
        },
        "reference document",
    )
    _require(references["schema_version"] == "0.1", "unsupported reference schema")
    _require(references["kind"] == "evaluation-reference-draft", "invalid reference kind")
    _require(references["authorship"] == "assistant", "reference authorship must remain explicit")
    _require(
        references["review_status"] == "pending-exact-maintainer-review"
        and references["reviewer"] is None
        and references["review_record"] is None,
        "checker cannot establish exact reference approval",
    )
    _require(
        type(references["cases"]) is list and len(references["cases"]) == len(inputs),
        "reference case set mismatch",
    )
    for case, public in zip(references["cases"], inputs, strict=True):
        _keys(case, {"id", "input_sha256", "answers"}, "reference case")
        _require(case["id"] == public["case_id"], "reference case/order mismatch")
        _require(case["input_sha256"] == _identity(public), "reference input identity mismatch")
        _require(
            type(case["answers"]) is list and len(case["answers"]) == len(public["questions"]),
            "reference question set mismatch",
        )
        for answer, question in zip(case["answers"], public["questions"], strict=True):
            _keys(answer, {"question_id", "expected", "rationale", "source_refs"}, "draft answer")
            _require(answer["question_id"] == question["id"], "reference question/order mismatch")
            _require(_answer(answer["expected"], question["answer_format"]), "invalid draft answer")
            _require(_text(answer["rationale"]), "invalid draft rationale")
            _require(
                type(answer["source_refs"]) is list and len(answer["source_refs"]) <= 8,
                "invalid draft source references",
            )
            for ref in answer["source_refs"]:
                _keys(ref, {"path", "line_start", "line_end"}, "source reference")
                _require(
                    type(ref["path"]) is str and ref["path"] in public["sources"],
                    "unknown virtual source reference",
                )
                lines = public["sources"][ref["path"]].split("\n")
                count = len(lines) - int(lines[-1] == "")
                _require(
                    type(ref["line_start"]) is int
                    and type(ref["line_end"]) is int
                    and 1 <= ref["line_start"] <= ref["line_end"] <= count,
                    "source reference outside virtual source lines",
                )


def check_candidate(root: Path, *, review: bool = False) -> dict:
    """Check declared draft bindings, not label semantics, independence or readiness."""
    root = root.resolve()
    tasks = _load(root, "tasks.json")
    inputs = _inputs(tasks)
    references = _load(root, "references.json")
    _references(references, inputs)
    result = {
        "kind": "evaluation-candidate-preflight",
        "schema_version": "0.1",
        "status": "draft-not-frozen",
        "integrity": "matched",
        "authorship": "assistant",
        "review_status": "pending-exact-maintainer-review",
        "benchmark_ready": False,
        "metadata_validation": "declared-not-attested",
        "execution_status": "not-run",
        "provider_calls": 0,
        "live_trials": 0,
        "candidate_sha256": _identity({"tasks": tasks, "references": references}),
        "case_count": len(inputs),
        "question_count": sum(len(case["questions"]) for case in inputs),
        "cases": [
            {
                "id": case["id"],
                "proposed_split": case["proposed_split"],
                "input_sha256": _identity(public),
                "question_count": len(case["questions"]),
            }
            for case, public in zip(tasks["cases"], inputs, strict=True)
        ],
    }
    if review:
        result["reference_drafts"] = references["cases"]
        result["review_inputs"] = inputs
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a single JSON preflight result")
    parser.add_argument("--review", action="store_true", help="include unapproved reference drafts")
    args = parser.parse_args(argv)
    try:
        result = check_candidate(ROOT, review=args.review)
    except CandidateError as error:
        failure = {
            "kind": "evaluation-candidate-preflight",
            "status": "invalid",
            "error": str(error),
            "benchmark_ready": False,
            "execution_status": "not-run",
            "provider_calls": 0,
            "live_trials": 0,
        }
        print(json.dumps(failure) if args.json else str(error))
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"Evaluation draft: {result['case_count']} cases, {result['question_count']} questions."
        )
        print("Integrity matched; assistant-authored references await exact maintainer review.")
        print("NOT FROZEN / NOT BENCHMARK-READY. No model calls, source execution or measurements.")
        for case in result["cases"]:
            print(f"  {case['id']}: {case['proposed_split']} [proposed]")
        if args.review:
            inputs = {case["case_id"]: case for case in result["review_inputs"]}
            for case in result["reference_drafts"]:
                print(f"\nDraft reference: {case['id']} / input {case['input_sha256']}")
                public = inputs[case["id"]]
                questions = {question["id"]: question for question in public["questions"]}
                for policy in public["policies"]:
                    print(f"  Policy data: {policy}")
                for path, content in public["sources"].items():
                    print(f"  Virtual source data: {path} (not executed)")
                    for number, line in enumerate(content.split("\n"), start=1):
                        print(f"    {number}: {line!r}")
                for answer in case["answers"]:
                    expected = (
                        "unknown (null)" if answer["expected"] is None else repr(answer["expected"])
                    )
                    print(f"  Question: {questions[answer['question_id']]['text']}")
                    print(f"  {answer['question_id']} = {expected}")
                    print(f"    {answer['rationale']}")
                    for ref in answer["source_refs"]:
                        print(f"    {ref['path']}:{ref['line_start']}-{ref['line_end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
