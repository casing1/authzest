"""Smoke an explicitly selected AuthZest binary, without executing scanned source or Codex."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

CHECKOUT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "fastapi_inventory": ("bounded", 4, 3),
    "fastapi_dependencies": ("bounded", 1, 2),
    "fastapi_inheritance": ("bounded", 1, 3),
    "fastapi_partial": ("partial", 1, 1),
}


class SmokeError(RuntimeError):
    """A release smoke check failed."""


def selected_binary(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise SmokeError(f"Selected binary is not a regular file: {path}")
    return resolved


def select_artifact(directory: Path) -> tuple[Path, str]:
    if not directory.is_dir():
        raise SmokeError(f"Artifact directory is missing: {directory}")
    candidates = sorted(
        path
        for path in directory.iterdir()
        if path.name.startswith("authzest-") and not path.name.endswith(".sha256")
    )
    if len(candidates) != 1:
        raise SmokeError(
            "Select a single-platform artifact directory with exactly one AuthZest asset."
        )
    binary = candidates[0]
    checksum = binary.with_name(binary.name + ".sha256")
    if binary.is_symlink() or checksum.is_symlink():
        raise SmokeError("Artifact and checksum must be regular files, not symlinks.")
    binary = selected_binary(binary)
    if not checksum.is_file():
        raise SmokeError(f"Matching checksum is missing: {checksum}")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if checksum.read_bytes() != f"{digest}  {binary.name}\n".encode("ascii"):
        raise SmokeError(f"Checksum mismatch or invalid manifest for {binary.name}")
    return binary, digest


def child_environment(bin_directory: Path) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "CONDA", "_PYI", "PYINSTALLER"))
        and key.upper() != "VIRTUAL_ENV"
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        NO_COLOR="1",
        TERM="dumb",
    )
    environment["PATH"] = str(bin_directory) + os.pathsep + environment.get("PATH", "")
    return environment


def run_command(
    binary: Path,
    arguments: list[str],
    expected_code: int,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
    *,
    allow_stderr: bool = False,
) -> str:
    try:
        result = subprocess.run(
            [str(binary), *arguments],
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SmokeError(f"Timed out after {timeout:g}s: {arguments}") from exc
    except (OSError, UnicodeError) as exc:
        raise SmokeError(f"Cannot run selected binary {binary}: {exc}") from exc
    if result.returncode != expected_code:
        raise SmokeError(
            f"{arguments}: expected exit {expected_code}, got {result.returncode}; "
            f"stderr={result.stderr[:500]!r}"
        )
    if result.stderr and not allow_stderr:
        raise SmokeError(f"{arguments}: unexpected stderr: {result.stderr[:500]!r}")
    if allow_stderr and (not result.stderr.startswith("Error:") or result.stdout):
        raise SmokeError(
            "Invalid-root scan must report an error on stderr, without JSON on stdout."
        )
    return result.stdout


def source_report(fixture: Path) -> dict[str, Any]:
    # Use this checkout's trusted analyzer, never a target module or an ambient older installation.
    source = CHECKOUT / "src"
    sys.path.insert(0, str(source))
    try:
        import authzest.runner

        if not Path(authzest.runner.__file__).resolve().is_relative_to(source):
            raise SmokeError("Expected-report analyzer is not loaded from this checkout.")
        return authzest.runner.ScanRunner().run(fixture).to_dict()
    finally:
        sys.path.pop(0)


def normalized_report(payload: object, root: Path) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("root") != str(root.resolve()):
        raise SmokeError("Report root does not match the selected owned fixture.")

    def normalize(value: object) -> Any:
        if isinstance(value, dict):
            return {
                key: item.replace("\\", "/")
                if key == "file" and isinstance(item, str)
                else normalize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    result = normalize(payload)
    result["root"] = "<owned-fixture>"
    return result


def first_difference(expected: object, actual: object, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return f"{path}: report fields differ"
        for key in expected:
            if difference := first_difference(expected[key], actual[key], f"{path}.{key}"):
                return difference
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected {len(expected)} items, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if difference := first_difference(left, right, f"{path}[{index}]"):
                return difference
    elif expected != actual:
        return f"{path}: expected {str(expected)[:120]!r}, got {str(actual)[:120]!r}"
    return None


def smoke_binary(
    binary: Path,
    expected_version: str,
    timeout: float = 45,
    *,
    artifact_digest: str | None = None,
) -> list[str]:
    binary = selected_binary(binary)
    if not math.isfinite(timeout) or timeout <= 0:
        raise SmokeError("Timeout must be finite and positive.")
    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="authzest-release-smoke-") as temporary:
        workspace = Path(temporary).resolve()
        bin_directory, cwd = workspace / "bin", workspace / "working"
        bin_directory.mkdir()
        cwd.mkdir()
        copied = bin_directory / ("authzest.exe" if binary.suffix.lower() == ".exe" else "authzest")
        shutil.copy2(binary, copied)
        if artifact_digest is not None:
            if hashlib.sha256(copied.read_bytes()).hexdigest() != artifact_digest:
                raise SmokeError("Copied artifact no longer matches the verified checksum.")
            # Downloads can lose +x. Only modify the selected, verified temporary copy.
            copied.chmod(copied.stat().st_mode | stat.S_IXUSR)
        environment = child_environment(bin_directory)
        fixtures = []
        for name, (status, files, routes) in FIXTURES.items():
            source = CHECKOUT / "examples" / name
            if not source.is_dir():
                raise SmokeError(f"Owned smoke fixture is missing: {source}")
            expected = source_report(source)
            baseline = (
                expected.get("schema_version"),
                expected.get("analysis_status"),
                expected.get("python_files"),
                expected.get("route_count"),
                expected.get("codex_status"),
            )
            if baseline != ("1.2", status, files, routes, "disabled"):
                raise SmokeError(f"Owned fixture baseline changed: {name}")
            target = workspace / "fixtures" / name
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            fixtures.append((name, target, normalized_report(expected, source), status))
        selected = (
            [("relocated verified artifact", copied)]
            if artifact_digest is not None
            else [("selected binary", binary), ("relocated binary copy", copied)]
        )
        for label, executable in selected:

            def command(
                arguments: list[str],
                code: int = 0,
                *,
                allow_stderr: bool = False,
                selected: Path = executable,
            ) -> str:
                return run_command(
                    selected,
                    arguments,
                    code,
                    cwd,
                    environment,
                    timeout,
                    allow_stderr=allow_stderr,
                )

            if command(["--version"]).strip() != f"authzest {expected_version}":
                raise SmokeError(f"{label}: installed version does not match {expected_version}")
            help_text = command(["--help"])
            if not all(fragment in help_text for fragment in ("Usage:", "scan", "--version")):
                raise SmokeError(f"{label}: help output is incomplete")
            checks.append(f"{label}: version and help")
            for name, target, expected, status in fixtures:
                variants = [(True, 0)] if status == "bounded" else [(False, 0), (True, 1)]
                for strict, code in variants:
                    arguments = ["scan", str(target), "--json"] + (["--strict"] if strict else [])
                    try:
                        actual = json.loads(command(arguments, code))
                    except json.JSONDecodeError as exc:
                        raise SmokeError(f"{label}/{name}: stdout is not valid JSON") from exc
                    difference = first_difference(expected, normalized_report(actual, target))
                    if difference:
                        raise SmokeError(f"{label}/{name}: {difference}")
                    checks.append(f"{label}: {name} JSON strict={strict} exit={code}")
            inventory = workspace / "fixtures" / "fastapi_inventory"
            text = command(["scan", str(inventory), "--strict"])
            if not all(fragment in text for fragment in ("FastAPI routes: 3", "Analysis: bounded")):
                raise SmokeError(f"{label}: text scan is incomplete")
            command(
                ["scan", str(workspace / "does-not-exist"), "--json", "--strict"],
                2,
                allow_stderr=True,
            )
            checks.append(f"{label}: text scan and invalid-root exit=2")
            print(
                f"PASS {label}: version/help, four owned fixtures, strict/JSON/text, invalid root",
                flush=True,
            )
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--binary", type=Path, help="Exact trusted built executable to test.")
    selection.add_argument(
        "--artifact-dir", type=Path, help="One platform's downloaded asset/checksum directory."
    )
    parser.add_argument(
        "--expected-version", help="PEP 440 version; defaults to this checkout's pyproject.toml."
    )
    parser.add_argument(
        "--timeout", type=float, default=45, help="Per-command timeout in seconds (default: 45)."
    )
    arguments = parser.parse_args()
    try:
        version = arguments.expected_version
        if version is None:
            with (CHECKOUT / "pyproject.toml").open("rb") as source:
                version = tomllib.load(source)["project"]["version"]
        binary, digest = (
            select_artifact(arguments.artifact_dir)
            if arguments.artifact_dir
            else (arguments.binary, None)
        )
        checks = smoke_binary(binary, version, arguments.timeout, artifact_digest=digest)
    except (SmokeError, OSError, KeyError, ValueError) as exc:
        raise SystemExit(f"Release smoke failed: {exc}") from exc
    print(f"Release smoke passed: {len(checks)} checks. No Codex or target code was executed.")
    print(
        "Relocation smoke is not clean-machine installation, upgrade, "
        "signing, or notarization verification."
    )


if __name__ == "__main__":
    main()
