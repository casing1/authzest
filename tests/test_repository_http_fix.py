"""Interactive HTTP repair flow with owned files, a fake provider and fake phases."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import subprocess
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.helpers.repository_http_engine_data import profile_data
from tests.helpers.repository_http_verification_data import AFTER, POLICY, SOURCE, case_data, inputs
from typer.testing import CliRunner

from authzest.analyzer.repository_origin import capture_repository_origin
from authzest.cli import app
from authzest.codex.contracts import canonical
from authzest.codex.repository_http_proposal import build_repository_http_request
from authzest.runner import repository_http_fix as module
from authzest.runner._repository_http_phase import RepositoryHttpPhaseResult
from authzest.runner._repository_http_staging import supported
from authzest.runner.repository_http_verification import _binding

pytestmark = pytest.mark.skipif(not supported(), reason="POSIX external repair flow scope")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("the flow test must not execute or connect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


class Answers:
    """Accept or decline each prompt in order by echoing its exact code."""

    def __init__(self, *choices):
        self.choices = list(choices)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        choice = self.choices.pop(0) if self.choices else "decline"
        if choice == "decline":
            return ""
        match = re.search(r"Type '([^']+)'", prompt)
        return match.group(1)


class Project:
    def __init__(self, tmp_path, *, poc=None, status="proposed-change", cases_source=None):
        self.root = (tmp_path / "project").resolve()
        self.root.mkdir()
        (self.root / "app.py").write_text(SOURCE)
        (self.root / "policy.md").write_text(POLICY)
        origin = capture_repository_origin(self.root, "app.py", "policy.md")
        request = build_repository_http_request(origin.snapshot, "offline-model")
        origin.close()
        data = case_data(request)
        if cases_source is not None:
            data["basis"]["source_sha256"] = sha256(cases_source.encode()).hexdigest()
        self.cases = tmp_path / "cases.json"
        self.cases.write_text(json.dumps(data))
        folder = tmp_path / "private-profile"
        folder.mkdir(mode=0o700)
        self.profile = folder / "runtime.json"
        self.profile.write_text(canonical(profile_data()))
        self.profile.chmod(0o600)
        self.recovery = tmp_path / "recovery"
        response = inputs()[1]
        response["request_id"] = request.request_id
        response["proposal"]["before_sha256"] = sha256(SOURCE.encode()).hexdigest()
        if poc is not None:
            response["proposal"]["poc"] = poc
        if status != "proposed-change":
            response.update(status=status, proposal=None)
        self.response = response
        self.adapter_calls = 0
        self.phase_calls = []
        self.criteria = {"before": True, "after": True}
        self.phase_hook = lambda *_: None
        self.steps = []

    def adapter(self, **_kwargs):
        async def suggest(request):
            self.adapter_calls += 1
            return self.response

        return SimpleNamespace(suggest_repository_http=suggest)

    def phase(self, session, request, response, cases, plan, profile, **options):
        phase = options["phase"]
        assert options["dispatch_guard"]() is None
        self.phase_calls.append(phase)
        self.phase_hook(phase)
        text = SOURCE if phase == "before" else AFTER
        payload = {
            "kind": "repository-http-phase-result",
            "phase": phase,
            "status": "complete",
            "failure": None,
            "criteria_met": self.criteria[phase],
            "file_session_id": session._session_id,
            "file_session_revision": session._revision,
            "plan_id": plan.plan_id,
            "source_sha256": sha256(text.encode()).hexdigest(),
            "comparison": {
                "phase": phase,
                "binding": _binding(plan.to_dict(), phase),
                "designated_regression_case_id": "other",
                "frame_status": "valid-supplied",
                "cleanup_supplied_confirmed": True,
                "supplied_before_differs_from_desired_after": self.criteria[phase]
                if phase == "before"
                else None,
                "supplied_criteria_met": self.criteria[phase],
                "planned_cases": 5,
                "counts": {"match": 5, "mismatch": 0, "error": 0, "not-dispatched": 0},
                "outcomes": [
                    {"case_id": name, "outcome": "match", "reason": "matches-supplied-" + phase}
                    for name in ("owner", "other", "anonymous", "normal", "public")
                ],
            },
            "cleanup_confirmed": True,
            "cleanup_errors": [],
            "engine_transport_cleanup_confirmed": True,
            "relay_capture": {"status": "complete", "failure": None},
            "relay_capture_failure": None,
            "stage_initialization_failure": None,
            "owned": [
                {"role": role, "create_attempted": True, "absence_observed": True}
                for role in ("A", "B")
            ],
            "runtime_attempted": True,
            "schedule_sha256": "c" * 64,
            "evidence_directory": "/owned/" + phase,
            "captures": [],
            "runtime_metadata": {},
        }
        return RepositoryHttpPhaseResult(canonical(payload))

    def emit(self, text):
        value = json.loads(text)
        self.steps.append(value.get("step") or value.get("kind"))

    def run(self, answers, *, clock=None):
        return asyncio.run(
            module.run_repository_http_fix(
                self.root,
                "app.py",
                "policy.md",
                "offline-model",
                cases_path=self.cases,
                profile_path=self.profile,
                recovery_parent=self.recovery,
                emit=self.emit,
                read=answers,
                adapter_factory=self.adapter,
                phase_runner=self.phase,
                **({"clock": clock} if clock else {}),
            )
        )


ALL = ("accept",) * 6


def test_complete_flow_applies_original_with_recovery_record(tmp_path):
    project = Project(tmp_path)
    result = project.run(Answers(*ALL))
    assert result["status"] == "original-applied" and result["exit_code"] == 0
    assert result["verified_fix"] is True and result["original_checkout_modified"] is True
    assert (project.root / "app.py").read_text() == AFTER
    assert project.phase_calls == ["before", "after"]
    record = Path(result["original"]["record_path"])
    assert (record / "before.py").read_text() == SOURCE
    assert result["restore_command"] == "authzest repo-restore " + str(record)
    assert result["original"]["verification"]["before_phase_evidence"] == "/owned/before"
    assert "captures" not in result["before_phase"]
    assert result["private_copy"]["state"] == "applied-after"
    assert project.steps.index("before-phase-finished") < project.steps.index("proposed-diff")
    assert project.steps.index("after-phase-finished") < project.steps.index("original-preview")


def test_declined_sharing_never_calls_provider(tmp_path):
    project = Project(tmp_path)
    result = project.run(Answers("decline"))
    assert result["status"] == "not-shared" and project.adapter_calls == 0
    assert project.phase_calls == [] and (project.root / "app.py").read_text() == SOURCE


@pytest.mark.parametrize(
    ("answers", "status", "phases"),
    [
        (("accept", "decline"), "copy-declined", []),
        (("accept", "accept", "decline"), "before-declined", []),
        (("accept", "accept", "accept", "decline"), "private-apply-declined", ["before"]),
        (("accept",) * 4 + ("decline",), "after-declined", ["before"]),
    ],
)
def test_each_effect_needs_its_own_answer(tmp_path, answers, status, phases):
    project = Project(tmp_path)
    result = project.run(Answers(*answers))
    assert result["status"] == status and result["exit_code"] == 0
    assert project.phase_calls == phases
    assert (project.root / "app.py").read_text() == SOURCE
    assert result["original_checkout_modified"] is False


def test_declining_original_keeps_verified_private_result(tmp_path):
    project = Project(tmp_path)
    result = project.run(Answers(*ALL[:5], "decline"))
    assert result["status"] == "original-declined" and result["verified_fix"] is True
    assert (project.root / "app.py").read_text() == SOURCE
    assert not project.recovery.exists()


def test_before_not_reproduced_stops_before_diff(tmp_path):
    project = Project(tmp_path)
    project.criteria["before"] = False
    result = project.run(Answers(*ALL))
    assert result["status"] == "before-not-reproduced" and result["exit_code"] == 1
    assert "proposed-diff" not in project.steps and project.phase_calls == ["before"]


def test_after_not_verified_never_offers_original(tmp_path):
    project = Project(tmp_path)
    project.criteria["after"] = False
    result = project.run(Answers(*ALL))
    assert result["status"] == "after-not-verified" and result["verified_fix"] is False
    assert "original-preview" not in project.steps
    assert (project.root / "app.py").read_text() == SOURCE


def test_original_edit_during_flow_is_a_conflict(tmp_path):
    project = Project(tmp_path)

    def edit(phase):
        if phase == "after":
            (project.root / "app.py").write_text(SOURCE + "# concurrent edit\n")

    project.phase_hook = edit
    result = project.run(Answers(*ALL))
    assert result["status"] == "original-conflict" and result["exit_code"] == 1
    assert (project.root / "app.py").read_text() == SOURCE + "# concurrent edit\n"
    assert result["original_checkout_modified"] is False


def test_case_basis_mismatch_stops_before_sharing(tmp_path):
    project = Project(tmp_path, cases_source="different source\n")
    result = project.run(Answers(*ALL))
    assert result["status"] == "invalid-input"
    assert result["failure"]["code"] == "case-basis-mismatch"
    assert project.adapter_calls == 0 and project.steps == []


def test_poc_outside_designated_case_is_refused(tmp_path):
    poc = {
        "method": "GET",
        "path": "/items/two",
        "headers": [{"name": "x-user", "value": "test-x"}],
    }
    project = Project(tmp_path, poc=poc)
    result = project.run(Answers(*ALL))
    assert result["status"] == "poc-not-covered" and result["failure"]["poc"] == poc
    assert project.phase_calls == []


def test_no_change_proposal_ends_cleanly(tmp_path):
    project = Project(tmp_path, status="no-change")
    result = project.run(Answers(*ALL))
    assert result["status"] == "no-proposed-change" and result["exit_code"] == 0


def test_expired_answer_is_refused(tmp_path):
    project = Project(tmp_path)
    times = iter([0.0, 301.0])

    def clock():
        return next(times, 1000.0)

    result = project.run(Answers(*ALL), clock=clock)
    assert result["status"] == "decision-expired" and project.phase_calls == []


def test_cli_preview_only_prints_case_basis(tmp_path):
    project = Project(tmp_path)
    runner = CliRunner()
    outcome = runner.invoke(
        app,
        [
            "repo-fix",
            str(project.root),
            "--source",
            "app.py",
            "--policy",
            "policy.md",
            "--model",
            "offline-model",
            "--preview-only",
            "--json",
        ],
    )
    assert outcome.exit_code == 0, outcome.output
    value = json.loads(outcome.stdout)
    assert value["kind"] == "repository-http-fix-preview"
    assert value["case_basis"] == json.loads(project.cases.read_text())["basis"]


def test_cli_restore_round_trip(tmp_path, monkeypatch):
    project = Project(tmp_path)
    result = project.run(Answers(*ALL))
    record = result["original"]["record_path"]
    runner = CliRunner()
    declined = runner.invoke(app, ["repo-restore", record, "--json"], input="\n")
    assert json.loads(declined.stdout)["status"] == "restore-declined"
    assert "Type 'restore " in declined.stderr
    assert (project.root / "app.py").read_text() == AFTER
    import secrets

    monkeypatch.setattr(secrets, "token_hex", lambda _n: "abcdef")
    restored = runner.invoke(app, ["repo-restore", record, "--json"], input="restore abcdef\n")
    assert json.loads(restored.stdout)["status"] == "restored", restored.output
    assert (project.root / "app.py").read_text() == SOURCE
    again = runner.invoke(app, ["repo-restore", record, "--json"], input="\n")
    assert json.loads(again.stdout)["status"] == "restore-refused"


def test_phase_runner_refusal_is_a_failed_result(tmp_path):
    from authzest.runner._repository_http_phase import RepositoryHttpPhaseError

    project = Project(tmp_path)

    def refuse(*_args, **_kwargs):
        raise RepositoryHttpPhaseError("invalid-private-http-phase-context")

    project.phase = refuse
    result = project.run(Answers(*ALL))
    assert result["status"] == "before-phase-failed" and result["exit_code"] == 1
    assert result["failure"] == {"code": "invalid-private-http-phase-context", "phase": "before"}
    assert (project.root / "app.py").read_text() == SOURCE


def test_partial_sharing_phrase_is_explained(tmp_path):
    project = Project(tmp_path)

    def only_identifier(prompt):
        return re.search(r"Type 'share ([^']+)'", prompt).group(1)

    result = project.run(only_identifier)
    assert result["status"] == "not-shared" and project.adapter_calls == 0
    assert result["failure"]["code"] == "sharing-phrase-mismatch"


def test_blank_sharing_answer_is_a_plain_decline(tmp_path):
    project = Project(tmp_path)
    result = project.run(Answers("decline"))
    assert result["status"] == "not-shared" and result["failure"] is None


def test_late_private_effect_never_extends_the_answer_deadline(tmp_path):
    project = Project(tmp_path)
    # copy prompt issued at 0, answered at 299 (valid), effect reached at 301.
    times = iter([0.0, 299.0, 301.0])

    def clock():
        return next(times, 1000.0)

    result = project.run(Answers(*ALL), clock=clock)
    assert result["status"] == "decision-expired" and result["exit_code"] == 1
    assert result["private_copy"]["private_root"] is None
    assert project.phase_calls == []
