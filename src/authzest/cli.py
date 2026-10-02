from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

import typer

from authzest import __version__
from authzest.cli_output import WorkflowOutput, format_record, section
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
    typer.echo(
        "Dependency evidence: inherited and route-local declarations, not access-control guarantees"
    )
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
        for dependency in serialized["effective_dependencies"]:
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
    """Check local scan readiness and optional Codex diagnostics."""
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


@app.command("codex-fixture")
def codex_fixture(
    model: Annotated[
        str, typer.Option(help="Exact Codex model identifier; no automatic fallback.")
    ],
    timeout_seconds: Annotated[
        float,
        typer.Option(help="One adapter attempt timeout, greater than 0 and up to 120 seconds."),
    ] = 120,
    runtime_check: Annotated[
        bool,
        typer.Option(
            "--runtime-check",
            help="Select the fixed owned-fixture runtime plan; "
            "separate verification approval required.",
        ),
    ] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="One final JSON on stdout; interaction on stderr.")
    ] = False,
) -> None:
    """Separately approve Codex review, fixture-copy edits, fixed checks and restore."""
    from authzest.runner._fixture_workspace import WorkspaceInitializationError
    from authzest.runner.codex_fixture import FixtureInputError, run_codex_fixture

    recovery: dict[str, object] = {}
    output = WorkflowOutput(as_json)

    async def run_with_recovery() -> dict:
        try:
            return await run_codex_fixture(
                model,
                timeout_seconds=timeout_seconds,
                runtime_check=runtime_check,
                emit=output.emit,
                read=output.read,
            )
        except (asyncio.CancelledError, KeyboardInterrupt) as exc:
            # Capture metadata inside the coroutine: asyncio.run may translate task
            # cancellation into a fresh KeyboardInterrupt, losing exception attributes.
            failure = getattr(exc, "workspace_initialization", None)
            if isinstance(failure, WorkspaceInitializationError):
                recovery.update(
                    workspace=str(failure.created_path),
                    initialization_stage=failure.initialization_stage,
                    runtime_verification_status="not-run",
                    detail="Initialization interrupted; inspect the retained workspace. "
                    "Its record may be absent or incomplete; no automatic cleanup was performed.",
                )
            else:
                workspace = getattr(exc, "fixture_workspace", None)
                if isinstance(workspace, Path):
                    recovery["workspace"] = str(workspace)
            raise

    try:
        result = asyncio.run(run_with_recovery())
    except FixtureInputError as exc:
        output.finish({"status": "invalid-input", "detail": str(exc)}, error=True)
        raise typer.Exit(code=2) from exc
    except (asyncio.CancelledError, KeyboardInterrupt):
        output.finish(
            {
                "status": "cancelled",
                "exit_code": 130,
                **({} if runtime_check else {"runtime_verification_status": "not-run"}),
                "detail": "Interrupted; inspect the retained workspace record if created.",
                **recovery,
            }
        )
        raise typer.Exit(code=130) from None
    except Exception:
        output.finish(
            {
                "status": "workflow-failed",
                **({} if runtime_check else {"runtime_verification_status": "not-run"}),
                "detail": "Inspect the retained workspace record if created.",
            }
        )
        raise typer.Exit(code=1) from None
    output.finish(result)
    raise typer.Exit(code=result["exit_code"])


@app.command("codex-owner-review")
def codex_owner_review(
    model: Annotated[
        str, typer.Option(help="Exact Codex model identifier; no automatic fallback.")
    ],
    timeout_seconds: Annotated[
        float,
        typer.Option(help="One adapter attempt timeout in seconds, greater than 0 up to 120."),
    ] = 120,
    preview_only: Annotated[
        bool,
        typer.Option(
            "--preview-only", help="Print the complete input preview offline; no account use."
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="One final/preview JSON on stdout; interaction on stderr."),
    ] = False,
) -> None:
    """Review the packaged owner policy; no patches or generated test execution."""
    from authzest.codex.diagnostics import sanitize_failure
    from authzest.runner.codex_owner_review import (
        OwnerReviewInputError,
        build_owner_review_preview,
        run_codex_owner_review,
    )

    output = WorkflowOutput(as_json)
    try:
        result = (
            build_owner_review_preview(model, timeout_seconds=timeout_seconds)
            if preview_only
            else asyncio.run(
                run_codex_owner_review(
                    model, timeout_seconds=timeout_seconds, emit=output.emit, read=output.read
                )
            )
        )
    except OwnerReviewInputError as exc:
        output.finish({"status": "invalid-input", "detail": str(exc)}, error=True)
        raise typer.Exit(code=2) from exc
    except (asyncio.CancelledError, KeyboardInterrupt):
        output.finish(
            {
                "status": "cancelled",
                "execution_status": "not-run",
                "failure": sanitize_failure(None, code="cancelled"),
            }
        )
        raise typer.Exit(code=130) from None
    except Exception:
        output.finish(
            {
                "status": "review-failed",
                "execution_status": "not-run",
                "failure": sanitize_failure(None),
            }
        )
        raise typer.Exit(code=1) from None
    output.finish(result, preview=preview_only)
    raise typer.Exit(code=result.get("exit_code", 0))


@app.command("fixture-demo")
def fixture_demo(
    as_json: Annotated[
        bool, typer.Option("--json", help="One final JSON on stdout; interaction on stderr.")
    ] = False,
) -> None:
    """Try an offline mock proposal with separate copy-edit, source-check and restore choices."""
    from authzest.runner.fixture_demo import run_fixture_demo

    output = WorkflowOutput(as_json)
    try:
        result = asyncio.run(run_fixture_demo(emit=output.emit, read=output.read))
    except (asyncio.CancelledError, KeyboardInterrupt):
        result = {
            "status": "cancelled",
            "exit_code": 130,
            "draft_provenance": "caller-authored-mock",
            "live_provider_calls": 0,
            "runtime_verification_status": "not-run",
            "detail": "Interrupted; inspect the retained workspace record if created.",
        }
    except Exception:
        result = {
            "status": "workflow-failed",
            "exit_code": 1,
            "draft_provenance": "caller-authored-mock",
            "live_provider_calls": 0,
            "runtime_verification_status": "not-run",
            "detail": "Inspect the retained workspace record if created.",
        }
    output.finish(result)
    raise typer.Exit(code=result["exit_code"])


def _format_proposal_preview(view: dict) -> str:
    lines = [
        "Offline proposal preview - draft / not-run / authorization unknown",
        "Not applied. Supplied snapshots only; not approval or verification.",
        section("Bundle", view["bundle_id"]),
    ]
    for title, key in (("Request", "request"), ("Review", "review"), ("Evidence", "evidence")):
        lines.extend(("", section(title, view[key])))
    proposal = view["proposal"]
    lines.extend(("", section("Proposal", {k: v for k, v in proposal.items() if k != "changes"})))
    for change in proposal["changes"]:
        lines.append(section("Change", change))
    lines.extend(("", section("Expectations", view["expectations"])))
    lines.extend(("", section("Limitations", view["limitations"])))
    return "\n".join(lines)


@app.command("proposal-preview")
def proposal_preview_command(
    path: Annotated[
        Path, typer.Argument(help="Offline JSON bundle; no embedded paths are opened.")
    ],
    as_json: bool = typer.Option(False, "--json", help="Print an ASCII-escaped JSON preview."),
) -> None:
    """Review stored evidence, exact diff and expected outcomes without applying or executing."""
    from authzest.runner.proposal_preview import PreviewInputError, load_preview

    try:
        view = load_preview(path)
        output = (
            json.dumps(view, ensure_ascii=True, indent=2, allow_nan=False)
            if as_json
            else _format_proposal_preview(view)
        )
    except PreviewInputError as exc:
        WorkflowOutput(as_json).finish({"status": "invalid-input", "detail": str(exc)}, error=True)
        raise typer.Exit(code=2) from None
    except KeyboardInterrupt:
        WorkflowOutput(as_json).finish({"status": "cancelled"}, error=True)
        raise typer.Exit(code=130) from None
    typer.echo(output)


@app.command("proposal-check")
def proposal_check_command(
    path: Annotated[
        Path, typer.Argument(help="Offline JSON bundle; no embedded paths are opened.")
    ],
    as_json: bool = typer.Option(False, "--json", help="Print ASCII-escaped comparison JSON."),
) -> None:
    """Compare source declaration targets offline; not runtime or authorization verification."""
    from authzest.runner.proposal_check import load_check
    from authzest.runner.proposal_preview import PreviewInputError

    try:
        result = load_check(path)
        # Quote every untrusted value, including human-readable output.
        payload = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False)
        output = (
            payload
            if as_json
            else (
                "Offline source declaration comparison - authorization unknown / runtime not-run\n"
                "Completed processing is not approval or a security pass. Not applied.\n"
                + format_record(result, title="Source declaration comparison")
            )
        )
    except PreviewInputError as exc:
        WorkflowOutput(as_json).finish({"status": "invalid-input", "detail": str(exc)}, error=True)
        raise typer.Exit(code=2) from None
    except KeyboardInterrupt:
        WorkflowOutput(as_json).finish({"status": "cancelled"}, error=True)
        raise typer.Exit(code=130) from None
    except Exception:
        WorkflowOutput(as_json).finish(
            {"status": "comparison-failed", "detail": "Offline comparison failed."}, error=True
        )
        raise typer.Exit(code=1) from None
    typer.echo(output)


def _format_review_demo(view: dict) -> str:
    return "\n\n".join(
        [
            "Offline integrated review demo - caller-authored mock; no live model",
            "Read-only. Declaration matches are not authorization or runtime verification.",
            section("Demo provenance", view["demo"]),
            _format_proposal_preview(view["preview"]),
            section("Source declaration comparison", view["comparison"]),
            section(
                "Defensive regression-test draft (prose only; not executable; not run)",
                view["regression_test_draft"],
            ),
            section("Review limitations", view["limitations"]),
        ]
    )


@app.command("review-demo")
def review_demo_command(
    as_json: bool = typer.Option(False, "--json", help="Print the ASCII-escaped review as JSON."),
) -> None:
    """Review one packaged mock diff, declaration comparison and unexecuted prose test draft."""
    from authzest.runner.review_demo import run_review_demo

    try:
        view = run_review_demo()
        output = (
            json.dumps(view, ensure_ascii=True, indent=2, allow_nan=False)
            if as_json
            else _format_review_demo(view)
        )
    except KeyboardInterrupt:
        WorkflowOutput(as_json).finish({"status": "cancelled"}, error=True)
        raise typer.Exit(code=130) from None
    except Exception:
        WorkflowOutput(as_json).finish(
            {"status": "review-failed", "detail": "Offline review composition failed."}, error=True
        )
        raise typer.Exit(code=1) from None
    typer.echo(output)


@app.command("_configuration-worker", hidden=True)
def _configuration_worker() -> None:
    """Internal fixed checker entry point for the packaged executable."""
    from authzest.runner._configuration_worker import worker_main

    raise typer.Exit(code=worker_main())


@app.command("_runtime-worker", hidden=True)
def _runtime_worker() -> None:
    """Internal fixed owned-fixture worker for the packaged executable."""
    from authzest.runner._runtime_worker import worker_main

    raise typer.Exit(code=worker_main())


@app.command("_runtime-smoke", hidden=True)
def _runtime_smoke() -> None:
    """Internal fixed-fixture packaging check; no target paths or generated commands."""
    from authzest.runner.runtime_smoke import run_runtime_smoke

    try:
        result = asyncio.run(run_runtime_smoke())
    except KeyboardInterrupt:
        result = {"status": "cancelled", "exit_code": 130}
    except Exception:
        result = {"status": "runtime-smoke-failed", "exit_code": 1}
    typer.echo(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    raise typer.Exit(code=result["exit_code"])


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
