"""Exercise the public file workflow with inert files and fake runtime/provider channels."""

import asyncio
import builtins
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from authzest.cli import app
from authzest.cli_output import WorkflowOutput
from authzest.codex import app_server
from authzest.owner_read_demo.checks import owner_read_controls
from authzest.runner import _owner_read_copy_files as copies
from authzest.runner import _owner_read_workflow as workflow
from authzest.runner._owner_read_phase_result import validate_owner_read_phase

SOURCE = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_owner_archive(owner_client):\n"
    '    assert owner_client.get("/records/archived-note").status_code == 200\n'
)
ARGS = [
    "owner-read-suggest",
    "--model",
    "offline-owner-file",
    "--file-workflow",
    "--runtime-config",
    "/fake/runtime.json",
]


def _evidence(capture):
    before = capture["phase"] == "before"
    rows = owner_read_controls()
    base = {
        "kind": "owner-read-guest-observation",
        "schema_version": "1.0",
        "source_sha256": capture["source_sha256"],
        "test_sha256": capture["test_sha256"],
    }
    regression = {
        "status": "assertion-failed" if before else "passed",
        "pytest_exit": int(before),
        "collected": 1,
        "setup": "passed",
        "call": "failed" if before else "passed",
        "teardown": "passed",
        "requests": 1,
        "response": rows[1]["before" if before else "intended"],
    }
    records = {
        "test": {**base, "role": "test", "regression": regression},
        "controls": {
            **base,
            "role": "controls",
            "observations": [
                {"case_id": row["case_id"], **row["before" if before else "intended"]}
                for row in rows
            ],
        },
    }
    captures = {
        role: {
            "exit_code": 0,
            "stdout": json.dumps(value).encode(),
            "stderr": b"",
            "cleanup_confirmed": True,
        }
        for role, value in records.items()
    }
    return validate_owner_read_phase(
        phase=capture["phase"],
        plan_id=capture["plan_id"],
        source_sha256=capture["source_sha256"],
        test_sha256=capture["test_sha256"],
        captures=captures,
    )


@pytest.fixture
def dialogue(monkeypatch, tmp_path):
    monkeypatch.setattr(copies, "_TEMP_PARENT", tmp_path)
    events, calls, runtimes, previews = [], [], [], []
    options = {
        "preflight": "ready",
        "proposal": "proposed-change",
        "provider_cancel": False,
        "decision": None,
    }

    class Runtime:
        def __init__(self, path):
            self.closed = False
            runtimes.append(self)

        def to_dict(self):
            return {"image_id": "sha256:" + "a" * 64, "endpoint": "unix:///fake/docker.sock"}

        def review_dict(self):
            return {"profile": self.to_dict(), "runtime_id": "owner-read-runtime-fake"}

        def check(self):
            assert not self.closed
            if options.get("runtime_changed"):
                raise workflow.OwnerReadRuntimeError("runtime-file-changed")

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    class Dispatcher:
        def __init__(self, runtime):
            self.runtime = runtime

        def preflight(self, *, guard):
            guard()
            events.append("preflight")
            return {"status": options["preflight"], "cleanup_confirmed": True}

        def __call__(self, capture, *, guard):
            guard()
            events.append(capture["phase"])
            assert capture["source_sha256"] == hashlib.sha256(capture["source"]).hexdigest()
            return _evidence(capture)

        def observations(self):
            return [{"scope": "fake-dispatcher", "events": list(events)}]

    def factory(**kwargs):
        async def suggest(request):
            events.append("provider")
            calls.append(request.to_dict())
            if options["provider_cancel"]:
                raise asyncio.CancelledError
            status = options["proposal"]
            return {
                "request_id": request.request_id,
                "status": status,
                "source": SOURCE if status == "proposed-change" else None,
                "test": TEST if status == "proposed-change" else None,
                "rationale": "Offline CLI fixture.",
            }

        return SimpleNamespace(suggest_owner_read=suggest)

    original_emit = WorkflowOutput.emit

    def emit(self, text):
        previews.append(json.loads(text))
        original_emit(self, text)

    def respond():
        preview = previews[-1]
        if preview["kind"] == "owner-read-runtime-review":
            stage, identifier = "runtime", preview["runtime_review_id"]
        elif preview["kind"] == "owner-read-sharing-preview":
            stage, identifier = "share", preview["sharing_id"]
        else:
            stage, identifier = preview["stage"], preview["plan_id"]
        if stage == "share" and options.get("runtime_drift_at_share"):
            options["runtime_changed"] = True
        if options["decision"] == stage:
            return "cancel"
        return stage + " " + identifier

    monkeypatch.setattr(workflow, "OwnerReadRuntime", Runtime)
    monkeypatch.setattr(workflow, "OwnerReadDockerDispatcher", Dispatcher)
    monkeypatch.setattr(app_server, "CodexAppServerAdapter", factory)
    monkeypatch.setattr(WorkflowOutput, "emit", emit)
    monkeypatch.setattr(builtins, "input", respond)
    return options, events, calls, runtimes, previews, tmp_path


def test_public_cli_single_json_full_workflow_is_restored(dialogue):
    _, events, calls, runtimes, previews, _ = dialogue
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    assert result.exit_code == 0, result.exception
    value = json.loads(result.stdout)
    assert events == ["preflight", "provider", "before", "after"]
    assert len(calls) == 1 and value["application_turn_attempts"] == 1
    assert value["execution_status"] == "completed"
    assert value["patch_application"] == "applied-to-copy"
    assert value["restoration_status"] == "restored"
    session = value["file_workflow"]
    assert session["status"] == "completed" and not session["recovery_required"]
    assert session["before"]["comparison"]["intended_matches"] == 6
    assert session["after"]["comparison"]["intended_matches"] == 7
    assert runtimes[0].closed and value["runtime_descriptor_cleanup_confirmed"]
    plans = [preview for preview in previews if preview["kind"] == "owner-read-file-stage-plan"]
    assert [plan["stage"] for plan in plans] == [
        "copy",
        "before",
        "diff",
        "apply",
        "after",
        "restore",
    ]
    assert all(
        plan["runtime"]["profile"]["endpoint"] == "unix:///fake/docker.sock" for plan in plans
    )
    assert "/fake/docker.sock" not in calls[0]["prompt"]
    root = Path(session["copy"]["path"])
    assert (root / "availability.py").read_text() == calls[0]["source"]["text"]
    assert (root / "test_owner_archived_read.py").read_text() == TEST
    assert "owner-read-runtime-review" in result.stderr


def test_human_summary_shows_observation_and_recovery(dialogue):
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 0, result.exception
    assert "File workflow: completed" in result.stdout
    assert "Restoration: restored" in result.stdout
    assert "independent checks 6/7" in result.stdout
    assert "independent checks 7/7" in result.stdout
    assert "Recovery required: false" in result.stdout


def test_unavailable_runtime_stops_before_provider_or_copy(dialogue):
    options, events, calls, runtimes, _, parent = dialogue
    options["preflight"] = "failed"
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    assert result.exit_code == 2
    value = json.loads(result.stdout)
    assert value["status"] == "runtime-unavailable"
    assert value["application_turn_attempts"] == 0
    assert events == ["preflight"] and calls == []
    assert list(parent.iterdir()) == [] and runtimes[0].closed


@pytest.mark.parametrize(
    "stage", ["runtime", "share", "copy", "before", "diff", "apply", "after", "restore"]
)
def test_public_workflow_cancel_never_approves_a_later_stage(dialogue, stage):
    options, events, calls, _, previews, _ = dialogue
    options["decision"] = stage
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    assert result.exit_code == 130, result.exception
    value = json.loads(result.stdout)
    if stage == "runtime":
        assert not events and not calls
    elif stage == "share":
        assert events == ["preflight"] and not calls
    elif stage in ("copy", "before"):
        assert events == ["preflight", "provider"]
    else:
        assert len(calls) == 1
    if stage in ("after", "restore"):
        assert value["file_workflow"]["recovery_required"] is True
    assert previews[-1].get("stage", stage) == stage


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_no_proposed_change_allocates_no_copy_or_guest(dialogue, status):
    options, events, _, _, _, parent = dialogue
    options["proposal"] = status
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    value = json.loads(result.stdout)
    assert result.exit_code == 0 and value["status"] == status
    assert events == ["preflight", "provider"]
    assert value["file_workflow"]["status"] == "not-started"
    assert list(parent.iterdir()) == []


def test_provider_cancellation_keeps_attempt_and_runtime_evidence(dialogue):
    options, events, _, runtimes, _, _ = dialogue
    options["provider_cancel"] = True
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    assert result.exit_code == 130
    value = json.loads(result.stdout)
    assert value["status"] == "cancelled" and value["application_turn_attempts"] == 1
    assert value["runtime_preflight"]["status"] == "ready"
    assert value["runtime_observations"] and runtimes[0].closed
    assert events == ["preflight", "provider"]


def test_offline_preview_has_runtime_and_sharing_without_prompts_or_preflight(dialogue):
    _, events, calls, runtimes, _, parent = dialogue
    result = CliRunner().invoke(app, [*ARGS, "--preview-only", "--json"])
    assert result.exit_code == 0, result.exception
    value = json.loads(result.stdout)
    assert value["kind"] == "owner-read-file-offline-preview"
    assert value["status"] == "preview-only" and value["runtime_review"]
    assert events == [] and calls == [] and runtimes[0].closed
    assert result.stderr == "" and list(parent.iterdir()) == []


@pytest.mark.parametrize(
    "options",
    [
        ["--file-workflow"],
        ["--runtime-config", "/fake/runtime.json"],
        ["--file-workflow", "--runtime-config", "/fake/runtime.json", "--prepare-copy"],
    ],
)
def test_invalid_mode_combination_stops_before_side_effects(dialogue, options):
    _, events, calls, runtimes, _, _ = dialogue
    result = CliRunner().invoke(
        app, ["owner-read-suggest", "--model", "offline-owner-file", *options, "--json"]
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "invalid-input"
    assert events == [] and calls == [] and runtimes == []


def test_post_provider_initialization_failure_preserves_proposal_and_attempt(dialogue, monkeypatch):
    from authzest.codex.contracts import ContractError
    from authzest.runner import _owner_read_file_session as sessions

    def failed_session(**kwargs):
        raise ContractError("Synthetic changed input after provider returned")

    monkeypatch.setattr(sessions, "OwnerReadFileSession", failed_session)
    _, events, calls, runtimes, _, parent = dialogue
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    assert result.exit_code == 1, result.exception
    value = json.loads(result.stdout)
    assert value["status"] == "file-workflow-unavailable"
    assert value["application_turn_attempts"] == 1 and len(calls) == 1
    assert value["proposal"]["status"] == "proposed-change"
    assert value["runtime_preflight"]["status"] == "ready"
    assert events == ["preflight", "provider"]
    assert list(parent.iterdir()) == [] and runtimes[0].closed


def test_runtime_edit_during_share_prompt_stops_before_provider(dialogue):
    options, events, calls, runtimes, _, parent = dialogue
    options["runtime_drift_at_share"] = True
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    assert result.exit_code == 2, result.exception
    value = json.loads(result.stdout)
    assert value["application_turn_attempts"] == 0
    assert value["status"] == "runtime-unavailable"
    assert events == ["preflight"] and calls == []
    assert list(parent.iterdir()) == [] and runtimes[0].closed


def test_runtime_constructor_failure_keeps_descriptor_cleanup_evidence(dialogue, monkeypatch):
    def failed_runtime(path):
        error = workflow.OwnerReadRuntimeError("runtime-input-unavailable")
        error.runtime_descriptor_cleanup_confirmed = False
        raise error

    monkeypatch.setattr(workflow, "OwnerReadRuntime", failed_runtime)
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    value = json.loads(result.stdout)
    assert result.exit_code == 2
    assert value["runtime_descriptor_cleanup_confirmed"] is False
    assert value["application_turn_attempts"] == 0


def test_runtime_observation_interruption_still_closes_profile(dialogue, monkeypatch):
    dispatcher = workflow.OwnerReadDockerDispatcher

    class InterruptedObservation(dispatcher):
        def observations(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(workflow, "OwnerReadDockerDispatcher", InterruptedObservation)
    _, _, _, runtimes, _, _ = dialogue
    result = CliRunner().invoke(app, [*ARGS, "--json"])
    value = json.loads(result.stdout)
    assert result.exit_code == 130 and value["status"] == "cancelled"
    assert value["runtime_observations_status"] == "unconfirmed"
    assert value["file_workflow"]["restoration_status"] == "restored"
    assert value["file_workflow"]["recovery_required"] is True
    assert value["runtime_descriptor_cleanup_confirmed"] is True and runtimes[0].closed
