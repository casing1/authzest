from authzest.codex.base import (
    CodexAnalysisRequest,
    CodexUnavailableError,
)


class DisabledCodexAdapter:
    """Safe default used until the user explicitly configures Codex integration."""

    @property
    def name(self) -> str:
        return "disabled"

    async def analyze(self, request: CodexAnalysisRequest) -> str:
        del request
        raise CodexUnavailableError("Codex integration is not configured.")
