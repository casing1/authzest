"""Offline apply/check/restore walkthrough of the maintained source-configuration fixture."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from authzest.runner.fixture_apply import FixtureApplySession
from scripts.demo_apply import _choice
from scripts.demo_proposal import build_demo_proposal


def _emit(emit, value: dict) -> None:
    emit(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False))


async def run_demo(*, read=input, emit=print, parent: Path | None = None) -> dict:
    """Use a caller-authored mock draft; each copy operation requires its own choice.

    This development-checkout example does not call a provider or execute fixture
    source. Only an approved, fixed configuration checker runs in a child process.
    ``parent`` and injected I/O are test helpers, not command-line path options.
    Files and their audit record are retained; no automatic restoration is implied.
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
        "verification_scope": "source-configuration",
        "runtime_verification_status": "not-run",
    }
    session = None
    try:
        _emit(
            emit,
            {
                **result,
                "kind": "offline-owned-fixture-configuration-preview",
                "limitations": [
                    "The review and defensive draft are caller-authored mock data, not AI output.",
                    "Apply, configuration verification and restore require separate exact choices.",
                    "Only a fresh fixture copy is changed; its files and record are retained.",
                    "The fixed checker reads source as data; no fixture import or execution.",
                    "No regression tests, runtime authorization check or verified security fix.",
                    "A separate process is not an OS/network sandbox "
                    "or human approval attestation.",
                ],
            },
        )
        request, review, proposal = build_demo_proposal()
        session = FixtureApplySession(proposal, request, review, parent=parent)
        result["workspace"] = str(session.workspace)
        _emit(emit, session.preview())
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
                verification = await session.verify()
            except Exception:
                verification = {
                    "status": "failed",
                    "reason": "verification-unavailable",
                    "verification_scope": "source-configuration",
                    "runtime_verification_status": "not-run",
                }
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
            result["detail"] = "Inspect the retained workspace record if created."
    except (asyncio.CancelledError, KeyboardInterrupt):
        result.update(status="cancelled", exit_code=130)
        result.pop("verification_status", None)
        result["detail"] = "Interrupted; inspect the retained workspace record if created."
    except Exception:
        result.update(status="workflow-failed", exit_code=1)
        result.pop("verification_status", None)
        result["detail"] = "Inspect the retained workspace record if created."
    finally:
        if session is not None:
            session.close()
    return result


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        result = asyncio.run(run_demo())
    except (asyncio.CancelledError, KeyboardInterrupt):
        result = {
            "status": "cancelled",
            "exit_code": 130,
            "runtime_verification_status": "not-run",
            "detail": "Interrupted; inspect the retained workspace record if created.",
        }
    except Exception:
        result = {
            "status": "workflow-failed",
            "exit_code": 1,
            "runtime_verification_status": "not-run",
            "detail": "Inspect the retained workspace record if created.",
        }
    _emit(print, result)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
