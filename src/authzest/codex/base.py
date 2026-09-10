from __future__ import annotations

from typing import Protocol

from authzest.codex.contracts import CodexAnalysisRequest


class CodexUnavailableError(RuntimeError):
    """Raised when an AI analysis is requested without a configured adapter."""


class CodexAdapter(Protocol):
    """Trusted transport implementation; source input never grants tools or execution."""

    @property
    def name(self) -> str: ...

    async def analyze(self, request: CodexAnalysisRequest) -> str:
        """Return untrusted JSON for validation, not authoritative findings."""
        ...
