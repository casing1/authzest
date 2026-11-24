"""Retained sealed HTTP A inputs; no guest, Engine or execution authority.

Only a current live HTTP source-only session can supply measured bytes.
Descriptor-relative checks detect ordinary edits and replacements; they are not
atomic against a hostile same-user writer. Exported records and stopped-create
plans cannot reopen this object.
"""

from __future__ import annotations

import inspect
import os
import stat
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import canonical, decode, identity
from authzest.codex.repository_http_proposal import (
    validate_repository_http_request,
    validate_repository_http_response,
)
from authzest.runner._repository_http_files import _identity
from authzest.runner._repository_http_files import supported as files_supported
from authzest.runner._repository_http_manifest import build_guest_manifest, validate_guest_manifest
from authzest.runner._repository_http_runtime_profile import build_container_create_plan
from authzest.runner.repository_http_cases import validate_repository_http_cases
from authzest.runner.repository_http_file_session import RepositoryHttpFileSession
from authzest.runner.repository_http_verification import validate_repository_http_verification_plan

_MAX_FILE = 16_384
_MAX_RECORD = 65_536


class RepositoryHttpStageError(RuntimeError):
    """Closed staging failure; no source or private paths appear in the message."""


class RepositoryHttpStageInitializationError(RepositoryHttpStageError):
    """Retain partial evidence and inspect it; no automatic retry or deletion."""

    def __init__(
        self,
        *,
        created_path,
        planned_path,
        stage,
        file_states,
        allocation_attempted,
        creation_confirmed,
        ownership_uncertain,
        descriptor_cleanup_confirmed,
    ):
        super().__init__("Repository input staging failed; retain its recorded state")
        self.created_path, self.planned_path = created_path, planned_path
        self.stage = self.initialization_stage = stage
        self.file_states = dict(file_states)
        self.allocation_attempted = allocation_attempted
        self.creation_confirmed = creation_confirmed
        self.ownership_uncertain = ownership_uncertain
        self.descriptor_cleanup_confirmed = descriptor_cleanup_confirmed


@dataclass(frozen=True, slots=True)
class _File:
    data: bytes
    identity: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RepositoryHttpStagedCreatePlan:
    """Detached historical file observations and unexecuted command data."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return "repository-http-staged-create-plan-" + identity(self.to_dict())


def supported() -> bool:
    return files_supported() and os.scandir in os.supports_fd


def _hash(value: bytes) -> str:
    return sha256(value).hexdigest()


def _evidence(value: _File) -> dict:
    return {"sha256": _hash(value.data), "identity": list(value.identity)}


class RepositoryHttpInputStage:
    """One sealed A-only tree bound to an exact live HTTP source-file checkpoint.

    ``_before_create`` is a trusted synchronous coordination hook, not permission.
    Closing retains all files and never changes sealed permissions.
    """

    def __init__(self, session, request, response, cases, plan, phase, *, _before_create=None):
        if (
            type(self) is not RepositoryHttpInputStage
            or type(session) is not RepositoryHttpFileSession
            or type(phase) is not str
            or phase not in {"before", "after"}
            or not supported()
        ):
            raise RepositoryHttpStageError("A supported live HTTP A repository stage is required")
        if _before_create is not None and (
            not callable(_before_create)
            or inspect.iscoroutinefunction(_before_create)
            or inspect.isgeneratorfunction(_before_create)
            or inspect.isasyncgenfunction(_before_create)
        ):
            raise RepositoryHttpStageError("Stage allocation hook must be synchronous")
        self._session, self._phase, self._role = session, phase, "A"
        self._state, self._busy, self._reentry_refused = "state-unconfirmed", True, False
        self._fds: dict[str, int] = {}
        self._parents: list[tuple[int | None, str, int, tuple[int, ...]]] = []
        self._directories: dict[str, tuple[int, ...]] = {}
        self._modes: dict[str, int] = {}
        self._members: dict[str, set[str]] = {}
        self._tracked: dict[str, _File] = {}
        self._partial = {"outer": "not-created"}
        self._path = None
        self._allocation_attempted = self._creation_confirmed = False
        self._ownership_uncertain = self._closure_uncertain = False
        self._descriptor_cleanup_confirmed = False
        self._cleanup_failure = None
        self._planned_path = None
        stage = "bind-current-inputs"
        try:
            self._checkpoint = session._capture_runtime_checkpoint(phase)
            self._bind(request, response, cases, plan)
            self._parent_path = self._checkpoint.private_root.parent
            self._name = "authzest-repository-http-inputs-" + uuid.uuid4().hex
            self._planned_path = self._parent_path / self._name
            stage = "open-private-parent"
            self._open_parent()
            stage = "allocation-hook"
            if _before_create is not None:
                result = _before_create()
                if result is not None:
                    if inspect.iscoroutine(result):
                        result.close()
                    raise RepositoryHttpStageError("Stage allocation hook must return None")
            self._assert_copy()
            self._check_parents()
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
                raise RepositoryHttpStageError("Stage allocation is unconfirmed")
            self._creation_confirmed = True
            self._path = self._planned_path
            self._partial["outer"] = "created-unconfirmed"
            self._open_directory("", self._name, "parent")
            self._partial["outer"] = "confirmed"
            os.fsync(self._fds["parent"])
            stage = "materialize-inputs"
            for name in self._input_materials:
                self._ensure_directories("input/" + name)
                self._create_file("input/" + name, self._input_materials[name])
            stage = "seal-input-directories"
            for name in sorted(
                (n for n in self._directories if n), key=lambda n: (n.count("/"), n), reverse=True
            ):
                self._assert_stage()
                os.fchmod(self._fds[name], 0o555)
                self._modes[name] = 0o555
                self._refresh(name, changing=True, mode_changed=True)
                os.fsync(self._fds[name])
            self._assert_copy()
            self._assert_stage()
            stage = "create-host-record"
            record = {
                "schema_version": "2.0",
                "kind": "repository-http-input-stage-record",
                "phase": phase,
                "role": "A",
                "verification_plan_id": self._plan_id,
                "checkpoint": self._checkpoint_evidence(),
                "manifest": self._manifest,
                "outer_core_identity": list(self._directories[""][:5]),
                "input_directories": {k: list(v) for k, v in self._directories.items() if k},
                "input_files": {k: _evidence(v) for k, v in self._tracked.items()},
                "execution_status": "not-run",
                "verified_fix": False,
            }
            self._create_file("record.json", canonical(record).encode("utf-8"))
            stage = "recheck-complete-stage"
            os.fsync(self._fds[""])
            self._checked()
            self._state = "staged-" + phase
        except BaseException as exc:
            self._state = "state-unconfirmed"
            cleanup = self._close_descriptors()
            failure = RepositoryHttpStageInitializationError(
                created_path=self._path,
                planned_path=self._planned_path,
                stage=stage,
                file_states=self._partial,
                allocation_attempted=self._allocation_attempted,
                creation_confirmed=self._creation_confirmed,
                ownership_uncertain=self._ownership_uncertain,
                descriptor_cleanup_confirmed=cleanup is None,
            )
            failure.primary_failure = getattr(exc, "repository_http_stage_primary_failure", exc)
            failure.cleanup_failure = self._cleanup_failure or cleanup
            original = exc
            if (
                cleanup is not None
                and not isinstance(cleanup, Exception)
                and isinstance(exc, Exception)
            ):
                original = cleanup
            if not isinstance(original, Exception):
                original.repository_http_stage_initialization = failure
                if original is exc:
                    raise
                raise original from exc
            raise failure from exc
        finally:
            self._busy = False

    def _bind(self, request, response, cases, plan):
        checked = validate_repository_http_request(request)
        context = checked.to_dict()
        checked_response = validate_repository_http_response(canonical(response), checked)
        checked_cases = validate_repository_http_cases(cases)
        validated_plan = validate_repository_http_verification_plan(
            plan, checked, checked_response, checked_cases
        )
        cp = self._checkpoint
        if (
            checked_response["status"] != "proposed-change"
            or checked.payload_json != cp.request.payload_json
            or canonical(checked_response) != canonical(cp.response)
            or checked_cases.payload_json != cp.cases.payload_json
            or validated_plan.payload_json != cp.verification_plan.payload_json
            or cp.phase != self._phase
        ):
            raise RepositoryHttpStageError("Current HTTP inputs differ from the live file session")
        source = context["selection"]["files"][0]
        path = source["path"]
        expected = (
            source["text"]
            if self._phase == "before"
            else checked_response["proposal"]["after_text"]
        ).encode("utf-8")
        if (
            cp.source_path != path
            or cp.source_bytes != expected
            or cp.materials != ((path, expected),)
        ):
            raise RepositoryHttpStageError("Current private source bytes differ from the proposal")
        self._manifest = build_guest_manifest(
            checked.request_id,
            context["http_interface"],
            {"path": path, "sha256": _hash(cp.source_bytes), "size_bytes": len(cp.source_bytes)},
        )
        self._plan_id = validated_plan.plan_id
        self._input_materials = {
            "manifest.json": canonical(self._manifest).encode("utf-8"),
            "project/" + path: cp.source_bytes,
        }

    def __copy__(self):
        raise TypeError("Live HTTP repository stages cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live HTTP repository stages cannot be copied")

    def __reduce__(self):
        raise TypeError("Live HTTP repository stages cannot be serialized")

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def input_path(self) -> Path | None:
        return None if self._path is None else self._path / "input"

    @property
    def state(self) -> str:
        return self._state

    @property
    def descriptor_cleanup_confirmed(self) -> bool:
        """Historical close observation only, never a claim about guest cleanup."""
        return self._descriptor_cleanup_confirmed

    @property
    def manifest(self) -> dict:
        """Detached declaration only; use snapshot() for refreshed file observations."""
        return validate_guest_manifest(self._manifest)

    def _assert_copy(self):
        if self._reentry_refused:
            raise RepositoryHttpStageError("Reentrant staging invalidated the operation")
        self._session._recheck_runtime_checkpoint(self._checkpoint)
        if self._reentry_refused:
            raise RepositoryHttpStageError("Reentrant staging invalidated the operation")

    def _open_fd(self, *args, **kwargs):
        try:
            fd = os.open(*args, **kwargs)
            if type(fd) is not int or fd < 0:
                if inspect.iscoroutine(fd):
                    fd.close()
                raise RepositoryHttpStageError("Descriptor acquisition is unconfirmed")
            return fd
        except BaseException as exc:
            self._closure_uncertain = True
            self._cleanup_failure = self._cleanup_failure or exc
            raise

    def _open_parent(self):
        path = self._parent_path
        if not isinstance(path, Path) or not path.is_absolute() or len(path.parts) > 64:
            raise RepositoryHttpStageError("Stage parent is unsupported")
        parent = None
        for index, name in enumerate((path.anchor, *path.parts[1:])):
            fd = self._open_fd(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            self._fds["parent-" + str(index)] = fd
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise RepositoryHttpStageError("Stage parent must contain real directories")
            self._parents.append((parent, name, fd, _identity(info)[:5]))
            parent = fd
        info = os.fstat(parent)
        if not (
            info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o700
            or info.st_uid == 0
            and info.st_mode & stat.S_ISVTX
        ):
            raise RepositoryHttpStageError("Stage parent permissions are unsupported")
        self._fds["parent"] = parent  # Alias only; closure deduplicates descriptors.
        self._check_parents()

    def _check_parents(self):
        for parent, name, fd, expected in self._parents:
            if (
                _identity(os.fstat(fd))[:5] != expected
                or _identity(os.stat(name, dir_fd=parent, follow_symlinks=False))[:5] != expected
            ):
                raise RepositoryHttpStageError("Stage parent identity changed")

    def _open_directory(self, relative, leaf, parent):
        fd = self._open_fd(
            leaf,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=self._fds[parent],
        )
        self._fds[relative] = fd
        self._modes[relative], self._members[relative] = 0o700, set()
        opened = os.fstat(fd)
        named = os.stat(leaf, dir_fd=self._fds[parent], follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or _identity(opened) != _identity(named)
            or stat.S_IMODE(opened.st_mode) & ~0o700
        ):
            raise RepositoryHttpStageError("Created stage directory is unconfirmed")
        os.fchmod(fd, 0o700)
        self._refresh(relative, changing=True)

    def _directory(self, name):
        self._check_parents()
        fd = self._fds[name]
        if fd < 0:
            raise RepositoryHttpStageError("Stage directory is closed")
        if name:
            parent, _, leaf = name.rpartition("/")
        else:
            parent, leaf = "parent", self._name
        opened = os.fstat(fd)
        named = os.stat(leaf, dir_fd=self._fds[parent], follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != self._modes[name]
            or _identity(opened) != _identity(named)
        ):
            raise RepositoryHttpStageError("Stage directory identity or permissions changed")
        return opened

    def _refresh(self, name, *, changing=False, mode_changed=False):
        current = _identity(self._directory(name))
        previous = self._directories.get(name)
        stable = (0, 1, 3, 4) if mode_changed else (0, 1, 2, 3, 4)
        if previous is not None and (
            any(current[i] != previous[i] for i in stable) or not changing and current != previous
        ):
            raise RepositoryHttpStageError("Stage directory changed unexpectedly")
        self._directories[name] = current

    def _membership(self, name):
        expected, seen = self._members[name], set()
        pin = _identity(self._directory(name))
        try:
            iterator = os.scandir(self._fds[name])
            if inspect.iscoroutine(iterator):
                iterator.close()
                raise RepositoryHttpStageError("Directory iterator is unconfirmed")
            closer = iterator.close
            if not callable(closer):
                raise RepositoryHttpStageError("Directory iterator closure is unavailable")
        except BaseException as exc:
            self._closure_uncertain = True
            self._cleanup_failure = self._cleanup_failure or exc
            raise
        primary = None
        try:
            for count, entry in enumerate(iterator, 1):
                if (
                    count > len(expected)
                    or type(entry.name) is not str
                    or entry.name not in expected
                    or entry.name in seen
                ):
                    raise RepositoryHttpStageError("Stage directory membership changed")
                seen.add(entry.name)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            self._close_resource(closer, primary)
        if seen != expected or _identity(self._directory(name)) != pin:
            raise RepositoryHttpStageError("Stage directory changed during enumeration")

    def _read(self, name):
        parent, _, leaf = name.rpartition("/")
        limit = _MAX_RECORD if name == "record.json" else _MAX_FILE
        fd = self._open_fd(
            leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fds[parent]
        )
        primary = None
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != (0o600 if name == "record.json" else 0o444)
                or not 0 <= before.st_size <= limit
            ):
                raise RepositoryHttpStageError("Expected bounded owned single-link stage file")
            chunks, remaining = [], limit + 1
            while remaining:
                maximum = min(remaining, _MAX_FILE)
                chunk = os.read(fd, maximum)
                if type(chunk) is not bytes or len(chunk) > maximum:
                    if inspect.iscoroutine(chunk):
                        chunk.close()
                    raise RepositoryHttpStageError("Stage read exceeded its requested bound")
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content, pin = b"".join(chunks), _identity(before)
            if (
                len(content) != before.st_size
                or len(content) > limit
                or _identity(os.fstat(fd)) != pin
                or _identity(os.stat(leaf, dir_fd=self._fds[parent], follow_symlinks=False)) != pin
            ):
                raise RepositoryHttpStageError("Stage file changed during readback")
            content.decode("utf-8", errors="strict")
            result = _File(content, pin)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            self._close_resource(lambda: os.close(fd), primary)
        if _identity(os.stat(leaf, dir_fd=self._fds[parent], follow_symlinks=False)) != pin:
            raise RepositoryHttpStageError("Stage file changed after descriptor closure")
        return result

    def _assert_stage(self):
        for name, pin in self._directories.items():
            if _identity(self._directory(name)) != pin:
                raise RepositoryHttpStageError("Stage directory checkpoint changed")
            self._membership(name)
        for name, pin in self._tracked.items():
            if self._read(name) != pin:
                raise RepositoryHttpStageError("Stage file checkpoint changed")
        for name, pin in self._directories.items():
            if _identity(self._directory(name)) != pin:
                raise RepositoryHttpStageError("Stage changed during verification")
            self._membership(name)

    def _ensure_directories(self, file):
        parts = file.split("/")[:-1]
        for count in range(1, len(parts) + 1):
            name = "/".join(parts[:count])
            if name in self._directories:
                continue
            self._assert_copy()
            self._assert_stage()
            parent, _, leaf = name.rpartition("/")
            self._partial[name] = "creation-attempted"
            try:
                result = os.mkdir(leaf, 0o700, dir_fd=self._fds[parent])
            except FileExistsError:
                raise
            except BaseException:
                self._ownership_uncertain = True
                raise
            if result is not None:
                if inspect.iscoroutine(result):
                    result.close()
                self._ownership_uncertain = True
                raise RepositoryHttpStageError("Stage directory creation is unconfirmed")
            self._partial[name] = "created-unconfirmed"
            self._members[parent].add(leaf)
            self._refresh(parent, changing=True)
            self._open_directory(name, leaf, parent)
            os.fsync(self._fds[parent])
            self._partial[name] = "confirmed"

    def _create_file(self, name, content):
        self._assert_copy()
        self._assert_stage()
        limit = _MAX_RECORD if name == "record.json" else _MAX_FILE
        if type(content) is not bytes or len(content) > limit:
            raise RepositoryHttpStageError("Stage file exceeds its fixed byte budget")
        content.decode("utf-8", errors="strict")
        parent, _, leaf = name.rpartition("/")
        self._partial[name] = "creation-attempted"
        fd = self._open_fd(
            leaf,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=self._fds[parent],
        )
        primary = None
        try:
            self._partial[name] = "created-unconfirmed"
            self._members[parent].add(leaf)
            pending = memoryview(content)
            while pending:
                written = os.write(fd, pending)
                if type(written) is not int or not 0 < written <= len(pending):
                    if inspect.iscoroutine(written):
                        written.close()
                    raise RepositoryHttpStageError("Stage write is incomplete")
                pending = pending[written:]
            os.fchmod(fd, 0o600 if name == "record.json" else 0o444)
            os.fsync(fd)
            pin = _identity(os.fstat(fd))
            if _identity(os.stat(leaf, dir_fd=self._fds[parent], follow_symlinks=False)) != pin:
                raise RepositoryHttpStageError("Created stage file name changed")
        except BaseException as exc:
            primary = exc
            raise
        finally:
            self._close_resource(lambda: os.close(fd), primary)
        self._refresh(parent, changing=True)
        observed = self._read(name)
        if observed != _File(content, pin):
            raise RepositoryHttpStageError("Stage file readback differs")
        self._tracked[name] = observed
        self._partial[name] = "confirmed"
        os.fsync(self._fds[parent])

    def _checkpoint_evidence(self):
        cp = self._checkpoint
        return {
            "session_id": cp.session_id,
            "revision": cp.revision,
            "phase": cp.phase,
            "root_identity": list(cp.root_identity),
            "files": {n: list(pin) for n, pin in cp.file_identities},
            "journal_sha256": _hash(cp.journal_bytes),
        }

    def _checked(self):
        self._assert_copy()
        self._assert_stage()
        if self._tracked["input/manifest.json"].data != canonical(self.manifest).encode("utf-8"):
            raise RepositoryHttpStageError("Stage declaration differs from sealed manifest bytes")
        self._assert_copy()

    def _enter(self):
        if self._busy:
            self._reentry_refused = True
            self._state = "state-unconfirmed"
            raise RepositoryHttpStageError("Reentrant stage access is unsupported")
        if self._state != "staged-" + self._phase:
            raise RepositoryHttpStageError("Stage is closed or unconfirmed")
        self._busy = True

    def _snapshot(self):
        return {
            "schema_version": "2.0",
            "kind": "repository-http-input-stage-snapshot",
            "phase": self._phase,
            "role": self._role,
            "state": self._state,
            "path": str(self._path),
            "input_path": str(self.input_path),
            "verification_plan_id": self._plan_id,
            "checkpoint": self._checkpoint_evidence(),
            "manifest": self.manifest,
            "directories": {k: list(v) for k, v in self._directories.items()},
            "files": {k: _evidence(v) for k, v in self._tracked.items()},
            "filesystem_observed": True,
            "runtime_invoked": False,
            "execution_authorized": False,
            "execution_status": "not-run",
            "authorization_status": "unknown",
            "verified_fix": False,
            "evidence": "historical-file-observation-not-runtime-or-resume-authority",
        }

    def assert_current(self):
        self._enter()
        try:
            self._checked()
        except BaseException as exc:
            self._state = "state-unconfirmed"
            if not isinstance(exc, Exception):
                raise
            raise RepositoryHttpStageError("Stage integrity is unconfirmed") from exc
        finally:
            self._busy = False

    def snapshot(self):
        self._enter()
        try:
            self._checked()
            result = decode(canonical(self._snapshot()))
            self._checked()
            return result
        except BaseException as exc:
            self._state = "state-unconfirmed"
            if not isinstance(exc, Exception):
                raise
            raise RepositoryHttpStageError("Stage snapshot is unconfirmed") from exc
        finally:
            self._busy = False

    def prepare_create(self, profile, session_nonce, role_nonce):
        self._enter()
        try:
            self._checked()
            before = self._snapshot()
            try:
                plan = build_container_create_plan(
                    profile,
                    self._role,
                    session_nonce=session_nonce,
                    role_nonce=role_nonce,
                    staging_root=str(self.input_path),
                    manifest=self.manifest,
                )
            finally:
                self._checked()
            if self._snapshot() != before:
                raise RepositoryHttpStageError("Stage changed during create planning")
            result = {
                "schema_version": "2.0",
                "kind": "repository-http-staged-create-plan",
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
            return RepositoryHttpStagedCreatePlan(raw)
        except BaseException as exc:
            self._state = "state-unconfirmed"
            if not isinstance(exc, Exception):
                raise
            raise RepositoryHttpStageError("Staged create planning is unconfirmed") from exc
        finally:
            self._busy = False

    def _close_resource(self, callback, primary=None):
        try:
            result = callback()
            if result is not None:
                if inspect.iscoroutine(result):
                    result.close()
                raise RepositoryHttpStageError("Resource closure is unconfirmed")
        except BaseException as cleanup:
            self._closure_uncertain = True
            self._cleanup_failure = self._cleanup_failure or cleanup
            if primary is not None:
                primary.repository_http_stage_cleanup_failure = cleanup
                if not isinstance(cleanup, Exception) and isinstance(primary, Exception):
                    cleanup.repository_http_stage_primary_failure = primary
                    raise cleanup
                raise primary from cleanup
            raise

    def _close_descriptors(self):
        failure, seen = None, set()
        for name in reversed(tuple(self._fds)):
            fd, self._fds[name] = self._fds[name], -1
            if fd < 0 or fd in seen:
                continue
            seen.add(fd)
            try:
                result = os.close(fd)
                if result is not None:
                    if inspect.iscoroutine(result):
                        result.close()
                    raise RepositoryHttpStageError("Descriptor closure is unconfirmed")
            except BaseException as exc:
                self._closure_uncertain = True
                self._cleanup_failure = self._cleanup_failure or exc
                if (
                    failure is None
                    or isinstance(failure, Exception)
                    and not isinstance(exc, Exception)
                ):
                    failure = exc
        if failure is None and self._closure_uncertain:
            failure = RepositoryHttpStageError("Prior resource uncertainty remains")
        self._descriptor_cleanup_confirmed = failure is None and not self._closure_uncertain
        return failure

    def close(self):
        """Close every held descriptor without deleting/chmodding retained evidence."""
        if self._busy:
            self._reentry_refused = True
            self._state = "state-unconfirmed"
            raise RepositoryHttpStageError("Reentrant stage closure is unsupported")
        self._busy = True
        try:
            failure = self._close_descriptors()
            if failure is not None:
                self._state = "state-unconfirmed"
                if not isinstance(failure, Exception):
                    raise failure
                raise RepositoryHttpStageError(
                    "Stage descriptor cleanup is unconfirmed"
                ) from failure
            if self._state != "state-unconfirmed":
                self._state = "closed"
        finally:
            self._busy = False
