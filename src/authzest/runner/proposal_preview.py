"""Bounded read-only input for offline previews; never follow embedded source paths."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from authzest.codex.contracts import MAX_JSON_BYTES
from authzest.codex.preview import preview_bundle, validate_preview_bundle


class PreviewInputError(ValueError):
    """Sanitized input failure, not an observed verification result."""


def preview_file_supported() -> bool:
    return os.name == "posix" and all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_NONBLOCK"))


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_bundle(path: Path) -> bytes:
    before = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_JSON_BYTES:
        raise PreviewInputError("Expected a bounded, nonempty regular bundle file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        if _stamp(opened) != _stamp(before) or not stat.S_ISREG(opened.st_mode):
            raise PreviewInputError("Bundle changed before read")
        chunks = []
        remaining = MAX_JSON_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 16_384))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if (
            len(data) != before.st_size
            or len(data) > MAX_JSON_BYTES
            or _stamp(os.fstat(fd)) != _stamp(before)
            or _stamp(os.stat(path, follow_symlinks=False)) != _stamp(before)
        ):
            raise PreviewInputError("Bundle changed during read")
        return data
    finally:
        os.close(fd)


def load_preview(path: Path) -> dict[str, Any]:
    """Read one selected file, then validate in memory before any presentation.

    O_NOFOLLOW protects the final component only. This detects ordinary changes, not
    all hostile concurrent writes, and says nothing about the embedded source paths.
    """
    if not preview_file_supported():
        raise PreviewInputError("File preview requires POSIX no-follow and nonblocking operations")
    try:
        bundle = validate_preview_bundle(_read_bundle(path).decode("utf-8"))
        return preview_bundle(bundle)
    except (OSError, ValueError) as exc:
        raise PreviewInputError(
            "Cannot preview: expected a stable regular UTF-8 bundle of at most 262144 bytes "
            "with valid, matching artifacts"
        ) from exc
