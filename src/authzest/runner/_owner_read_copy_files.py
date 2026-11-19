"""Materialize three inert owner-read artifacts in one new, retained POSIX directory."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

from authzest.codex.owner_read_suggestion import BASELINE_SHA256, _validate_rule, _validate_test
from authzest.runner._owner_policy_file_workspace import _identity, _root_identity, supported

FILES = ("availability.py", "test_owner_archived_read.py", "proposed-availability.txt")
_TEMP_PARENT = Path("/tmp")
_LIMIT = 4096


def copy_supported() -> bool:
    return supported() and os.scandir in os.supports_fd and os.mkdir in os.supports_dir_fd


def _verify_file(root: int, name: str, data: bytes, created: tuple[int, ...]) -> None:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or info.st_size != len(data)
            or _identity(info) != created
        ):
            raise ValueError("File identity changed")
        observed = bytearray()
        while len(observed) <= len(data):
            chunk = os.read(fd, len(data) + 1 - len(observed))
            if not chunk:
                break
            observed.extend(chunk)
        if (
            observed != data
            or _identity(os.fstat(fd)) != created
            or _identity(os.stat(name, dir_fd=root, follow_symlinks=False)) != created
        ):
            raise ValueError("File changed during verification")
    finally:
        os.close(fd)


def _verify_directory(root: int, path: Path, expected: tuple[int, ...]) -> None:
    opened = os.fstat(root)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or stat.S_IMODE(opened.st_mode) != 0o700
        or opened.st_uid != os.geteuid()
        or _root_identity(opened) != expected
        or _identity(os.stat(path, follow_symlinks=False)) != _identity(opened)
    ):
        raise ValueError("Directory identity changed")


def stage_private_copy(
    baseline: bytes, test: bytes, proposed: bytes, *, guard: Callable[[], None]
) -> dict:
    """Create a new fixed copy. A decision expiry before mkdir propagates to the coordinator."""
    contents = (baseline, test, proposed)
    if (
        any(type(data) is not bytes or not 0 < len(data) <= _LIMIT for data in contents)
        or hashlib.sha256(baseline).hexdigest() != BASELINE_SHA256
        or baseline == proposed
    ):
        raise ValueError("Invalid owner-read copy artifacts")
    _validate_rule(proposed.decode("ascii"))
    _validate_test(test.decode("ascii"))
    states = {name: {"state": "not-created"} for name in FILES}
    result = {
        "status": "creation-failed",
        "exit_code": 1,
        "path": None,
        "files": states,
        "stage": "check-platform",
        "interrupted": False,
    }
    if not copy_supported():
        return result

    created = {}
    try:
        with ExitStack() as handles:
            result["stage"] = "open-temp-parent"
            parent = _TEMP_PARENT.resolve(strict=True)
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
            parent_fd = os.open(parent, flags)
            handles.callback(os.close, parent_fd)
            parent_info = os.fstat(parent_fd)
            if not (
                parent_info.st_uid == 0
                and parent_info.st_mode & stat.S_ISVTX
                or parent_info.st_uid == os.geteuid()
                and stat.S_IMODE(parent_info.st_mode) == 0o700
            ):
                raise ValueError("Unsupported temporary directory permissions")
            name = "authzest-owner-read-" + secrets.token_hex(16)
            path = parent / name
            result["stage"] = "check-decision"
            if guard() is not None:
                raise ValueError("Invalid copy guard")

            # The name is known before dispatch so an interrupt can retain an uncertain location.
            result.update(stage="create-directory", path=str(path))
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                result["path"] = None
                raise
            except OSError:
                # An ordinary refusal with no entry should not advertise a retained directory.
                try:
                    os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    result["path"] = None
                except OSError:
                    pass  # Keep the selected location for an uncertain result.
                raise
            result["stage"] = "open-directory"
            root = os.open(name, flags, dir_fd=parent_fd)
            handles.callback(os.close, root)
            directory_id = _root_identity(os.fstat(root))
            _verify_directory(root, path, directory_id)
            for name, data in zip(FILES, contents, strict=True):
                _verify_directory(root, path, directory_id)
                result["stage"] = "create-" + name
                states[name]["state"] = "creation-attempted"
                fd = os.open(
                    name, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600, dir_fd=root
                )
                try:
                    states[name]["state"] = "created-unconfirmed"
                    os.fchmod(fd, 0o600)
                    view = memoryview(data)
                    while view:
                        written = os.write(fd, view)
                        if written <= 0:
                            raise OSError("Incomplete write")
                        view = view[written:]
                    os.fsync(fd)
                    created[name] = _identity(os.fstat(fd))
                finally:
                    os.close(fd)
            result["stage"] = "verify-copy"
            os.fsync(root)
            # Only these three entries are expected; reject an extra without enumerating the rest.
            initial = _identity(os.fstat(root))
            names = set()
            with os.scandir(root) as entries:
                for entry in entries:
                    if entry.name not in FILES or entry.name in names:
                        raise ValueError("Unexpected directory entry")
                    names.add(entry.name)
            if len(names) != len(FILES):
                raise ValueError("Missing directory entry")
            for name, data in zip(FILES, contents, strict=True):
                _verify_file(root, name, data, created[name])
            for name in FILES:
                if _identity(os.stat(name, dir_fd=root, follow_symlinks=False)) != created[name]:
                    raise ValueError("File changed during final verification")
            _verify_directory(root, path, directory_id)
            if _identity(os.fstat(root)) != initial:
                raise ValueError("Directory changed during verification")
            result["stage"] = "close-descriptors"
    except (OSError, ValueError, KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, TimeoutError) and result["stage"] == "check-decision":
            raise
        result["interrupted"] = isinstance(exc, KeyboardInterrupt | SystemExit)
        if result["path"] is not None:
            result["status"] = "incomplete"
        return result

    for name, data in zip(FILES, contents, strict=True):
        states[name].update(
            state="verified", sha256=hashlib.sha256(data).hexdigest(), identity=list(created[name])
        )
    result.update(
        status="prepared", exit_code=0, stage="complete", root_identity=list(directory_id)
    )
    return result
