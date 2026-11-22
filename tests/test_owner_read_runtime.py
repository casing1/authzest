"""Private inert runtime files and supplied metadata, with no process or socket calls."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import stat
import subprocess
from types import SimpleNamespace

import pytest

from authzest.runner import _owner_read_runtime as runtime
from test_generated_repair_container_inspect import example

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX owner-read runtime workflow")


@pytest.fixture(autouse=True)
def no_execution_or_connections(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Runtime input and comparisons must remain local data-only operations")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def profile_file(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    client = tmp_path / "docker"
    client.write_bytes(b"A fixed inert client fixture.\n")
    client.chmod(0o700)
    endpoint = tmp_path / "runtime.sock"
    endpoint.write_bytes(b"Inert endpoint metadata fixture.\n")
    endpoint.chmod(0o700)
    original = os.stat
    socket_mode = [stat.S_IFSOCK | 0o700]

    def supplied_socket_stat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if str(path) not in {str(endpoint), endpoint.name}:
            return info
        fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        fields["st_mode"] = socket_mode[0]
        return SimpleNamespace(**fields)

    monkeypatch.setattr(runtime.os, "stat", supplied_socket_stat)
    data = {
        "schema_version": "1.0",
        "docker_executable": str(client),
        "docker_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
        "endpoint": "unix://" + str(endpoint),
        "daemon_id": "reviewed-local-daemon",
        "image_id": "sha256:" + "a" * 64,
        "platform": "linux/arm64",
    }
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path, data, client, endpoint, socket_mode


def _write(path, data):
    path.write_text(json.dumps(data))
    path.chmod(0o600)


def test_readonly_profile_capture_pins_client_socket_and_detaches_review(profile_file):
    path, data, *_ = profile_file
    initial = set(path.parent.iterdir())
    with runtime.OwnerReadRuntime(path) as loaded:
        assert loaded.to_dict() == data
        assert set(path.parent.iterdir()) == initial
        assert loaded.check() is None
        review = loaded.review_dict()
        assert review["profile"] == data
        assert review["image_trust"] == "operator-reviewed-preprovisioned-local-image"
        assert review["metadata_is_image_provenance"] is False
        review["profile"]["image_id"] = "changed detached copy"
        assert loaded.to_dict() == data
        descriptors = [pin.fd for pin in loaded._pins if pin.fd >= 0]
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    with pytest.raises(runtime.OwnerReadRuntimeError, match="closed"):
        loaded.check()
    loaded.close()


def test_environment_uses_dispatcher_private_empty_config_and_no_inherited_credentials(
    profile_file, monkeypatch
):
    path, data, *_ = profile_file
    parent = path.parent / "phase"
    parent.mkdir(mode=0o700)
    directory = parent / "config"
    directory.mkdir(mode=0o700)
    config = directory / "config.json"
    config.write_bytes(b"{}\n")
    config.chmod(0o600)
    monkeypatch.setenv("DOCKER_CONTEXT", "untrusted-context")
    monkeypatch.setenv("DOCKER_CONFIG", "/credential-directory")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-secret")
    with runtime.OwnerReadRuntime(path) as loaded:
        assert loaded.environment(directory) == {
            "HOME": str(parent),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "DOCKER_HOST": data["endpoint"],
            "DOCKER_CONFIG": str(directory),
        }
        config.write_bytes(b'{"auths":{}}')
        with pytest.raises(runtime.OwnerReadRuntimeError, match="empty-config"):
            loaded.environment(directory)
    assert directory.exists(), "Dispatcher owns its configuration cleanup"


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "2.0"),
        ("docker_sha256", "a" * 63),
        ("image_id", "repo:latest"),
        ("endpoint", "tcp://127.0.0.1:2375"),
        ("platform", "windows/amd64"),
        ("daemon_id", "contains whitespace"),
        ("docker_executable", "/tmp/../bin/docker"),
    ],
)
def test_invalid_declarations_are_refused(profile_file, field, value):
    path, data, *_ = profile_file
    data[field] = value
    _write(path, data)
    with pytest.raises((runtime.OwnerReadRuntimeError, OSError)):
        runtime.OwnerReadRuntime(path)


def test_config_requires_exact_fields_and_strict_duplicate_free_bounded_json(profile_file):
    path, data, *_ = profile_file
    for raw in (b'{"schema_version":"1.0","schema_version":"1.0"}', b"{" * 17000):
        path.write_bytes(raw)
        with pytest.raises((runtime.OwnerReadRuntimeError, OSError)):
            runtime.OwnerReadRuntime(path)
    data["extra"] = "arbitrary-config"
    _write(path, data)
    with pytest.raises(runtime.OwnerReadRuntimeError):
        runtime.OwnerReadRuntime(path)


@pytest.mark.parametrize("which", ["config", "client", "socket", "socket-permissions"])
def test_actual_file_or_socket_identity_changes_stop_rechecks(profile_file, which):
    path, _, client, endpoint, socket_mode = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        if which == "socket-permissions":
            socket_mode[0] = stat.S_IFSOCK | 0o777
        else:
            changed = {"config": path, "client": client, "socket": endpoint}[which]
            mode = changed.stat().st_mode & 0o777
            replacement = changed.with_suffix(".replacement")
            replacement.write_bytes(changed.read_bytes())
            replacement.chmod(mode)
            replacement.replace(changed)
        with pytest.raises((runtime.OwnerReadRuntimeError, OSError)):
            loaded.check()


@pytest.mark.parametrize("mode", [0o644, 0o666, 0o400])
def test_profile_must_be_private_and_writable_by_owner_only(profile_file, mode):
    path, *_ = profile_file
    path.chmod(mode)
    with pytest.raises(runtime.OwnerReadRuntimeError):
        runtime.OwnerReadRuntime(path)


def test_symlink_and_hardlink_profile_refused(profile_file):
    path, *_ = profile_file
    link = path.with_name("link.json")
    link.symlink_to(path)
    with pytest.raises((runtime.OwnerReadRuntimeError, OSError)):
        runtime.OwnerReadRuntime(link)
    link.unlink()
    os.link(path, link)
    with pytest.raises(runtime.OwnerReadRuntimeError):
        runtime.OwnerReadRuntime(path)


def test_changed_client_digest_refuses_initial_capture(profile_file):
    path, _, client, *_ = profile_file
    client.write_bytes(b"Changed inert client.")
    with pytest.raises(runtime.OwnerReadRuntimeError, match="digest-mismatch"):
        runtime.OwnerReadRuntime(path)


def _image(loaded):
    return {
        "Id": loaded.image_id,
        "Os": "linux",
        "Architecture": "arm64",
        "Config": {
            "User": "65532:65532",
            "WorkingDir": "/tmp",
            "Entrypoint": runtime.ENTRYPOINT[:],
            "Cmd": [],
            "Env": runtime.IMAGE_ENVIRONMENT[:],
            "Volumes": None,
            "Healthcheck": None,
            "OnBuild": None,
            "Labels": {"reviewed": "image"},
        },
    }


def _daemon(loaded):
    return {
        "ID": loaded.daemon_id,
        "OSType": "linux",
        "Architecture": "aarch64",
        "CgroupVersion": "2",
        "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns"],
        "MemoryLimit": True,
        "SwapLimit": True,
        "PidsLimit": True,
        "CpuCfsPeriod": True,
        "CpuCfsQuota": True,
    }


def test_pure_daemon_and_image_comparison_is_not_provenance(profile_file):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        assert runtime.validate_daemon(_daemon(loaded), loaded) is None
        assert runtime.validate_image(_image(loaded), loaded) is None
        image = _image(loaded)
        image["Config"]["Labels"] = None
        assert runtime.validate_image(image, loaded) is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("ID", "different-daemon"),
        ("OSType", "windows"),
        ("CgroupVersion", "1"),
        ("Architecture", "amd64"),
        ("MemoryLimit", False),
        ("SwapLimit", 1),
        ("SecurityOptions", ["name=seccomp,profile=unconfined"]),
        ("SecurityOptions", ["name=seccomp,profile=builtin", "name=rootless"]),
    ],
)
def test_daemon_drift_or_missing_enforcement_refused(profile_file, key, value):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        info = _daemon(loaded)
        info[key] = value
        with pytest.raises(runtime.OwnerReadRuntimeError):
            runtime.validate_daemon(info, loaded)


@pytest.mark.parametrize(
    "key,value",
    [
        ("User", "0:0"),
        ("WorkingDir", "/"),
        ("Entrypoint", ["/bin/sh"]),
        ("Env", runtime.IMAGE_ENVIRONMENT + ["SECRET=inherited"]),
        ("Volumes", {"/secrets": {}}),
        ("Healthcheck", {"Test": ["CMD", "touch"]}),
        ("OnBuild", ["RUN arbitrary"]),
    ],
)
def test_unexpected_image_configuration_refused(profile_file, key, value):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        info = _image(loaded)
        info["Config"][key] = value
        with pytest.raises(runtime.OwnerReadRuntimeError):
            runtime.validate_image(info, loaded)


def _created(loaded, role):
    _, value = example()
    image = _image(loaded)
    labels = {"org.authzest.owner-read.session": "f" * 32, "org.authzest.owner-read.role": role}
    mounts = {
        "/reviewed/availability.py": "/input/availability.py",
        "/reviewed/test_owner_archived_read.py": "/input/test_owner_archived_read.py",
    }
    value.update(
        Name="/owned-owner-read", Image=loaded.image_id, Args=runtime.ENTRYPOINT[1:] + [role]
    )
    value["Config"].update(
        Image=loaded.image_id,
        Entrypoint=runtime.ENTRYPOINT[:],
        Cmd=[role],
        Env=runtime.IMAGE_ENVIRONMENT[:],
        OpenStdin=True,
        AttachStdin=True,
        StdinOnce=True,
        Labels={**image["Config"]["Labels"], **labels},
    )
    value["HostConfig"]["Mounts"] = [
        {
            "Type": "bind",
            "Source": source,
            "Target": target,
            "ReadOnly": True,
            "BindOptions": {"Propagation": "rprivate"},
        }
        for source, target in mounts.items()
    ]
    value["Mounts"] = [
        {
            "Type": "bind",
            "Source": source,
            "Destination": target,
            "RW": False,
            "Propagation": "rprivate",
            "Mode": "",
        }
        for source, target in mounts.items()
    ]
    return value, {
        "container_id": value["Id"],
        "name": "owned-owner-read",
        "labels": labels,
        "role": role,
        "mounts": mounts,
        "image_info": image,
    }


@pytest.mark.parametrize("role", ["test", "controls"])
def test_created_container_matches_fixed_effective_controls(profile_file, role):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        value, arguments = _created(loaded, role)
        original = copy.deepcopy(value)
        assert runtime.validate_created_container(value, loaded, **arguments) is None
        assert value == original


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("HostConfig", "Privileged", True),
        ("HostConfig", "NetworkMode", "host"),
        ("HostConfig", "ReadonlyRootfs", False),
        ("HostConfig", "Memory", True),
        ("HostConfig", "SecurityOpt", ["seccomp=unconfined"]),
        ("Config", "User", "0:0"),
        ("Config", "Env", runtime.IMAGE_ENVIRONMENT + ["SECRET=bad"]),
    ],
)
def test_effective_control_drift_refuses_start(profile_file, section, key, value):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        info, arguments = _created(loaded, "test")
        info[section][key] = value
        with pytest.raises(runtime.OwnerReadRuntimeError):
            runtime.validate_created_container(info, loaded, **arguments)


def test_unexpected_mount_or_source_refused(profile_file):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        info, arguments = _created(loaded, "test")
        info["Mounts"][0]["RW"] = True
        with pytest.raises(runtime.OwnerReadRuntimeError):
            runtime.validate_created_container(info, loaded, **arguments)


def test_daemon_cpu_control_fields_use_actual_cli_info_spelling(profile_file):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        actual = _daemon(loaded)
        assert runtime.validate_daemon(actual, loaded) is None
        for field in ("CpuCfsPeriod", "CpuCfsQuota"):
            wrong_case = dict(actual)
            wrong_case["CPU" + field[3:]] = wrong_case.pop(field)
            with pytest.raises(runtime.OwnerReadRuntimeError):
                runtime.validate_daemon(wrong_case, loaded)


def test_created_container_requires_single_stdin_attachment(profile_file):
    path, *_ = profile_file
    with runtime.OwnerReadRuntime(path) as loaded:
        info, arguments = _created(loaded, "test")
        assert info["Config"]["StdinOnce"] is True
        assert runtime.validate_created_container(info, loaded, **arguments) is None
        info["Config"]["StdinOnce"] = False
        with pytest.raises(runtime.OwnerReadRuntimeError):
            runtime.validate_created_container(info, loaded, **arguments)
