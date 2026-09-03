from __future__ import annotations

from pathlib import Path

from authzest.analyzer import RepositoryAnalyzer
from authzest.models import ScanReport


class ScanRunner:
    """Application service shared by CLI and HTTP transports."""

    def __init__(self, analyzer: RepositoryAnalyzer | None = None) -> None:
        self._analyzer = analyzer or RepositoryAnalyzer()

    def run(self, root: Path) -> ScanReport:
        return self._analyzer.analyze(root)
