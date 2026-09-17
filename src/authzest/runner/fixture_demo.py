"""Offline, source-only walkthrough of the packaged owned-configuration fixture."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from authzest.codex.fixture_demo import build_demo_proposal
from authzest.runner._fixture_workspace import WorkspaceInitializationError, supported
from authzest.runner.fixture_apply import FixtureApplySession


def _emit(emit: Callable[[str], None], value: dict) -> None:
    emit(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False))


def _choice(read: Callable[[str], str], action: str, identity: str) -> str:
    try:
        answer = read(f"Type '{action} {identity}' to confirm; Enter declines, 'cancel' cancels: ")
    except (EOFError, KeyboardInterrupt):
        return "cancel"
    if answer == f"{action} {identity}":
        return "approve"
    return "cancel" if answer == "cancel" else "decline"


async def run_fixture_demo(*, read=input, emit=print, parent: Path | None = None) -> dict:
    """Preview a mock draft, then separately decide apply/check/restore on a fresh copy.

    The only worker reads the fixed maintained source as data after an exact verify
    choice. It does not import or execute the fixture. No provider, caller target,
    runtime-plan selector or automatic approval is supported. ``parent`` and injected
    I/O are test helpers, not CLI path options. Files and audit records are retained.
    """
    result = {
        "kind": "offline-owned-fixture-configuration-workflow",
        "status": "not-started",
        "exit_code": 0,
        "draft_provenance": "caller-authored-mock",
        "simulated_draft": True,
        "decisions_authenticated": False,
        "live_provider_calls": 0,
        "workspace": None,
        "application": None,
        "verification": None,
        "restoration": None,
        "original_checkout_modified": False,
        "verification_status": "not-run",
        "runtime_check_requested": False,
        "verification_scope": "source-configuration",
        "runtime_verification_status": "not-run",
    }
    # Guard before even the temporary source inventory is created.
    if not supported():
        result.update(
            status="unsupported-platform",
            exit_code=2,
            detail="Fixture demonstration requires supported POSIX file operations.",
        )
        return result
    session = None
    try:
        _emit(
            emit,
            {
                **result,
                "kind": "offline-owned-fixture-configuration-preview",
                "limitations": [
                    "The review and defensive draft are caller-authored mock data, not AI output.",
                    "Apply, source verification and restore require separate exact choices.",
                    "Only a fresh fixture copy is changed; its files and record are retained.",
                    "The fixed checker reads source as data; no fixture import or execution.",
                    "Proposed check labels and expectations do not execute a regression suite.",
                    "No authorization guarantee, runtime observation or general verified fix.",
                    "A separate process is not an OS/network sandbox "
                    "or human approval attestation.",
                ],
            },
        )
        request, review, proposal = build_demo_proposal()
        session = FixtureApplySession(proposal, request, review, parent=parent, runtime_check=False)
        result["workspace"] = str(session.workspace)
        _emit(
            emit,
            {
                **session.preview(),
                "evidence": request.to_dict()["evidence"],
                "review": review.to_dict(),
                "draft_provenance": "caller-authored-mock",
            },
        )
        session.decide(_choice(read, "apply", proposal.proposal_id))
        application = session.apply()
        result["application"] = asdict(application)
        _emit(emit, result["application"])
        if application.status == "applied":
            try:
                preview = session.verification_preview()
                _emit(emit, preview)
                plan_id = preview["plan_id"]
                session.decide_verification(_choice(read, "verify", plan_id), plan_id)
            except Exception:
                verification = session.fail_verification_setup()
            else:
                # Escaped execution errors are not known pre-execution failures.
                verification = await session.verify()
            result["verification"] = verification
            result["verification_status"] = verification["status"]
            _emit(emit, verification)
            _emit(emit, session.restoration_preview())
            result["restoration"] = asdict(
                session.restore(_choice(read, "restore", proposal.proposal_id))
            )
            _emit(emit, result["restoration"])
        application_ok = application.status in ("applied", "declined", "cancelled")
        if result["restoration"] is not None:
            application_ok = application_ok and result["restoration"]["status"] in (
                "restored",
                "restoration-decline",
                "restoration-cancel",
            )
        verification = result["verification"]
        verification_failed = verification is not None and (
            verification["status"] == "failed"
            or (
                verification["status"] == "not-run"
                and verification["reason"] not in ("declined", "cancelled")
            )
        )
        result["status"] = (
            "application-failed"
            if not application_ok
            else "verification-failed"
            if verification_failed
            else "completed"
        )
        result["exit_code"] = 0 if application_ok and not verification_failed else 1
        if result["exit_code"]:
            result["detail"] = (
                "Verification journal persistence is unconfirmed; "
                "the retained record may be stale. "
                "Inspect the workspace files and command output; this is not a restart receipt."
                if verification is not None and verification.get("journal_status") == "unconfirmed"
                else "Inspect the retained workspace record if created."
            )
    except (asyncio.CancelledError, KeyboardInterrupt) as exc:
        result.update(status="cancelled", exit_code=130)
        result.pop("verification_status", None)
        result["detail"] = "Interrupted; inspect the retained workspace record if created."
        failure = getattr(exc, "workspace_initialization", None)
        if isinstance(failure, WorkspaceInitializationError):
            result.update(
                workspace=str(failure.created_path),
                initialization_stage=failure.initialization_stage,
                detail="Initialization interrupted; inspect the retained workspace. "
                "Its record may be absent or incomplete; no automatic cleanup was performed.",
            )
    except WorkspaceInitializationError as exc:
        result.update(
            status="workflow-failed",
            exit_code=1,
            workspace=str(exc.created_path),
            initialization_stage=exc.initialization_stage,
            detail="Initialization failed; inspect the retained workspace. "
            "Its record may be absent or incomplete; no automatic cleanup was performed.",
        )
        result.pop("verification_status", None)
    except Exception:
        result.update(status="workflow-failed", exit_code=1)
        result.pop("verification_status", None)
        result["detail"] = "Inspect the retained workspace record if created."
    finally:
        if session is not None:
            session.close()
    return result
