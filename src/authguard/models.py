from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Route:
    """A FastAPI-style route found in Python source."""

    path: str
    methods: tuple[str, ...]
    function: str
    file: Path
    line: int

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        data = asdict(self)
        file_path = self.file
        if root is not None:
            with suppress(ValueError):
                file_path = file_path.relative_to(root)
        data["file"] = str(file_path)
        data["methods"] = list(self.methods)
        return data


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Framework-neutral result returned by the analysis core."""

    root: Path
    python_files: int
    routes: tuple[Route, ...] = field(default_factory=tuple)
    parse_errors: tuple[str, ...] = field(default_factory=tuple)
    codex_status: str = "disabled"

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "python_files": self.python_files,
            "route_count": len(self.routes),
            "routes": [route.to_dict(self.root) for route in self.routes],
            "parse_errors": list(self.parse_errors),
            "codex_status": self.codex_status,
        }
