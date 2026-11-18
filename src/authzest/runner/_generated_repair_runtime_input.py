"""Bounded private profile-file input, never runtime readiness or consent.

The file is held through no-follow descriptors and rechecked before dispatch.
Its image/engine fields remain declarations: neither a matching file nor a caller
copy of this module's review JSON establishes image contents or kernel controls.
"""

from __future__ import annotations

import os
import stat
import sys
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import ContractError
from authzest.runner._generated_repair_runtime_profile import (
    MAX_PROFILE_BYTES,
    RuntimeProfile,
    validate_runtime_profile,
)

# Kept literal for an installed source package: loading a profile must not rely on
# a writable repository manifest. Source regressions compare these maintained
# bindings with both manifest platforms. Root updates recipes when assets change.
EXPECTED_IMAGE_INPUTS = {
    "linux/amd64": {
        "T": {
            "dependency_lock_sha256": (
                "8f87350f05c065015a9f2c7633aee604afc31c6d02cc96459b6fcd09520718fc"
            ),
            "recipe_sha256": "dca3e1e7f946036ca2cfcfd84ce9a328a47e6a0ef652f0f37adf1af35175a32d",
        },
        "A": {
            "dependency_lock_sha256": (
                "d5e47e336f638d33f90d8241f76ebe58cecb45d7e910ce9d7fe487efd8e636bb"
            ),
            "recipe_sha256": "d4fdf1be501e67bfa745866b80839f386c3df423049bf592d6f415b6226c501d",
        },
        "B": {
            "dependency_lock_sha256": (
                "15ede46cc460b1a15b005f8bc0dcf46515c6ee96242ee0a22617c7af89d4908e"
            ),
            "recipe_sha256": "b74ac75b61872b242de3468cf2bb557ee72e4a6acc6f76bd23d07a9cdbe3edb6",
        },
    },
    "linux/arm64": {
        "T": {
            "dependency_lock_sha256": (
                "e2a56894eeff0a0ef1433ec9eecf99e75339e52e92f9fe39ea9e015618f030cf"
            ),
            "recipe_sha256": "4df11eb391e89bb2fed9fc1b40bb69c675c720e390aba5c59a3423b760defc4a",
        },
        "A": {
            "dependency_lock_sha256": (
                "4fe83c082c5db3d478c0b40f39d626b3c687182d0c28efd818d5cffea93699b8"
            ),
            "recipe_sha256": "967c8e33fe2c21dcaf81a00dcb0f46e76d27f26c49c518bb4fcd0a41a233d8ed",
        },
        "B": {
            "dependency_lock_sha256": (
                "15ede46cc460b1a15b005f8bc0dcf46515c6ee96242ee0a22617c7af89d4908e"
            ),
            "recipe_sha256": "093ff1de9c111d46117677e437cc84f564dee8b758476117cb3002aee7a11d3d",
        },
    },
}
_OPEN_DIR_FD = os.open in os.supports_dir_fd
_STAT_DIR_FD = os.stat in os.supports_dir_fd
_STAT_NOFOLLOW = os.stat in os.supports_follow_symlinks


class GeneratedRuntimeInputError(ValueError):
    """A redacted profile input failure; no source/user path enters its message."""


def _fail(reason):
    raise GeneratedRuntimeInputError(reason)


def _supported():
    return (
        os.name == "posix"
        and not getattr(sys, "frozen", False)
        and all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
        and _OPEN_DIR_FD
        and _STAT_DIR_FD
        and _STAT_NOFOLLOW
        and hasattr(os, "pread")
    )


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


def _directory(info):
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o022
        and not info.st_mode & stat.S_ISVTX
    ):
        _fail("runtime-profile-parent-unavailable")
    return _identity(info)[:5]


def _file(info):
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or not 0 < info.st_size <= MAX_PROFILE_BYTES
    ):
        _fail("runtime-profile-private-file-required")
    return _identity(info)


def _path(path):
    if type(path) not in {str, Path, type(Path())}:
        _fail("runtime-profile-path-invalid")
    raw = str(path)
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError as exc:
        raise GeneratedRuntimeInputError("runtime-profile-path-invalid") from exc
    if (
        not encoded
        or len(encoded) > 512
        or any(ord(char) < 32 or ord(char) == 127 for char in raw)
        or ".." in raw.split("/")
    ):
        _fail("runtime-profile-path-invalid")
    value = Path(os.path.abspath(raw))
    if len(str(value).encode("utf-8")) > 512 or not 2 <= len(value.parts) <= 33:
        _fail("runtime-profile-path-invalid")
    return value


def _profile(raw):
    try:
        value = validate_runtime_profile(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ContractError, ValueError, TypeError) as exc:
        raise GeneratedRuntimeInputError("runtime-profile-declaration-invalid") from exc
    data = value.to_dict()
    for role, bindings in EXPECTED_IMAGE_INPUTS[data["platform"]].items():
        if any(data["images"][role][key] != expected for key, expected in bindings.items()):
            _fail("runtime-profile-maintained-input-drift")
    return value


class LoadedRuntimeProfile:
    """Observed private file and pinned data, not a live runtime capability.

    The operator and Python caller are trusted. Held descriptors and repeated
    checks detect ordinary edits/replacements; they are not atomic pathname CAS
    against a hostile same-user writer. Close retains the original file unchanged.
    """

    def __init__(self, path):
        self._closed = False
        self._cleanup_confirmed = True
        self._parents = []
        self._fd = -1
        self._profile = None
        self._raw = b""
        self._identity = None
        self._path = None
        try:
            if not _supported():
                _fail("runtime-profile-platform-unsupported")
            self._path = _path(path)
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            root_fd = os.open("/", flags)
            self._parents.append((Path("/"), root_fd, None))
            self._parents[0] = (Path("/"), root_fd, _directory(os.fstat(root_fd)))
            current = Path("/")
            for part in self._path.parts[1:-1]:
                parent_fd = self._parents[-1][1]
                current = current / part
                fd = os.open(part, flags, dir_fd=parent_fd)
                self._parents.append((current, fd, None))
                self._parents[-1] = (current, fd, _directory(os.fstat(fd)))
            self._fd = os.open(
                self._path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=self._parents[-1][1],
            )
            self._identity = _file(os.fstat(self._fd))
            self._raw = self._read()
            if len(self._raw) != self._identity[6]:
                _fail("runtime-profile-file-changed")
            self._profile = _profile(self._raw)
            self.assert_current()
        except BaseException as exc:
            self._failed(exc)

    def _failed(self, original):
        try:
            self.close()
        except BaseException as interrupted:
            self._cleanup_confirmed = False
            if not isinstance(interrupted, Exception) and isinstance(original, Exception):
                interrupted.runtime_profile_cleanup_confirmed = False
                raise
        if not isinstance(original, Exception):
            original.runtime_profile_cleanup_confirmed = self._cleanup_confirmed
            raise original
        if isinstance(original, GeneratedRuntimeInputError):
            original.descriptor_cleanup_confirmed = self._cleanup_confirmed
            raise original
        error = GeneratedRuntimeInputError("runtime-profile-file-unavailable")
        error.descriptor_cleanup_confirmed = self._cleanup_confirmed
        raise error from original

    def _read(self):
        if self._fd < 0:
            _fail("runtime-profile-input-closed")
        raw = bytearray()
        while True:
            chunk = os.pread(self._fd, min(4096, MAX_PROFILE_BYTES + 1 - len(raw)), len(raw))
            if type(chunk) is not bytes:
                _fail("runtime-profile-file-unavailable")
            raw.extend(chunk)
            if len(raw) > MAX_PROFILE_BYTES:
                _fail("runtime-profile-size-limit")
            if not chunk:
                return bytes(raw)

    @property
    def profile(self) -> RuntimeProfile:
        if self._closed or self._profile is None:
            _fail("runtime-profile-input-closed")
        return self._profile

    def assert_current(self) -> None:
        try:
            if self._closed or self._profile is None or not _supported():
                _fail("runtime-profile-input-closed")
            for path, fd, observed in self._parents:
                if _directory(os.fstat(fd)) != observed or _directory(os.lstat(path)) != observed:
                    _fail("runtime-profile-parent-changed")
            named = os.stat(self._path.name, dir_fd=self._parents[-1][1], follow_symlinks=False)
            if _file(named) != self._identity or _file(os.fstat(self._fd)) != self._identity:
                _fail("runtime-profile-file-changed")
            raw = self._read()
            checked = _profile(raw)
            if (
                raw != self._raw
                or len(raw) != self._identity[6]
                or _file(os.fstat(self._fd)) != self._identity
                or _file(
                    os.stat(self._path.name, dir_fd=self._parents[-1][1], follow_symlinks=False)
                )
                != self._identity
                or checked.payload_json != self._profile.payload_json
            ):
                _fail("runtime-profile-file-changed")
            # Check the full named parent path again after the bounded read.
            if any(_directory(os.lstat(path)) != observed for path, _, observed in self._parents):
                _fail("runtime-profile-parent-changed")
        except BaseException as exc:
            self._failed(exc)

    def review_dict(self) -> dict:
        self.assert_current()
        return {
            "schema_version": "1.0",
            "kind": "generated-repair-runtime-input-review",
            "status": "profile-file-captured-unverified-runtime",
            "profile_id": self.profile.profile_id,
            "profile": self.profile.to_dict(),
            "profile_path": str(self._path),
            "profile_file": {
                "sha256": sha256(self._raw).hexdigest(),
                "identity": list(self._identity),
                "size": len(self._raw),
                "parents": [
                    {"path": str(path), "identity": list(observed)}
                    for path, _, observed in self._parents
                ],
            },
            "execution_authorized": False,
            "resource_enforcement_established": False,
            "isolation_established": False,
            "limitations": [
                "The profile file is observed; declared client/daemon/image contents "
                "are not attested.",
                "Current image contents and per-entry kernel controls require "
                "separate verification.",
                "This review is data, not a reusable decision, runtime receipt "
                "or session resume token.",
                "Exclude hostile same-user writers; pathname checks are not "
                "atomic compare-and-swap.",
            ],
        }

    def close(self) -> None:
        self._closed = True
        first = None
        pending = []
        if self._fd >= 0:
            pending.append(self._fd)
            self._fd = -1
        pending.extend(fd for _, fd, _ in reversed(self._parents))
        self._parents = []
        for fd in pending:
            try:
                os.close(fd)
            except BaseException as exc:
                self._cleanup_confirmed = False
                if first is None or isinstance(first, Exception) and not isinstance(exc, Exception):
                    first = exc
        if first is not None and not isinstance(first, Exception):
            raise first
        if not self._cleanup_confirmed:
            # An earlier close may have consumed every descriptor while still
            # leaving its result uncertain. Never signal success on a later
            # empty close, or retry a stale descriptor number that may be reused.
            error = GeneratedRuntimeInputError("runtime-profile-descriptor-cleanup-unconfirmed")
            error.descriptor_cleanup_confirmed = False
            raise error from first


def prepare_generated_runtime_input(path) -> LoadedRuntimeProfile:
    """Capture/recheck one private current profile, without process or network I/O."""
    return LoadedRuntimeProfile(path)
