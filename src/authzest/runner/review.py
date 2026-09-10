"""Optional review service, deliberately not connected to scan/CLI/API."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from authzest.codex.base import CodexAdapter, CodexUnavailableError
from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    validate_response,
)
from authzest.codex.disabled import DisabledCodexAdapter
from authzest.models import ScanReport


@dataclass(frozen=True, slots=True)
class ReviewResult:
    report: ScanReport
    status: Literal["ok", "not-approved", "unavailable", "timeout", "invalid-response", "error"]
    response: ValidatedResponse | None
    provenance: dict[str, Any]


async def review_report(
    report: ScanReport,
    request: CodexAnalysisRequest,
    *,
    approved_request_id: str | None = None,
    adapter: CodexAdapter | None = None,
    timeout_seconds: float = 10.0,
) -> ReviewResult:
    """Require exact snapshot approval; preserve the caller's deterministic report.

    Cancellation propagates to the caller and the cooperative async adapter. This is not
    a process sandbox or a user-facing consent system; live transports belong to #35.
    """
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError("Timeout must be finite and between 0 and 120 seconds")
    payload = request.to_dict()
    provenance = {
        "request_id": request.request_id,
        "schema_version": payload["schema_version"],
        "report_schema_version": payload["report_schema_version"],
        "mode": payload["mode"],
        "config": payload["config"],
        "source_revision": payload["source_revision"],
        "source_identity": payload["source_identity"],
        "evidence_ids": [item["id"] for item in payload["evidence"]],
        "returned_identity": None,
        "usage": None,
        "latency_ms": None,
    }
    if approved_request_id != request.request_id:
        return ReviewResult(report, "not-approved", None, provenance)
    selected = adapter if adapter is not None else DisabledCodexAdapter()
    start = perf_counter()
    response = None
    try:
        async with asyncio.timeout(timeout_seconds):
            raw = await selected.analyze(request)
        response = validate_response(raw, request)
        provenance["returned_identity"] = response.to_dict()["identity"]
        provenance["usage"] = response.to_dict()["usage"]
        status = "ok"
    except CodexUnavailableError:
        status = "unavailable"
    except TimeoutError:
        status = "timeout"
    except ContractError:
        status = "invalid-response"
    except asyncio.CancelledError:
        raise
    except Exception:
        # Never publish exception details that could contain source or credentials.
        status = "error"
    provenance["latency_ms"] = (perf_counter() - start) * 1000
    return ReviewResult(report, status, response, provenance)
