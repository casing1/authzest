"""Real owned inert files and synthetic endpoint facts; never execute a client."""

from __future__ import annotations

import asyncio
import copy
import os
import socket
import stat
import subprocess
from hashlib import sha256
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _generated_repair_phase as phase
from authzest.runner._generated_repair_runtime_profile import validate_runtime_profile
from test_generated_repair_runtime_profile import profile_data

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
        assert path == "/reviewed/run/docker.sock"
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
    pin = phase._ClientPin(files.profile, files.tick)
    initial = copy.deepcopy(pin.identity)
    pin.check()
    assert pin.identity == initial
    assert len(files.observations) == 2 and len(opened) == 4
    assert len(files.ticks) >= 12
    assert files.binary.read_bytes() == CLIENT
    for descriptor in opened:
        with pytest.raises(OSError):
            actual_fstat(descriptor)


@pytest.mark.parametrize("replace_inode", [False, True], ids=["same-inode", "new-inode"])
@pytest.mark.parametrize("change_bytes", [False, True], ids=["same-bytes", "different-bytes"])
def test_client_byte_or_file_identity_changes_are_refused(files, replace_inode, change_bytes):
    pin = phase._ClientPin(files.profile, files.tick)
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
    with pytest.raises(phase.PhaseError):
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
    pin = phase._ClientPin(files.profile, files.tick)
    getattr(files, target).chmod(mode)
    with pytest.raises(phase.PhaseError):
        pin.check()


@pytest.mark.parametrize(
    "change", ["extra-file", "extra-directory", "different-bytes", "replacement"]
)
def test_empty_private_config_has_exact_membership_bytes_and_file_identity(files, change):
    pin = phase._ClientPin(files.profile, files.tick)
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
    with pytest.raises(phase.PhaseError):
        pin.check()


@pytest.mark.parametrize("target", ["binary", "config", "binary_parent", "config_parent"])
@pytest.mark.parametrize("initial", [False, True], ids=["changed-after-pin", "initial-alias"])
def test_file_and_parent_symlink_aliases_are_refused_even_with_matching_bytes(
    files, target, initial
):
    pin = None if initial else phase._ClientPin(files.profile, files.tick)
    path = getattr(files, target)
    original = files.root / ("retained-" + target)
    path.rename(original)
    path.symlink_to(original, target_is_directory=original.is_dir())
    assert path.is_symlink()
    with pytest.raises(phase.PhaseError):
        if initial:
            phase._ClientPin(files.profile, files.tick)
        else:
            pin.check()


@pytest.mark.parametrize("target", ["binary", "config"])
def test_single_link_inputs_cannot_gain_another_hardlink(files, target):
    pin = phase._ClientPin(files.profile, files.tick)
    path = getattr(files, target)
    os.link(path, files.root / ("hardlink-" + target))
    assert path.stat().st_nlink == 2
    with pytest.raises(phase.PhaseError):
        pin.check()


@pytest.mark.parametrize("part", ["inode", "owner", "parent-chain"])
def test_endpoint_identity_fact_drift_is_refused(files, part):
    pin = phase._ClientPin(files.profile, files.tick)
    if part == "parent-chain":
        files.endpoint["parent_chain_sha256"] = "b" * 64
    else:
        files.endpoint["socket_identity"][1 if part == "inode" else 3] += 1
    with pytest.raises(phase.PhaseError, match="client-config-or-endpoint-changed"):
        pin.check()
    assert len(files.observations) == 2


def test_original_deadline_failure_prevents_new_file_or_endpoint_observation(files, monkeypatch):
    now, deadline = [100.0], 101.0

    def tick():
        if now[0] >= deadline:
            raise phase.PhaseError("original-phase-or-cleanup-deadline-expired")

    pin = phase._ClientPin(files.profile, tick)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Expired original timer must block further identity reads")

    monkeypatch.setattr(phase, "_file_digest", forbidden)
    monkeypatch.setattr(phase, "_endpoint_identity", forbidden)
    now[0] = deadline
    with pytest.raises(phase.PhaseError, match="original-phase-or-cleanup-deadline-expired"):
        pin.check()
    with pytest.raises(phase.PhaseError, match="original-phase-or-cleanup-deadline-expired"):
        phase._ClientPin(files.profile, tick)


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
        if len(ticks) == 3:
            raise phase.PhaseError("original-phase-or-cleanup-deadline-expired")

    monkeypatch.setattr(phase.os, "open", tracked)
    with pytest.raises(phase.PhaseError, match="original-phase-or-cleanup-deadline-expired"):
        phase._ClientPin(files.profile, tick)
    assert len(opened) == 1 and not files.observations
    with pytest.raises(OSError):
        actual_fstat(opened[0])
