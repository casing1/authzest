import asyncio
from pathlib import Path

import httpx

from authzest.api.app import create_app


def test_health_endpoint() -> None:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "authzest"}


def test_scan_endpoint(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        '@router.delete("/tokens/{token_id}")\ndef revoke_token():\n    pass\n',
        encoding="utf-8",
    )

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(scan_root=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["route_count"] == 1


def test_scan_endpoint_does_not_accept_a_caller_controlled_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "inside.py").write_text('@app.get("/inside")\ndef inside(): pass\n')
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.py").write_text('@app.get("/outside")\ndef outside(): pass\n')

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(scan_root=workspace))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans", json={"path": str(outside)})

    response = asyncio.run(request())

    payload = response.json()
    assert response.status_code == 200
    assert payload["root"] == str(workspace.resolve())
    assert payload["route_count"] == 1
    assert payload["routes"][0]["path"] == "/inside"

    operation = create_app(scan_root=workspace).openapi()["paths"]["/api/scans"]["post"]
    assert "requestBody" not in operation
