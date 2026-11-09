"""The preview CLI exposes fixed data without a model or an execution path."""

import json
import socket
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from authzest.cli import app

runner = CliRunner()


def test_generation_preview_help_is_explicitly_offline():
    result = runner.invoke(app, ["generation-preview", "--help"])
    assert result.exit_code == 0
    assert "no Codex call" in result.stdout
    assert "--json" in result.stdout


def test_generation_preview_default_is_complete_readable_input_not_model_output():
    from authzest.codex.generated_repair import (
        build_generated_repair_request,
        generated_repair_prompt,
    )

    request = build_generated_repair_request()
    result = runner.invoke(app, ["generation-preview"])
    assert result.exit_code == 0
    assert "OFFLINE INPUT PREVIEW - NO GENERATION" in result.stdout
    assert "pending maintainer review" in result.stdout
    assert "NOT authentication" in result.stdout
    assert generated_repair_prompt(request) in result.stdout
    assert result.stderr == ""


def test_generation_preview_json_is_one_complete_document_and_deterministic():
    from authzest.codex.generated_repair import (
        build_generated_repair_request,
        generated_repair_output_schema,
        generated_repair_prompt,
    )

    request = build_generated_repair_request()
    first = runner.invoke(app, ["generation-preview", "--json"])
    second = runner.invoke(app, ["generation-preview", "--json"])
    assert first.exit_code == second.exit_code == 0
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == ""
    payload = json.loads(first.stdout)
    assert payload == {
        "kind": "generated-repair-request-preview",
        "status": "preview-only",
        "request_id": request.request_id,
        "request": request.to_dict(),
        "prompt": generated_repair_prompt(request),
        "output_schema": generated_repair_output_schema(request),
        "model_invoked": False,
        "applied": False,
        "execution_status": "not-run",
    }


def test_generation_preview_never_opens_target_files_or_calls_a_provider(monkeypatch):
    # Warm imports, then forbid effects in the actual invocation.
    from authzest.codex.generated_repair import build_generated_repair_request

    build_generated_repair_request()

    def forbidden(*args, **kwargs):
        raise AssertionError("The offline preview must not perform external effects")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for method in ("open", "read_text", "read_bytes", "write_text", "write_bytes", "resolve"):
        monkeypatch.setattr(Path, method, forbidden)
    result = runner.invoke(app, ["generation-preview", "--json"])
    assert result.exit_code == 0, result.exception
    assert json.loads(result.stdout)["execution_status"] == "not-run"


def test_generation_preview_reports_invalid_owned_context_without_raw_source(monkeypatch):
    from authzest.codex import generated_repair
    from authzest.codex.contracts import ContractError

    def invalid():
        raise ContractError("PRIVATE RESPONSE MUST NOT LEAK")

    monkeypatch.setattr(generated_repair, "build_generated_repair_request", invalid)
    result = runner.invoke(app, ["generation-preview", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "validation failed" in result.stderr
    assert "PRIVATE" not in result.stderr


def test_generation_preview_rejects_arbitrary_repository_or_model_inputs():
    for arguments in (["/tmp/target"], ["--model", "unapproved"], ["--execute"]):
        result = runner.invoke(app, ["generation-preview", *arguments])
        assert result.exit_code == 2
