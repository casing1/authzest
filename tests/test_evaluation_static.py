import copy
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_comparison as comparison
from scripts import evaluation_static as adapter


@pytest.fixture
def fixed(tmp_path):
    directory = tmp_path / comparison.reference.REFERENCE
    directory.mkdir(parents=True)
    for name in ("tasks.json", "references.json", "manifest.json"):
        shutil.copyfile(comparison.ROOT / comparison.reference.REFERENCE / name, directory / name)
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        comparison.ROOT / "scripts/evaluation_metrics.py",
        tmp_path / "scripts/evaluation_metrics.py",
    )
    return tmp_path


def test_answers_are_staged_using_tasks_only_without_target_io_or_execution(fixed, monkeypatch):
    original_open = Path.open
    opened = []

    def task_only(path, *args, **kwargs):
        assert path.name == "tasks.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("static answers must not read references, execute targets or access providers")

    monkeypatch.setattr(Path, "open", task_only)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(comparison.FastAPIRouteParser, "parse_file", forbidden)
    monkeypatch.setattr(comparison.FastAPIRouteParser, "parse_repository", forbidden)
    staged = adapter.stage_static(fixed)
    assert opened == ["tasks.json"]
    assert len(staged["records"]) == len(staged["observations"]) == 7
    assert sum(len(items) for items in staged["records"].values()) == 21
    assert all(item["status"] == "valid" for item in staged["observations"])
    for case in staged["observations"]:
        for item in case["questions"][1:]:
            assert item["answer"] is None
        declaration = case["questions"][0]
        if declaration["answer"] is not None:
            assert declaration["evidence"]


def test_registered_static_observation_has_honest_fixed_source_metrics(fixed, monkeypatch):
    original_score = comparison.reference.score_reference
    scored = []

    def score_after_staging(root, records):
        assert len(records) == 7
        assert sum(len(items) for items in records.values()) == 21
        scored.append(copy.deepcopy(records))
        return original_score(root, records)

    monkeypatch.setattr(comparison.reference, "score_reference", score_after_staging)
    result = adapter.static_observation(fixed)
    assert len(scored) == 1
    assert result["kind"] == "registered-static-source-observation"
    assert result["response_origin"] == "deterministic-registered-source-query"
    assert result["static_baseline_measured"] is True
    assert result["baseline_scope"] == "fixed-seven-owned-source-tasks"
    assert result["query_registry_authorship"] == "assistant"
    assert result["evaluation_independence"] == "not-established-public-developed-tasks"
    assert result["model_quality_measured"] is False
    assert result["live_benchmark_ready"] is False
    assert result["live_configuration_frozen"] is False
    assert result["provider_calls_by_this_tool"] == result["live_trials"] == 0
    assert result["target_execution"] == "not-run"
    assert result["reference"]["independent_review_attested"] is False
    calculation = result["calculation"]
    counts = calculation["overall"]["counts"]
    assert (
        counts["cases"],
        counts["questions"],
        counts["answerable"],
        counts["required_unknown"],
    ) == (7, 21, 14, 7)
    assert counts["answered"] == counts["correct_answers"] == 5
    assert counts["correct_unknowns"] == 7
    assert counts["abstentions"] == 16
    assert counts["false_abstentions"] == 9
    assert counts["invalid_responses"] == counts["missing_responses"] == 0
    assert calculation["by_family"]["declaration"]["counts"]["answered"] == 5
    assert calculation["by_family"]["policy-intent"]["counts"]["answered"] == 0
    assert calculation["by_family"]["runtime-assurance"]["counts"]["answered"] == 0
    assert all(value is None for value in calculation["unmeasured"].values())


def test_empty_direct_scope_is_known_not_unknown_and_partial_queries_abstain(fixed):
    staged = adapter.stage_static(fixed)
    provider = staged["records"]["unexpanded-provider-graph"]
    assert provider[0]["answer"] == ""
    assert provider[1]["answer"] is provider[2]["answer"] is None
    for case in ("keyword-path-coverage", "composed-context-levels"):
        assert staged["records"][case][0]["answer"] is None
    assert staged["records"]["method-local-context"][0]["answer"] == "parcel:write"
    assert staged["records"]["separate-application-owners"][0]["answer"] == "2"
    assert staged["records"]["uncalled-factory-source"][0]["answer"] == "1"
    assert staged["records"]["status-probe-context"][0]["answer"] == "2"


def test_unsupported_task_identity_is_not_retargeted_from_human_case_name(fixed, monkeypatch):
    original = comparison.reference.reference_inputs

    def changed_tasks(root):
        cases = original(root)
        cases[0]["questions"][0]["text"] += " Changed task wording."
        return cases

    monkeypatch.setattr(comparison.reference, "reference_inputs", changed_tasks)
    staged = adapter.stage_static(fixed)
    assert all(item["answer"] is None for item in staged["records"]["method-local-context"])
    assert staged["observations"][0]["questions"][0]["reason"] == "unregistered-query"


@pytest.mark.parametrize("changed", ["source", "request-id"])
def test_changed_packet_with_stale_identity_is_invalid_not_a_retargeted_query(
    fixed, monkeypatch, changed
):
    original = comparison.build_plan

    def changed_plan(root):
        plan = original(root)
        payload = plan["tasks"][0]["packets"]["static-only"]["payload"]
        if changed == "source":
            payload["sources"]["main.py"] += "\n# edited without new identity\n"
        else:
            payload["request_id"] = "request-" + "0" * 64
        return plan

    monkeypatch.setattr(comparison, "build_plan", changed_plan)
    staged = adapter.stage_static(fixed)
    assert staged["records"]["method-local-context"] == []
    assert staged["observations"][0]["status"] == "invalid"
    assert staged["observations"][0]["error"] == "input-identity-mismatch"


@pytest.mark.parametrize("failure", ["query-input", "malformed-answer"])
def test_adapter_failures_keep_entire_case_and_denominators(fixed, monkeypatch, failure):
    def failed_query(sources, query):
        if failure == "query-input":
            raise adapter.QueryError("synthetic invalid evaluator input")
        return {"answer": True, "reason": "synthetic-invalid", "evidence": []}

    monkeypatch.setattr(adapter, "evaluate_query", failed_query)
    result = adapter.static_observation(fixed)
    counts = result["calculation"]["overall"]["counts"]
    assert (
        counts["cases"],
        counts["questions"],
        counts["answerable"],
        counts["required_unknown"],
    ) == (7, 21, 14, 7)
    assert counts["invalid_responses"] == 7
    assert counts["missing_responses"] == 0
    assert counts["correct_unknowns"] == 0
    assert counts["answered"] == 0


@pytest.mark.parametrize("json_output", [True, False])
def test_explicit_static_cli_is_separate_from_synthetic_dry_run(
    fixed, monkeypatch, capsys, json_output
):
    monkeypatch.setattr(comparison, "ROOT", fixed)
    assert comparison.main(["--static-only", *(["--json"] if json_output else [])]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    if json_output:
        result = json.loads(output.out)
        assert result["static_baseline_measured"] is True
        assert "modes" not in result
        assert result["model_quality_measured"] is False
    else:
        assert "DETERMINISTIC OWNED-SOURCE OBSERVATION" in output.out
        assert "Answered 5/21; abstained 16; invalid cases 0" in output.out
        assert '""' in output.out
        assert "unknown" in output.out


@pytest.mark.parametrize(
    "args", [["--static-only", "--dry-run"], ["--static-only", "--fault", "invalid"]]
)
def test_static_cli_rejects_synthetic_fault_injection_and_mode_mixing(args, capsys):
    with pytest.raises(SystemExit) as error:
        comparison.main(args)
    assert error.value.code == 2
    assert capsys.readouterr().err


def test_static_cli_reference_drift_fails_without_an_output_score(fixed, monkeypatch, capsys):
    monkeypatch.setattr(comparison, "ROOT", fixed)
    path = fixed / comparison.reference.REFERENCE / "references.json"
    path.write_bytes(path.read_bytes() + b"\n")
    assert comparison.main(["--static-only", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["kind"] == "offline-comparison-error"
    assert "calculation" not in result
