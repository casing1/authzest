"""Private operator-reviewed Docker input and pure owner-read metadata comparisons.

A pinned local image ID is an operator trust boundary. These declarations and
metadata comparisons do not establish image provenance or effective kernel
isolation. The fixed guest checks its effective controls before loading inputs.
This module starts no process and makes no socket connection.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.runner._generated_repair_container_inspect import _host, _network, _state

MAX_CONFIG_BYTES = 16_384
ENTRYPOINT = ["/usr/local/bin/python", "-I", "-B", "/opt/authzest-owner/guest.py"]
IMAGE_ENVIRONMENT = [
    "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG=C.UTF-8",
    "GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305",
    "PYTHON_VERSION=3.12.16",
    "PYTHON_SHA256=b5796915dc45ff745cfb4e990a7e7c93d6f546328a102ce31448d69ebc37575c",
]
_FIELDS = {
    "schema_version",
    "docker_executable",
    "docker_sha256",
    "endpoint",
    "daemon_id",
    "image_id",
    "platform",
}
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class OwnerReadRuntimeError(ValueError):
    """A redacted runtime declaration, local identity or supplied metadata failed."""


def _fail(reason):
    raise OwnerReadRuntimeError(reason)


def _identity(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _path(value):
    if isinstance(value, Path):
        value = str(value)
    if (
        type(value) is not str
        or not value.startswith("/")
        or len(value.encode("utf-8")) > 512
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or any(part in (".", "..") for part in value.split("/"))
        or len(Path(value).parts) > 33
    ):
        _fail("runtime-path-invalid")
    return Path(value)


def _directory(info):
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o022
        and not info.st_mode & stat.S_ISVTX
    ):
        _fail("runtime-parent-unavailable")
    return _identity(info)[:5]


class _PinnedPath:
    def __init__(self, path, kind):
        self.path, self.kind = _path(path), kind
        self.parents = []
        self.fd = -1
        try:
            current = Path("/")
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            fd = os.open(current, flags)
            self.parents.append((current, fd, None))
            self.parents[-1] = (current, fd, _directory(os.fstat(fd)))
            for part in self.path.parts[1:-1]:
                current = current / part
                fd = os.open(part, flags, dir_fd=self.parents[-1][1])
                self.parents.append((current, fd, None))
                self.parents[-1] = (current, fd, _directory(os.fstat(fd)))
            info = os.stat(self.path.name, dir_fd=self.parents[-1][1], follow_symlinks=False)
            if kind != "socket":
                self.fd = os.open(
                    self.path.name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=self.parents[-1][1],
                )
                if _identity(os.fstat(self.fd)) != _identity(info):
                    _fail("runtime-file-changed")
            self.identity = self._validate(info)
            self.raw = self._read() if kind == "config" else None
            self.sha256 = self._digest() if kind != "socket" else None
            self.check()
        except BaseException:
            self.close()
            raise

    def _validate(self, info):
        if self.kind == "socket":
            if (
                not stat.S_ISSOCK(info.st_mode)
                or info.st_uid not in {0, os.geteuid()}
                or info.st_mode & 0o022
            ):
                _fail("runtime-private-local-socket-required")
        elif (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid not in {0, os.geteuid()}
            or info.st_mode & 0o022
            or not 0 < info.st_size <= (MAX_CONFIG_BYTES if self.kind == "config" else 134_217_728)
        ):
            _fail("runtime-regular-file-required")
        elif self.kind == "config" and (
            info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600
        ):
            _fail("runtime-private-config-required")
        elif self.kind == "client" and not info.st_mode & 0o111:
            _fail("runtime-client-not-executable")
        return _identity(info)

    def _read(self):
        data = bytearray()
        maximum = MAX_CONFIG_BYTES if self.kind == "config" else 134_217_728
        while len(data) <= maximum:
            chunk = os.pread(self.fd, min(65_536, maximum + 1 - len(data)), len(data))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > maximum:
            _fail("runtime-file-budget")
        return bytes(data)

    def _digest(self):
        digest = hashlib.sha256()
        offset = 0
        maximum = MAX_CONFIG_BYTES if self.kind == "config" else 134_217_728
        while offset <= maximum:
            chunk = os.pread(self.fd, min(65_536, maximum + 1 - offset), offset)
            if not chunk:
                break
            digest.update(chunk)
            offset += len(chunk)
        if offset > maximum:
            _fail("runtime-file-budget")
        return digest.hexdigest()

    def check(self):
        if not self.parents:
            _fail("runtime-input-closed")
        for path, fd, expected in self.parents:
            if _directory(os.fstat(fd)) != expected or _directory(os.lstat(path)) != expected:
                _fail("runtime-parent-changed")
        info = os.stat(self.path.name, dir_fd=self.parents[-1][1], follow_symlinks=False)
        if self._validate(info) != self.identity:
            _fail("runtime-file-changed")
        if self.fd >= 0 and (
            self._validate(os.fstat(self.fd)) != self.identity
            or self._digest() != self.sha256
            or self.kind == "config"
            and self._read() != self.raw
        ):
            _fail("runtime-file-changed")
        if (
            self._validate(
                os.stat(self.path.name, dir_fd=self.parents[-1][1], follow_symlinks=False)
            )
            != self.identity
        ):
            _fail("runtime-file-changed")
        if self.fd >= 0 and self._validate(os.fstat(self.fd)) != self.identity:
            _fail("runtime-file-changed")

    def close(self):
        failure = None
        descriptors = [self.fd, *(fd for _, fd, _ in self.parents)]
        self.fd, self.parents = -1, []
        for fd in descriptors:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError as exc:
                    failure = exc
        if failure is not None:
            raise failure


def _declaration(raw):
    try:
        value = decode(raw.decode("utf-8"))
    except (ContractError, UnicodeError) as exc:
        raise OwnerReadRuntimeError("runtime-config-invalid") from exc
    if value.keys() != _FIELDS or value["schema_version"] != "1.0":
        _fail("runtime-config-invalid")
    _path(value["docker_executable"])
    if type(value["docker_sha256"]) is not str or not _DIGEST.fullmatch(value["docker_sha256"]):
        _fail("runtime-config-invalid")
    endpoint = value["endpoint"]
    if type(endpoint) is not str or not endpoint.startswith("unix://"):
        _fail("runtime-local-endpoint-required")
    _path(endpoint[7:])
    if (
        type(value["image_id"]) is not str
        or not value["image_id"].startswith("sha256:")
        or not _DIGEST.fullmatch(value["image_id"][7:])
        or type(value["platform"]) is not str
        or value["platform"] not in {"linux/amd64", "linux/arm64"}
        or type(value["daemon_id"]) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,127}", value["daemon_id"]) is None
    ):
        _fail("runtime-config-invalid")
    return value


class OwnerReadRuntime:
    """Hold one private config and local client/socket pins through a trusted invocation.

    The operator provisions and reviews the locally present image before choosing
    its immutable ID. Same-account concurrent writers must be excluded. Local file
    checks do not authenticate the daemon or the supplied image's build history.
    """

    def __init__(self, path):
        self._pins = []
        self._closed = False
        try:
            if os.name != "posix" or getattr(sys, "frozen", False) or not hasattr(os, "pread"):
                _fail("runtime-platform-unsupported")
            self._config = self._pin(path, "config")
            self._data = _declaration(self._config.raw)
            self._client = self._pin(self.docker, "client")
            if self._client.sha256 != self._data["docker_sha256"]:
                _fail("runtime-client-digest-mismatch")
            self._socket = self._pin(self.endpoint[7:], "socket")
            self.check()
        except BaseException as exc:
            try:
                self.close()
                exc.runtime_descriptor_cleanup_confirmed = True
            except BaseException:
                exc.runtime_descriptor_cleanup_confirmed = False
            raise

    def _pin(self, path, kind):
        pin = _PinnedPath(path, kind)
        self._pins.append(pin)
        return pin

    @property
    def docker(self):
        return self._data["docker_executable"]

    @property
    def image_id(self):
        return self._data["image_id"]

    @property
    def platform(self):
        return self._data["platform"]

    @property
    def daemon_id(self):
        return self._data["daemon_id"]

    @property
    def endpoint(self):
        return self._data["endpoint"]

    def to_dict(self):
        return decode(canonical(self._data))

    def review_dict(self):
        return {
            "kind": "owner-read-runtime-review",
            "schema_version": "1.0",
            "runtime_id": "owner-read-runtime-" + identity(self.to_dict()),
            "profile": self.to_dict(),
            "config_file_sha256": self._config.sha256,
            "config_file_identity": list(self._config.identity),
            "client_identity": list(self._client.identity),
            "socket_identity": list(self._socket.identity),
            "image_trust": "operator-reviewed-preprovisioned-local-image",
            "metadata_is_image_provenance": False,
        }

    def check(self):
        if self._closed:
            _fail("runtime-input-closed")
        for pin in self._pins:
            pin.check()

    def environment(self, config_dir):
        """Validate one dispatcher-owned empty config before constructing a clean environment."""
        self.check()
        directory = _path(config_dir)
        parent = directory.parent
        for path in (parent, directory):
            info = os.stat(path, follow_symlinks=False)
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700
            ):
                _fail("runtime-private-client-directory-required")
        if set(os.listdir(directory)) != {"config.json"}:
            _fail("runtime-empty-config-required")
        pin = _PinnedPath(directory / "config.json", "config")
        try:
            if pin.raw != b"{}\n":
                _fail("runtime-empty-config-required")
            pin.check()
            return {
                "HOME": str(parent),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "DOCKER_HOST": self.endpoint,
                "DOCKER_CONFIG": str(directory),
            }
        finally:
            pin.close()

    def close(self):
        self._closed = True
        failure = None
        for pin in reversed(self._pins):
            try:
                pin.close()
            except OSError as exc:
                failure = exc
        self._pins = []
        if failure is not None:
            raise failure

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *_):
        self.close()


def validate_daemon(info, runtime):
    """Compare a supplied daemon report with the operator's local pin."""
    if (
        type(info) is not dict
        or info.get("ID") != runtime.daemon_id
        or info.get("OSType") != "linux"
        or info.get("CgroupVersion") != "2"
        or type(info.get("Architecture")) is not str
        or info.get("Architecture")
        not in ({"aarch64", "arm64"} if runtime.platform == "linux/arm64" else {"x86_64", "amd64"})
        or type(info.get("SecurityOptions")) is not list
        or len(info["SecurityOptions"]) > 32
        or "name=seccomp,profile=builtin" not in info["SecurityOptions"]
        or any(
            type(item) is not str
            or item
            not in {
                "name=seccomp,profile=builtin",
                "name=cgroupns",
                "name=apparmor",
                "name=selinux",
            }
            for item in info["SecurityOptions"]
        )
        or any(
            info.get(name) is not True
            for name in ("MemoryLimit", "SwapLimit", "PidsLimit", "CpuCfsPeriod", "CpuCfsQuota")
        )
    ):
        _fail("runtime-daemon-mismatch")


def validate_image(info, runtime):
    """Check supplied metadata for the exact preprovisioned image the operator reviewed."""
    if type(info) is not dict or type(info.get("Config")) is not dict:
        _fail("runtime-image-mismatch")
    config = info["Config"]
    if (
        info.get("Id") != runtime.image_id
        or info.get("Os") != "linux"
        or info.get("Architecture") != runtime.platform.split("/")[1]
        or config.get("User") != "65532:65532"
        or config.get("WorkingDir") != "/tmp"
        or config.get("Entrypoint") != ENTRYPOINT
        or config.get("Cmd") not in (None, [])
        or config.get("Env") != IMAGE_ENVIRONMENT
        or config.get("Volumes") not in (None, {})
        or config.get("Healthcheck") not in (None, {})
        or config.get("OnBuild") not in (None, [])
        or config.get("ExposedPorts") not in (None, {})
        or config.get("Labels") is not None
        and (
            type(config["Labels"]) is not dict
            or len(config["Labels"]) > 32
            or any(
                type(key) is not str
                or len(key) > 256
                or type(value) is not str
                or len(value) > 1024
                for key, value in config["Labels"].items()
            )
        )
    ):
        _fail("runtime-image-mismatch")


def validate_created_container(
    info, runtime, *, container_id, name, labels, role, mounts, image_info
):
    """Compare a stopped guest's effective Docker report with the two fixed input mounts."""
    validate_image(image_info, runtime)
    expected_labels = {**(image_info["Config"].get("Labels") or {}), **labels}
    if (
        type(info) is not dict
        or role not in {"test", "controls"}
        or type(container_id) is not str
        or not _DIGEST.fullmatch(container_id)
        or info.get("Id") != container_id
        or info.get("Name") != "/" + name
        or info.get("Image") != runtime.image_id
        or info.get("Path") != ENTRYPOINT[0]
        or info.get("Args") != ENTRYPOINT[1:] + [role]
        or info.get("Platform") != "linux"
        or type(info.get("RestartCount")) is not int
        or info["RestartCount"] != 0
    ):
        _fail("runtime-created-container-mismatch")
    try:
        _state(info["State"])
        config = info["Config"]
        if (
            config["Image"] != runtime.image_id
            or config["Labels"] != expected_labels
            or config["User"] != "65532:65532"
            or config["WorkingDir"] != "/tmp"
            or config["Entrypoint"] != ENTRYPOINT
            or config["Cmd"] != [role]
            or config["Env"] != IMAGE_ENVIRONMENT
            or config.get("Volumes") not in (None, {})
            or config.get("ExposedPorts") not in (None, {})
            or config.get("OnBuild") not in (None, [])
            or config.get("Healthcheck") != {"Test": ["NONE"]}
            or any(
                config.get(key) is not True
                for key in ("OpenStdin", "AttachStdin", "AttachStdout", "AttachStderr")
            )
            or config.get("Tty") is not False
            or config.get("StdinOnce") is not True
        ):
            _fail("runtime-created-container-mismatch")
        if (
            type(mounts) is not dict
            or set(mounts.values())
            != {"/input/availability.py", "/input/test_owner_archived_read.py"}
            or len(mounts) != 2
        ):
            _fail("runtime-created-container-mismatch")
        if type(info["Mounts"]) is not list or len(info["Mounts"]) != 2:
            _fail("runtime-created-container-mismatch")
        resolved = []
        for row in info["Mounts"]:
            normalized = dict(row)
            for source in mounts:
                if sys.platform == "darwin" and normalized.get("Source") == "/host_mnt" + source:
                    normalized["Source"] = source
            resolved.append(normalized)
        declared = [{"source": source, "target": target} for source, target in mounts.items()]
        _host(info["HostConfig"], {"role": "T", "declared_files": declared}, resolved)
        _network(info["NetworkSettings"], False)
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        raise OwnerReadRuntimeError("runtime-created-container-mismatch") from exc
