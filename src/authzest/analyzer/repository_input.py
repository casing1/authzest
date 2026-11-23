"""Bounded, explicitly selected external source capture; never import or execute it.

Held descriptors and repeated reads detect ordinary edits and replacements. This
is not an atomic snapshot against a hostile same-user writer. No repository walk,
dependency loading, secret discovery or automatic file selection occurs here.
"""

from __future__ import annotations

import os
import stat
import sys
import unicodedata
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

MAX_SOURCE_BYTES = 16_384
MAX_POLICY_BYTES = 8192
MAX_TOTAL_BYTES = 65_536
MAX_CONTEXT_FILES = 4
_OPEN_DIR_FD = os.open in os.supports_dir_fd
_STAT_DIR_FD = os.stat in os.supports_dir_fd
_STAT_NOFOLLOW = os.stat in os.supports_follow_symlinks


class RepositoryInputError(ValueError):
    """A closed input failure without source text or private filesystem paths."""


@dataclass(frozen=True, slots=True)
class CapturedFile:
    path: str
    text: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "text": self.text, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class RepositoryInput:
    root: Path
    source: str
    policy: str
    contexts: tuple[str, ...]
    files: tuple[CapturedFile, ...]

    def to_dict(self) -> dict:
        """Relative selected inputs only; the local absolute root is not shared."""
        return {
            "source": self.source,
            "policy": self.policy,
            "contexts": list(self.contexts),
            "files": [file.to_dict() for file in self.files],
        }


def _fail(code: str) -> None:
    raise RepositoryInputError(code)


def _supported() -> bool:
    return (
        os.name == "posix"
        and not getattr(sys, "frozen", False)
        and _OPEN_DIR_FD
        and _STAT_DIR_FD
        and _STAT_NOFOLLOW
        and all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "pread"))
    )


def _relative(value: str, suffixes: set[str]) -> str:
    if type(value) is not str:
        _fail("repository-input-selection-invalid")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        _fail("repository-input-selection-invalid")
    parts = value.split("/")
    if (
        not encoded
        or len(encoded) > 512
        or len(parts) > 16
        or "\\" in value
        or any(not part or part.startswith(".") for part in parts)
        or any(unicodedata.category(char).startswith("C") for char in value)
        or Path(value).suffix not in suffixes
    ):
        _fail("repository-input-selection-invalid")
    return value


def _identity(info: os.stat_result) -> tuple:
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


def _read(fd: int, limit: int) -> bytes:
    raw = bytearray()
    while len(raw) <= limit:
        chunk = os.pread(fd, min(4096, limit + 1 - len(raw)), len(raw))
        if not chunk:
            return bytes(raw)
        raw.extend(chunk)
    _fail("repository-input-size-limit")


def capture_repository(
    root: Path, source: str, policy: str, contexts: tuple[str, ...] = ()
) -> RepositoryInput:
    """Capture source, policy, then optional contexts; unsupported paths fail closed."""
    if not _supported():
        _fail("repository-input-platform-unsupported")
    source = _relative(source, {".py"})
    policy = _relative(policy, {".md", ".txt"})
    if type(contexts) is not tuple or len(contexts) > MAX_CONTEXT_FILES:
        _fail("repository-input-selection-invalid")
    contexts = tuple(_relative(path, {".py"}) for path in contexts)
    paths = (source, policy, *contexts)
    if len(set(paths)) != len(paths) or not isinstance(root, Path):
        _fail("repository-input-selection-invalid")
    try:
        if any(unicodedata.category(char).startswith("C") for char in str(root)):
            _fail("repository-input-root-invalid")
        try:
            root = Path(os.path.abspath(root.expanduser()))
        except RuntimeError:
            raise RepositoryInputError("repository-input-root-invalid") from None
        if len(root.parts) > 64 or len(str(root).encode("utf-8")) > 4096:
            _fail("repository-input-root-invalid")
        with ExitStack() as stack:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            directories = []

            def directory(name, parent=None):
                fd = os.open(name, flags, dir_fd=parent)
                stack.callback(os.close, fd)
                info = os.fstat(fd)
                if not stat.S_ISDIR(info.st_mode):
                    _fail("repository-input-directory-required")
                observed = _identity(info)[:5]
                directories.append((parent, name, fd, observed))
                return fd

            root_fd = directory(root.anchor)
            for part in root.parts[1:]:
                root_fd = directory(part, root_fd)
            captured, opened, total = [], [], 0
            for path in paths:
                parts = path.split("/")
                parent = root_fd
                for part in parts[:-1]:
                    parent = directory(part, parent)
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                stack.callback(os.close, fd)
                info = os.fstat(fd)
                limit = MAX_POLICY_BYTES if path == policy else MAX_SOURCE_BYTES
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    _fail("repository-input-regular-file-required")
                if not 0 <= info.st_size <= limit or total + info.st_size > MAX_TOTAL_BYTES:
                    _fail("repository-input-size-limit")
                raw = _read(fd, limit)
                if len(raw) != info.st_size:
                    _fail("repository-input-changed")
                text = raw.decode("utf-8", errors="strict")
                if "\0" in text or path == policy and not text.strip():
                    _fail("repository-input-text-invalid")
                total += len(raw)
                if total > MAX_TOTAL_BYTES:
                    _fail("repository-input-size-limit")
                captured.append(CapturedFile(path, text, sha256(raw).hexdigest()))
                opened.append((parent, parts[-1], fd, _identity(info), raw, limit))
            for parent, name, fd, observed, raw, limit in opened:
                if (
                    _identity(os.fstat(fd)) != observed
                    or _identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != observed
                    or _read(fd, limit) != raw
                    or _identity(os.fstat(fd)) != observed
                    or _identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != observed
                ):
                    _fail("repository-input-changed")
            for parent, name, fd, observed in directories:
                if (
                    _identity(os.fstat(fd))[:5] != observed
                    or _identity(os.stat(name, dir_fd=parent, follow_symlinks=False))[:5]
                    != observed
                ):
                    _fail("repository-input-changed")
            return RepositoryInput(root, source, policy, contexts, tuple(captured))
    except (OSError, UnicodeError):
        raise RepositoryInputError("repository-input-unavailable") from None
