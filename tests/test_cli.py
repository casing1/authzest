import json
from pathlib import Path

from typer.testing import CliRunner

from authzest import __version__
from authzest.cli import app

runner = CliRunner()


def test_help_lists_core_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "scan" in result.stdout
    assert "doctor" in result.stdout
    assert "ui" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"authzest {__version__}"


def test_scan_can_return_json(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        '@app.get("/health")\ndef health():\n    return {"status": "ok"}\n'
        'cache = object()\n@cache.get("/cache")\ndef cached(): pass\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["python_files"] == 1
    assert payload["route_count"] == 1
    assert payload["routes"][0]["path"] == "/health"


def test_scan_json_reports_each_router_registration(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import APIRouter, FastAPI\n"
        "app = FastAPI()\n"
        'router = APIRouter(prefix="/users")\n'
        '@router.get("/me")\ndef read_me(): pass\n'
        'app.include_router(router, prefix="/v1")\n'
        'app.include_router(router, prefix="/v2")\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["python_files"] == 1
    assert payload["parse_errors"] == []
    assert payload["route_count"] == 2
    assert [route["path"] for route in payload["routes"]] == ["/v1/users/me", "/v2/users/me"]
    assert all(route["file"] == "main.py" for route in payload["routes"])
