"""Adversarial in-memory consent checks; maintained candidate text stays inert."""

from __future__ import annotations

import ast
import asyncio
import base64
import builtins
import inspect
import math
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.codex.generated_repair import (
    build_generated_repair_request,
    validate_generated_repair_proposal,
)
from authzest.runner import _generated_repair_session as session
from authzest.runner import _generated_repair_workspace as io
from authzest.runner import generated_repair_controls as controls
from authzest.runner.generated_repair_verification import (
    GeneratedRepairExecutorReadiness,
    GeneratedRepairVerificationPreview,
    build_generated_repair_verification_preview,
)

TRACKED_FILES = (
    "app.py",
    "tests/test_generated_ownership.py",
    "before.txt",
    "after.txt",
    "test.txt",
    "record.json",
)
POSIX_COPY = pytest.mark.skipif(not io.supported(), reason="POSIX private-copy operations")


class Clock:
    def __init__(self, value=1000.0):
        self.value = value
        self.calls = 0
        self.callback = None

    def __call__(self):
        self.calls += 1
        callback, self.callback = self.callback, None
        if callback is not None:
            callback()
        return self.value


@pytest.fixture(autouse=True)
def maintained_text_is_never_executed(monkeypatch, request, tmp_path):
    assert len(request.node.nodeid) < 512
    # Python 3.14 may lazily initialize this maintained stdlib implementation.
    assert ast.unparse(ast.Constant(value=None)) == "None"

    def forbidden(*args, **kwargs):
        pytest.fail("Session tests must not execute candidate code or external effects")

    original_import = builtins.__import__
    original_compile = builtins.compile

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "fastapi",
            "uvicorn",
            "httpx",
            "requests",
            "openai",
            "docker",
            "app",
        } or name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    def ast_only_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def _preview(status="proposed-change"):
    request = build_generated_repair_request()
    data = request.to_dict()
    source = data["scenario"]["source"]
    proposal = validate_generated_repair_proposal(
        canonical(
            {
                "schema_version": "1.0",
                "request_id": request.request_id,
                "status": status,
                "rationale": "Maintained inert consent regression, not a repair.",
                "evidence_ids": list(data["evidence_ids"].values()),
                "assumptions": ["No candidate Python is executed."],
                "uncertainties": ["No runtime observation is available."],
                "limitations": ["This is only private file-I/O coordination."],
                "proposal": {
                    "source_path": "app.py",
                    "before_sha256": source["sha256"],
                    "after_text": source["text"] + "\n# Inert maintained consent fixture.\n",
                    "test_path": "tests/test_generated_ownership.py",
                    "test_text": "# Maintained inert text; never collected or executed.\n",
                }
                if status == "proposed-change"
                else None,
            }
        ),
        request,
    )
    return build_generated_repair_verification_preview(request, proposal)


@pytest.fixture
def live():
    clock = Clock()
    coordinator = session.GeneratedRepairSession(_preview(), clock=clock)
    yield coordinator, clock
    if not coordinator.result().to_dict()["closed"]:
        coordinator.close()


def _stage(coordinator, name):
    return coordinator.result().to_dict()["stages"][name]


def _approve(coordinator, stage="copy", *, lifetime_seconds=300):
    plan = coordinator.prepare(stage)
    coordinator.decide(
        stage,
        "approved",
        plan_id=plan.plan_id,
        lifetime_seconds=lifetime_seconds,
    )
    return plan


def _copied(monkeypatch, tmp_path, coordinator):
    captured = []
    original = io.GeneratedRepairWorkspace.__init__

    def record_copy(workspace, *args, **kwargs):
        original(workspace, *args, **kwargs)
        captured.append(workspace)

    monkeypatch.setattr(io.GeneratedRepairWorkspace, "__init__", record_copy)
    _approve(coordinator)
    coordinator.create_copy(_parent=tmp_path)
    assert len(captured) == 1
    return captured[0]


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_nonchange_preflight_never_allocates(monkeypatch, tmp_path, status):
    monkeypatch.setattr(
        io.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("No copy for non-change")
    )
    coordinator = session.GeneratedRepairSession(_preview(status), clock=Clock())
    try:
        with pytest.raises((session.GeneratedRepairSessionError, ContractError)):
            coordinator.prepare("copy")
        coordinator.create_copy(_parent=tmp_path)
        assert coordinator.result().to_dict()["workspace"]["path"] is None
        assert list(tmp_path.iterdir()) == []
    finally:
        coordinator.close()


@pytest.mark.parametrize("mutation", ["wrong-type", "authority", "request", "proposal"])
def test_forged_preview_never_allocates(monkeypatch, mutation):
    preview = _preview()
    if mutation == "wrong-type":
        forged = preview.to_dict()
    else:
        data = preview.to_dict()
        if mutation == "authority":
            data["execution_authorized"] = True
        elif mutation == "request":
            data["request_id"] = "different-request"
        else:
            data["proposal_preview"]["proposal"]["proposal"]["after_text"] += "# changed\n"
        forged = GeneratedRepairVerificationPreview(canonical(data))
    monkeypatch.setattr(
        io.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("No copy for forged preview")
    )
    with pytest.raises((session.GeneratedRepairSessionError, ContractError)):
        session.GeneratedRepairSession(forged)


@pytest.mark.parametrize(
    "value", [True, False, None, "1000", float("nan"), float("inf"), -float("inf")]
)
def test_nonfinite_or_non_numeric_initial_clock_is_refused(value):
    with pytest.raises(session.GeneratedRepairSessionError):
        session.GeneratedRepairSession(_preview(), clock=lambda: value)


@pytest.mark.parametrize("value", [True, False, None, "1", 0, -1, 301, float("nan"), float("inf")])
def test_invalid_decision_lifetime_never_replaces_pending_decision(live, value):
    coordinator, _ = live
    plan = coordinator.prepare("copy")
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=value)
    assert _stage(coordinator, "copy")["decision"] == "pending"
    assert _stage(coordinator, "copy")["attempted"] is False


def test_plan_and_result_are_immutable_detached_snapshots(live):
    coordinator, _ = live
    plan = coordinator.prepare("copy")
    result = coordinator.result()
    raw_plan, raw_result = plan.payload_json, result.payload_json
    detached = plan.to_dict()
    detached.clear()
    detached_result = result.to_dict()
    detached_result["stages"]["copy"]["decision"] = "approved"
    assert plan.payload_json == raw_plan
    assert result.payload_json == raw_result
    assert _stage(coordinator, "copy")["decision"] == "pending"
    with pytest.raises((FrozenInstanceError, AttributeError)):
        plan.payload_json = "{}"
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.payload_json = "{}"


@pytest.mark.parametrize("stage", ["before", "source-diff", "source-apply", "after", "restore"])
def test_wrong_stage_cannot_authorize_a_copy(live, tmp_path, stage):
    coordinator, _ = live
    plan = coordinator.prepare("copy")
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide(stage, "approved", plan_id=plan.plan_id)
    coordinator.create_copy(_parent=tmp_path)
    assert _stage(coordinator, "copy")["attempted"] is True
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("choice", ["approved ", "approve", "yes", True, None, 1])
def test_noncanonical_choice_is_never_a_decision(live, choice):
    coordinator, _ = live
    plan = coordinator.prepare("copy")
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide("copy", choice, plan_id=plan.plan_id)
    assert _stage(coordinator, "copy")["decision"] == "pending"


@pytest.mark.parametrize("choice", ["approved", "declined", "cancelled"])
def test_terminal_decision_cannot_be_replaced_or_renewed(live, choice):
    coordinator, clock = live
    plan = coordinator.prepare("copy")
    coordinator.decide("copy", choice, plan_id=plan.plan_id, lifetime_seconds=10)
    clock.value += 1
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=300)
    assert _stage(coordinator, "copy")["decision"] == choice


def test_cross_session_plan_id_cannot_authorize_a_matching_proposal(live):
    coordinator, clock = live
    other = session.GeneratedRepairSession(_preview(), clock=clock)
    try:
        plan = coordinator.prepare("copy")
        other_plan = other.prepare("copy")
        assert plan.plan_id != other_plan.plan_id
        with pytest.raises(session.GeneratedRepairSessionError):
            other.decide("copy", "approved", plan_id=plan.plan_id)
        assert _stage(other, "copy")["decision"] == "pending"
    finally:
        other.close()


@pytest.mark.parametrize("state", ["no-plan", "pending", "declined", "cancelled", "expired"])
def test_copy_without_current_approval_consumes_only_attempt_and_never_allocates(
    live, monkeypatch, tmp_path, state
):
    coordinator, clock = live
    if state != "no-plan":
        plan = coordinator.prepare("copy")
        if state in {"declined", "cancelled"}:
            coordinator.decide("copy", state, plan_id=plan.plan_id)
        elif state == "expired":
            coordinator.decide("copy", "approved", plan_id=plan.plan_id)
            clock.value += 300
    monkeypatch.setattr(
        session,
        "GeneratedRepairWorkspace",
        lambda *args, **kwargs: pytest.fail("No allocation without current consent"),
    )
    result = coordinator.create_copy(_parent=tmp_path).to_dict()
    assert result["stages"]["copy"]["attempted"] is True
    assert result["stages"]["copy"]["status"] != "copied-private-workspace"
    assert result["workspace"]["path"] is None
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.create_copy(_parent=tmp_path)


def test_shorter_decision_lifetime_expires_without_renewing_original_plan(live, tmp_path):
    coordinator, clock = live
    plan = _approve(coordinator, lifetime_seconds=5)
    assert plan.to_dict()["expires_at"] == 1300.0
    assert _stage(coordinator, "copy")["effective_expires_at"] == 1005.0
    clock.value = 1005.0
    coordinator.create_copy(_parent=tmp_path)
    assert _stage(coordinator, "copy")["decision"] == "approved"
    assert _stage(coordinator, "copy")["expired"] is True
    assert list(tmp_path.iterdir()) == []


def test_late_approval_does_not_extend_original_300_second_deadline(live, tmp_path):
    coordinator, clock = live
    plan = coordinator.prepare("copy")
    clock.value = 1299.0
    coordinator.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=300)
    assert _stage(coordinator, "copy")["effective_expires_at"] == 1300.0
    clock.value = 1300.0
    coordinator.create_copy(_parent=tmp_path)
    assert _stage(coordinator, "copy")["attempted"] is True
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("value", [True, "1001", float("nan"), float("inf"), 999.0])
def test_invalid_or_backward_clock_at_effect_boundary_never_allocates(
    live, tmp_path, monkeypatch, value
):
    coordinator, clock = live
    _approve(coordinator)
    clock.value = value
    monkeypatch.setattr(
        session,
        "GeneratedRepairWorkspace",
        lambda *args, **kwargs: pytest.fail("No allocation with an invalid clock"),
    )
    result = coordinator.create_copy(_parent=tmp_path).to_dict()
    assert result["stages"]["copy"]["attempted"] is True
    assert result["stages"]["copy"]["status"] != "copied-private-workspace"
    assert result["workspace"]["path"] is None


def test_positive_but_unrepresentable_decision_lifetime_is_refused(live):
    coordinator, _ = live
    plan = coordinator.prepare("copy")
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide(
            "copy", "approved", plan_id=plan.plan_id, lifetime_seconds=math.nextafter(0.0, 1.0)
        )
    assert _stage(coordinator, "copy")["decision"] == "pending"


def test_clock_too_large_for_a_representable_plan_deadline_is_refused():
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator = session.GeneratedRepairSession(_preview(), clock=lambda: 1e30)
        coordinator.prepare("copy")


@pytest.mark.parametrize("operation", ["prepare", "decide", "copy", "before", "close"])
def test_reentrant_clock_callback_cannot_alter_an_outer_plan(live, tmp_path, operation):
    coordinator, clock = live
    attempted = []

    def reenter():
        actions = {
            "prepare": lambda: coordinator.prepare("copy"),
            "decide": lambda: coordinator.decide("copy", "approved", plan_id="unbound"),
            "copy": lambda: coordinator.create_copy(_parent=tmp_path),
            "before": coordinator.prepare_before,
            "close": coordinator.close,
        }
        with pytest.raises(session.GeneratedRepairSessionError):
            actions[operation]()
        attempted.append(operation)

    clock.callback = reenter
    plan = coordinator.prepare("copy")
    assert attempted == [operation]
    assert plan.to_dict()["stage"] == "copy"
    assert _stage(coordinator, "copy")["attempted"] is False
    assert _stage(coordinator, "before")["attempted"] is False
    assert coordinator.result().to_dict()["closed"] is False


@POSIX_COPY
@pytest.mark.parametrize("operation", ["prepare", "decide", "copy", "before", "close"])
def test_reentrant_constructor_callback_cannot_consume_or_close_busy_session(
    live, monkeypatch, tmp_path, operation
):
    coordinator, _ = live
    _approve(coordinator)
    original = session.GeneratedRepairWorkspace
    attempts = []

    def construct(*args, **kwargs):
        actions = {
            "prepare": lambda: coordinator.prepare("copy"),
            "decide": lambda: coordinator.decide("copy", "cancelled", plan_id="unbound"),
            "copy": lambda: coordinator.create_copy(_parent=tmp_path),
            "before": coordinator.prepare_before,
            "close": coordinator.close,
        }
        with pytest.raises(session.GeneratedRepairSessionError):
            actions[operation]()
        attempts.append(operation)
        return original(*args, **kwargs)

    monkeypatch.setattr(session, "GeneratedRepairWorkspace", construct)
    result = coordinator.create_copy(_parent=tmp_path).to_dict()
    assert attempts == [operation]
    assert result["stages"]["copy"]["status"] == "copied-private-workspace"
    assert result["stages"]["before"]["attempted"] is False
    assert result["closed"] is False


@POSIX_COPY
@pytest.mark.parametrize(
    "name", TRACKED_FILES, ids=["app", "test", "before", "after", "test-snapshot", "record"]
)
@pytest.mark.parametrize("mutation", ["edit", "inode", "mode", "hardlink", "symlink", "fifo"])
def test_tracked_file_changes_invalidate_approved_before_plan(
    live, monkeypatch, tmp_path, name, mutation
):
    coordinator, _ = live
    copy = _copied(monkeypatch, tmp_path, coordinator)
    _approve(coordinator, "before")
    initial_source = (copy.path / "app.py").read_bytes()
    target = copy.path / name
    initial = target.read_bytes()
    if mutation == "edit":
        target.write_bytes(initial + b" ")
    elif mutation == "inode":
        replacement = target.with_name("replacement")
        replacement.write_bytes(initial)
        replacement.chmod(0o600)
        replacement.replace(target)
    elif mutation == "mode":
        target.chmod(0o644)
    elif mutation == "hardlink":
        os.link(target, target.with_name("extra-link"))
    else:
        target.unlink()
        if mutation == "symlink":
            outside = tmp_path / "outside.txt"
            outside.write_bytes(b"never modify outside\n")
            target.symlink_to(outside)
        else:
            os.mkfifo(target, 0o600)
    monkeypatch.setattr(
        session.DisabledGeneratedRepairExecutor,
        "prepare",
        lambda *args, **kwargs: pytest.fail("No disabled preparation after changed files"),
    )
    result = coordinator.prepare_before().to_dict()
    assert result["stages"]["before"]["attempted"] is True
    assert result["stages"]["before"]["status"] != "prepared-disabled"
    assert result["baseline"] == "not-established"
    assert result["readiness"] is None
    if mutation == "symlink":
        assert (tmp_path / "outside.txt").read_bytes() == b"never modify outside\n"
    if name != "app.py":
        assert (copy.path / "app.py").read_bytes() == initial_source


@POSIX_COPY
@pytest.mark.parametrize("directory", ["root", "tests"])
@pytest.mark.parametrize("mutation", ["mode", "moved", "symlink", "inode"])
def test_directory_changes_invalidate_approved_before_plan(
    live, monkeypatch, tmp_path, directory, mutation
):
    coordinator, _ = live
    copy = _copied(monkeypatch, tmp_path, coordinator)
    _approve(coordinator, "before")
    target = copy.path if directory == "root" else copy.path / "tests"
    if mutation == "mode":
        target.chmod(0o755)
    else:
        moved = tmp_path / ("moved-" + directory)
        target.rename(moved)
        if mutation == "symlink":
            target.symlink_to(moved, target_is_directory=True)
        elif mutation == "inode":
            target.mkdir(mode=0o700)
    result = coordinator.prepare_before().to_dict()
    assert result["stages"]["before"]["attempted"] is True
    assert result["stages"]["before"]["status"] != "prepared-disabled"
    assert result["baseline"] == "not-established"
    assert result["verified_fix"] is False


@POSIX_COPY
def test_expiry_after_manifest_reads_prevents_disabled_preparation(live, monkeypatch, tmp_path):
    coordinator, clock = live
    copy = _copied(monkeypatch, tmp_path, coordinator)
    _approve(coordinator, "before", lifetime_seconds=1)
    original = copy.read_source

    def read_and_expire():
        result = original()
        clock.value += 2
        return result

    monkeypatch.setattr(copy, "read_source", read_and_expire)
    monkeypatch.setattr(
        session.DisabledGeneratedRepairExecutor,
        "prepare",
        lambda *args, **kwargs: pytest.fail("No preparation after manifest-read expiry"),
    )
    result = coordinator.prepare_before().to_dict()
    assert result["stages"]["before"]["attempted"] is True
    assert result["stages"]["before"]["decision"] == "approved"
    assert result["stages"]["before"]["expired"] is True
    assert result["readiness"] is None


@POSIX_COPY
def test_partial_initialization_is_retained_not_retried_and_not_reported_not_applied(
    live, monkeypatch, tmp_path
):
    coordinator, _ = live
    _approve(coordinator)
    original = io.GeneratedRepairWorkspace._create_initial

    def fail_after(workspace, name, content):
        if name == "after.txt":
            raise OSError("Maintained partial initialization failure")
        return original(workspace, name, content)

    monkeypatch.setattr(io.GeneratedRepairWorkspace, "_create_initial", fail_after)
    result = coordinator.create_copy(_parent=tmp_path).to_dict()
    state = result["workspace"]
    assert state["state"] == "state-unconfirmed"
    assert state["initialization_stage"] == "create-after.txt"
    assert state["file_states"]["app.py"] == "confirmed"
    assert state["file_states"]["record.json"] == "not-created"
    assert state["descriptor_cleanup_confirmed"] is True
    assert result["stages"]["copy"]["attempted"] is True
    assert len(list(tmp_path.iterdir())) == 1
    assert (list(tmp_path.iterdir())[0] / "app.py").is_file()
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.create_copy(_parent=tmp_path)


@POSIX_COPY
def test_cancellation_preserves_partial_initialization_and_consumed_attempt(
    live, monkeypatch, tmp_path
):
    coordinator, _ = live
    _approve(coordinator)
    original = io.GeneratedRepairWorkspace._create_initial

    def cancel_after(workspace, name, content):
        if name == "after.txt":
            raise KeyboardInterrupt("Maintained cancellation")
        return original(workspace, name, content)

    monkeypatch.setattr(io.GeneratedRepairWorkspace, "_create_initial", cancel_after)
    with pytest.raises(KeyboardInterrupt) as captured:
        coordinator.create_copy(_parent=tmp_path)
    result = captured.value.generated_repair_session_result.to_dict()
    assert result["workspace"]["initialization_stage"] == "create-after.txt"
    assert result["workspace"]["file_states"]["app.py"] == "confirmed"
    assert result["workspace"]["state"] == "state-unconfirmed"
    assert result["stages"]["copy"]["attempted"] is True
    assert len(list(tmp_path.iterdir())) == 1
    assert (
        coordinator.result().payload_json
        == captured.value.generated_repair_session_result.payload_json
    )


@POSIX_COPY
def test_fake_ready_default_result_cannot_establish_runtime_proof(live, monkeypatch, tmp_path):
    coordinator, _ = live
    _copied(monkeypatch, tmp_path, coordinator)
    _approve(coordinator, "before")
    original = session.DisabledGeneratedRepairExecutor.prepare

    def fake_ready(executor, preview):
        data = original(executor, preview).to_dict()
        data["status"] = "ready"
        data["runtime_invoked"] = True
        data["execution_status"] = "passed"
        data["verified_fix"] = True
        return GeneratedRepairExecutorReadiness(canonical(data))

    monkeypatch.setattr(session.DisabledGeneratedRepairExecutor, "prepare", fake_ready)
    result = coordinator.prepare_before().to_dict()
    assert result["preparation_status"] == "failed"
    assert result["readiness"] is None
    assert result["baseline"] == "not-established"
    assert result["authorization_status"] == "unknown"
    assert result["execution_status"] == "not-run"
    assert result["verified_fix"] is False


@POSIX_COPY
def test_closing_retains_fixed_artifacts_and_cannot_be_reopened(live, monkeypatch, tmp_path):
    coordinator, _ = live
    copy = _copied(monkeypatch, tmp_path, coordinator)
    before = {name: (copy.path / name).read_bytes() for name in TRACKED_FILES}
    coordinator.close()
    assert coordinator.result().to_dict()["closed"] is True
    assert {name: (copy.path / name).read_bytes() for name in TRACKED_FILES} == before
    for operation in (
        lambda: coordinator.prepare("copy"),
        lambda: coordinator.prepare("before"),
        lambda: coordinator.create_copy(_parent=tmp_path),
        coordinator.prepare_before,
    ):
        with pytest.raises(session.GeneratedRepairSessionError):
            operation()


def test_module_has_no_execution_apply_or_imported_approval_surface():
    parameters = inspect.signature(session.GeneratedRepairSession).parameters
    assert set(parameters) == {"preview", "clock"}
    assert not any(
        hasattr(session.GeneratedRepairSession, name)
        for name in (
            "run",
            "execute",
            "resume",
            "load",
            "from_dict",
            "from_json",
            "accept_facts",
            "apply_source",
            "restore_source",
            "apply",
            "restore",
        )
    )
    assert math.isfinite(Clock()())


def test_matching_caller_supplied_before_profile_cannot_unlock_later_stages(live):
    coordinator, _ = live
    material = controls.build_generated_repair_controls()
    rows = [row for case in material.to_dict()["cases"] for row in case["requests"]]
    scripted = {
        "kind": "generated-repair-http-facts",
        "schema_version": "1.0",
        "controls_id": material.controls_id,
        "candidate": "before",
        "facts": [
            {
                "request_id": row["request_id"],
                "status_code": row["expected_before"]["status_code"],
                "headers": [["content-type", "application/json"]],
                "body_base64": base64.b64encode(
                    canonical(row["expected_before"]["body_json"]).encode()
                ).decode(),
            }
            for row in rows
        ],
    }
    compared = controls.compare_generated_repair_observations(
        canonical(scripted), material, candidate="before"
    ).to_dict()
    assert compared["matching_request_count"] == 21
    assert compared["matches_expected_profile"] is True
    assert compared["execution_status"] == "not-established"
    # Data-only observations are not accepted by any session method or later-stage plan.
    for stage in ("source-diff", "source-apply", "after", "restore"):
        with pytest.raises(session.GeneratedRepairSessionError, match="runtime-not-implemented"):
            coordinator.prepare(stage)
    result = coordinator.result().to_dict()
    assert result["baseline"] == "not-established"
    assert result["source_application"] == "not-run"
    assert result["restoration_status"] == "not-run"
    assert result["verified_fix"] is False


@POSIX_COPY
def test_result_is_historical_and_never_reopens_files_or_calls_the_clock(
    live, monkeypatch, tmp_path
):
    coordinator, clock = live
    copy = _copied(monkeypatch, tmp_path, coordinator)
    saved = coordinator.result().payload_json
    (copy.path / "app.py").write_bytes(b"# user-edited inert text\n")
    clock.callback = lambda: pytest.fail("Historical result must not sample time")
    monkeypatch.setattr(
        copy, "read_source", lambda: pytest.fail("Historical result must not read files")
    )
    monkeypatch.setattr(
        copy, "read_record", lambda: pytest.fail("Historical result must not read the record")
    )
    result = coordinator.result()
    assert result.payload_json == saved
    assert result.to_dict()["execution_status"] == "not-run"
    assert result.to_dict()["baseline"] == "not-established"


def test_async_clock_is_refused_without_being_scheduled():
    async def async_clock():
        pytest.fail("No async clock should be scheduled")

    with pytest.raises(session.GeneratedRepairSessionError):
        session.GeneratedRepairSession(_preview(), clock=async_clock)


def test_coroutine_returning_clock_is_closed_and_refused():
    async def coroutine_sample():
        pytest.fail("No coroutine clock body should execute")

    sample = coroutine_sample()
    with pytest.raises(session.GeneratedRepairSessionError):
        session.GeneratedRepairSession(_preview(), clock=lambda: sample)
    assert sample.cr_frame is None


def test_huge_integer_lifetime_is_refused_without_mutating_pending_decision(live):
    coordinator, _ = live
    plan = coordinator.prepare("copy")
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=10**400)
    assert _stage(coordinator, "copy")["decision"] == "pending"


@pytest.mark.parametrize(
    "plan_id", [None, True, "wrong-plan", "x" * 129], ids=["none", "bool", "wrong", "long"]
)
def test_invalid_plan_id_cannot_change_a_current_pending_decision(live, plan_id):
    coordinator, _ = live
    coordinator.prepare("copy")
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.decide("copy", "approved", plan_id=plan_id)
    assert _stage(coordinator, "copy")["decision"] == "pending"


def test_repreparing_a_pending_plan_never_refreshes_its_original_deadline(live):
    coordinator, clock = live
    first = coordinator.prepare("copy")
    clock.value = 1299.0
    second = coordinator.prepare("copy")
    assert first.payload_json == second.payload_json
    assert second.to_dict()["created_at"] == 1000.0
    assert second.to_dict()["expires_at"] == 1300.0
    clock.value = 1300.0
    with pytest.raises(session.GeneratedRepairSessionError, match="expired"):
        coordinator.prepare("copy")


@POSIX_COPY
def test_expiry_inside_workspace_validation_stops_immediately_before_directory_allocation(
    live, monkeypatch, tmp_path
):
    coordinator, clock = live
    _approve(coordinator)
    original = io._checked_preview
    validations = []

    def validate_then_expire(preview):
        checked = original(preview)
        validations.append(True)
        clock.value = 1300.0
        return checked

    monkeypatch.setattr(io, "_checked_preview", validate_then_expire)
    monkeypatch.setattr(
        io.tempfile,
        "mkdtemp",
        lambda **kwargs: pytest.fail("Expired constructor validation must not allocate"),
    )
    result = coordinator.create_copy(_parent=tmp_path).to_dict()
    assert validations == [True]
    assert result["stages"]["copy"]["attempted"] is True
    assert result["stages"]["copy"]["decision"] == "approved"
    assert result["stages"]["copy"]["expired"] is True
    assert result["workspace"]["path"] is None
    assert list(tmp_path.iterdir()) == []


@POSIX_COPY
@pytest.mark.parametrize("state", ["no-plan", "pending", "declined", "cancelled", "expired"])
def test_before_without_current_consent_preserves_confirmed_copy_and_never_prepares(
    live, monkeypatch, tmp_path, state
):
    coordinator, clock = live
    copy = _copied(monkeypatch, tmp_path, coordinator)
    initial = {name: (copy.path / name).read_bytes() for name in TRACKED_FILES}
    if state != "no-plan":
        plan = coordinator.prepare("before")
        if state in {"declined", "cancelled"}:
            coordinator.decide("before", state, plan_id=plan.plan_id)
        elif state == "expired":
            coordinator.decide("before", "approved", plan_id=plan.plan_id, lifetime_seconds=1)
            clock.value += 1
    monkeypatch.setattr(
        session.DisabledGeneratedRepairExecutor,
        "prepare",
        lambda *args, **kwargs: pytest.fail("No default preparation without current consent"),
    )
    result = coordinator.prepare_before().to_dict()
    expected_status = "expired" if state == "expired" else "refused"
    assert result["stages"]["before"]["status"] == expected_status
    assert result["stages"]["before"]["attempted"] is True
    assert result["workspace"]["state"] == "ready-before"
    assert result["preparation_status"] == "not-run"
    assert result["stages"]["before"]["dispatched"] is False
    assert result["readiness"] is None
    assert {name: (copy.path / name).read_bytes() for name in TRACKED_FILES} == initial
    with pytest.raises(session.GeneratedRepairSessionError):
        coordinator.prepare_before()


def test_late_decision_records_its_own_time_without_rewriting_plan_creation(live):
    coordinator, clock = live
    plan = coordinator.prepare("copy")
    clock.value = 1100.0
    result = coordinator.decide("copy", "approved", plan_id=plan.plan_id).to_dict()
    assert plan.to_dict()["created_at"] == 1000.0
    assert plan.to_dict()["expires_at"] == 1300.0
    assert result["stages"]["copy"]["decided_at"] == 1100.0
    assert result["stages"]["copy"]["effective_expires_at"] == 1300.0


def test_short_lifetime_expiring_during_decision_validation_is_permanently_terminal(
    live, monkeypatch, tmp_path
):
    coordinator, clock = live
    plan = coordinator.prepare("copy")

    def advance_on_second_sample():
        clock.callback = lambda: setattr(clock, "value", 1002.0)

    clock.callback = advance_on_second_sample
    with pytest.raises(session.GeneratedRepairSessionError, match="expired"):
        coordinator.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=1)
    assert _stage(coordinator, "copy")["decision"] == "pending"
    assert _stage(coordinator, "copy")["expired"] is True
    with pytest.raises(session.GeneratedRepairSessionError, match="expired|terminal"):
        coordinator.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=300)
    with pytest.raises(session.GeneratedRepairSessionError, match="expired|terminal"):
        coordinator.prepare("copy")
    monkeypatch.setattr(
        session,
        "GeneratedRepairWorkspace",
        lambda *args, **kwargs: pytest.fail("An expired decision cannot be revived into a copy"),
    )
    result = coordinator.create_copy(_parent=tmp_path).to_dict()
    assert result["stages"]["copy"]["attempted"] is True
    assert result["stages"]["copy"]["dispatched"] is False
    assert result["workspace"]["path"] is None
    assert list(tmp_path.iterdir()) == []
