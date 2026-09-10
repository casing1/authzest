from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

from authzest import __version__

DiagnosticStatus = Literal["ok", "warning", "error"]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
ExecutableFinder = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    status: DiagnosticStatus
    detail: str
    remedy: str | None = None


@dataclass(frozen=True, slots=True)
class DoctorReport:
    version: str
    checks: tuple[DiagnosticCheck, ...]

    @property
    def ready(self) -> bool:
        return not any(check.status == "error" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "ready": self.ready,
            "checks": [asdict(check) for check in self.checks],
        }


def _run_command(command: Sequence[str], run: CommandRunner) -> subprocess.CompletedProcess[str]:
    return run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )


def collect_diagnostics(
    *,
    which: ExecutableFinder = shutil.which,
    run: CommandRunner = subprocess.run,
) -> DoctorReport:
    """Collect local readiness information without reading credential files."""
    checks: list[DiagnosticCheck] = []
    python_version = sys.version_info[:3]
    python_detail = ".".join(str(part) for part in python_version)
    if python_version >= (3, 12):
        checks.append(DiagnosticCheck("Python", "ok", python_detail))
    else:
        checks.append(
            DiagnosticCheck(
                "Python",
                "error",
                python_detail,
                "Install Python 3.12 or newer, then reinstall AuthZest.",
            )
        )

    codex_path = which("codex")
    if codex_path is None:
        checks.append(
            DiagnosticCheck(
                "Codex CLI",
                "warning",
                "not found; local static scans still work",
                "AI analysis is not implemented; no Codex setup is needed for local scans.",
            )
        )
        return DoctorReport(version=__version__, checks=tuple(checks))

    try:
        version_result = _run_command((codex_path, "--version"), run)
        version_text = version_result.stdout.strip() or "installed"
        version_status: DiagnosticStatus = "ok" if version_result.returncode == 0 else "warning"
        checks.append(
            DiagnosticCheck(
                "Codex CLI",
                version_status,
                f"{version_text}; diagnostic only; AI analysis is not implemented",
            )
        )

        login_result = _run_command((codex_path, "login", "status"), run)
        if login_result.returncode == 0:
            login_text = login_result.stdout.strip() or "authenticated"
            checks.append(DiagnosticCheck("Codex login", "ok", login_text))
        else:
            checks.append(
                DiagnosticCheck(
                    "Codex login",
                    "warning",
                    "not authenticated; local static scans still work",
                    "This is an optional diagnostic; logging in does not enable AI analysis.",
                )
            )
    except (OSError, subprocess.TimeoutExpired):
        checks.append(
            DiagnosticCheck(
                "Codex CLI",
                "warning",
                "installed but could not be checked",
                "AI analysis is not implemented; this optional check does not block local scans.",
            )
        )

    return DoctorReport(version=__version__, checks=tuple(checks))
