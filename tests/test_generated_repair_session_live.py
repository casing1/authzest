"""Owned inert copies and fixed fake phase results; never execute generated code."""

from __future__ import annotations

import ast
import base64
import builtins
import copy
import json
import socket
import subprocess
from hashlib import sha256

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _generated_repair_session as session
from authzest.runner._generated_repair_phase import (
    MAX_SESSION_EVIDENCE_BYTES,
    GeneratedRepairPhaseResult,
    PhaseError,
)
from authzest.runner._generated_repair_relay import compare_generated_repair_relay_capture
from authzest.runner._generated_repair_workspace import supported
from authzest.runner.generated_repair_controls import build_generated_repair_controls
from test_generated_repair_phase import _capture
from test_generated_repair_runtime_profile import profile
from test_generated_repair_session import Clock, _preview

pytestmark = pytest.mark.skipif(not supported(), reason="POSIX inert private-copy scope")


def approve(value, stage, **kwargs):
    plan = value.prepare(stage)
    value.decide(stage, "approved", plan_id=plan.plan_id, **kwargs)
    return plan


def phase_data(workspace, candidate, runtime, options):
    capture = _capture(candidate)
    comparison = compare_generated_repair_relay_capture(
        capture.decode(), build_generated_repair_controls(), candidate=candidate
    ).to_dict()
    code = 1 if candidate == "before" else 0
    return {
        "schema_version": "1.0",
        "kind": "generated-repair-phase-result",
        "candidate": candidate,
        "profile_id": runtime.profile_id,
        "phase_plan_id": options["phase_plan_id"],
        "session_nonce": options["session_nonce"],
        "status": "complete",
        "failure": None,
        "cleanup_confirmed": True,
        "engine_transport_cleanup_confirmed": True,
        "cleanup_errors": [],
        "generated_runtime_attempted": True,
        "test_exit_code": code,
        "comparison": comparison,
        "owned": [
            {
                "role": role,
                "name": f"authzest-generated-{options['session_nonce']}-{role.lower()}-{'d' * 32}",
                "id": str(index) * 64,
                "create_attempted": True,
                "absence_observed": True,
            }
            for index, role in enumerate("TAB", 1)
        ],
        "application_sha256": sha256(workspace.read_source().data).hexdigest(),
        "test_sha256": sha256(workspace.read_test().data).hexdigest(),
        "captures": [
            {
                "label": "attach-start-T-1",
                "complete": True,
                "returncode": code,
                "stdout_base64": base64.b64encode(b"untrusted pytest observation").decode(),
                "stderr_base64": "",
            },
            {
                "label": "attach-start-B-2",
                "complete": True,
                "returncode": 0,
                "stdout_base64": base64.b64encode(capture).decode(),
                "stderr_base64": "",
            },
        ],
        "transport_failure": None,
        "evidence_directory": "/private/owned-test-phase",
        "execution_authorized": False,
        "authorization_status": "unknown",
        "verified_fix": False,
        "source_applied": False,
    }


@pytest.fixture
def live(monkeypatch, tmp_path):
    assert ast.unparse(ast.Constant(value=None)) == "None"
    clock = Clock()
    guards, calls, mutate = [], [], [lambda value: None]

    def forbidden(*_, **__):
        pytest.fail("Inert session regression must not run processes, sockets or generated code")

    for name in ("exec", "eval"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    def fake_phase(workspace, candidate, runtime, **options):
        calls.append((candidate, options))
        options["evidence_budget"].charge(session.MAX_PHASE_RESULT_BYTES)
        options["dispatch_guard"]()
        data = phase_data(workspace, candidate, runtime, options)
        mutate[0](data)
        return GeneratedRepairPhaseResult(canonical(data))

    monkeypatch.setattr(session, "execute_generated_repair_phase", fake_phase)
    value = session.GeneratedRepairSession(
        _preview(),
        runtime_profile=profile(),
        runtime_guard=lambda: guards.append("current"),
        clock=clock,
    )
    try:
        yield value, clock, calls, guards, mutate, tmp_path
    finally:
        value.close()


def copied(live):
    value, _, _, _, _, parent = live
    approve(value, "copy")
    result = value.create_copy(_parent=parent).to_dict()
    assert result["stages"]["copy"]["status"] == "copied-private-workspace"
    return value


def before(live):
    value = copied(live)
    approve(value, "before")
    result = value.run_before().to_dict()
    assert result["stages"]["before"]["status"] == "checked-before"
    return value


def applied(live):
    value = before(live)
    approve(value, "source-diff")
    value.accept_diff()
    approve(value, "source-apply")
    result = value.apply_source().to_dict()
    assert result["source_application"] == "applied-copy-only"
    return value


def test_full_current_phase_diff_apply_after_restore_uses_same_budget_and_exact_bytes(live):
    value = applied(live)
    original = value._workspace.read_test()
    assert value._workspace.read_source().data == (value._workspace.path / "after.txt").read_bytes()
    approve(value, "after")
    checked = value.run_after().to_dict()
    assert checked["stages"]["after"]["status"] == "checked-after"
    assert checked["finite_controls_match"] is True
    assert checked["poc_exit_pattern"] == "before-1-after-0"
    assert (
        checked["verified_fix"] is False
        and checked["test_report_authenticity"] == "not-established"
    )
    assert [row[0] for row in live[2]] == ["before", "after"]
    assert live[2][0][1]["evidence_budget"] is live[2][1][1]["evidence_budget"]
    approve(value, "restore")
    restored = value.restore_source().to_dict()
    assert restored["restoration_status"] == "restored-before"
    assert restored["workspace"]["state"] == "restored-before"
    assert (
        value._workspace.read_source().data == (value._workspace.path / "before.txt").read_bytes()
    )
    assert value._workspace.read_test() == original
    assert json.loads(value._workspace.read_record().data)["phase"] == "restored-before"
    assert len(value.result().payload_json.encode()) <= session.MAX_RESULT_BYTES
    assert all("captures" not in result for result in restored["checks"].values())


@pytest.mark.parametrize("stage", ["source-diff", "source-apply", "after", "restore"])
def test_copied_bytes_and_supplied_facts_do_not_unlock_later_stages(live, stage):
    value = copied(live)
    with pytest.raises(session.GeneratedRepairSessionError):
        value.prepare(stage)
    assert not live[2] and value.result().to_dict()["baseline"] == "not-established"


@pytest.mark.parametrize(
    "key",
    [
        "candidate",
        "profile_id",
        "session_nonce",
        "phase_plan_id",
        "application_sha256",
        "test_sha256",
    ],
)
def test_wrong_current_call_binding_never_establishes_baseline(live, key):
    value = copied(live)
    live[4][0] = lambda data: data.__setitem__(key, "different")
    approve(value, "before")
    result = value.run_before().to_dict()
    assert result["baseline"] == "not-established"
    assert result["cleanup_unconfirmed"] is True
    with pytest.raises(session.GeneratedRepairSessionError):
        value.prepare("source-diff")


@pytest.mark.parametrize("change", ["boolean-only", "wrong-facts", "missing-capture", "wrong-exit"])
def test_success_boolean_or_counts_without_complete_current_relay_are_insufficient(live, change):
    value = copied(live)

    def tamper(data):
        if change == "boolean-only":
            data["comparison"] = {"matches_expected_profile": True}
        elif change == "wrong-facts":
            data["captures"][1]["stdout_base64"] = base64.b64encode(_capture("after")).decode()
        elif change == "missing-capture":
            data["captures"].pop()
        else:
            data["captures"][0]["returncode"] = True

    live[4][0] = tamper
    approve(value, "before")
    result = value.run_before().to_dict()
    assert result["baseline"] == "not-established"
    assert result["stages"]["before"]["status"] == "failed"


def test_passing_pytest_does_not_replace_independent_before_profile(live):
    value = copied(live)

    def passing(data):
        data["test_exit_code"] = data["captures"][0]["returncode"] = 0

    live[4][0] = passing
    approve(value, "before")
    result = value.run_before().to_dict()
    assert result["baseline"] == "intended-before-defect-observed"
    assert result["checks"]["before"]["test_exit_code"] == 0
    assert result["poc_exit_pattern"] == "not-observed" and result["verified_fix"] is False


def test_diff_acceptance_is_separate_from_apply_and_bound_to_original_plan(live):
    value = before(live)
    with pytest.raises(session.GeneratedRepairSessionError):
        value.prepare("source-apply")
    initial = value._workspace.read_source()
    plan = approve(value, "source-diff")
    assert plan.to_dict()["source_diff"][0]["path"] == "app.py"
    result = value.accept_diff().to_dict()
    assert result["stages"]["source-diff"]["status"] == "accepted-exact-diff"
    assert value._workspace.read_source() == initial
    with pytest.raises(session.GeneratedRepairSessionError, match="consumed"):
        value.accept_diff()
    apply = value.prepare("source-apply").to_dict()
    assert apply["prior_results"]["accepted_diff_plan"] == plan.plan_id


@pytest.mark.parametrize("stage", ["before", "source-diff", "source-apply", "after", "restore"])
def test_expired_stage_never_dispatches_or_replaces_bytes(live, stage):
    value = copied(live) if stage == "before" else before(live)
    if stage in {"source-apply", "after", "restore"}:
        approve(value, "source-diff")
        value.accept_diff()
    if stage in {"after", "restore"}:
        approve(value, "source-apply")
        value.apply_source()
    original = value._workspace.read_source()
    plan = approve(value, stage)
    count = len(live[2])
    live[1].value = plan.to_dict()["expires_at"]
    action = {
        "before": value.run_before,
        "source-diff": value.accept_diff,
        "source-apply": value.apply_source,
        "after": value.run_after,
        "restore": value.restore_source,
    }[stage]
    result = action().to_dict()
    assert result["stages"][stage]["status"] == "expired"
    assert value._workspace.read_source() == original and len(live[2]) == count


def test_edited_apply_input_refuses_without_overwriting_user_bytes(live):
    value = before(live)
    approve(value, "source-diff")
    value.accept_diff()
    approve(value, "source-apply")
    source = value._workspace.path / "app.py"
    source.write_bytes(b"# user-edited inert content\n")
    result = value.apply_source().to_dict()
    assert result["workspace"]["state"] == "state-unconfirmed"
    assert source.read_bytes() == b"# user-edited inert content\n"


@pytest.mark.parametrize("clean", [True, False])
def test_failed_after_preserves_confirmed_applied_file_and_controls_restore(live, clean):
    value = applied(live)

    def failed(data):
        data["status"] = "failed"
        data["failure"] = "independent-http-profile-mismatch"
        data["cleanup_confirmed"] = clean
        if not clean:
            data["owned"][-1]["absence_observed"] = False

    live[4][0] = failed
    approve(value, "after")
    result = value.run_after().to_dict()
    assert result["source_application"] == "applied-copy-only"
    assert result["workspace"]["state"] == "applied-after"
    assert result["checks"]["after"]["status"] == "failed"
    if clean:
        approve(value, "restore")
        assert value.restore_source().to_dict()["restoration_status"] == "restored-before"
    else:
        with pytest.raises(session.GeneratedRepairSessionError, match="cleanup"):
            value.prepare("restore")


def test_after_budget_refusal_before_phase_construction_retains_restore_capacity(live, monkeypatch):
    value = applied(live)

    def exhausted(*_, **__):
        raise PhaseError("retained-session-evidence-limit")

    monkeypatch.setattr(session, "execute_generated_repair_phase", exhausted)
    approve(value, "after")
    result = value.run_after().to_dict()
    assert result["cleanup_unconfirmed"] is False
    approve(value, "restore")
    assert value.restore_source().to_dict()["restoration_status"] == "restored-before"


def test_actual_shared_budget_exhaustion_does_not_consume_reserved_restore_plan(live):
    value = applied(live)
    approve(value, "after")
    budget = value._evidence_budget
    budget.charge(MAX_SESSION_EVIDENCE_BYTES - budget.used)
    result = value.run_after().to_dict()
    assert result["checks"]["after"] is None
    assert (
        result["cleanup_unconfirmed"] is False
        and result["source_application"] == "applied-copy-only"
    )
    plan = approve(value, "restore")
    assert (
        plan.to_dict()["permitted_effect"] == "restore-exact-original-before-in-private-copy-only"
    )
    result = value.restore_source().to_dict()
    assert result["restoration_status"] == "restored-before"
    assert result["retained_evidence_bytes_reserved_or_charged"] == MAX_SESSION_EVIDENCE_BYTES


@pytest.mark.parametrize("attached", [False, True])
def test_phase_cancellation_propagates_with_bounded_current_history(live, monkeypatch, attached):
    value = applied(live)
    approve(value, "after")

    def cancel(workspace, candidate, runtime, **options):
        error = KeyboardInterrupt()
        if attached:
            data = phase_data(workspace, candidate, runtime, options)
            data.update(status="failed", failure="KeyboardInterrupt")
            error.generated_repair_phase_result = GeneratedRepairPhaseResult(canonical(data))
        raise error

    monkeypatch.setattr(session, "execute_generated_repair_phase", cancel)
    with pytest.raises(KeyboardInterrupt) as error:
        value.run_after()
    result = error.value.generated_repair_session_result.to_dict()
    assert result["cleanup_unconfirmed"] is not attached
    assert result["source_application"] == "applied-copy-only"
    if attached:
        approve(value, "restore")
        assert value.restore_source().to_dict()["restoration_status"] == "restored-before"


def test_ordinary_phase_exception_without_receipt_blocks_restore(live, monkeypatch):
    value = applied(live)
    approve(value, "after")

    def broken(*_, **__):
        raise OSError("unconfirmed phase")

    monkeypatch.setattr(session, "execute_generated_repair_phase", broken)
    result = value.run_after().to_dict()
    assert result["cleanup_unconfirmed"] is True
    with pytest.raises(session.GeneratedRepairSessionError):
        value.prepare("restore")


@pytest.mark.parametrize("stage", ["before", "after"])
@pytest.mark.parametrize("exit_code", [78, 2, 137, -9])
def test_native_launcher_refusal_keeps_confirmed_cleanup_and_exact_exit(live, stage, exit_code):
    value = copied(live) if stage == "before" else applied(live)

    def refused(data):
        data.update(status="failed", failure="docker-command-failed", test_exit_code=exit_code)
        data["captures"][0]["returncode"] = exit_code

    live[4][0] = refused
    approve(value, stage)
    result = (value.run_before() if stage == "before" else value.run_after()).to_dict()
    assert result["checks"][stage]["test_exit_code"] == exit_code
    assert result["checks"][stage]["cleanup_confirmed"] is True
    assert result["cleanup_unconfirmed"] is False
    if stage == "before":
        assert result["baseline"] == "not-established"
        with pytest.raises(session.GeneratedRepairSessionError):
            value.prepare("source-diff")
    else:
        approve(value, "restore")
        assert value.restore_source().to_dict()["restoration_status"] == "restored-before"


def test_missing_runtime_guard_cannot_activate_profile_or_source_writes():
    with pytest.raises(session.GeneratedRepairSessionError, match="guard"):
        session.GeneratedRepairSession(_preview(), runtime_profile=profile())
    value = session.GeneratedRepairSession(_preview())
    try:
        for stage in session._LATER_STAGES:
            with pytest.raises(
                session.GeneratedRepairSessionError, match="runtime-not-implemented"
            ):
                value.prepare(stage)
    finally:
        value.close()


def test_result_is_detached_and_never_calls_live_guard_or_clock(live):
    value = before(live)
    previous = value.result()
    value._runtime_guard = value._clock = lambda: pytest.fail("Historical result called a guard")
    assert value.result() == previous
    data = value.result().to_dict()
    data["checks"]["before"]["cleanup_confirmed"] = False
    assert value.result().to_dict()["checks"]["before"]["cleanup_confirmed"] is True


def test_each_active_stage_full_plan_contains_original_runtime_and_prior_bindings(live):
    value = before(live)
    plan = value.prepare("source-diff")
    data = plan.to_dict()
    assert data["runtime_profile_id"] == profile().profile_id
    assert data["runtime_profile"] == profile().to_dict()
    assert (
        data["prior_results"]["before"]
        == value.result().to_dict()["checks"]["before"]["phase_result_id"]
    )
    used = value._evidence_budget.used
    assert value.prepare("source-diff") == plan and value._evidence_budget.used == used
    changed = copy.deepcopy(data)
    changed["runtime_profile_id"] = "wrong"
    value._plans["source-diff"] = session.GeneratedRepairSessionPlan(canonical(changed))
    with pytest.raises(session.GeneratedRepairSessionError):
        value.decide("source-diff", "approved", plan_id=plan.plan_id)


def test_replacing_valid_context_before_copy_cannot_silently_rebind_session(live):
    value = live[0]
    value._preview = _preview("unknown")
    with pytest.raises(session.GeneratedRepairSessionError, match="context changed"):
        value.prepare("copy")
    assert value.result().to_dict()["workspace"]["path"] is None
    assert not list(live[5].iterdir())


def test_replacing_valid_runtime_profile_cannot_rebind_original_guard(live):
    value = live[0]
    data = profile().to_dict()
    data["images"]["A"]["image_id"] = "sha256:" + "e" * 64
    value._profile = session.validate_runtime_profile(canonical(data))
    with pytest.raises(session.GeneratedRepairSessionError, match="runtime profile changed"):
        value.prepare("copy")
    assert value.result().to_dict()["workspace"]["path"] is None
