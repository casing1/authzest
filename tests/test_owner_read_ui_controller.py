"""Owned UI threads, inert plans and fake workflows; no provider or container execution."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path

import pytest

from authzest.api._owner_read_controller import (
    MAX_PLAN_BYTES,
    MAX_RESULT_BYTES,
    OwnerReadUIController,
    UIWorkflowError,
)
from authzest.codex.contracts import identity


def packet(stage, **extra):
    if stage == "runtime":
        value = {"kind": "owner-read-runtime-review", "schema_version": "1.0", **extra}
        key, prefix = "runtime_review_id", "owner-read-runtime-"
    elif stage == "share":
        value = {"kind": "owner-read-sharing-preview", **extra}
        key, prefix = "sharing_id", "share-"
    else:
        value = {
            "kind": "owner-read-file-stage-plan",
            "schema_version": "1.0",
            "stage": stage,
            **extra,
        }
        key, prefix = "plan_id", "owner-read-stage-"
    value[key] = prefix + identity(value)
    return value


def expected(plan):
    kind = plan["kind"]
    if kind == "owner-read-runtime-review":
        return "runtime " + plan["runtime_review_id"]
    if kind == "owner-read-sharing-preview":
        return "share " + plan["sharing_id"]
    return plan["stage"] + " " + plan["plan_id"]


def outcome(status="not-shared", **extra):
    return {
        "kind": "owner-read-suggestion",
        "schema_version": "1.0",
        "status": status,
        "exit_code": 130 if status == "cancelled" else 0,
        "execution_status": "not-run",
        "patch_application": "not-run",
        **extra,
    }


def wait_for(controller, predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = controller.current()
        if value is not None and predicate(value):
            return value
        time.sleep(0.005)
    pytest.fail("Owned controller did not reach the expected state")


@pytest.fixture
def controllers():
    owned, gates = [], []

    def create(workflow, **options):
        controller = OwnerReadUIController(
            Path("/inert/runtime.json"), workflow=workflow, **options
        )
        owned.append(controller)
        return controller

    create.gates = gates
    yield create
    for gate in gates:
        gate.set()
    for controller in owned:
        assert controller.close(timeout_seconds=3), "Owned test worker must not leak"


def one_prompt(stage="runtime", *, answers=None, **fields):
    async def workflow(_model, *, emit, read, **_options):
        plan = packet(stage, **fields)
        emit(json.dumps(plan))
        answer = read("Type '" + expected(plan) + "' to continue, or press Enter to decline: ")
        if answers is not None:
            answers.append(answer)
        return outcome("cancelled" if answer == "cancel" else "not-shared")

    return workflow


def test_constructor_and_idle_snapshot_do_not_open_profile_or_execute(monkeypatch):
    import os
    import socket
    import subprocess

    def forbidden(*_args, **_kwargs):
        pytest.fail("Constructing an idle controller must not access a runtime")

    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    controller = OwnerReadUIController(Path("/missing/runtime.json"))
    assert controller.current() is None
    assert controller.close() is True


def test_exact_current_answer_replay_and_detached_snapshots(controllers):
    answers = []
    controller = controllers(one_prompt(answers=answers))
    started = controller.start("offline-model")
    assert set(started) == {
        "run_id",
        "revision",
        "state",
        "events",
        "pending",
        "view",
        "view_error",
        "result_available",
        "failure",
        "cancel_requested",
    }
    assert len(started["run_id"]) == 32 and int(started["run_id"], 16) >= 0
    waiting = wait_for(controller, lambda value: value["pending"] is not None)
    prompt = waiting["pending"]
    assert len(prompt["prompt_id"]) == 32
    assert set(prompt) == {"prompt_id", "stage", "prompt", "plan", "remaining_seconds"}
    assert prompt["remaining_seconds"] <= 300
    with pytest.raises(UIWorkflowError) as error:
        controller.decide(started["run_id"], prompt["prompt_id"], "wrong approval")
    assert error.value.status_code == 422
    assert controller.current()["pending"]["prompt_id"] == prompt["prompt_id"]
    answer = expected(prompt["plan"])
    prompt["plan"]["kind"] = "changed detached value"
    waiting["events"][0]["status"] = "changed detached event"
    assert controller.current()["pending"]["plan"]["kind"] == "owner-read-runtime-review"
    response = controller.decide(started["run_id"], prompt["prompt_id"], answer)
    assert response["pending"] is None and response["revision"] > waiting["revision"]
    with pytest.raises(UIWorkflowError) as error:
        controller.decide(started["run_id"], prompt["prompt_id"], answer)
    assert error.value.status_code == 409
    finished = wait_for(controller, lambda value: value["state"] == "finished")
    assert answers == [answer]
    assert finished["view"]["provenance"] == "imported-unverified"
    assert json.loads(controller.download(started["run_id"]))["status"] == "not-shared"
    finished["view"]["summary"]["status"] = "changed detached view"
    assert controller.current()["view"]["summary"]["status"] == "not-shared"


def test_one_active_lease_and_current_prompt_for_every_stage(controllers):
    stages = ("runtime", "share", "copy", "before", "diff", "apply", "after", "restore")
    answers = []

    async def workflow(_model, *, emit, read, **_):
        for stage in stages:
            plan = packet(stage)
            emit(json.dumps(plan))
            answers.append(read("Type '" + expected(plan) + "' for this stage: "))
        return outcome()

    controller = controllers(workflow)
    run = controller.start("offline-model")
    ids, revisions = [], []
    for stage in stages:
        waiting = wait_for(
            controller,
            lambda value: value["pending"] is not None and value["pending"]["prompt_id"] not in ids,
        )
        assert waiting["pending"]["stage"] == stage
        assert waiting["revision"] > run["revision"]
        with pytest.raises(UIWorkflowError) as error:
            controller.start("overlapping-model")
        assert error.value.code == "run-active"
        prompt = waiting["pending"]
        ids.append(prompt["prompt_id"])
        revisions.append(waiting["revision"])
        controller.decide(run["run_id"], prompt["prompt_id"], expected(prompt["plan"]))
    finished = wait_for(controller, lambda value: value["state"] == "finished")
    assert len(set(ids)) == 8 and revisions == sorted(revisions)
    assert len(answers) == 8 and len(finished["events"]) <= 256
    assert all(set(event) == {"sequence", "stage", "status"} for event in finished["events"])


def test_wrong_run_and_prompt_cannot_approve_current_plan(controllers):
    controller = controllers(one_prompt())
    run = controller.start("offline-model")
    waiting = wait_for(controller, lambda value: value["pending"] is not None)
    prompt = waiting["pending"]
    for run_id, prompt_id in (("a" * 32, prompt["prompt_id"]), (run["run_id"], "b" * 32)):
        with pytest.raises(UIWorkflowError):
            controller.decide(run_id, prompt_id, expected(prompt["plan"]))
    assert controller.current()["pending"]["prompt_id"] == prompt["prompt_id"]


def test_cancel_wakes_pending_read_and_retains_core_cancel_result(controllers):
    answers = []
    controller = controllers(one_prompt(answers=answers))
    run = controller.start("offline-model")
    wait_for(controller, lambda value: value["pending"] is not None)
    cancelled = controller.cancel(run["run_id"])
    assert cancelled["cancel_requested"] is True and cancelled["pending"] is None
    finished = wait_for(controller, lambda value: value["state"] in ("finished", "failed"))
    assert answers == ["cancel"]
    assert finished["state"] == "finished"
    assert json.loads(controller.download(run["run_id"]))["status"] == "cancelled"


def test_cancel_running_async_workflow_is_cooperative(controllers):
    entered, cleaned = threading.Event(), threading.Event()

    async def workflow(_model, **_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    controller = controllers(workflow)
    run = controller.start("offline-model")
    assert entered.wait(1)
    controller.cancel(run["run_id"])
    finished = wait_for(controller, lambda value: value["state"] == "failed")
    assert cleaned.is_set() and finished["cancel_requested"] is True
    assert finished["failure"] == "workflow-interrupted" and not finished["result_available"]


def test_sync_worker_keeps_lease_during_stop_and_shutdown(controllers):
    entered, gate = threading.Event(), threading.Event()
    controllers.gates.append(gate)

    async def workflow(_model, **_):
        entered.set()
        assert gate.wait(2)
        return outcome()

    controller = controllers(workflow)
    run = controller.start("offline-model")
    assert entered.wait(1) and controller._run.thread.daemon is False
    stopped = controller.cancel(run["run_id"])
    assert stopped["state"] == "stopping"
    with pytest.raises(UIWorkflowError) as error:
        controller.start("second")
    assert error.value.code == "run-active"
    assert controller.close(timeout_seconds=0.01) is False
    assert controller.current()["state"] == "stopping"
    gate.set()
    assert controller.close(timeout_seconds=2) is True


def test_pending_expiry_cannot_be_extended_by_polling_or_late_answer(controllers):
    now = [10.0]
    answers = []
    controller = controllers(one_prompt(answers=answers), clock=lambda: now[0])
    run = controller.start("offline-model")
    waiting = wait_for(controller, lambda value: value["pending"] is not None)
    prompt = waiting["pending"]
    now[0] += 301
    expired = controller.snapshot(run["run_id"])
    assert expired["pending"] is None and expired["failure"] == "prompt-expired"
    with pytest.raises(UIWorkflowError) as error:
        controller.decide(run["run_id"], prompt["prompt_id"], expected(prompt["plan"]))
    assert error.value.status_code == 409
    wait_for(controller, lambda value: value["state"] in ("finished", "failed"))
    assert answers == ["cancel"]


@pytest.mark.parametrize("answer", ["x" * 257, None, True])
def test_oversized_or_wrong_typed_answer_does_not_consume_prompt(controllers, answer):
    controller = controllers(one_prompt())
    run = controller.start("offline-model")
    waiting = wait_for(controller, lambda value: value["pending"] is not None)
    with pytest.raises(UIWorkflowError) as error:
        controller.decide(run["run_id"], waiting["pending"]["prompt_id"], answer)
    assert error.value.status_code == 422
    assert controller.current()["pending"] is not None


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        '{"kind":1,"kind":2}',
        json.dumps(packet("runtime", schema_version="2.0")),
        json.dumps({**packet("runtime"), "runtime_review_id": "forged"}),
        json.dumps({"kind": "other-plan"}),
    ],
)
def test_malformed_unsupported_or_unbound_plans_fail_without_raw_error_text(controllers, raw):
    async def workflow(_model, *, emit, **_):
        emit(raw)
        return outcome()

    controller = controllers(workflow)
    controller.start("offline-model")
    failed = wait_for(controller, lambda value: value["state"] == "failed")
    assert failed["failure"] == "plan-invalid"
    assert not failed["result_available"] and failed["pending"] is None


def test_plan_size_refusal_and_complete_large_current_plan(controllers):
    async def oversized(_model, *, emit, **_):
        emit("x" * (MAX_PLAN_BYTES + 1))
        return outcome()

    controller = controllers(oversized)
    controller.start("offline-model")
    failed = wait_for(controller, lambda value: value["state"] == "failed")
    assert failed["failure"] == "plan-too-large"
    complete = controllers(one_prompt(padding="x" * 700000))
    complete.start("offline-model")
    waiting = wait_for(complete, lambda value: value["pending"] is not None)
    assert len(waiting["pending"]["plan"]["padding"]) == 700000


def test_prompt_text_must_bind_to_its_current_full_plan(controllers):
    async def workflow(_model, *, emit, read, **_):
        emit(json.dumps(packet("runtime")))
        read("Type 'runtime stale-plan' to continue: ")
        return outcome()

    controller = controllers(workflow)
    controller.start("offline-model")
    failed = wait_for(controller, lambda value: value["state"] == "failed")
    assert failed["failure"] == "plan-invalid"


def test_raw_result_download_survives_bounded_view_projection_failure(controllers):
    async def workflow(_model, **_):
        return outcome(raw_capture="x" * 600000)

    controller = controllers(workflow)
    run = controller.start("offline-model")
    finished = wait_for(controller, lambda value: value["state"] == "finished")
    assert finished["result_available"] is True and finished["view"] is None
    assert finished["view_error"] == "result-view-unavailable"
    assert len(json.loads(controller.download(run["run_id"]))["raw_capture"]) == 600000


@pytest.mark.parametrize("kind", ["oversized", "invalid", "nan"])
def test_invalid_or_oversized_final_result_is_never_a_successful_attachment(controllers, kind):
    async def workflow(_model, **_):
        return (
            outcome(raw="x" * MAX_RESULT_BYTES)
            if kind == "oversized"
            else []
            if kind == "invalid"
            else {"value": float("nan")}
        )

    controller = controllers(workflow)
    run = controller.start("offline-model")
    failed = wait_for(controller, lambda value: value["state"] == "failed")
    assert failed["failure"] == ("result-too-large" if kind == "oversized" else "result-invalid")
    assert failed["result_available"] is False
    with pytest.raises(UIWorkflowError) as error:
        controller.download(run["run_id"])
    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "model,timeout",
    [("contains whitespace", 120), ("ok", True), ("ok", 121), ("ok", 0), ("ok", float("nan"))],
)
def test_invalid_start_does_not_create_a_worker(controllers, model, timeout):
    controller = controllers(one_prompt())
    with pytest.raises(UIWorkflowError) as error:
        controller.start(model, timeout_seconds=timeout)
    assert error.value.status_code == 422 and controller.current() is None


def test_finished_run_is_replaced_only_after_its_worker_ends(controllers):
    async def workflow(_model, **_):
        return outcome()

    controller = controllers(workflow)
    first = controller.start("offline-model")
    wait_for(controller, lambda value: value["state"] == "finished")
    controller._run.thread.join(1)
    second = controller.start("offline-model")
    assert second["run_id"] != first["run_id"]
    with pytest.raises(UIWorkflowError) as error:
        controller.snapshot(first["run_id"])
    assert error.value.status_code == 404


@pytest.mark.skipif(os.name != "posix", reason="Private copy operations require POSIX")
@pytest.mark.parametrize("choice", ["approve", "decline-after", "cancel-after"])
def test_existing_core_full_copy_check_apply_restore_flow_uses_browser_broker(
    controllers, monkeypatch, tmp_path, choice
):
    from helpers.fake_owner_read_ui import core_workflow

    workflow = core_workflow(monkeypatch, tmp_path)
    controller = controllers(workflow)
    run = controller.start("offline-ui-core")
    stages = []
    prompt_ids = []
    while True:
        value = wait_for(
            controller,
            lambda value: (
                value["state"] in ("finished", "failed")
                or value["pending"] is not None
                and value["pending"]["prompt_id"] not in prompt_ids
            ),
        )
        if value["state"] in ("finished", "failed"):
            break
        prompt = value["pending"]
        prompt_ids.append(prompt["prompt_id"])
        stages.append(prompt["stage"])
        answer = expected(prompt["plan"])
        if prompt["stage"] == "after" and choice != "approve":
            answer = "" if choice == "decline-after" else "cancel"
        controller.decide(run["run_id"], prompt["prompt_id"], answer)
    assert value["state"] == "finished", value
    assert stages == ["runtime", "share", "copy", "before", "diff", "apply", "after"] + (
        [] if choice == "cancel-after" else ["restore"]
    )
    raw = json.loads(controller.download(run["run_id"]))
    if choice == "cancel-after":
        from test_owner_read_file_session import SOURCE

        assert raw["file_workflow"]["status"] == "cancelled"
        assert raw["file_workflow"]["recovery_required"] is True
        assert raw["file_workflow"]["restoration_status"] == "required"
        assert (
            Path(raw["file_workflow"]["copy"]["path"]) / "availability.py"
        ).read_text() == SOURCE
        assert value["view"]["summary"]["recovery_required"] is True
        return
    assert raw["file_workflow"]["status"] == ("completed" if choice == "approve" else "declined")
    assert raw["application_turn_attempts"] == 1
    assert (Path(raw["file_workflow"]["copy"]["path"]) / "availability.py").read_text() == raw[
        "source_evidence"
    ]["source"]["text"]
    assert value["view"]["summary"]["recovery_required"] is False
    assert value["view"]["session"]["checks"]["before"]["comparison"]["intended_match_count"] == 6
    if choice == "approve":
        assert (
            value["view"]["session"]["checks"]["after"]["comparison"]["intended_match_count"] == 7
        )
    else:
        assert value["view"]["session"]["checks"]["after"] is None
        assert raw["file_workflow"]["restoration_status"] == "restored"


def test_fractional_clock_keeps_pending_time_within_original_limit(controllers):
    now = [900.0000000000003]
    controller = controllers(one_prompt(), clock=lambda: now[0])
    controller.start("offline-model")
    waiting = wait_for(controller, lambda value: value["pending"] is not None)
    assert 0 < waiting["pending"]["remaining_seconds"] <= 300
    assert controller._run.pending.deadline - now[0] <= 300


def test_repeated_cancel_does_not_interrupt_owned_async_cleanup(controllers):
    entered, cleanup_started, cleanup_finished = (threading.Event() for _ in range(3))

    async def workflow(_model, **_):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup_started.set()
            await asyncio.sleep(0.05)
            cleanup_finished.set()
            return outcome("cancelled")

    controller = controllers(workflow)
    run = controller.start("offline-model")
    assert entered.wait(1)
    controller.cancel(run["run_id"])
    assert cleanup_started.wait(1)
    controller.cancel(run["run_id"])
    controller.cancel(run["run_id"])
    finished = wait_for(controller, lambda value: value["state"] in ("finished", "failed"))
    assert finished["state"] == "finished" and cleanup_finished.is_set()
    assert json.loads(controller.download(run["run_id"]))["status"] == "cancelled"
