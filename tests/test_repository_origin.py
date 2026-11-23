"""Initial identity continuity using owned inert files; no target/provider execution."""

import builtins
import copy
import os
import pickle
import socket
import stat
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from authzest.analyzer import repository_input as loader
from authzest.analyzer import repository_origin as origin

SOURCE = 'raise RuntimeError("Selected source must never execute")\n'
POLICY = "Only an authenticated owner may read an item.\n"


@pytest.fixture
def repo(tmp_path):
    if not loader._supported():
        pytest.skip("Live origin needs descriptor-relative POSIX source operations")
    root = tmp_path.resolve() / "external"
    root.mkdir()
    (root / "app.py").write_text(SOURCE, encoding="utf-8")
    (root / "POLICY.md").write_text(POLICY, encoding="utf-8")
    return root


def capture(repo, **kwargs):
    return origin.capture_repository_origin(repo, "app.py", "POLICY.md", **kwargs)


def test_initial_snapshot_retains_exact_bytes_and_is_content_only(repo):
    (repo / "api").mkdir()
    (repo / "api" / "__init__.py").write_bytes(b"")
    raw = 'OWNER = "소유자"\r\n'.encode()
    (repo / "api" / "권한.py").write_bytes(raw)
    with capture(repo, contexts=("api/권한.py", "api/__init__.py")) as live:
        data = live.snapshot
        assert live.verify(data.to_dict()) is data
        assert data.root == repo
        assert data.files[0].text == SOURCE and data.files[1].text == POLICY
        assert data.files[2].text.encode() == raw
        assert data.files[2].sha256 == sha256(raw).hexdigest()
        assert data.files[-1].text == ""
        assert "root" not in data.to_dict()
        assert str(repo) not in str(data.to_dict())
        with pytest.raises(FrozenInstanceError):
            data.source = "replacement.py"
        with pytest.raises(AttributeError):
            live.snapshot = data
    assert live.closed
    assert live.snapshot is data  # Detached content does not regain live authority.
    with pytest.raises(origin.RepositoryOriginError, match="closed"):
        live.verify()


def test_capture_matches_unchanged_content_loader_without_changing_its_api(repo):
    expected = loader.capture_repository(repo, "app.py", "POLICY.md")
    with capture(repo) as live:
        assert live.snapshot == expected
        assert live.verify() == expected
    assert loader.capture_repository(repo, "app.py", "POLICY.md") == expected


def test_empty_selected_source_is_preserved_without_synthetic_content(repo):
    (repo / "app.py").write_bytes(b"")
    with capture(repo) as live:
        assert live.snapshot.files[0].text == ""
        assert live.snapshot.files[0].sha256 == sha256(b"").hexdigest()
        assert live.verify() == live.snapshot


def test_capture_and_verify_have_no_write_import_network_or_execution_effect(repo, monkeypatch):
    actual_open = os.open

    def readonly_open(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        return actual_open(path, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Selected-file capture performed an external effect")

    monkeypatch.setattr(os, "open", readonly_open)
    for owner, names in (
        (os, ("write", "mkdir", "rename", "unlink", "listdir", "scandir", "system")),
        (builtins, ("exec", "eval")),
        (socket, ("socket", "create_connection")),
        (subprocess, ("Popen",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    with capture(repo) as live:
        assert live.verify().files[0].text == SOURCE


def test_unselected_additions_and_directory_timestamp_changes_are_allowed(repo):
    with capture(repo) as live:
        (repo / ".env").write_bytes(b"do-not-read=private\x00")
        (repo / "unselected.py").write_bytes(b"\xffnot selected")
        (repo / "unselected-directory").mkdir()
        assert live.verify().files[0].text == SOURCE


@pytest.mark.parametrize("member", ["app.py", "POLICY.md", "api/auth.py"])
def test_selected_byte_edit_is_refused_with_redacted_failure(repo, member):
    (repo / "api").mkdir()
    (repo / "api" / "auth.py").write_text("OWNER = 'alice'\n")
    with capture(repo, contexts=("api/auth.py",)) as live:
        (repo / member).write_text("changed\n")
        with pytest.raises(origin.RepositoryOriginError, match="changed") as error:
            live.verify()
        assert str(repo) not in str(error.value) and member not in str(error.value)


@pytest.mark.parametrize("member", ["app.py", "POLICY.md"])
def test_same_bytes_in_replacement_inode_do_not_satisfy_initial_identity(repo, member):
    with capture(repo) as live:
        target = repo / member
        data = target.read_bytes()
        target.rename(repo / (member + ".old"))
        target.write_bytes(data)
        with pytest.raises(origin.RepositoryOriginError, match="changed"):
            live.verify(live.snapshot.to_dict())


def test_same_bytes_in_place_rewrite_is_not_a_fresh_origin(repo):
    with capture(repo) as live:
        path = repo / "app.py"
        before = path.stat()
        path.write_bytes(path.read_bytes())
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
        with pytest.raises(origin.RepositoryOriginError, match="changed"):
            live.verify()


@pytest.mark.parametrize("kind", ["file-mode", "root-mode", "hardlink", "missing", "symlink"])
def test_metadata_name_and_link_changes_are_refused(repo, kind):
    with capture(repo) as live:
        path = repo / "app.py"
        if kind == "file-mode":
            path.chmod(stat.S_IMODE(path.stat().st_mode) ^ 0o020)
        elif kind == "root-mode":
            repo.chmod(stat.S_IMODE(repo.stat().st_mode) ^ 0o020)
        elif kind == "hardlink":
            os.link(path, repo / "alias.py")
        elif kind == "missing":
            path.unlink()
        else:
            path.rename(repo / "actual.py")
            path.symlink_to(repo / "actual.py")
        with pytest.raises(origin.RepositoryOriginError):
            live.verify()


def test_root_replaced_by_same_content_does_not_keep_authority(repo):
    with capture(repo) as live:
        repo.rename(repo.parent / "old-root")
        repo.mkdir()
        (repo / "app.py").write_text(SOURCE)
        (repo / "POLICY.md").write_text(POLICY)
        with pytest.raises(origin.RepositoryOriginError, match="changed"):
            live.verify()


def test_selected_parent_replaced_by_same_content_is_refused(repo):
    parent = repo / "api"
    parent.mkdir()
    (parent / "auth.py").write_text("guard = True\n")
    with capture(repo, contexts=("api/auth.py",)) as live:
        parent.rename(repo / "old-api")
        parent.mkdir()
        (parent / "auth.py").write_text("guard = True\n")
        with pytest.raises(origin.RepositoryOriginError, match="changed"):
            live.verify()


def test_file_changed_during_verification_is_refused(repo, monkeypatch):
    with capture(repo) as live:
        read = loader._read

        def changed_after_read(fd, limit):
            raw = read(fd, limit)
            (repo / "app.py").write_text("changed = True\n")
            return raw

        monkeypatch.setattr(loader, "_read", changed_after_read)
        with pytest.raises(origin.RepositoryOriginError, match="changed"):
            live.verify()


def test_parent_changed_after_last_file_read_is_refused(repo, monkeypatch):
    with capture(repo) as live:
        read = loader._read
        calls = 0

        def replace_root(fd, limit):
            nonlocal calls
            raw = read(fd, limit)
            calls += 1
            if calls == 2:
                repo.rename(repo.parent / "old-root")
                repo.mkdir()
                (repo / "app.py").write_text(SOURCE)
                (repo / "POLICY.md").write_text(POLICY)
            return raw

        monkeypatch.setattr(loader, "_read", replace_root)
        with pytest.raises(origin.RepositoryOriginError, match="changed"):
            live.verify()


def test_initial_capture_refuses_edits_between_selected_reads(repo, monkeypatch):
    read = loader._read
    calls = 0

    def edit_source(fd, limit):
        nonlocal calls
        raw = read(fd, limit)
        calls += 1
        if calls == 2:
            (repo / "app.py").write_text("changed = True\n")
        return raw

    monkeypatch.setattr(loader, "_read", edit_source)
    with pytest.raises(origin.RepositoryOriginError, match="changed"):
        capture(repo)


@pytest.mark.parametrize("change", ["text", "hash", "path", "extra", "order", "wrong-type"])
def test_supplied_current_selection_must_match_exact_initial_content(repo, change):
    with capture(repo) as live:
        value = live.snapshot.to_dict()
        if change == "text":
            value["files"][0]["text"] += "# drift\n"
        elif change == "hash":
            value["files"][0]["sha256"] = "0" * 64
        elif change == "path":
            value["source"] = "other.py"
        elif change == "extra":
            value["root"] = str(repo)
        elif change == "order":
            value["files"].reverse()
        else:
            value = list(value.items())
        with pytest.raises(origin.RepositoryOriginError, match="selection-mismatch"):
            live.verify(value)


def test_held_descriptors_live_until_close_and_all_are_released(repo, monkeypatch):
    actual_open = os.open
    descriptors = []

    def tracked_open(*args, **kwargs):
        fd = actual_open(*args, **kwargs)
        descriptors.append(fd)
        return fd

    monkeypatch.setattr(os, "open", tracked_open)
    live = capture(repo)
    assert len(descriptors) >= len(repo.parts) + 2
    assert all(os.fstat(fd) for fd in descriptors)
    live.close()
    live.close()
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)
    assert (repo / "app.py").read_text() == SOURCE


def test_initial_failure_closes_all_previously_opened_descriptors(repo, monkeypatch):
    actual_open = os.open
    descriptors = []

    def fail_after_source(path, *args, **kwargs):
        if path == "POLICY.md":
            raise OSError("private full path must not escape")
        fd = actual_open(path, *args, **kwargs)
        descriptors.append(fd)
        return fd

    monkeypatch.setattr(os, "open", fail_after_source)
    with pytest.raises(origin.RepositoryOriginError, match="unavailable") as error:
        capture(repo)
    assert "private" not in str(error.value)
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_close_failure_is_redacted_and_does_not_skip_other_descriptors(repo, monkeypatch):
    actual_open, actual_close = os.open, os.close
    descriptors, closed = [], []

    def tracked_open(*args, **kwargs):
        fd = actual_open(*args, **kwargs)
        descriptors.append(fd)
        return fd

    def unconfirmed_close(fd):
        actual_close(fd)
        closed.append(fd)
        if len(closed) == 1:
            raise OSError("private root information must not escape")

    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "close", unconfirmed_close)
    live = capture(repo)
    with pytest.raises(origin.RepositoryOriginError, match="close-unconfirmed") as error:
        live.close()
    assert "private" not in str(error.value) and live.closed
    assert sorted(closed) == sorted(descriptors)
    live.close()
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_capture_interruption_releases_every_descriptor_and_retains_cleanup_status(
    repo, monkeypatch, cleanup_failure
):
    actual_open, actual_close = os.open, os.close
    descriptors = []
    close_calls = 0

    def tracked_open(*args, **kwargs):
        fd = actual_open(*args, **kwargs)
        descriptors.append(fd)
        return fd

    def interrupted_read(*args):
        raise KeyboardInterrupt("owned interruption")

    def unconfirmed_close(fd):
        nonlocal close_calls
        actual_close(fd)
        close_calls += 1
        if cleanup_failure and close_calls == 1:
            raise OSError("private cleanup detail")

    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "close", unconfirmed_close)
    monkeypatch.setattr(loader, "_read", interrupted_read)
    with pytest.raises(KeyboardInterrupt) as error:
        capture(repo)
    assert error.value.origin_cleanup_confirmed is not cleanup_failure
    assert close_calls == len(descriptors)
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_capture_cleanup_failure_is_reported_without_private_error_text(repo, monkeypatch):
    actual_close = os.close
    calls = 0

    def failure_read(*args):
        raise OSError("private original path")

    def uncertain_close(fd):
        nonlocal calls
        actual_close(fd)
        calls += 1
        if calls == 1:
            raise OSError("private cleanup path")

    monkeypatch.setattr(loader, "_read", failure_read)
    monkeypatch.setattr(os, "close", uncertain_close)
    with pytest.raises(origin.RepositoryOriginError, match="cleanup-unconfirmed") as error:
        capture(repo)
    assert "private" not in str(error.value)


def test_verification_read_failure_stays_in_origin_error_contract(repo, monkeypatch):
    with capture(repo) as live:

        def fail_read(*args):
            raise loader.RepositoryInputError("repository-input-size-limit")

        monkeypatch.setattr(loader, "_read", fail_read)
        with pytest.raises(origin.RepositoryOriginError, match="repository-origin-size-limit"):
            live.verify()


def test_context_exit_releases_descriptors_when_user_raises(repo):
    with pytest.raises(RuntimeError, match="owned caller"), capture(repo) as live:
        raise RuntimeError("owned caller")
    assert live.closed
    with pytest.raises(origin.RepositoryOriginError, match="closed"):
        live.verify()


def test_origin_refuses_other_process_without_reopening_paths(repo, monkeypatch):
    live = capture(repo)
    pid = os.getpid()
    monkeypatch.setattr(os, "getpid", lambda: pid + 1)
    with pytest.raises(origin.RepositoryOriginError, match="process-changed"):
        live.verify()
    live.close()  # Releasing inherited descriptors grants no new authority.
    assert live.closed


def test_content_objects_saved_records_and_forged_handles_cannot_adopt_authority(repo):
    snapshot = loader.capture_repository(repo, "app.py", "POLICY.md")
    with pytest.raises(origin.RepositoryOriginError, match="factory-required"):
        origin.RepositoryOrigin(snapshot, (), (), None)
    with pytest.raises(origin.RepositoryOriginError, match="closed"):
        object.__new__(origin.RepositoryOrigin).verify()
    with capture(repo) as live:
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError, match="cannot be"):
                operation(live)
        assert not any(hasattr(live, name) for name in ("open", "reopen", "resume", "from_dict"))


@pytest.mark.parametrize(
    "kind", ["file-symlink", "root-symlink", "parent-symlink", "hardlink", "fifo"]
)
def test_initial_links_and_special_files_are_refused_without_blocking(repo, kind):
    if kind == "root-symlink":
        alias = repo.parent / "alias"
        alias.symlink_to(repo, target_is_directory=True)
        repo = alias
    elif kind == "parent-symlink":
        (repo / "api").symlink_to(repo, target_is_directory=True)
        with pytest.raises(origin.RepositoryOriginError):
            capture(repo, contexts=("api/app.py",))
        return
    else:
        path = repo / "app.py"
        path.unlink()
        if kind == "file-symlink":
            path.symlink_to(repo / "POLICY.md")
        elif kind == "hardlink":
            os.link(repo / "POLICY.md", path)
        else:
            os.mkfifo(path)
    with pytest.raises(origin.RepositoryOriginError):
        capture(repo)


@pytest.mark.parametrize(
    "source,policy,contexts",
    [
        ("../app.py", "POLICY.md", ()),
        ("app.py", ".env", ()),
        ("app.py", "POLICY.md", ["auth.py"]),
        ("app.py", "POLICY.md", ("app.py",)),
        ("app.py", "POLICY.md", ("auth.py",) * 5),
    ],
)
def test_existing_selection_bounds_are_preserved(repo, source, policy, contexts):
    with pytest.raises(origin.RepositoryOriginError, match="selection-invalid"):
        origin.capture_repository_origin(repo, source, policy, contexts)


@pytest.mark.parametrize("member,limit", [("app.py", 16_384), ("POLICY.md", 8192)])
def test_per_file_budget_is_retained(repo, member, limit):
    (repo / member).write_bytes(b"x" * (limit + 1))
    with pytest.raises(origin.RepositoryOriginError, match="size-limit"):
        capture(repo)


def test_total_budget_is_retained(repo):
    (repo / "app.py").write_bytes(b"x" * loader.MAX_SOURCE_BYTES)
    names = tuple(f"context{i}.py" for i in range(4))
    for name in names:
        (repo / name).write_bytes(b"x" * loader.MAX_SOURCE_BYTES)
    with pytest.raises(origin.RepositoryOriginError, match="size-limit"):
        capture(repo, contexts=names)


@pytest.mark.parametrize(
    "member,raw", [("app.py", b"\xff"), ("app.py", b"a\0b"), ("POLICY.md", b" \n")]
)
def test_text_validation_is_retained(repo, member, raw):
    (repo / member).write_bytes(raw)
    with pytest.raises(origin.RepositoryOriginError):
        capture(repo)


def test_platform_refusal_occurs_before_opening_any_original(monkeypatch):
    monkeypatch.setattr(loader, "_supported", lambda: False)
    with pytest.raises(origin.RepositoryOriginError, match="platform-unsupported"):
        origin.capture_repository_origin(None, "app.py", "POLICY.md")
