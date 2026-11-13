"""Owned inert-file refusal tests; no application, test or engine is executed."""

from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

import pytest

from authzest.runner import _generated_repair_staging as staging
from authzest.runner._generated_repair_workspace import GeneratedRepairWorkspace
from test_generated_repair_runtime_profile import profile
from test_generated_repair_staging import restore_stage_permissions  # noqa: F401
from test_generated_repair_workspace import _preview
from test_generated_repair_workspace_failures import keep_candidate_text_inert  # noqa: F401

pytestmark = pytest.mark.skipif(not staging.supported(), reason="POSIX held-FD input staging")


@pytest.fixture
def copied(tmp_path):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    yield copy
    copy.close()


@pytest.fixture
def staged(copied):
    stage = staging.GeneratedRepairInputStage(copied, "before", "T")
    yield stage
    if stage._closure_uncertain:
        with pytest.raises(staging.StageError):
            stage.close()
    else:
        stage.close()
    assert all(fd == -1 for fd in stage._fds.values())


def _replace(path, content):
    path.chmod(0o644)
    path.write_bytes(content)
    path.chmod(0o444)


@pytest.mark.parametrize("role", [None, True, "", "B", "t", "C"])
def test_unsupported_roles_have_no_stage_allocation(copied, role):
    before = set(copied.path.parent.iterdir())
    with pytest.raises(staging.StageError):
        staging.GeneratedRepairInputStage(copied, "before", role)
    assert set(copied.path.parent.iterdir()) == before


@pytest.mark.parametrize("candidate", [None, True, "", "after", "restored-before"])
def test_unavailable_phase_has_no_stage_allocation(copied, candidate):
    before = set(copied.path.parent.iterdir())
    with pytest.raises(staging.StageError):
        staging.GeneratedRepairInputStage(copied, candidate, "T")
    assert set(copied.path.parent.iterdir()) == before


@pytest.mark.parametrize("closed", [False, True])
def test_imported_checkpoint_or_closed_copy_cannot_create_live_stage(copied, closed):
    value = {"source": copied.read_source()} if not closed else copied
    if closed:
        copied.close()
    before = set(copied.path.parent.iterdir())
    with pytest.raises(staging.StageError):
        staging.GeneratedRepairInputStage(value, "before", "A")
    assert set(copied.path.parent.iterdir()) == before


@pytest.mark.parametrize("exception", [ValueError, KeyboardInterrupt, SystemExit])
def test_final_guard_refusal_does_not_allocate(copied, exception):
    before = set(copied.path.parent.iterdir())

    def guard():
        raise exception("inert-guard")

    with pytest.raises((staging.StageError, KeyboardInterrupt, SystemExit)) as caught:
        staging.GeneratedRepairInputStage(copied, "before", "T", _before_create=guard)
    failure = getattr(caught.value, "stage_initialization", caught.value)
    assert failure.allocation_attempted is False
    assert failure.created_path is None and failure.creation_confirmed is False
    assert failure.descriptor_cleanup_confirmed is True
    assert set(copied.path.parent.iterdir()) == before


@pytest.mark.parametrize("async_function", [False, True])
def test_async_guard_is_not_awaited_and_does_not_allocate(copied, async_function):
    async def pending():
        pytest.fail("Async allocation hooks must not run")

    coroutine = None if async_function else pending()
    guard = pending if async_function else lambda: coroutine
    before = set(copied.path.parent.iterdir())
    with pytest.raises(staging.StageError):
        staging.GeneratedRepairInputStage(copied, "before", "T", _before_create=guard)
    assert set(copied.path.parent.iterdir()) == before
    if coroutine is not None:
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED


@pytest.mark.parametrize("mutation", ["edit", "apply", "close"])
def test_checkpoint_is_rechecked_after_guard_before_allocation(copied, mutation):
    before = set(copied.path.parent.iterdir())

    def guard():
        if mutation == "edit":
            (copied.path / "app.py").write_bytes(b"# owned inert edit\n")
        elif mutation == "apply":
            copied.apply_source(copied.read_source(), guard=lambda: None)
        else:
            copied.close()

    with pytest.raises(staging.StageInitializationError) as caught:
        staging.GeneratedRepairInputStage(copied, "before", "T", _before_create=guard)
    assert caught.value.allocation_attempted is False
    assert caught.value.created_path is None
    assert set(copied.path.parent.iterdir()) == before


@pytest.mark.parametrize("operation", ["snapshot", "assert_current", "prepare_create"])
@pytest.mark.parametrize("original", ["app.py", "tests/test_generated_ownership.py", "record.json"])
def test_changed_original_checkpoint_invalidates_all_stage_exports(
    staged, copied, operation, original
):
    (copied.path / original).write_bytes(b"# changed inert original\n")
    with pytest.raises(staging.StageError):
        if operation == "prepare_create":
            staged.prepare_create(profile(), "a" * 32, "b" * 32)
        else:
            getattr(staged, operation)()
    assert staged.state == "state-unconfirmed"


def test_app_only_stage_still_pins_original_test(copied):
    stage = staging.GeneratedRepairInputStage(copied, "before", "A")
    try:
        assert not (stage.input_path / "tests").exists()
        (copied.path / "tests/test_generated_ownership.py").write_bytes(b"# changed\n")
        with pytest.raises(staging.StageError):
            stage.assert_current()
        assert stage.state == "state-unconfirmed"
    finally:
        stage.close()


@pytest.mark.parametrize("transition", ["apply", "apply-restore"])
def test_managed_source_transition_invalidates_even_when_restored_bytes_match(
    staged, copied, transition
):
    original = copied.read_source()
    applied = copied.apply_source(original, guard=lambda: None)
    if transition == "apply-restore":
        assert copied.restore_source(applied, guard=lambda: None).data == original.data
    with pytest.raises(staging.StageError):
        staged.assert_current()
    assert staged.state == "state-unconfirmed"


@pytest.mark.parametrize("name", ["app.py", "tests/test_generated_ownership.py"])
def test_staged_edits_are_latched_and_original_copy_is_unchanged(staged, copied, name):
    before = (copied.read_source(), copied.read_test(), copied.read_record())
    path = staged.input_path / name
    content = path.read_bytes()
    _replace(path, b"# changed inert staged text\n")
    with pytest.raises(staging.StageError):
        staged.snapshot()
    _replace(path, content)
    with pytest.raises(staging.StageError):
        staged.assert_current()
    assert staged.state == "state-unconfirmed"
    assert (copied.read_source(), copied.read_test(), copied.read_record()) == before


@pytest.mark.parametrize("kind", ["root", "input", "tests", "app", "record"])
def test_permissions_are_part_of_stage_identity(staged, kind):
    paths = {
        "root": staged.path,
        "input": staged.input_path,
        "tests": staged.input_path / "tests",
        "app": staged.input_path / "app.py",
        "record": staged.path / "record.json",
    }
    paths[kind].chmod(0o755 if kind in {"root", "input", "tests"} else 0o644)
    with pytest.raises(staging.StageError):
        staged.assert_current()
    assert staged.state == "state-unconfirmed"


@pytest.mark.parametrize("kind", ["same-bytes", "symlink", "fifo", "directory", "missing"])
def test_replaced_stage_file_is_not_accepted_by_bytes_alone(staged, kind):
    path = staged.input_path / "app.py"
    original = path.read_bytes()
    old_inode = path.stat().st_ino
    staged.input_path.chmod(0o755)
    if kind == "same-bytes":
        replacement = staged.path / "owned-inert-replacement.tmp"
        replacement.write_bytes(original)
        replacement.chmod(0o444)
        os.replace(replacement, path)
        assert path.stat().st_ino != old_inode
        assert staged._read("app.py").identity != staged._tracked["app.py"].identity
    else:
        path.unlink()
        if kind == "symlink":
            path.symlink_to(staged.path / "record.json")
        elif kind == "fifo":
            os.mkfifo(path, 0o444)
        elif kind == "directory":
            path.mkdir()
    staged.input_path.chmod(0o555)
    if kind != "same-bytes":
        with pytest.raises((OSError, staging.StageError)):
            staged._read("app.py")
    with pytest.raises(staging.StageError):
        staged.assert_current()
    assert staged.state == "state-unconfirmed"


def test_hardlink_count_is_checked_without_changing_original_copy(staged):
    peer = staged.path.parent / "inert-stage-hardlink-peer"
    os.link(staged.input_path / "app.py", peer)
    assert peer.stat().st_nlink == 2
    with pytest.raises(staging.StageError):
        staged.assert_current()
    assert peer.exists() and staged.state == "state-unconfirmed"


def test_extra_input_file_is_not_hidden_from_bounded_membership(staged):
    staged.input_path.chmod(0o755)
    extra = staged.input_path / "extra.py"
    extra.write_bytes(b"# retained inert extra file\n")
    staged.input_path.chmod(0o555)
    with pytest.raises(staging.StageError):
        staged._membership("input")
    with pytest.raises(staging.StageError):
        staged.assert_current()
    assert extra.exists()


def test_membership_stops_after_one_extra_entry_and_closes_iterator(staged, monkeypatch):
    original = os.scandir
    observed = {"next": 0, "closed": 0}

    class Endless:
        def __iter__(self):
            return self

        def __next__(self):
            observed["next"] += 1
            return SimpleNamespace(name={1: "app.py", 2: "tests"}.get(observed["next"], "extra"))

        def close(self):
            observed["closed"] += 1

    def scan(fd):
        return Endless() if fd == staged._fds["input"] else original(fd)

    with monkeypatch.context() as change:
        change.setattr(os, "scandir", scan)
        with pytest.raises(staging.StageError):
            staged.assert_current()
    assert observed == {"next": 3, "closed": 1}
    assert staged.state == "state-unconfirmed"


def test_read_budget_rejects_oversized_chunk_before_appending(staged, monkeypatch):
    original = os.read
    inode = (staged.input_path / "app.py").stat().st_ino

    def read(fd, maximum):
        return b"x" * (maximum + 1) if os.fstat(fd).st_ino == inode else original(fd, maximum)

    with monkeypatch.context() as change:
        change.setattr(os, "read", read)
        with pytest.raises(staging.StageError):
            staged._read("app.py")


@pytest.mark.parametrize("mode", ["zero", "bool", "too-many"])
def test_incomplete_write_retains_confirmed_directory_and_partial_file(copied, monkeypatch, mode):
    def write(fd, pending):
        return {"zero": 0, "bool": True, "too-many": len(pending) + 1}[mode]

    with monkeypatch.context() as change:
        change.setattr(os, "write", write)
        with pytest.raises(staging.StageInitializationError) as caught:
            staging.GeneratedRepairInputStage(copied, "before", "T")
    failure = caught.value
    assert failure.created_path is not None and failure.created_path.is_dir()
    assert failure.allocation_attempted and failure.creation_confirmed
    assert failure.file_states["app.py"] == "created-unconfirmed"
    assert (failure.created_path / "input/app.py").exists()
    assert failure.descriptor_cleanup_confirmed is True
    assert copied.state == "ready-before"


@pytest.mark.parametrize("exception", [OSError, KeyboardInterrupt])
def test_unreturned_directory_allocation_is_unknown_not_zero_writes(copied, monkeypatch, exception):
    original = os.mkdir

    def mkdir(name, *args, **kwargs):
        if str(name).startswith("authzest-generated-inputs-"):
            original(name, *args, **kwargs)
            raise exception("after-owned-mkdir")
        return original(name, *args, **kwargs)

    with monkeypatch.context() as change:
        change.setattr(os, "mkdir", mkdir)
        with pytest.raises((staging.StageInitializationError, KeyboardInterrupt)) as caught:
            staging.GeneratedRepairInputStage(copied, "before", "T")
    failure = getattr(caught.value, "stage_initialization", caught.value)
    assert failure.created_path is None and failure.planned_path.is_dir()
    assert failure.allocation_attempted and failure.ownership_uncertain
    assert failure.creation_confirmed is False
    assert list(failure.planned_path.iterdir()) == []


def test_collision_target_is_not_opened_retried_or_deleted(copied, monkeypatch):
    collision = copied.path.parent / ("authzest-generated-inputs-" + "d" * 32)
    collision.mkdir()
    marker = collision / "existing.txt"
    marker.write_bytes(b"owned preexisting collision target")
    with monkeypatch.context() as change:
        change.setattr(staging.uuid, "uuid4", lambda: SimpleNamespace(hex="d" * 32))
        with pytest.raises(staging.StageInitializationError) as caught:
            staging.GeneratedRepairInputStage(copied, "before", "T")
    assert caught.value.created_path is None
    assert caught.value.creation_confirmed is False and caught.value.ownership_uncertain is False
    assert marker.read_bytes() == b"owned preexisting collision target"
    assert sorted(path.name for path in collision.iterdir()) == ["existing.txt"]


def test_file_close_failure_is_not_overwritten_by_successful_directory_cleanup(copied, monkeypatch):
    original = os.close
    original_inodes = {state.identity[1] for state in copied._tracked.values()}
    failed = []

    def close(fd):
        info = os.fstat(fd)
        original(fd)
        if (
            not failed
            and info.st_mode & 0o170000 == 0o100000
            and info.st_ino not in original_inodes
        ):
            failed.append(True)
            raise OSError("after-file-close")

    # Restrict failure to a stage-owned file, after original workspace reads.
    original_read = staging.GeneratedRepairInputStage._create_file

    def create(self, *args):
        with monkeypatch.context() as fault:
            fault.setattr(os, "close", close)
            return original_read(self, *args)

    with monkeypatch.context() as change:
        change.setattr(staging.GeneratedRepairInputStage, "_create_file", create)
        with pytest.raises(staging.StageInitializationError) as caught:
            staging.GeneratedRepairInputStage(copied, "before", "T")
    assert failed and caught.value.created_path.is_dir()
    assert caught.value.descriptor_cleanup_confirmed is False


def test_staged_plan_rechecks_files_after_pure_builder(staged, monkeypatch):
    original = staging.build_container_create_plan

    def builder(*args, **kwargs):
        result = original(*args, **kwargs)
        _replace(staged.input_path / "app.py", b"# inert change during plan\n")
        return result

    with monkeypatch.context() as change:
        change.setattr(staging, "build_container_create_plan", builder)
        with pytest.raises(staging.StageError):
            staged.prepare_create(profile(), "a" * 32, "b" * 32)
    assert staged.state == "state-unconfirmed"


def test_reentrant_snapshot_cannot_run_during_create_planning(staged, monkeypatch):
    def builder(*args, **kwargs):
        staged.snapshot()

    with monkeypatch.context() as change:
        change.setattr(staging, "build_container_create_plan", builder)
        with pytest.raises(staging.StageError):
            staged.prepare_create(profile(), "a" * 32, "b" * 32)
    assert staged.state == "state-unconfirmed"


def test_close_retains_bytes_and_refuses_fresh_evidence(staged):
    before = (staged.input_path / "app.py").read_bytes()
    path = staged.path
    staged.close()
    assert staged.state == "closed"
    assert (path / "input/app.py").read_bytes() == before
    assert (path / "record.json").is_file()
    with pytest.raises(staging.StageError):
        staged.snapshot()


def test_bookkeeping_failure_after_file_open_closes_the_acquired_descriptor(copied, monkeypatch):
    original_create = staging.GeneratedRepairInputStage._create_file
    original_open = os.open
    opened = []

    class RefusingMembers(set):
        def add(self, value):
            raise MemoryError("owned bookkeeping fault after file acquisition")

    def create(self, name, content):
        kind, _ = self._location(name)
        self._members[kind] = RefusingMembers(self._members[kind])

        def acquire(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            if args[1] & os.O_CREAT:
                opened.append(fd)
            return fd

        with monkeypatch.context() as fault:
            fault.setattr(os, "open", acquire)
            return original_create(self, name, content)

    with monkeypatch.context() as change:
        change.setattr(staging.GeneratedRepairInputStage, "_create_file", create)
        with pytest.raises(staging.StageInitializationError) as caught:
            staging.GeneratedRepairInputStage(copied, "before", "T")
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])
    assert caught.value.descriptor_cleanup_confirmed is True
    assert (caught.value.created_path / "input/app.py").is_file()


@pytest.mark.parametrize("exception", [OSError, KeyboardInterrupt])
def test_unreturned_file_acquisition_keeps_descriptor_disposition_unknown(
    copied, monkeypatch, exception
):
    original = os.open
    actual_supported = staging.supported()
    assert actual_supported
    acquired = []

    def acquire(*args, **kwargs):
        fd = original(*args, **kwargs)
        if args[1] & os.O_CREAT:
            acquired.append(fd)
            raise exception("owned acquisition interrupted before descriptor return")
        return fd

    try:
        with monkeypatch.context() as change:
            # Patching os.open changes support-set identity; preserve this host's observed support.
            change.setattr(staging, "supported", lambda: actual_supported)
            change.setattr(os, "open", acquire)
            with pytest.raises((staging.StageInitializationError, KeyboardInterrupt)) as caught:
                staging.GeneratedRepairInputStage(copied, "before", "T")
        failure = getattr(caught.value, "stage_initialization", caught.value)
        assert failure.created_path.is_dir()
        assert failure.descriptor_cleanup_confirmed is False
        assert failure.file_states["app.py"] == "creation-attempted"
        assert len(acquired) == 1 and os.fstat(acquired[0]).st_size == 0
    finally:
        # The test owns the deliberately hidden descriptor; the helper never received it.
        for fd in acquired:
            os.close(fd)


def test_iterator_close_failure_latches_unknown_resource_cleanup(staged, monkeypatch):
    original = os.scandir

    class CloseFailure:
        def __init__(self, iterator):
            self.iterator = iterator

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.iterator)

        def close(self):
            self.iterator.close()
            raise OSError("after owned iterator close")

    def scan(fd):
        value = original(fd)
        return CloseFailure(value) if fd == staged._fds["input"] else value

    with monkeypatch.context() as change:
        change.setattr(os, "scandir", scan)
        with pytest.raises(staging.StageError):
            staged.assert_current()
    assert staged.state == "state-unconfirmed" and staged._closure_uncertain
    with pytest.raises(staging.StageError):
        staged.close()
    assert staged._descriptor_cleanup_confirmed is False


def test_file_sync_failure_retains_partial_bytes_with_confirmed_fd_cleanup(copied, monkeypatch):
    original = os.fsync

    def sync(fd):
        if os.fstat(fd).st_mode & 0o170000 == 0o100000:
            raise OSError("owned file fsync failure")
        return original(fd)

    with monkeypatch.context() as change:
        change.setattr(os, "fsync", sync)
        with pytest.raises(staging.StageInitializationError) as caught:
            staging.GeneratedRepairInputStage(copied, "before", "T")
    failure = caught.value
    assert failure.file_states["app.py"] == "created-unconfirmed"
    assert failure.descriptor_cleanup_confirmed is True
    assert (failure.created_path / "input/app.py").read_bytes() == copied.read_source().data
