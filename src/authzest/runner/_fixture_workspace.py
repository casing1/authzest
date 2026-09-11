"""Private POSIX fixture-copy I/O, not an arbitrary-checkout or hostile-writer sandbox."""

from __future__ import annotations

import os
import stat
import tempfile
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(RuntimeError):
    """A precondition or bounded workspace operation failed."""


class CommittedWriteError(WorkspaceError):
    """Replacement happened, but its durability/current state could not be confirmed."""


@dataclass(frozen=True)
class FileState:
    data: bytes
    identity: tuple[int, ...]


def _identity(info: os.stat_result) -> tuple[int, ...]:
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


def supported() -> bool:
    return os.name == "posix" and all(
        hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")
    )


class FixtureWorkspace:
    """Only creates a new directory; never opens an existing checkout as a write target.

    Call close() to release the directory handle. Files are intentionally retained.
    The caller must exclude concurrent writers, including other same-user processes.
    """

    def __init__(self, before: bytes, after: bytes, *, parent: Path | None = None):
        if not supported():
            raise WorkspaceError("Fixture application requires supported POSIX file operations")
        self.path = Path(tempfile.mkdtemp(prefix="authzest-fixture-", dir=parent)).resolve()
        self._fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self._root = os.fstat(self._fd)
        try:
            self._check_root()
            for name, data in (("main.py", before), ("before.txt", before), ("after.txt", after)):
                self._create(name, data)
            os.fsync(self._fd)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def _check_root(self) -> None:
        if self._fd < 0:
            raise WorkspaceError("Workspace session is closed")
        info = os.stat(self.path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(info.st_mode)
            or (info.st_dev, info.st_ino) != (self._root.st_dev, self._root.st_ino)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise WorkspaceError("Workspace directory identity or permissions changed")

    def read_main(self) -> FileState:
        self._check_root()
        fd = os.open("main.py", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fd)
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_size > 131_072
            ):
                raise WorkspaceError("Expected a private, bounded, single-link regular main.py")
            chunks = []
            remaining = 131_073
            while remaining:
                chunk = os.read(fd, min(remaining, 16_384))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if len(data) > 131_072 or _identity(os.fstat(fd)) != _identity(before):
                raise WorkspaceError("Source changed during read or exceeded the limit")
            if _identity(os.stat("main.py", dir_fd=self._fd, follow_symlinks=False)) != _identity(
                before
            ):
                raise WorkspaceError("Source name no longer identifies the opened file")
            self._check_root()
            return FileState(data, _identity(before))
        finally:
            os.close(fd)

    def _create(self, name: str, data: bytes) -> None:
        fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self._fd
        )
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("Incomplete workspace write")
                view = view[written:]
            os.fsync(fd)
        except BaseException:
            self._discard(name)
            raise
        finally:
            os.close(fd)

    def _stage(self, data: bytes) -> str:
        self._check_root()
        name = ".stage-" + uuid.uuid4().hex
        self._create(name, data)
        return name

    def _discard(self, name: str) -> None:
        # Only a session-created random staging entry, never caller-selected paths.
        # Preserve the primary write outcome; an unremovable stage stays for inspection.
        with suppress(OSError):
            os.unlink(name, dir_fd=self._fd)

    def write_record(self, data: bytes) -> None:
        name = self._stage(data)
        try:
            self._check_root()
            os.replace(name, "record.json", src_dir_fd=self._fd, dst_dir_fd=self._fd)
            os.fsync(self._fd)
        finally:
            self._discard(name)

    def replace_main(
        self, expected: FileState, data: bytes, *, guard: Callable[[], None]
    ) -> FileState:
        name = self._stage(data)
        committed = False
        try:
            if self.read_main() != expected:
                raise WorkspaceError("Current file differs from the reviewed state")
            guard()
            self._check_root()
            # Atomic replacement is NOT compare-and-swap against a hostile concurrent writer.
            os.replace(name, "main.py", src_dir_fd=self._fd, dst_dir_fd=self._fd)
            committed = True
            os.fsync(self._fd)
            result = self.read_main()
            if result.data != data:
                raise WorkspaceError("Post-replacement content is unexpected")
            return result
        except (OSError, WorkspaceError) as exc:
            if committed:
                raise CommittedWriteError(
                    "Replacement occurred; inspect retained workspace"
                ) from exc
            raise
        finally:
            self._discard(name)
