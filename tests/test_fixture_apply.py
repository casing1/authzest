import json
import os
import socket
import stat
import subprocess

import pytest

from authzest.codex.contracts import ContractError
from authzest.runner import _fixture_workspace as io
from authzest.runner.fixture_apply import FixtureApplySession
from test_proposal_contract import AFTER, SOURCE, draft, make_context


@pytest.fixture
def session(tmp_path):
    if not io.supported():
        pytest.skip("POSIX fixture-copy operations only")
    request, review = make_context(tmp_path)
    clock = [10]
    created = FixtureApplySession(
        draft(request, review), request, review, parent=tmp_path, clock=lambda: clock[0]
    )
    yield created, clock
    created.close()


def main_bytes(session):
    return (session[0].workspace / "main.py").read_bytes()


def record(session):
    return json.loads((session[0].workspace / "record.json").read_text())


def test_only_new_private_copy_and_durable_snapshots(session, tmp_path):
    app, _ = session
    assert app.workspace != tmp_path
    assert app.workspace.parent == tmp_path
    assert main_bytes(session) == SOURCE.encode()
    assert (app.workspace / "before.txt").read_bytes() == SOURCE.encode()
    assert (app.workspace / "after.txt").read_bytes() == AFTER.encode()
    assert stat.S_IMODE(app.workspace.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in app.workspace.iterdir())
    assert record(session)["restart_supported"] is False
    assert app.preview()["original_checkout_modified"] is False


def test_approval_applies_only_copy_and_consumes_decision(session, tmp_path):
    app, _ = session
    unrelated = tmp_path / "notes.txt"
    unrelated.write_text("my work")
    app.decide("approve")
    result = app.apply()
    assert result.status == "applied" and result.applied and not result.restored
    assert result.verification_status == "not-run"
    assert main_bytes(session) == AFTER.encode()
    assert (tmp_path / "main.py").read_text() == SOURCE
    assert unrelated.read_text() == "my work"
    assert app.apply().status == "session-finished"
    with pytest.raises(io.WorkspaceError):
        app.decide("approve")
    journal = record(session)
    assert journal["applied"] and journal["decision_consumed"]
    assert journal["phase"] == "applied"
    assert not list(app.workspace.glob(".stage-*"))


@pytest.mark.parametrize("choice,reason", [("decline", "declined"), ("cancel", "cancelled")])
def test_latest_refusal_revokes_prior_approval(session, choice, reason):
    app, _ = session
    app.decide("approve")
    app.decide(choice)
    assert app.apply().status == reason
    assert app.apply().status == "decision-consumed"
    assert main_bytes(session) == SOURCE.encode()
    assert record(session)["decision"]["choice"] == choice


def test_pending_and_fresh_decision_after_refusal(session):
    app, _ = session
    assert app.apply().status == "pending"
    app.decide("decline")
    app.apply()
    app.decide("approve")
    assert app.apply().applied


@pytest.mark.parametrize(
    "when,reason", [(9, "clock-before-decision"), (310, "expired"), (311, "expired")]
)
def test_expiry_and_backwards_clock(session, when, reason):
    app, clock = session
    app.decide("approve")
    clock[0] = when
    assert app.apply().status == reason
    assert main_bytes(session) == SOURCE.encode()


@pytest.mark.parametrize("choice", ["", "yes", None, True])
def test_invalid_choice_has_no_side_effect(session, choice):
    app, _ = session
    with pytest.raises(ContractError):
        app.decide(choice)
    assert app.apply().status == "pending"
    assert main_bytes(session) == SOURCE.encode()


@pytest.mark.parametrize(
    "mutation",
    [
        "content",
        "same-bytes-new-inode",
        "mode",
        "hardlink",
        "symlink",
        "directory",
        "missing",
        "fifo",
        "oversize",
        "invalid-utf8",
    ],
)
def test_reject_changed_or_unsafe_current_file(session, tmp_path, mutation):
    app, _ = session
    target = app.workspace / "main.py"
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"unrelated")
    app.decide("approve")
    if mutation == "content":
        target.write_bytes(b"# newer user edit\n")
    elif mutation == "same-bytes-new-inode":
        replacement = app.workspace / "replacement"
        replacement.write_bytes(SOURCE.encode())
        replacement.chmod(0o600)
        replacement.replace(target)
    elif mutation == "mode":
        target.chmod(0o644)
    elif mutation == "hardlink":
        os.link(target, app.workspace / "another-link")
    elif mutation in ("symlink", "directory", "missing", "fifo"):
        target.unlink()
        if mutation == "symlink":
            target.symlink_to(outside)
        elif mutation == "directory":
            target.mkdir()
        elif mutation == "fifo":
            os.mkfifo(target, 0o600)
    elif mutation == "oversize":
        target.write_bytes(b"x" * 131_073)
    else:
        target.write_bytes(b"\xff")
    result = app.apply()
    assert not result.applied and result.status in ("stale-source", "not-applied")
    assert outside.read_bytes() == b"unrelated"
    if mutation in ("content", "oversize", "invalid-utf8"):
        assert main_bytes(session) != SOURCE.encode()
    assert (tmp_path / "main.py").read_text() == SOURCE


@pytest.mark.parametrize("mutation", ["permissions", "rename", "symlink"])
def test_changed_workspace_directory_refused(session, tmp_path, mutation):
    app, _ = session
    app.decide("approve")
    if mutation == "permissions":
        app.workspace.chmod(0o755)
    else:
        app.workspace.rename(tmp_path / "moved-copy")
        if mutation == "symlink":
            app.workspace.symlink_to(tmp_path / "moved-copy", target_is_directory=True)
    assert not app.apply().applied
    assert (tmp_path / "main.py").read_text() == SOURCE


def test_expiry_during_staging_refused(session, monkeypatch):
    app, clock = session
    app.decide("approve")
    stage = app._workspace._stage

    def expire(data):
        name = stage(data)
        if data == AFTER.encode():
            clock[0] = 310
        return name

    monkeypatch.setattr(app._workspace, "_stage", expire)
    assert not app.apply().applied
    assert main_bytes(session) == SOURCE.encode()


def test_change_during_staging_is_preserved(session, monkeypatch):
    app, _ = session
    app.decide("approve")
    stage = app._workspace._stage

    def edit(data):
        name = stage(data)
        if data == AFTER.encode():
            (app.workspace / "main.py").write_bytes(b"# later edit\n")
        return name

    monkeypatch.setattr(app._workspace, "_stage", edit)
    assert not app.apply().applied
    assert main_bytes(session) == b"# later edit\n"


@pytest.mark.parametrize("failure", ["replace", "zero-write", "partial-write-error", "fsync"])
def test_precommit_io_failure_preserves_copy(session, monkeypatch, failure):
    app, _ = session
    app.decide("approve")
    if failure == "replace":
        replace = os.replace

        def fail(src, dst, **kwargs):
            if dst == "main.py":
                raise OSError("injected replacement failure")
            return replace(src, dst, **kwargs)

        monkeypatch.setattr(os, "replace", fail)
    elif failure == "zero-write":
        monkeypatch.setattr(os, "write", lambda *args: 0)
    elif failure == "partial-write-error":
        write = os.write
        calls = []

        def partial(fd, data):
            if calls:
                raise OSError("injected disk full")
            calls.append(True)
            return write(fd, data[:4])

        monkeypatch.setattr(os, "write", partial)
    else:
        monkeypatch.setattr(os, "fsync", lambda *args: (_ for _ in ()).throw(OSError("fsync")))
    result = app.apply()
    assert not result.applied and result.status.startswith("not-applied")
    assert main_bytes(session) == SOURCE.encode()
    assert app.apply().status == "session-finished"


def test_partial_writes_complete_before_replace(session, monkeypatch):
    app, _ = session
    app.decide("approve")
    write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: write(fd, data[:3]))
    assert app.apply().applied
    assert main_bytes(session) == AFTER.encode()


@pytest.mark.parametrize("failure", ["audit", "directory-fsync", "post-read"])
def test_postcommit_failure_never_claims_unchanged(session, monkeypatch, failure):
    app, _ = session
    app.decide("approve")
    replace = os.replace
    committed = []

    def observe(src, dst, **kwargs):
        if committed and failure == "audit":
            raise OSError("injected audit failure")
        result = replace(src, dst, **kwargs)
        if dst == "main.py":
            committed.append(True)
        return result

    monkeypatch.setattr(os, "replace", observe)
    if failure == "directory-fsync":
        sync = os.fsync

        def fail_sync(fd):
            if committed:
                raise OSError("directory fsync")
            return sync(fd)

        monkeypatch.setattr(os, "fsync", fail_sync)
    elif failure == "post-read":
        read = app._workspace.read_main

        def fail_read():
            if committed:
                raise OSError("post-write read")
            return read()

        monkeypatch.setattr(app._workspace, "read_main", fail_read)
    result = app.apply()
    assert result.applied and result.status.startswith("applied-")
    assert result.verification_status == "not-run"
    assert main_bytes(session) == AFTER.encode()
    assert app.restore("approve").status == "restoration-unavailable"


def test_successful_restore_needs_explicit_choice_and_is_single_use(session):
    app, _ = session
    app.decide("approve")
    app.apply()
    preview = app.restoration_preview()
    assert preview["from_text"] == AFTER and preview["to_text"] == SOURCE
    assert app.restore("decline").status == "restoration-decline"
    assert app.restore("cancel").status == "restoration-cancel"
    assert main_bytes(session) == AFTER.encode()
    restored = app.restore("approve")
    assert restored.applied and restored.restored and restored.status == "restored"
    assert main_bytes(session) == SOURCE.encode()
    assert app.restore("approve").status == "restoration-unavailable"
    assert record(session)["restored"]


@pytest.mark.parametrize("mutation", ["content", "inode", "mode", "link"])
def test_restore_refuses_later_work(session, mutation):
    app, _ = session
    app.decide("approve")
    app.apply()
    path = app.workspace / "main.py"
    if mutation == "content":
        path.write_bytes(b"# keep later work\n")
    elif mutation == "inode":
        other = app.workspace / "edit"
        other.write_bytes(AFTER.encode())
        other.chmod(0o600)
        other.replace(path)
    elif mutation == "mode":
        path.chmod(0o644)
    else:
        os.link(path, app.workspace / "link")
    current = path.read_bytes()
    result = app.restore("approve")
    assert not result.restored and result.status == "not-restored"
    assert path.read_bytes() == current
    assert app.restore("approve").status == "restoration-unavailable"


def test_closed_session_retains_files_and_refuses_writes(session):
    app, _ = session
    app.decide("approve")
    app.close()
    app.close()
    assert not app.apply().applied
    assert main_bytes(session) == SOURCE.encode()


def test_no_network_or_subprocess(session, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No provider or target execution allowed")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    app, _ = session
    app.decide("approve")
    assert app.apply().applied
    assert app.restore("approve").restored


def test_unsupported_platform_fails_before_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "supported", lambda: False)
    with pytest.raises(io.WorkspaceError, match="POSIX"):
        io.FixtureWorkspace(b"before", b"after", parent=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["multi-source", "other-name", "revision"])
def test_reject_expanded_application_scope(tmp_path, kind):
    sources = {"main.py": SOURCE, "other.py": "x = 1\n"} if kind == "multi-source" else None
    if kind == "other-name":
        sources = {"other.py": SOURCE}
    request, review = make_context(tmp_path, sources, "a" * 40 if kind == "revision" else None)
    replacements = {"other.py": AFTER} if kind == "other-name" else {"main.py": AFTER}
    with pytest.raises(ContractError, match="only main.py"):
        FixtureApplySession(
            draft(request, review, replacements=replacements), request, review, parent=tmp_path
        )
    assert not list(tmp_path.glob("authzest-fixture-*"))


def test_decision_record_failure_invalidates_session(session, monkeypatch):
    app, _ = session
    app.decide("approve")

    def fail(data):
        raise OSError("journal unavailable")

    monkeypatch.setattr(app._workspace, "write_record", fail)
    with pytest.raises(OSError):
        app.decide("cancel")
    assert app.apply().status == "session-finished"
    assert main_bytes(session) == SOURCE.encode()


def test_session_initialization_failure_closes_handle(tmp_path, monkeypatch):
    if not io.supported():
        pytest.skip("POSIX")
    request, review = make_context(tmp_path)
    closed = []
    close = io.FixtureWorkspace.close

    def observe(self):
        closed.append(self.path)
        close(self)

    def fail(self, data):
        raise OSError("initial journal failure")

    monkeypatch.setattr(io.FixtureWorkspace, "close", observe)
    monkeypatch.setattr(io.FixtureWorkspace, "write_record", fail)
    with pytest.raises(OSError):
        FixtureApplySession(draft(request, review), request, review, parent=tmp_path)
    assert len(closed) == 1 and closed[0].is_dir()


@pytest.mark.parametrize("failure", ["replace", "audit", "post-read"])
def test_restore_failure_distinguishes_committed_state(session, monkeypatch, failure):
    app, _ = session
    app.decide("approve")
    app.apply()
    replace = os.replace
    committed = []

    def fail(src, dst, **kwargs):
        if (failure == "replace" and dst == "main.py") or (failure == "audit" and committed):
            raise OSError("restore fault")
        result = replace(src, dst, **kwargs)
        if dst == "main.py":
            committed.append(True)
        return result

    monkeypatch.setattr(os, "replace", fail)
    if failure == "post-read":
        read = app._workspace.read_main

        def fail_read():
            if committed:
                raise OSError("unconfirmed restore")
            return read()

        monkeypatch.setattr(app._workspace, "read_main", fail_read)
    result = app.restore("approve")
    assert result.applied and result.verification_status == "not-run"
    if failure == "replace":
        assert result.restored is False and main_bytes(session) == AFTER.encode()
    elif failure == "audit":
        assert result.restored is True and result.status.startswith("restored-audit-failed")
        assert main_bytes(session) == SOURCE.encode()
    else:
        assert result.restored is None and result.status == "restoration-state-unconfirmed"
        assert main_bytes(session) == SOURCE.encode()


def test_invalid_restore_choice_never_changes_files(session):
    app, _ = session
    with pytest.raises(ContractError):
        app.restore("yes")
    assert app.restore("approve").status == "restoration-unavailable"
    assert main_bytes(session) == SOURCE.encode()


def test_staging_name_collision_preserves_existing_file(session, monkeypatch):
    app, _ = session
    app.decide("approve")
    collision = app.workspace / ".stage-fixed"
    collision.write_bytes(b"keep this existing entry")
    monkeypatch.setattr(io.uuid, "uuid4", lambda: type("ID", (), {"hex": "fixed"})())
    assert not app.apply().applied
    assert collision.read_bytes() == b"keep this existing entry"
    assert main_bytes(session) == SOURCE.encode()


def test_cleanup_failure_does_not_mask_a_committed_write(session, monkeypatch):
    app, _ = session
    app.decide("approve")

    def fail(*args, **kwargs):
        raise OSError("cleanup refused")

    monkeypatch.setattr(os, "unlink", fail)
    assert app.apply().status == "applied"
    assert main_bytes(session) == AFTER.encode()


@pytest.mark.parametrize("mutation", ["growing", "replacement"])
def test_change_during_read_is_detected(session, monkeypatch, mutation):
    app, _ = session
    read = os.read
    touched = []

    def changing(fd, count):
        data = read(fd, count)
        if not touched:
            touched.append(True)
            path = app.workspace / "main.py"
            if mutation == "growing":
                with path.open("ab") as target:
                    target.write(b"# later\n")
            else:
                path.rename(app.workspace / "moved.py")
                path.write_bytes(SOURCE.encode())
                path.chmod(0o600)
        return data

    monkeypatch.setattr(os, "read", changing)
    with pytest.raises(io.WorkspaceError):
        app._workspace.read_main()


@pytest.mark.parametrize(
    "text", [SOURCE.replace("\n", "\r\n"), SOURCE.rstrip("\n"), SOURCE + "# 한글\u2028text\n"]
)
def test_exact_bytes_survive_apply_restore(tmp_path, text):
    if not io.supported():
        pytest.skip("POSIX")
    request, review = make_context(tmp_path, {"main.py": text})
    after = text.replace("debug=True", "debug=False")
    app = FixtureApplySession(
        draft(request, review, replacements={"main.py": after}), request, review, parent=tmp_path
    )
    try:
        app.decide("approve")
        assert app.apply().applied
        assert (app.workspace / "main.py").read_bytes() == after.encode()
        assert app.restore("approve").restored
        assert (app.workspace / "main.py").read_bytes() == text.encode()
    finally:
        app.close()
