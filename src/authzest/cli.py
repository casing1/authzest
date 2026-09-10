from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from authzest import __version__
from authzest.diagnostics import collect_diagnostics
from authzest.runner import ScanRunner

app = typer.Typer(
    name="authzest",
    help="Source-aware authorization security testing for FastAPI projects.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"authzest {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """AuthZest command-line application."""
    del version


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="FastAPI repository to analyze.")],
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit with code 1 for known partial analysis (not a security verdict).",
    ),
) -> None:
    """Scan a repository and summarize discovered FastAPI routes."""
    try:
        report = ScanRunner().run(path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        if strict and report.analysis_status == "partial":
            raise typer.Exit(code=1)
        return

    typer.echo(f"Repository: {report.root}")
    typer.echo(f"Python files: {report.python_files}")
    typer.echo(f"FastAPI routes: {len(report.routes)}")
    typer.echo(f"Codex analysis: {report.codex_status}")
    typer.echo(
        f"Analysis: {report.analysis_status} (supported static subset; not a security verdict)"
    )
    typer.echo("Dependency evidence: route-local declarations, not access-control guarantees")
    for route in report.routes:
        methods = ",".join(route.methods)
        serialized = route.to_dict(report.root)
        source_file = serialized["file"]
        typer.echo(f"  {methods:7} {route.path}  ({source_file}:{route.line})")
        if registration := serialized["registration"]:
            typer.echo(f"    Registration: {serialized['registration_id']}")
            if application := registration["application"]:
                location = application["location"]
                typer.echo(f"    App: {location['file']}:{location['line']}:{location['column']}")
            typer.echo(f"    Scope: {registration['execution_scope']}")
            for site in registration["include_chain"]:
                location = site["location"]
                typer.echo(
                    f"    Include: {location['file']}:{location['line']}:{location['column']}"
                    f" prefix={site['prefix']!r}"
                )
        for dependency in serialized["dependencies"]:
            location = dependency["location"]
            target = dependency["target"] if dependency["target"] is not None else "<unresolved>"
            parameter = f" parameter={dependency['parameter']}" if dependency["parameter"] else ""
            typer.echo(
                f"    {dependency['kind']}: {target}"
                f" [{dependency['declaration_level']}{parameter}; {dependency['resolution']}]"
                f" ({location['file']}:{location['line']}:{location['column']})"
            )
            if dependency["kind"] == "Security":
                scopes = dependency["scopes"]
                typer.echo(
                    f"      Declared scopes: {json.dumps(scopes, ensure_ascii=False)}"
                    if scopes is not None
                    else "      Declared scopes: unknown"
                )
            if dependency["unresolved_reasons"]:
                typer.echo(f"      Unresolved: {', '.join(dependency['unresolved_reasons'])}")
    if report.parse_errors:
        typer.echo(f"Parse errors: {len(report.parse_errors)} (partial source inventory)", err=True)
        for error in report.parse_errors:
            typer.echo(f"  {error}", err=True)
    for diagnostic in report.diagnostics:
        location = diagnostic.location.to_dict(report.root)
        typer.echo(
            f"[{diagnostic.severity}:{diagnostic.code}] "
            f"{location['file']}:{location['line'] or '?'}:{location['column'] or '?'} "
            f"{diagnostic.message}",
            err=True,
        )
    if strict and report.analysis_status == "partial":
        raise typer.Exit(code=1)


@app.command()
def doctor(
    as_json: bool = typer.Option(False, "--json", help="Print diagnostics as JSON."),
) -> None:
    """Check local scan readiness and optional Codex diagnostics; AI analysis is not implemented."""
    report = collect_diagnostics()
    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"AuthZest {report.version}")
        for check in report.checks:
            label = {"ok": "OK", "warning": "WARN", "error": "ERROR"}[check.status]
            typer.echo(f"[{label}] {check.name}: {check.detail}")
            if check.remedy:
                typer.echo(f"       {check.remedy}")
        typer.echo("Ready for local scans." if report.ready else "Setup needs attention.")
    if not report.ready:
        raise typer.Exit(code=1)


@app.command()
def ui(
    host: Annotated[str, typer.Option(help="Address for the local server.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port for the local server.")] = 8000,
    reload: Annotated[bool, typer.Option(help="Reload when Python source changes.")] = False,
    workspace: Annotated[
        Path | None,
        typer.Option(
            help="Directory that the local API is allowed to scan (default: current directory).",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Run the optional local dashboard without deploying a website."""
    try:
        import uvicorn
    except ImportError as exc:
        typer.echo(
            "UI dependencies are not installed. Reinstall AuthZest with the 'ui' extra.",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    resolved_workspace = (workspace or Path.cwd()).expanduser().resolve()
    os.environ["AUTHZEST_SCAN_ROOT"] = str(resolved_workspace)

    typer.echo(f"AuthZest local server: http://{host}:{port}")
    typer.echo(f"API docs: http://{host}:{port}/docs")
    typer.echo(f"Scan workspace: {resolved_workspace}")
    uvicorn.run("authzest.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
