"""Private fresh-copy byte I/O, not approval, execution or a resumable session.

Only a future trusted coordinator may supply real decisions and runtime proof.
Atomic rename is not compare-and-swap against hostile same-user writers; an
operator must exclude those writers. Closing retains every workspace artifact.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import sys
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from authzest.codex.generated_repair import build_generated_repair_request
from authzest.runner.generated_repair_verification import _checked_preview

MAX_SOURCE_BYTES = 16_384
MAX_RECORD_BYTES = 65_536
_TEST = "tests/test_generated_ownership.py"
_FILES = ("app.py", _TEST, "before.txt", "after.txt", "test.txt", "record.json")


class WorkspaceError(RuntimeError):
    """An owned workspace precondition or bounded operation failed."""


class WorkspaceInitializationError(WorkspaceError):
    """Initialization failed; partial files are retained, not retried or removed."""

    def __init__(self, created_path: Path, initialization_stage: str, file_states: dict):
        super().__init__("Workspace initialization failed; inspect the retained private copy")
        self.created_path = created_path
        self.initialization_stage = initialization_stage
        self.file_states = dict(file_states)


class CommittedWriteError(WorkspaceError):
    """A write was attempted or its cleanup/durability cannot be confirmed."""

    def __init__(
        self,
        operation: str,
        *,
        commit_attempted: bool,
        committed: bool,
        cleanup_failed: bool = False,
        journal_attempted: bool = False,
        journal_committed: bool = False,
        journal_phase: str | None = None,
    ):
        super().__init__("Workspace write state is unconfirmed; do not retry or blindly restore")
        self.operation = operation
        self.commit_attempted = commit_attempted
        self.committed = committed
        self.cleanup_failed = cleanup_failed
        self.journal_attempted = journal_attempted
        self.journal_committed = journal_committed
        self.journal_phase = journal_phase
        self.state_unconfirmed = True


@dataclass(frozen=True, slots=True)
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
    return (
        os.name == "posix"
        and not getattr(sys, "frozen", False)
        and all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
        and all(op in os.supports_dir_fd for op in (os.open, os.stat, os.unlink, os.rename))
        and os.stat in os.supports_follow_symlinks
    )


class GeneratedRepairWorkspace:
    """Retain a fresh private before source, generated test and closed journal.

    ``_parent`` is an owned test seam, never an existing workspace or destination
    option. This helper has no live approval, runtime executor or restart API.
    A guard is trusted synchronous coordination, not authenticated authority.
    """

    def __init__(self, preview, *, _parent: Path | None = None):
        # Rebuild the current source, policy, proposal, controls and exact diff
        # before even checking the platform or allocating a directory.
        checked = _checked_preview(preview)
        data = checked.to_dict()
        if data["proposal_status"] != "proposed-change":
            raise WorkspaceError("Only a current proposed change can materialize a copy")
        proposal = data["proposal_preview"]["proposal"]["proposal"]
        before = build_generated_repair_request().to_dict()["scenario"]["source"]["text"]
        self._before = before.encode("utf-8")
        self._after = proposal["after_text"].encode("utf-8")
        self._test = proposal["test_text"].encode("utf-8")
        if max(map(len, (self._before, self._after, self._test))) > MAX_SOURCE_BYTES:
            raise WorkspaceError("Workspace source or test exceeds the fixed byte budget")
        if not supported():
            raise WorkspaceError("Private copies require supported POSIX Python source operations")
        self._preview_id = checked.verification_preview_id
        self._state = "state-unconfirmed"
        self._busy = False
        self._fd = self._tests_fd = -1
        self._directories: dict[str, tuple[int, ...]] = {}
        self._tracked: dict[str, FileState] = {}
        self._partial = dict.fromkeys(_FILES, "not-created")
        self.path = Path(tempfile.mkdtemp(prefix="authzest-generated-repair-", dir=_parent))
        stage = "open-root"
        try:
            self.path = self.path.absolute()
            self._fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self._capture_directory("root")
            stage = "create-tests-directory"
            os.mkdir("tests", 0o700, dir_fd=self._fd)
            self._capture_directory("root", changing=True)
            self._tests_fd = os.open(
                "tests", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._fd
            )
            self._capture_directory("tests")
            for name, content in (
                ("app.py", self._before),
                (_TEST, self._test),
                ("before.txt", self._before),
                ("after.txt", self._after),
                ("test.txt", self._test),
            ):
                stage = "create-" + name
                self._create_initial(name, content)
            stage = "sync-initial-directories"
            os.fsync(self._tests_fd)
            os.fsync(self._fd)
            stage = "verify-initial-files"
            self._assert_all()
            stage = "create-initial-record"
            self._create_initial("record.json", self._record_bytes("ready-before"))
            stage = "sync-initial-record"
            os.fsync(self._fd)
            self._assert_all()
            self._state = "ready-before"
        except BaseException as exc:
            failure = WorkspaceInitializationError(self.path, stage, self._partial)
            self._state = "state-unconfirmed"
            try:
                self.close()
                failure.descriptor_cleanup_confirmed = True
            except BaseException as interrupted:
                failure.descriptor_cleanup_confirmed = False
                if not isinstance(interrupted, Exception) and isinstance(exc, Exception):
                    interrupted.workspace_initialization = failure
                    raise
            if isinstance(exc, Exception):
                raise failure from exc
            exc.workspace_initialization = failure
            raise

    @property
    def state(self) -> str:
        return self._state

    def close(self) -> None:
        """Close only descriptors; never delete a retained file or directory."""
        failure = None
        for name in ("_tests_fd", "_fd"):
            fd = getattr(self, name, -1)
            setattr(self, name, -1)
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError as exc:
                    failure = exc
        if failure is not None:
            raise WorkspaceError("Workspace descriptor closure failed") from failure

    def _directory(self, kind: str) -> tuple[int, os.stat_result, os.stat_result]:
        if self._fd < 0 or (kind == "tests" and self._tests_fd < 0):
            raise WorkspaceError("Workspace session is closed")
        fd = self._fd if kind == "root" else self._tests_fd
        opened = os.fstat(fd)
        named = (
            os.stat(self.path, follow_symlinks=False)
            if kind == "root"
            else os.stat("tests", dir_fd=self._fd, follow_symlinks=False)
        )
        if (
            not stat.S_ISDIR(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != 0o700
            or _identity(opened) != _identity(named)
        ):
            raise WorkspaceError("Workspace directory identity or permissions changed")
        return fd, opened, named

    def _capture_directory(self, kind: str, *, changing: bool = False) -> None:
        _, opened, _ = self._directory(kind)
        current = _identity(opened)
        previous = self._directories.get(kind)
        # Owned child creation changes link count, size and timestamps. Inode,
        # type/mode and ownership must still be the exact held directory.
        if (
            previous is not None
            and (current[:5] != previous[:5] or not changing)
            and current != previous
        ):
            raise WorkspaceError("Workspace directory changed unexpectedly")
        self._directories[kind] = current

    def _check_directories(self) -> None:
        for kind, expected in self._directories.items():
            if _identity(self._directory(kind)[1]) != expected:
                raise WorkspaceError("Workspace directory changed since the last owned operation")

    def _location(self, name: str) -> tuple[int, str, str]:
        if name == _TEST:
            return self._tests_fd, "test_generated_ownership.py", "tests"
        return self._fd, name, "root"

    def _read(self, name: str, *, limit: int | None = None) -> FileState:
        fd_dir, basename, _ = self._location(name)
        maximum = (
            limit
            if limit is not None
            else (MAX_RECORD_BYTES if name == "record.json" else MAX_SOURCE_BYTES)
        )
        fd = os.open(basename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd_dir)
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600
                or not 0 <= before.st_size <= maximum
            ):
                raise WorkspaceError("Expected a private bounded single-link regular file")
            chunks = []
            remaining = maximum + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 16_384))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
            expected = _identity(before)
            if (
                len(content) != before.st_size
                or len(content) > maximum
                or _identity(os.fstat(fd)) != expected
                or _identity(os.stat(basename, dir_fd=fd_dir, follow_symlinks=False)) != expected
            ):
                raise WorkspaceError("Workspace file changed while reading")
            try:
                content.decode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise WorkspaceError("Workspace files must be exact UTF-8") from exc
            return FileState(content, expected)
        finally:
            os.close(fd)

    def _assert_all(self) -> None:
        try:
            self._check_directories()
            for name, expected in self._tracked.items():
                if self._read(name) != expected:
                    raise WorkspaceError("Tracked workspace bytes or file identity changed")
            self._check_directories()
        except (OSError, WorkspaceError):
            self._state = "state-unconfirmed"
            raise

    def _write_new(self, name: str, content: bytes) -> tuple[int, ...]:
        fd_dir, basename, _ = self._location(name)
        if name in self._partial:
            self._partial[name] = "creation-attempted"
        fd = os.open(
            basename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=fd_dir,
        )
        if name in self._partial:
            self._partial[name] = "created-unconfirmed"
        try:
            os.fchmod(fd, 0o600)
            pending = memoryview(content)
            while pending:
                written = os.write(fd, pending)
                if written <= 0:
                    raise OSError("Incomplete workspace write")
                pending = pending[written:]
            os.fsync(fd)
            final = _identity(os.fstat(fd))
            if _identity(os.stat(basename, dir_fd=fd_dir, follow_symlinks=False)) != final:
                raise WorkspaceError("New workspace name no longer identifies the created file")
            return final
        finally:
            os.close(fd)

    def _create_initial(self, name: str, content: bytes) -> None:
        self._assert_all()
        created_identity = self._write_new(name, content)
        _, _, directory = self._location(name)
        self._capture_directory(directory, changing=True)
        result = self._read(name)
        if result.data != content or result.identity != created_identity:
            raise WorkspaceError("Initial workspace file did not read back exactly")
        self._tracked[name] = result
        self._partial[name] = "confirmed"

    def _record_bytes(self, phase: str, *, pending: str | None = None) -> bytes:
        hashes = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in (
                ("before", self._before),
                ("after", self._after),
                ("test", self._test),
            )
        }
        data = {
            "schema_version": "1.0",
            "kind": "generated-repair-private-workspace-record",
            "verification_preview_id": self._preview_id,
            "hashes": hashes,
            "phase": phase,
            "pending_operation": pending,
            "directories": {key: list(value[:5]) for key, value in self._directories.items()},
            "files": {
                name: {
                    "sha256": hashlib.sha256(value.data).hexdigest(),
                    "identity": list(value.identity),
                }
                for name, value in self._tracked.items()
                if name != "record.json"
            },
            "source_application": "apply-pending"
            if pending == "apply"
            else ("not-run" if phase == "ready-before" else "applied-copy-only"),
            "test_materialization": "materialized-private-copy",
            "restoration": "restore-pending"
            if pending == "restore"
            else ("restored-before" if phase == "restored-before" else "not-run"),
            "execution_status": "not-run",
            "authorization_status": "unknown",
            "approval": "not-provided",
            "verified_fix": False,
        }
        content = json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        if len(content) > MAX_RECORD_BYTES:
            raise WorkspaceError("Closed workspace journal exceeds its fixed budget")
        return content

    def _public_read(self, name: str) -> FileState:
        try:
            self._assert_all()
            return self._tracked[name]
        except (OSError, WorkspaceError) as exc:
            self._state = "state-unconfirmed"
            raise WorkspaceError("Workspace integrity is unconfirmed") from exc

    def read_source(self) -> FileState:
        return self._public_read("app.py")

    def read_test(self) -> FileState:
        return self._public_read(_TEST)

    def read_record(self) -> FileState:
        return self._public_read("record.json")

    def _stage(self, content: bytes) -> tuple[str, FileState]:
        self._assert_all()
        name = ".stage-" + uuid.uuid4().hex
        try:
            created_identity = self._write_new(name, content)
            self._capture_directory("root", changing=True)
            result = self._read(name, limit=MAX_RECORD_BYTES)
            if result.data != content or result.identity != created_identity:
                raise WorkspaceError("Staged bytes failed exact readback")
            return name, result
        except BaseException:
            # No complete stage pin exists: retain it and poison the session,
            # rather than unlinking an entry whose exact identity is unknown.
            self._state = "state-unconfirmed"
            raise

    def _discard(self, stage: tuple[str, FileState]) -> None:
        name, expected = stage
        self._check_directories()
        if self._read(name, limit=MAX_RECORD_BYTES) != expected:
            raise WorkspaceError("Staging entry identity changed; it was retained")
        os.unlink(name, dir_fd=self._fd)
        os.fsync(self._fd)
        self._capture_directory("root", changing=True)

    def _persist_record(self, phase: str, *, pending: str | None = None) -> None:
        self._journal_phase = pending or phase
        self._journal_attempted = self._journal_committed = False
        content = self._record_bytes(phase, pending=pending)
        stage = self._stage(content)
        self._assert_all()
        # On failure retain any stage as evidence. The enclosing transition
        # poisons writes and separately reports source and journal effects.
        if self._read(stage[0], limit=MAX_RECORD_BYTES) != stage[1]:
            raise WorkspaceError("Journal staging entry changed before replacement")
        self._journal_attempted = True
        os.replace(stage[0], "record.json", src_dir_fd=self._fd, dst_dir_fd=self._fd)
        self._journal_committed = True
        self._capture_directory("root", changing=True)
        os.fsync(self._fd)
        result = self._read("record.json")
        if result.data != content or result.identity[:-1] != stage[1].identity[:-1]:
            raise WorkspaceError("Journal replacement did not read back exactly")
        self._tracked["record.json"] = result
        self._assert_all()

    def _transition(self, expected: FileState, guard: Callable[[], None], *, restore: bool):
        if self._busy:
            raise WorkspaceError("Reentrant workspace effects are not permitted")
        self._busy = True
        try:
            return self._transition_once(expected, guard, restore=restore)
        finally:
            self._busy = False

    def _transition_once(self, expected: FileState, guard: Callable[[], None], *, restore: bool):
        operation = "restore" if restore else "apply"
        required = "applied-after" if restore else "ready-before"
        next_state = "restored-before" if restore else "applied-after"
        content = self._before if restore else self._after
        if self._state != required:
            raise WorkspaceError("Workspace phase does not allow this one-use operation")
        if (
            type(expected) is not FileState
            or not callable(guard)
            or inspect.iscoroutinefunction(guard)
        ):
            raise WorkspaceError("A tracked state and synchronous decision guard are required")
        try:
            self._assert_all()
        except (OSError, WorkspaceError) as exc:
            self._state = "state-unconfirmed"
            raise WorkspaceError("Workspace changed before the requested operation") from exc
        if expected != self._tracked["app.py"]:
            raise WorkspaceError("Source state differs from the reviewed exact file")
        stage = None
        consumed = attempted = committed = False
        self._journal_attempted = self._journal_committed = False
        self._journal_phase = None
        failure = None
        try:
            stage = self._stage(content)
            self._assert_all()
            decision = guard()
            if decision is not None:
                if inspect.iscoroutine(decision):
                    decision.close()
                raise WorkspaceError("Decision guard must synchronously return None")
            self._assert_all()
            if self._read(stage[0], limit=MAX_RECORD_BYTES) != stage[1]:
                raise WorkspaceError("Source staging entry changed before replacement")
            # Durable intent precedes source rename. A crash or a failed final
            # journal cannot leave a trustworthy-looking ready-before record.
            self._state = "state-unconfirmed"
            self._persist_record("state-unconfirmed", pending=operation)
            self._assert_all()
            if self._read(stage[0], limit=MAX_RECORD_BYTES) != stage[1]:
                raise WorkspaceError("Source staging entry changed after intent persistence")
            # Not CAS: exclude hostile concurrent same-user writers.
            attempted = True
            os.replace(stage[0], "app.py", src_dir_fd=self._fd, dst_dir_fd=self._fd)
            consumed = committed = True
            self._capture_directory("root", changing=True)
            os.fsync(self._fd)
            result = self._read("app.py")
            if result.data != content or result.identity[:-1] != stage[1].identity[:-1]:
                raise WorkspaceError("Source replacement did not read back exactly")
            self._tracked["app.py"] = result
            self._assert_all()
            self._persist_record(next_state)
            self._state = next_state
            return result
        except BaseException as exc:
            failure = exc
            if not isinstance(exc, Exception):
                exc.workspace_commit_attempted = attempted
                exc.workspace_commit_uncertain = attempted or self._journal_attempted
                exc.workspace_committed = committed
            raise
        finally:
            cleanup_failure = None
            if stage is not None and not consumed:
                try:
                    self._discard(stage)
                except BaseException as exc:
                    cleanup_failure = exc
            uncertain = (
                self._journal_attempted
                or attempted
                or committed
                or cleanup_failure is not None
                or (failure is not None and self._state == "state-unconfirmed")
            )
            if uncertain and (failure is not None or cleanup_failure is not None):
                self._state = "state-unconfirmed"
                error = CommittedWriteError(
                    operation,
                    commit_attempted=attempted,
                    committed=committed,
                    cleanup_failed=cleanup_failure is not None,
                    journal_attempted=self._journal_attempted,
                    journal_committed=self._journal_committed,
                    journal_phase=self._journal_phase,
                )
                original = failure or cleanup_failure
                if (
                    cleanup_failure is not None
                    and not isinstance(cleanup_failure, Exception)
                    and (failure is None or isinstance(failure, Exception))
                ):
                    original = cleanup_failure
                if not isinstance(original, Exception):
                    original.workspace_commit_error = error
                    original.workspace_cleanup_failed = cleanup_failure is not None
                    original.workspace_journal_attempted = self._journal_attempted
                    original.workspace_journal_committed = self._journal_committed
                    original.workspace_journal_phase = self._journal_phase
                    original.workspace_commit_attempted = attempted
                    original.workspace_commit_uncertain = attempted or self._journal_attempted
                    original.workspace_committed = committed
                    if original is not failure:
                        raise original
                else:
                    raise error from original

    def apply_source(self, expected: FileState, *, guard: Callable[[], None]) -> FileState:
        """Replace app.py only with the validated after bytes; never execute it."""
        return self._transition(expected, guard, restore=False)

    def restore_source(self, expected: FileState, *, guard: Callable[[], None]) -> FileState:
        """Restore exact creation-time before bytes, preserving the generated test."""
        return self._transition(expected, guard, restore=True)
