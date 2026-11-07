import copy
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_comparison as comparison
from scripts import evaluation_response as response


@pytest.fixture
def fixed(tmp_path):
    directory = tmp_path / comparison.reference.REFERENCE
    directory.mkdir(parents=True)
    for filename in ("tasks.json", "references.json", "manifest.json"):
        shutil.copyfile(
            comparison.ROOT / comparison.reference.REFERENCE / filename, directory / filename
        )
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        comparison.ROOT / "scripts/evaluation_metrics.py",
        tmp_path / "scripts/evaluation_metrics.py",
    )
    return tmp_path


def by_case(plan, name):
    return next(task for task in plan["tasks"] if task["case_id"] == name)


def assert_no_private_keys(value):
    banned = {
        "expected",
        "rationale",
        "source_refs",
        "proposed_split",
        "authorship",
        "decision",
        "review_status",
        "reference_sha256",
        "candidate_sha256",
        "case_id",
    }
    if isinstance(value, dict):
        assert not set(value) & banned
        for child in value.values():
            assert_no_private_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_private_keys(child)


def test_plan_reads_tasks_only_without_target_io_or_execution(fixed, monkeypatch):
    original_open = Path.open
    opened = []

    def task_only(path, *args, **kwargs):
        assert path.name == "tasks.json"
        opened.append(path.name)
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("no file parser, repository traversal, provider, subprocess or network")

    monkeypatch.setattr(Path, "open", task_only)
    monkeypatch.setattr(comparison.FastAPIRouteParser, "parse_file", forbidden)
    monkeypatch.setattr(comparison.FastAPIRouteParser, "parse_repository", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    plan = comparison.build_plan(fixed)
    assert opened == ["tasks.json"]
    assert plan["case_count"] == 7
    assert plan["question_count"] == 21
    assert len(plan["tasks"]) * len(plan["modes"]) == 21
    assert plan["static_answer_adapter"] == "registered-source-query-v1"
    assert plan["provider_calls_by_this_tool"] == 0
    assert plan["target_execution"] == "not-run"
    assert plan["live_configuration_frozen"] is False
    assert plan["live_benchmark_ready"] is False


def test_paired_payloads_differ_only_in_evidence_and_derived_request_id(fixed):
    plan = comparison.build_plan(fixed)
    for task in plan["tasks"]:
        packets = task["packets"]
        assert len({item["request_id"] for item in packets.values()}) == 3
        payloads = [copy.deepcopy(item["payload"]) for item in packets.values()]
        for mode, payload in zip(comparison.MODES, payloads, strict=True):
            assert payload["task_id"] == task["task_id"]
            request_id = payload.pop("request_id")
            assert request_id == comparison._identity(
                "request-", {"mode": mode, "payload": payload}
            )
            assert_no_private_keys(payload)
            assert task["case_id"] not in json.dumps(payload)
            if mode != "evidence-assisted":
                assert payload["evidence"] == []
            else:
                assert payload["evidence"][0]["analysis_status"] == "partial"
            payload.pop("evidence")
        assert payloads[0] == payloads[1] == payloads[2]
        # No aliasing: editing one exported packet must not edit another mode.
        packets["model-only"]["payload"]["policies"].append("changed")
        assert "changed" not in packets["evidence-assisted"]["payload"]["policies"]


@pytest.mark.parametrize("changed", ["sources", "policies", "questions"])
def test_task_ids_bind_only_public_task_content(fixed, monkeypatch, changed):
    cases = comparison.reference.reference_inputs(fixed)
    before = comparison.build_plan(fixed)
    if changed == "sources":
        cases[0]["sources"]["main.py"] += "\n# changed task source\n"
    elif changed == "policies":
        cases[0]["policies"][0] += " Changed policy context."
    else:
        cases[0]["questions"][0]["text"] += " Changed wording."
    monkeypatch.setattr(comparison.reference, "reference_inputs", lambda root: copy.deepcopy(cases))
    after = comparison.build_plan(fixed)
    assert before["tasks"][0]["task_id"] != after["tasks"][0]["task_id"]
    assert before["tasks"][1]["task_id"] == after["tasks"][1]["task_id"]
    cases[0]["case_id"] = "new-evaluator-name"
    assert comparison.build_plan(fixed)["tasks"][0]["task_id"] == after["tasks"][0]["task_id"]


def evidence(plan, name):
    return by_case(plan, name)["packets"]["evidence-assisted"]["payload"]["evidence"][0]


def test_evidence_preserves_partial_module_scope_diagnostics_and_deferred_owners(fixed):
    plan = comparison.build_plan(fixed)
    composed = evidence(plan, "composed-context-levels")
    assert all(item["source_id"].startswith("source-") for item in composed["modules"])
    assert {item["file"] for item in composed["modules"]} == {"main.py", "api/pockets.py"}
    assert composed["scope"] == "independent-modules-no-import-resolution"
    assert any(
        d["code"] == "unresolved-include-owner"
        for m in composed["modules"]
        for d in m["diagnostics"]
    )
    routes = [route for module in composed["modules"] for route in module["routes"]]
    assert [route["path"] for route in routes] == ["/pockets/recent"]
    assert routes[0]["file"] == "api/pockets.py"
    keyword = evidence(plan, "keyword-path-coverage")["modules"][0]
    assert [route["path"] for route in keyword["routes"]] == ["/ready"]
    assert "unsupported-route-arguments" in {item["code"] for item in keyword["diagnostics"]}
    factory = evidence(plan, "uncalled-factory-source")["modules"][0]["routes"][0]
    assert factory["registration"]["execution_scope"] == "deferred"
    owners = evidence(plan, "separate-application-owners")["modules"][0]["routes"]
    assert len({route["registration_id"] for route in owners}) == 2
    provider = evidence(plan, "unexpanded-provider-graph")["modules"][0]["routes"][0]
    assert [item["kind"] for item in provider["dependencies"]] == ["Depends"]
    assert all(item["scopes"] is None for item in provider["dependencies"])


def test_wrong_mode_response_is_not_reused_for_another_packet(fixed):
    task = comparison.build_plan(fixed)["tasks"][0]
    raw = comparison._mock_response(task["packets"]["model-only"]["payload"], None)
    spec = comparison._spec(task["packets"]["evidence-assisted"]["payload"])
    assert response.decode_response(spec, raw)["error"] == "request-id-mismatch"


@pytest.mark.parametrize("changed", ["instructions", "evidence"])
def test_request_ids_bind_instruction_and_evidence_changes_without_relabeling_tasks(
    fixed, monkeypatch, changed
):
    before = comparison.build_plan(fixed)["tasks"][0]
    if changed == "instructions":
        monkeypatch.setattr(comparison, "INSTRUCTIONS", comparison.INSTRUCTIONS + " Changed.")
    else:
        extract = comparison._declarations

        def changed_evidence(sources):
            data = extract(sources)
            data["limitations"].append("Additional explicit limitation.")
            return data

        monkeypatch.setattr(comparison, "_declarations", changed_evidence)
    after = comparison.build_plan(fixed)["tasks"][0]
    assert before["task_id"] == after["task_id"]
    for mode in comparison.MODES:
        differs = before["packets"][mode]["request_id"] != after["packets"][mode]["request_id"]
        assert differs == (changed == "instructions" or mode == "evidence-assisted")


def test_dry_run_stages_every_packet_and_response_before_any_reference_read(fixed, monkeypatch):
    original_decode = comparison.decode_response
    original_score = comparison.reference.score_reference
    decoded = []

    def observe_decode(spec, raw):
        decoded.append(spec.request_id)
        return original_decode(spec, raw)

    def observe_score(root, records):
        assert len(decoded) == 21
        assert len(records) == 7
        return original_score(root, records)

    monkeypatch.setattr(comparison, "decode_response", observe_decode)
    monkeypatch.setattr(comparison.reference, "score_reference", observe_score)
    result = comparison.dry_run(fixed)
    assert result["live_trials"] == 0
    assert result["model_quality_measured"] is False
    assert result["static_baseline_measured"] is False
    assert result["static_answer_adapter"] == "registered-source-query-v1"
    assert result["static_adapter_used"] is False
    assert set(result["modes"]) == set(comparison.MODES)
    assert "overall" not in result
    for mode in result["modes"].values():
        assert mode["response_origin"].startswith("synthetic-")
        assert all(item["status"] == "valid" for item in mode["responses"])
        counts = mode["calculation"]["overall"]["counts"]
        assert counts["questions"] == 21
        assert counts["answerable"] == 14
        assert counts["required_unknown"] == 7
        assert counts["correct_unknowns"] == 7
        assert counts["false_abstentions"] == 14
        assert counts["invalid_responses"] == 0
        assert all(value is None for value in mode["calculation"]["unmeasured"].values())


@pytest.mark.parametrize("fault", ["missing", "invalid"])
def test_failed_slots_preserve_denominators_without_crediting_unknown(fixed, fault):
    result = comparison.dry_run(fixed, fault=fault)
    for mode in result["modes"].values():
        assert mode["responses"][0]["status"] == fault
        counts = mode["calculation"]["overall"]["counts"]
        assert (
            counts["cases"],
            counts["questions"],
            counts["answerable"],
            counts["required_unknown"],
        ) == (7, 21, 14, 7)
        assert counts["invalid_responses"] == 1
        assert counts["missing_responses"] == (1 if fault == "missing" else 0)
        assert counts["invalid_questions"] == 3
        assert counts["correct_unknowns"] == 6
        assert counts["false_abstentions"] == 12


@pytest.mark.parametrize("fault", [None, "missing", "invalid"])
def test_dry_run_does_not_launch_subprocesses_or_network(fixed, monkeypatch, fault):
    def forbidden(*args, **kwargs):
        pytest.fail("synthetic dry-run cannot call providers, processes or network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = comparison.dry_run(fixed, fault=fault)
    assert result["provider_calls_by_this_tool"] == 0
    assert result["target_execution"] == "not-run"


@pytest.mark.parametrize(
    "args",
    [[], ["--dry-run"], ["--dry-run", "--fault", "missing"], ["--dry-run", "--fault", "invalid"]],
)
def test_cli_single_json_and_no_model_claims(fixed, monkeypatch, capsys, args):
    monkeypatch.setattr(comparison, "ROOT", fixed)
    assert comparison.main([*args, "--json"]) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert output.err == ""
    assert result["live_benchmark_ready"] is False
    assert result["provider_calls_by_this_tool"] == 0
    assert result["target_execution"] == "not-run"


@pytest.mark.parametrize("args", [[], ["--dry-run"]])
def test_cli_human_distinguishes_registered_adapter_from_synthetic_dry_run(
    fixed, monkeypatch, capsys, args
):
    monkeypatch.setattr(comparison, "ROOT", fixed)
    assert comparison.main(args) == 0
    output = capsys.readouterr().out
    assert "NO LIVE TRIALS" in output
    assert "Static adapter: registered source queries" in output
    if args:
        assert "not a static baseline or model-quality result" in output


def test_cli_integrity_failure_is_not_a_score(fixed, monkeypatch, capsys):
    monkeypatch.setattr(comparison, "ROOT", fixed)
    (fixed / comparison.reference.REFERENCE / "tasks.json").unlink()
    assert comparison.main(["--json"]) == 1
    assert json.loads(capsys.readouterr().out)["kind"] == "offline-comparison-error"


@pytest.mark.parametrize(
    "args", [["--fault", "missing"], ["--provider", "codex"], ["--model", "any"], ["--repeat", "2"]]
)
def test_cli_rejects_live_provider_config_and_unscoped_fault(args, capsys):
    with pytest.raises(SystemExit) as error:
        comparison.main(args)
    assert error.value.code == 2
    assert capsys.readouterr().err
