"""Explicitly enabled same-origin operator transport for the existing repair engine.

The launcher owns the controller, runtime path, origin and in-memory capability.
HTTP input selects neither files nor commands. A capability is not a human-review
receipt; the engine retains its current plan and file-state approval checks.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import re
import threading
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from authzest.api._owner_read_controller import UIWorkflowError

_MAX_BODY = 4096
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_RUN_ID = re.compile(r"[0-9a-f]{32}\Z")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(_):
    raise ValueError("invalid JSON number")


async def _body(request: Request) -> dict:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > _MAX_BODY:
            raise HTTPException(413, "AI request exceeds the 4 KiB limit")
        content.extend(chunk)
    try:
        value = json.loads(
            content.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant
        )
    except (UnicodeError, ValueError, RecursionError):
        raise HTTPException(400, "Invalid AI request") from None
    if type(value) is not dict:
        raise HTTPException(400, "Expected a JSON object")
    return value


def _run_id(value: str) -> str:
    if _RUN_ID.fullmatch(value) is None:
        raise HTTPException(404, "AI run unavailable")
    return value


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except UIWorkflowError as exc:
        raise HTTPException(exc.status_code, exc.code) from None


def _diagnostics() -> dict:
    # Existing trusted CLI metadata only. Never return its free-form detail,
    # executable path, login identity, provider output or credentials.
    from authzest.codex.app_server import SUPPORTED_CODEX_VERSION
    from authzest.diagnostics import collect_diagnostics

    report = collect_diagnostics()
    checks = {check.name: check for check in report.checks}
    codex, login = checks.get("Codex CLI"), checks.get("Codex login")
    status = "unknown"
    if codex is not None and codex.detail.startswith("not found;"):
        status = "unavailable"
    elif login is not None:
        status = "authenticated" if login.status == "ok" else "unauthenticated"
    version = "unknown"
    if codex is not None and codex.status == "ok":
        match = re.match(r"codex-cli ([0-9]+\.[0-9]+\.[0-9]+)(?:;|\s|$)", codex.detail)
        if match:
            version = "supported" if match[1] == SUPPORTED_CODEX_VERSION else "unsupported"
    return {"codex_status": status, "version_status": version, "model_access": "not-checked"}


def install_ai_routes(
    application: FastAPI,
    controller,
    *,
    origin: str,
    token: str,
    diagnostics: Callable | None = None,
) -> None:
    """Install one fixed local transport; called only by an explicit launcher."""
    if type(origin) is not str:
        raise ValueError("Expected a numeric loopback origin")
    matched = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})", origin)
    if matched is None or not 1 <= int(matched[1]) <= 65535 or str(int(matched[1])) != matched[1]:
        raise ValueError("Expected a numeric loopback origin")
    if type(token) is not str or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        raise ValueError("Expected a private launch capability")
    authority = origin.removeprefix("http://").encode("ascii")
    origin_bytes, token_bytes = origin.encode("ascii"), token.encode("ascii")
    diagnostic_lock = threading.Lock()
    diagnostic_check = diagnostics or _diagnostics

    def headers(response):
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
                ),
            }
        )
        return response

    @application.middleware("http")
    async def local_operator_access(request: Request, call_next):
        path = request.scope["path"]
        if path == "/api/ai" or path.startswith("/api/ai/"):
            raw = request.scope["headers"]

            def values(name):
                return [value for key, value in raw if key.lower() == name]

            hosts, origins = values(b"host"), values(b"origin")
            tokens, sites = values(b"x-authzest-token"), values(b"sec-fetch-site")
            if hosts != [authority] or len(origins) > 1 or origins and origins != [origin_bytes]:
                return headers(JSONResponse({"detail": "AI workspace origin denied"}, 403))
            if (
                len(tokens) != 1
                or len(tokens[0]) != len(token_bytes)
                or not hmac.compare_digest(tokens[0], token_bytes)
            ):
                return headers(JSONResponse({"detail": "AI workspace access denied"}, 401))
            if sites and sites != [b"same-origin"]:
                return headers(JSONResponse({"detail": "AI workspace origin denied"}, 403))
            if request.method not in ("GET", "HEAD"):
                if origins != [origin_bytes]:
                    return headers(JSONResponse({"detail": "AI workspace origin denied"}, 403))
                types = values(b"content-type")
                if len(types) != 1 or types[0].split(b";", 1)[0].strip().lower() != (
                    b"application/json"
                ):
                    return headers(JSONResponse({"detail": "Expected application/json"}, 415))
        return headers(await call_next(request))

    @application.get("/api/ai/session", tags=["local AI workflow"])
    def session():
        return {"run": _call(controller.current)}

    @application.post("/api/ai/runs", status_code=202, tags=["local AI workflow"])
    async def start(request: Request):
        body = await _body(request)
        model, timeout = body.get("model"), body.get("timeout_seconds", 120)
        if (
            set(body) - {"model", "timeout_seconds"}
            or type(model) is not str
            or _MODEL.fullmatch(model) is None
            or type(timeout) not in (int, float)
            or not 0 < timeout <= 120
        ):
            raise HTTPException(400, "Invalid AI run options")
        return _call(controller.start, model, timeout_seconds=timeout)

    @application.get("/api/ai/runs/{run_id}", tags=["local AI workflow"])
    def snapshot(run_id: str):
        return _call(controller.snapshot, _run_id(run_id))

    @application.post(
        "/api/ai/runs/{run_id}/decisions", status_code=202, tags=["local AI workflow"]
    )
    async def decide(run_id: str, request: Request):
        body = await _body(request)
        if (
            set(body) != {"prompt_id", "answer"}
            or type(body["prompt_id"]) is not str
            or type(body["answer"]) is not str
        ):
            raise HTTPException(400, "Expected the current prompt and typed answer")
        try:
            if (
                len(body["prompt_id"].encode("utf-8")) > 128
                or len(body["answer"].encode("utf-8")) > 256
            ):
                raise ValueError
        except (UnicodeError, ValueError):
            raise HTTPException(400, "Invalid decision text") from None
        return _call(controller.decide, _run_id(run_id), body["prompt_id"], body["answer"])

    @application.post("/api/ai/runs/{run_id}/cancel", status_code=202, tags=["local AI workflow"])
    async def cancel(run_id: str, request: Request):
        if await _body(request):
            raise HTTPException(400, "Cancel accepts no options")
        return _call(controller.cancel, _run_id(run_id))

    @application.get("/api/ai/runs/{run_id}/result", tags=["local AI workflow"])
    def download(run_id: str):
        run_id = _run_id(run_id)
        raw = _call(controller.download, run_id)
        return Response(
            raw,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="authzest-owner-read-{run_id}.json"'
            },
        )

    def checked_diagnostics():
        if not diagnostic_lock.acquire(blocking=False):
            raise HTTPException(409, "Codex diagnostics already running")
        try:
            value = diagnostic_check()
            if (
                type(value) is not dict
                or value.get("codex_status")
                not in ("authenticated", "unauthenticated", "unavailable", "unknown")
                or value.get("version_status") not in ("supported", "unsupported", "unknown")
                or value.get("model_access") != "not-checked"
            ):
                raise ValueError
            return {key: value[key] for key in ("codex_status", "version_status", "model_access")}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Codex diagnostics unavailable") from None
        finally:
            diagnostic_lock.release()

    @application.post("/api/ai/diagnostics", tags=["local AI workflow"])
    async def check_diagnostics(request: Request):
        if await _body(request):
            raise HTTPException(400, "Diagnostics accepts no options")
        return await asyncio.to_thread(checked_diagnostics)
