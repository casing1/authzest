"""Retain initial selected-file identities in one live, read-only POSIX handle.

The snapshot is content, not authority. Only this process's unclosed capture can
verify continuity; saved data cannot reopen it. Repeated descriptor/name/byte
checks detect ordinary changes, not an atomic snapshot against hostile writers.
"""

from __future__ import annotations

import os
import stat
import unicodedata
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path

from authzest.analyzer import repository_input as _input
from authzest.analyzer.repository_input import CapturedFile, RepositoryInput, RepositoryInputError

_FACTORY = object()


class RepositoryOriginError(RepositoryInputError):
    """A redacted initial-capture or live-continuity failure."""


def _fail(code: str) -> None:
    raise RepositoryOriginError("repository-origin-" + code)


class RepositoryOrigin:
    """Current-process ownership of held read descriptors, never a saved-record opener.

    ``snapshot`` remains content-only data even after close. Private Python fields
    are trusted coordination, not protection from arbitrary code in this process.
    """

    __slots__ = ("_closed", "_directories", "_files", "_owner", "_pid", "_snapshot", "_stack")

    def __init__(self, snapshot, directories, files, stack, *, _factory=None):
        if _factory is not _FACTORY:
            _fail("factory-required")
        self._snapshot = snapshot
        self._directories = tuple(directories)
        self._files = tuple(files)
        self._stack = stack
        self._pid = os.getpid()
        self._closed = False
        self._owner = None

    def _claim(self, owner: object) -> None:
        """Transfer descriptor ownership once to a trusted current-process coordinator."""
        self.verify()
        if type(owner) is not object or self._owner is not None:
            _fail("already-owned-or-invalid-owner")
        self._owner = owner

    @property
    def snapshot(self) -> RepositoryInput:
        """Immutable selected content; this property does not assert freshness."""
        return self._snapshot

    @property
    def closed(self) -> bool:
        return self._closed

    def __copy__(self):
        raise TypeError("Live origin handles cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live origin handles cannot be copied")

    def __reduce__(self):
        raise TypeError("Live origin handles cannot be serialized")

    def __enter__(self) -> RepositoryOrigin:
        self.verify()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Release this process's descriptors; retain content and all original files."""
        if self._closed:
            return
        self._closed = True
        try:
            self._stack.close()
        except OSError:
            _fail("close-unconfirmed")

    def _check_directories(self) -> None:
        for parent, name, fd, observed in self._directories:
            if (
                _input._identity(os.fstat(fd))[:5] != observed
                or _input._identity(os.stat(name, dir_fd=parent, follow_symlinks=False))[:5]
                != observed
                or _input._identity(os.fstat(fd))[:5] != observed
            ):
                _fail("changed")

    def verify(self, selection: dict | None = None) -> RepositoryInput:
        """Check exact initial selection, identities and bytes without importing code."""
        if getattr(self, "_closed", True):
            _fail("closed")
        if self._pid != os.getpid():
            _fail("process-changed")
        if selection is not None and (
            type(selection) is not dict or selection != self._snapshot.to_dict()
        ):
            _fail("selection-mismatch")
        try:
            self._check_directories()
            for parent, name, fd, observed, raw, limit in self._files:
                if (
                    _input._identity(os.fstat(fd)) != observed
                    or _input._identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
                    != observed
                    or _input._read(fd, limit) != raw
                    or _input._identity(os.fstat(fd)) != observed
                    or _input._identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
                    != observed
                ):
                    _fail("changed")
            self._check_directories()
        except RepositoryOriginError:
            raise
        except RepositoryInputError as exc:
            raise RepositoryOriginError(
                str(exc).replace("repository-input-", "repository-origin-", 1)
            ) from None
        except OSError:
            raise RepositoryOriginError("repository-origin-unavailable") from None
        return self._snapshot


def capture_repository_origin(
    root: Path, source: str, policy: str, contexts: tuple[str, ...] = ()
) -> RepositoryOrigin:
    """Capture only selected bounded inputs, retaining initial read descriptors."""
    if not _input._supported():
        _fail("platform-unsupported")
    stack = ExitStack()
    try:
        source = _input._relative(source, {".py"})
        policy = _input._relative(policy, {".md", ".txt"})
        if type(contexts) is not tuple or len(contexts) > _input.MAX_CONTEXT_FILES:
            _fail("selection-invalid")
        contexts = tuple(_input._relative(path, {".py"}) for path in contexts)
        paths = (source, policy, *contexts)
        if len(set(paths)) != len(paths) or not isinstance(root, Path):
            _fail("selection-invalid")
        if any(unicodedata.category(char).startswith("C") for char in str(root)):
            _fail("root-invalid")
        try:
            root = Path(os.path.abspath(root.expanduser()))
        except RuntimeError:
            raise RepositoryOriginError("repository-origin-root-invalid") from None
        if len(root.parts) > 64 or len(str(root).encode("utf-8")) > 4096:
            _fail("root-invalid")
        directories, opened, captured = [], [], []
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

        def directory(name, parent=None):
            fd = os.open(name, flags, dir_fd=parent)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                _fail("directory-required")
            directories.append((parent, name, fd, _input._identity(info)[:5]))
            return fd

        root_fd = directory(root.anchor)
        for part in root.parts[1:]:
            root_fd = directory(part, root_fd)
        total = 0
        for path in paths:
            parts = path.split("/")
            parent = root_fd
            for part in parts[:-1]:
                parent = directory(part, parent)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            limit = _input.MAX_POLICY_BYTES if path == policy else _input.MAX_SOURCE_BYTES
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                _fail("regular-file-required")
            if not 0 <= info.st_size <= limit or total + info.st_size > _input.MAX_TOTAL_BYTES:
                _fail("size-limit")
            raw = _input._read(fd, limit)
            if len(raw) != info.st_size:
                _fail("changed")
            text = raw.decode("utf-8", errors="strict")
            if "\0" in text or path == policy and not text.strip():
                _fail("text-invalid")
            total += len(raw)
            if total > _input.MAX_TOTAL_BYTES:
                _fail("size-limit")
            captured.append(CapturedFile(path, text, sha256(raw).hexdigest()))
            opened.append((parent, parts[-1], fd, _input._identity(info), raw, limit))
        result = RepositoryOrigin(
            RepositoryInput(root, source, policy, contexts, tuple(captured)),
            directories,
            opened,
            stack,
            _factory=_FACTORY,
        )
        result.verify()
        return result
    except BaseException as exc:
        cleanup_confirmed = True
        try:
            stack.close()
        except OSError:
            cleanup_confirmed = False
            if isinstance(exc, Exception):
                raise RepositoryOriginError("repository-origin-cleanup-unconfirmed") from None
        if not isinstance(exc, Exception):
            exc.origin_cleanup_confirmed = cleanup_confirmed
        if isinstance(exc, RepositoryOriginError):
            raise
        if isinstance(exc, RepositoryInputError):
            raise RepositoryOriginError(
                str(exc).replace("repository-input-", "repository-origin-", 1)
            ) from None
        if isinstance(exc, OSError | UnicodeError):
            raise RepositoryOriginError("repository-origin-unavailable") from None
        raise
