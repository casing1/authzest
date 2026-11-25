"""Approved original-file application and recovery with owned temporary projects."""

from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
from contextlib import suppress
from hashlib import sha256

import pytest
from tests.helpers.repository_http_file_data import make_http_file_session, perform
from tests.helpers.repository_http_verification_data import AFTER, SOURCE

from authzest.codex.contracts import canonical
from authzest.runner._repository_http_phase import RepositoryHttpPhaseResult
from authzest.runner._repository_http_staging import supported
from authzest.runner.repository_http_original import (
    RepositoryHttpOriginalError,
    apply_original,
    inspect_original_record,
    prepare_original_application,
    restore_original,
)

pytestmark = pytest.mark.skipif(not supported(), reason="POSIX original-file scope")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("original application must not execute or connect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)


def _after(session, **changes):
    payload = {
        "kind": "repository-http-phase-result",
        "phase": "after",
        "status": "complete",
        "criteria_met": True,
        "file_session_id": session._session_id,
        "file_session_revision": session._revision,
        "plan_id": session._verification_plan.plan_id,
        "source_sha256": sha256(AFTER.encode()).hexdigest(),
        "evidence_directory": "/owned/evidence",
        **changes,
    }
    return RepositoryHttpPhaseResult(canonical(payload))


@pytest.fixture
def applied(tmp_path):
    sessions = []

    def create():
        session, *_ = make_http_file_session(tmp_path, prefix="p" + str(len(sessions)))
        sessions.append(session)
        perform(session, "copy")
        perform(session, "accept-diff")
        perform(session, "apply")
        root = tmp_path / ("p" + str(len(sessions) - 1) + "-origin")
        return session, root.resolve(), tmp_path / ("recovery-" + str(len(sessions)))

    yield create
    for session in sessions:
        with suppress(Exception):
            session.close()


def test_preview_describes_exact_single_file_change_without_effect(applied):
    session, root, _ = applied()
    preview = prepare_original_application(session, _after(session))
    assert preview["source_path"] == "app.py" and preview["effect"] == "not-performed"
    assert '+    if x_user != "test-owner":' in preview["diff"]
    assert (root / "app.py").read_text() == SOURCE


def test_apply_writes_repair_preserves_mode_and_retains_backup(applied):
    session, root, recovery = applied()
    mode = stat.S_IMODE(os.stat(root / "app.py").st_mode)
    record = apply_original(session, _after(session), recovery_parent=recovery)
    assert (root / "app.py").read_text() == AFTER
    assert stat.S_IMODE(os.stat(root / "app.py").st_mode) == mode
    path = recovery / record["record_id"]
    assert record["state"] == "applied" and record["record_path"] == str(path)
    assert (path / "before.py").read_text() == SOURCE
    assert (path / "after.py").read_text() == AFTER
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path / "before.py").st_mode) == 0o400
    assert stat.S_IMODE(os.stat(path / "record.json").st_mode) == 0o600
    assert [entry.name for entry in root.iterdir() if entry.name.startswith(".")] == []
    saved = inspect_original_record(path)
    assert saved["current_original"] == "matches-applied" and saved["restore_allowed"]


def test_edit_before_application_is_refused_without_record(applied):
    session, root, recovery = applied()
    (root / "app.py").write_text(SOURCE + "# user edit\n")
    with pytest.raises(RepositoryHttpOriginalError, match="original-edit-conflict"):
        apply_original(session, _after(session), recovery_parent=recovery)
    assert (root / "app.py").read_text() == SOURCE + "# user edit\n"
    assert not recovery.exists()


def test_policy_edit_is_also_a_conflict(applied):
    session, root, recovery = applied()
    (root / "policy.md").write_text("changed policy\n")
    with pytest.raises(RepositoryHttpOriginalError, match="original-edit-conflict"):
        apply_original(session, _after(session), recovery_parent=recovery)
    assert (root / "app.py").read_text() == SOURCE


def test_edit_just_before_rename_is_refused_and_retains_record(applied):
    session, root, recovery = applied()
    calls = []

    def guard():
        calls.append(1)
        if len(calls) == 2:
            (root / "app.py").write_text(SOURCE + "# racing edit\n")

    with pytest.raises(RepositoryHttpOriginalError, match="original-edit-conflict") as caught:
        apply_original(session, _after(session), recovery_parent=recovery, guard=guard)
    record = caught.value.result
    assert record["state"] == "original-unchanged-failed"
    assert record["failure"]["temporary_cleanup"] == "temporary-removed"
    assert (root / "app.py").read_text() == SOURCE + "# racing edit\n"
    assert [entry.name for entry in root.iterdir() if entry.name.startswith(".")] == []


@pytest.mark.parametrize(
    "change",
    [
        {"criteria_met": False},
        {"status": "failed"},
        {"phase": "before"},
        {"file_session_revision": 0},
        {"file_session_id": "repository-http-file-session-" + "0" * 32},
        {"source_sha256": "0" * 64},
        {"plan_id": "repository-http-verification-plan-" + "0" * 64},
    ],
)
def test_unbound_or_failed_after_phase_is_refused(applied, change):
    session, root, recovery = applied()
    with pytest.raises(RepositoryHttpOriginalError, match="after-phase-not-bound"):
        apply_original(session, _after(session, **change), recovery_parent=recovery)
    assert (root / "app.py").read_text() == SOURCE and not recovery.exists()


def test_session_must_be_applied_after(tmp_path):
    session, *_ = make_http_file_session(tmp_path)
    try:
        perform(session, "copy")
        with pytest.raises(RepositoryHttpOriginalError, match="original-edit-conflict"):
            apply_original(session, _after(session), recovery_parent=tmp_path / "r")
    finally:
        session.close()


def test_guard_refusal_stops_before_any_write(applied):
    session, root, recovery = applied()

    def expired():
        raise RepositoryHttpOriginalError("decision-expired")

    with pytest.raises(RepositoryHttpOriginalError, match="decision-expired"):
        apply_original(session, _after(session), recovery_parent=recovery, guard=expired)
    assert (root / "app.py").read_text() == SOURCE and not recovery.exists()


def test_shared_recovery_parent_is_refused(applied):
    session, root, recovery = applied()
    recovery.mkdir(mode=0o755)
    recovery.chmod(0o755)
    with pytest.raises(RepositoryHttpOriginalError, match="private-recovery-directory"):
        apply_original(session, _after(session), recovery_parent=recovery)
    assert (root / "app.py").read_text() == SOURCE


def test_restore_returns_backup_once(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]
    restored = restore_original(path)
    assert restored["state"] == "restored"
    assert (root / "app.py").read_text() == SOURCE
    assert inspect_original_record(path)["current_original"] == "matches-backup"
    with pytest.raises(RepositoryHttpOriginalError, match="record-state-not-restorable"):
        restore_original(path)


def test_restore_never_overwrites_later_edits(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]
    (root / "app.py").write_text(AFTER + "# later edit\n")
    preview = inspect_original_record(path)
    assert preview["current_original"] == "changed-after-application"
    assert preview["restore_allowed"] is False
    with pytest.raises(RepositoryHttpOriginalError, match="original-changed-after-application"):
        restore_original(path)
    assert (root / "app.py").read_text() == AFTER + "# later edit\n"


def test_restore_guard_edit_race_is_refused(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]

    def racing():
        (root / "app.py").write_text(AFTER + "# race\n")

    with pytest.raises(RepositoryHttpOriginalError, match="original-changed-after-application"):
        restore_original(path, guard=racing)
    assert (root / "app.py").read_text() == AFTER + "# race\n"
    assert [entry.name for entry in root.iterdir() if entry.name.startswith(".")] == []


def test_tampered_backup_or_record_is_refused(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]
    (path / "before.py").chmod(0o600)
    (path / "before.py").write_text("tampered\n")
    with pytest.raises(RepositoryHttpOriginalError, match="record-backup-mismatch"):
        restore_original(path)
    (path / "before.py").write_text(SOURCE)
    raw = (path / "record.json").read_text()
    (path / "record.json").write_text(raw.replace('"kind"', '"kind":"x","kind"', 1))
    with pytest.raises(RepositoryHttpOriginalError, match="record-"):
        restore_original(path)
    assert (root / "app.py").read_text() == AFTER


def test_replaced_project_directory_is_refused(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]
    moved = root.with_name(root.name + "-moved")
    shutil.move(root, moved)
    root.mkdir()
    (root / "app.py").write_text(AFTER)
    with pytest.raises(RepositoryHttpOriginalError, match="original-directory-replaced"):
        restore_original(path)
    assert (root / "app.py").read_text() == AFTER


def test_relative_or_shared_record_directory_is_refused(applied, tmp_path):
    with pytest.raises(RepositoryHttpOriginalError, match="absolute-record-directory"):
        restore_original(tmp_path.relative_to(tmp_path.parent))
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(RepositoryHttpOriginalError, match="private-recovery-directory"):
        restore_original(shared)


def _rewrite_state(path, state):
    import json

    raw = json.loads((path / "record.json").read_text())
    raw["state"] = state
    (path / "record.json").write_text(json.dumps(raw))


def test_interrupted_apply_after_rename_can_be_restored(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]
    # As if the process died after the rename but before the completion record.
    _rewrite_state(path, "intent-recorded")
    preview = inspect_original_record(path)
    assert preview["current_original"] == "matches-applied" and preview["restore_allowed"]
    assert restore_original(path)["state"] == "restored"
    assert (root / "app.py").read_text() == SOURCE


def test_interrupted_apply_before_rename_is_not_rewritten(applied):
    session, root, recovery = applied()
    record = apply_original(session, _after(session), recovery_parent=recovery)
    path = recovery / record["record_id"]
    restore_original(path)
    _rewrite_state(path, "intent-recorded")
    assert inspect_original_record(path)["restore_allowed"] is False
    with pytest.raises(RepositoryHttpOriginalError, match="original-already-matches-backup"):
        restore_original(path)
    assert (root / "app.py").read_text() == SOURCE
