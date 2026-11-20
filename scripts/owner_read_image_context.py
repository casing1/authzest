"""Write the fixed owner-read dependency-image build context as an uncompressed tar stream."""

from __future__ import annotations

import io
import os
import stat
import sys
import tarfile
from pathlib import Path
from typing import BinaryIO

_ROOT = Path(__file__).resolve().parents[1]
# Include only the image guest's first-party imports and the packaged positive sample.
_MODULES = (
    "__init__",
    "analyzer/__init__",
    "analyzer/repository",
    "codex/__init__",
    "codex/base",
    "codex/contracts",
    "codex/diagnostics",
    "codex/disabled",
    "codex/fixture_draft",
    "codex/owner_read_suggestion",
    "codex/proposals",
    "models",
    "owner_read_demo/__init__",
    "owner_read_demo/app",
    "owner_read_demo/availability",
    "owner_read_demo/checks",
    "owner_read_demo/positive_regression",
    "owner_read_demo/rehearsal",
    "parser/__init__",
    "parser/dependencies",
    "parser/fastapi",
    "parser/repository",
    "runner/__init__",
    "runner/scan",
)
_FILES = (
    ("Dockerfile", "runtime/owner_read/Dockerfile"),
    ("assets/guest.py", "runtime/owner_read/guest.py"),
    ("assets/owner_read_kernel.py", "runtime/owner_read/owner_read_kernel.py"),
    ("assets/_guest_common.py", "runtime/generated_repair/_guest_common.py"),
    *((f"package/authzest/{name}.py", f"src/authzest/{name}.py") for name in _MODULES),
)


def _read_source(relative_name: str) -> bytes:
    source = _ROOT / relative_name
    if source.resolve(strict=True) != source:
        raise ValueError("Linked build input")
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Expected regular single-link source")
        data = stream.read(262145)
        if len(data) != info.st_size or len(data) > 262144:
            raise ValueError("Unexpected build input size")
    return data


def write_context(output: BinaryIO) -> None:
    # Read the complete fixed list before writing anything to the build stream.
    files = [(name, _read_source(relative)) for name, relative in _FILES]
    with tarfile.open(fileobj=output, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in files:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o444
            archive.addfile(entry, io.BytesIO(data))


def main() -> int:
    if len(sys.argv) != 1 or sys.stdout.isatty() or os.name != "posix":
        print("On POSIX, redirect the fixed build context to a new tar file.", file=sys.stderr)
        return 2
    write_context(sys.stdout.buffer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
