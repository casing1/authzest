"""Final pending-intent expiry checks on inert owned copy bytes only."""

from __future__ import annotations

import json
import os

import pytest

from authzest.runner import _generated_repair_session as session
from authzest.runner import _generated_repair_workspace as workspace
from test_generated_repair_session import _preview
from test_generated_repair_session_live import (
    applied,
    approve,
    before,
)
from test_generated_repair_session_live import (
    live as guarded_session_fixture,
)

pytestmark = pytest.mark.skipif(not workspace.supported(), reason="POSIX inert copy scope")


@pytest.fixture
def live(monkeypatch, tmp_path):
    yield from guarded_session_fixture.__wrapped__(monkeypatch, tmp_path)


def transition_context(live, restore):
    value = applied(live) if restore else before(live)
    stage = "restore" if restore else "source-apply"
    if not restore:
        approve(value, "source-diff")
        value.accept_diff()
    plan = approve(value, stage)
    return value, stage, plan


def app_renames(monkeypatch):
    calls = []
    original = os.replace

    def record(src, dst, *args, **kwargs):
        if dst == "app.py":
            calls.append((src, dst))
        return original(src, dst, *args, **kwargs)

    monkeypatch.setattr(workspace.os, "replace", record)
    return calls


@pytest.mark.parametrize("restore", [False, True])
def test_expiry_during_durable_pending_intent_refuses_application_rename(
    live, monkeypatch, restore
):
    value, stage, plan = transition_context(live, restore)
    copy = value._workspace
    source, test = copy.read_source(), copy.read_test()
    renames = app_renames(monkeypatch)
    persist = workspace.GeneratedRepairWorkspace._persist_record

    def slow_intent(copy, phase, *, pending=None):
        answer = persist(copy, phase, pending=pending)
        if pending == ("restore" if restore else "apply"):
            live[1].value = plan.to_dict()["expires_at"]
        return answer

    monkeypatch.setattr(workspace.GeneratedRepairWorkspace, "_persist_record", slow_intent)
    result = (value.restore_source() if restore else value.apply_source()).to_dict()
    assert renames == []
    assert (copy.path / "app.py").read_bytes() == source.data
    assert (copy.path / "tests/test_generated_ownership.py").read_bytes() == test.data
    assert result["stages"][stage]["expired"] is True
    assert result["stages"][stage]["status"] == "state-unconfirmed"
    assert result["workspace"]["state"] == "state-unconfirmed"
    record = json.loads((copy.path / "record.json").read_bytes())
    assert record["phase"] == "state-unconfirmed"
    assert record["pending_operation"] == ("restore" if restore else "apply")
    with pytest.raises(session.GeneratedRepairSessionError):
        value.prepare(stage)


@pytest.mark.parametrize("restore", [False, True])
def test_final_guard_after_intent_within_original_window_completes_once(live, monkeypatch, restore):
    value, stage, plan = transition_context(live, restore)
    source_test = value._workspace.read_test()
    renames = app_renames(monkeypatch)
    persist = workspace.GeneratedRepairWorkspace._persist_record

    def nearly_expired(copy, phase, *, pending=None):
        answer = persist(copy, phase, pending=pending)
        if pending is not None:
            live[1].value = plan.to_dict()["expires_at"] - 1
        return answer

    monkeypatch.setattr(workspace.GeneratedRepairWorkspace, "_persist_record", nearly_expired)
    result = (value.restore_source() if restore else value.apply_source()).to_dict()
    assert len(renames) == 1
    assert result["stages"][stage]["status"] == (
        "restored-before" if restore else "applied-copy-only"
    )
    assert value._workspace.read_test() == source_test


@pytest.mark.parametrize("restore", [False, True])
def test_final_guard_cancellation_retains_intent_without_renaming(live, monkeypatch, restore):
    value, stage, _ = transition_context(live, restore)
    source, test = value._workspace.read_source(), value._workspace.read_test()
    renames = app_renames(monkeypatch)
    original = value._runtime_guard

    def cancel_pending():
        original()
        if value._workspace.state == "state-unconfirmed":
            raise KeyboardInterrupt()

    value._runtime_guard = cancel_pending
    with pytest.raises(KeyboardInterrupt) as cancelled:
        (value.restore_source if restore else value.apply_source)()
    result = cancelled.value.generated_repair_session_result.to_dict()
    assert not renames and result["workspace"]["state"] == "state-unconfirmed"
    assert result["stages"][stage]["status"] == "state-unconfirmed"
    assert (value._workspace.path / "app.py").read_bytes() == source.data
    assert (value._workspace.path / "tests/test_generated_ownership.py").read_bytes() == test.data
    assert cancelled.value.workspace_commit_attempted is False
    assert cancelled.value.workspace_journal_committed is True


@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.parametrize("name", ["app.py", "tests/test_generated_ownership.py"])
def test_edit_during_final_context_guard_is_preserved_without_overwrite(
    live, monkeypatch, restore, name
):
    value, _, _ = transition_context(live, restore)
    original_source = (value._workspace.path / "app.py").read_bytes()
    original_test = (value._workspace.path / "tests/test_generated_ownership.py").read_bytes()
    renames = app_renames(monkeypatch)
    original = value._runtime_guard
    edited = b"# ordinary inert external edit\n"

    def edit_pending():
        original()
        if value._workspace.state == "state-unconfirmed":
            (value._workspace.path / name).write_bytes(edited)

    value._runtime_guard = edit_pending
    result = (value.restore_source() if restore else value.apply_source()).to_dict()
    assert not renames and result["workspace"]["state"] == "state-unconfirmed"
    assert (value._workspace.path / name).read_bytes() == edited
    if name == "app.py":
        assert (
            value._workspace.path / "tests/test_generated_ownership.py"
        ).read_bytes() == original_test
    else:
        assert (value._workspace.path / "app.py").read_bytes() == original_source


def test_default_workspace_guard_still_runs_once_and_optional_guard_sees_pending_intent(tmp_path):
    copy = workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    calls = []
    try:
        current = copy.apply_source(copy.read_source(), guard=lambda: calls.append("initial"))
        assert calls == ["initial"]

        def commit():
            record = json.loads(copy.read_record().data)
            assert copy.state == "state-unconfirmed" and record["pending_operation"] == "restore"
            calls.append("commit")

        copy.restore_source(current, guard=lambda: calls.append("initial"), commit_guard=commit)
        assert calls == ["initial", "initial", "commit"]
    finally:
        copy.close()


@pytest.mark.parametrize("value", [True, 0, "approved"])
def test_invalid_final_guard_result_keeps_uncertainty_and_original_bytes(
    tmp_path, monkeypatch, value
):
    copy = workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    source = copy.read_source()
    renames = app_renames(monkeypatch)
    try:
        with pytest.raises(workspace.CommittedWriteError) as failure:
            copy.apply_source(source, guard=lambda: None, commit_guard=lambda: value)
        assert failure.value.commit_attempted is False and failure.value.journal_committed is True
        assert copy.state == "state-unconfirmed" and not renames
        assert (copy.path / "app.py").read_bytes() == source.data
    finally:
        copy.close()


def test_async_final_guard_is_refused_before_staging_or_intent(tmp_path):
    copy = workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    original = copy.read_record()

    async def unsupported():
        return None

    try:
        with pytest.raises(workspace.WorkspaceError, match="synchronous"):
            copy.apply_source(copy.read_source(), guard=lambda: None, commit_guard=unsupported)
        assert copy.state == "ready-before" and copy.read_record() == original
    finally:
        copy.close()
