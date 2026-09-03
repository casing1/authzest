from __future__ import annotations

import hashlib
import os
import platform
import shutil
from importlib.metadata import version
from pathlib import Path


def normalized_platform() -> tuple[str, str]:
    system = {"darwin": "macos", "windows": "windows"}.get(
        platform.system().lower(), platform.system().lower()
    )
    machine = platform.machine().lower()
    architecture = "arm64" if machine in {"aarch64", "arm64"} else "x64"
    return system, architecture


def write_checksum(target: Path) -> Path:
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    checksum = target.with_name(f"{target.name}.sha256")
    checksum.write_bytes(f"{digest}  {target.name}\n".encode("ascii"))
    return checksum


def main() -> None:
    system, architecture = normalized_platform()
    release_label = os.environ.get("AUTHZEST_RELEASE_TAG") or version("authzest")
    release_label = release_label.removeprefix("v")
    extension = ".exe" if system == "windows" else ""
    source = Path("dist") / f"authzest{extension}"
    if not source.is_file():
        raise SystemExit(f"Built executable not found: {source}")

    release_dir = Path("release")
    release_dir.mkdir(exist_ok=True)
    target = release_dir / f"authzest-{release_label}-{system}-{architecture}{extension}"
    shutil.copy2(source, target)

    checksum = write_checksum(target)
    print(target)
    print(checksum)


if __name__ == "__main__":
    main()
