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
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans", json={"path": str(tmp_path)})

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["route_count"] == 1
