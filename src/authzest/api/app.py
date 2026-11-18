from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from authzest import __version__
from authzest.result_viewer import MAX_RESULT_BYTES, ResultViewError, preview_workflow_result
from authzest.runner import ScanRunner


def _default_frontend_dist() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root) / "frontend" / "dist"
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def _default_scan_root() -> Path:
    configured_root = os.environ.get("AUTHZEST_SCAN_ROOT")
    return Path(configured_root) if configured_root else Path.cwd()


def create_app(frontend_dist: Path | None = None, scan_root: Path | None = None) -> FastAPI:
    application = FastAPI(
        title="AuthZest API",
        version=__version__,
        description="Local API for source-aware FastAPI authorization analysis.",
    )
    runner = ScanRunner()
    resolved_scan_root = (scan_root or _default_scan_root()).expanduser().resolve()
    if not resolved_scan_root.is_dir():
        raise NotADirectoryError(f"Workspace is not a directory: {resolved_scan_root}")

    @application.get("/health", tags=["system"])
    @application.get("/api/health", tags=["system"], include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "authzest"}

    @application.post("/api/scans", tags=["analysis"])
    def scan_repository() -> dict[str, object]:
        try:
            return runner.run(resolved_scan_root).to_dict()
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/results/preview", tags=["results"])
    async def preview_result(request: Request) -> dict[str, object]:
        """Project explicitly uploaded bytes; never accept a path or retain a result."""
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/json"
        ):
            raise HTTPException(status_code=415, detail="Upload an application/json result")
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_RESULT_BYTES:
                raise HTTPException(status_code=413, detail="Result exceeds the 512 KiB limit")
            content.extend(chunk)
        try:
            return preview_workflow_result(bytes(content))
        except ResultViewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    resolved_frontend = frontend_dist or _default_frontend_dist()
    if resolved_frontend.is_dir():
        assets = resolved_frontend / "assets"
        if assets.is_dir():
            application.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @application.get("/", include_in_schema=False)
        def dashboard() -> FileResponse:
            return FileResponse(resolved_frontend / "index.html")
    else:

        @application.get("/", include_in_schema=False)
        def api_root() -> dict[str, str]:
            return {
                "name": "AuthZest",
                "message": "Build frontend/ to serve the dashboard here.",
                "docs": "/docs",
            }

    return application


app = create_app()
