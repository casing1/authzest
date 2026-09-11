"""Interactively apply/restore a fixed defensive draft in a fresh owned-fixture copy."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from authzest.codex.contracts import ContractError
from authzest.runner._fixture_workspace import WorkspaceError
from authzest.runner.fixture_apply import FixtureApplySession
from scripts.demo_proposal import build_demo_proposal


def _choice(read: Callable[[str], str], action: str, proposal_id: str) -> str:
    try:
        answer = read(
            f"Type '{action} {proposal_id}' to confirm; Enter declines, 'cancel' cancels: "
        )
    except (EOFError, KeyboardInterrupt):
        return "cancel"
    if answer == f"{action} {proposal_id}":
        return "approve"
    return "cancel" if answer == "cancel" else "decline"


def run_demo(*, read=input, emit=print, parent: Path | None = None) -> dict:
    request, review, proposal = build_demo_proposal()
    session = FixtureApplySession(proposal, request, review, parent=parent)
    try:
        emit(
            "Owned fixture COPY only. No Codex, source execution, or verified fix. "
            "Files are retained."
        )
        emit(json.dumps(session.preview(), ensure_ascii=True, indent=2))
        session.decide(_choice(read, "apply", proposal.proposal_id))
        applied = session.apply()
        emit(json.dumps(asdict(applied), ensure_ascii=True, indent=2))
        restored = None
        if applied.status == "applied":
            emit(
                "Optional restoration of this copy only; detected later edits cause refusal. "
                "Enter keeps the change."
            )
            emit(json.dumps(session.restoration_preview(), ensure_ascii=True, indent=2))
            restored = session.restore(_choice(read, "restore", proposal.proposal_id))
            emit(json.dumps(asdict(restored), ensure_ascii=True, indent=2))
        return {
            "kind": "offline-owned-fixture-application",
            "workspace": str(session.workspace),
            "application": asdict(applied),
            "restoration": asdict(restored) if restored else None,
            "original_checkout_modified": False,
            "live_provider_calls": 0,
            "verification_status": "not-run",
        }
    finally:
        session.close()


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        result = run_demo()
    except (OSError, WorkspaceError, ContractError) as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__, "detail": str(exc)}))
        return 1
    statuses = {result["application"]["status"]}
    if result["restoration"]:
        statuses.add(result["restoration"]["status"])
    return (
        0
        if statuses
        <= {
            "applied",
            "declined",
            "cancelled",
            "restored",
            "restoration-decline",
            "restoration-cancel",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
