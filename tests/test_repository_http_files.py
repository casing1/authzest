"""Owned inert files only: never import/collect/execute the materialized Python."""

import builtins
import copy
import os
import pickle
import socket
import stat
import subprocess
from pathlib import Path

import pytest

from authzest.runner import _repository_http_files as module
from authzest.runner._repository_http_files import (
    RepositoryHttpFiles,
    RepositoryHttpFilesError,
    RepositoryHttpFilesInitializationError,
    RepositoryHttpFilesWriteError,
)

SOURCE = "project/app.py"
TEST = "project/tests/test_authzest_regression.py"
BEFORE = b'raise RuntimeError("inert before; must never execute")\n'
AFTER = b'raise RuntimeError("inert after; must never execute")\n'


def materials(source=SOURCE, before=BEFORE):
    return {
        source: before,
        "evidence/policy.txt": "소유자만 접근할 수 있습니다.\r\n".encode(),
        "evidence/source.before": before,
        "evidence/source.after": AFTER,
        "record.json": b'{"state":"before"}',
    }


@pytest.fixture(autouse=True)
def no_target_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network or process use is outside private byte-file tests")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "fastapi", "uvicorn", "httpx", "openai", "docker"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for owner, names in (
        (socket, ("socket", "create_connection")),
        (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
        (os, ("system", "fork", "execv", "execve", "posix_spawn")),
    ):
        for name in names:
            if hasattr(owner, name):
                monkeypatch.setattr(owner, name, forbidden)


@pytest.fixture
def parent(tmp_path):
    if not module.supported():
        pytest.skip("Live private files require POSIX source operations")
    path = tmp_path.resolve() / "private-parent"
    path.mkdir(mode=0o700)
    return path


@pytest.fixture
def workspace(parent):
    with RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=lambda: None) as result:
        yield result


def test_flat_source_unicode_policy_exact_bytes_permissions_and_detached_identifiers(workspace):
    workspace.verify()
    assert workspace.path.parent.name == "private-parent"
    assert workspace.path.name.startswith("authzest-repository-http-")
    for name, content in materials().items():
        assert workspace.read(name) == content
        assert (workspace.path / name).read_bytes() == content
        assert stat.S_IMODE((workspace.path / name).stat().st_mode) == 0o600
        assert (workspace.path / name).stat().st_nlink == 1
    for path in [workspace.path, *(p for p in workspace.path.rglob("*") if p.is_dir())]:
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    ids = workspace.identities
    assert len(ids[SOURCE]) == 9
    ids[SOURCE][0] = -1
    assert workspace.identities[SOURCE][0] != -1
    assert workspace.root_identity[1] == workspace.path.stat().st_ino
    assert not workspace.closed and not workspace.poisoned
    with pytest.raises(AttributeError):
        workspace.source_path = TEST
    with pytest.raises(AttributeError):
        workspace.path = Path("/unused")


def test_exact_source_apply_journal_update_restore_keep_immutable_evidence(workspace):
    baseline = workspace.identities
    workspace.replace("record.json", b'{"state":"apply-intent"}', guard=lambda: None)
    journal = workspace.identities["record.json"]
    assert journal[1] != baseline["record.json"][1]
    workspace.replace(SOURCE, AFTER, guard=lambda: None)
    after = workspace.identities[SOURCE]
    assert after[1] != baseline[SOURCE][1]
    assert workspace.read(SOURCE) == AFTER
    workspace.replace("record.json", b'{"state":"after"}', guard=lambda: None)
    workspace.replace(SOURCE, BEFORE, guard=lambda: None)
    assert workspace.read(SOURCE) == BEFORE
    assert workspace.read("record.json") == b'{"state":"after"}'
    for name, content in materials().items():
        if name not in {SOURCE, "record.json"}:
            assert workspace.read(name) == content
            assert workspace.identities[name] == baseline[name]


def test_empty_original_source_can_be_restored(parent):
    with RepositoryHttpFiles(
        materials(before=b""), SOURCE, _parent=parent, guard=lambda: None
    ) as ws:
        ws.replace(SOURCE, AFTER, guard=lambda: None)
        ws.replace(SOURCE, b"", guard=lambda: None)
        assert ws.read(SOURCE) == b""


def test_no_input_dictionary_alias_after_creation(parent):
    supplied = materials()
    with RepositoryHttpFiles(supplied, SOURCE, _parent=parent, guard=lambda: None) as workspace:
        supplied[SOURCE] = b"other"
        supplied["record.json"] = b"edited journal"
        supplied["project/unselected.py"] = b"unselected"
        assert workspace.read(SOURCE) == BEFORE
        assert workspace.read("record.json") == b'{"state":"before"}'
        assert set(workspace.identities) == set(materials())


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        "hardlink",
        "fifo",
        "rewrite",
        "replace",
        "mode",
        "extra",
        "missing",
        "directory",
        "journal",
    ],
)
def test_private_tampering_refuses_and_poison(workspace, kind):
    source = workspace.path / SOURCE
    if kind == "symlink":
        source.unlink()
        source.symlink_to(workspace.path / "evidence/source.before")
    elif kind == "hardlink":
        os.link(source, source.with_name("linked.py"))
    elif kind == "fifo":
        source.unlink()
        os.mkfifo(source, 0o600)
    elif kind == "rewrite":
        source.write_bytes(BEFORE)
    elif kind == "replace":
        replacement = source.with_name("swap.py")
        replacement.write_bytes(BEFORE)
        replacement.chmod(0o600)
        replacement.replace(source)
    elif kind == "mode":
        source.chmod(0o644)
    elif kind == "extra":
        (workspace.path / "unexpected").write_bytes(b"x")
    elif kind == "missing":
        (workspace.path / "evidence/source.after").unlink()
    elif kind == "directory":
        directory = source.parent
        directory.rename(directory.with_name("renamed"))
        directory.mkdir(mode=0o700)
    else:
        (workspace.path / "record.json").write_bytes(b'{"state":"forged"}')
    with pytest.raises(RepositoryHttpFilesError, match="unconfirmed"):
        workspace.verify()
    assert workspace.poisoned
    with pytest.raises(RepositoryHttpFilesError):
        workspace.replace(SOURCE, AFTER, guard=lambda: None)


def test_close_retains_all_files_and_releases_live_descriptors(workspace):
    fds = list(workspace._fds)
    path = workspace.path
    workspace.close()
    workspace.close()
    assert workspace.closed
    assert (path / SOURCE).read_bytes() == BEFORE
    for fd in fds:
        with pytest.raises(OSError):
            os.fstat(fd)
    for method in (
        workspace.verify,
        lambda: workspace.read(SOURCE),
        lambda: workspace.replace(SOURCE, AFTER, guard=lambda: None),
    ):
        with pytest.raises(RepositoryHttpFilesError):
            method()


def test_process_binding_copy_pickle_and_forged_empty_instance(workspace, monkeypatch):
    for operation in (
        lambda: copy.copy(workspace),
        lambda: copy.deepcopy(workspace),
        lambda: pickle.dumps(workspace),
    ):
        with pytest.raises(TypeError):
            operation()
    original = os.getpid()
    monkeypatch.setattr(os, "getpid", lambda: original + 1)
    with pytest.raises(RepositoryHttpFilesError, match="process"):
        workspace.verify()
    with pytest.raises(RepositoryHttpFilesError):
        object.__new__(RepositoryHttpFiles).verify()


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "/outside.py",
        "project/.hidden.py",
        "project/a\\b.py",
        "project/a\n.py",
        "elsewhere/a.py",
        "evidence/extra.py",
        "project/" + "/".join(["a"] * 17) + ".py",
        "project/" + "x" * 520 + ".py",
    ],
)
def test_invalid_paths_refused_before_allocating(parent, path):
    data = materials()
    data[path] = b""
    with pytest.raises(RepositoryHttpFilesError):
        RepositoryHttpFiles(data, SOURCE, _parent=parent, guard=lambda: None)
    assert not list(parent.iterdir())


@pytest.mark.parametrize(
    "left,right",
    [
        ("project/pkg.py", "project/pkg.py/child.py"),
        ("project/NAME.py", "project/name.py"),
        ("project/café.py", "project/cafe\u0301.py"),
        ("project/ΐ.py", "project/Ϊ́.py"),
    ],
)
def test_prefix_and_canonical_caseless_aliases_refused(parent, left, right):
    data = materials()
    data[left] = b""
    data[right] = b""
    with pytest.raises(RepositoryHttpFilesError):
        RepositoryHttpFiles(data, SOURCE, _parent=parent, guard=lambda: None)
    assert not list(parent.iterdir())


@pytest.mark.parametrize(
    "name,value",
    [
        (SOURCE, b"x" * 16385),
        ("record.json", b"x" * 65537),
        ("evidence/policy.txt", b"x" * 8193),
        ("evidence/source.after", b"\xff"),
        ("evidence/source.after", "not bytes"),
        ("evidence/source.after", b"\0"),
    ],
    ids=["source-limit", "journal-limit", "policy-limit", "invalid-utf8", "not-bytes", "nul"],
)
def test_invalid_bytes_and_individual_budgets_refused(parent, name, value):
    data = materials()
    data[name] = value
    with pytest.raises(RepositoryHttpFilesError):
        RepositoryHttpFiles(data, SOURCE, _parent=parent, guard=lambda: None)
    assert not list(parent.iterdir())


@pytest.mark.parametrize(
    "path,value",
    [
        (TEST, b"tampered"),
        ("evidence/source.before", b"tampered"),
        (SOURCE, b"x" * 16385),
        ("record.json", b"x" * 65537),
        (SOURCE, b"\xff"),
    ],
    ids=["generated-test", "immutable-evidence", "source-limit", "journal-limit", "invalid-utf8"],
)
def test_nonmutable_or_invalid_replacement_does_not_poison_valid_workspace(workspace, path, value):
    with pytest.raises(RepositoryHttpFilesError):
        workspace.replace(path, value, guard=lambda: None)
    assert not workspace.poisoned
    assert workspace.read(SOURCE) == BEFORE


def test_unsafe_parent_and_symlink_parent_refused(tmp_path, parent):
    unsafe = tmp_path.resolve() / "public"
    unsafe.mkdir(mode=0o755)
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(parent, target_is_directory=True)
    for path in (unsafe, alias, Path("relative"), parent / ".."):
        with pytest.raises(RepositoryHttpFilesInitializationError) as error:
            RepositoryHttpFiles(materials(), SOURCE, _parent=path, guard=lambda: None)
        assert error.value.created_path is None
        assert error.value.descriptor_cleanup_confirmed
    assert not list(parent.iterdir())


def test_copy_guard_expiry_creates_no_directory(parent):
    def expired():
        raise TimeoutError("owned fake expiry")

    with pytest.raises(RepositoryHttpFilesInitializationError) as error:
        RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=expired)
    assert error.value.created_path is None
    assert error.value.stage == "check-guard"
    assert not list(parent.iterdir())


@pytest.mark.parametrize("phase", ["write", "fsync", "readback", "directory"])
def test_initialization_failures_retain_partial_tree_and_close_fds(parent, monkeypatch, phase):
    original = RepositoryHttpFiles._write_new
    seen = []
    if phase == "write":
        monkeypatch.setattr(os, "write", lambda *args: 0)
    elif phase == "fsync":
        monkeypatch.setattr(
            os, "fsync", lambda *args: (_ for _ in ()).throw(OSError("owned failure"))
        )
    elif phase == "readback":
        monkeypatch.setattr(
            RepositoryHttpFiles,
            "_read_current",
            lambda *args: (_ for _ in ()).throw(OSError("owned failure")),
        )
    else:
        mkdir = os.mkdir

        def broken(name, *args, **kwargs):
            if name == "evidence":
                raise OSError("owned failure")
            return mkdir(name, *args, **kwargs)

        monkeypatch.setattr(os, "mkdir", broken)

    def pinned(self, *args):
        seen.extend(self._fds)
        return original(self, *args)

    monkeypatch.setattr(RepositoryHttpFiles, "_write_new", pinned)
    with pytest.raises(RepositoryHttpFilesInitializationError) as error:
        RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=lambda: None)
    assert error.value.created_path in list(parent.iterdir())
    assert error.value.created_path.is_dir()
    assert error.value.descriptor_cleanup_confirmed
    for fd in seen:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize(
    "phase",
    [
        "stage-write",
        "stage-readback",
        "guard",
        "guard-value",
        "rename-before",
        "rename-after",
        "sync",
        "replacement-readback",
    ],
)
def test_replacement_failures_report_actual_boundary_and_retain_evidence(
    workspace, monkeypatch, phase
):
    replace, fsync, read = os.replace, os.fsync, RepositoryHttpFiles._read_current

    def guard():
        return None

    if phase == "stage-write":
        monkeypatch.setattr(os, "write", lambda *args: 0)
    elif phase == "stage-readback":

        def fail_stage(self, name, maximum):
            if ".authzest-" in name:
                raise OSError("owned failure")
            return read(self, name, maximum)

        monkeypatch.setattr(RepositoryHttpFiles, "_read_current", fail_stage)
    elif phase == "guard":

        def expired():
            raise TimeoutError("owned fake expiry")

        guard = expired
    elif phase == "guard-value":

        def guard():
            return False
    elif phase.startswith("rename"):

        def broken(*args, **kwargs):
            if phase == "rename-after":
                replace(*args, **kwargs)
            raise OSError("owned failure")

        monkeypatch.setattr(os, "replace", broken)
    elif phase == "sync":
        committed = []

        def mark(*args, **kwargs):
            result = replace(*args, **kwargs)
            committed.append(True)
            return result

        def fail_sync(fd):
            if committed:
                raise OSError("owned failure")
            return fsync(fd)

        monkeypatch.setattr(os, "replace", mark)
        monkeypatch.setattr(os, "fsync", fail_sync)
    else:
        committed = []

        def mark(*args, **kwargs):
            result = replace(*args, **kwargs)
            committed.append(True)
            return result

        def fail_read(self, name, maximum):
            if committed and name == SOURCE:
                raise OSError("owned failure")
            return read(self, name, maximum)

        monkeypatch.setattr(os, "replace", mark)
        monkeypatch.setattr(RepositoryHttpFiles, "_read_current", fail_read)
    with pytest.raises(RepositoryHttpFilesWriteError) as error:
        workspace.replace(SOURCE, AFTER, guard=guard)
    failure = error.value
    assert failure.operation == SOURCE and failure.state_unconfirmed
    assert failure.commit_attempted == (
        phase in {"rename-before", "rename-after", "sync", "replacement-readback"}
    )
    assert failure.committed == (phase in {"sync", "replacement-readback"})
    assert (workspace.path / SOURCE).read_bytes() == (
        AFTER if phase in {"rename-after", "sync", "replacement-readback"} else BEFORE
    )
    if not failure.commit_attempted or phase == "rename-before":
        assert failure.staging_path.exists()
    assert workspace.poisoned
    with pytest.raises(RepositoryHttpFilesError):
        workspace.replace(SOURCE, BEFORE, guard=lambda: None)


def test_final_guard_immediately_precedes_replace_and_reentrant_write_refused(
    workspace, monkeypatch
):
    events = []
    for name in ("open", "stat", "fstat", "read", "write", "fsync", "scandir"):
        original = getattr(os, name)

        def tracked(*args, _original=original, _name=name, **kwargs):
            events.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(os, name, tracked)
    original_replace = os.replace

    def replace(*args, **kwargs):
        assert events[-1] == "guard"
        return original_replace(*args, **kwargs)

    monkeypatch.setattr(os, "replace", replace)

    def guard():
        with pytest.raises(RepositoryHttpFilesError, match="Reentrant"):
            workspace.replace(SOURCE, AFTER, guard=lambda: None)
        with pytest.raises(RepositoryHttpFilesError, match="active"):
            workspace.close()
        events.append("guard")

    workspace.replace(SOURCE, AFTER, guard=guard)
    assert workspace.read(SOURCE) == AFTER


def test_async_guards_are_not_executed(workspace):
    async def guard():
        raise AssertionError("must not run")

    with pytest.raises(RepositoryHttpFilesWriteError) as error:
        workspace.replace(SOURCE, AFTER, guard=guard)
    assert error.value.stage == "check-guard"
    assert not error.value.commit_attempted


def test_unsupported_platform_refuses_before_allocating(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "supported", lambda: False)
    with pytest.raises(RepositoryHttpFilesError, match="POSIX"):
        RepositoryHttpFiles(materials(), SOURCE, _parent=tmp_path, guard=lambda: None)
    assert not list(tmp_path.iterdir())


def test_exact_http_source_policy_evidence_and_journal_bounds(parent):
    data = materials(before=b"x" * 16_384)
    data.update(
        {
            "evidence/policy.txt": b"p" * 8192,
            "evidence/source.after": b"y" * 16_384,
            "record.json": b"{}" + b" " * 65_534,
        }
    )
    assert sum(len(v) for k, v in data.items() if k != "record.json") == 57_344
    with RepositoryHttpFiles(data, SOURCE, _parent=parent, guard=lambda: None) as ws:
        assert set(ws.identities) == set(data)
        assert len(ws.read("record.json")) == 65_536
        assert ws.read(SOURCE) == b"x" * 16_384
        ws.replace(SOURCE, b"z" * 16_384, guard=lambda: None)
        ws.replace("record.json", data["record.json"], guard=lambda: None)


@pytest.mark.parametrize("kind", ["missing", "before", "test", "context", "source-target"])
def test_closed_http_material_shape_refused_before_parent_open(parent, kind):
    data = materials()
    source = SOURCE
    if kind == "missing":
        del data["record.json"]
    elif kind == "before":
        data["evidence/source.before"] += b"edited"
    elif kind == "test":
        data[TEST] = b"inert generated test forbidden"
    elif kind == "context":
        data["project/context.py"] = b"inert context forbidden"
    else:
        source = TEST
    with pytest.raises(RepositoryHttpFilesError):
        RepositoryHttpFiles(data, source, _parent=parent, guard=lambda: None)
    assert not list(parent.iterdir())


def test_default_parent_is_canonicalized_only_for_trusted_temp_default(parent, monkeypatch):
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(parent))
    with RepositoryHttpFiles(materials(), SOURCE, guard=lambda: None) as ws:
        assert ws.path.parent == parent


def test_original_parent_sibling_changes_do_not_change_private_evidence(workspace):
    (workspace.path.parent / "unrelated").write_bytes(b"owned inert sibling")
    workspace.verify()
    assert workspace.read(SOURCE) == BEFORE


@pytest.mark.parametrize("kind", ["root-replace", "parent-mode"])
def test_root_or_parent_identity_change_refused(workspace, kind):
    if kind == "root-replace":
        workspace.path.rename(workspace.path.with_name("renamed-owned-copy"))
        workspace.path.mkdir(mode=0o700)
    else:
        workspace.path.parent.chmod(0o750)
    with pytest.raises(RepositoryHttpFilesError):
        workspace.verify()
    assert workspace.poisoned


@pytest.mark.parametrize("actually_closed", [False, True])
def test_file_close_uncertainty_is_not_reported_as_confirmed_cleanup(
    parent, monkeypatch, actually_closed
):
    original = os.close
    failed = []

    def fail_once(fd):
        if not failed and stat.S_ISREG(os.fstat(fd).st_mode):
            failed.append(fd)
            if actually_closed:
                original(fd)
            raise OSError("owned uncertain close")
        original(fd)

    monkeypatch.setattr(os, "close", fail_once)
    try:
        with pytest.raises(RepositoryHttpFilesInitializationError) as error:
            RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=lambda: None)
        assert error.value.created_path.is_dir()
        assert error.value.descriptor_cleanup_confirmed is False
    finally:
        if failed and not actually_closed:
            original(failed[0])


def test_owned_mock_interrupt_retains_failure_flags_without_swallowing(workspace, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt) as error:
        workspace.replace(SOURCE, AFTER, guard=lambda: None)
    failure = error.value.repository_http_files_write
    assert failure.commit_attempted and not failure.committed
    assert failure.staging_path.is_file()
    assert workspace.poisoned


@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
def test_close_attempts_remaining_descriptors_before_propagating_interrupt(
    workspace, monkeypatch, signal
):
    original = os.close
    fds = list(workspace._fds)
    calls = []

    def interrupted(fd):
        original(fd)
        calls.append(fd)
        if len(calls) == 1:
            raise signal

    monkeypatch.setattr(os, "close", interrupted)
    with pytest.raises(signal) as error:
        workspace.close()
    assert error.value.repository_http_files_cleanup_confirmed is False
    assert set(calls) == set(fds)
    assert workspace.closed and workspace.poisoned and not workspace._fds
    for fd in fds:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_cleanup_interrupt_during_initialization_is_not_swallowed(parent, monkeypatch):
    original = os.close
    calls = []

    def fail_guard():
        raise ValueError("owned ordinary initial failure")

    def interrupted(fd):
        original(fd)
        calls.append(fd)
        if len(calls) == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(os, "close", interrupted)
    with pytest.raises(KeyboardInterrupt) as error:
        RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=fail_guard)
    assert error.value.repository_http_files_initialization.created_path is None
    assert not error.value.repository_http_files_initialization.descriptor_cleanup_confirmed
    assert not list(parent.iterdir())
    for fd in calls:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize(
    "source",
    [
        "project/pkg/app.py",
        "project/앱.py",
        "project/class.py",
        "project/__init__.py",
        "project/1app.py",
        "project/a-b.py",
        "project/app.PY",
        "Project/app.py",
        "project/" + "x" * 129 + ".py",
        None,
        1,
    ],
    ids=[
        "nested",
        "unicode",
        "keyword",
        "package-initializer",
        "leading-digit",
        "punctuation",
        "suffix-case",
        "root-case",
        "identifier-limit",
        "none",
        "integer",
    ],
)
def test_flat_http_source_contract_refuses_before_guard_or_parent_open(parent, monkeypatch, source):
    calls = []

    def forbidden(*args):
        calls.append(True)
        raise AssertionError("Invalid HTTP material must not open a parent")

    monkeypatch.setattr(RepositoryHttpFiles, "_open_parent", forbidden)
    with pytest.raises(RepositoryHttpFilesError):
        RepositoryHttpFiles(materials(source=source), source, _parent=parent, guard=forbidden)
    assert calls == []
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("filename", ["app.py", "_application0.py", "a" * 128 + ".py"])
def test_supported_flat_http_source_spellings_remain_exact(parent, filename):
    source = "project/" + filename
    with RepositoryHttpFiles(materials(source), source, _parent=parent, guard=lambda: None) as ws:
        assert ws.source_path == source
        assert ws.read(source) == BEFORE
        assert set(ws.identities) == set(materials(source))


def test_http_and_older_material_layouts_do_not_adopt_each_other(parent):
    from authzest.runner._repository_files import RepositoryFiles, RepositoryFilesError

    old = materials()
    old.update({TEST: b"inert test", "evidence/test.txt": b"inert test"})
    with pytest.raises(RepositoryHttpFilesError):
        RepositoryHttpFiles(old, SOURCE, _parent=parent, guard=lambda: None)
    with pytest.raises(RepositoryFilesError):
        RepositoryFiles(materials(), SOURCE, _parent=parent, guard=lambda: None)
    assert not list(parent.iterdir())


def test_subclass_cannot_adopt_http_constructor(parent):
    class Child(RepositoryHttpFiles):
        pass

    with pytest.raises(RepositoryHttpFilesError):
        Child(materials(), SOURCE, _parent=parent, guard=lambda: None)
    assert not list(parent.iterdir())


def test_root_name_collision_retains_first_tree_and_never_adopts_it(parent, monkeypatch):
    monkeypatch.setattr(module.secrets, "token_hex", lambda _: "ab" * 16)
    with RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=lambda: None) as first:
        original = first.identities
        with pytest.raises(RepositoryHttpFilesInitializationError) as error:
            RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=lambda: None)
        assert error.value.created_path is None
        assert error.value.descriptor_cleanup_confirmed
        assert first.identities == original
        assert first.read(SOURCE) == BEFORE
        assert list(parent.iterdir()) == [first.path]


def test_async_constructor_guard_refused_before_invocation_or_allocation(parent):
    called = []

    async def guard():
        called.append(True)

    with pytest.raises(RepositoryHttpFilesInitializationError) as error:
        RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=guard)
    assert not called and list(parent.iterdir()) == []
    assert error.value.created_path is None
    assert error.value.stage == "check-guard"
    assert error.value.descriptor_cleanup_confirmed


def test_constructor_guard_coroutine_result_closed_without_running(parent):
    async def unused():
        raise AssertionError("No coroutine body may execute")

    coroutine = unused()
    with pytest.raises(RepositoryHttpFilesInitializationError) as error:
        RepositoryHttpFiles(materials(), SOURCE, _parent=parent, guard=lambda: coroutine)
    assert coroutine.cr_frame is None
    assert list(parent.iterdir()) == []
    assert error.value.created_path is None
    assert error.value.descriptor_cleanup_confirmed
