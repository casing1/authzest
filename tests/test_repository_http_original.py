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
from authzest.runner import repository_http_original as original_module
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


def _set_xattr(path, name, value):
    """Set one extended attribute through the platform API, or skip the test."""
    import ctypes
    import ctypes.util
    import errno
    import sys

    if sys.platform == "darwin":
        lib = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        lib.setxattr.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.c_int,
        ]
        if lib.setxattr(str(path).encode(), name.encode(), value, len(value), 0, 0) != 0:
            pytest.skip("extended attributes unavailable")
        return
    try:
        os.setxattr(path, name, value)
    except (AttributeError, OSError) as exc:
        if isinstance(exc, AttributeError) or exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
            pytest.skip("extended attributes unavailable")
        raise


def _session_with_metadata(tmp_path, prepare):
    """Create the owned project, adjust metadata, then capture it."""
    from tests.helpers.repository_http_verification_data import POLICY, case_data, inputs

    from authzest.analyzer.repository_origin import capture_repository_origin
    from authzest.codex.repository_http_copy_plan import prepare_repository_http_copy_plan
    from authzest.codex.repository_http_proposal import build_repository_http_request
    from authzest.runner.repository_http_cases import build_repository_http_cases
    from authzest.runner.repository_http_file_session import RepositoryHttpFileSession

    root = (tmp_path / "meta-origin").resolve()
    root.mkdir()
    (root / "app.py").write_text(SOURCE)
    (root / "policy.md").write_text(POLICY)
    prepare(root / "app.py")
    parent = tmp_path / "meta-private"
    parent.mkdir(mode=0o700)
    origin = capture_repository_origin(root, "app.py", "policy.md")
    request = build_repository_http_request(origin.snapshot, "offline-model")
    response = inputs()[1]
    response["request_id"] = request.request_id
    response["proposal"]["before_sha256"] = request.to_dict()["selection"]["files"][0]["sha256"]
    cases = build_repository_http_cases(case_data(request))
    plan = prepare_repository_http_copy_plan(request, response, cases)
    session = RepositoryHttpFileSession(origin, request, response, cases, plan, _parent=parent)
    for step in ("copy", "accept-diff", "apply"):
        perform(session, step)
    return session, root


def _metadata_of(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        return original_module._metadata(fd)
    finally:
        os.close(fd)


def test_extended_attributes_and_mode_survive_apply_and_restore(tmp_path):
    name = "user.authzest.test" if os.uname().sysname != "Darwin" else "org.authzest.test"

    def prepare(path):
        _set_xattr(path, name, b"keep-me")
        os.chmod(path, 0o640)

    session, root = _session_with_metadata(tmp_path, prepare)
    try:
        before = _metadata_of(root / "app.py")
        assert name in before["xattrs"]
        record = apply_original(session, _after(session), recovery_parent=tmp_path / "r")
        assert (root / "app.py").read_text() == AFTER
        assert _metadata_of(root / "app.py") == before
        assert name in record["metadata"]["xattr_names"] and record["metadata"]["mode"] == 0o640
        restore_original(tmp_path / "r" / record["record_id"])
        assert (root / "app.py").read_text() == SOURCE
        assert _metadata_of(root / "app.py") == before
    finally:
        session.close()


@pytest.mark.skipif(os.uname().sysname != "Darwin", reason="macOS extended ACL API")
@pytest.mark.parametrize("access", ["allow:read", "deny:delete"])
def test_macos_acl_survives_apply_or_blocks_replacement(tmp_path, access):
    import ctypes
    import ctypes.util

    lib = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    lib.acl_from_text.argtypes = [ctypes.c_char_p]
    lib.acl_from_text.restype = ctypes.c_void_p
    lib.acl_set_file.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
    lib.acl_free.argtypes = [ctypes.c_void_p]
    lib.acl_init.argtypes = [ctypes.c_int]
    lib.acl_init.restype = ctypes.c_void_p

    def prepare(path):
        text = "!#acl 1\ngroup:ABCDEFAB-CDEF-ABCD-EFAB-CDEF0000000C:everyone:12:" + access + "\n"
        acl = lib.acl_from_text(text.encode())
        assert acl
        try:
            assert lib.acl_set_file(str(path).encode(), 0x00000100, acl) == 0
        finally:
            lib.acl_free(acl)

    session, root = _session_with_metadata(tmp_path, prepare)
    try:
        before = _metadata_of(root / "app.py")
        assert before["acl_sha256"] is not None
        if access == "deny:delete":
            # The ACL forbids replacing the entry: refuse and keep the original.
            with pytest.raises(RepositoryHttpOriginalError) as caught:
                apply_original(session, _after(session), recovery_parent=tmp_path / "r")
            assert caught.value.result["state"] == "original-unchanged-failed"
            assert (root / "app.py").read_text() == SOURCE
            assert [entry.name for entry in root.iterdir() if entry.name.startswith(".")] == []
            return
        record = apply_original(session, _after(session), recovery_parent=tmp_path / "r")
        assert record["metadata"]["acl_present"] is True
        assert _metadata_of(root / "app.py") == before
    finally:
        session.close()
        # Clear the test ACL so pytest can remove its temporary directory later.
        empty = lib.acl_init(0)
        try:
            lib.acl_set_file(str(root / "app.py").encode(), 0x00000100, empty)
        finally:
            lib.acl_free(empty)


def test_group_survives_when_another_group_is_available(tmp_path):
    current = os.getegid()
    others = [gid for gid in os.getgroups() if gid != current]
    if not others:
        pytest.skip("no second group available")

    session, root = _session_with_metadata(tmp_path, lambda path: os.chown(path, -1, others[0]))
    try:
        apply_original(session, _after(session), recovery_parent=tmp_path / "r")
        assert os.stat(root / "app.py").st_gid == others[0]
    finally:
        session.close()


@pytest.mark.parametrize(
    ("change", "code"),
    [({"uid": -5}, "original-owner-differs"), ({"flags": 2}, "original-file-flags-unsupported")],
)
def test_unsupported_ownership_or_flags_are_refused(applied, monkeypatch, change, code):
    session, root, recovery = applied()
    real = original_module._metadata
    monkeypatch.setattr(original_module, "_metadata", lambda fd: {**real(fd), **change})
    with pytest.raises(RepositoryHttpOriginalError, match=code):
        apply_original(session, _after(session), recovery_parent=recovery)
    assert (root / "app.py").read_text() == SOURCE and not recovery.exists()


def test_unpreservable_metadata_never_replaces_original(applied, monkeypatch):
    session, root, recovery = applied()
    calls = []
    real = original_module._metadata

    def drifting(fd):
        value = real(fd)
        calls.append(1)
        if len(calls) > 1:  # The temporary copy differs from the original.
            value["xattrs"] = {**value["xattrs"], "org.authzest.lost": "0" * 64}
        return value

    monkeypatch.setattr(original_module, "_metadata", drifting)
    with pytest.raises(
        RepositoryHttpOriginalError, match="original-metadata-not-preserved"
    ) as caught:
        apply_original(session, _after(session), recovery_parent=recovery)
    assert caught.value.result["state"] == "original-unchanged-failed"
    assert (root / "app.py").read_text() == SOURCE
    assert [entry.name for entry in root.iterdir() if entry.name.startswith(".")] == []


def test_interruption_right_after_rename_stays_restorable(applied, monkeypatch):
    session, root, recovery = applied()
    real_rename = os.rename

    def rename_then_interrupt(*args, **kwargs):
        real_rename(*args, **kwargs)
        if args[1] == "app.py":  # Only the original replacement, not record.json.
            raise KeyboardInterrupt

    monkeypatch.setattr(original_module.os, "rename", rename_then_interrupt)
    with pytest.raises(KeyboardInterrupt) as caught:
        apply_original(session, _after(session), recovery_parent=recovery)
    monkeypatch.setattr(original_module.os, "rename", real_rename)
    record = caught.value.repository_http_original_record
    assert record["state"] == "recovery-required"
    assert (root / "app.py").read_text() == AFTER
    path = recovery / record["record_id"]
    preview = inspect_original_record(path)
    assert preview["current_original"] == "matches-applied" and preview["restore_allowed"]
    assert restore_original(path)["state"] == "restored"
    assert (root / "app.py").read_text() == SOURCE


def test_rename_failure_before_effect_reports_unchanged(applied, monkeypatch):
    session, root, recovery = applied()

    real_rename = os.rename

    def refuse(*args, **kwargs):
        if args[1] == "app.py":
            raise PermissionError("synthetic")
        return real_rename(*args, **kwargs)

    monkeypatch.setattr(original_module.os, "rename", refuse)
    with pytest.raises(RepositoryHttpOriginalError) as caught:
        apply_original(session, _after(session), recovery_parent=recovery)
    assert caught.value.result["state"] == "original-unchanged-failed"
    assert (root / "app.py").read_text() == SOURCE
    monkeypatch.setattr(original_module.os, "rename", real_rename)
    # The safety net still refuses: the original equals the backup, not the repair.
    path = recovery / caught.value.result["record_id"]
    assert inspect_original_record(path)["restore_allowed"] is False


def test_replacement_stays_private_until_metadata_is_installed(applied, monkeypatch):
    session, root, recovery = applied()
    real = original_module._copy_metadata
    modes = []

    def observe(source, target, meta):
        modes.append(stat.S_IMODE(os.fstat(target).st_mode))
        real(source, target, meta)
        modes.append(stat.S_IMODE(os.fstat(target).st_mode))

    monkeypatch.setattr(original_module, "_copy_metadata", observe)
    record = apply_original(session, _after(session), recovery_parent=recovery)
    expected = record["metadata"]["mode"]
    restore_original(recovery / record["record_id"])
    assert modes == [0o600, expected, 0o600, expected]
