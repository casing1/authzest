"""Fixed-label integration uses caller records or an explicit null-only control."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluate_reference as evaluator


@pytest.fixture
def fixed(tmp_path: Path) -> Path:
    directory = tmp_path / evaluator.REFERENCE
    directory.mkdir(parents=True)
    for filename in ("tasks.json", "references.json", "manifest.json"):
        shutil.copyfile(evaluator.ROOT / evaluator.REFERENCE / filename, directory / filename)
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        evaluator.ROOT / "scripts/evaluation_metrics.py", tmp_path / "scripts/evaluation_metrics.py"
    )
    return tmp_path


def null_records(root: Path) -> dict:
    return {
        case["case_id"]: [
            {"question_id": question["id"], "answer": None} for question in case["questions"]
        ]
        for case in evaluator.reference_inputs(root)
    }


def assert_ratio(actual: dict, numerator: int, denominator: int) -> None:
    assert actual == {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def test_fixed_values_are_separate_from_archived_metadata_and_live_readiness(fixed):
    snapshot = evaluator.load_reference(fixed)
    result = snapshot["preflight"]
    assert result["status"] == "reference-values-fixed"
    assert result["candidate_sha256"] == evaluator.CANDIDATE_SHA256
    assert result["case_count"] == 7
    assert result["question_count"] == 21
    assert result["authorship"] == "assistant"
    assert result["archived_proposal_status"] == "draft-not-frozen"
    assert result["archived_reference_review_status"] == "pending-exact-maintainer-review"
    assert result["decision"] == {
        "value": "accepted-current-reference-values",
        "source": "direct-user-chat-confirmation",
        "recorded_by": "assistant",
        "recorded_date": "2026-11-06",
        "confirmation": "current-21-reference-values-confirmed",
        "scope": "current-21-reference-values",
        "identity_assurance": "not-authenticated-by-this-tool",
        "inspection_attestation": "not-collected",
        "independent_review_attested": False,
    }
    assert result["live_benchmark_ready"] is False
    assert result["live_configuration_frozen"] is False
    assert result["live_execution_authorized"] is False
    assert result["provider_calls_by_this_tool"] == 0
    assert result["target_execution"] == "not-run"
    assert result["scoring_status"] == "not-run"
    assert "calculation" not in result
    assert snapshot["references"]["reviewer"] is None
    assert snapshot["references"]["review_record"] is None


def test_snapshot_raw_bytes_remain_identical_to_original_proposal():
    for filename in ("tasks.json", "references.json"):
        frozen = evaluator.ROOT / evaluator.REFERENCE / filename
        original = evaluator.ROOT / "tests/fixtures/evaluation_candidate/draft" / filename
        assert frozen.read_bytes() == original.read_bytes()


def test_input_projection_only_opens_task_data_and_excludes_private_fields(fixed, monkeypatch):
    original_open = Path.open
    opened = []

    def guarded_open(path, *args, **kwargs):
        assert path.name == "tasks.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    inputs = evaluator.reference_inputs(fixed)
    assert opened == ["tasks.json"]
    assert len(inputs) == 7
    assert all(set(case) == {"case_id", "sources", "policies", "questions"} for case in inputs)
    serialized = json.dumps(inputs)
    for private in ("expected", "rationale", "source_refs", "proposed_split", "authorship"):
        assert private not in serialized


def test_all_unknown_control_stages_answers_before_evaluator_only_reads(fixed, monkeypatch):
    original_score = evaluator.score_reference
    staged = []

    def inspect_score(root, responses):
        assert len(responses) == 7
        assert sum(len(records) for records in responses.values()) == 21
        assert all(item["answer"] is None for records in responses.values() for item in records)
        staged.append(responses)
        return original_score(root, responses)

    monkeypatch.setattr(evaluator, "score_reference", inspect_score)
    result = evaluator.all_unknown_control(fixed)
    assert len(staged) == 1
    assert result["response_origin"] == "synthetic-all-unknown-control"
    assert result["model_quality_measured"] is False
    assert result["scoring_status"] == "calculated-offline"
    calculation = result["calculation"]
    assert calculation["reference_review_status"] == "not-assessed"
    assert calculation["benchmark_ready"] is False
    counts = calculation["overall"]["counts"]
    assert counts == {
        "cases": 7,
        "questions": 21,
        "answerable": 14,
        "required_unknown": 7,
        "invalid_responses": 0,
        "missing_responses": 0,
        "answered": 0,
        "correct_answers": 0,
        "correct_unknowns": 7,
        "abstentions": 21,
        "false_abstentions": 14,
        "false_certainties": 0,
        "invalid_questions": 0,
    }
    ratios = calculation["overall"]["metrics"]
    assert_ratio(ratios["task_coverage"], 0, 21)
    assert_ratio(ratios["answered_accuracy"], 0, 0)
    assert_ratio(ratios["required_unknown_handling"], 7, 7)
    assert_ratio(ratios["false_abstention"], 14, 14)
    assert_ratio(ratios["invalid_responses"], 0, 7)
    assert calculation["by_split"]["development"]["counts"]["questions"] == 9
    assert calculation["by_split"]["reserved-evaluation"]["counts"]["questions"] == 12
    assert all(group["counts"]["questions"] == 7 for group in calculation["by_family"].values())
    assert all(value is None for value in calculation["unmeasured"].values())


def test_caller_empty_csv_answer_is_not_unknown_or_a_model_measurement(fixed):
    responses = null_records(fixed)
    # A manually specified known-empty scope answer, not copied from a reference loader.
    responses["unexpanded-provider-graph"][0] = {
        "question_id": "direct-route-security-scopes",
        "answer": "",
    }
    result = evaluator.score_reference(fixed, responses)
    assert result["response_origin"] == "caller-provided-normalized-records"
    assert result["provider_calls_by_this_tool"] == 0
    overall = result["calculation"]["overall"]
    assert overall["counts"]["correct_answers"] == 1
    assert overall["counts"]["correct_unknowns"] == 7
    assert overall["counts"]["false_abstentions"] == 13
    assert_ratio(overall["metrics"]["answered_accuracy"], 1, 1)
    assert_ratio(overall["metrics"]["task_coverage"], 1, 21)


@pytest.mark.parametrize("bad", [None, {}, [], [{"question_id": "wrong", "answer": None}]])
def test_invalid_or_missing_whole_case_preserves_all_fixed_denominators(fixed, bad):
    responses = null_records(fixed)
    responses["status-probe-context"] = bad
    result = evaluator.score_reference(fixed, responses)["calculation"]
    counts = result["overall"]["counts"]
    assert counts["cases"] == 7
    assert counts["questions"] == 21
    assert counts["answerable"] == 14
    assert counts["required_unknown"] == 7
    assert counts["invalid_responses"] == 1
    assert counts["invalid_questions"] == 3
    assert counts["correct_unknowns"] == 6
    assert_ratio(result["overall"]["metrics"]["invalid_responses"], 1, 7)


def test_unknown_response_case_is_an_error_not_a_dropped_trial(fixed):
    with pytest.raises(evaluator.ReferenceError, match="invalid response manifest"):
        evaluator.score_reference(fixed, {"not-in-plan": []})


@pytest.mark.parametrize("filename", ["tasks.json", "references.json", "manifest.json"])
def test_raw_snapshot_drift_is_rejected_even_if_json_values_are_identical(fixed, filename):
    path = fixed / evaluator.REFERENCE / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(evaluator.ReferenceError, match="hash mismatch"):
        evaluator.load_reference(fixed)


def test_canonical_candidate_identity_is_separately_checked(fixed, monkeypatch):
    original = evaluator.candidate.validate_candidate_documents

    def changed_identity(tasks, references):
        return {**original(tasks, references), "candidate_sha256": "0" * 64}

    monkeypatch.setattr(evaluator.candidate, "validate_candidate_documents", changed_identity)
    with pytest.raises(evaluator.ReferenceError, match="candidate identity mismatch"):
        evaluator.load_reference(fixed)


@pytest.mark.parametrize("target", ["selected-copy", "trusted-import-source"])
def test_both_recorded_and_imported_arithmetic_source_must_match(
    fixed, tmp_path, monkeypatch, target
):
    arithmetic_root = fixed
    if target == "trusted-import-source":
        arithmetic_root = tmp_path / "other-owned-checkout"
        (arithmetic_root / "scripts").mkdir(parents=True)
        monkeypatch.setattr(evaluator, "METRICS_ROOT", arithmetic_root)
    (arithmetic_root / "scripts/evaluation_metrics.py").write_text(
        'raise AssertionError("must never import from a selected data root")\n', encoding="utf-8"
    )
    with pytest.raises(evaluator.ReferenceError, match="fixed metrics hash mismatch"):
        evaluator.score_reference(fixed, {})


@pytest.mark.parametrize(
    "raw",
    [b'{"kind":1,"kind":2}', b'{"value":NaN}', b'{"value":Infinity}', b'{"value":', b'"\xff"'],
)
def test_strict_json_rejects_duplicate_nonfinite_malformed_and_invalid_utf8(fixed, raw):
    (fixed / evaluator.REFERENCE / "tasks.json").write_bytes(raw)
    with pytest.raises(evaluator.ReferenceError, match="invalid reference JSON"):
        evaluator.load_reference(fixed)


def test_bounded_read_never_requests_the_unbounded_document(fixed, monkeypatch):
    requests = []

    class BoundedStream(io.BytesIO):
        def read(self, size=-1):
            requests.append(size)
            return super().read(size)

    monkeypatch.setattr(evaluator, "MAX_DOCUMENT_BYTES", 64)
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: BoundedStream(b"x" * 1000))
    with pytest.raises(evaluator.ReferenceError, match="exceeds byte limit"):
        evaluator.load_reference(fixed)
    assert requests == [65]


@pytest.mark.parametrize("filename", ["tasks.json", "references.json", "manifest.json"])
@pytest.mark.parametrize("failure", ["missing", "directory", "symlink"])
def test_fixed_json_files_must_be_present_regular_and_unlinked(fixed, filename, failure):
    path = fixed / evaluator.REFERENCE / filename
    raw = path.read_bytes()
    path.unlink()
    if failure == "directory":
        path.mkdir()
    elif failure == "symlink":
        target = fixed / "owned-target.json"
        target.write_bytes(raw)
        path.symlink_to(target)
    with pytest.raises(evaluator.ReferenceError, match="cannot read|non-regular|linked"):
        evaluator.load_reference(fixed)


def test_intermediate_symlink_is_not_followed(fixed):
    directory = fixed / "tests/fixtures/evaluation_reference"
    saved = fixed / "saved-reference-directory"
    directory.rename(saved)
    directory.symlink_to(saved, target_is_directory=True)
    with pytest.raises(evaluator.ReferenceError, match="linked reference path"):
        evaluator.load_reference(fixed)


def test_symlink_root_is_not_treated_as_an_owned_data_directory(fixed):
    linked = fixed / "linked-root"
    linked.symlink_to(fixed, target_is_directory=True)
    with pytest.raises(evaluator.ReferenceError, match="non-directory reference root"):
        evaluator.load_reference(linked)


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorship", "human"),
        ("live_benchmark_ready", True),
        ("live_execution_authorized", True),
        ("live_configuration_frozen", True),
    ],
)
def test_manifest_semantics_cannot_claim_more_than_the_recorded_decision(
    fixed, monkeypatch, field, value
):
    path = fixed / evaluator.REFERENCE / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    raw = json.dumps(manifest).encode()
    path.write_bytes(raw)
    # Simulate a developer refreshing a raw hash without honoring the v1 semantic contract.
    monkeypatch.setattr(evaluator, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(evaluator.ReferenceError, match="manifest semantics mismatch"):
        evaluator.load_reference(fixed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("independent_review_attested", True),
        ("identity_assurance", "authenticated"),
        ("inspection_attestation", "all-labels-inspected"),
        ("recorded_by", "maintainer"),
        ("confirmation", "unnecessary verbatim conversation content"),
    ],
)
def test_manifest_decision_does_not_add_false_identity_or_review_attestations(
    fixed, monkeypatch, field, value
):
    path = fixed / evaluator.REFERENCE / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["decision"][field] = value
    raw = json.dumps(manifest).encode()
    path.write_bytes(raw)
    monkeypatch.setattr(evaluator, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(evaluator.ReferenceError, match="manifest semantics mismatch"):
        evaluator.load_reference(fixed)


def test_tool_never_launches_target_code_process_or_network(fixed, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("reference tooling must not execute targets, subprocesses or network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = evaluator.all_unknown_control(fixed)
    assert result["target_execution"] == "not-run"
    assert result["provider_calls_by_this_tool"] == 0
    assert not (fixed / "main.py").exists()
    assert not (fixed / "app").exists()


def test_default_cli_is_preflight_only_with_one_json_object(fixed, monkeypatch, capsys):
    monkeypatch.setattr(evaluator, "ROOT", fixed)

    def no_score(*args, **kwargs):
        pytest.fail("default CLI must not calculate responses")

    monkeypatch.setattr(evaluator, "score_reference", no_score)
    assert evaluator.main(["--json"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert captured.err == ""
    assert result["scoring_status"] == "not-run"
    assert "calculation" not in result
    assert "references" not in result


@pytest.mark.parametrize("json_output", [True, False])
def test_control_cli_is_labeled_synthetic_not_model_quality(
    fixed, monkeypatch, capsys, json_output
):
    monkeypatch.setattr(evaluator, "ROOT", fixed)
    assert evaluator.main(["--control", *(["--json"] if json_output else [])]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    if json_output:
        result = json.loads(captured.out)
        assert result["response_origin"] == "synthetic-all-unknown-control"
        assert result["model_quality_measured"] is False
    else:
        assert "SYNTHETIC ALL-UNKNOWN CONTROL" in captured.out
        assert "not a static baseline or model-quality result" in captured.out
        assert "answered_accuracy: 0/0 (None)" in captured.out


def test_human_preflight_does_not_imply_live_readiness(fixed, monkeypatch, capsys):
    monkeypatch.setattr(evaluator, "ROOT", fixed)
    assert evaluator.main([]) == 0
    output = capsys.readouterr().out
    assert "7 cases, 21 questions" in output
    assert "live benchmark NOT READY" in output
    assert "SYNTHETIC" not in output


@pytest.mark.parametrize("json_output", [True, False])
def test_cli_integrity_error_is_exit_one_not_a_performance_result(
    fixed, monkeypatch, capsys, json_output
):
    monkeypatch.setattr(evaluator, "ROOT", fixed)
    (fixed / evaluator.REFERENCE / "tasks.json").unlink()
    assert evaluator.main(["--json"] if json_output else []) == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    if json_output:
        result = json.loads(captured.out)
        assert result["status"] == "invalid"
        assert result["live_benchmark_ready"] is False
        assert "calculation" not in result
    else:
        assert "cannot read fixed reference file" in captured.out


@pytest.mark.parametrize(
    "args", [["--file", "response.json"], ["--provider", "codex"], ["--control", "x"]]
)
def test_cli_rejects_arbitrary_files_and_live_provider_options(args, capsys):
    with pytest.raises(SystemExit) as error:
        evaluator.main(args)
    assert error.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
