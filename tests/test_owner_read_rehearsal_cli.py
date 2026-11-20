"""Check that the human and JSON views report the same fixed rehearsal."""

import json

from typer.testing import CliRunner

from authzest.cli import app
from authzest.runner import owner_read_rehearsal as runner


def test_human_and_json_show_actual_phase_states(monkeypatch):
    def matched(status, http, intended):
        return {
            "status": "matched",
            "observation": {"regression": {"status": status, "response": {"status_code": http}}},
            "comparison": {"intended_matches": intended, "checks_total": 7},
            "failure": None,
        }

    result = {
        "status": "completed",
        "exit_code": 0,
        "baseline": matched("assertion-failed", 403, 6),
        "reference": matched("passed", 200, 7),
    }
    monkeypatch.setattr(runner, "run_rehearsal", lambda: result)
    cli = CliRunner()
    text = cli.invoke(app, ["owner-read-rehearse"])
    assert text.exit_code == 0
    for expected in ("assertion-failed", "HTTP 403", "6 / 7", "HTTP 200", "7 / 7"):
        assert expected in text.stdout
    assert json.loads(cli.invoke(app, ["owner-read-rehearse", "--json"]).stdout) == result


def test_missing_optional_dependencies_has_actionable_help(monkeypatch):
    result = {
        "status": "missing-dependencies",
        "exit_code": 2,
        "baseline": {"status": "failed", "failure": "missing-dependencies"},
        "reference": {"status": "not-run"},
    }
    monkeypatch.setattr(runner, "run_rehearsal", lambda: result)
    invocation = CliRunner().invoke(app, ["owner-read-rehearse"])
    assert invocation.exit_code == 2
    assert 'python -m pip install -e ".[owner-read]"' in invocation.stdout
    assert "HTTP 200" not in invocation.stdout
