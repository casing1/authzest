"""Private inert profile files and descriptors; no client, daemon or target."""

from __future__ import annotations

import asyncio
import copy
import os
import pickle
import socket
import subprocess
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _repository_http_runtime_input as runtime_input
from authzest.runner._repository_http_runtime_profile import RepositoryHttpRuntimeProfile
from test_repository_http_runtime_profile import profile_data

pytestmark = pytest.mark.skipif(
    not runtime_input._supported(), reason="POSIX no-follow private profile scope"
)


def _declaration():
    return profile_data()


@pytest.fixture(autouse=True)
def forbid_execution_and_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Profile input must not execute a process or contact a socket")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "execve", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


@pytest.fixture
def profile_file(tmp_path):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    path = parent / "runtime.json"
    path.write_text(canonical(_declaration()) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _descriptors(value):
    return [value._fd, *(fd for _, fd, _ in value._parents)]


def _assert_closed(fds):
    for fd in fds:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_capture_review_and_unchanged_rechecks_are_data_only(profile_file):
    raw = profile_file.read_bytes()
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)
    try:
        assert value.assert_current() is None
        review = value.review_dict()
        assert type(value.profile) is RepositoryHttpRuntimeProfile
        assert review["schema_version"] == "2.0"
        assert review["kind"] == "repository-http-runtime-input-review"
        assert review["status"] == "profile-file-captured-unverified-runtime"
        assert review["profile"] == _declaration()
        assert review["profile_id"] == value.profile.profile_id
        assert review["profile_file"]["sha256"] == sha256(raw).hexdigest()
        assert review["profile_file"]["size"] == len(raw)
        assert len(review["profile_file"]["identity"]) == 9
        assert review["profile_file"]["parents"]
        assert review["execution_authorized"] is False
        assert review["resource_enforcement_established"] is False
        assert review["isolation_established"] is False
        assert "ready" not in review and "readiness" not in review
        review["profile"]["engine"]["endpoint"] = "changed detached data"
        assert value.review_dict()["profile"] == _declaration()
        assert profile_file.read_bytes() == raw
    finally:
        value.close()
    _assert_closed(fds)
    value.close()
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="input-closed"):
        value.assert_current()
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="input-closed"):
        _ = value.profile


def test_loading_never_reads_a_repository_manifest(profile_file, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Installed loader must use maintained source pins, not repository files")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    try:
        assert value.profile.to_dict() == _declaration()
    finally:
        value.close()


@pytest.mark.parametrize("role", ["A", "B"])
@pytest.mark.parametrize("field", ["dependency_lock_sha256", "recipe_sha256"])
def test_declared_image_input_drift_refuses(profile_file, role, field):
    data = _declaration()
    data["images"][role][field] = "f" * 64
    profile_file.write_text(canonical(data))
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="declaration-invalid"):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


def test_asset_or_duplicate_declaration_refuses(profile_file):
    data = _declaration()
    data["images"]["A"]["assets"]["app_launcher.py"] = "f" * 64
    profile_file.write_text(canonical(data))
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="declaration-invalid"):
        runtime_input.prepare_repository_http_runtime_input(profile_file)
    profile_file.write_text('{"schema_version":"1.0","schema_version":"1.0"}')
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="declaration-invalid"):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize("mode", [0o400, 0o644, 0o660, 0o620])
def test_profile_requires_exact_private_mode(profile_file, mode):
    profile_file.chmod(mode)
    with pytest.raises(
        runtime_input.RepositoryHttpRuntimeInputError, match="private-file-required"
    ):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize(
    "payload",
    [b"", b"x" * 16385, b"\xff\xff", b"[]"],
    ids=["empty", "oversized", "invalid-utf8", "array"],
)
def test_empty_oversized_or_invalid_profile_refuses(profile_file, payload):
    profile_file.write_bytes(payload)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize(
    "kind", ["leaf-symlink", "dangling-symlink", "directory", "fifo", "hardlink"]
)
def test_aliases_and_nonregular_inputs_refuse(profile_file, kind):
    if kind == "hardlink":
        os.link(profile_file, profile_file.with_name("second-link"))
    elif kind == "leaf-symlink":
        original = profile_file.with_name("original")
        profile_file.rename(original)
        profile_file.symlink_to(original)
    else:
        profile_file.unlink()
        if kind == "dangling-symlink":
            profile_file.symlink_to(profile_file.with_name("missing"))
        elif kind == "directory":
            profile_file.mkdir(mode=0o600)
        else:
            os.mkfifo(profile_file, 0o600)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


def test_linked_or_writable_parent_refuses(profile_file):
    alias = profile_file.parent.with_name("alias")
    alias.symlink_to(profile_file.parent, target_is_directory=True)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError):
        runtime_input.prepare_repository_http_runtime_input(alias / profile_file.name)
    profile_file.parent.chmod(0o777)
    try:
        with pytest.raises(
            runtime_input.RepositoryHttpRuntimeInputError, match="parent-unavailable"
        ):
            runtime_input.prepare_repository_http_runtime_input(profile_file)
    finally:
        profile_file.parent.chmod(0o700)


@pytest.mark.parametrize("mutation", ["bytes", "same-byte-replacement", "mode", "link", "unlink"])
def test_file_edits_or_identity_replacement_close_the_pin(profile_file, mutation):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)
    if mutation == "bytes":
        profile_file.write_bytes(profile_file.read_bytes() + b" ")
    elif mutation == "same-byte-replacement":
        replacement = profile_file.with_name("replacement")
        replacement.write_bytes(profile_file.read_bytes())
        replacement.chmod(0o600)
        os.replace(replacement, profile_file)
    elif mutation == "mode":
        profile_file.chmod(0o640)
    elif mutation == "link":
        os.link(profile_file, profile_file.with_name("second"))
    else:
        profile_file.unlink()
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError) as caught:
        value.assert_current()
    assert str(profile_file) not in str(caught.value)
    assert caught.value.descriptor_cleanup_confirmed is True
    _assert_closed(fds)


@pytest.mark.parametrize("mutation", ["replacement", "symlink", "mode"])
def test_named_parent_drift_closes_the_pin(profile_file, mutation):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)
    if mutation == "mode":
        profile_file.parent.chmod(0o770)
    else:
        parent = profile_file.parent
        old = parent.with_name("retained-old")
        parent.rename(old)
        if mutation == "symlink":
            parent.symlink_to(old, target_is_directory=True)
        else:
            parent.mkdir(mode=0o700)
            (parent / profile_file.name).write_bytes((old / profile_file.name).read_bytes())
            (parent / profile_file.name).chmod(0o600)
    try:
        with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError):
            value.assert_current()
        _assert_closed(fds)
    finally:
        if mutation == "mode":
            profile_file.parent.chmod(0o700)


def test_replacement_during_bounded_read_is_detected(profile_file, monkeypatch):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds, actual_pread = _descriptors(value), os.pread
    replacement = profile_file.with_name("replacement")
    replacement.write_bytes(profile_file.read_bytes())
    replacement.chmod(0o600)
    changed = False

    def replace_during_read(fd, count, offset):
        nonlocal changed
        answer = actual_pread(fd, count, offset)
        if fd == value._fd and not changed:
            changed = True
            os.replace(replacement, profile_file)
        return answer

    monkeypatch.setattr(os, "pread", replace_during_read)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError):
        value.assert_current()
    assert changed
    _assert_closed(fds)


def test_open_failure_closes_already_owned_directory_descriptors(profile_file, monkeypatch):
    actual_open, observed = os.open, []

    def fail_leaf(path, *args, **kwargs):
        if path == profile_file.name:
            raise PermissionError("must not expose profile name or permissions")
        fd = actual_open(path, *args, **kwargs)
        observed.append(fd)
        return fd

    monkeypatch.setattr(os, "open", fail_leaf)
    with pytest.raises(
        runtime_input.RepositoryHttpRuntimeInputError, match="file-unavailable"
    ) as caught:
        runtime_input.prepare_repository_http_runtime_input(profile_file)
    assert caught.value.descriptor_cleanup_confirmed is True
    assert observed
    _assert_closed(observed)


def test_cleanup_error_preserves_primary_failure_and_attempts_remaining_fds(
    profile_file, monkeypatch
):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds, actual_close, closed = _descriptors(value), os.close, []
    profile_file.chmod(0o640)

    def uncertain_close(fd):
        actual_close(fd)
        closed.append(fd)
        if fd == fds[0]:
            raise OSError("simulated close uncertainty")

    monkeypatch.setattr(os, "close", uncertain_close)
    with pytest.raises(
        runtime_input.RepositoryHttpRuntimeInputError, match="private-file-required"
    ) as caught:
        value.assert_current()
    assert caught.value.descriptor_cleanup_confirmed is False
    assert sorted(closed) == sorted(fds)
    _assert_closed(fds)


def test_prior_close_uncertainty_stays_sticky_without_reclosing_stale_fds(
    profile_file, monkeypatch
):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds, actual_close, closed = _descriptors(value), os.close, []
    profile_file.chmod(0o640)

    def uncertain_close(fd):
        actual_close(fd)
        closed.append(fd)
        if fd == fds[0]:
            raise OSError("simulated consumed-but-unconfirmed descriptor")

    monkeypatch.setattr(os, "close", uncertain_close)
    with pytest.raises(
        runtime_input.RepositoryHttpRuntimeInputError, match="private-file-required"
    ) as caught:
        value.assert_current()
    assert caught.value.descriptor_cleanup_confirmed is False
    assert sorted(closed) == sorted(fds)
    _assert_closed(fds)
    before = list(closed)
    for _ in range(2):
        with pytest.raises(
            runtime_input.RepositoryHttpRuntimeInputError, match="cleanup-unconfirmed"
        ) as caught:
            value.close()
        assert caught.value.descriptor_cleanup_confirmed is False
        assert closed == before


def test_close_cancellation_propagates_once_and_later_closure_remains_uncertain(
    profile_file, monkeypatch
):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds, actual_close, closed = _descriptors(value), os.close, []
    original = KeyboardInterrupt("first-close-cancellation")

    def interrupted_close(fd):
        actual_close(fd)
        closed.append(fd)
        if fd == fds[0]:
            raise original

    monkeypatch.setattr(os, "close", interrupted_close)
    with pytest.raises(KeyboardInterrupt) as caught:
        value.close()
    assert caught.value is original
    assert sorted(closed) == sorted(fds)
    _assert_closed(fds)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="cleanup-unconfirmed"):
        value.close()
    assert len(closed) == len(fds)


def test_interrupted_read_propagates_after_closing_all_owned_descriptors(profile_file, monkeypatch):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)

    def interrupted(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "pread", interrupted)
    with pytest.raises(KeyboardInterrupt) as caught:
        value.assert_current()
    assert caught.value.runtime_profile_cleanup_confirmed is True
    _assert_closed(fds)


@pytest.mark.parametrize("mode", ["frozen", "unsupported"])
def test_unsupported_platform_refuses_before_open(profile_file, monkeypatch, mode):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Unsupported platform must refuse before file acquisition")

    if mode == "frozen":
        monkeypatch.setattr(runtime_input.sys, "frozen", True, raising=False)
    else:
        monkeypatch.setattr(runtime_input, "_supported", lambda: False)
    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="platform-unsupported"):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize(
    "path",
    [None, False, "", "../profile", "bad\nprofile", "x" * 513],
    ids=["none", "boolean", "empty", "parent-traversal", "newline", "oversized"],
)
def test_invalid_paths_are_redacted_without_open(path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid paths must refuse before file acquisition")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="path-invalid"):
        runtime_input.prepare_repository_http_runtime_input(path)


def test_wrong_file_owner_refuses(profile_file, monkeypatch):
    actual_fstat = os.fstat

    def wrong_owner(fd):
        info = actual_fstat(fd)
        if info.st_ino == profile_file.stat().st_ino and info.st_dev == profile_file.stat().st_dev:
            names = (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_uid",
                "st_gid",
                "st_nlink",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
            values = {name: getattr(info, name) for name in names}
            values["st_uid"] = os.geteuid() + 1
            return SimpleNamespace(**values)
        return info

    monkeypatch.setattr(os, "fstat", wrong_owner)
    with pytest.raises(
        runtime_input.RepositoryHttpRuntimeInputError, match="private-file-required"
    ):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize("special", [0o4000, 0o2000, 0o1000])
def test_reported_special_file_mode_is_not_private_profile_mode(profile_file, special):
    # macOS can strip these chmod bits on non-executable user files. Exercise
    # reported metadata explicitly rather than pretending the OS retained them.
    info = profile_file.stat()
    with pytest.raises(
        runtime_input.RepositoryHttpRuntimeInputError, match="private-file-required"
    ):
        runtime_input._file(
            SimpleNamespace(
                st_mode=info.st_mode | special,
                st_uid=info.st_uid,
                st_nlink=info.st_nlink,
                st_size=info.st_size,
            )
        )


def test_relative_selected_path_is_captured_without_resolving_aliases(profile_file, monkeypatch):
    monkeypatch.chdir(profile_file.parent)
    value = runtime_input.prepare_repository_http_runtime_input(profile_file.name)
    try:
        assert value.review_dict()["profile_path"] == str(profile_file)
        value.assert_current()
    finally:
        value.close()


def test_premature_eof_cannot_pin_a_valid_json_prefix_as_the_complete_file(
    profile_file, monkeypatch
):
    prefix = canonical(_declaration()).encode()
    profile_file.write_bytes(prefix + b" " * 32)

    def short_read(_fd, count, offset):
        return prefix[offset : offset + count]

    monkeypatch.setattr(os, "pread", short_read)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="file-changed"):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize("change", ["legacy", "legacy-kind", "T", "amd64", "unknown-field"])
def test_http_loader_refuses_other_contracts(profile_file, change):
    data = _declaration()
    if change == "legacy":
        data["schema_version"] = "1.0"
    elif change == "legacy-kind":
        data["kind"] = "generated-repair-runtime-profile"
    elif change == "T":
        data["images"]["T"] = data["images"]["A"]
    elif change == "amd64":
        data["platform"] = "linux/amd64"
    else:
        data["execution_authorized"] = True
    profile_file.write_text(canonical(data))
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="declaration-invalid"):
        runtime_input.prepare_repository_http_runtime_input(profile_file)


@pytest.mark.parametrize("operation", [copy.copy, copy.deepcopy, pickle.dumps])
def test_live_profile_input_cannot_be_copied_or_saved(profile_file, operation):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    try:
        with pytest.raises(TypeError):
            operation(value)
        value.assert_current()
    finally:
        value.close()


@pytest.mark.parametrize("operation", ["profile", "assert_current", "review_dict", "close"])
@pytest.mark.parametrize("owner", ["process", "thread"])
def test_foreign_owner_cannot_use_or_close_the_pin(profile_file, monkeypatch, operation, owner):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)
    with monkeypatch.context() as patch:
        if owner == "process":
            patch.setattr(runtime_input.os, "getpid", lambda: value._pid + 1)
        else:
            patch.setattr(runtime_input.threading, "get_ident", lambda: value._thread + 1)
        with pytest.raises(
            runtime_input.RepositoryHttpRuntimeInputError, match="owner-unavailable"
        ):
            getattr(value, operation)() if operation != "profile" else value.profile
        assert all(os.fstat(fd) for fd in fds)
    value.assert_current()
    value.close()
    _assert_closed(fds)


@pytest.mark.parametrize("operation", ["profile", "assert_current", "review_dict", "close"])
def test_suppressed_reentry_poison_closes_the_outer_pin(profile_file, monkeypatch, operation):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds, pread = _descriptors(value), os.pread
    ran = False

    def reenter(fd, count, offset):
        nonlocal ran
        if not ran:
            ran = True
            with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="reentrant"):
                getattr(value, operation)() if operation != "profile" else value.profile
        return pread(fd, count, offset)

    monkeypatch.setattr(os, "pread", reenter)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="reentrant"):
        value.assert_current()
    assert ran
    _assert_closed(fds)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="input-closed"):
        value.assert_current()


def test_profile_property_does_not_return_stale_declaration(profile_file):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)
    profile_file.write_bytes(profile_file.read_bytes() + b" ")
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError):
        _ = value.profile
    _assert_closed(fds)


def test_profile_object_tampering_is_refused(profile_file):
    value = runtime_input.prepare_repository_http_runtime_input(profile_file)
    fds = _descriptors(value)
    value._profile = value._profile.to_dict()
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="file-changed"):
        value.assert_current()
    _assert_closed(fds)


def test_subclass_cannot_capture_a_profile(profile_file, monkeypatch):
    class Other(runtime_input.LoadedRepositoryHttpRuntimeProfile):
        pass

    def forbidden(*args, **kwargs):
        pytest.fail("Subclass must refuse before acquiring a file")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(runtime_input.RepositoryHttpRuntimeInputError, match="subclass"):
        Other(profile_file)
