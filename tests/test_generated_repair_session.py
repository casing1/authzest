"""Maintained inert text and owned temporary copies; no generated execution."""

from __future__ import annotations

import ast
import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import canonical
from authzest.codex.generated_repair import (
    build_generated_repair_request,
    validate_generated_repair_proposal,
)
from authzest.runner import _generated_repair_session as session
from authzest.runner import _generated_repair_workspace as workspace
from authzest.runner.generated_repair_verification import (
    build_generated_repair_verification_preview,
)


class Clock:
    def __init__(self, value=10.0):
        self.value = value

    def __call__(self):
        return self.value


@pytest.fixture(autouse=True)
def _forbid_execution_and_network(monkeypatch, tmp_path):
    # Python 3.14 imports the trusted stdlib unparser lazily. Initialize it
    # before blocking Python execution, not by allowing candidate execution.
    assert ast.unparse(ast.Constant(value=None)) == "None"

    def forbidden(*args, **kwargs):
        pytest.fail("Offline session tests must not execute code, processes or network calls")

    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)


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
                "rationale": "Maintained inert session fixture, not a repair.",
                "evidence_ids": list(data["evidence_ids"].values()),
                "assumptions": ["No generated text is executed."],
                "uncertainties": ["No runtime observation exists."],
                "limitations": ["Offline one-use decisions only."],
                "proposal": {
                    "source_path": "app.py",
                    "before_sha256": source["sha256"],
                    "after_text": source["text"] + "\n# Maintained inert session candidate.\n",
                    "test_path": "tests/test_generated_ownership.py",
                    "test_text": "# Maintained inert session test text.\n",
                }
                if status == "proposed-change"
                else None,
            }
        ),
        request,
    )
    return build_generated_repair_verification_preview(request, proposal)


def _approve(value, stage, **kwargs):
    plan = value.prepare(stage)
    value.decide(stage, "approved", plan_id=plan.plan_id, **kwargs)
    return plan


def test_constructor_result_and_copy_plan_are_inert_detached_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(
        session, "GeneratedRepairWorkspace", lambda *a, **k: pytest.fail("Unexpected copy")
    )
    value = session.GeneratedRepairSession(_preview(), clock=Clock())
    try:
        initial = value.result().to_dict()
        assert initial["workspace"]["path"] is None
        assert initial["history"] == []
        assert initial["execution_status"] == "not-run"
        assert initial["baseline"] == "not-established"
        assert initial["verified_fix"] is False
        assert initial["authorization_status"] == "unknown"
        plan = value.prepare("copy")
        data = plan.to_dict()
        assert data["stage"] == "copy"
        assert data["generation"] == 1
        assert data["expires_at"] == 310
        assert data["request"]["scenario"]["source"]["text"]
        assert len(data["verification_preview"]["proposal_preview"]["changes"]) == 2
        assert data["verification_preview"]["controls"]["request_count"] == 21
        assert data["verification_preview"]["recipe"]["status"] == "proposed-not-enforced"
        assert data["file_manifest"] is None
        assert data["execution_authorized"] is False
        assert len(plan.payload_json.encode()) < session.MAX_PLAN_BYTES
        assert len(value.result().payload_json.encode()) < session.MAX_RESULT_BYTES
        data["stage"] = "restore"
        assert plan.to_dict()["stage"] == "copy"
        initial["verified_fix"] = True
        assert value.result().to_dict()["verified_fix"] is False
        with pytest.raises(FrozenInstanceError):
            plan.payload_json = "{}"
        with pytest.raises(FrozenInstanceError):
            value.result().payload_json = "{}"
        assert list(tmp_path.iterdir()) == []
    finally:
        value.close()


def test_repeated_prepare_returns_original_plan_and_does_not_extend_deadline():
    clock = Clock()
    value = session.GeneratedRepairSession(_preview(), clock=clock)
    try:
        first = value.prepare("copy")
        clock.value = 100
        assert value.prepare("copy") == first
        approved = value.decide("copy", "approved", plan_id=first.plan_id).to_dict()
        assert approved["stages"]["copy"]["effective_expires_at"] == 310
        assert len(approved["history"]) == 2
        with pytest.raises(session.GeneratedRepairSessionError, match="terminal"):
            value.decide("copy", "approved", plan_id=first.plan_id)
        assert value.prepare("copy") == first
        clock.value = 310
        with pytest.raises(session.GeneratedRepairSessionError, match="expired"):
            value.prepare("copy")
        assert value.result().to_dict()["stages"]["copy"]["decision"] == "approved"
        assert value.result().to_dict()["stages"]["copy"]["expired"] is True
    finally:
        value.close()


@pytest.mark.parametrize("choice", ["declined", "cancelled"])
def test_terminal_refusal_cannot_allocate_and_only_consumes_one_attempt(tmp_path, choice):
    value = session.GeneratedRepairSession(_preview(), clock=Clock())
    try:
        plan = value.prepare("copy")
        value.decide("copy", choice, plan_id=plan.plan_id)
        result = value.create_copy(_parent=tmp_path).to_dict()
        assert result["stages"]["copy"]["attempted"] is True
        assert result["stages"]["copy"]["status"] == "refused"
        assert result["stages"]["copy"]["decision"] == choice
        assert result["workspace"]["path"] is None
        with pytest.raises(session.GeneratedRepairSessionError, match="consumed"):
            value.create_copy(_parent=tmp_path)
        assert list(tmp_path.iterdir()) == []
    finally:
        value.close()


@pytest.mark.skipif(not workspace.supported(), reason="POSIX private-copy operations")
def test_approved_fresh_copy_and_separate_before_preparation_remain_non_runtime(tmp_path):
    value = session.GeneratedRepairSession(_preview(), clock=Clock())
    copy_plan = _approve(value, "copy")
    copied = value.create_copy(_parent=tmp_path).to_dict()
    path = value._workspace.path
    try:
        assert path.parent == tmp_path
        assert copied["workspace"]["state"] == "ready-before"
        assert copied["stages"]["copy"]["status"] == "copied-private-workspace"
        assert copied["test_materialization"] == "materialized-private-copy"
        before_plan = value.prepare("before")
        assert before_plan.plan_id != copy_plan.plan_id
        data = before_plan.to_dict()
        assert set(data["file_manifest"]["files"]) == set(session._FILE_NAMES)
        assert set(data["file_manifest"]["directories"]) == {"root", "tests"}
        for item in data["file_manifest"]["files"].values():
            assert len(item["sha256"]) == 64
            assert len(item["identity"]) == 9
        value.decide("before", "approved", plan_id=before_plan.plan_id)
        prepared = value.prepare_before().to_dict()
        assert prepared["stages"]["before"]["status"] == "prepared-disabled"
        assert prepared["preparation_status"] == "completed"
        assert prepared["readiness"]["status"] == "not-ready"
        assert prepared["readiness"]["reason"] == "runtime-not-implemented"
        assert prepared["execution_status"] == "not-run"
        assert prepared["baseline"] == "not-established"
        assert prepared["source_application"] == "not-run"
        assert prepared["restoration_status"] == "not-run"
        assert prepared["authorization_status"] == "unknown"
        assert prepared["verified_fix"] is False
        assert len(prepared["history"]) == 6
        record = json.loads((path / "record.json").read_bytes())
        assert record["approval"] == "not-provided"
        assert record["phase"] == "ready-before"
        assert record["execution_status"] == "not-run"
        assert (path / "app.py").read_bytes() == (path / "before.txt").read_bytes()
        assert (path / "tests/test_generated_ownership.py").read_bytes() == (
            path / "test.txt"
        ).read_bytes()
        for stage in session._LATER_STAGES:
            with pytest.raises(
                session.GeneratedRepairSessionError, match="runtime-not-implemented"
            ):
                value.prepare(stage)
        with pytest.raises(session.GeneratedRepairSessionError, match="consumed"):
            value.prepare_before()
    finally:
        value.close()
    assert path.is_dir()
    assert value.result().to_dict()["workspace"]["descriptor_cleanup_confirmed"] is True
    assert value.result().to_dict()["closed"] is True


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_non_change_session_cannot_prepare_or_create_copy(tmp_path, status):
    value = session.GeneratedRepairSession(_preview(status), clock=Clock())
    try:
        with pytest.raises(session.GeneratedRepairSessionError, match="proposed change"):
            value.prepare("copy")
        result = value.create_copy(_parent=tmp_path).to_dict()
        assert result["stages"]["copy"]["attempted"] is True
        assert result["stages"]["copy"]["status"] == "refused"
        assert result["workspace"]["path"] is None
        assert list(tmp_path.iterdir()) == []
    finally:
        value.close()


def test_results_are_historical_and_never_call_clock_or_workspace(monkeypatch):
    clock = Clock()
    value = session.GeneratedRepairSession(_preview(), clock=clock)
    try:
        plan = value.prepare("copy")
        value.decide("copy", "approved", plan_id=plan.plan_id)
        previous = value.result()
        clock.value = float("nan")
        monkeypatch.setattr(value, "_check_context", lambda: pytest.fail("Context read"))
        assert value.result() == previous
        assert value.result().to_dict()["stages"]["copy"]["decision"] == "approved"
    finally:
        value.close()


def test_shortened_decision_expiry_cannot_be_replaced_with_a_new_approval(tmp_path, monkeypatch):
    clock = Clock(1000)
    value = session.GeneratedRepairSession(_preview(), clock=clock)
    try:
        plan = value.prepare("copy")
        original_check = value._check_context
        calls = 0

        def expire_during_validation():
            nonlocal calls
            original_check()
            calls += 1
            if calls == 2:
                clock.value = 1002

        monkeypatch.setattr(value, "_check_context", expire_during_validation)
        with pytest.raises(session.GeneratedRepairSessionError, match="expired"):
            value.decide("copy", "approved", plan_id=plan.plan_id, lifetime_seconds=1)
        monkeypatch.setattr(value, "_check_context", original_check)
        expired = value.result().to_dict()["stages"]["copy"]
        assert expired["decision"] == "pending"
        assert expired["decided_at"] is None
        assert expired["expired"] is True
        assert clock.value < plan.to_dict()["expires_at"]
        with pytest.raises(session.GeneratedRepairSessionError, match="expired"):
            value.decide("copy", "approved", plan_id=plan.plan_id)
        with pytest.raises(session.GeneratedRepairSessionError, match="expired"):
            value.prepare("copy")
        result = value.create_copy(_parent=tmp_path).to_dict()
        assert result["stages"]["copy"]["status"] == "expired"
        assert result["workspace"]["path"] is None
        assert list(tmp_path.iterdir()) == []
    finally:
        value.close()
