"""Temporary-file-only checks; registered policy text is never evaluated."""

import asyncio
import builtins
import os
import socket
import stat
import subprocess
import sys

import pytest

from authzest.codex.owner_policy_repair_pair import build_owner_policy_repair_pair
from authzest.runner import _owner_policy_file_workspace as io


def registered_bytes(candidate):
    return build_owner_policy_repair_pair().to_dict()["content"][candidate]["text"].encode("utf-8")


@pytest.fixture(autouse=True)
def forbid_policy_and_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Workspace tests must not run a worker, provider, policy or subprocess")

    original_import = builtins.__import__
    original_compile = builtins.compile
    sources = {registered_bytes("before"), registered_bytes("after")}

    def checked_import(name, globals=None, locals=None, fromlist=(), level=0):
        targets = {name, *(f"{name}.{item}" for item in fromlist or ())}
        assert not targets.intersection(
            {
                "authzest.codex.app_server",
                "authzest.runner._owner_policy_worker",
                "authzest.runner._owner_policy_repair_worker",
                "authzest.runner._owner_policy_file_worker",
            }
        )
        return original_import(name, globals, locals, fromlist, level)

    def checked_compile(source, *args, **kwargs):
        content = source.encode("utf-8") if isinstance(source, str) else source
        if isinstance(content, bytes) and content in sources:
            forbidden()
        return original_compile(source, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "compile", checked_compile)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def workspace(tmp_path):
    if not io.supported():
        pytest.skip("Supported POSIX source file operations required")
    created = io.PolicyFileWorkspace(_parent=tmp_path)
    yield created
    created.close()


def test_only_new_private_registered_copy_is_created(workspace, tmp_path):
    assert workspace.path.parent == tmp_path and workspace.path != tmp_path
    assert stat.S_IMODE(workspace.path.stat().st_mode) == 0o700
    assert {item.name for item in workspace.path.iterdir()} == {
        "policy.py",
        "before.txt",
        "after.txt",
    }
    assert workspace.read_policy().data == registered_bytes("before")
    for name, candidate in (
        ("policy.py", "before"),
        ("before.txt", "before"),
        ("after.txt", "after"),
    ):
        path = workspace.path / name
        assert path.read_bytes() == registered_bytes(candidate)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert path.stat().st_nlink == 1
    assert not (tmp_path / "policy.py").exists()


def test_workspace_has_no_source_or_public_destination_parameter(tmp_path):
    for arguments in (
        {"before": b"code"},
        {"after": b"code"},
        {"parent": tmp_path},
        {"path": tmp_path},
    ):
        with pytest.raises(TypeError):
            io.PolicyFileWorkspace(**arguments)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("reason", ["frozen", "flags", "dir-fd", "follow-links"])
def test_unsupported_capability_is_reported_before_creation(tmp_path, monkeypatch, reason):
    if reason == "frozen":
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    elif reason == "flags":
        monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
    elif reason == "dir-fd":
        monkeypatch.setattr(os, "supports_dir_fd", set())
    else:
        monkeypatch.setattr(os, "supports_follow_symlinks", set())
    assert not io.supported()
    with pytest.raises(io.WorkspaceError, match="supported POSIX"):
        io.PolicyFileWorkspace(_parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_apply_restore_records_and_close_preserve_copy_and_stable_root_identity(workspace):
    root = workspace.root_identity
    assert len(root) == 5
    before = workspace.read_policy()
    guards = []
    after = workspace.replace_policy(
        before, registered_bytes("after"), guard=lambda: guards.append(1)
    )
    assert after.data == registered_bytes("after") and after.identity != before.identity
    workspace.write_record(b'{"phase":"applied"}')
    assert workspace.root_identity == root
    restored = workspace.replace_policy(
        after, registered_bytes("before"), guard=lambda: guards.append(2)
    )
    assert restored.data == before.data and restored.identity != before.identity
    assert guards == [1, 2]
    assert workspace.root_identity == root
    workspace.close()
    workspace.close()
    assert (workspace.path / "record.json").read_bytes() == b'{"phase":"applied"}'
    assert (workspace.path / "policy.py").read_bytes() == before.data
    assert not list(workspace.path.glob(".stage-*"))
    for action in (
        workspace.read_policy,
        lambda: workspace.root_identity,
        lambda: workspace.write_record(b"{}"),
    ):
        with pytest.raises(io.WorkspaceError, match="closed"):
            action()


@pytest.mark.parametrize(
    "data", [b"print('unregistered')", b"", "source", bytearray(b"source"), None]
)
def test_replacement_refuses_unregistered_or_nonbyte_source_without_staging(
    workspace, monkeypatch, data
):
    before = workspace.read_policy()
    monkeypatch.setattr(workspace, "_stage", lambda data: pytest.fail("No staging permitted"))
    with pytest.raises(io.WorkspaceError, match="registered bytes"):
        workspace.replace_policy(before, data, guard=lambda: pytest.fail("No guard permitted"))
    assert workspace.read_policy() == before


def test_decision_guard_runs_after_staging_and_can_refuse_without_replacement(workspace):
    before = workspace.read_policy()

    def refuse():
        stages = list(workspace.path.glob(".stage-*"))
        assert len(stages) == 1 and stages[0].read_bytes() == registered_bytes("after")
        assert workspace.read_policy() == before
        raise io.WorkspaceError("expired decision")

    with pytest.raises(io.WorkspaceError, match="expired decision"):
        workspace.replace_policy(before, registered_bytes("after"), guard=refuse)
    assert workspace.read_policy() == before
    assert not list(workspace.path.glob(".stage-*"))


def test_invalid_state_guard_and_record_types_have_no_write_effect(workspace, monkeypatch):
    before = workspace.read_policy()
    monkeypatch.setattr(workspace, "_stage", lambda data: pytest.fail("No staging permitted"))
    with pytest.raises(io.WorkspaceError, match="tracked state"):
        workspace.replace_policy(None, registered_bytes("after"), guard=lambda: None)
    with pytest.raises(io.WorkspaceError, match="decision guard"):
        workspace.replace_policy(before, registered_bytes("after"), guard=None)
    with pytest.raises(io.WorkspaceError, match="Final decision check"):
        workspace.replace_policy(
            before, registered_bytes("after"), guard=lambda: None, before_commit=1
        )
    with pytest.raises(io.WorkspaceError, match="Record must be bytes"):
        workspace.write_record("{}")
    assert workspace.read_policy() == before


def test_final_decision_check_refuses_expiry_during_postguard_read(workspace, monkeypatch):
    before = workspace.read_policy()
    read = workspace.read_policy
    now = [1]
    calls = []

    def guard():
        assert now[0] < 2
        calls.append("guard")

    def delayed_read():
        result = read()
        if calls:
            calls.append("postguard-read")
            now[0] = 2
        return result

    def final_check():
        calls.append("before-commit")
        if now[0] >= 2:
            raise io.WorkspaceError("decision expired after file verification")

    monkeypatch.setattr(workspace, "read_policy", delayed_read)
    with pytest.raises(io.WorkspaceError, match="expired after file verification"):
        workspace.replace_policy(
            before, registered_bytes("after"), guard=guard, before_commit=final_check
        )
    assert calls == ["guard", "postguard-read", "before-commit"]
    assert read() == before
    assert not list(workspace.path.glob(".stage-*"))


@pytest.mark.parametrize("when", ["before-staging", "during-staging", "during-guard"])
def test_later_user_edits_are_preserved(workspace, monkeypatch, when):
    before = workspace.read_policy()
    later = b"# keep later user edits\n"

    def edit():
        (workspace.path / "policy.py").write_bytes(later)

    if when == "before-staging":
        edit()
    elif when == "during-staging":
        stage = workspace._stage

        def changed(data):
            name = stage(data)
            edit()
            return name

        monkeypatch.setattr(workspace, "_stage", changed)
    with pytest.raises(io.WorkspaceError):
        workspace.replace_policy(
            before,
            registered_bytes("after"),
            guard=edit if when == "during-guard" else lambda: None,
        )
    assert (workspace.path / "policy.py").read_bytes() == later


@pytest.mark.parametrize(
    "mutation",
    [
        "same-bytes-inode",
        "mode",
        "hardlink",
        "symlink",
        "directory",
        "missing",
        "fifo",
        "oversize",
        "invalid-utf8",
        "owner",
    ],
)
def test_changed_or_unsafe_file_never_replaces_current_or_outside_file(
    workspace, tmp_path, monkeypatch, mutation
):
    before = workspace.read_policy()
    target = workspace.path / "policy.py"
    outside = tmp_path / "unrelated.txt"
    outside.write_bytes(b"unrelated")
    if mutation == "same-bytes-inode":
        other = workspace.path / "replacement"
        other.write_bytes(before.data)
        other.chmod(0o600)
        other.replace(target)
    elif mutation == "mode":
        target.chmod(0o644)
    elif mutation == "hardlink":
        os.link(target, workspace.path / "another-link")
    elif mutation in {"symlink", "directory", "missing", "fifo"}:
        target.unlink()
        if mutation == "symlink":
            target.symlink_to(outside)
        elif mutation == "directory":
            target.mkdir()
        elif mutation == "fifo":
            os.mkfifo(target, 0o600)
    elif mutation == "oversize":
        target.write_bytes(b"x" * (io.MAX_SOURCE_BYTES + 1))
    elif mutation == "invalid-utf8":
        target.write_bytes(b"\xff")
    else:
        monkeypatch.setattr(os, "geteuid", lambda: before.identity[3] + 1)
    with pytest.raises((OSError, io.WorkspaceError)):
        workspace.replace_policy(before, registered_bytes("after"), guard=lambda: None)
    assert outside.read_bytes() == b"unrelated"


@pytest.mark.parametrize("mutation", ["mode", "rename", "symlink", "new-directory"])
def test_root_changes_are_refused(workspace, tmp_path, mutation):
    if mutation == "mode":
        workspace.path.chmod(0o755)
    else:
        workspace.path.rename(tmp_path / "moved-copy")
        if mutation == "symlink":
            workspace.path.symlink_to(tmp_path / "moved-copy", target_is_directory=True)
        elif mutation == "new-directory":
            workspace.path.mkdir(mode=0o700)
    for action in (
        workspace.read_policy,
        lambda: workspace.root_identity,
        lambda: workspace.write_record(b"{}"),
    ):
        with pytest.raises((OSError, io.WorkspaceError)):
            action()


@pytest.mark.parametrize("data", [b"", b"x" * 32_768, b"a\r\nb\r\n", "# 한글\u2028text".encode()])
def test_bounded_reads_preserve_exact_utf8_bytes_without_normalization(workspace, data):
    (workspace.path / "policy.py").write_bytes(data)
    assert workspace.read_policy().data == data


@pytest.mark.parametrize("mutation", ["grow", "replace-name"])
def test_midread_changes_are_detected(workspace, monkeypatch, mutation):
    read = os.read
    changed = []

    def changing(fd, count):
        data = read(fd, count)
        if not changed:
            changed.append(True)
            path = workspace.path / "policy.py"
            if mutation == "grow":
                with path.open("ab") as handle:
                    handle.write(b"# edit\n")
            else:
                path.rename(workspace.path / "moved.py")
                path.write_bytes(registered_bytes("before"))
                path.chmod(0o600)
        return data

    monkeypatch.setattr(os, "read", changing)
    with pytest.raises(io.WorkspaceError):
        workspace.read_policy()


def test_incomplete_read_is_not_accepted_as_the_full_snapshot(workspace, monkeypatch):
    monkeypatch.setattr(os, "read", lambda *args: b"")
    with pytest.raises(io.WorkspaceError, match="changed during read"):
        workspace.read_policy()


@pytest.mark.parametrize("failure", ["replace", "zero-write", "partial-write", "stage-fsync"])
def test_precommit_failure_keeps_original_bytes(workspace, monkeypatch, failure):
    before = workspace.read_policy()
    if failure == "replace":
        monkeypatch.setattr(
            os, "replace", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("replace"))
        )
    elif failure == "zero-write":
        monkeypatch.setattr(os, "write", lambda *args: 0)
    elif failure == "partial-write":
        write = os.write
        calls = []

        def fail_write(fd, data):
            if calls:
                raise OSError("partial")
            calls.append(True)
            return write(fd, data[:3])

        monkeypatch.setattr(os, "write", fail_write)
    else:
        monkeypatch.setattr(os, "fsync", lambda *args: (_ for _ in ()).throw(OSError("fsync")))
    with pytest.raises(OSError):
        workspace.replace_policy(before, registered_bytes("after"), guard=lambda: None)
    assert workspace.read_policy() == before
    assert not list(workspace.path.glob(".stage-*"))


def test_short_writes_complete_before_replacement(workspace, monkeypatch):
    before = workspace.read_policy()
    write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: write(fd, data[:3]))
    assert workspace.replace_policy(
        before, registered_bytes("after"), guard=lambda: None
    ).data == registered_bytes("after")


@pytest.mark.parametrize("failure", ["directory-fsync", "post-read", "unexpected-content"])
def test_postcommit_failure_reports_committed_state(workspace, monkeypatch, failure):
    before = workspace.read_policy()
    replace = os.replace
    fsync = os.fsync
    read = workspace.read_policy
    committed = []

    def observe(src, dst, **kwargs):
        result = replace(src, dst, **kwargs)
        committed.append(True)
        if failure == "unexpected-content":
            (workspace.path / "policy.py").write_bytes(b"# changed after rename\n")
        return result

    def fail_sync(fd):
        if committed:
            raise OSError("directory fsync")
        return fsync(fd)

    def fail_read():
        if committed:
            raise OSError("post-read")
        return read()

    monkeypatch.setattr(os, "replace", observe)
    if failure == "directory-fsync":
        monkeypatch.setattr(os, "fsync", fail_sync)
    elif failure == "post-read":
        monkeypatch.setattr(workspace, "read_policy", fail_read)
    with pytest.raises(io.CommittedWriteError):
        workspace.replace_policy(before, registered_bytes("after"), guard=lambda: None)
    expected = (
        b"# changed after rename\n"
        if failure == "unexpected-content"
        else registered_bytes("after")
    )
    assert (workspace.path / "policy.py").read_bytes() == expected


def test_staging_collision_does_not_remove_existing_entry(workspace, monkeypatch):
    collision = workspace.path / ".stage-fixed"
    collision.write_bytes(b"preserve")
    monkeypatch.setattr(io.uuid, "uuid4", lambda: type("Nonce", (), {"hex": "fixed"})())
    with pytest.raises(FileExistsError):
        workspace.replace_policy(
            workspace.read_policy(), registered_bytes("after"), guard=lambda: None
        )
    assert collision.read_bytes() == b"preserve"


def test_record_replacement_does_not_follow_external_symlink(workspace, tmp_path):
    outside = tmp_path / "unrelated.json"
    outside.write_bytes(b"preserve")
    record = workspace.path / "record.json"
    record.symlink_to(outside)
    workspace.write_record(b'{"phase":"ready-before"}')
    assert outside.read_bytes() == b"preserve"
    assert not record.is_symlink()
    assert stat.S_IMODE(record.stat().st_mode) == 0o600


def test_record_directory_fsync_failure_is_unconfirmed_commit(workspace, monkeypatch):
    fsync = os.fsync

    def fail_directory(fd):
        if fd == workspace._fd:
            raise OSError("directory fsync")
        return fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory)
    with pytest.raises(io.CommittedWriteError):
        workspace.write_record(b'{"phase":"retained"}')
    assert (workspace.path / "record.json").read_bytes() == b'{"phase":"retained"}'


@pytest.mark.parametrize("operation", ["policy", "record"])
@pytest.mark.parametrize("point", ["rename-return", "directory-fsync"])
@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
def test_postrename_interrupt_preserves_exception_and_commit_metadata(
    workspace, monkeypatch, operation, point, exception_type
):
    before = workspace.read_policy()
    replace = os.replace
    fsync = os.fsync
    interrupt = exception_type("stop")

    def interrupted_replace(src, dst, **kwargs):
        result = replace(src, dst, **kwargs)
        if point == "rename-return":
            raise interrupt
        return result

    def interrupted_fsync(fd):
        if point == "directory-fsync" and fd == workspace._fd:
            raise interrupt
        return fsync(fd)

    monkeypatch.setattr(os, "replace", interrupted_replace)
    monkeypatch.setattr(os, "fsync", interrupted_fsync)
    with pytest.raises(exception_type) as caught:
        if operation == "policy":
            workspace.replace_policy(before, registered_bytes("after"), guard=lambda: None)
        else:
            workspace.write_record(b'{"phase":"retained"}')
    assert caught.value is interrupt
    assert interrupt.workspace_commit_uncertain is True
    assert getattr(interrupt, "workspace_committed", False) is (point == "directory-fsync")
    assert (workspace.path / "policy.py").read_bytes() == (
        registered_bytes("after") if operation == "policy" else before.data
    )
    if operation == "record":
        assert (workspace.path / "record.json").read_bytes() == b'{"phase":"retained"}'
    assert not list(workspace.path.glob(".stage-*"))


def test_evidence_snapshots_are_not_loaded_as_replacement_authority(workspace):
    original = workspace.read_policy()
    (workspace.path / "before.txt").write_bytes(b"untrusted later evidence edit")
    applied = workspace.replace_policy(original, registered_bytes("after"), guard=lambda: None)
    restored = workspace.replace_policy(applied, registered_bytes("before"), guard=lambda: None)
    assert restored.data == original.data


def test_cleanup_failure_does_not_mask_confirmed_replacement(workspace, monkeypatch):
    original = workspace.read_policy()
    monkeypatch.setattr(
        os, "unlink", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cleanup"))
    )
    result = workspace.replace_policy(original, registered_bytes("after"), guard=lambda: None)
    assert result.data == registered_bytes("after")


@pytest.mark.parametrize(
    "stage", ["create-policy", "create-before", "create-after", "sync-directory"]
)
@pytest.mark.parametrize("interrupt", [False, True])
def test_initialization_failure_retains_path_stage_and_closes_handle(
    tmp_path, monkeypatch, stage, interrupt
):
    if not io.supported():
        pytest.skip("Supported POSIX source file operations required")
    create = io.PolicyFileWorkspace._create
    close = io.PolicyFileWorkspace.close
    fsync = os.fsync
    closed = []

    def fail():
        raise KeyboardInterrupt() if interrupt else OSError("private initialization detail")

    def create_file(self, name, data):
        if (
            stage
            == {
                "policy.py": "create-policy",
                "before.txt": "create-before",
                "after.txt": "create-after",
            }[name]
        ):
            fail()
        return create(self, name, data)

    def sync(fd):
        if stage == "sync-directory" and stat.S_ISDIR(os.fstat(fd).st_mode):
            fail()
        return fsync(fd)

    def observe_close(self):
        fd = self._fd
        close(self)
        closed.append(fd)

    monkeypatch.setattr(io.PolicyFileWorkspace, "_create", create_file)
    monkeypatch.setattr(io.PolicyFileWorkspace, "close", observe_close)
    monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises(
        KeyboardInterrupt if interrupt else io.WorkspaceInitializationError
    ) as caught:
        io.PolicyFileWorkspace(_parent=tmp_path)
    error = caught.value.workspace_initialization if interrupt else caught.value
    assert isinstance(error, io.WorkspaceInitializationError)
    assert error.initialization_stage == stage
    assert error.created_path.parent == tmp_path and error.created_path.is_dir()
    assert "private initialization detail" not in str(error)
    assert len(closed) == 1
    with pytest.raises(OSError):
        os.fstat(closed[0])


def test_mkdtemp_failure_does_not_invent_retained_path(tmp_path, monkeypatch):
    if not io.supported():
        pytest.skip("Supported POSIX source file operations required")
    monkeypatch.setattr(
        io.tempfile, "mkdtemp", lambda **kwargs: (_ for _ in ()).throw(OSError("creation"))
    )
    with pytest.raises(OSError) as caught:
        io.PolicyFileWorkspace(_parent=tmp_path)
    assert not isinstance(caught.value, io.WorkspaceInitializationError)
    assert list(tmp_path.iterdir()) == []
