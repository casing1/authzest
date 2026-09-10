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

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "fastapi_inheritance"
runner = CliRunner()


def scan_api(path: Path) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(scan_root=path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/scans")

    return asyncio.run(request())


def test_owned_inheritance_example_preserves_context_without_target_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def reject_target_import(name: str, *args: object, **kwargs: object) -> object:
        assert name.split(".")[0] not in {"fastapi", "examples", "main"}
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_target_import)
    payload = ScanRunner().run(EXAMPLE).to_dict()
    assert payload["schema_version"] == "1.2"
    assert payload["analysis_status"] == "bounded"
    assert payload["python_files"] == 1 and payload["route_count"] == 3
    assert payload["diagnostics"] == [] and payload["codex_status"] == "disabled"
    routes = payload["routes"]
    assert len({route["registration_id"] for route in routes}) == 3
    by_include = {
        route["registration"]["include_chain"][0]["location"]["line"]: route for route in routes
    }
    for line, path, application, mount in [
        (40, "/items", "application_context", "primary_mount"),
        (41, "/items", "alternate_context", "secondary_mount"),
        (42, "/copy/items", "application_context", "secondary_mount"),
    ]:
        route = by_include[line]
        assert route["path"] == path
        assert [d["target"] for d in route["dependencies"]] == ["route_context"]
        effective = route["effective_dependencies"]
        assert [d["target"] for d in effective] == [
            application,
            mount,
            "router_context",
            "route_context",
        ]
        assert [d["declaration_level"] for d in effective] == [
            "application",
            "include",
            "router",
            "decorator",
        ]
        assert [d["location"]["line"] for d in effective] == [
            31 if line == 41 else 30,
            line,
            32,
            35,
        ]
        for dependency in effective:
            assert dependency["kind"] == "Depends"
            assert dependency["resolution"] == "reference"
            assert dependency["location"]["file"] == "main.py"
            assert dependency["location"]["column"] > 0
            assert dependency["scopes"] is None and dependency["unresolved_reasons"] == []


def test_inheritance_example_matches_core_cli_api_and_text() -> None:
    core = ScanRunner().run(EXAMPLE).to_dict()
    cli = runner.invoke(app, ["scan", str(EXAMPLE), "--json", "--strict"])
    response = scan_api(EXAMPLE)
    assert cli.exit_code == 0 and cli.stderr == ""
    assert response.status_code == 200
    assert core == json.loads(cli.stdout) == response.json()
    text = runner.invoke(app, ["scan", str(EXAMPLE), "--strict"])
    assert text.exit_code == 0
    assert "inherited and route-local declarations, not access-control guarantees" in text.stdout
    assert text.stdout.count("Depends: application_context [application; reference]") == 2
    assert text.stdout.count("Depends: alternate_context [application; reference]") == 1
    assert text.stdout.count("Depends: primary_mount [include; reference]") == 1
    assert text.stdout.count("Depends: secondary_mount [include; reference]") == 2
    assert text.stdout.count("Depends: router_context [router; reference]") == 3
    assert text.stdout.count("Depends: route_context [decorator; reference]") == 3


@pytest.mark.parametrize("level", ["application", "router", "include"])
@pytest.mark.parametrize("strict", [False, True])
def test_dynamic_inherited_evidence_is_partial_across_transports(
    tmp_path: Path, level: str, strict: bool
) -> None:
    declaration = "dependencies=[Security(context, scopes=runtime_scopes)]"
    (tmp_path / "main.py").write_text(
        "from fastapi import APIRouter, FastAPI, Security\n"
        f"app = FastAPI({declaration if level == 'application' else ''})\n"
        f"router = APIRouter({declaration if level == 'router' else ''})\n"
        '@router.get("/items")\n'
        "def items(): pass\n"
        f"app.include_router(router{', ' + declaration if level == 'include' else ''})\n",
        encoding="utf-8",
    )
    arguments = ["scan", str(tmp_path), "--json"] + (["--strict"] if strict else [])
    cli = runner.invoke(app, arguments)
    assert cli.exit_code == (1 if strict else 0) and cli.stderr == ""
    payload = json.loads(cli.stdout)
    response = scan_api(tmp_path)
    assert response.status_code == 200 and response.json() == payload
    assert payload["analysis_status"] == "partial" and payload["parse_errors"] == []
    route = payload["routes"][0]
    assert route["dependencies"] == []
    assert len(route["effective_dependencies"]) == 1
    evidence = route["effective_dependencies"][0]
    assert evidence["declaration_level"] == level
    assert evidence["target"] == "context" and evidence["scopes"] is None
    assert evidence["resolution"] == "unresolved"
    assert evidence["unresolved_reasons"] == ["dynamic-security-scopes"]
    text = runner.invoke(app, ["scan", str(tmp_path), "--strict"])
    assert text.exit_code == 1
    assert f"Security: context [{level}; unresolved]" in text.stdout
    assert "Declared scopes: unknown" in text.stdout
    assert "dynamic-security-scopes" in text.stderr
