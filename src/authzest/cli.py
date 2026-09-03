from __future__ import annotations

import json
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
) -> None:
    """Scan a repository and summarize discovered FastAPI routes."""
    try:
        report = ScanRunner().run(path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return

    typer.echo(f"Repository: {report.root}")
    typer.echo(f"Python files: {report.python_files}")
    typer.echo(f"FastAPI routes: {len(report.routes)}")
    typer.echo(f"Codex analysis: {report.codex_status}")
    for route in report.routes:
        methods = ",".join(route.methods)
        typer.echo(f"  {methods:7} {route.path}  ({route.file.name}:{route.line})")
    if report.parse_errors:
        typer.echo(f"Parse errors: {len(report.parse_errors)}", err=True)


@app.command()
def doctor(
    as_json: bool = typer.Option(False, "--json", help="Print diagnostics as JSON."),
) -> None:
    """Check whether AuthZest and the optional Codex integration are ready."""
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

    typer.echo(f"AuthZest local server: http://{host}:{port}")
    typer.echo(f"API docs: http://{host}:{port}/docs")
    uvicorn.run("authzest.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
