from __future__ import annotations

from pathlib import Path

from authzest.models import ScanReport
from authzest.parser import FastAPIRouteParser
from authzest.parser.repository import is_local_source

SKIPPED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "venv",
}


class RepositoryAnalyzer:
    """Coordinate source parsers and aggregate a repository-level report."""

    def __init__(self, parser: FastAPIRouteParser | None = None) -> None:
        self._parser = parser or FastAPIRouteParser()

    def analyze(self, root: Path) -> ScanReport:
        resolved_root = root.expanduser().resolve()
        if not resolved_root.exists():
            raise FileNotFoundError(f"Path does not exist: {resolved_root}")
        if not resolved_root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {resolved_root}")

        python_files = [
            path
            for path in resolved_root.rglob("*.py")
            if not any(
                part in SKIPPED_DIRECTORIES for part in path.relative_to(resolved_root).parts[:-1]
            )
            and is_local_source(path, resolved_root)
        ]
        result = self._parser.parse_repository(resolved_root, python_files)

        return ScanReport(
            root=resolved_root,
            python_files=len(python_files),
            routes=result.routes,
            parse_errors=result.errors,
        )
