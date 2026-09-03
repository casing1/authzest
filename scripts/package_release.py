from __future__ import annotations

import hashlib
import platform
import shutil
from pathlib import Path


def normalized_platform() -> tuple[str, str]:
    system = {"darwin": "macos", "windows": "windows"}.get(
        platform.system().lower(), platform.system().lower()
    )
    machine = platform.machine().lower()
    architecture = "arm64" if machine in {"aarch64", "arm64"} else "x64"
    return system, architecture


def main() -> None:
    system, architecture = normalized_platform()
    extension = ".exe" if system == "windows" else ""
    source = Path("dist") / f"authguard{extension}"
    if not source.is_file():
        raise SystemExit(f"Built executable not found: {source}")

    release_dir = Path("release")
    release_dir.mkdir(exist_ok=True)
    target = release_dir / f"authguard-{system}-{architecture}{extension}"
    shutil.copy2(source, target)

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    checksum = target.with_name(f"{target.name}.sha256")
    checksum.write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    print(target)
    print(checksum)


if __name__ == "__main__":
    main()
