import json
from pathlib import Path

from typer.testing import CliRunner

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
    assert result.stdout.strip() == "authzest 0.1.0"


def test_scan_can_return_json(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        '@app.get("/health")\ndef health():\n    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["python_files"] == 1
    assert payload["route_count"] == 1
