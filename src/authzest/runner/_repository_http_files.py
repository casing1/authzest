"""Fresh retained HTTP-only source bytes, not execution or a resumable session.

The synchronous guard is trusted caller coordination. Atomic rename is not CAS
against a hostile same-user writer; exclude concurrent writers. No target code
is imported, parsed or executed here. Closing only releases held descriptors.
"""

from __future__ import annotations

import inspect
import os
import secrets
import stat
import sys
import tempfile
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from authzest.codex.contracts import ContractError
from authzest.codex.repository_http_proposal import validate_repository_http_options

MAX_MATERIAL_BYTES = 131_072
MAX_JOURNAL_BYTES = 65_536
MAX_SOURCE_BYTES = 16_384
_EVIDENCE = {
    "evidence/policy.txt",
    "evidence/source.before",
    "evidence/source.after",
}
_OPEN_DIR = os.open in os.supports_dir_fd
_STAT_DIR = os.stat in os.supports_dir_fd
_MKDIR_DIR = os.mkdir in os.supports_dir_fd
_RENAME_DIR = os.rename in os.supports_dir_fd
_STAT_NOFOLLOW = os.stat in os.supports_follow_symlinks
_SCANDIR_FD = os.scandir in os.supports_fd


class RepositoryHttpFilesError(RuntimeError):
    """A closed private-file precondition or bounded operation failed."""


class RepositoryHttpFilesInitializationError(RepositoryHttpFilesError):
    """Any partially created private tree is retained, never adopted or deleted."""

    def __init__(self, created_path, stage, file_states, *, descriptor_cleanup_confirmed):
        super().__init__("Private workspace initialization failed; retained state needs inspection")
        self.created_path = created_path
        self.stage = stage
        self.file_states = dict(file_states)
        self.descriptor_cleanup_confirmed = descriptor_cleanup_confirmed


class RepositoryHttpFilesWriteError(RepositoryHttpFilesError):
    """An attempted write is not a reason to claim successful commit or rollback."""

    def __init__(self, operation, stage, *, commit_attempted, committed, staging_path):
        super().__init__("Private file write failed; do not retry or blindly restore")
        self.operation = operation
        self.stage = stage
        self.commit_attempted = commit_attempted
        self.committed = committed
        self.staging_path = staging_path
        self.state_unconfirmed = True


@dataclass(frozen=True, slots=True)
class _File:
    data: bytes
    identity: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Directory:
    fd: int
    parent: int
    name: str
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
        and _OPEN_DIR
        and _STAT_DIR
        and _MKDIR_DIR
        and _RENAME_DIR
        and _STAT_NOFOLLOW
        and _SCANDIR_FD
        and all(hasattr(os, n) for n in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
    )


def _path(value: str) -> tuple[str, ...]:
    if type(value) is not str:
        raise RepositoryHttpFilesError("Private material path is invalid")
    try:
        raw = value.encode("utf-8")
    except UnicodeError:
        raise RepositoryHttpFilesError("Private material path is invalid") from None
    parts = tuple(value.split("/"))
    if (
        not raw
        or len(raw) > 520
        or len(parts) > 17
        or "\\" in value
        or any(not p or p.startswith(".") for p in parts)
        or any(unicodedata.category(c).startswith("C") for c in value)
    ):
        raise RepositoryHttpFilesError("Private material path is invalid")
    return parts


def _bytes(value: bytes, limit: int) -> None:
    if type(value) is not bytes or len(value) > limit:
        raise RepositoryHttpFilesError("Private material byte limit exceeded")
    try:
        value.decode("utf-8", errors="strict")
    except UnicodeError:
        raise RepositoryHttpFilesError("Private material must be UTF-8") from None
    if b"\0" in value:
        raise RepositoryHttpFilesError("Private material contains invalid text")


def _materials(materials: dict[str, bytes], source_path: str) -> dict[str, bytes]:
    """Accept only one flat HTTP source and its closed host-only byte evidence."""
    if type(materials) is not dict or len(materials) != 5:
        raise RepositoryHttpFilesError("HTTP private material manifest is invalid")
    parts = _path(source_path)
    if len(parts) != 2 or parts[0] != "project":
        raise RepositoryHttpFilesError("HTTP private source must be one flat selected file")
    try:
        validate_repository_http_options(parts[1])
    except ContractError as exc:
        raise RepositoryHttpFilesError("HTTP private source path is unsupported") from exc
    if set(materials) != _EVIDENCE | {source_path, "record.json"}:
        raise RepositoryHttpFilesError("HTTP private material manifest is invalid")
    keys = []
    for name, content in materials.items():
        _path(name)
        normalized = unicodedata.normalize("NFD", unicodedata.normalize("NFD", name).casefold())
        key = tuple(normalized.split("/"))
        for other in keys:
            if key[: len(other)] == other or other[: len(key)] == key:
                raise RepositoryHttpFilesError("HTTP private material paths overlap")
        keys.append(key)
        limit = MAX_JOURNAL_BYTES if name == "record.json" else MAX_SOURCE_BYTES
        if name == "evidence/policy.txt":
            limit = 8192
        _bytes(content, limit)
    if (
        sum(len(v) for k, v in materials.items() if k != "record.json") > MAX_MATERIAL_BYTES
        or materials[source_path] != materials["evidence/source.before"]
    ):
        raise RepositoryHttpFilesError("HTTP private material exceeds its bounds or bindings")
    return dict(materials)


def _guard(guard: Callable[[], None]) -> None:
    if (
        not callable(guard)
        or inspect.iscoroutinefunction(guard)
        or inspect.isgeneratorfunction(guard)
        or inspect.isasyncgenfunction(guard)
    ):
        raise RepositoryHttpFilesError("A synchronous file guard is required")
    result = guard()
    if result is not None:
        if inspect.iscoroutine(result):
            result.close()
        raise RepositoryHttpFilesError("File guard must synchronously return None")


class RepositoryHttpFiles:
    """Only freshly created, current-process private trees can be operated on.

    ``_parent`` is an inert-test seam, not an existing-workspace destination.
    Caller-controlled guards do not establish human approval or runtime evidence.
    """

    def __init__(
        self,
        materials: dict[str, bytes],
        source_path: str,
        *,
        _parent: Path | None = None,
        guard: Callable[[], None],
    ):
        if type(self) is not RepositoryHttpFiles:
            raise RepositoryHttpFilesError("Private workspace subclass adoption is unsupported")
        contents = _materials(materials, source_path)
        if not supported():
            raise RepositoryHttpFilesError(
                "Private files require supported POSIX source operations"
            )
        self._source_path = source_path
        self._pid = os.getpid()
        self._closed = False
        self._poisoned = False
        self._descriptor_uncertain = False
        self._busy = False
        self._fds: list[int] = []
        self._parents: list[tuple[int | None, str, int, tuple[int, ...]]] = []
        self._dirs: dict[str, _Directory] = {}
        self._files: dict[str, _File] = {}
        self._entries: dict[str, set[str]] = {}
        self._partial = dict.fromkeys(contents, "not-created")
        created_path = None
        stage = "open-parent"
        try:
            parent = (
                Path(tempfile.gettempdir()).resolve(strict=True) if _parent is None else _parent
            )
            parent_fd = self._open_parent(parent)
            name = "authzest-repository-http-" + secrets.token_hex(16)
            candidate = parent / name
            if len(str(candidate).encode("utf-8")) > 4096:
                raise RepositoryHttpFilesError("Private parent path is too long")
            stage = "check-guard"
            _guard(guard)
            stage = "create-root"
            created_path = candidate
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                created_path = None
                raise
            except OSError:
                try:
                    os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    created_path = None
                raise
            self._path = candidate
            stage = "open-root"
            self._open_directory("", parent_fd, name)
            directories = {
                "/".join(_path(n)[:i]) for n in contents for i in range(1, len(_path(n)))
            }
            for relative in sorted(directories, key=lambda p: (len(p.split("/")), p)):
                parent_key, _, basename = relative.rpartition("/")
                stage = "create-directory"
                self._check_directories()
                os.mkdir(basename, 0o700, dir_fd=self._dirs[parent_key].fd)
                self._entries[parent_key].add(basename)
                self._refresh(parent_key)
                self._open_directory(relative, self._dirs[parent_key].fd, basename)
            for name, content in contents.items():
                stage = "create-material"
                self._assert_all()
                self._partial[name] = "creation-attempted"
                before = self._write_new(name, content)
                self._partial[name] = "created-unconfirmed"
                parent_key, _, basename = name.rpartition("/")
                self._entries[parent_key].add(basename)
                self._refresh(parent_key)
                result = self._read_current(name, len(content))
                if result != _File(content, before):
                    raise RepositoryHttpFilesError("Initial private material failed readback")
                self._files[name] = result
                self._partial[name] = "verified"
            stage = "sync-initial-tree"
            for directory in reversed(list(self._dirs.values())):
                os.fsync(directory.fd)
            os.fsync(parent_fd)
            stage = "verify-initial-tree"
            self.verify()
        except BaseException as exc:
            self._poisoned = True
            cleanup = True
            cleanup_failure = None
            try:
                self.close()
            except BaseException as interrupted:
                cleanup = False
                cleanup_failure = interrupted
            failure = RepositoryHttpFilesInitializationError(
                created_path, stage, self._partial, descriptor_cleanup_confirmed=cleanup
            )
            if (
                cleanup_failure is not None
                and not isinstance(cleanup_failure, Exception)
                and isinstance(exc, Exception)
            ):
                cleanup_failure.repository_http_files_initialization = failure
                raise cleanup_failure from exc
            if not isinstance(exc, Exception):
                exc.repository_http_files_initialization = failure
                raise
            raise failure from exc

    def _live(self) -> None:
        if type(self) is not RepositoryHttpFiles or getattr(self, "_pid", None) != os.getpid():
            raise RepositoryHttpFilesError("Private file handle does not belong to this process")
        if getattr(self, "_closed", True) or getattr(self, "_poisoned", True):
            raise RepositoryHttpFilesError("Private file handle is closed or unconfirmed")

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def source_path(self) -> str:
        return self._source_path

    @property
    def path(self) -> Path:
        return self._path

    @property
    def poisoned(self) -> bool:
        return self._poisoned

    @property
    def root_identity(self) -> tuple[int, ...]:
        self.verify()
        return self._dirs[""].identity

    @property
    def identities(self) -> dict[str, list[int]]:
        self.verify()
        return {name: list(value.identity) for name, value in self._files.items()}

    def _open_parent(self, path: Path) -> int:
        if (
            not isinstance(path, Path)
            or not path.is_absolute()
            or len(path.parts) > 64
            or any(part in {".", ".."} for part in path.parts)
            or any(unicodedata.category(c).startswith("C") for c in str(path))
        ):
            raise RepositoryHttpFilesError("Private temporary parent is invalid")
        parent = None
        for name in (path.anchor, *path.parts[1:]):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            self._fds.append(fd)
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise RepositoryHttpFilesError("Private parent must contain real directories")
            self._parents.append((parent, name, fd, _identity(info)[:5]))
            parent = fd
        info = os.fstat(parent)
        if not (
            info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o700
            or info.st_uid == 0
            and info.st_mode & stat.S_ISVTX
        ):
            raise RepositoryHttpFilesError("Private temporary parent permissions are unsupported")
        self._check_parents()
        return parent

    def _check_parents(self) -> None:
        for parent, name, fd, expected in self._parents:
            if (
                _identity(os.fstat(fd))[:5] != expected
                or _identity(os.stat(name, dir_fd=parent, follow_symlinks=False))[:5] != expected
            ):
                raise RepositoryHttpFilesError("Private parent identity changed")

    def _open_directory(self, relative: str, parent: int, name: str) -> None:
        named = _identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        self._fds.append(fd)
        info = os.fstat(fd)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or _identity(info) != named
        ):
            raise RepositoryHttpFilesError("Private directory changed or is not private")
        self._dirs[relative] = _Directory(fd, parent, name, _identity(info))
        self._entries[relative] = set()

    def _refresh(self, relative: str) -> None:
        previous = self._dirs[relative]
        info = os.fstat(previous.fd)
        current = _identity(info)
        if (
            current[:5] != previous.identity[:5]
            or _identity(os.stat(previous.name, dir_fd=previous.parent, follow_symlinks=False))
            != current
        ):
            raise RepositoryHttpFilesError("Private directory identity changed during own write")
        self._dirs[relative] = _Directory(previous.fd, previous.parent, previous.name, current)

    def _check_directories(self) -> None:
        self._check_parents()
        for relative, directory in self._dirs.items():
            if (
                _identity(os.fstat(directory.fd)) != directory.identity
                or _identity(
                    os.stat(directory.name, dir_fd=directory.parent, follow_symlinks=False)
                )
                != directory.identity
            ):
                raise RepositoryHttpFilesError("Private directory changed unexpectedly")
            expected = self._entries[relative]
            names = set()
            with os.scandir(directory.fd) as entries:
                for entry in entries:
                    if entry.name not in expected or entry.name in names:
                        raise RepositoryHttpFilesError("Unexpected private directory entry")
                    names.add(entry.name)
            if names != expected:
                raise RepositoryHttpFilesError("Private directory entry is missing")

    def _location(self, name: str) -> tuple[int, str, str]:
        parent, _, basename = name.rpartition("/")
        return self._dirs[parent].fd, basename, parent

    def _read_current(self, name: str, maximum: int) -> _File:
        parent, basename, _ = self._location(name)
        fd = os.open(basename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            before = _identity(info)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid()
                or info.st_nlink != 1
                or not 0 <= info.st_size <= maximum
            ):
                raise RepositoryHttpFilesError(
                    "Private file must be a bounded single-link regular file"
                )
            raw = bytearray()
            while len(raw) <= maximum:
                chunk = os.read(fd, min(4096, maximum + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            if (
                len(raw) != info.st_size
                or len(raw) > maximum
                or _identity(os.fstat(fd)) != before
                or _identity(os.stat(basename, dir_fd=parent, follow_symlinks=False)) != before
            ):
                raise RepositoryHttpFilesError("Private file changed during readback")
            return _File(bytes(raw), before)
        finally:
            self._close_file(fd)

    def _write_new(self, name: str, data: bytes) -> tuple[int, ...]:
        parent, basename, _ = self._location(name)
        fd = os.open(
            basename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=parent,
        )
        if name in self._partial:
            self._partial[name] = "created-unconfirmed"
        try:
            os.fchmod(fd, 0o600)
            pending = memoryview(data)
            while pending:
                written = os.write(fd, pending)
                if type(written) is not int or not 0 < written <= len(pending):
                    raise OSError("Incomplete private file write")
                pending = pending[written:]
            os.fsync(fd)
            result = _identity(os.fstat(fd))
            if _identity(os.stat(basename, dir_fd=parent, follow_symlinks=False)) != result:
                raise RepositoryHttpFilesError("New private file identity changed")
            return result
        finally:
            self._close_file(fd)

    def _close_file(self, fd: int) -> None:
        try:
            os.close(fd)
        except BaseException:
            self._descriptor_uncertain = True
            raise

    def _assert_all(self) -> None:
        self._check_directories()
        for name, expected in self._files.items():
            if self._read_current(name, len(expected.data)) != expected:
                raise RepositoryHttpFilesError("Private file bytes or identity changed")
        self._check_directories()

    def verify(self) -> None:
        self._live()
        try:
            self._assert_all()
        except (OSError, RepositoryHttpFilesError) as exc:
            self._poisoned = True
            raise RepositoryHttpFilesError("Private tree integrity is unconfirmed") from exc

    def read(self, path: str) -> bytes:
        self.verify()
        if type(path) is not str or path not in self._files:
            raise RepositoryHttpFilesError("Private file is not in the current manifest")
        return self._files[path].data

    def replace(self, path: str, data: bytes, *, guard: Callable[[], None]) -> None:
        self._live()
        if self._busy:
            raise RepositoryHttpFilesError("Reentrant private file writes are unsupported")
        if type(path) is not str or path not in {self.source_path, "record.json"}:
            raise RepositoryHttpFilesError("Only the private source or journal can be replaced")
        _bytes(data, MAX_JOURNAL_BYTES if path == "record.json" else MAX_SOURCE_BYTES)
        self._busy = True
        stage = "verify-before-stage"
        staged_path = None
        attempted = committed = False
        try:
            self.verify()
            parent, basename, parent_key = self._location(path)
            staged_name = ".authzest-" + secrets.token_hex(16) + ".tmp"
            staged = parent_key + "/" + staged_name if parent_key else staged_name
            staged_path = self.path / staged
            stage = "create-stage"
            pinned = self._write_new(staged, data)
            self._entries[parent_key].add(staged_name)
            self._refresh(parent_key)
            current = self._read_current(staged, len(data))
            if current != _File(data, pinned):
                raise RepositoryHttpFilesError("Private staging readback differs")
            self._files[staged] = current
            stage = "verify-before-commit"
            self.verify()
            stage = "check-guard"
            _guard(guard)
            # No filesystem work between this trusted final guard and replace.
            stage = "replace"
            attempted = True
            os.replace(staged_name, basename, src_dir_fd=parent, dst_dir_fd=parent)
            committed = True
            self._entries[parent_key].remove(staged_name)
            self._refresh(parent_key)
            stage = "sync-replacement"
            os.fsync(parent)
            stage = "readback-replacement"
            result = self._read_current(path, len(data))
            # Rename may change ctime, but must preserve the staged inode/metadata.
            if result.data != data or result.identity[:-1] != current.identity[:-1]:
                raise RepositoryHttpFilesError("Private replacement did not read back exactly")
            del self._files[staged]
            self._files[path] = result
            stage = "verify-replacement"
            self.verify()
        except BaseException as exc:
            self._poisoned = True
            failure = RepositoryHttpFilesWriteError(
                path,
                stage,
                commit_attempted=attempted,
                committed=committed,
                staging_path=staged_path,
            )
            if not isinstance(exc, Exception):
                exc.repository_http_files_write = failure
                raise
            raise failure from exc
        finally:
            self._busy = False

    def close(self) -> None:
        if self._busy:
            raise RepositoryHttpFilesError("Cannot close an active private write")
        if self._closed:
            return
        self._closed = True
        failure = None
        while self._fds:
            try:
                os.close(self._fds.pop())
            except BaseException as exc:
                self._descriptor_uncertain = True
                if failure is None or isinstance(failure, Exception):
                    failure = exc
        if failure is not None or self._descriptor_uncertain:
            self._poisoned = True
            if failure is not None and not isinstance(failure, Exception):
                failure.repository_http_files_cleanup_confirmed = False
                raise failure
            raise RepositoryHttpFilesError("Private descriptor cleanup is unconfirmed")

    def __enter__(self):
        self._live()
        return self

    def __exit__(self, *_):
        self.close()

    def __copy__(self):
        raise TypeError("Live private file handles cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("Live private file handles cannot be copied")

    def __reduce__(self):
        raise TypeError("Live private file handles cannot be serialized")
