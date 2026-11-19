"""One-use review of a new private copy for the synthetic owner-read fixture."""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from typing import Any

from authzest.codex.contracts import ContractError, identity
from authzest.codex.owner_read_suggestion import SOURCE_PATH, TEST_PATH, OwnerReadRequest
from authzest.owner_read_demo.checks import owner_read_controls
from authzest.runner._owner_read_copy_files import FILES, copy_supported, stage_private_copy

__all__ = ["copy_spec", "copy_supported", "prepare_current_copy"]

_DECISION_SECONDS = 300
Inputs = Callable[[], tuple[OwnerReadRequest, dict[str, Any], list[dict[str, Any]]]]


def copy_spec() -> dict[str, Any]:
    return {
        "stage": "copy",
        "parent": "/tmp",
        "files": {
            FILES[0]: {"source": SOURCE_PATH, "contents": "packaged baseline"},
            FILES[1]: {"source": TEST_PATH, "contents": "proposed test"},
            FILES[2]: {"source": SOURCE_PATH, "contents": "proposed replacement (inert text)"},
        },
        "directory_mode": "0700",
        "file_mode": "0600",
        "max_bytes_per_file": 4096,
        "decision_expires_after_seconds": _DECISION_SECONDS,
        "controls": owner_read_controls(),
        "controls_status": "expected-only",
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "retention": "Keep the new directory for inspection, including incomplete copies.",
    }


def _plan(inputs: Inputs, sharing_id: str, nonce: str) -> dict[str, Any]:
    request, proposal, diffs = inputs()
    fields = {
        "kind": "owner-read-copy-plan",
        "schema_version": "1.0",
        "request_id": request.request_id,
        "sharing_id": sharing_id,
        "copy_nonce": nonce,
        "scope": copy_spec(),
        "baseline": request.to_dict()["source"],
        "proposal": proposal,
        "diffs": diffs,
    }
    return {**fields, "plan_id": "owner-read-copy-" + identity(fields)}


def prepare_current_copy(
    *,
    sharing_id: str,
    inputs: Inputs,
    emit: Callable[[str], Any],
    read: Callable[[str], str],
) -> dict[str, Any]:
    """Only the host's current suggestion supplies inputs; there is no saved-plan CLI."""
    outcome = {"status": "inputs-changed", "path": None, "exit_code": 1}
    try:
        nonce = secrets.token_hex(16)
        plan = _plan(inputs, sharing_id, nonce)
        outcome["plan_id"] = plan["plan_id"]
        deadline = time.monotonic() + _DECISION_SECONDS

        def guard():
            if time.monotonic() >= deadline:
                raise TimeoutError

        emit(json.dumps(plan, ensure_ascii=True, indent=2, allow_nan=False))
        expected = "copy " + plan["plan_id"]
        answer = read(f"Type '{expected}' to prepare the private copy, or press Enter to decline: ")
        if answer == "cancel":
            return {**outcome, "status": "cancelled", "exit_code": 130}
        if answer != expected:
            return {**outcome, "status": "declined", "exit_code": 0}
        guard()
        if _plan(inputs, sharing_id, nonce) != plan:
            return outcome
        staged = stage_private_copy(
            plan["baseline"]["text"].encode("ascii"),
            plan["proposal"]["test"].encode("ascii"),
            plan["proposal"]["source"].encode("ascii"),
            guard=guard,
        )
        return {**outcome, **staged}
    except TimeoutError:
        return {**outcome, "status": "expired"}
    except (EOFError, KeyboardInterrupt):
        return {**outcome, "status": "cancelled", "exit_code": 130}
    except (ContractError, OSError):
        return outcome
