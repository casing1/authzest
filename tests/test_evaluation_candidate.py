"""The evaluation preflight checks inert draft data, not benchmark correctness."""

from __future__ import annotations

import hashlib
import io
import json
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import check_evaluation_candidate as checker


def identity(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def public_case(case: dict) -> dict:
    return {
        "case_id": case["id"],
        "sources": case["sources"],
        "policies": case["policies"],
        "questions": case["questions"],
    }


@pytest.fixture
def draft(tmp_path: Path) -> tuple[Path, dict, dict]:
    tasks = {
        "schema_version": "0.1",
        "kind": "evaluation-candidate-tasks",
        "status": "draft-not-frozen",
        "authorship": "assistant",
        "cases": [
            {
                "id": "inert-example",
                "proposed_split": "reserved-evaluation",
                "sources": {
                    "app/main.py": (
                        'raise AssertionError("virtual source must never execute")\n'
                        "# Evidence is on this second line.\n"
                    )
                },
                "policies": ["This example has no declared scopes."],
                "questions": [
                    {
                        "id": "declared-scopes",
                        "family": "declaration",
                        "text": "Which scopes are declared?",
                        "answer_format": "sorted-csv",
                    }
                ],
            }
        ],
    }
    references = {
        "schema_version": "0.1",
        "kind": "evaluation-reference-draft",
        "authorship": "assistant",
        "review_status": "pending-exact-maintainer-review",
        "reviewer": None,
        "review_record": None,
        "cases": [
            {
                "id": "inert-example",
                "input_sha256": identity(public_case(tasks["cases"][0])),
                "answers": [
                    {
                        "question_id": "declared-scopes",
                        "expected": "",
                        "rationale": "REFERENCE RATIONALE: no scope declaration appears.",
                        "source_refs": [{"path": "app/main.py", "line_start": 1, "line_end": 2}],
                    }
                ],
            }
        ],
    }
    write_draft(tmp_path, tasks, references)
    return tmp_path, tasks, references


def write_draft(root: Path, tasks: dict, references: dict) -> None:
    directory = root / checker.CANDIDATE
    directory.mkdir(parents=True, exist_ok=True)
    for filename, value in (("tasks.json", tasks), ("references.json", references)):
        (directory / filename).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def answer(references: dict) -> dict:
    return references["cases"][0]["answers"][0]


def test_minimal_draft_is_inert_and_cannot_establish_readiness(draft, monkeypatch):
    root, tasks, references = draft

    def no_process(*args, **kwargs):
        pytest.fail("preflight must not launch a subprocess")

    monkeypatch.setattr(subprocess, "Popen", no_process)
    monkeypatch.setattr(socket, "socket", no_process)
    result = checker.check_candidate(root)
    assert result == {
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
        "candidate_sha256": identity({"tasks": tasks, "references": references}),
        "case_count": 1,
        "question_count": 1,
        "cases": [
            {
                "id": "inert-example",
                "proposed_split": "reserved-evaluation",
                "input_sha256": identity(public_case(tasks["cases"][0])),
                "question_count": 1,
            }
        ],
    }
    assert not (root / "app").exists()


def test_public_inputs_never_open_references_or_leak_answer_metadata(draft, monkeypatch):
    root, tasks, _ = draft
    original_open = Path.open
    opened = []

    def guarded_open(path, *args, **kwargs):
        assert path.name != "references.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    projected = checker.public_inputs(root)
    assert projected == [public_case(tasks["cases"][0])]
    assert opened == ["tasks.json"]
    serialized = json.dumps(projected)
    for private in ("expected", "rationale", "proposed_split", "authorship", "REFERENCE RATIONALE"):
        assert private not in serialized


def test_input_change_rejects_stale_reference_binding(draft):
    root, tasks, references = draft
    tasks["cases"][0]["sources"]["app/main.py"] += "# changed\n"
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="identity mismatch"):
        checker.check_candidate(root)


def test_known_empty_csv_remains_distinct_from_unknown(draft):
    root, tasks, references = draft
    known = checker.check_candidate(root, review=True)
    assert known["reference_drafts"][0]["answers"][0]["expected"] == ""
    answer(references)["expected"] = None
    write_draft(root, tasks, references)
    unknown = checker.check_candidate(root, review=True)
    assert unknown["reference_drafts"][0]["answers"][0]["expected"] is None
    assert known["candidate_sha256"] != unknown["candidate_sha256"]


def test_sorted_csv_rejects_duplicate_or_unsorted_answers(draft):
    root, tasks, references = draft
    answer(references)["expected"] = "write,read,read"
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="invalid draft answer"):
        checker.check_candidate(root)


@pytest.mark.parametrize("start,end", [(True, 1), (1, True), (0, 1), (2, 1), (1, 3)])
def test_source_citations_require_integer_inclusive_real_line_bounds(draft, start, end):
    root, tasks, references = draft
    answer(references)["source_refs"][0].update(line_start=start, line_end=end)
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="outside virtual source lines"):
        checker.check_candidate(root)


def test_source_citation_must_reference_an_embedded_source(draft):
    root, tasks, references = draft
    answer(references)["source_refs"][0]["path"] = "other.py"
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="unknown virtual source"):
        checker.check_candidate(root)


@pytest.mark.parametrize(
    "document,key,value,diagnostic",
    [
        ("tasks", "extra", True, "task document fields"),
        ("tasks", "status", "frozen", "cannot claim a freeze"),
        ("tasks", "authorship", "maintainer", "authorship"),
        ("references", "authorship", "maintainer", "authorship"),
        ("references", "review_status", "approved", "cannot establish exact reference approval"),
        ("references", "reviewer", "casing1", "cannot establish exact reference approval"),
        (
            "references",
            "review_record",
            "approved by user",
            "cannot establish exact reference approval",
        ),
    ],
)
def test_strict_metadata_does_not_accept_extra_fields_or_fake_approval(
    draft, document, key, value, diagnostic
):
    root, tasks, references = draft
    target = tasks if document == "tasks" else references
    target[key] = value
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match=diagnostic):
        checker.check_candidate(root)


@pytest.mark.parametrize("duplicate", ["case", "question"])
def test_duplicate_identifiers_are_rejected(draft, duplicate):
    root, tasks, references = draft
    if duplicate == "case":
        tasks["cases"].append(tasks["cases"][0])
    else:
        tasks["cases"][0]["questions"].append(tasks["cases"][0]["questions"][0])
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="duplicate"):
        checker.check_candidate(root)


@pytest.mark.parametrize("raw", [b'{"kind":1,"kind":2}', b'{"value":NaN}', b'{"value":', b'"\xff"'])
def test_strict_json_rejects_duplicates_nonfinite_malformed_and_invalid_utf8(draft, raw):
    root, _, _ = draft
    (root / checker.CANDIDATE / "tasks.json").write_bytes(raw)
    with pytest.raises(checker.CandidateError, match="invalid candidate JSON"):
        checker.check_candidate(root)


def test_documents_are_bounded_on_read_not_after_unbounded_loading(draft, monkeypatch):
    root, _, _ = draft
    requests = []

    class BoundedStream(io.BytesIO):
        def read(self, size=-1):
            requests.append(size)
            return super().read(size)

    monkeypatch.setattr(checker, "MAX_DOCUMENT_BYTES", 64)
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: BoundedStream(b"x" * 1000))
    with pytest.raises(checker.CandidateError, match="exceeds byte limit"):
        checker.check_candidate(root)
    assert requests == [65]


@pytest.mark.parametrize("path", ["../main.py", "/tmp/main.py", "app\\main.py"])
def test_virtual_source_paths_cannot_escape_the_embedded_namespace(draft, path):
    root, tasks, references = draft
    tasks["cases"][0]["sources"] = {path: "pass\n"}
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="invalid virtual source path"):
        checker.check_candidate(root)


@pytest.mark.parametrize("component", ["tasks.json", "draft"])
def test_candidate_files_and_parent_components_cannot_be_symlinks(draft, component):
    root, _, _ = draft
    candidate = root / checker.CANDIDATE
    original = candidate / component if component == "tasks.json" else candidate
    target = original.with_name(original.name + "-actual")
    original.rename(target)
    try:
        original.symlink_to(target, target_is_directory=target.is_dir())
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable in this test environment")
    with pytest.raises(checker.CandidateError, match="linked candidate path"):
        checker.check_candidate(root)


def test_nonfile_candidate_is_rejected_before_open(draft):
    root, _, _ = draft
    tasks = root / checker.CANDIDATE / "tasks.json"
    tasks.unlink()
    tasks.mkdir()
    with pytest.raises(checker.CandidateError, match="non-regular candidate path"):
        checker.check_candidate(root)


def test_missing_document_is_a_candidate_error(draft):
    root, _, _ = draft
    (root / checker.CANDIDATE / "references.json").unlink()
    with pytest.raises(checker.CandidateError, match="cannot read candidate references.json"):
        checker.check_candidate(root)


@pytest.mark.parametrize("limit", ["case-count", "source-count", "source-bytes"])
def test_case_and_virtual_source_inputs_have_explicit_bounds(draft, limit):
    root, tasks, references = draft
    if limit == "case-count":
        tasks["cases"] *= 13
    elif limit == "source-count":
        tasks["cases"][0]["sources"] = {f"file{index}.py": "pass" for index in range(5)}
    else:
        tasks["cases"][0]["sources"] = {
            "main.py": "가" * (checker.MAX_SOURCE_BYTES // len("가".encode()) + 1)
        }
    write_draft(root, tasks, references)
    with pytest.raises(checker.CandidateError, match="count|too large"):
        checker.check_candidate(root)


def test_cli_default_is_a_human_draft_summary_without_references(draft, monkeypatch, capsys):
    root, _, _ = draft
    monkeypatch.setattr(checker, "ROOT", root)
    assert checker.main([]) == 0
    output = capsys.readouterr()
    assert "1 cases, 1 questions" in output.out
    assert "NOT FROZEN / NOT BENCHMARK-READY" in output.out
    assert "reserved-evaluation [proposed]" in output.out
    assert "REFERENCE RATIONALE" not in output.out
    assert output.err == ""


def test_cli_json_emits_one_result_and_review_is_explicit(draft, monkeypatch, capsys):
    root, _, _ = draft
    monkeypatch.setattr(checker, "ROOT", root)
    assert checker.main(["--json"]) == 0
    ordinary = json.loads(capsys.readouterr().out)
    assert "reference_drafts" not in ordinary
    assert "review_inputs" not in ordinary
    assert checker.main(["--json", "--review"]) == 0
    reviewed = json.loads(capsys.readouterr().out)
    assert reviewed["reference_drafts"][0]["answers"][0]["expected"] == ""
    assert reviewed["benchmark_ready"] is False
    assert reviewed["review_inputs"] == checker.public_inputs(root)


def test_cli_human_review_labels_known_empty_and_unknown(draft, monkeypatch, capsys):
    root, tasks, references = draft
    monkeypatch.setattr(checker, "ROOT", root)
    assert checker.main(["--review"]) == 0
    output = capsys.readouterr().out
    assert "declared-scopes = ''" in output
    assert "Question: Which scopes are declared?" in output
    assert "Policy data: This example has no declared scopes." in output
    assert "Virtual source data: app/main.py (not executed)" in output
    assert "1: 'raise AssertionError(" in output
    answer(references)["expected"] = None
    write_draft(root, tasks, references)
    assert checker.main(["--review"]) == 0
    output = capsys.readouterr().out
    assert "declared-scopes = unknown (null)" in output
    assert "app/main.py:1-2" in output


def test_cli_errors_are_explicit_and_nonzero(draft, monkeypatch, capsys):
    root, _, _ = draft
    monkeypatch.setattr(checker, "ROOT", root)
    (root / checker.CANDIDATE / "tasks.json").write_text("{}", encoding="utf-8")
    assert checker.main([]) == 1
    assert "invalid task document fields" in capsys.readouterr().out
    assert checker.main(["--json"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "kind": "evaluation-candidate-preflight",
        "status": "invalid",
        "error": "invalid task document fields",
        "benchmark_ready": False,
        "execution_status": "not-run",
        "provider_calls": 0,
        "live_trials": 0,
    }


def test_cli_invalid_usage_does_not_read_candidate(monkeypatch, capsys):
    def unexpected_read(*args, **kwargs):
        pytest.fail("invalid CLI options must stop before reading draft data")

    monkeypatch.setattr(checker, "check_candidate", unexpected_read)
    with pytest.raises(SystemExit) as error:
        checker.main(["--unknown"])
    assert error.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_repository_draft_has_bound_inputs_without_claiming_an_evaluation():
    result = checker.check_candidate(Path(__file__).resolve().parents[1])
    assert (result["case_count"], result["question_count"]) == (7, 21)
    assert result["integrity"] == "matched"
    assert result["status"] == "draft-not-frozen"
    assert result["review_status"] == "pending-exact-maintainer-review"
    assert result["benchmark_ready"] is False
    assert result["execution_status"] == "not-run"
    assert result["provider_calls"] == result["live_trials"] == 0
    assert "reference_drafts" not in result


def test_repository_draft_denominators_remain_explicit_proposals():
    root = Path(__file__).resolve().parents[1]
    review = checker.check_candidate(root, review=True)
    inputs = review["review_inputs"]
    families = [question["family"] for case in inputs for question in case["questions"]]
    assert {family: families.count(family) for family in set(families)} == {
        "declaration": 7,
        "policy-intent": 7,
        "runtime-assurance": 7,
    }
    assert all(len(case["questions"]) == 3 for case in inputs)
    expected = [item["expected"] for case in review["reference_drafts"] for item in case["answers"]]
    assert sum(value is None for value in expected) == 7
    assert sum(value is not None for value in expected) == 14
    assert "" in expected  # Empty CSV is a known declaration answer, not unknown.
    splits = [case["proposed_split"] for case in review["cases"]]
    assert splits.count("development") == 3
    assert splits.count("reserved-evaluation") == 4
    policies = [
        answer["expected"]
        for case, refs in zip(inputs, review["reference_drafts"], strict=True)
        for question, answer in zip(case["questions"], refs["answers"], strict=True)
        if question["family"] == "policy-intent"
    ]
    assert {value: policies.count(value) for value in set(policies)} == {
        "restricted": 4,
        "mixed": 2,
        "public": 1,
    }


def test_public_control_preserves_the_exact_original_six_candidate_entries():
    root = Path(__file__).resolve().parents[1] / checker.CANDIDATE
    tasks = json.loads((root / "tasks.json").read_text(encoding="utf-8"))
    references = json.loads((root / "references.json").read_text(encoding="utf-8"))
    original = {
        "tasks": tasks | {"cases": tasks["cases"][:6]},
        "references": references | {"cases": references["cases"][:6]},
    }
    # Canonical draft identity at PR #133 / main 8b204e2, not a label approval.
    assert identity(original) == "e596cc93d136f537fc7c909c7294399e8688672d0183557dd5e0d7feeed37482"


def test_public_intent_control_is_explicit_and_does_not_claim_anonymous_reachability():
    root = Path(__file__).resolve().parents[1]
    review = checker.check_candidate(root, review=True)
    public, refs = review["review_inputs"][-1], review["reference_drafts"][-1]
    assert public["case_id"] == refs["id"] == "status-probe-context"
    assert review["cases"][-1]["proposed_split"] == "reserved-evaluation"
    assert "both intentionally public" in public["policies"][0]
    assert "ordinary response formatting" in public["policies"][1]
    assert "Depends(parse_display_units)" in public["sources"]["main.py"]
    assert public["sources"]["main.py"].count("@app.get(") == 2
    answers = {answer["question_id"]: answer for answer in refs["answers"]}
    assert answers["source-http-declaration-count"]["expected"] == "2"
    assert answers["registration-policy-intent"]["expected"] == "public"
    assert answers["registration-policy-intent"]["source_refs"] == []
    assert answers["anonymous-reachability-assurance"]["expected"] is None
    assert review["review_status"] == "pending-exact-maintainer-review"
    assert review["benchmark_ready"] is False
