from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from authzest.runner import ScanRunner


class ScanRequest(BaseModel):
    path: str


def _default_frontend_dist() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root) / "frontend" / "dist"
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    application = FastAPI(
        title="AuthZest API",
        version="0.1.0",
        description="Local API for source-aware FastAPI authorization analysis.",
    )
    runner = ScanRunner()

    @application.get("/health", tags=["system"])
    @application.get("/api/health", tags=["system"], include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "authzest"}

    @application.post("/api/scans", tags=["analysis"])
    def scan_repository(request: ScanRequest) -> dict[str, object]:
        try:
            return runner.run(Path(request.path)).to_dict()
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
