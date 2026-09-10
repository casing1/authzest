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


def test_scan_json_reports_cross_file_routes_with_source_provenance(tmp_path: Path) -> None:
    package = tmp_path / "api"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "users.py").write_text(
        "from fastapi import APIRouter\n"
        'router = APIRouter(prefix="/users")\n'
        '@router.get("/me")\ndef read_me(): pass\n',
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from api import users\n"
        "app = FastAPI()\n"
        'app.include_router(users.router, prefix="/v1")\n'
        'app.include_router(users.router, prefix="/v2")\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["python_files"] == 3
    assert payload["parse_errors"] == []
    assert payload["route_count"] == 2
    assert [route["path"] for route in payload["routes"]] == ["/v1/users/me", "/v2/users/me"]
    assert all(route["file"] == str(Path("api/users.py")) for route in payload["routes"])
    assert all(route["line"] == 4 for route in payload["routes"])
    assert all(route["methods"] == ["GET"] for route in payload["routes"])


def test_scan_text_distinguishes_equal_filenames_in_different_directories(tmp_path: Path) -> None:
    for package in ("api", "admin"):
        directory = tmp_path / package
        directory.mkdir()
        (directory / "users.py").write_text(
            "from fastapi import APIRouter\nrouter = APIRouter()\n"
            f'@router.get("/{package}/users")\ndef read_users(): pass\n',
            encoding="utf-8",
        )

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert f"({Path('api/users.py')}:4)" in result.stdout
    assert f"({Path('admin/users.py')}:4)" in result.stdout


def test_scan_text_displays_parse_errors_without_discarding_routes(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\ndef health(): pass\n',
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "GET     /health  (main.py:4)" in result.stdout
    assert "Parse errors: 1 (partial source inventory)" in result.stderr
    assert str(tmp_path / "broken.py") in result.stderr
    assert "invalid syntax" in result.stderr


def test_scan_json_keeps_parse_errors_in_the_existing_contract(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "root",
        "python_files",
        "route_count",
        "routes",
        "parse_errors",
        "codex_status",
    }
    assert payload["python_files"] == 1
    assert payload["route_count"] == 0
    assert len(payload["parse_errors"]) == 1
    assert str(tmp_path / "broken.py") in payload["parse_errors"][0]
    assert result.stderr == ""
