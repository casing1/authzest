"""Synchronous fake-session CLI checks; no Docker, AI or generated code runs."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from authzest import _generated_repair_cli as flow
from authzest.cli import app
from authzest.cli_output import WorkflowOutput, format_generated_file_workflow_result
from authzest.codex.contracts import canonical
from authzest.codex.generated_repair import prepare_generated_repair_preview
from authzest.codex.generated_repair_transport import build_generated_repair_transport_request
from authzest.runner import codex_generated_repair
from authzest.runner._generated_repair_session import (
    GeneratedRepairSessionPlan,
    GeneratedRepairSessionResult,
)
from authzest.runner.codex_generated_repair import build_generated_repair_sharing_preview
from test_codex_generate_cli import fake_result
from test_generated_repair_runtime_profile import profile
from test_generated_repair_transport import inner

MODEL = "offline-file-flow-model"


def generation(status="proposed-change"):
    sharing = build_generated_repair_sharing_preview(MODEL, invocation_nonce="b" * 32)
    request = build_generated_repair_transport_request(MODEL)
    checked = fake_result(request, status).to_dict()
    proposal = flow.validate_generated_repair_proposal(
        canonical(checked["proposal"]), inner(request)
    )
    return {
        "kind": "codex-generated-repair-workflow",
        "status": "generation-ready",
        "exit_code": 0,
        **{
            key: sharing[key]
            for key in (
                "request_id",
                "generation_request_id",
                "sharing_id",
                "sharing_content_id",
                "invocation_nonce",
                "limits",
            )
        },
        "sharing_decision": "approve",
        "application_turn_attempts": 1,
        "generation": checked,
        "proposal_status": status,
        "proposal_preview": prepare_generated_repair_preview(proposal, inner(request)).to_dict(),
        "returned_identity": checked["identity"],
        "usage": checked["usage"],
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "applied": False,
        "original_checkout_modified": False,
        "authorization_status": "unknown",
    }


class RuntimeInput:
    def __init__(self):
        self.profile = profile()
        self.calls, self.closed, self.close_failure = 0, False, False

    def assert_current(self):
        self.calls += 1

    def review_dict(self):
        return {"profile": self.profile.to_dict(), "provenance": "fake-unverified", "ready": False}

    def close(self):
        self.closed = True
        if self.close_failure:
            raise OSError("FAKE_PRIVATE_PATH")


class FakeSession:
    def __init__(self, world, preview, *, runtime_profile, runtime_guard):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        assert preview.to_dict()["proposal_status"] == "proposed-change"
        assert runtime_profile == world.runtime.profile
        self.world, self.guard, self.plans = world, runtime_guard, {}
        self.data = {
            "session_nonce": "a" * 32,
            "stages": {
                stage: {"status": "not-run", "decision": "pending"} for stage in flow._ACTIONS
            },
            "workspace": {"path": None, "state": "not-created"},
            "execution_status": "not-run",
            "source_application": "not-run",
            "restoration_status": "not-run",
            "baseline": "not-established",
            "cleanup_unconfirmed": False,
            "authorization_status": "unknown",
            "checks": {"before": None, "after": None},
            "closed": False,
        }
        world.sessions.append(self)

    def prepare(self, stage):
        self.world.prepared.append(stage)
        if stage == self.world.prepare_failure or (
            stage == "restore" and (self.data["cleanup_unconfirmed"] or self.world.edited)
        ):
            raise ValueError("Current stage unavailable")
        value = GeneratedRepairSessionPlan(
            canonical(
                {
                    "stage": stage,
                    "session_nonce": self.data["session_nonce"],
                    "expires_at": 300,
                    "exact_diff": "--- app.py\n+++ app.py\n+# maintained fake payload\n",
                }
            )
        )
        self.plans[stage] = value
        return value

    def decide(self, stage, choice, *, plan_id):
        assert self.plans[stage].plan_id == plan_id
        self.data["stages"][stage]["decision"] = choice

    def _action(self, stage):
        self.guard()
        self.world.actions.append(stage)
        if stage == self.world.interrupt_stage:
            raise self.world.interruption
        if stage == self.world.fail_stage:
            self.data["stages"][stage]["status"] = "failed"
            self.data["cleanup_unconfirmed"] = self.world.cleanup_unconfirmed
            return self.result()
        if stage == "source-apply" and self.world.partial_apply:
            self.data["source_application"] = "state-unconfirmed"
            self.data["workspace"]["state"] = "state-unconfirmed"
            self.data["stages"][stage]["status"] = "state-unconfirmed"
            return self.result()
        self.data["stages"][stage]["status"] = flow._SUCCESS[stage]
        if stage == "copy":
            self.data["workspace"].update(path="/inert/private-copy", state="ready-before")
        elif stage in ("before", "after"):
            self.data["execution_status"] = "completed"
            self.data["checks"][stage] = {
                "status": "complete",
                "test_exit_code": 1 if stage == "before" else 0,
                "cleanup_confirmed": True,
                "comparison": {
                    "matching_case_count": 17,
                    "case_count": 17,
                    "matching_request_count": 21,
                    "request_count": 21,
                },
            }
            if stage == "before":
                self.data["baseline"] = "intended-before-defect-observed"
        elif stage == "source-apply":
            self.data["source_application"] = "applied-copy-only"
            self.data["workspace"]["state"] = "applied-after"
        elif stage == "restore":
            self.data["restoration_status"] = "restored-before"
            self.data["workspace"]["state"] = "restored-before"
        return self.result()

    def create_copy(self):
        return self._action("copy")

    def run_before(self):
        return self._action("before")

    def accept_diff(self):
        return self._action("source-diff")

    def apply_source(self):
        return self._action("source-apply")

    def run_after(self):
        return self._action("after")

    def restore_source(self):
        return self._action("restore")

    def result(self):
        return GeneratedRepairSessionResult(canonical(self.data))

    def close(self):
        self.data["closed"] = True
        if self.world.close_interruption is not None:
            raise self.world.close_interruption


@pytest.fixture
def world(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Fake CLI flow cannot execute a process or use a network")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    value = SimpleNamespace(
        runtime=RuntimeInput(),
        sessions=[],
        prepared=[],
        actions=[],
        previews=[],
        choices={},
        fail_stage=None,
        interrupt_stage=None,
        interruption=KeyboardInterrupt(),
        close_interruption=None,
        prepare_failure=None,
        cleanup_unconfirmed=False,
        edited=False,
        partial_apply=False,
        generation_calls=0,
    )
    monkeypatch.setattr(
        flow, "GeneratedRepairSession", lambda *args, **kwargs: FakeSession(value, *args, **kwargs)
    )

    def emit(text):
        value.previews.append(json.loads(text))

    def read(prompt):
        phrase = prompt.split("'")[1]
        stage = phrase.split()[0]
        answer = value.choices.get(stage, phrase)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    value.emit, value.read = emit, read
    return value


def invoke(world, result=None):
    return flow.run_generated_file_workflow(
        generation() if result is None else result,
        model=MODEL,
        timeout_seconds=120,
        runtime_input=world.runtime,
        emit=world.emit,
        read=world.read,
    )


def test_full_current_generation_proceeds_synchronously_through_independent_choices(world):
    result = invoke(world)
    assert world.actions == list(flow._ACTIONS)
    assert result["status"] == "file-workflow-complete" and result["exit_code"] == 0
    assert result["file_workflow"]["session_result"]["closed"] is True
    assert result["patch_application"] == "applied-copy-only"
    assert result["restoration_status"] == "restored-before"
    assert result["original_checkout_modified"] is False
    previews = [item for item in world.previews if item["kind"].endswith("preview")]
    assert len(previews) == len({item["confirmation_phrase"] for item in previews}) == 6
    assert all("exact_diff" in item["plan"] for item in previews)


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_non_change_proposals_exit_without_copy_or_runtime_guard(world, status):
    result = invoke(world, generation(status))
    assert result["file_workflow"]["status"] == "no-proposed-change"
    assert world.sessions == [] and world.runtime.calls == 0


@pytest.mark.parametrize(
    "field",
    [
        "sharing_id",
        "limits",
        "returned_identity",
        "usage",
        "proposal_preview",
    ],
)
def test_tampered_current_generation_cannot_create_copy(world, field):
    result = generation()
    result[field] = None
    actual = invoke(world, result)
    assert actual["status"] == "file-workflow-failed" and actual["exit_code"] == 1
    assert world.sessions == []


@pytest.mark.parametrize("answer", ["", "yes", "cancel", "copy old-nonce old-plan"])
def test_copy_decline_cancel_or_stale_phrase_never_acts(world, answer):
    world.choices["copy"] = answer
    result = invoke(world)
    assert world.actions == [] and world.prepared == ["copy"]
    assert result["file_workflow"]["status"] in {"declined", "cancelled"}


@pytest.mark.parametrize("stage", ["before", "source-diff", "source-apply"])
def test_decline_before_application_stops_later_actions(world, stage):
    world.choices[stage] = ""
    result = invoke(world)
    assert stage not in world.actions and "restore" not in world.prepared
    assert result["patch_application"] == "not-run"


def test_after_decline_still_requires_a_separate_restore_choice(world):
    world.choices["after"] = ""
    result = invoke(world)
    assert "after" not in world.actions and world.actions[-1] == "restore"
    assert result["restoration_status"] == "restored-before"
    assert result["status"] == "file-workflow-declined"


def test_clean_after_failure_can_restore_but_remains_failed(world):
    world.fail_stage = "after"
    result = invoke(world)
    assert result["status"] == "file-workflow-failed" and result["exit_code"] == 1
    assert result["restoration_status"] == "restored-before"


@pytest.mark.parametrize("problem", ["cleanup", "user-edit"])
def test_uncertain_or_user_edited_after_does_not_force_restore(world, problem):
    world.fail_stage = "after"
    world.cleanup_unconfirmed = problem == "cleanup"
    world.edited = problem == "user-edit"
    result = invoke(world)
    assert "restore" not in world.actions
    assert result["file_workflow"]["restore_status"] == "unavailable-or-failed"


@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt(), SystemExit(7)])
def test_global_input_interruption_stops_prompts_and_retains_applied_copy(world, error):
    world.choices["after"] = error
    result = invoke(world)
    assert result["exit_code"] == 130 and result["status"] == "file-workflow-cancelled"
    assert "restore" not in world.prepared
    assert result["patch_application"] == "applied-copy-only"


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(7)])
def test_phase_cancellation_retains_checkpoint_without_automatic_restoration(world, error):
    world.interrupt_stage = "after"
    world.interruption = error
    result = invoke(world)
    assert result["exit_code"] == 130 and world.actions[-1] == "after"
    assert "restore" not in world.prepared and result["patch_application"] == "applied-copy-only"


def test_system_exit_at_restore_input_stops_interaction_and_retains_applied_copy(world):
    world.choices["restore"] = SystemExit(7)
    result = invoke(world)
    assert result["exit_code"] == 130 and result["status"] == "file-workflow-cancelled"
    assert world.actions[-1] == "after"
    assert result["patch_application"] == "applied-copy-only"
    assert result["restoration_status"] == "not-run"


def test_system_exit_during_session_close_retains_prior_application_and_restore(world):
    world.close_interruption = SystemExit(7)
    result = invoke(world)
    assert result["exit_code"] == 130 and result["status"] == "file-workflow-cancelled"
    assert result["patch_application"] == "applied-copy-only"
    assert result["restoration_status"] == "restored-before"
    assert result["file_workflow"]["close_status"] == "cancelled-unconfirmed"


def test_human_result_is_compact_and_escapes_untrusted_paths(world):
    result = invoke(world)
    result["file_workflow"]["session_result"]["workspace"]["path"] = "/inert/\u009b31m\u202e"
    rendered = format_generated_file_workflow_result(result)
    assert "Independent cases: 17/17" in rendered and "Independent requests: 21/21" in rendered
    assert "observations are historical" in rendered
    assert "\u009b" not in rendered and "\\u009b" in rendered
    assert "\u202e" not in rendered and "\\u202e" in rendered
    assert "after_text" not in rendered and "test_text" not in rendered


def configure_cli(world, monkeypatch):
    monkeypatch.setattr(flow, "prepare_file_runtime", lambda _: world.runtime)
    monkeypatch.setattr(WorkflowOutput, "read", lambda _, prompt: world.read(prompt))

    async def generated(model, **kwargs):
        world.generation_calls += 1
        assert model == MODEL
        return generation()

    monkeypatch.setattr(codex_generated_repair, "run_codex_generated_repair", generated)


def test_public_cli_runs_full_flow_after_event_loop_and_prints_single_json(world, monkeypatch):
    configure_cli(world, monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    value = json.loads(result.stdout)
    assert value["kind"] == "codex-generated-file-workflow"
    assert value["status"] == "file-workflow-complete"
    assert world.generation_calls == 1 and world.runtime.closed is True
    assert '"confirmation_phrase"' in result.stderr and '"exact_diff"' in result.stderr
    assert "not sent to" not in result.stdout


@pytest.mark.parametrize("choice,code", [("", 0), ("cancel", 130), ("runtime-review old old", 0)])
def test_runtime_review_decline_stops_before_any_generation(world, monkeypatch, choice, code):
    configure_cli(world, monkeypatch)
    world.choices["runtime-review"] = choice
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--json",
        ],
    )
    assert result.exit_code == code
    value = json.loads(result.stdout)
    assert value["status"].startswith("runtime-review-")
    assert value["application_turn_attempts"] == world.generation_calls == 0
    assert world.sessions == [] and world.runtime.closed is True


def test_file_preview_is_one_complete_local_sharing_split_without_prompts(world, monkeypatch):
    configure_cli(world, monkeypatch)
    monkeypatch.setattr(WorkflowOutput, "read", lambda *_: pytest.fail("Preview cannot prompt"))
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--preview-only",
            "--json",
        ],
    )
    assert result.exit_code == 0
    value = json.loads(result.stdout)
    assert value["kind"] == "codex-generated-file-workflow-preview"
    assert value["runtime_review_preview"]["local_only"] is True
    assert "runtime_review_preview" not in value["sharing_preview"]["transport_request"]
    assert world.generation_calls == 0 and world.sessions == [] and world.runtime.closed is True


@pytest.mark.parametrize(
    "args",
    [
        ["--file-workflow"],
        ["--runtime-profile", "/fake/profile"],
    ],
)
def test_invalid_option_pair_fails_before_runtime_loader_or_provider(world, monkeypatch, args):
    configure_cli(world, monkeypatch)
    monkeypatch.setattr(flow, "prepare_file_runtime", lambda *_: pytest.fail("No loader"))
    result = CliRunner().invoke(app, ["codex-generate", "--model", MODEL, "--json", *args])
    assert result.exit_code == 2 and json.loads(result.stdout)["status"] == "invalid-input"
    assert world.generation_calls == 0


def test_runtime_descriptor_close_failure_preserves_completed_effects(world, monkeypatch):
    configure_cli(world, monkeypatch)
    world.runtime.close_failure = True
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--json",
        ],
    )
    assert result.exit_code == 1
    value = json.loads(result.stdout)
    assert value["patch_application"] == "applied-copy-only"
    assert value["restoration_status"] == "restored-before"
    assert value["file_workflow"]["runtime_input_cleanup"] == "unconfirmed"
    assert "FAKE_PRIVATE_PATH" not in result.stdout + result.stderr


def test_public_cli_system_exit_after_apply_keeps_one_checkpoint_json(world, monkeypatch):
    configure_cli(world, monkeypatch)
    world.interrupt_stage, world.interruption = "after", SystemExit(7)
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--json",
        ],
    )
    assert result.exit_code == 130
    value = json.loads(result.stdout)
    assert value["status"] == "file-workflow-cancelled"
    assert value["patch_application"] == "applied-copy-only"
    assert value["execution_status"] == "completed"
    assert "restore" not in world.prepared


def test_partial_application_is_unknown_in_single_json_and_never_blindly_restored(
    world, monkeypatch
):
    configure_cli(world, monkeypatch)
    world.partial_apply = True
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--json",
        ],
    )
    assert result.exit_code == 1
    value = json.loads(result.stdout)
    assert value["applied"] is None
    assert value["patch_application"] == "state-unconfirmed"
    assert value["current_copy_state"] == "state-unconfirmed"
    assert "after" not in world.prepared and "restore" not in world.prepared
    assert "Applied (historical): unknown" in format_generated_file_workflow_result(value)


@pytest.mark.parametrize("prompt_stage", ["runtime-review", "share"])
@pytest.mark.parametrize("mutation", ["edit", "replace"])
def test_profile_change_in_prompt_blocks_provider_and_copy(
    world, monkeypatch, tmp_path, prompt_stage, mutation
):
    from authzest.runner import _generated_repair_runtime_input as runtime_input
    from test_generated_repair_runtime_input import _declaration

    if not runtime_input._supported():
        pytest.skip("POSIX private profile input scope")
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    path = parent / "runtime.json"
    raw = canonical(_declaration()).encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    loaded = runtime_input.prepare_generated_runtime_input(path)
    monkeypatch.setattr(flow, "prepare_file_runtime", lambda _: loaded)
    original = codex_generated_repair.run_codex_generated_repair
    adapter_calls = []

    def no_adapter(**kwargs):
        adapter_calls.append(kwargs)
        pytest.fail("Changed local runtime must not consume a provider turn")

    async def generated(model, **kwargs):
        world.generation_calls += 1
        return await original(model, **kwargs, adapter_factory=no_adapter)

    monkeypatch.setattr(codex_generated_repair, "run_codex_generated_repair", generated)

    def read(_, prompt):
        phrase = prompt.split("'")[1]
        if phrase.split()[0] == prompt_stage:
            if mutation == "edit":
                path.write_bytes(raw + b"\n")
            else:
                replacement = path.with_name("replacement.json")
                replacement.write_bytes(raw)
                replacement.chmod(0o600)
                os.replace(replacement, path)
        return phrase

    monkeypatch.setattr(WorkflowOutput, "read", read)
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            str(path),
            "--json",
        ],
    )
    assert result.exit_code == 2, result.stdout + result.stderr
    value = json.loads(result.stdout)
    assert value["status"] == "invalid-input" and value["application_turn_attempts"] == 0
    assert value["execution_status"] == value["patch_application"] == "not-run"
    assert world.sessions == [] and adapter_calls == []
    assert loaded._closed is True


def test_public_cli_actual_owned_file_session_with_fake_phase_applies_and_restores(
    world, monkeypatch
):
    from authzest.runner import _generated_repair_session as session_module
    from authzest.runner._generated_repair_phase import (
        MAX_PHASE_RESULT_BYTES,
        GeneratedRepairPhaseResult,
    )
    from test_generated_repair_session_live import phase_data

    configure_cli(world, monkeypatch)
    monkeypatch.setattr(flow, "GeneratedRepairSession", session_module.GeneratedRepairSession)
    observed = []

    def phase(workspace, candidate, runtime, **options):
        options["evidence_budget"].charge(MAX_PHASE_RESULT_BYTES)
        options["dispatch_guard"]()
        observed.append((candidate, workspace.read_source().data))
        return GeneratedRepairPhaseResult(
            canonical(phase_data(workspace, candidate, runtime, options))
        )

    monkeypatch.setattr(session_module, "execute_generated_repair_phase", phase)
    result = CliRunner().invoke(
        app,
        [
            "codex-generate",
            "--model",
            MODEL,
            "--file-workflow",
            "--runtime-profile",
            "/fake/profile",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    value = json.loads(result.stdout)
    checkpoint = value["file_workflow"]["session_result"]
    assert value["status"] == "file-workflow-complete"
    assert [candidate for candidate, _ in observed] == ["before", "after"]
    assert observed[0][1] != observed[1][1]
    assert checkpoint["closed"] is True
    assert checkpoint["restoration_status"] == "restored-before"
    assert checkpoint["poc_exit_pattern"] == "before-1-after-0"
    assert Path(checkpoint["workspace"]["path"], "app.py").read_bytes() == observed[0][1]
