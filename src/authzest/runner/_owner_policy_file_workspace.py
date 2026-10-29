"""Private registered-policy copy I/O; never an existing-checkout or execution API."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from authzest.codex.owner_policy_repair_pair import build_owner_policy_repair_pair

MAX_SOURCE_BYTES = 32_768


class WorkspaceError(RuntimeError):
    """A bounded workspace precondition or operation failed."""


class WorkspaceInitializationError(WorkspaceError):
    """A confirmed new directory remains after incomplete initialization."""

    STAGES = frozenset(
        {
            "resolve-path",
            "open-directory",
            "inspect-directory",
            "check-directory",
            "create-policy",
            "create-before",
            "create-after",
            "sync-directory",
            "read-initial-source",
            "write-initial-record",
        }
    )

    def __init__(self, created_path: Path, initialization_stage: str):
        if initialization_stage not in self.STAGES:
            raise ValueError("Unknown workspace initialization stage")
        super().__init__("Policy workspace initialization failed; inspect the retained directory.")
        self.created_path = created_path
        self.initialization_stage = initialization_stage


class CommittedWriteError(WorkspaceError):
    """Replacement happened, but durability or the resulting state is unconfirmed."""


@dataclass(frozen=True)
class FileState:
    data: bytes
    identity: tuple[int, ...]


def _root_identity(info: os.stat_result) -> tuple[int, ...]:
    # Child creation/replacement changes directory timestamps, not session identity.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        *_root_identity(info),
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def supported() -> bool:
    return (
        os.name == "posix"
        and not getattr(sys, "frozen", False)
        and all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
        and all(
            operation in os.supports_dir_fd
            for operation in (os.open, os.stat, os.unlink, os.rename)
        )
        and os.stat in os.supports_follow_symlinks
    )


class PolicyFileWorkspace:
    """Create only a new registered copy; retain files when the handle is closed.

    ``_parent`` is a private test seam, not a production destination option.
    A trusted operator must exclude concurrent writers, including same-user processes.
    No process, policy evaluation, provider, authentication or restart/resume is supplied.
    """

    def __init__(self, *, _parent: Path | None = None):
        if not supported():
            raise WorkspaceError("Policy copies require supported POSIX Python source operations")
        content = build_owner_policy_repair_pair().to_dict()["content"]
        before, after = (
            content[candidate]["text"].encode("utf-8") for candidate in ("before", "after")
        )
        if max(len(before), len(after)) > MAX_SOURCE_BYTES:
            raise WorkspaceError("Registered source exceeds the workspace limit")
        self._allowed = frozenset((before, after))
        self.path = Path(tempfile.mkdtemp(prefix="authzest-owner-policy-", dir=_parent))
        self._fd = -1
        stage = "resolve-path"
        try:
            self.path = self.path.resolve()
            stage = "open-directory"
            self._fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stage = "inspect-directory"
            self._root = _root_identity(os.fstat(self._fd))
            stage = "check-directory"
            self._check_root()
            for create_stage, name, data in (
                ("create-policy", "policy.py", before),
                ("create-before", "before.txt", before),
                ("create-after", "after.txt", after),
            ):
                stage = create_stage
                self._create(name, data)
            stage = "sync-directory"
            os.fsync(self._fd)
        except BaseException as exc:
            failure = WorkspaceInitializationError(self.path, stage)
            try:
                self.close()
            except Exception:
                pass
            except BaseException as interrupted:
                interrupted.workspace_initialization = failure
                raise
            if isinstance(exc, Exception):
                raise failure from None
            exc.workspace_initialization = failure
            raise

    @property
    def root_identity(self) -> tuple[int, ...]:
        self._check_root()
        return self._root

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def _check_root(self) -> None:
        if self._fd < 0:
            raise WorkspaceError("Workspace session is closed")
        opened = os.fstat(self._fd)
        named = os.stat(self.path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or _root_identity(opened) != self._root
            or _root_identity(named) != self._root
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != 0o700
        ):
            raise WorkspaceError("Workspace directory identity or permissions changed")

    def read_policy(self) -> FileState:
        self._check_root()
        fd = os.open("policy.py", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fd)
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600
                or not 0 <= before.st_size <= MAX_SOURCE_BYTES
            ):
                raise WorkspaceError("Expected a private bounded single-link regular policy.py")
            chunks = []
            remaining = MAX_SOURCE_BYTES + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 16_384))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if (
                len(data) != before.st_size
                or len(data) > MAX_SOURCE_BYTES
                or _identity(os.fstat(fd)) != _identity(before)
            ):
                raise WorkspaceError("Policy changed during read or exceeded the limit")
            if _identity(os.stat("policy.py", dir_fd=self._fd, follow_symlinks=False)) != _identity(
                before
            ):
                raise WorkspaceError("Policy name no longer identifies the opened file")
            try:
                if data.decode("utf-8").encode("utf-8") != data:
                    raise WorkspaceError("Policy source must round-trip exact UTF-8")
            except UnicodeError as exc:
                raise WorkspaceError("Policy source must be exact UTF-8") from exc
            self._check_root()
            return FileState(data, _identity(before))
        finally:
            os.close(fd)

    def _create(self, name: str, data: bytes) -> None:
        self._check_root()
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
            self._check_root()
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
        # Only a just-created entry, never a caller-selected deletion target.
        with suppress(OSError):
            os.unlink(name, dir_fd=self._fd)

    def write_record(self, data: bytes) -> None:
        if type(data) is not bytes:
            raise WorkspaceError("Record must be bytes")
        name = self._stage(data)
        committed = False
        commit_attempted = False
        try:
            self._check_root()
            commit_attempted = True
            os.replace(name, "record.json", src_dir_fd=self._fd, dst_dir_fd=self._fd)
            committed = True
            os.fsync(self._fd)
            self._check_root()
        except BaseException as exc:
            if not isinstance(exc, Exception):
                if commit_attempted:
                    exc.workspace_commit_uncertain = True
                if committed:
                    exc.workspace_committed = True
            elif committed:
                raise CommittedWriteError(
                    "Record replacement occurred; inspect retained workspace"
                ) from exc
            raise
        finally:
            self._discard(name)

    def replace_policy(
        self,
        expected: FileState,
        data: bytes,
        *,
        guard: Callable[[], None],
        before_commit: Callable[[], None] | None = None,
    ) -> FileState:
        """Replace fixed bytes, with an optional final trusted decision-time check."""
        if type(expected) is not FileState or type(data) is not bytes or data not in self._allowed:
            raise WorkspaceError("Policy replacement requires tracked state and registered bytes")
        if not callable(guard):
            raise WorkspaceError("Policy replacement requires a decision guard")
        if before_commit is not None and not callable(before_commit):
            raise WorkspaceError("Final decision check must be callable")
        name = self._stage(data)
        committed = False
        commit_attempted = False
        try:
            if self.read_policy() != expected:
                raise WorkspaceError("Current policy differs from the reviewed state")
            guard()
            if self.read_policy() != expected:
                raise WorkspaceError("Policy changed during the decision guard")
            self._check_root()
            if before_commit is not None:
                before_commit()
            # Atomic rename is not compare-and-swap against a concurrent hostile writer.
            commit_attempted = True
            os.replace(name, "policy.py", src_dir_fd=self._fd, dst_dir_fd=self._fd)
            committed = True
            os.fsync(self._fd)
            result = self.read_policy()
            if result.data != data:
                raise WorkspaceError("Post-replacement policy content is unexpected")
            return result
        except BaseException as exc:
            if not isinstance(exc, Exception):
                if commit_attempted:
                    exc.workspace_commit_uncertain = True
                if committed:
                    exc.workspace_committed = True
            elif committed:
                raise CommittedWriteError(
                    "Policy replacement occurred; inspect retained workspace"
                ) from exc
            raise
        finally:
            self._discard(name)
