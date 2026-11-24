"""Real owned inert files and synthetic endpoint facts; never execute a client."""

from __future__ import annotations

import asyncio
import copy
import os
import pickle
import socket
import stat
import subprocess
from hashlib import sha256
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _repository_http_client_pin as phase
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpRuntimeProfile,
    validate_runtime_profile,
)
from test_repository_http_runtime_profile import profile_data

pytestmark = pytest.mark.skipif(
    os.name != "posix" or not hasattr(os, "O_NOFOLLOW"),
    reason="Private POSIX client file pin scope",
)
CLIENT = b"maintained inert client bytes, never executable source\n"


@pytest.fixture(autouse=True)
def no_process_or_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Client identity tests must not execute a client or contact an endpoint")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "execve", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


@pytest.fixture
def files(tmp_path, monkeypatch):
    binary_parent, config_parent = tmp_path / "client", tmp_path / "private-config-parent"
    binary_parent.mkdir(mode=0o700)
    config_parent.mkdir(mode=0o700)
    binary = binary_parent / "docker"
    binary.write_bytes(CLIENT)
    binary.chmod(0o500)
    config_dir = config_parent / "docker-config"
    config_dir.mkdir(mode=0o700)
    config = config_dir / "config.json"
    config.write_bytes(b"{}\n")
    config.chmod(0o600)
    declaration = profile_data()
    declaration["engine"].update(
        executable=str(binary),
        executable_sha256=sha256(CLIENT).hexdigest(),
        config_dir=str(config_dir),
    )
    profile = validate_runtime_profile(canonical(declaration))
    endpoint = {
        "socket_identity": [1, 2, stat.S_IFSOCK | 0o600, os.geteuid(), os.getegid(), 1, 0, 3, 4],
        "parent_chain_sha256": "a" * 64,
    }
    observations = []

    def observed(path):
        assert path == "/private/runtime/docker.sock"
        observations.append(path)
        return copy.deepcopy(endpoint)

    monkeypatch.setattr(phase, "_endpoint_identity", observed)
    ticks = []
    return SimpleNamespace(
        root=tmp_path,
        binary=binary,
        binary_parent=binary_parent,
        config=config,
        config_dir=config_dir,
        config_parent=config_parent,
        profile=profile,
        endpoint=endpoint,
        observations=observations,
        ticks=ticks,
        tick=lambda: ticks.append("original-deadline-checked"),
    )


def test_matching_client_is_rehashed_through_real_no_follow_descriptors(files, monkeypatch):
    actual_open, actual_fstat = os.open, os.fstat
    opened = []

    def tracked(path, flags, *args, **kwargs):
        assert str(path) in {str(files.binary), str(files.config)}
        assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
        descriptor = actual_open(path, flags, *args, **kwargs)
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(phase.os, "open", tracked)
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    initial = copy.deepcopy(pin._identity_json)
    pin.check()
    assert pin._identity_json == initial
    assert len(files.observations) == 2 and len(opened) == 4
    assert len(files.ticks) >= 12
    assert files.binary.read_bytes() == CLIENT
    for descriptor in opened:
        with pytest.raises(OSError):
            actual_fstat(descriptor)


@pytest.mark.parametrize("replace_inode", [False, True], ids=["same-inode", "new-inode"])
@pytest.mark.parametrize("change_bytes", [False, True], ids=["same-bytes", "different-bytes"])
def test_client_byte_or_file_identity_changes_are_refused(files, replace_inode, change_bytes):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    before = files.binary.stat()
    raw = b"x" * len(CLIENT) if change_bytes else CLIENT
    if replace_inode:
        replacement = files.root / "replacement-client"
        replacement.write_bytes(raw)
        replacement.chmod(0o500)
        replacement.replace(files.binary)
        assert files.binary.stat().st_ino != before.st_ino
    else:
        files.binary.chmod(0o700)
        files.binary.write_bytes(raw)
        files.binary.chmod(0o500)
        os.utime(files.binary, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        assert files.binary.stat().st_ino == before.st_ino
    with pytest.raises(phase.RepositoryHttpClientPinError):
        pin.check()
    assert files.binary.read_bytes() == raw


@pytest.mark.parametrize(
    "target,mode",
    [
        ("binary", 0o400),
        ("binary", 0o520),
        ("binary", 0o700),
        ("config", 0o640),
        ("config", 0o400),
        ("config_dir", 0o750),
        ("binary_parent", 0o777),
        ("config_parent", 0o777),
    ],
)
def test_client_config_and_parent_permission_drift_is_refused(files, target, mode):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    getattr(files, target).chmod(mode)
    with pytest.raises(phase.RepositoryHttpClientPinError):
        pin.check()


@pytest.mark.parametrize(
    "change", ["extra-file", "extra-directory", "different-bytes", "replacement"]
)
def test_empty_private_config_has_exact_membership_bytes_and_file_identity(files, change):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    if change == "extra-file":
        (files.config_dir / "credentials.json").write_bytes(b"inert")
    elif change == "extra-directory":
        (files.config_dir / "contexts").mkdir()
    elif change == "different-bytes":
        files.config.write_bytes(b"[]\n")
    else:
        old_inode = files.config.stat().st_ino
        replacement = files.root / "replacement-config"
        replacement.write_bytes(b"{}\n")
        replacement.chmod(0o600)
        replacement.replace(files.config)
        assert files.config.stat().st_ino != old_inode
    with pytest.raises(phase.RepositoryHttpClientPinError):
        pin.check()


@pytest.mark.parametrize("target", ["binary", "config", "binary_parent", "config_parent"])
@pytest.mark.parametrize("initial", [False, True], ids=["changed-after-pin", "initial-alias"])
def test_file_and_parent_symlink_aliases_are_refused_even_with_matching_bytes(
    files, target, initial
):
    pin = None if initial else phase.RepositoryHttpClientPin(files.profile, files.tick)
    path = getattr(files, target)
    original = files.root / ("retained-" + target)
    path.rename(original)
    path.symlink_to(original, target_is_directory=original.is_dir())
    assert path.is_symlink()
    with pytest.raises(phase.RepositoryHttpClientPinError):
        if initial:
            phase.RepositoryHttpClientPin(files.profile, files.tick)
        else:
            pin.check()


@pytest.mark.parametrize("target", ["binary", "config"])
def test_single_link_inputs_cannot_gain_another_hardlink(files, target):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    path = getattr(files, target)
    os.link(path, files.root / ("hardlink-" + target))
    assert path.stat().st_nlink == 2
    with pytest.raises(phase.RepositoryHttpClientPinError):
        pin.check()


@pytest.mark.parametrize("part", ["inode", "owner", "parent-chain"])
def test_endpoint_identity_fact_drift_is_refused(files, part):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    if part == "parent-chain":
        files.endpoint["parent_chain_sha256"] = "b" * 64
    else:
        files.endpoint["socket_identity"][1 if part == "inode" else 3] += 1
    with pytest.raises(
        phase.RepositoryHttpClientPinError, match="client-config-or-endpoint-changed"
    ):
        pin.check()
    assert len(files.observations) == 2


def test_original_deadline_failure_prevents_new_file_or_endpoint_observation(files, monkeypatch):
    now, deadline = [100.0], 101.0

    def tick():
        if now[0] >= deadline:
            raise phase.RepositoryHttpClientPinError("original-phase-or-cleanup-deadline-expired")

    pin = phase.RepositoryHttpClientPin(files.profile, tick)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Expired original timer must block further identity reads")

    monkeypatch.setattr(phase, "_digest", forbidden)
    monkeypatch.setattr(phase, "_endpoint_identity", forbidden)
    now[0] = deadline
    with pytest.raises(
        phase.RepositoryHttpClientPinError, match="original-phase-or-cleanup-deadline-expired"
    ):
        pin.check()
    with pytest.raises(
        phase.RepositoryHttpClientPinError, match="original-phase-or-cleanup-deadline-expired"
    ):
        phase.RepositoryHttpClientPin(files.profile, tick)


def test_deadline_failure_mid_hash_closes_the_opened_file_and_stops_before_endpoint(
    files, monkeypatch
):
    actual_open, actual_fstat = os.open, os.fstat
    opened, ticks = [], []

    def tracked(*args, **kwargs):
        descriptor = actual_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def tick():
        ticks.append(None)
        if opened:
            raise phase.RepositoryHttpClientPinError("original-phase-or-cleanup-deadline-expired")

    monkeypatch.setattr(phase.os, "open", tracked)
    with pytest.raises(
        phase.RepositoryHttpClientPinError, match="original-phase-or-cleanup-deadline-expired"
    ):
        phase.RepositoryHttpClientPin(files.profile, tick)
    assert len(opened) == 1 and not files.observations
    with pytest.raises(OSError):
        actual_fstat(opened[0])


def test_review_is_detached_current_file_data_without_runtime_claims(files):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    report = pin.review_dict()
    assert report["schema_version"] == "2.0"
    assert report["kind"] == "repository-http-client-file-review"
    assert report["profile_id"] == files.profile.profile_id
    assert report["file_observations"]["endpoint"] == files.endpoint
    for key in (
        "engine_contact_attempted",
        "runtime_invoked",
        "execution_authorized",
        "resource_enforcement_established",
        "isolation_established",
        "verified_fix",
    ):
        assert report[key] is False
    assert report["authorization_status"] == "unknown"
    report["file_observations"]["endpoint"]["parent_chain_sha256"] = "b" * 64
    assert pin.review_dict()["file_observations"]["endpoint"] == files.endpoint
    report["file_observations"]["client"][0] = -1
    assert pin.identity["client"][0] >= 0


@pytest.mark.parametrize("value", [None, {}, "{}", SimpleNamespace(payload_json="{}")])
def test_only_exact_http_profile_can_start_file_comparison(files, monkeypatch, value):
    def forbidden(*args, **kwargs):
        pytest.fail("Wrong profile type must refuse before I/O")

    monkeypatch.setattr(os, "lstat", forbidden)
    with pytest.raises(phase.RepositoryHttpClientPinError, match="profile-type-invalid"):
        phase.RepositoryHttpClientPin(value, files.tick)


def test_legacy_profile_type_is_not_adopted(files):
    from authzest.runner._generated_repair_runtime_profile import RuntimeProfile

    with pytest.raises(phase.RepositoryHttpClientPinError, match="profile-type-invalid"):
        phase.RepositoryHttpClientPin(RuntimeProfile(files.profile.payload_json), files.tick)


@pytest.mark.parametrize("operation", [copy.copy, copy.deepcopy, pickle.dumps])
def test_pin_cannot_be_copied_or_serialized(files, operation):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    with pytest.raises(TypeError):
        operation(pin)
    pin.check()


@pytest.mark.parametrize("owner", ["process", "thread"])
def test_foreign_owner_refuses_before_additional_io(files, monkeypatch, owner):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    ticks, observations = len(files.ticks), len(files.observations)
    with monkeypatch.context() as patch:
        if owner == "process":
            patch.setattr(phase.os, "getpid", lambda: pin._pid + 1)
        else:
            patch.setattr(phase.threading, "get_ident", lambda: pin._thread + 1)
        with pytest.raises(phase.RepositoryHttpClientPinError, match="owner-unavailable"):
            pin.check()
    assert len(files.ticks) == ticks and len(files.observations) == observations
    pin.check()


def test_suppressed_reentry_refuses_outer_check_and_stays_failed(files):
    pin, armed = None, False

    def tick():
        if armed:
            with pytest.raises(phase.RepositoryHttpClientPinError, match="pin-unavailable"):
                pin.check()

    pin = phase.RepositoryHttpClientPin(files.profile, tick)
    armed = True
    with pytest.raises(phase.RepositoryHttpClientPinError, match="pin-unavailable"):
        pin.check()
    with pytest.raises(phase.RepositoryHttpClientPinError, match="pin-unavailable"):
        pin.check()


@pytest.mark.parametrize("part", ["executable_sha256", "images"])
def test_full_profile_declaration_change_invalidates_the_existing_pin(files, part):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    data = files.profile.to_dict()
    if part == "images":
        data["images"]["A"]["image_id"] = "sha256:" + "b" * 64
    else:
        data["engine"][part] = "a" * 64
    pin._profile = RepositoryHttpRuntimeProfile(canonical(data))
    with pytest.raises(phase.RepositoryHttpClientPinError, match="profile-changed"):
        pin.check()


def test_current_client_parent_identity_is_bound_even_when_mode_and_bytes_match(files):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    previous = files.root / "retained-client-parent"
    files.binary_parent.rename(previous)
    files.binary_parent.mkdir(mode=0o700)
    files.binary.write_bytes(CLIENT)
    files.binary.chmod(0o500)
    with pytest.raises(phase.RepositoryHttpClientPinError, match="changed"):
        pin.check()


@pytest.mark.parametrize("change", ["config-bytes", "config-extra", "client-mode"])
def test_changes_during_endpoint_name_inspection_are_refused(files, monkeypatch, change):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)

    def endpoint(_path):
        if change == "config-bytes":
            files.config.write_bytes(b"[]\n")
        elif change == "config-extra":
            (files.config_dir / "extra").write_bytes(b"not a credential")
        else:
            files.binary.chmod(0o700)
        return copy.deepcopy(files.endpoint)

    monkeypatch.setattr(phase, "_endpoint_identity", endpoint)
    with pytest.raises(phase.RepositoryHttpClientPinError, match="changed"):
        pin.check()


def test_ordinary_os_failures_are_redacted_and_disable_reuse(files):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    files.binary.unlink()
    with pytest.raises(phase.RepositoryHttpClientPinError) as caught:
        pin.check()
    assert str(files.binary) not in str(caught.value)
    with pytest.raises(phase.RepositoryHttpClientPinError, match="pin-unavailable"):
        pin.check()


def test_close_uncertainty_is_reported_without_retrying_a_consumed_descriptor(files, monkeypatch):
    actual_close, closed = os.close, []

    def uncertain(fd):
        actual_close(fd)
        closed.append(fd)
        raise OSError("simulated consumed descriptor close uncertainty")

    monkeypatch.setattr(os, "close", uncertain)
    with pytest.raises(phase.RepositoryHttpClientPinError) as caught:
        phase.RepositoryHttpClientPin(files.profile, files.tick)
    assert caught.value.descriptor_cleanup_confirmed is False
    assert len(closed) == 1
    with pytest.raises(OSError):
        os.fstat(closed[0])
    assert not files.observations


def test_keyboard_interrupt_during_hash_keeps_cleanup_evidence(files, monkeypatch):
    actual_open, opened = os.open, []

    def tracked(*args, **kwargs):
        fd = actual_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "open", tracked)
    monkeypatch.setattr(os, "read", interrupted)
    with pytest.raises(KeyboardInterrupt) as caught:
        phase.RepositoryHttpClientPin(files.profile, files.tick)
    assert caught.value.http_client_descriptor_cleanup_confirmed is True
    assert len(opened) == 1 and not files.observations
    with pytest.raises(OSError):
        os.fstat(opened[0])


@pytest.mark.parametrize("kind", ["async", "generator", "return-value"])
def test_deadline_check_must_be_synchronous_and_confirmed(files, kind):
    async def asynchronous():
        pass

    def generator():
        yield None

    hook = {"async": asynchronous, "generator": generator, "return-value": lambda: True}[kind]
    with pytest.raises(phase.RepositoryHttpClientPinError, match="deadline-check"):
        phase.RepositoryHttpClientPin(files.profile, hook)


@pytest.mark.parametrize("mutation", ["replacement", "reflection", "wrong-type"])
@pytest.mark.parametrize("operation", ["check", "review_dict"])
def test_final_deadline_hook_cannot_relabel_old_observations_with_a_new_profile(
    files, mutation, operation
):
    pin = phase.RepositoryHttpClientPin(files.profile, files.tick)
    before = len(files.ticks)
    pin.check()
    ticks_per_check = len(files.ticks) - before
    original_observations = pin._identity_json
    data = files.profile.to_dict()
    data["images"]["A"]["image_id"] = "sha256:" + "b" * 64
    replacement = validate_runtime_profile(canonical(data))
    calls = 0

    def mutate_at_last_tick():
        nonlocal calls
        calls += 1
        if calls == ticks_per_check:
            if mutation == "replacement":
                pin._profile = replacement
            elif mutation == "reflection":
                object.__setattr__(pin._profile, "payload_json", replacement.payload_json)
            else:
                pin._profile = replacement.to_dict()

    pin._tick_hook = mutate_at_last_tick
    with pytest.raises(phase.RepositoryHttpClientPinError, match="profile"):
        getattr(pin, operation)()
    assert calls == ticks_per_check
    assert pin._identity_json == original_observations
    with pytest.raises(phase.RepositoryHttpClientPinError, match="pin-unavailable"):
        pin.check()
