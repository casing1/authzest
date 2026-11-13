"""Private retained input snapshots; no mount, engine, executor or consent API.

Only exact live workspace objects enter this helper. Held descriptors and bounded
membership/readback checks detect changes; they are not an OS sandbox or atomic
compare-and-swap against a hostile concurrent same-user writer. Closing retains
all files, including partial initialization evidence.
"""

from __future__ import annotations

import hashlib
import inspect
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from authzest.codex.contracts import canonical, decode, identity
from authzest.runner._generated_repair_runtime_profile import build_container_create_plan
from authzest.runner._generated_repair_workspace import (
    MAX_RECORD_BYTES,
    MAX_SOURCE_BYTES,
    FileState,
    GeneratedRepairWorkspace,
    _identity,
)
from authzest.runner._generated_repair_workspace import supported as workspace_supported

_TEST = "tests/test_generated_ownership.py"
_FILES = ("app.py", _TEST, "record.json")


class StageError(RuntimeError):
    """A stage is unsupported, closed, changed or otherwise unconfirmed."""


class StageInitializationError(StageError):
    """A single attempted creation failed; do not retry or remove unknown paths."""

    def __init__(
        self,
        *,
        created_path: Path | None,
        planned_path: Path,
        stage: str,
        file_states: dict,
        allocation_attempted: bool,
        creation_confirmed: bool,
        ownership_uncertain: bool,
        descriptor_cleanup_confirmed: bool,
    ):
        super().__init__("Input stage initialization failed; retain and inspect its recorded state")
        self.created_path = created_path
        self.planned_path = planned_path
        self.stage = self.initialization_stage = stage
        self.file_states = dict(file_states)
        self.allocation_attempted = allocation_attempted
        self.creation_confirmed = creation_confirmed
        self.ownership_uncertain = ownership_uncertain
        self.descriptor_cleanup_confirmed = descriptor_cleanup_confirmed


@dataclass(frozen=True, slots=True)
class StagedCreatePlan:
    """Historical stage evidence and unexecuted argv, not a resumable capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return "generated-repair-staged-create-plan-" + identity(self.to_dict())


def supported() -> bool:
    return workspace_supported() and os.scandir in os.supports_fd


def _evidence(value: FileState) -> dict:
    return {
        "sha256": hashlib.sha256(value.data).hexdigest(),
        "identity": list(value.identity),
    }


class GeneratedRepairInputStage:
    """One fresh T/A input snapshot for one exact live copy checkpoint.

    A synchronous preallocation hook is trusted coordination, not permission or
    a clock. Exported snapshots/records cannot reopen or refresh this object.
    """

    def __init__(self, copy, candidate, role, *, _before_create=None):
        if (
            type(copy) is not GeneratedRepairWorkspace
            or type(candidate) is not str
            or candidate not in {"before", "after"}
            or type(role) is not str
            or role not in {"T", "A"}
            or not supported()
        ):
            raise StageError("Supported live T/A workspace staging is required")
        if _before_create is not None and (
            not callable(_before_create) or inspect.iscoroutinefunction(_before_create)
        ):
            raise StageError("Stage allocation hook must be synchronous")
        self._copy, self._candidate, self._role = copy, candidate, role
        self._phase = "ready-before" if candidate == "before" else "applied-after"
        self._state = "state-unconfirmed"
        self._busy = True
        self._reentry_refused = False
        self._fds = dict.fromkeys(("parent", "root", "input", "tests"), -1)
        self._directories: dict[str, tuple[int, ...]] = {}
        self._modes = {"root": 0o700, "input": 0o700, "tests": 0o700}
        self._members = {"root": set(), "input": set(), "tests": set()}
        self._tracked: dict[str, FileState] = {}
        self._partial = dict.fromkeys(("outer", "input", "tests", *_FILES), "not-created")
        if role == "A":
            self._partial["tests"] = self._partial[_TEST] = "not-planned"
        self._path = None
        self._parent_path = copy.path.parent
        self._name = "authzest-generated-inputs-" + uuid.uuid4().hex
        self._planned_path = self._parent_path / self._name
        self._allocation_attempted = self._creation_confirmed = False
        self._ownership_uncertain = False
        self._descriptor_cleanup_confirmed = True
        self._closure_uncertain = False
        self._cleanup_failure = None
        stage = "capture-original-checkpoint"
        try:
            self._checkpoint = self._capture_copy()
            stage = "open-original-parent"
            self._fds["parent"] = self._open_fd(
                self._parent_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
            )
            self._parent_identity = _identity(os.fstat(self._fds["parent"]))[:5]
            self._check_parent()
            stage = "allocation-guard"
            if _before_create is not None:
                decision = _before_create()
                if decision is not None:
                    if inspect.iscoroutine(decision):
                        decision.close()
                    raise StageError("Stage allocation hook must synchronously return None")
            stage = "recheck-before-allocation"
            self._assert_copy()
            self._check_parent()
            stage = "create-outer"
            self._allocation_attempted = True
            self._partial["outer"] = "creation-attempted"
            try:
                result = os.mkdir(self._name, 0o700, dir_fd=self._fds["parent"])
            except FileExistsError:
                raise
            except BaseException:
                self._ownership_uncertain = True
                raise
            if result is not None:
                if inspect.iscoroutine(result):
                    result.close()
                self._ownership_uncertain = True
                raise StageError("Stage directory creation is unconfirmed")
            self._creation_confirmed = True
            self._path = self._planned_path
            self._partial["outer"] = "created-unconfirmed"
            stage = "open-outer"
            self._fds["root"] = self._open_dir(self._name, "parent")
            os.fchmod(self._fds["root"], 0o700)
            self._refresh("root", changing=True)
            self._partial["outer"] = "confirmed"
            os.fsync(self._fds["parent"])
            stage = "create-input-directory"
            self._create_directory("input", "root", "input")
            if role == "T":
                stage = "create-test-directory"
                self._create_directory("tests", "input", "tests")
            self._assert_copy()
            stage = "materialize-app"
            self._create_file("app.py", self._checkpoint[0].data)
            if role == "T":
                stage = "materialize-test"
                self._create_file(_TEST, self._checkpoint[1].data)
            stage = "seal-input-directories"
            for kind in ("tests", "input") if role == "T" else ("input",):
                os.fchmod(self._fds[kind], 0o555)
                self._modes[kind] = 0o555
                self._refresh(kind, changing=True, mode_changed=True)
                os.fsync(self._fds[kind])
            self._assert_copy()
            self._assert_stage()
            stage = "create-host-record"
            record = {
                "schema_version": "1.0",
                "kind": "generated-repair-input-stage-record",
                "candidate": candidate,
                "role": role,
                "original_checkpoint": self._checkpoint_evidence(),
                "outer_core_identity": list(self._directories["root"][:5]),
                "input_directories": {
                    key: list(value) for key, value in self._directories.items() if key != "root"
                },
                "input_files": {key: _evidence(value) for key, value in self._tracked.items()},
            }
            self._create_file("record.json", canonical(record).encode("utf-8"))
            stage = "sync-and-recheck-complete-stage"
            os.fsync(self._fds["root"])
            self._assert_copy()
            self._assert_stage()
            self._state = "staged-" + candidate
        except BaseException as exc:
            self._state = "state-unconfirmed"
            cleanup = self._close_descriptors()
            failure = StageInitializationError(
                created_path=self._path,
                planned_path=self._planned_path,
                stage=stage,
                file_states=self._partial,
                allocation_attempted=self._allocation_attempted,
                creation_confirmed=self._creation_confirmed,
                ownership_uncertain=self._ownership_uncertain,
                descriptor_cleanup_confirmed=cleanup is None,
            )
            failure.primary_failure = getattr(exc, "stage_primary_failure", exc)
            failure.cleanup_failure = self._cleanup_failure or cleanup
            original = exc
            if (
                cleanup is not None
                and not isinstance(cleanup, Exception)
                and isinstance(exc, Exception)
            ):
                original = cleanup
            if not isinstance(original, Exception):
                original.stage_initialization = original.staging_initialization = failure
                if original is exc:
                    raise
                raise original from exc
            raise failure from exc
        finally:
            self._busy = False

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def input_path(self) -> Path | None:
        return None if self._path is None else self._path / "input"

    @property
    def state(self) -> str:
        return self._state

    def _capture_copy(self) -> tuple[FileState, FileState, FileState]:
        if self._copy.state != self._phase or getattr(self._copy, "_busy", False):
            raise StageError("Original copy phase is unavailable")
        values = (self._copy.read_source(), self._copy.read_test(), self._copy.read_record())
        if self._copy.state != self._phase or getattr(self._copy, "_busy", False):
            raise StageError("Original copy phase changed")
        if any(type(value) is not FileState for value in values):
            raise StageError("Original copy checkpoint is malformed")
        for value in values[:2]:
            if type(value.data) is not bytes or len(value.data) > MAX_SOURCE_BYTES:
                raise StageError("Original input exceeds the fixed byte budget")
            value.data.decode("utf-8", errors="strict")
        return values

    def _assert_copy(self) -> None:
        if self._reentry_refused:
            raise StageError("Reentrant stage access invalidated the operation")
        if self._capture_copy() != self._checkpoint:
            raise StageError("Original copy checkpoint changed")

    def _check_parent(self) -> None:
        fd = self._fds["parent"]
        if fd < 0:
            raise StageError("Stage parent descriptor is closed")
        opened = os.fstat(fd)
        named = os.stat(self._parent_path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or _identity(opened)[:5] != self._parent_identity
            or _identity(named)[:5] != self._parent_identity
        ):
            raise StageError("Original parent identity changed")

    def _open_dir(self, name: str, parent: str) -> int:
        return self._open_fd(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=self._fds[parent],
        )

    def _open_fd(self, *args, **kwargs) -> int:
        try:
            fd = os.open(*args, **kwargs)
            if type(fd) is not int or fd < 0:
                if inspect.iscoroutine(fd):
                    fd.close()
                raise StageError("Descriptor acquisition is unconfirmed")
            return fd
        except BaseException as exc:
            self._closure_uncertain = True
            if self._cleanup_failure is None:
                self._cleanup_failure = exc
            raise

    def _directory(self, kind: str) -> os.stat_result:
        self._check_parent()
        fd = self._fds[kind]
        if fd < 0:
            raise StageError("Stage descriptor is closed")
        opened = os.fstat(fd)
        parent, leaf = {
            "root": ("parent", self._name),
            "input": ("root", "input"),
            "tests": ("input", "tests"),
        }[kind]
        named = os.stat(leaf, dir_fd=self._fds[parent], follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != self._modes[kind]
            or _identity(opened) != _identity(named)
        ):
            raise StageError("Stage directory identity or permissions changed")
        return opened

    def _refresh(self, kind: str, *, changing=False, mode_changed=False) -> None:
        current = _identity(self._directory(kind))
        previous = self._directories.get(kind)
        if previous is not None:
            stable = (0, 1, 3, 4) if mode_changed else (0, 1, 2, 3, 4)
            if any(current[index] != previous[index] for index in stable) or (
                not changing and current != previous
            ):
                raise StageError("Stage directory changed unexpectedly")
        self._directories[kind] = current

    def _membership(self, kind: str) -> None:
        expected = self._members[kind]
        directory_pin = _identity(self._directory(kind))
        seen = set()
        try:
            iterator = os.scandir(self._fds[kind])
            if inspect.iscoroutine(iterator):
                iterator.close()
                raise StageError("Directory iterator acquisition is unconfirmed")
            closer = iterator.close
            if not callable(closer):
                raise StageError("Directory iterator closure is unavailable")
        except BaseException as exc:
            self._closure_uncertain = True
            if self._cleanup_failure is None:
                self._cleanup_failure = exc
            raise
        failure = None
        try:
            for count, entry in enumerate(iterator, 1):
                if (
                    count > len(expected)
                    or type(entry.name) is not str
                    or entry.name not in expected
                ):
                    raise StageError("Unexpected stage directory membership")
                if entry.name in seen:
                    raise StageError("Duplicate stage directory entry")
                seen.add(entry.name)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            self._close_resource(closer, failure)
        if seen != expected:
            raise StageError("Stage directory membership changed")
        if _identity(self._directory(kind)) != directory_pin:
            raise StageError("Stage directory changed during enumeration")

    def _location(self, name: str) -> tuple[str, str]:
        if name == _TEST:
            return "tests", "test_generated_ownership.py"
        return ("root", name) if name == "record.json" else ("input", name)

    def _read(self, name: str) -> FileState:
        kind, leaf = self._location(name)
        limit = MAX_RECORD_BYTES if name == "record.json" else MAX_SOURCE_BYTES
        fd = self._open_fd(
            leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fds[kind]
        )
        failure = None
        try:
            before = os.fstat(fd)
            mode = 0o600 if name == "record.json" else 0o444
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != mode
                or not 0 <= before.st_size <= limit
            ):
                raise StageError("Expected bounded owned single-link stage file")
            chunks, remaining = [], limit + 1
            while remaining:
                maximum = min(remaining, MAX_SOURCE_BYTES)
                chunk = os.read(fd, maximum)
                if type(chunk) is not bytes or len(chunk) > maximum:
                    if inspect.iscoroutine(chunk):
                        chunk.close()
                    raise StageError("Stage read exceeded its requested bound")
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
            pin = _identity(before)
            if (
                len(content) != before.st_size
                or len(content) > limit
                or _identity(os.fstat(fd)) != pin
                or _identity(os.stat(leaf, dir_fd=self._fds[kind], follow_symlinks=False)) != pin
            ):
                raise StageError("Stage file changed while reading")
            content.decode("utf-8", errors="strict")
            result = FileState(content, pin)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            self._close_resource(lambda: os.close(fd), failure)
        if _identity(os.stat(leaf, dir_fd=self._fds[kind], follow_symlinks=False)) != pin:
            raise StageError("Stage file changed after descriptor closure")
        return result

    def _assert_stage(self) -> None:
        for kind, pin in self._directories.items():
            if _identity(self._directory(kind)) != pin:
                raise StageError("Stage directory checkpoint changed")
            self._membership(kind)
        for name, pin in self._tracked.items():
            if self._read(name) != pin:
                raise StageError("Stage file checkpoint changed")
        for kind, pin in self._directories.items():
            if _identity(self._directory(kind)) != pin:
                raise StageError("Stage directory changed during verification")
            self._membership(kind)

    def _create_directory(self, name: str, parent: str, kind: str) -> None:
        self._assert_stage()
        self._partial[kind] = "creation-attempted"
        os.mkdir(name, 0o700, dir_fd=self._fds[parent])
        self._partial[kind] = "created-unconfirmed"
        self._members[parent].add(name)
        self._refresh(parent, changing=True)
        self._fds[kind] = self._open_dir(name, parent)
        os.fchmod(self._fds[kind], 0o700)
        self._refresh(kind, changing=True)
        os.fsync(self._fds[parent])
        self._partial[kind] = "confirmed"

    def _create_file(self, name: str, content: bytes) -> None:
        self._assert_copy()
        self._assert_stage()
        limit = MAX_RECORD_BYTES if name == "record.json" else MAX_SOURCE_BYTES
        if type(content) is not bytes or len(content) > limit:
            raise StageError("Stage file exceeds its fixed byte budget")
        content.decode("utf-8", errors="strict")
        kind, leaf = self._location(name)
        self._partial[name] = "creation-attempted"
        fd = self._open_fd(
            leaf,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=self._fds[kind],
        )
        failure = None
        try:
            self._partial[name] = "created-unconfirmed"
            self._members[kind].add(leaf)
            pending = memoryview(content)
            while pending:
                written = os.write(fd, pending)
                if type(written) is not int or not 0 < written <= len(pending):
                    if inspect.iscoroutine(written):
                        written.close()
                    raise StageError("Incomplete stage write")
                pending = pending[written:]
            os.fchmod(fd, 0o600 if name == "record.json" else 0o444)
            os.fsync(fd)
            pin = _identity(os.fstat(fd))
            if _identity(os.stat(leaf, dir_fd=self._fds[kind], follow_symlinks=False)) != pin:
                raise StageError("Created stage file name changed")
        except BaseException as exc:
            failure = exc
            raise
        finally:
            self._close_resource(lambda: os.close(fd), failure)
        self._refresh(kind, changing=True)
        result = self._read(name)
        if result != FileState(content, pin):
            raise StageError("Stage file did not read back exactly")
        self._tracked[name] = result
        self._partial[name] = "confirmed"
        os.fsync(self._fds[kind])

    def _checkpoint_evidence(self) -> dict:
        return {
            "phase": self._phase,
            "source": _evidence(self._checkpoint[0]),
            "test": _evidence(self._checkpoint[1]),
            "record": _evidence(self._checkpoint[2]),
        }

    def _snapshot(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "generated-repair-input-stage-snapshot",
            "candidate": self._candidate,
            "role": self._role,
            "state": self._state,
            "path": str(self._path),
            "input_path": str(self.input_path),
            "original_checkpoint": self._checkpoint_evidence(),
            "directories": {key: list(value) for key, value in self._directories.items()},
            "files": {key: _evidence(value) for key, value in self._tracked.items()},
            "filesystem_observed": True,
            "runtime_invoked": False,
            "execution_authorized": False,
            "authorization_status": "unknown",
            "verified_fix": False,
            "evidence": "historical-current-file-observation-not-runtime-or-resume-authority",
        }

    def _enter(self) -> None:
        if self._busy:
            self._reentry_refused = True
            self._state = "state-unconfirmed"
            raise StageError("Reentrant stage operations are not permitted")
        if self._state != "staged-" + self._candidate:
            raise StageError("Stage is closed or unconfirmed")
        self._busy = True

    def _checked(self) -> None:
        self._assert_copy()
        self._assert_stage()
        self._assert_copy()

    def assert_current(self) -> None:
        self._enter()
        try:
            self._checked()
        except BaseException as exc:
            self._state = "state-unconfirmed"
            if not isinstance(exc, Exception):
                raise
            raise StageError("Input stage integrity is unconfirmed") from exc
        finally:
            self._busy = False

    def snapshot(self) -> dict:
        self._enter()
        try:
            self._checked()
            result = self._snapshot()
            self._checked()
            return result
        except BaseException as exc:
            self._state = "state-unconfirmed"
            if not isinstance(exc, Exception):
                raise
            raise StageError("Input stage snapshot is unconfirmed") from exc
        finally:
            self._busy = False

    def prepare_create(self, profile, session_nonce, role_nonce) -> StagedCreatePlan:
        self._enter()
        try:
            self._checked()
            before = self._snapshot()
            parameters = {
                "session_nonce": session_nonce,
                "role_nonce": role_nonce,
                "staging_root": str(self.input_path),
                "application_sha256": hashlib.sha256(self._checkpoint[0].data).hexdigest(),
            }
            if self._role == "T":
                parameters["test_sha256"] = hashlib.sha256(self._checkpoint[1].data).hexdigest()
            try:
                plan = build_container_create_plan(profile, self._role, **parameters)
            finally:
                self._checked()
            if self._snapshot() != before:
                raise StageError("Input stage changed during create planning")
            result = {
                "schema_version": "1.0",
                "kind": "generated-repair-staged-create-plan",
                "stage_snapshot": before,
                "container_create_plan": plan.to_dict(),
                "status": "planned-not-executed",
                "filesystem_observed": True,
                "runtime_invoked": False,
                "execution_authorized": False,
                "authorization_status": "unknown",
                "verified_fix": False,
            }
            raw = canonical(result)
            decode(raw)
            self._checked()
            return StagedCreatePlan(raw)
        except BaseException as exc:
            self._state = "state-unconfirmed"
            if not isinstance(exc, Exception):
                raise
            raise StageError("Staged create planning is unconfirmed") from exc
        finally:
            self._busy = False

    def _close_resource(self, callback, primary=None) -> None:
        try:
            result = callback()
            if result is not None:
                if inspect.iscoroutine(result):
                    result.close()
                raise StageError("Resource closure is unconfirmed")
        except BaseException as cleanup:
            self._closure_uncertain = True
            if self._cleanup_failure is None:
                self._cleanup_failure = cleanup
            if primary is not None:
                primary.stage_cleanup_failure = cleanup
                if not isinstance(cleanup, Exception) and isinstance(primary, Exception):
                    cleanup.stage_primary_failure = primary
                    raise cleanup
                raise primary from cleanup
            raise

    def _close_descriptors(self):
        failure = None
        for kind in ("tests", "input", "root", "parent"):
            fd, self._fds[kind] = self._fds[kind], -1
            if fd >= 0:
                try:
                    result = os.close(fd)
                    if result is not None:
                        if inspect.iscoroutine(result):
                            result.close()
                        raise StageError("Descriptor closure is unconfirmed")
                except BaseException as exc:
                    self._closure_uncertain = True
                    if self._cleanup_failure is None:
                        self._cleanup_failure = exc
                    if failure is None or (
                        isinstance(failure, Exception) and not isinstance(exc, Exception)
                    ):
                        failure = exc
        if failure is None and self._closure_uncertain:
            failure = StageError("Prior resource closure remains unconfirmed")
        self._descriptor_cleanup_confirmed = failure is None and not self._closure_uncertain
        return failure

    def close(self) -> None:
        """Close held descriptors only; never chmod, unlink or delete evidence."""
        if self._busy:
            self._reentry_refused = True
            self._state = "state-unconfirmed"
            raise StageError("Reentrant stage closure is not permitted")
        self._busy = True
        try:
            failure = self._close_descriptors()
            if failure is not None:
                self._state = "state-unconfirmed"
                if not isinstance(failure, Exception):
                    raise failure
                raise StageError("Stage descriptor closure is unconfirmed") from failure
            if self._state != "state-unconfirmed":
                self._state = "closed"
        finally:
            self._busy = False
