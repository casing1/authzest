import asyncio
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from authzest.api.app import create_app
from authzest.cli import app
from authzest.runner import ScanRunner

runner = CliRunner()


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("strict", [False, True])
def test_partial_cli_contract_preserves_output_before_optional_failure(
    tmp_path: Path, json_output: bool, strict: bool
) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    arguments = ["scan", str(tmp_path)]
    if json_output:
        arguments.append("--json")
    if strict:
        arguments.append("--strict")
    result = runner.invoke(app, arguments)
    assert result.exit_code == (1 if strict else 0)
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == "1.0"
        assert payload["analysis_status"] == "partial"
        assert payload["diagnostics"][0]["location"]["file"] == "broken.py"
        assert result.stderr == ""
    else:
        assert "Analysis: partial" in result.stdout
        assert "not a security verdict" in result.stdout
        assert "source-parse-error" in result.stderr


def test_strict_empty_inventory_is_bounded_not_a_security_pass(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path), "--strict", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["analysis_status"] == "bounded"
    assert payload["diagnostics"] == []
    assert payload["route_count"] == 0


def test_strict_invalid_input_retains_exit_two(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path / "absent"), "--strict", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Error:" in result.stderr


def test_cli_api_and_core_share_registration_contract(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI, APIRouter\n"
        "app = FastAPI()\nrouter = APIRouter()\n"
        '@router.get("/items")\ndef items(): pass\n'
        'app.include_router(router, prefix="/v1")\n'
        'app.include_router(router, prefix="/v1")\n',
        encoding="utf-8",
    )

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(scan_root=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans")

    response = asyncio.run(request())
    cli = runner.invoke(app, ["scan", str(tmp_path), "--json"])
    assert response.status_code == 200
    assert cli.exit_code == 0
    payload = response.json()
    assert payload == json.loads(cli.stdout) == ScanRunner().run(tmp_path).to_dict()
    assert payload["analysis_status"] == "bounded"
    assert len({route["registration_id"] for route in payload["routes"]}) == 2
    text = runner.invoke(app, ["scan", str(tmp_path)])
    for route in payload["routes"]:
        assert route["registration_id"] in text.stdout
    assert "App: main.py:2:" in text.stdout
    assert "Include: main.py:6:" in text.stdout
    assert "Include: main.py:7:" in text.stdout


def test_api_keeps_partial_analysis_http_success_with_diagnostics(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(scan_root=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["analysis_status"] == "partial"
    assert response.json()["diagnostics"][0]["code"] == "source-parse-error"
