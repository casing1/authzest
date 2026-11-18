"""Read-only body import API, including streaming limits without Content-Length."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from authzest.api.app import create_app
from authzest.result_viewer import MAX_RESULT_BYTES
from test_result_viewer import record


def request(content, *, content_type="application/json", headers=None):
    async def run():
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/results/preview",
                content=content,
                headers={"content-type": content_type, **(headers or {})},
            )

    return asyncio.run(run())


def test_projects_uploaded_result_without_reading_any_referenced_paths():
    response = request(json.dumps(record()).encode())
    assert response.status_code == 200
    assert response.json()["provenance"] == "imported-unverified"
    assert "PRIVATE-DO-NOT" not in response.text


@pytest.mark.parametrize("content_type", ["text/plain", "multipart/form-data", ""])
def test_requires_explicit_json_upload(content_type):
    response = request(b"{}", content_type=content_type)
    assert response.status_code == 415


def test_rejects_path_request_without_opening_it():
    response = request(b'{"path":"/PRIVATE-DO-NOT-READ"}')
    assert response.status_code == 400
    assert "PRIVATE-DO-NOT" not in response.text


def test_enforces_streamed_limit_even_when_content_length_is_forged():
    async def chunks():
        for _ in range(9):
            yield b" " * (MAX_RESULT_BYTES // 8)

    response = request(chunks(), headers={"content-length": "1"})
    assert response.status_code == 413


def test_rejects_duplicate_keys_without_echoing_uploaded_text():
    response = request(b'{"private-secret":1,"private-secret":2}')
    assert response.status_code == 400 and "private-secret" not in response.text
