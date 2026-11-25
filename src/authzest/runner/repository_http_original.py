"""Approved final write of one verified repair to the original source file.

The caller is trusted to obtain the user's current decision after a passing
after phase. This module rechecks the held original bytes/identities, retains
a private backup and durable intent record, writes through the captured
parent directory descriptor and reads the result back. Recovery restores the
backup only while the original still holds exactly the applied bytes, so later
edits are never overwritten. Atomic rename is not compare-and-swap against a
concurrent writer; the operator must not edit the file during these steps.
"""

from __future__ import annotations

import difflib
import errno
import inspect
import json
import os
import secrets
import stat
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import canonical
from authzest.runner._repository_http_phase import RepositoryHttpPhaseResult
from authzest.runner.repository_http_file_session import RepositoryHttpFileSession

SCHEMA_VERSION = "2.0"
RECORD_KIND = "repository-http-original-record"
MAX_RECORD_BYTES = 65_536
MAX_SOURCE_BYTES = 16_384
_BACKUP, _APPLIED, _RECORD = "before.py", "after.py", "record.json"
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
# An interrupted apply can leave intent-recorded after the rename; the exact
# applied-bytes check below still decides whether restoring is safe.
_RESTORABLE = frozenset({"intent-recorded", "applied", "recovery-required"})
_STATES = {
    "intent-recorded",
    "applied",
    "original-unchanged-failed",
    "recovery-required",
    "restored",
}


class RepositoryHttpOriginalError(RuntimeError):
    """A refused or failed original operation; ``result`` holds retained facts."""

    def __init__(self, code: str, result: dict | None = None):
        super().__init__(code)
        self.code = code
        self.result = result


def default_recovery_parent() -> Path:
    return Path.home() / ".authzest" / "recovery"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _hash(data: bytes) -> str:
    return sha256(data).hexdigest()


def _identity(info: os.stat_result) -> list:
    return [info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode), info.st_size, info.st_mtime_ns]


def _diff(path: str, old: bytes, new: bytes) -> str:
    return "".join(
        difflib.unified_diff(
            old.decode("utf-8").splitlines(keepends=True),
            new.decode("utf-8").splitlines(keepends=True),
            fromfile="a/" + path,
            tofile="b/" + path,
        )
    )


def _guard(guard: Callable[[], None] | None) -> None:
    if guard is None:
        return
    answer = guard()
    if inspect.iscoroutine(answer):
        answer.close()
    if answer is not None:
        raise RepositoryHttpOriginalError("decision-guard-must-return-none")


def _read_fd(fd: int, limit: int) -> bytes:
    raw = bytearray()
    while len(raw) <= limit:
        chunk = os.pread(fd, min(4096, limit + 1 - len(raw)), len(raw))
        if not chunk:
            return bytes(raw)
        raw.extend(chunk)
    raise RepositoryHttpOriginalError("file-size-limit")


def _read_leaf(parent: int, name: str, limit: int) -> tuple[bytes, os.stat_result]:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RepositoryHttpOriginalError("regular-file-required")
        raw = _read_fd(fd, limit)
        if os.fstat(fd).st_size != len(raw):
            raise RepositoryHttpOriginalError("file-changed-during-read")
        return raw, info
    finally:
        os.close(fd)


def _write_new(
    parent: int,
    name: str,
    data: bytes,
    mode: int,
    prepare: Callable[[int], None] | None = None,
) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent)
    try:
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RepositoryHttpOriginalError("short-write")
            view = view[written:]
        if prepare is not None:
            prepare(fd)
        os.fsync(fd)
    finally:
        os.close(fd)


# Security metadata: the replacement is a new inode, so ownership, group, mode,
# ACLs and extended attributes (including Linux ACL/label xattrs) are copied from
# the current file and compared before the rename; anything unpreservable refuses.
_COPYFILE_ACL, _COPYFILE_XATTR = 1 << 0, 1 << 2
_LIBC = None


def _libc():
    global _LIBC
    if _LIBC is None:
        import ctypes
        import ctypes.util

        lib = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        lib.fcopyfile.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        lib.fcopyfile.restype = ctypes.c_int
        lib.flistxattr.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        lib.flistxattr.restype = ctypes.c_ssize_t
        lib.fgetxattr.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.c_int,
        ]
        lib.fgetxattr.restype = ctypes.c_ssize_t
        lib.fremovexattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.fremovexattr.restype = ctypes.c_int
        lib.acl_get_fd.argtypes = [ctypes.c_int]
        lib.acl_get_fd.restype = ctypes.c_void_p
        lib.acl_to_text.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.acl_to_text.restype = ctypes.c_void_p
        lib.acl_free.argtypes = [ctypes.c_void_p]
        _LIBC = (ctypes, lib)
    return _LIBC


def _metadata_failure() -> RepositoryHttpOriginalError:
    return RepositoryHttpOriginalError("original-metadata-not-preserved")


def _xattr_names(fd: int) -> list[str]:
    if sys.platform == "darwin":
        ctypes, lib = _libc()
        size = lib.flistxattr(fd, None, 0, 0)
        if size < 0:
            raise _metadata_failure()
        buffer = ctypes.create_string_buffer(max(size, 1))
        size = lib.flistxattr(fd, buffer, size, 0)
        if size < 0:
            raise _metadata_failure()
        return sorted(name.decode("utf-8") for name in buffer.raw[:size].split(b"\0") if name)
    if hasattr(os, "listxattr"):
        try:
            return sorted(os.listxattr(fd))
        except OSError as exc:
            if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
                return []
            raise _metadata_failure() from None
    return []


def _xattr_value(fd: int, name: str) -> bytes:
    if sys.platform == "darwin":
        ctypes, lib = _libc()
        key = name.encode("utf-8")
        size = lib.fgetxattr(fd, key, None, 0, 0, 0)
        if size < 0:
            raise _metadata_failure()
        buffer = ctypes.create_string_buffer(max(size, 1))
        size = lib.fgetxattr(fd, key, buffer, size, 0, 0)
        if size < 0:
            raise _metadata_failure()
        return buffer.raw[:size]
    return os.getxattr(fd, name)


def _acl_text(fd: int) -> str | None:
    if sys.platform != "darwin":
        return None  # Linux POSIX ACLs are system.posix_acl_* extended attributes.
    ctypes, lib = _libc()
    acl = lib.acl_get_fd(fd)
    if not acl:
        return None
    try:
        text = lib.acl_to_text(acl, None)
        if not text:
            raise _metadata_failure()
        try:
            return ctypes.string_at(text).decode("utf-8")
        finally:
            lib.acl_free(text)
    finally:
        lib.acl_free(acl)


def _metadata(fd: int) -> dict:
    info = os.fstat(fd)
    acl = _acl_text(fd)
    return {
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": stat.S_IMODE(info.st_mode),
        "flags": getattr(info, "st_flags", 0),
        "xattrs": {name: _hash(_xattr_value(fd, name)) for name in _xattr_names(fd)},
        "acl_sha256": None if acl is None else _hash(acl.encode("utf-8")),
    }


def _check_supported_metadata(meta: dict) -> None:
    if meta["uid"] != os.geteuid():
        raise RepositoryHttpOriginalError("original-owner-differs")
    if meta["flags"]:
        raise RepositoryHttpOriginalError("original-file-flags-unsupported")


def _copy_metadata(source: int, target: int, meta: dict) -> None:
    try:
        if sys.platform == "darwin":
            _, lib = _libc()
            if lib.fcopyfile(source, target, None, _COPYFILE_ACL | _COPYFILE_XATTR) != 0:
                raise _metadata_failure()
            for name in set(_xattr_names(target)) - set(meta["xattrs"]):
                if lib.fremovexattr(target, name.encode("utf-8"), 0) != 0:
                    raise _metadata_failure()
        elif hasattr(os, "setxattr"):
            for name in meta["xattrs"]:
                os.setxattr(target, name, os.getxattr(source, name))
            for name in set(_xattr_names(target)) - set(meta["xattrs"]):
                os.removexattr(target, name)
        if os.fstat(target).st_gid != meta["gid"]:
            os.fchown(target, -1, meta["gid"])
        os.fchmod(target, meta["mode"])
    except OSError:
        raise _metadata_failure() from None
    if _metadata(target) != meta:
        raise _metadata_failure()


def _remove_temporary(parent: int, name: str) -> str:
    """Remove our own temporary file; a copied deny-delete ACL is cleared first."""
    try:
        os.unlink(name, dir_fd=parent)
        return "temporary-removed"
    except FileNotFoundError:
        return "temporary-absent"
    except PermissionError:
        if sys.platform != "darwin":
            return "temporary-removal-unconfirmed"
    except OSError:
        return "temporary-removal-unconfirmed"
    try:
        ctypes, lib = _libc()
        lib.acl_init.argtypes = [ctypes.c_int]
        lib.acl_init.restype = ctypes.c_void_p
        lib.acl_set_fd.argtypes = [ctypes.c_int, ctypes.c_void_p]
        lib.acl_set_fd.restype = ctypes.c_int
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            empty = lib.acl_init(0)
            if not empty:
                return "temporary-removal-unconfirmed"
            try:
                if lib.acl_set_fd(fd, empty) != 0:
                    return "temporary-removal-unconfirmed"
            finally:
                lib.acl_free(empty)
        finally:
            os.close(fd)
        os.unlink(name, dir_fd=parent)
        return "temporary-removed"
    except OSError:
        return "temporary-removal-unconfirmed"


def _summary(meta: dict) -> dict:
    return {
        "uid": meta["uid"],
        "gid": meta["gid"],
        "mode": meta["mode"],
        "xattr_names": sorted(meta["xattrs"]),
        "acl_present": meta["acl_sha256"] is not None,
    }


def _leaf_metadata(parent: int, name: str) -> dict:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        return _metadata(fd)
    finally:
        os.close(fd)


def _replace_record(folder: int, record: dict) -> None:
    raw = (canonical(record) + "\n").encode("utf-8")
    if len(raw) > MAX_RECORD_BYTES:
        raise RepositoryHttpOriginalError("record-size-limit")
    temporary = ".record." + secrets.token_hex(8) + ".tmp"
    _write_new(folder, temporary, raw, 0o600)
    os.rename(temporary, _RECORD, src_dir_fd=folder, dst_dir_fd=folder)
    os.fsync(folder)


def _private_directory(path: Path, *, create: bool) -> None:
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise RepositoryHttpOriginalError("private-recovery-directory-required")


def _check_after_result(target, after_result) -> dict:
    if type(after_result) is not RepositoryHttpPhaseResult:
        raise RepositoryHttpOriginalError("after-phase-result-required")
    data = after_result.to_dict()
    if (
        data.get("kind") != "repository-http-phase-result"
        or data.get("phase") != "after"
        or data.get("status") != "complete"
        or data.get("criteria_met") is not True
        or data.get("file_session_id") != target.session_id
        or data.get("file_session_revision") != target.revision
        or data.get("plan_id") != target.verification_plan_id
        or data.get("source_sha256") != _hash(target.after)
    ):
        raise RepositoryHttpOriginalError("after-phase-not-bound-or-not-passing")
    return data


def prepare_original_application(
    session: RepositoryHttpFileSession, after_result: RepositoryHttpPhaseResult
) -> dict:
    """Recheck the original and describe the exact single-file write; no effect."""
    if type(session) is not RepositoryHttpFileSession:
        raise RepositoryHttpOriginalError("live-file-session-required")
    target = session._original_target()
    _check_after_result(target, after_result)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "repository-http-original-preview",
        "root": str(target.root),
        "source_path": target.source_path,
        "before_sha256": _hash(target.before),
        "after_sha256": _hash(target.after),
        "diff": _diff(target.source_path, target.before, target.after),
        "original_state": "matches-capture",
        "effect": "not-performed",
    }


def apply_original(
    session: RepositoryHttpFileSession,
    after_result: RepositoryHttpPhaseResult,
    *,
    recovery_parent: Path,
    guard: Callable[[], None] | None = None,
    verification: dict | None = None,
) -> dict:
    """Write the verified repair to the original after a fresh conflict check.

    Returns the retained record. Raises ``RepositoryHttpOriginalError`` with the
    record (when one exists) for refusals and failures; never retries.
    """
    if type(session) is not RepositoryHttpFileSession or not isinstance(recovery_parent, Path):
        raise RepositoryHttpOriginalError("invalid-original-application-context")
    try:
        target = session._original_target()
    except Exception as exc:
        raise RepositoryHttpOriginalError("original-edit-conflict") from exc
    phase = _check_after_result(target, after_result)
    try:
        meta = _metadata(target.source_fd)
    except OSError:
        raise _metadata_failure() from None
    _check_supported_metadata(meta)
    _guard(guard)
    _private_directory(recovery_parent, create=True)
    record_id = (
        "original-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    )
    record_path = recovery_parent / record_id
    os.mkdir(record_path, 0o700)
    folder = os.open(record_path, _DIR_FLAGS)
    holder = os.open(recovery_parent, _DIR_FLAGS)
    try:
        os.fsync(holder)
    finally:
        os.close(holder)
    parent_info = os.fstat(target.parent_fd)
    record = {
        "schema_version": SCHEMA_VERSION,
        "kind": RECORD_KIND,
        "record_id": record_id,
        "created_at": _now(),
        "root": str(target.root),
        "source_path": target.source_path,
        "parent_identity": [parent_info.st_dev, parent_info.st_ino],
        "before_sha256": _hash(target.before),
        "after_sha256": _hash(target.after),
        "original_identity": [
            target.identity[0],
            target.identity[1],
            stat.S_IMODE(target.identity[2]),
            target.identity[6],
            target.identity[7],
        ],
        "applied_identity": None,
        "metadata": _summary(meta),
        "state": "intent-recorded",
        "failure": None,
        "verification": {
            "plan_id": phase["plan_id"],
            "file_session_id": phase["file_session_id"],
            "after_phase_evidence": phase.get("evidence_directory"),
            **(verification or {}),
        },
        "backup_file": _BACKUP,
        "applied_file": _APPLIED,
        "history": [{"event": "intent-recorded", "at": _now()}],
    }
    temporary = None
    renamed = False
    try:
        _write_new(folder, _BACKUP, target.before, 0o400)
        _write_new(folder, _APPLIED, target.after, 0o400)
        _replace_record(folder, record)
        _guard(guard)
        temporary = "." + target.name + ".authzest-" + secrets.token_hex(6) + ".tmp"
        _write_new(
            target.parent_fd,
            temporary,
            target.after,
            meta["mode"],
            lambda fd: _copy_metadata(target.source_fd, fd, meta),
        )
        # Final edit-conflict check immediately before the rename.
        try:
            current = session._original_target()
        except Exception as exc:
            raise RepositoryHttpOriginalError("original-edit-conflict") from exc
        if current.identity != target.identity or current.before != target.before:
            raise RepositoryHttpOriginalError("original-edit-conflict")
        _guard(guard)
        os.rename(temporary, target.name, src_dir_fd=target.parent_fd, dst_dir_fd=target.parent_fd)
        renamed, temporary = True, None
        os.fsync(target.parent_fd)
        raw, info = _read_leaf(target.parent_fd, target.name, MAX_SOURCE_BYTES)
        if raw != target.after:
            raise RepositoryHttpOriginalError("original-readback-mismatch")
        if _leaf_metadata(target.parent_fd, target.name) != meta:
            raise RepositoryHttpOriginalError("original-metadata-readback-mismatch")
        record["applied_identity"] = _identity(info)
        record["state"] = "applied"
        record["history"].append({"event": "applied", "at": _now()})
        _replace_record(folder, record)
        record["record_path"] = str(record_path)
        return record
    except BaseException as exc:
        cleanup = None
        if temporary is not None:
            cleanup = _remove_temporary(target.parent_fd, temporary)
        code = exc.code if isinstance(exc, RepositoryHttpOriginalError) else type(exc).__name__
        record["state"] = "recovery-required" if renamed else "original-unchanged-failed"
        record["failure"] = {"code": code, "temporary_cleanup": cleanup}
        record["history"].append({"event": record["state"], "at": _now()})
        try:
            _replace_record(folder, record)
        except BaseException:
            record["failure"]["record_persisted"] = False
        record["record_path"] = str(record_path)
        if not isinstance(exc, Exception):
            exc.repository_http_original_record = record
            raise
        raise RepositoryHttpOriginalError(code, record) from None
    finally:
        os.close(folder)


def _open_folder(path: Path) -> int:
    if not isinstance(path, Path) or not path.is_absolute():
        raise RepositoryHttpOriginalError("absolute-record-directory-required")
    _private_directory(path, create=False)
    return os.open(path, _DIR_FLAGS)


def _load_record(folder: int) -> tuple[dict, bytes, bytes]:
    raw, _ = _read_leaf(folder, _RECORD, MAX_RECORD_BYTES)

    def pairs(items):
        value = {}
        for key, child in items:
            if key in value:
                raise RepositoryHttpOriginalError("record-duplicate-field")
            value[key] = child
        return value

    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, ValueError) as exc:
        raise RepositoryHttpOriginalError("record-invalid") from exc
    if (
        type(record) is not dict
        or record.get("schema_version") != SCHEMA_VERSION
        or record.get("kind") != RECORD_KIND
        or record.get("state") not in _STATES
        or type(record.get("root")) is not str
        or type(record.get("source_path")) is not str
        or type(record.get("parent_identity")) is not list
    ):
        raise RepositoryHttpOriginalError("record-invalid")
    before, _ = _read_leaf(folder, _BACKUP, MAX_SOURCE_BYTES)
    after, _ = _read_leaf(folder, _APPLIED, MAX_SOURCE_BYTES)
    if _hash(before) != record.get("before_sha256") or _hash(after) != record.get("after_sha256"):
        raise RepositoryHttpOriginalError("record-backup-mismatch")
    return record, before, after


def _open_original_parent(record: dict) -> tuple[int, str]:
    root = Path(record["root"])
    parts = record["source_path"].split("/")
    if not root.is_absolute() or any(part in ("", ".", "..") for part in parts) or len(parts) > 32:
        raise RepositoryHttpOriginalError("record-invalid")
    fds = []
    try:
        fd = os.open(root.anchor, _DIR_FLAGS)
        fds.append(fd)
        for part in [*root.parts[1:], *parts[:-1]]:
            fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            fds.append(fd)
        info = os.fstat(fd)
        if [info.st_dev, info.st_ino] != record["parent_identity"]:
            raise RepositoryHttpOriginalError("original-directory-replaced")
        fds.pop()
        return fd, parts[-1]
    finally:
        for value in fds:
            os.close(value)


def inspect_original_record(record_path: Path) -> dict:
    """Describe a retained record and the original's current state; no effect."""
    folder = _open_folder(record_path)
    try:
        record, before, after = _load_record(folder)
    finally:
        os.close(folder)
    parent, name = _open_original_parent(record)
    try:
        try:
            current, _ = _read_leaf(parent, name, MAX_SOURCE_BYTES)
        except FileNotFoundError:
            current = None
    finally:
        os.close(parent)
    status = (
        "missing"
        if current is None
        else "matches-applied"
        if current == after
        else "matches-backup"
        if current == before
        else "changed-after-application"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "repository-http-original-restore-preview",
        "record_path": str(record_path),
        "record": record,
        "current_original": status,
        "restore_allowed": status == "matches-applied" and record["state"] in _RESTORABLE,
        "diff": _diff(record["source_path"], after, before) if status == "matches-applied" else "",
    }


def restore_original(record_path: Path, *, guard: Callable[[], None] | None = None) -> dict:
    """Restore the backup only while the original exactly equals the applied bytes."""
    folder = _open_folder(record_path)
    parent = None
    temporary = None
    try:
        record, before, after = _load_record(folder)
        if record["state"] not in _RESTORABLE:
            raise RepositoryHttpOriginalError("record-state-not-restorable")
        parent, name = _open_original_parent(record)
        current, info = _read_leaf(parent, name, MAX_SOURCE_BYTES)
        if current == before:
            raise RepositoryHttpOriginalError("original-already-matches-backup")
        if current != after:
            raise RepositoryHttpOriginalError("original-changed-after-application")
        _guard(guard)
        current_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            meta = _metadata(current_fd)
            _check_supported_metadata(meta)
            temporary = "." + name + ".authzest-" + secrets.token_hex(6) + ".tmp"
            _write_new(
                parent,
                temporary,
                before,
                meta["mode"],
                lambda fd: _copy_metadata(current_fd, fd, meta),
            )
        finally:
            os.close(current_fd)
        again, again_info = _read_leaf(parent, name, MAX_SOURCE_BYTES)
        if again != after or _identity(again_info) != _identity(info):
            raise RepositoryHttpOriginalError("original-changed-after-application")
        _guard(guard)
        os.rename(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        temporary = None
        os.fsync(parent)
        raw, _ = _read_leaf(parent, name, MAX_SOURCE_BYTES)
        if raw != before or _leaf_metadata(parent, name) != meta:
            record["state"] = "recovery-required"
            record["failure"] = {"code": "restore-readback-mismatch", "temporary_cleanup": None}
            record["history"].append({"event": "recovery-required", "at": _now()})
            _replace_record(folder, record)
            raise RepositoryHttpOriginalError("restore-readback-mismatch", record)
        record["state"] = "restored"
        record["failure"] = None
        record["history"].append({"event": "restored", "at": _now()})
        _replace_record(folder, record)
        record["record_path"] = str(record_path)
        return record
    finally:
        if temporary is not None and parent is not None:
            _remove_temporary(parent, temporary)
        if parent is not None:
            os.close(parent)
        os.close(folder)
