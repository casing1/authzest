"""Private current-copy byte transitions for the synthetic owner's archived read.

Only the current coordinator supplies the preparation result and exact artifacts.
There is no path-based opener or saved-record importer. Files and uncertain writes
are retained. Atomic rename cannot exclude hostile concurrent same-user writers.
"""

from __future__ import annotations

import hashlib
import inspect
import os
import secrets
import stat
from collections.abc import Callable
from pathlib import Path

from authzest.codex.contracts import canonical, decode
from authzest.codex.owner_read_suggestion import BASELINE_SHA256, _validate_rule, _validate_test
from authzest.runner._generated_repair_workspace import FileState
from authzest.runner._owner_policy_file_workspace import _identity, _root_identity
from authzest.runner._owner_read_copy_files import FILES, copy_supported

_RECORD = "record.json"
_MAX_RECORD = 65_536
_LIMIT = 4096


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_guard(guard: Callable[[], None]) -> None:
    value = guard()
    if inspect.iscoroutine(value):
        value.close()
    if value is not None:
        raise ValueError("A synchronous guard must return None")


class OwnerReadWorkspaceError(RuntimeError):
    """Retained copy metadata accompanies a failed initialization or transition."""

    def __init__(self, workspace: OwnerReadWorkspace, message: str):
        super().__init__(message)
        self.path = workspace.path
        self.state = workspace.state
        self.stage = workspace._stage
        self.recovery_required = self.state == "state-unconfirmed"
        self.source_replace_attempted = workspace._replace_attempted
        self.source_replaced = workspace._replaced
        self.descriptor_cleanup_confirmed = None


class OwnerReadWorkspace:
    """Adopt one just-prepared copy, keep identities, and retain a durable journal.

    A guard is trusted synchronous coordination, never authenticated consent.
    It is checked before journal intent and again immediately before replacement.
    A separate commit_guard may perform the latter check for the same decision.
    """

    def __init__(
        self,
        prepared_copy: dict,
        baseline: bytes,
        test: bytes,
        proposed: bytes,
        *,
        binding_id: str,
    ):
        self.path = None
        self._fd = -1
        self._state = "state-unconfirmed"
        self._stage = "validate-preparation"
        self._busy = False
        self._replace_attempted = self._replaced = False
        self._tracked: dict[str, FileState] = {}
        self._temps: dict[str, FileState] = {}
        self._attempted: set[str] = set()
        self._pending = None
        self._history: list[dict] = []
        try:
            contents = (baseline, test, proposed)
            if (
                not copy_supported()
                or any(type(data) is not bytes or not 0 < len(data) <= _LIMIT for data in contents)
                or _sha(baseline) != BASELINE_SHA256
                or baseline == proposed
                or type(binding_id) is not str
                or not 0 < len(binding_id) <= 256
                or not binding_id.isascii()
                or not binding_id.isprintable()
                or type(prepared_copy) is not dict
                or prepared_copy.get("status") != "prepared"
                or type(prepared_copy.get("exit_code")) is not int
                or prepared_copy["exit_code"] != 0
                or prepared_copy.get("stage") != "complete"
                or prepared_copy.get("interrupted") is not False
                or type(prepared_copy.get("path")) is not str
                or type(prepared_copy.get("files")) is not dict
                or prepared_copy["files"].keys() != set(FILES)
            ):
                raise ValueError("Expected a current prepared owner-read copy")
            _validate_rule(proposed.decode("ascii"))
            _validate_test(test.decode("ascii"))
            self._contents = dict(zip(FILES, contents, strict=True))
            self._binding_id = binding_id
            self.path = Path(prepared_copy["path"])
            if not self.path.is_absolute() or self.path.resolve(strict=True) != self.path:
                raise ValueError("Expected the unchanged absolute preparation path")
            root = prepared_copy.get("root_identity")
            if type(root) is not list or len(root) != 5 or any(type(v) is not int for v in root):
                raise ValueError("Invalid prepared directory identity")
            self._root = tuple(root)
            self._stage = "open-prepared-directory"
            self._fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self._root_check()
            for name, data in self._contents.items():
                item = prepared_copy["files"][name]
                if (
                    type(item) is not dict
                    or item.get("state") != "verified"
                    or item.get("sha256") != _sha(data)
                    or type(item.get("identity")) is not list
                    or len(item["identity"]) != 9
                    or any(type(value) is not int for value in item["identity"])
                ):
                    raise ValueError("Invalid prepared file identity")
                self._tracked[name] = FileState(data, tuple(item["identity"]))
            self._stage = "verify-prepared-copy"
            self._assert_all()
            self._stage = "create-initial-record"
            record = self._record_bytes("ready-before")
            self._tracked[_RECORD] = self._create(_RECORD, record)
            os.fsync(self._fd)
            self._assert_all()
            self._state = "ready-before"
            self._stage = "ready-before"
        except BaseException as exc:
            failure = OwnerReadWorkspaceError(self, "Owner-read copy adoption failed")
            try:
                self.close()
                failure.descriptor_cleanup_confirmed = True
            except BaseException:
                failure.descriptor_cleanup_confirmed = False
            if isinstance(exc, Exception):
                raise failure from exc
            exc.owner_read_workspace_error = failure
            raise

    @property
    def state(self) -> str:
        return self._state

    def close(self) -> None:
        """Close the held descriptor and retain all files."""
        fd, self._fd = self._fd, -1
        if fd >= 0:
            os.close(fd)

    def _root_check(self) -> tuple[int, ...]:
        if self._fd < 0 or self.path is None:
            raise ValueError("Owner-read workspace is closed")
        info = os.fstat(self._fd)
        named = os.stat(self.path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.geteuid()
            or _root_identity(info) != self._root
            or _identity(named) != _identity(info)
        ):
            raise ValueError("Owner-read directory changed")
        return _identity(info)

    def _read(self, name: str) -> FileState:
        limit = _MAX_RECORD if name == _RECORD or name.startswith(".record-") else _LIMIT
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fd)
        try:
            initial = os.fstat(fd)
            if (
                not stat.S_ISREG(initial.st_mode)
                or stat.S_IMODE(initial.st_mode) != 0o600
                or initial.st_uid != os.geteuid()
                or initial.st_nlink != 1
                or not 0 < initial.st_size <= limit
            ):
                raise ValueError("Invalid owner-read file properties")
            data = bytearray()
            while len(data) <= initial.st_size:
                part = os.read(fd, initial.st_size + 1 - len(data))
                if not part:
                    break
                data.extend(part)
            if (
                len(data) != initial.st_size
                or _identity(os.fstat(fd)) != _identity(initial)
                or _identity(os.stat(name, dir_fd=self._fd, follow_symlinks=False))
                != _identity(initial)
            ):
                raise ValueError("Owner-read file changed during capture")
            return FileState(bytes(data), _identity(initial))
        finally:
            os.close(fd)

    def _assert_all(self) -> None:
        initial = self._root_check()
        expected = self._tracked | self._temps
        names = set()
        with os.scandir(self._fd) as entries:
            for entry in entries:
                if entry.name not in expected or entry.name in names:
                    raise ValueError("Unexpected owner-read directory entry")
                names.add(entry.name)
        if names != expected.keys():
            raise ValueError("Missing owner-read directory entry")
        for name, value in expected.items():
            if self._read(name) != value:
                raise ValueError("Tracked owner-read bytes or identity changed")
        if self._root_check() != initial:
            raise ValueError("Owner-read directory changed during capture")

    def _create(self, name: str, data: bytes) -> FileState:
        fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self._fd
        )
        try:
            os.fchmod(fd, 0o600)
            remaining = memoryview(data)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("Incomplete owner-read write")
                remaining = remaining[written:]
            os.fsync(fd)
            identity = _identity(os.fstat(fd))
        finally:
            os.close(fd)
        captured = self._read(name)
        if captured.data != data or captured.identity != identity:
            raise ValueError("Owner-read created file readback changed")
        return captured

    def _record_bytes(self, state: str, *, pending: str | None = None) -> bytes:
        value = {
            "schema_version": "1.0",
            "kind": "owner-read-private-workspace-record",
            "binding_id": self._binding_id,
            "state": state,
            "pending_operation": pending,
            "history": self._history,
            "root_identity": list(self._root),
            "artifacts": {
                name: {"sha256": _sha(data), "bytes": len(data)}
                for name, data in self._contents.items()
            },
            "files": {
                name: {"sha256": _sha(value.data), "identity": list(value.identity)}
                for name, value in (self._tracked | self._temps).items()
                if name != _RECORD
            },
            "execution_status": "not-run",
            "source_application": "applied-copy-only"
            if state in {"applied-after", "restored-before"}
            else "unknown"
            if state == "state-unconfirmed"
            else "not-run",
            "restoration_status": "restored-before" if state == "restored-before" else "not-run",
        }
        raw = canonical(value).encode("ascii")
        if len(raw) > _MAX_RECORD:
            raise ValueError("Owner-read journal exceeds its budget")
        return raw

    def _persist(self, state: str, *, pending: str | None = None) -> None:
        self._assert_all()
        name = ".record-" + secrets.token_hex(16)
        self._temps[name] = self._create(name, self._record_bytes(state, pending=pending))
        self._assert_all()
        staged = self._temps[name]
        os.replace(name, _RECORD, src_dir_fd=self._fd, dst_dir_fd=self._fd)
        del self._temps[name]
        result = self._read(_RECORD)
        if result.data != staged.data or result.identity[:-1] != staged.identity[:-1]:
            raise ValueError("Owner-read journal replacement readback changed")
        self._tracked[_RECORD] = result
        os.fsync(self._fd)
        self._assert_all()

    def _capture(self, name: str) -> FileState:
        try:
            self._assert_all()
            return self._tracked[name]
        except (OSError, ValueError) as exc:
            self._state = "state-unconfirmed"
            raise OwnerReadWorkspaceError(self, "Owner-read copy integrity is unconfirmed") from exc

    def read_source(self) -> FileState:
        return self._capture(FILES[0])

    def read_test(self) -> FileState:
        return self._capture(FILES[1])

    def read_record(self) -> FileState:
        return self._capture(_RECORD)

    def snapshot(self) -> dict:
        """Capture all current identities without importing any historical record."""
        self.read_source()
        return {
            "path": str(self.path),
            "binding_id": self._binding_id,
            "state": self.state,
            "root_identity": list(self._root),
            "files": {
                name: {"sha256": _sha(value.data), "identity": list(value.identity)}
                for name, value in self._tracked.items()
            },
        }

    def record_event(self, stage: str, details: dict) -> None:
        """Retain bounded coordinator metadata without changing source or test."""
        if (
            self._busy
            or self._state == "state-unconfirmed"
            or len(self._history) >= 32
            or type(stage) is not str
            or not 0 < len(stage) <= 64
            or not stage.isascii()
            or not stage.isprintable()
            or type(details) is not dict
        ):
            raise OwnerReadWorkspaceError(self, "Owner-read journal event is unavailable")
        encoded = canonical(details)
        if len(encoded.encode("ascii")) > 2048 or (
            len(canonical(self._history).encode("ascii")) + len(encoded.encode("ascii")) > 32768
        ):
            raise OwnerReadWorkspaceError(self, "Owner-read journal event exceeds its budget")
        event = {"sequence": len(self._history), "stage": stage, "details": decode(encoded)}
        self._busy = True
        self._stage = "record-event-" + stage
        try:
            self._assert_all()
            self._history.append(event)
            self._persist(self._state, pending=self._pending)
            self._stage = self._state
        except BaseException as exc:
            self._state = "state-unconfirmed"
            failure = OwnerReadWorkspaceError(self, "Owner-read journal event write failed")
            if isinstance(exc, Exception):
                raise failure from exc
            exc.owner_read_workspace_error = failure
            raise
        finally:
            self._busy = False

    def _transition(
        self,
        expected: FileState,
        guard: Callable[[], None],
        *,
        restore: bool,
        commit_guard: Callable[[], None] | None,
    ) -> FileState:
        operation = "restore" if restore else "apply"
        required = "applied-after" if restore else "ready-before"
        target = "restored-before" if restore else "applied-after"
        content = self._contents[FILES[0] if restore else FILES[2]]
        if (
            self._busy
            or self._state != required
            or operation in self._attempted
            or type(expected) is not FileState
            or not callable(guard)
            or inspect.iscoroutinefunction(guard)
            or commit_guard is not None
            and (not callable(commit_guard) or inspect.iscoroutinefunction(commit_guard))
        ):
            raise OwnerReadWorkspaceError(self, "Owner-read source transition is unavailable")
        self._busy = True
        self._attempted.add(operation)
        self._replace_attempted = self._replaced = False
        self._stage = "check-" + operation
        stage = None
        intent = False
        try:
            self._assert_all()
            if self._tracked[FILES[0]] != expected:
                raise ValueError("Owner-read source differs from reviewed state")
            self._stage = "stage-" + operation
            stage = ".source-" + secrets.token_hex(16)
            self._temps[stage] = self._create(stage, content)
            self._assert_all()
            _check_guard(guard)
            self._assert_all()
            self._stage = "persist-" + operation + "-intent"
            intent = True
            self._state = "state-unconfirmed"
            self._pending = operation
            self._persist("state-unconfirmed", pending=operation)
            self._assert_all()
            self._stage = "replace-" + operation
            _check_guard(commit_guard if commit_guard is not None else guard)
            self._replace_attempted = True
            os.replace(stage, FILES[0], src_dir_fd=self._fd, dst_dir_fd=self._fd)
            self._replaced = True
            staged = self._temps.pop(stage)
            source = self._read(FILES[0])
            # Rename can update ctime. Every other captured identity field must agree.
            if source.data != content or source.identity[:-1] != staged.identity[:-1]:
                raise ValueError("Owner-read replaced source readback changed")
            self._tracked[FILES[0]] = source
            os.fsync(self._fd)
            self._assert_all()
            self._stage = "persist-" + operation + "-completion"
            self._persist(target)
            self._state = target
            self._pending = None
            self._stage = target
            return source
        except BaseException as exc:
            # Before durable intent, remove only an unchanged file we created.
            if not intent and stage in self._temps:
                try:
                    self._assert_all()
                    os.unlink(stage, dir_fd=self._fd)
                    del self._temps[stage]
                    os.fsync(self._fd)
                    self._assert_all()
                except BaseException:
                    self._state = "state-unconfirmed"
            elif not intent and stage is not None:
                # An exclusive creation or its readback may have failed partway.
                self._state = "state-unconfirmed"
            if intent or self._stage == "check-" + operation:
                self._state = "state-unconfirmed"
            failure = OwnerReadWorkspaceError(self, "Owner-read source transition failed")
            if isinstance(exc, Exception):
                raise failure from exc
            exc.owner_read_workspace_error = failure
            raise
        finally:
            self._busy = False

    def apply_source(
        self,
        expected: FileState,
        *,
        guard: Callable[[], None],
        commit_guard: Callable[[], None] | None = None,
    ) -> FileState:
        """Apply the captured proposed rule exactly once to the owned private copy."""
        return self._transition(expected, guard, restore=False, commit_guard=commit_guard)

    def restore_source(
        self,
        expected: FileState,
        *,
        guard: Callable[[], None],
        commit_guard: Callable[[], None] | None = None,
    ) -> FileState:
        """Restore creation-time baseline bytes while preserving the captured test."""
        return self._transition(expected, guard, restore=True, commit_guard=commit_guard)
