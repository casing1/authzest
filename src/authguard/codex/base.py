from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from authguard.models import Route


@dataclass(frozen=True, slots=True)
class CodexAnalysisRequest:
    repository: Path
    routes: tuple[Route, ...]


@dataclass(frozen=True, slots=True)
class CodexFinding:
    title: str
    severity: str
    summary: str


class CodexUnavailableError(RuntimeError):
    """Raised when an AI analysis is requested without a configured adapter."""


class CodexAdapter(Protocol):
    """Boundary implemented later by a Codex CLI or App Server adapter."""

    @property
    def name(self) -> str: ...

    async def analyze(self, request: CodexAnalysisRequest) -> tuple[CodexFinding, ...]: ...
