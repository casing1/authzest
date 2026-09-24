"""Unit-policy evidence is separate from static declarations or HTTP guarantees."""

import builtins
import copy
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from examples.fastapi_owner_policy import policy
from examples.fastapi_owner_policy.policy import Principal, Report, can_read_report
from typer.testing import CliRunner

from authzest.cli import app
from authzest.runner import ScanRunner

REPOSITORY = Path(__file__).resolve().parents[1]
EXAMPLE = REPOSITORY / "examples" / "fastapi_owner_policy"
CORPUS = json.loads(
    (Path(__file__).parent / "fixtures" / "owner_policy" / "cases.json").read_text(encoding="utf-8")
)
VALID_PRINCIPAL = Principal("alice", True, frozenset({"reports:read"}))
VALID_REPORT = Report("report-001", "alice")


def contexts(case):
    # Decode only; expected decisions are independently recorded in the JSON.
    principal = case["principal"]
    report = case["report"]
    return (
        None
        if principal is None
        else Principal(
            principal["subject"], principal["authenticated"], frozenset(principal["scopes"])
        ),
        None if report is None else Report(**report),
    )


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["id"])
def test_independently_authored_owner_policy_cases(case):
    principal, report = contexts(case)
    assert can_read_report(principal, report) is case["expected"]


def test_case_metadata_and_complete_three_condition_matrix():
    assert CORPUS["authorship"] == "assistant-authored expected values; not human-authored"
    assert CORPUS["policy_review"]["status"] == "criteria-approved-label-review-pending"
    approval = CORPUS["policy_review"]["approval"]
    assert approval["date"] == "2026-09-24"
    assert approval["individual_expected_labels"] == "not-independently-reviewed"
    assert approval["scope"].startswith("Policy criteria only:")
    assert CORPUS["frozen_evaluation_corpus"] is False
    assert len({case["id"] for case in CORPUS["cases"]}) == len(CORPUS["cases"])
    assert all(type(case["expected"]) is bool for case in CORPUS["cases"])
    matrix = [case for case in CORPUS["cases"] if case["category"] == "truth-table"]
    assert len(matrix) == 8
    assert {
        (
            case["principal"]["authenticated"],
            "reports:read" in case["principal"]["scopes"],
            case["principal"]["subject"] == case["report"]["owner_id"],
        )
        for case in matrix
    } == {
        (False, False, False),
        (False, False, True),
        (False, True, False),
        (False, True, True),
        (True, False, False),
        (True, False, True),
        (True, True, False),
        (True, True, True),
    }


@pytest.mark.parametrize(
    ("principal", "report"),
    [
        pytest.param(
            Principal("alice", 1, frozenset({"reports:read"})), VALID_REPORT, id="truthy-int"
        ),
        pytest.param(
            Principal("alice", "yes", frozenset({"reports:read"})), VALID_REPORT, id="truthy-str"
        ),
        pytest.param(
            Principal(1, True, frozenset({"reports:read"})), VALID_REPORT, id="subject-type"
        ),
        pytest.param(VALID_PRINCIPAL, Report("report-001", 1), id="owner-type"),
        pytest.param(VALID_PRINCIPAL, Report(1, "alice"), id="report-id-type"),
        pytest.param(Principal("alice", True, "reports:read"), VALID_REPORT, id="scope-string"),
        pytest.param(Principal("alice", True, ["reports:read"]), VALID_REPORT, id="scope-list"),
        pytest.param(
            Principal("alice", True, {"reports:read"}), VALID_REPORT, id="scope-mutable-set"
        ),
        pytest.param(Principal("alice", True, None), VALID_REPORT, id="scope-none"),
        pytest.param(
            Principal("alice", True, frozenset({"reports:read", 1})),
            VALID_REPORT,
            id="scope-member-type",
        ),
        pytest.param(object.__new__(Principal), VALID_REPORT, id="missing-principal-fields"),
        pytest.param(VALID_PRINCIPAL, object.__new__(Report), id="missing-report-fields"),
        pytest.param(
            {"subject": "alice", "authenticated": True, "scopes": frozenset({"reports:read"})},
            VALID_REPORT,
            id="untrusted-mapping",
        ),
    ],
)
def test_malformed_context_denies_without_raising(principal, report):
    assert can_read_report(principal, report) is False


def test_subclasses_are_not_accepted_as_trusted_context():
    class OtherPrincipal(Principal):
        pass

    class OtherReport(Report):
        pass

    assert (
        can_read_report(OtherPrincipal("alice", True, frozenset({"reports:read"})), VALID_REPORT)
        is False
    )
    assert can_read_report(VALID_PRINCIPAL, OtherReport("report-001", "alice")) is False


@pytest.mark.parametrize(
    ("value", "field"),
    [(VALID_PRINCIPAL, "subject"), (VALID_REPORT, "owner_id")],
)
def test_policy_context_is_frozen(value, field):
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, "changed")


def forbidden(*args, **kwargs):
    pytest.fail(
        "The maintained policy and static inventory must not execute target code or perform I/O"
    )


def test_pure_policy_has_no_io_and_preserves_inputs(monkeypatch):
    inputs = [(contexts(case), case["expected"]) for case in CORPUS["cases"]]
    snapshot = copy.deepcopy(inputs)
    with monkeypatch.context() as guard:
        for name in ("open", "exec", "eval"):
            guard.setattr(builtins, name, forbidden)
        for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
            guard.setattr(Path, name, forbidden)
        guard.setattr(os, "open", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(socket.socket, "connect", forbidden)
        for (principal, report), expected in inputs:
            assert can_read_report(principal, report) is expected
    assert inputs == snapshot


def forbid_target_execution(monkeypatch):
    original_import = builtins.__import__
    original_exec = builtins.exec

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in {"examples", "fastapi", "main", "policy"}, (
            "Static scanning must not import the example or its framework"
        )
        return original_import(name, *args, **kwargs)

    def guarded_exec(code, *args, **kwargs):
        filename = getattr(code, "co_filename", "").replace("\\", "/")
        assert "/examples/fastapi_owner_policy/" not in filename, (
            "Static scanning must not execute example code"
        )
        return original_exec(code, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "exec", guarded_exec)
    monkeypatch.setattr(policy, "can_read_report", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def test_static_scan_preserves_declaration_evidence_without_executing_example(monkeypatch):
    source_lines = (EXAMPLE / "main.py").read_text(encoding="utf-8").splitlines()
    with monkeypatch.context() as guard:
        forbid_target_execution(guard)
        payload = ScanRunner().run(EXAMPLE).to_dict()

    assert payload["python_files"] == 2
    assert payload["route_count"] == 1
    assert payload["analysis_status"] == "bounded"
    assert payload["diagnostics"] == payload["parse_errors"] == []
    assert payload["codex_status"] == "disabled"
    route = payload["routes"][0]
    assert (route["path"], route["methods"], route["function"]) == (
        "/reports/{report_id}",
        ["GET"],
        "read_report",
    )
    assert route["file"] == "main.py"
    assert source_lines[route["line"] - 1].startswith("def read_report(")
    assert len(route["dependencies"]) == 1
    assert route["dependencies"] == route["effective_dependencies"]
    dependency = route["dependencies"][0]
    assert dependency["kind"] == "Security"
    assert dependency["target"] == "require_authenticated_principal"
    assert dependency["declaration_level"] == "parameter-annotation"
    assert dependency["parameter"] == "principal"
    assert dependency["scopes"] == ["reports:read"]
    assert dependency["resolution"] == "reference"
    assert dependency["unresolved_reasons"] == []
    location = dependency["location"]
    assert location["file"] == "main.py"
    assert source_lines[location["line"] - 1][location["column"] - 1 :].startswith("Security(")
    declaration = route["registration"]["declaration"]
    assert declaration["file"] == "main.py"
    assert source_lines[declaration["line"] - 1].startswith('@app.get("/reports/{report_id}")')
    assert "authorization_verdict" not in payload
    assert "allowed" not in route


def test_static_cli_text_and_json_agree_without_running_example(monkeypatch):
    runner = CliRunner()
    with monkeypatch.context() as guard:
        forbid_target_execution(guard)
        text_result = runner.invoke(app, ["scan", str(EXAMPLE)])
        json_result = runner.invoke(app, ["scan", str(EXAMPLE), "--json", "--strict"])

    assert text_result.exit_code == json_result.exit_code == 0
    assert text_result.stderr == json_result.stderr == ""
    payload = json.loads(json_result.stdout)
    route = payload["routes"][0]
    assert f"Python files: {payload['python_files']}" in text_result.stdout
    assert f"FastAPI routes: {payload['route_count']}" in text_result.stdout
    assert route["path"] in text_result.stdout
    assert f"(main.py:{route['line']})" in text_result.stdout
    assert "require_authenticated_principal" in text_result.stdout
    assert 'Declared scopes: ["reports:read"]' in text_result.stdout
    assert "not a security verdict" in text_result.stdout
    assert "not access-control guarantees" in text_result.stdout
    assert payload["codex_status"] == "disabled"
