import asyncio
import builtins
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from authzest.api.app import create_app
from authzest.cli import app
from authzest.runner import ScanRunner

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "fastapi_dependencies"
runner = CliRunner()


def scan_api(path: Path) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(scan_root=path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans")

    return asyncio.run(request())


def test_owned_dependency_example_has_source_facts_without_target_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def reject_target_import(name: str, *args: object, **kwargs: object) -> object:
        assert name.split(".")[0] not in {"fastapi", "examples", "main"}
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_target_import)
    payload = ScanRunner().run(EXAMPLE).to_dict()
    assert payload["schema_version"] == "1.1"
    assert payload["analysis_status"] == "bounded"
    assert payload["python_files"] == 1 and payload["route_count"] == 2
    assert payload["diagnostics"] == [] and payload["codex_status"] == "disabled"
    assert payload["routes"][0]["dependencies"] == []
    assert payload["routes"][1]["dependencies"] == [
        {
            "kind": "Depends",
            "target": "trace_request",
            "location": {"file": "main.py", "line": 27, "column": 34},
            "declaration_level": "decorator",
            "parameter": None,
            "resolution": "reference",
            "scopes": None,
            "unresolved_reasons": [],
        },
        {
            "kind": "Depends",
            "target": "pagination",
            "location": {"file": "main.py", "line": 29, "column": 37},
            "declaration_level": "parameter-annotation",
            "parameter": "page",
            "resolution": "reference",
            "scopes": None,
            "unresolved_reasons": [],
        },
        {
            "kind": "Security",
            "target": "example_context",
            "location": {"file": "main.py", "line": 30, "column": 31},
            "declaration_level": "parameter-default",
            "parameter": "context",
            "resolution": "reference",
            "scopes": ["items:read"],
            "unresolved_reasons": [],
        },
    ]


def test_example_report_matches_cli_api_and_text() -> None:
    core = ScanRunner().run(EXAMPLE).to_dict()
    cli = runner.invoke(app, ["scan", str(EXAMPLE), "--json", "--strict"])
    response = scan_api(EXAMPLE)
    assert cli.exit_code == 0 and cli.stderr == ""
    assert response.status_code == 200
    assert core == json.loads(cli.stdout) == response.json()
    text = runner.invoke(app, ["scan", str(EXAMPLE)])
    assert text.exit_code == 0
    assert "route-local declarations, not access-control guarantees" in text.stdout
    assert "Depends: pagination [parameter-annotation parameter=page; reference]" in text.stdout
    assert "Depends: trace_request [decorator; reference]" in text.stdout
    assert (
        "Security: example_context [parameter-default parameter=context; reference]" in text.stdout
    )
    assert 'Declared scopes: ["items:read"]' in text.stdout


@pytest.mark.parametrize("strict", [False, True])
def test_dynamic_scopes_retain_partial_json_and_api_evidence(tmp_path: Path, strict: bool) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI, Security\n"
        "app = FastAPI()\n"
        '@app.get("/items")\n'
        "def items(context=Security(provider, scopes=runtime_scopes)): pass\n",
        encoding="utf-8",
    )
    arguments = ["scan", str(tmp_path), "--json"] + (["--strict"] if strict else [])
    cli = runner.invoke(app, arguments)
    assert cli.exit_code == (1 if strict else 0)
    assert cli.stderr == ""
    payload = json.loads(cli.stdout)
    response = scan_api(tmp_path)
    assert response.status_code == 200 and response.json() == payload
    assert payload["analysis_status"] == "partial"
    assert payload["parse_errors"] == []
    dependency = payload["routes"][0]["dependencies"][0]
    assert dependency["target"] == "provider"
    assert dependency["scopes"] is None
    assert dependency["resolution"] == "unresolved"
    assert dependency["unresolved_reasons"]
    assert any(d["code"] in dependency["unresolved_reasons"] for d in payload["diagnostics"])
    text = runner.invoke(app, ["scan", str(tmp_path), "--strict"])
    assert text.exit_code == 1
    assert "Declared scopes: unknown" in text.stdout
    assert "Unresolved:" in text.stdout
    assert "main.py:4:" in text.stderr


@pytest.mark.parametrize("declaration", ["Depends()", "Depends(first, dependency=second)"])
def test_implicit_and_ambiguous_targets_are_not_printed_as_resolved(
    tmp_path: Path, declaration: str
) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI, Depends\n"
        "app = FastAPI()\n"
        '@app.get("/items")\n'
        f"def items(value={declaration}): pass\n",
        encoding="utf-8",
    )
    text = runner.invoke(app, ["scan", str(tmp_path), "--strict"])
    assert text.exit_code == 1
    assert "Depends: <unresolved> [parameter-default parameter=value; unresolved]" in text.stdout
