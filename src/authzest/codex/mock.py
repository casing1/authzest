"""Scripted transport for offline tests; never synthesizes model results."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from authzest.codex.base import CodexUnavailableError
from authzest.codex.contracts import CodexAnalysisRequest, canonical


@dataclass(slots=True)
class MockCodexAdapter:
    response: str
    behavior: Literal["success", "failure", "unavailable", "wait", "cancel"] = "success"
    name: str = field(default="mock", init=False)
    calls: int = field(default=0, init=False)
    finished: bool = field(default=False, init=False)

    async def analyze(self, request: CodexAnalysisRequest) -> str:
        self.calls += 1
        try:
            if request.to_dict()["config"]["provider"] != "mock":
                raise CodexUnavailableError("Mock transport cannot impersonate a live provider")
            if self.behavior == "failure":
                raise RuntimeError("Scripted transport failure")
            if self.behavior == "unavailable":
                raise CodexUnavailableError("Scripted provider unavailable")
            if self.behavior == "cancel":
                raise asyncio.CancelledError
            if self.behavior == "wait":
                await asyncio.Event().wait()
            if self.behavior not in ("success", "wait"):
                raise ValueError("Unknown mock behavior")
            return self.response
        finally:
            self.finished = True


def scripted_response(request: CodexAnalysisRequest, answers: dict[str, str | None]) -> str:
    """Build a test response from explicit caller scripts, never evaluator labels."""
    payload = request.to_dict()
    # Use a source citation in both comparison modes, not privileged extracted evidence.
    reference = next(item["id"] for item in payload["evidence"] if item["kind"] == "source")
    return canonical(
        {
            "schema_version": payload["schema_version"],
            "request_id": request.request_id,
            "identity": {
                key: payload["config"][key]
                for key in ("provider", "model", "adapter_version", "prompt_version")
            },
            "usage": None,
            "answers": [
                {
                    "question_id": key,
                    "status": "unknown" if value is None else "hypothesis",
                    "answer": value,
                    "explanation": "Scripted offline response; not a model judgment.",
                    "evidence_ids": [reference],
                    "assumptions": [],
                    "unknowns": ["Runtime behavior is not established by this fixture."],
                    "review_questions": ["Does the declared policy match the intended behavior?"],
                }
                for key, value in answers.items()
            ],
        }
    )
