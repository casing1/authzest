"""HTTP-only private profile-file input, never runtime readiness or consent.

The file is held through no-follow descriptors and rechecked before dispatch.
Its image/engine fields remain declarations: neither a matching file nor a caller
copy of this module's review JSON establishes image contents or kernel controls.
"""

from __future__ import annotations

import os
import stat
import sys
import threading
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import ContractError
from authzest.runner._repository_http_runtime_profile import (
    MAX_PROFILE_BYTES,
    RepositoryHttpRuntimeProfile,
    validate_runtime_profile,
)

_OPEN_DIR_FD = os.open in os.supports_dir_fd
_STAT_DIR_FD = os.stat in os.supports_dir_fd
_STAT_NOFOLLOW = os.stat in os.supports_follow_symlinks


class RepositoryHttpRuntimeInputError(ValueError):
    """A redacted profile input failure; no source/user path enters its message."""


def _fail(reason):
    raise RepositoryHttpRuntimeInputError(reason)


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
        _fail("http-runtime-profile-parent-unavailable")
    return _identity(info)[:5]


def _file(info):
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or not 0 < info.st_size <= MAX_PROFILE_BYTES
    ):
        _fail("http-runtime-profile-private-file-required")
    return _identity(info)


def _path(path):
    if type(path) not in {str, Path, type(Path())}:
        _fail("http-runtime-profile-path-invalid")
    raw = str(path)
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError as exc:
        raise RepositoryHttpRuntimeInputError("http-runtime-profile-path-invalid") from exc
    if (
        not encoded
        or len(encoded) > 512
        or any(ord(char) < 32 or ord(char) == 127 for char in raw)
        or ".." in raw.split("/")
    ):
        _fail("http-runtime-profile-path-invalid")
    value = Path(os.path.abspath(raw))
    if len(str(value).encode("utf-8")) > 512 or not 2 <= len(value.parts) <= 33:
        _fail("http-runtime-profile-path-invalid")
    return value


def _profile(raw):
    try:
        value = validate_runtime_profile(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ContractError, ValueError, TypeError) as exc:
        raise RepositoryHttpRuntimeInputError("http-runtime-profile-declaration-invalid") from exc
    return value


class LoadedRepositoryHttpRuntimeProfile:
    """Observed private file and pinned data, not a live runtime capability.

    The operator and Python caller are trusted. Held descriptors and repeated
    checks detect ordinary edits/replacements; they are not atomic pathname CAS
    against a hostile same-user writer. Close retains the original file unchanged.
    """

    def __init__(self, path):
        if type(self) is not LoadedRepositoryHttpRuntimeProfile:
            _fail("http-runtime-profile-subclass-unsupported")
        self._pid, self._thread = os.getpid(), threading.get_ident()
        self._busy, self._poisoned = True, False
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
                _fail("http-runtime-profile-platform-unsupported")
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
                _fail("http-runtime-profile-file-changed")
            self._profile = _profile(self._raw)
            self._verify()
        except BaseException as exc:
            self._failed(exc)
        finally:
            self._busy = False

    def __copy__(self):
        raise TypeError("Live HTTP profile inputs cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live HTTP profile inputs cannot be copied")

    def __reduce__(self):
        raise TypeError("Live HTTP profile inputs cannot be serialized")

    def _owner(self):
        if (
            type(self) is not LoadedRepositoryHttpRuntimeProfile
            or self._pid != os.getpid()
            or self._thread != threading.get_ident()
        ):
            _fail("http-runtime-profile-owner-unavailable")

    def _enter(self):
        self._owner()
        if self._busy:
            self._poisoned = True
            _fail("http-runtime-profile-reentrant-operation")
        if self._closed or self._poisoned or self._profile is None:
            _fail("http-runtime-profile-input-closed")
        self._busy = True

    def _failed(self, original):
        try:
            self._close()
        except BaseException as interrupted:
            self._cleanup_confirmed = False
            if not isinstance(interrupted, Exception) and isinstance(original, Exception):
                interrupted.runtime_profile_cleanup_confirmed = False
                raise
        if not isinstance(original, Exception):
            original.runtime_profile_cleanup_confirmed = self._cleanup_confirmed
            raise original
        if isinstance(original, RepositoryHttpRuntimeInputError):
            original.descriptor_cleanup_confirmed = self._cleanup_confirmed
            raise original
        error = RepositoryHttpRuntimeInputError("http-runtime-profile-file-unavailable")
        error.descriptor_cleanup_confirmed = self._cleanup_confirmed
        raise error from original

    def _read(self):
        if self._fd < 0:
            _fail("http-runtime-profile-input-closed")
        raw = bytearray()
        while True:
            chunk = os.pread(self._fd, min(4096, MAX_PROFILE_BYTES + 1 - len(raw)), len(raw))
            if type(chunk) is not bytes:
                _fail("http-runtime-profile-file-unavailable")
            raw.extend(chunk)
            if len(raw) > MAX_PROFILE_BYTES:
                _fail("http-runtime-profile-size-limit")
            if not chunk:
                return bytes(raw)

    @property
    def profile(self) -> RepositoryHttpRuntimeProfile:
        self.assert_current()
        return self._profile

    def assert_current(self) -> None:
        self._enter()
        try:
            self._verify()
        except BaseException as exc:
            self._failed(exc)
        finally:
            self._busy = False

    def _verify(self):
        if self._closed or self._profile is None or self._poisoned or not _supported():
            _fail("http-runtime-profile-input-closed")
        self._owner()
        for path, fd, observed in self._parents:
            if _directory(os.fstat(fd)) != observed or _directory(os.lstat(path)) != observed:
                _fail("http-runtime-profile-parent-changed")
        named = os.stat(self._path.name, dir_fd=self._parents[-1][1], follow_symlinks=False)
        if _file(named) != self._identity or _file(os.fstat(self._fd)) != self._identity:
            _fail("http-runtime-profile-file-changed")
        raw = self._read()
        checked = _profile(raw)
        if (
            raw != self._raw
            or len(raw) != self._identity[6]
            or _file(os.fstat(self._fd)) != self._identity
            or _file(os.stat(self._path.name, dir_fd=self._parents[-1][1], follow_symlinks=False))
            != self._identity
            or type(self._profile) is not RepositoryHttpRuntimeProfile
            or checked.payload_json != self._profile.payload_json
        ):
            _fail("http-runtime-profile-file-changed")
        # Check the named parent path again after the bounded read and refuse
        # suppressed reentry; neither check is hostile-writer atomic CAS.
        if any(_directory(os.lstat(path)) != observed for path, _, observed in self._parents):
            _fail("http-runtime-profile-parent-changed")
        self._owner()
        if self._poisoned:
            _fail("http-runtime-profile-reentrant-operation")

    def review_dict(self) -> dict:
        self._enter()
        try:
            self._verify()
            result = {
                "schema_version": "2.0",
                "kind": "repository-http-runtime-input-review",
                "status": "profile-file-captured-unverified-runtime",
                "profile_id": self._profile.profile_id,
                "profile": self._profile.to_dict(),
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
                "engine_contact_attempted": False,
                "runtime_invoked": False,
                "execution_authorized": False,
                "resource_enforcement_established": False,
                "isolation_established": False,
                "authorization_status": "unknown",
                "verified_fix": False,
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
            self._verify()
            return result
        except BaseException as exc:
            self._failed(exc)
        finally:
            self._busy = False

    def close(self) -> None:
        self._owner()
        if self._busy:
            self._poisoned = True
            _fail("http-runtime-profile-reentrant-operation")
        self._busy = True
        try:
            self._close()
        finally:
            self._busy = False

    def _close(self) -> None:
        self._closed = True
        first = None
        pending = []
        if self._fd >= 0:
            pending.append(self._fd)
            self._fd = -1
        pending.extend(fd for _, fd, _ in reversed(self._parents))
        self._parents = []
        for fd in dict.fromkeys(pending):
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
            error = RepositoryHttpRuntimeInputError(
                "http-runtime-profile-descriptor-cleanup-unconfirmed"
            )
            error.descriptor_cleanup_confirmed = False
            raise error from first


def prepare_repository_http_runtime_input(path) -> LoadedRepositoryHttpRuntimeProfile:
    """Capture/recheck one private current profile, without process or network I/O."""
    return LoadedRepositoryHttpRuntimeProfile(path)
