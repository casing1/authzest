from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from authzest import __version__
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
