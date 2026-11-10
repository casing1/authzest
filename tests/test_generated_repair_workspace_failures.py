"""Adversarial private-copy file checks; candidate Python text stays inert."""

from __future__ import annotations

import ast
import asyncio
import builtins
import json
import os
import socket
import stat
import subprocess
import sys

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.codex.generated_repair import (
    build_generated_repair_request,
    validate_generated_repair_proposal,
)
from authzest.runner import _generated_repair_workspace as io
from authzest.runner.generated_repair_verification import (
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


@pytest.fixture(autouse=True)
def keep_candidate_text_inert(monkeypatch, request, tmp_path):
    assert len(request.node.nodeid) < 512
    # Only maintained stdlib AST initialization may occur before these guards.
    assert ast.unparse(ast.Constant(value=None)) == "None"

    def forbidden(*args, **kwargs):
        pytest.fail("Private-copy tests must not execute candidate code or external effects")

    original_import = builtins.__import__
    original_compile = builtins.compile

    def checked_import(name, *args, **kwargs):
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
        # ast.parse performs a non-executing PyCF_ONLY_AST compile internally.
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def context():
    request = build_generated_repair_request()

    def proposal_for(status="proposed-change"):
        source = request.to_dict()["scenario"]["source"]
        return validate_generated_repair_proposal(
            canonical(
                {
                    "schema_version": "1.0",
                    "request_id": request.request_id,
                    "status": status,
                    "rationale": "Maintained inert file-operation regression only.",
                    "evidence_ids": list(request.to_dict()["evidence_ids"].values()),
                    "assumptions": ["No runtime execution or approvals are provided."],
                    "uncertainties": ["Runtime behavior is unobserved."],
                    "limitations": ["File operations do not verify a repair."],
                    "proposal": {
                        "source_path": "app.py",
                        "before_sha256": source["sha256"],
                        "after_text": source["text"] + "\n# Inert maintained candidate.\n",
                        "test_path": "tests/test_generated_ownership.py",
                        "test_text": "# Inert maintained test text; never collected.\n",
                    }
                    if status == "proposed-change"
                    else None,
                }
            ),
            request,
        )

    proposal = proposal_for()
    preview = build_generated_repair_verification_preview(request, proposal)
    return request, proposal_for, preview


@pytest.fixture
def workspace(tmp_path, context):
    if not io.supported():
        pytest.skip("Private-copy operations require supported POSIX source mode")
    created = io.GeneratedRepairWorkspace(context[2], _parent=tmp_path)
    yield created
    created.close()


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_nonchange_preflight_never_creates_a_directory(context, tmp_path, monkeypatch, status):
    request, proposal_for, _ = context
    preview = build_generated_repair_verification_preview(request, proposal_for(status))
    monkeypatch.setattr(
        io.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("No directory for non-change")
    )
    with pytest.raises((io.WorkspaceError, ContractError)):
        io.GeneratedRepairWorkspace(preview, _parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mutation", ["wrong-type", "identity", "approved", "proposal"])
def test_forged_preview_preflight_has_no_file_effects(context, tmp_path, monkeypatch, mutation):
    if mutation == "wrong-type":
        preview = context[2].to_dict()
    else:
        data = context[2].to_dict()
        if mutation == "identity":
            data["request_id"] = "stale-request"
        elif mutation == "approved":
            data["execution_authorized"] = True
        else:
            data["proposal_preview"]["proposal"]["proposal"]["after_text"] += "# edit\n"
        preview = object.__new__(GeneratedRepairVerificationPreview)
        object.__setattr__(preview, "payload_json", canonical(data))
    monkeypatch.setattr(
        io.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("No directory for forged input")
    )
    with pytest.raises((io.WorkspaceError, ContractError)):
        io.GeneratedRepairWorkspace(preview, _parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("reason", ["frozen", "flags", "dir-fd", "follow-links"])
def test_unsupported_runtime_is_rejected_before_creation(context, tmp_path, monkeypatch, reason):
    if reason == "frozen":
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    elif reason == "flags":
        monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
    elif reason == "dir-fd":
        monkeypatch.setattr(os, "supports_dir_fd", set())
    else:
        monkeypatch.setattr(os, "supports_follow_symlinks", set())
    assert not io.supported()
    with pytest.raises(io.WorkspaceError):
        io.GeneratedRepairWorkspace(context[2], _parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "name", TRACKED_FILES, ids=["app", "test", "before", "after", "test-snapshot", "record"]
)
@pytest.mark.parametrize(
    "mutation", ["edit", "same-bytes-inode", "mode", "hardlink", "symlink", "fifo", "missing"]
)
def test_any_tracked_file_tamper_refuses_application_without_outside_write(
    workspace, tmp_path, name, mutation
):
    before = workspace.read_source()
    target = workspace.path / name
    initial = target.read_bytes()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"preserve outside bytes\n")
    if mutation == "edit":
        target.write_bytes(initial + b" ")
    elif mutation == "same-bytes-inode":
        other = target.with_name("replacement")
        other.write_bytes(initial)
        other.chmod(0o600)
        other.replace(target)
    elif mutation == "mode":
        target.chmod(0o644)
    elif mutation == "hardlink":
        os.link(target, target.with_name("extra-link"))
    else:
        target.unlink()
        if mutation == "symlink":
            target.symlink_to(outside)
        elif mutation == "fifo":
            os.mkfifo(target, 0o600)
    with pytest.raises((io.WorkspaceError, OSError)):
        workspace.apply_source(before, guard=lambda: pytest.fail("No guard after tamper"))
    assert outside.read_bytes() == b"preserve outside bytes\n"
    if name != "app.py":
        assert (workspace.path / "app.py").read_bytes() == before.data
    elif mutation == "edit":
        assert target.read_bytes() == initial + b" "


@pytest.mark.parametrize("directory", ["root", "tests"])
@pytest.mark.parametrize("mutation", ["mode", "moved", "symlink", "new-inode"])
def test_directory_identity_or_permissions_change_refuses_operations(
    workspace, tmp_path, directory, mutation
):
    before = workspace.read_source()
    target = workspace.path if directory == "root" else workspace.path / "tests"
    if mutation == "mode":
        target.chmod(0o755)
    else:
        moved = tmp_path / f"moved-{directory}"
        target.rename(moved)
        if mutation == "symlink":
            target.symlink_to(moved, target_is_directory=True)
        elif mutation == "new-inode":
            target.mkdir(mode=0o700)
    for action in (
        workspace.read_source,
        workspace.read_test,
        workspace.read_record,
        lambda: workspace.apply_source(before, guard=lambda: None),
    ):
        with pytest.raises((io.WorkspaceError, OSError)):
            action()


@pytest.mark.parametrize("name", ["app.py", "tests/test_generated_ownership.py", "record.json"])
@pytest.mark.parametrize("mutation", ["oversize", "invalid-utf8", "truncated"])
def test_changed_or_unbounded_utf8_is_never_accepted(workspace, name, mutation):
    before = workspace.read_source()
    target = workspace.path / name
    if mutation == "oversize":
        target.write_bytes(b"x" * 262_145)
    elif mutation == "invalid-utf8":
        target.write_bytes(b"\xff")
    else:
        target.write_bytes(b"")
    with pytest.raises((io.WorkspaceError, OSError)):
        workspace.apply_source(before, guard=lambda: pytest.fail("No guard for changed bytes"))


@pytest.mark.parametrize("mutation", ["grow", "replace-name", "short-read"])
def test_changes_or_incomplete_reads_are_not_full_file_evidence(workspace, monkeypatch, mutation):
    read = os.read
    changed = []
    target = workspace.path / "app.py"

    def changing(fd, count):
        if mutation == "short-read":
            return b""
        data = read(fd, count)
        if not changed:
            changed.append(True)
            if mutation == "grow":
                with target.open("ab") as handle:
                    handle.write(b"# later bytes\n")
            else:
                initial = target.read_bytes()
                target.rename(workspace.path / "moved-app.py")
                target.write_bytes(initial)
                target.chmod(0o600)
        return data

    monkeypatch.setattr(os, "read", changing)
    with pytest.raises((io.WorkspaceError, OSError)):
        workspace.read_source()


@pytest.mark.parametrize(
    "bad", [None, False, b"source", object()], ids=["none", "bool", "bytes", "object"]
)
def test_untracked_expected_state_never_runs_guard(workspace, bad):
    before = workspace.read_source()
    with pytest.raises(io.WorkspaceError):
        workspace.apply_source(bad, guard=lambda: pytest.fail("No guard for invalid state"))
    assert workspace.read_source() == before


@pytest.mark.parametrize(
    "guard_kind", ["none", "truthy", "falsey", "async-function", "async-return"]
)
def test_guard_must_be_synchronous_and_return_exactly_none(workspace, guard_kind):
    before = workspace.read_source()

    async def asynchronous_guard():
        return None

    guards = {
        "none": None,
        "truthy": lambda: True,
        "falsey": lambda: False,
        "async-function": asynchronous_guard,
        "async-return": lambda: asynchronous_guard(),
    }
    with pytest.raises(io.WorkspaceError):
        workspace.apply_source(before, guard=guards[guard_kind])
    assert workspace.read_source() == before
    assert not list(workspace.path.glob(".stage-*"))


def test_guard_refusal_retains_ready_before_and_cleans_staging(workspace):
    before = workspace.read_source()

    def refusal():
        raise io.WorkspaceError("decision expired")

    with pytest.raises(io.WorkspaceError, match="decision expired"):
        workspace.apply_source(before, guard=refusal)
    assert workspace.read_source() == before
    assert workspace.state == "ready-before"
    assert not list(workspace.path.glob(".stage-*"))


@pytest.mark.parametrize(
    "name", TRACKED_FILES, ids=["app", "test", "before", "after", "test-snapshot", "record"]
)
def test_guard_edit_is_preserved_and_blocks_replacement(workspace, name):
    before = workspace.read_source()
    target = workspace.path / name
    edit = target.read_bytes() + b"# changed during decision\n"

    def edit_during_guard():
        target.write_bytes(edit)

    with pytest.raises((io.WorkspaceError, OSError)):
        workspace.apply_source(before, guard=edit_during_guard)
    assert target.read_bytes() == edit
    if name != "app.py":
        assert (workspace.path / "app.py").read_bytes() == before.data


def test_wrong_phase_and_stale_snapshot_cannot_reapply_or_restore(workspace):
    before = workspace.read_source()
    with pytest.raises(io.WorkspaceError):
        workspace.restore_source(before, guard=lambda: pytest.fail("Restore before apply"))
    after = workspace.apply_source(before, guard=lambda: None)
    for action in (
        lambda: workspace.apply_source(after, guard=lambda: pytest.fail("Double apply")),
        lambda: workspace.restore_source(before, guard=lambda: pytest.fail("Stale restore")),
    ):
        with pytest.raises(io.WorkspaceError):
            action()
    assert workspace.read_source() == after
    restored = workspace.restore_source(after, guard=lambda: None)
    assert restored.data == before.data
    for action in (
        lambda: workspace.apply_source(restored, guard=lambda: pytest.fail("Applied once")),
        lambda: workspace.restore_source(restored, guard=lambda: pytest.fail("Restored once")),
    ):
        with pytest.raises(io.WorkspaceError):
            action()
    assert workspace.read_source() == restored


def test_restore_does_not_overwrite_later_user_edit(workspace):
    before = workspace.read_source()
    after = workspace.apply_source(before, guard=lambda: None)
    later = b"# Keep a later user edit, not an approved source snapshot.\n"
    (workspace.path / "app.py").write_bytes(later)
    with pytest.raises((io.WorkspaceError, OSError)):
        workspace.restore_source(after, guard=lambda: pytest.fail("No restore after edit"))
    assert (workspace.path / "app.py").read_bytes() == later


def test_close_is_idempotent_and_never_deletes_retained_evidence(workspace):
    retained = {name: (workspace.path / name).read_bytes() for name in TRACKED_FILES}
    workspace.close()
    workspace.close()
    assert {name: (workspace.path / name).read_bytes() for name in TRACKED_FILES} == retained
    for read in (workspace.read_source, workspace.read_test, workspace.read_record):
        with pytest.raises(io.WorkspaceError):
            read()


@pytest.mark.parametrize("nth_write", [1, 2, 4, 6])
@pytest.mark.parametrize("interrupted", [False, True], ids=["error", "interrupt"])
def test_partial_initialization_reports_retained_path_and_stage(
    context, tmp_path, monkeypatch, nth_write, interrupted
):
    if not io.supported():
        pytest.skip("Private-copy operations require supported POSIX source mode")
    write = os.write
    calls = []
    interruption = KeyboardInterrupt("stop initialization")

    def fail_write(fd, data):
        calls.append(fd)
        if len(calls) == nth_write:
            if interrupted:
                raise interruption
            raise OSError("private initialization diagnostic must not leak")
        return write(fd, data)

    monkeypatch.setattr(os, "write", fail_write)
    expected_error = KeyboardInterrupt if interrupted else io.WorkspaceInitializationError
    with pytest.raises(expected_error) as caught:
        io.GeneratedRepairWorkspace(context[2], _parent=tmp_path)
    if interrupted:
        assert caught.value is interruption
        error = interruption.workspace_initialization
    else:
        error = caught.value
    assert isinstance(error, io.WorkspaceInitializationError)
    assert error.created_path.parent == tmp_path
    assert error.created_path.is_dir()
    assert stat.S_IMODE(error.created_path.stat().st_mode) == 0o700
    assert isinstance(error.initialization_stage, str) and error.initialization_stage
    assert isinstance(error.file_states, dict)
    assert "private initialization diagnostic" not in str(error)
    # The rejected partial directory remains inspectable, never silently deleted.
    assert list(tmp_path.iterdir()) == [error.created_path]


def test_mkdtemp_failure_does_not_invent_a_retained_copy(context, tmp_path, monkeypatch):
    if not io.supported():
        pytest.skip("Private-copy operations require supported POSIX source mode")

    def fail_creation(**kwargs):
        raise OSError("directory creation failed")

    monkeypatch.setattr(io.tempfile, "mkdtemp", fail_creation)
    with pytest.raises((OSError, io.WorkspaceError)) as caught:
        io.GeneratedRepairWorkspace(context[2], _parent=tmp_path)
    if isinstance(caught.value, io.WorkspaceInitializationError):
        assert caught.value.created_path is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ["zero-write", "partial-write", "stage-fsync"])
def test_pre_source_commit_write_failures_preserve_before(workspace, monkeypatch, failure):
    before = workspace.read_source()
    if failure == "zero-write":
        monkeypatch.setattr(os, "write", lambda *args: 0)
    elif failure == "partial-write":
        write = os.write
        wrote = []

        def fail_after_partial(fd, data):
            if wrote:
                raise OSError("partial staged write")
            wrote.append(True)
            return write(fd, data[:3])

        monkeypatch.setattr(os, "write", fail_after_partial)
    else:

        def fail_file_sync(fd):
            raise OSError("staging fsync failed")

        monkeypatch.setattr(os, "fsync", fail_file_sync)
    with pytest.raises((OSError, io.WorkspaceError)):
        workspace.apply_source(before, guard=lambda: None)
    assert (workspace.path / "app.py").read_bytes() == before.data
    # An incomplete write has no verified stage pin. Retain it for inspection
    # rather than unlinking an entry whose exact identity is unconfirmed.
    assert list(workspace.path.glob(".stage-*"))
    assert workspace.state == "state-unconfirmed"
    with pytest.raises(io.WorkspaceError):
        workspace.restore_source(before, guard=lambda: pytest.fail("No uncertain restore"))


def test_short_staging_writes_complete_without_changing_the_planned_bytes(workspace, monkeypatch):
    before = workspace.read_source()
    expected = (workspace.path / "after.txt").read_bytes()
    write = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: write(fd, data[:3]))
    after = workspace.apply_source(before, guard=lambda: None)
    assert after.data == expected
    assert workspace.state == "applied-after"


@pytest.mark.parametrize("point", ["before-rename", "rename-return", "post-fsync", "final-record"])
@pytest.mark.parametrize("operation", ["apply", "restore"])
def test_source_commit_failures_are_unconfirmed_and_do_not_automatically_restore(
    workspace, monkeypatch, point, operation
):
    before = workspace.read_source()
    after_bytes = (workspace.path / "after.txt").read_bytes()
    if operation == "restore":
        current = workspace.apply_source(before, guard=lambda: None)
        transition = workspace.restore_source
        replacement = before.data
    else:
        current = before
        transition = workspace.apply_source
        replacement = after_bytes
    replace = os.replace
    fsync = os.fsync
    renamed = []

    def failing_replace(src, dst, **kwargs):
        if os.fspath(dst) == "app.py":
            if point == "before-rename":
                raise OSError("source replace failed before return")
            result = replace(src, dst, **kwargs)
            renamed.append(True)
            if point == "rename-return":
                raise OSError("source changed but call did not return")
            return result
        if os.fspath(dst) == "record.json" and renamed and point == "final-record":
            raise OSError("final journal update failed")
        return replace(src, dst, **kwargs)

    def failing_fsync(fd):
        if point == "post-fsync" and renamed and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("directory fsync after source rename failed")
        return fsync(fd)

    monkeypatch.setattr(os, "replace", failing_replace)
    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(io.CommittedWriteError) as caught:
        transition(current, guard=lambda: None)
    error = caught.value
    assert error.operation == operation
    assert error.commit_attempted is True
    assert error.committed is (point in {"post-fsync", "final-record"})
    assert error.state_unconfirmed is True
    assert workspace.state == "state-unconfirmed"
    expected = current.data if point == "before-rename" else replacement
    assert (workspace.path / "app.py").read_bytes() == expected
    with pytest.raises(io.WorkspaceError):
        workspace.restore_source(before, guard=lambda: pytest.fail("No uncertain restore"))
    assert (workspace.path / "app.py").read_bytes() == expected


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
@pytest.mark.parametrize("point", ["rename-return", "post-fsync"])
@pytest.mark.parametrize("operation", ["apply", "restore"])
def test_postrename_cancellation_propagates_with_uncertain_commit_metadata(
    workspace, monkeypatch, exception_type, point, operation
):
    before = workspace.read_source()
    after_bytes = (workspace.path / "after.txt").read_bytes()
    if operation == "restore":
        current = workspace.apply_source(before, guard=lambda: None)
        transition = workspace.restore_source
        replacement = before.data
    else:
        current = before
        transition = workspace.apply_source
        replacement = after_bytes
    replace = os.replace
    fsync = os.fsync
    interruption = exception_type("cancel this file operation")
    renamed = []

    def interrupted_replace(src, dst, **kwargs):
        result = replace(src, dst, **kwargs)
        if os.fspath(dst) == "app.py":
            renamed.append(True)
            if point == "rename-return":
                raise interruption
        return result

    def interrupted_fsync(fd):
        if point == "post-fsync" and renamed and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise interruption
        return fsync(fd)

    monkeypatch.setattr(os, "replace", interrupted_replace)
    monkeypatch.setattr(os, "fsync", interrupted_fsync)
    with pytest.raises(exception_type) as caught:
        transition(current, guard=lambda: None)
    assert caught.value is interruption
    error = interruption.workspace_commit_error
    assert isinstance(error, io.CommittedWriteError)
    assert error.operation == operation
    assert error.commit_attempted is True
    assert error.committed is (point == "post-fsync")
    assert error.state_unconfirmed is True
    assert workspace.state == "state-unconfirmed"
    assert (workspace.path / "app.py").read_bytes() == replacement


@pytest.mark.parametrize("operation", ["apply", "restore"])
def test_postrename_user_edit_is_preserved_not_accepted_as_the_planned_write(
    workspace, monkeypatch, operation
):
    before = workspace.read_source()
    if operation == "restore":
        current = workspace.apply_source(before, guard=lambda: None)
        transition = workspace.restore_source
    else:
        current = before
        transition = workspace.apply_source
    replace = os.replace
    later = b"# User edit after the source rename must survive.\n"

    def later_edit(src, dst, **kwargs):
        result = replace(src, dst, **kwargs)
        if os.fspath(dst) == "app.py":
            (workspace.path / "app.py").write_bytes(later)
        return result

    monkeypatch.setattr(os, "replace", later_edit)
    with pytest.raises(io.CommittedWriteError) as caught:
        transition(current, guard=lambda: None)
    assert caught.value.operation == operation
    assert caught.value.commit_attempted is True
    assert caught.value.committed is True
    assert workspace.state == "state-unconfirmed"
    assert (workspace.path / "app.py").read_bytes() == later


@pytest.mark.parametrize("interrupted", [False, True], ids=["error", "interrupt"])
def test_failed_staging_cleanup_is_reported_and_retained(workspace, monkeypatch, interrupted):
    before = workspace.read_source()
    interruption = KeyboardInterrupt("cleanup interrupted")

    def fail_unlink(*args, **kwargs):
        if interrupted:
            raise interruption
        raise OSError("cleanup failed")

    def refuse():
        raise io.WorkspaceError("decision refused")

    monkeypatch.setattr(os, "unlink", fail_unlink)
    expected_error = KeyboardInterrupt if interrupted else io.CommittedWriteError
    with pytest.raises(expected_error) as caught:
        workspace.apply_source(before, guard=refuse)
    error = interruption.workspace_commit_error if interrupted else caught.value
    assert isinstance(error, io.CommittedWriteError)
    assert error.operation == "apply"
    assert error.commit_attempted is False
    assert error.committed is False
    assert error.cleanup_failed is True
    assert error.state_unconfirmed is True
    if interrupted:
        assert interruption.workspace_cleanup_failed is True
    assert workspace.state == "state-unconfirmed"
    assert (workspace.path / "app.py").read_bytes() == before.data
    assert list(workspace.path.glob(".stage-*"))


def test_changed_effective_owner_blocks_read_and_application(workspace, monkeypatch):
    before = workspace.read_source()
    monkeypatch.setattr(os, "geteuid", lambda: before.identity[3] + 1)
    with pytest.raises((OSError, io.WorkspaceError)):
        workspace.read_source()
    with pytest.raises(io.WorkspaceError):
        workspace.apply_source(before, guard=lambda: pytest.fail("Wrong effective owner"))
    assert (workspace.path / "app.py").read_bytes() == before.data


@pytest.mark.parametrize("mutation", ["edit", "replace", "symlink"])
def test_guard_cannot_substitute_staged_bytes_or_trigger_unsafe_cleanup(
    workspace, tmp_path, mutation
):
    before = workspace.read_source()
    outside = tmp_path / "outside-stage.txt"
    outside.write_bytes(b"keep this outside file\n")
    retained = []

    def mutate_staging():
        stages = list(workspace.path.glob(".stage-*"))
        assert len(stages) == 1
        target = stages[0]
        retained.append(target)
        if mutation == "edit":
            target.write_bytes(b"# An unapproved staging edit.\n")
        elif mutation == "replace":
            replacement = workspace.path / "stage-substitute"
            replacement.write_bytes(target.read_bytes())
            replacement.chmod(0o600)
            replacement.replace(target)
        else:
            target.unlink()
            target.symlink_to(outside)

    with pytest.raises(io.CommittedWriteError) as caught:
        workspace.apply_source(before, guard=mutate_staging)
    assert caught.value.commit_attempted is False
    assert caught.value.committed is False
    assert caught.value.cleanup_failed is True
    assert workspace.state == "state-unconfirmed"
    assert (workspace.path / "app.py").read_bytes() == before.data
    assert outside.read_bytes() == b"keep this outside file\n"
    assert retained[0].exists()
    if mutation == "symlink":
        assert retained[0].is_symlink()


@pytest.mark.parametrize("operation", ["apply", "restore"])
@pytest.mark.parametrize("point", ["before-rename", "rename-return", "post-fsync"])
def test_intent_journal_failure_blocks_source_write_and_records_separate_commit_state(
    workspace, monkeypatch, operation, point
):
    before = workspace.read_source()
    if operation == "restore":
        current = workspace.apply_source(before, guard=lambda: None)
        transition = workspace.restore_source
    else:
        current = before
        transition = workspace.apply_source
    replace = os.replace
    fsync = os.fsync
    intent_renamed = []

    def fail_intent(src, dst, **kwargs):
        if os.fspath(dst) == "app.py":
            pytest.fail("An unconfirmed intent journal must block source replacement")
        if os.fspath(dst) == "record.json":
            if point == "before-rename":
                raise OSError("intent journal rename failed")
            result = replace(src, dst, **kwargs)
            intent_renamed.append(True)
            if point == "rename-return":
                raise OSError("intent renamed but return was interrupted")
            return result
        return replace(src, dst, **kwargs)

    def fail_after_intent(fd):
        if point == "post-fsync" and intent_renamed and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("intent journal directory fsync failed")
        return fsync(fd)

    monkeypatch.setattr(os, "replace", fail_intent)
    monkeypatch.setattr(os, "fsync", fail_after_intent)
    with pytest.raises(io.CommittedWriteError) as caught:
        transition(current, guard=lambda: None)
    error = caught.value
    assert error.operation == operation
    assert error.commit_attempted is False
    assert error.committed is False
    assert error.journal_attempted is True
    assert error.journal_committed is (point == "post-fsync")
    assert error.journal_phase == operation
    assert workspace.state == "state-unconfirmed"
    assert (workspace.path / "app.py").read_bytes() == current.data
    record = json.loads((workspace.path / "record.json").read_bytes())
    if point != "before-rename":
        assert record["phase"] == "state-unconfirmed"
        assert record["pending_operation"] == operation
        if operation == "apply":
            assert record["source_application"] == "apply-pending"
        else:
            assert record["restoration"] == "restore-pending"
    else:
        assert record["phase"] == ("ready-before" if operation == "apply" else "applied-after")
    assert record["execution_status"] == "not-run"
    assert record["verified_fix"] is False


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
def test_clean_precommit_cancellation_preserves_ready_state_and_false_commit_metadata(
    workspace, exception_type
):
    before = workspace.read_source()
    interruption = exception_type("cancel at the decision guard")

    def cancel():
        raise interruption

    with pytest.raises(exception_type) as caught:
        workspace.apply_source(before, guard=cancel)
    assert caught.value is interruption
    assert interruption.workspace_commit_attempted is False
    assert interruption.workspace_commit_uncertain is False
    assert interruption.workspace_committed is False
    assert not getattr(interruption, "workspace_cleanup_failed", False)
    assert workspace.state == "ready-before"
    assert workspace.read_source() == before
    assert not list(workspace.path.glob(".stage-*"))


@pytest.mark.parametrize("nested", ["apply", "restore"])
def test_reentrant_guard_operation_is_refused_without_a_source_replacement(
    workspace, monkeypatch, nested
):
    before = workspace.read_source()
    replace = os.replace
    source_replacements = []

    def observe_replace(src, dst, **kwargs):
        if os.fspath(dst) == "app.py":
            source_replacements.append(dst)
        return replace(src, dst, **kwargs)

    def recurse():
        nested_operation = workspace.apply_source if nested == "apply" else workspace.restore_source
        nested_operation(before, guard=lambda: pytest.fail("No nested guard invocation"))

    monkeypatch.setattr(os, "replace", observe_replace)
    with pytest.raises(io.WorkspaceError):
        workspace.apply_source(before, guard=recurse)
    assert source_replacements == []
    assert workspace.state == "ready-before"
    assert workspace.read_source() == before
    assert not list(workspace.path.glob(".stage-*"))
    # Rejection must release only the outer operation's busy guard.
    after = workspace.apply_source(before, guard=lambda: None)
    assert after.data != before.data
    assert len(source_replacements) == 1


@pytest.mark.parametrize("operation", ["apply", "restore"])
@pytest.mark.parametrize("nested", ["apply", "restore"])
def test_swallowed_reentrant_refusal_allows_only_the_outer_exact_replacement(
    workspace, monkeypatch, operation, nested
):
    before = workspace.read_source()
    if operation == "restore":
        current = workspace.apply_source(before, guard=lambda: None)
        transition = workspace.restore_source
        expected = before.data
    else:
        current = before
        transition = workspace.apply_source
        expected = (workspace.path / "after.txt").read_bytes()
    replace = os.replace
    source_replacements = []
    rejections = []

    def observe_replace(src, dst, **kwargs):
        if os.fspath(dst) == "app.py":
            source_replacements.append(dst)
        return replace(src, dst, **kwargs)

    def swallow_nested_refusals():
        nested_operation = workspace.apply_source if nested == "apply" else workspace.restore_source
        for _ in range(2):
            with pytest.raises(io.WorkspaceError):
                nested_operation(current, guard=lambda: pytest.fail("No nested guard invocation"))
            rejections.append(True)

    monkeypatch.setattr(os, "replace", observe_replace)
    result = transition(current, guard=swallow_nested_refusals)
    assert result.data == expected
    assert len(rejections) == 2
    assert len(source_replacements) == 1
    assert workspace.state == ("applied-after" if operation == "apply" else "restored-before")
    assert workspace.read_source() == result
    assert not list(workspace.path.glob(".stage-*"))


def test_ordinary_guard_refusal_releases_busy_flag_without_consuming_operation(workspace):
    before = workspace.read_source()

    def refuse():
        raise io.WorkspaceError("ordinary decision refusal")

    for _ in range(2):
        with pytest.raises(io.WorkspaceError, match="ordinary decision refusal"):
            workspace.apply_source(before, guard=refuse)
        assert workspace.state == "ready-before"
        assert workspace.read_source() == before
    after = workspace.apply_source(before, guard=lambda: None)
    assert workspace.state == "applied-after"
    restored = workspace.restore_source(after, guard=lambda: None)
    assert restored.data == before.data
    assert workspace.state == "restored-before"
