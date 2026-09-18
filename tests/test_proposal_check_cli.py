"""Only the selected bundle file is read; checking declarations never executes source."""

import asyncio
import builtins
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest.cli import app
from authzest.codex.contracts import MAX_JSON_BYTES
from authzest.parser.fastapi import FastAPIRouteParser
from authzest.runner import ScanRunner
from authzest.runner import proposal_check as workflow
from authzest.runner import proposal_preview as reader
from test_declaration_check import BASE, WITH_DEPENDENCY, bundle_for

runner = CliRunner()
posix_only = pytest.mark.skipif(not reader.preview_file_supported(), reason="Bounded POSIX reader")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Proposal checking must not start a process, provider or network connection")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.mark.parametrize("color", [False, True])
def test_help_is_discoverable_without_inspecting_any_input(monkeypatch, color):
    monkeypatch.setattr(workflow, "load_check", lambda *a: pytest.fail("No bundle reads for help"))
    result = runner.invoke(app, ["proposal-check", "--help"], color=color)
    assert result.exit_code == 0
    assert "--json" in unstyle(result.stdout)
    assert "proposal-check" in unstyle(runner.invoke(app, ["--help"], color=color).stdout)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["one.json", "two.json"],
        ["one.json", "--yes"],
        ["one.json", "--model=x"],
        ["one.json", "--runtime-check"],
        ["one.json", "--apply"],
    ],
)
def test_cli_requires_one_bundle_and_exposes_no_approval_or_runtime_options(monkeypatch, args):
    monkeypatch.setattr(workflow, "load_check", lambda *a: pytest.fail("Reject before input read"))
    assert runner.invoke(app, ["proposal-check", *args]).exit_code == 2


@posix_only
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("outcome", ["matched", "mismatched", "unknown", "not-evaluated"])
def test_zero_exit_means_processed_not_a_security_or_expectation_pass(tmp_path, as_json, outcome):
    bundle = bundle_for(
        after=WITH_DEPENDENCY
        if outcome != "unknown"
        else WITH_DEPENDENCY + "\nother = FastAPI()\n",
        observation="policy-intent" if outcome == "not-evaluated" else "dependency-declarations",
        expected={"intent": "public"}
        if outcome == "not-evaluated"
        else {"count": 2 if outcome == "mismatched" else 1},
    )
    path = tmp_path / "bundle.json"
    path.write_text(bundle.payload_json)
    before = path.read_bytes()
    result = runner.invoke(app, ["proposal-check", str(path), *(["--json"] if as_json else [])])
    assert result.exit_code == 0 and result.stderr == ""
    assert result.stdout.isascii()
    payload = result.stdout if as_json else result.stdout[result.stdout.index("{") :]
    report = json.loads(payload)
    assert report == workflow.check_proposal(bundle)
    assert report["results"][0]["status"] == outcome
    assert report["summary"][outcome] == 1
    assert report["authorization_verdict"] == "unknown"
    assert report["verification_status"] == report["runtime_verification_status"] == "not-run"
    assert report["applied"] is False and report["live_provider_calls"] == 0
    if not as_json:
        assert "not approval" in result.stdout and "Not applied" in result.stdout
    assert path.read_bytes() == before


@posix_only
def test_reads_one_selected_bundle_without_embedded_path_or_repository_access(
    tmp_path, monkeypatch
):
    bundle = bundle_for(path="private/never-read.py")
    path = tmp_path / "selected.json"
    path.write_text(bundle.payload_json)
    expected = workflow.check_proposal(bundle)
    opened = []
    real_open = os.open

    def selected_open(selected, flags, *args, **kwargs):
        assert Path(selected) == path
        assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
        assert flags & os.O_ACCMODE == os.O_RDONLY
        opened.append(Path(selected))
        return real_open(selected, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Only the selected bundle may be opened; source paths are labels")

    monkeypatch.setattr(os, "open", selected_open)
    for obj, name in [
        (builtins, "open"),
        (Path, "read_text"),
        (Path, "read_bytes"),
        (ScanRunner, "run"),
        (FastAPIRouteParser, "parse_file"),
        (FastAPIRouteParser, "parse_repository"),
    ]:
        monkeypatch.setattr(obj, name, forbidden)
    result = runner.invoke(app, ["proposal-check", str(path), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected and opened == [path]


@posix_only
@pytest.mark.parametrize("as_json", [False, True])
def test_untrusted_declaration_and_limitation_strings_are_ascii_escaped(tmp_path, as_json):
    scopes = ["\x1b[31m", "\u202e", "읽기"]
    after = BASE.replace(
        "def reports():", f"def reports(user=Security(current_user, scopes={scopes!r})):"
    )
    # C0 controls are invalid manifest strings but can occur in parsed source literals.
    bundle = bundle_for(after=after, observation="scope-declarations", expected={"scopes": []})
    path = tmp_path / "bundle.json"
    path.write_text(bundle.payload_json)
    result = runner.invoke(app, ["proposal-check", str(path), *(["--json"] if as_json else [])])
    assert result.exit_code == 0 and result.stdout.isascii()
    assert (
        "\x1b" not in result.stdout
        and "\u202e" not in result.stdout
        and "읽기" not in result.stdout
    )
    assert "\\u001b" in result.stdout and "\\u202e" in result.stdout
    text = result.stdout if as_json else result.stdout[result.stdout.index("{") :]
    report = json.loads(text)
    assert report["results"][0]["status"] == "mismatched"
    assert report["results"][0]["observed"] == {"scopes": sorted(scopes)}


@posix_only
@pytest.mark.parametrize(
    "kind", ["missing", "empty", "invalid-json", "invalid-utf8", "oversize", "directory", "symlink"]
)
def test_invalid_bundle_input_has_only_redacted_usage_error(tmp_path, kind):
    path = tmp_path / "private-input.json"
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        path.symlink_to(tmp_path / "missing-target")
    elif kind != "missing":
        path.write_bytes(
            {
                "empty": b"",
                "invalid-json": b'{"private":"never-display"}',
                "invalid-utf8": b"\xff",
                "oversize": b"x" * (MAX_JSON_BYTES + 1),
            }[kind]
        )
    result = runner.invoke(app, ["proposal-check", str(path), "--json"])
    assert result.exit_code == 2 and result.stdout == "" and result.stderr.isascii()
    payload = json.loads(result.stderr)
    assert payload["status"] == "invalid-input"
    assert "private-input" not in payload["detail"] and "never-display" not in payload["detail"]


def test_unsupported_platform_does_not_inspect_input(monkeypatch):
    monkeypatch.setattr(reader, "preview_file_supported", lambda: False)
    monkeypatch.setattr(
        reader,
        "_read_bundle",
        lambda *a, **kw: pytest.fail("No filesystem on unsupported platform"),
    )
    result = runner.invoke(app, ["proposal-check", "unused.json"])
    assert result.exit_code == 2 and result.stdout == ""
    assert json.loads(result.stderr)["status"] == "invalid-input"


@pytest.mark.parametrize(
    "failure,code,status",
    [(RuntimeError, 1, "comparison-failed"), (KeyboardInterrupt, 130, "cancelled")],
)
def test_internal_error_and_interrupt_have_no_partial_or_untrusted_output(
    monkeypatch, failure, code, status
):
    def fail(*args, **kwargs):
        raise failure("PRIVATE-COMPARISON-EXCEPTION")

    monkeypatch.setattr(workflow, "load_check", fail)
    result = runner.invoke(app, ["proposal-check", "unused.json"])
    assert result.exit_code == code and result.stdout == ""
    assert json.loads(result.stderr)["status"] == status
    assert "PRIVATE-COMPARISON-EXCEPTION" not in result.output
