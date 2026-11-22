"""Private owner-read coordination with a trusted, explicitly supplied phase dispatcher.

This module has no CLI entry, transport, saved-plan importer or resume operation.
A supplied dispatcher is trusted host code. Detached observations alone do not grant
execution or source-write authority. The operator must exclude concurrent same-user
writers while a private copy is active.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import secrets
from collections.abc import Callable
from importlib.metadata import version
from time import monotonic

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.owner_read_suggestion import (
    validate_owner_read_request,
    validate_owner_read_response,
)
from authzest.runner._owner_read_copy_files import copy_supported, stage_private_copy
from authzest.runner._owner_read_phase_result import (
    MAX_RESULT_BYTES,
    OwnerReadPhaseResult,
    validate_owner_read_phase,
)
from authzest.runner._owner_read_workspace import OwnerReadWorkspace, OwnerReadWorkspaceError
from authzest.runner.owner_read_copy import Inputs, copy_spec
from authzest.runner.owner_read_suggestion import _changes

_STAGES = ("copy", "before", "diff", "apply", "after", "restore")
_SECONDS = 300


class _Stop(Exception):
    def __init__(self, status: str):
        self.status = status


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class OwnerReadFileSession:
    """One current validated proposal and one fresh copy, with six separate decisions.

    ``inputs`` must rebuild the current invocation's request/proposal/diffs. The
    synchronous ``dispatcher`` receives captured bytes, current plan ID and a
    freshness guard. It must perform and clean up two isolated guests and return
    the host validator's result. There is deliberately no production dispatcher
    or public active CLI connection in this implementation increment.
    """

    def __init__(self, *, sharing_id: str, inputs: Inputs, dispatcher: Callable, clock=monotonic):
        if (
            type(sharing_id) is not str
            or not sharing_id.startswith("share-")
            or len(sharing_id) > 128
            or not callable(dispatcher)
            or inspect.iscoroutinefunction(dispatcher)
        ):
            raise ValueError("Expected current sharing identity and synchronous trusted dispatcher")
        self._inputs = inputs
        self._dispatcher = dispatcher
        self._clock = clock
        self._last_time = 0.0
        self._used = False
        self._active_stage = None
        self._workspace = None
        self._snapshot = None
        self._nonce = secrets.token_hex(16)
        self._current = json.loads(canonical(self._read_inputs()))
        self._sharing_id = sharing_id
        self._binding = "owner-read-session-" + identity(
            {"nonce": self._nonce, "sharing_id": sharing_id, "inputs": self._current}
        )
        self._result = {
            "kind": "owner-read-file-session",
            "schema_version": "1.0",
            "session_id": self._binding,
            "status": "not-started",
            "exit_code": 1,
            "verification_basis": "trusted-dispatcher-observations",
            "installed_version": version("authzest"),
            "request_id": self._current["request"]["request_id"],
            "sharing_id": sharing_id,
            "copy": None,
            "stages": {
                stage: {"status": "not-run", "guest_dispatch_started": False} for stage in _STAGES
            },
            "before": None,
            "after": None,
            "patch_application": "not-run",
            "restoration_status": "not-needed",
            "recovery_required": False,
            "descriptor_cleanup_confirmed": None,
            "guest_cleanup_confirmed": None,
            "original_checkout_modified": False,
        }

    def _read_inputs(self):
        request, proposal, diffs = self._inputs()
        request = validate_owner_read_request(request)
        proposal = validate_owner_read_response(canonical(proposal), request)
        if proposal["status"] != "proposed-change" or canonical(
            _changes(request, proposal)
        ) != canonical(diffs):
            raise ContractError("Expected a current validated proposed change and exact diffs")
        return {"request": request.to_dict(), "proposal": proposal, "diffs": diffs}

    def _now(self):
        now = self._clock()
        if type(now) not in (int, float) or not 0 <= now < float("inf") or now < self._last_time:
            raise _Stop("clock-unconfirmed")
        self._last_time = now
        return now

    def _check(self, *, files=True):
        if canonical(self._read_inputs()) != canonical(self._current):
            raise _Stop("inputs-changed")
        if files and self._workspace is not None and self._workspace.snapshot() != self._snapshot:
            raise _Stop("files-changed")

    def _plan(self, stage):
        return {
            "kind": "owner-read-file-stage-plan",
            "schema_version": "1.0",
            "session_id": self._binding,
            "stage": stage,
            "installed_version": self._result["installed_version"],
            "inputs": self._current,
            "files": self._snapshot,
            "prior_stages": self._result["stages"],
            "observations": {stage: self._result[stage] for stage in ("before", "after")},
            "copy_scope": {**copy_spec(), "additional_file": "record.json"},
            "phase_limits": {
                "roles": ["test", "controls"],
                "seconds": 40,
                "cleanup_seconds": 10,
                "combined_output_bytes": 262144,
            },
            "decision_expires_after_seconds": _SECONDS,
        }

    def _decide(self, stage, emit, read):
        self._active_stage = stage
        self._check()
        payload = self._plan(stage)
        # The JSON round trip detaches prior stages before this stage is recorded.
        payload = json.loads(canonical(payload))
        plan_id = "owner-read-stage-" + identity(payload)
        start = self._now()
        deadline = start + _SECONDS
        if not start < deadline or deadline - start > _SECONDS:
            raise _Stop("clock-unconfirmed")
        emit(json.dumps({**payload, "plan_id": plan_id}, ensure_ascii=True, indent=2))
        record = self._result["stages"][stage]
        record.update(status="awaiting-decision", plan_id=plan_id)
        answer = read(
            f"Type '{stage} {plan_id}' to approve this stage, or press Enter to decline: "
        )
        if answer != f"{stage} {plan_id}":
            record["status"] = "cancelled" if answer == "cancel" else "declined"
            raise _Stop(record["status"])

        def guard():
            self._check(files=stage not in ("apply", "restore"))
            if self._now() >= deadline:
                record["status"] = "expired"
                raise _Stop("expired")

        guard()
        record["status"] = "approved"
        return plan_id, guard

    def _event(self, stage, details):
        self._workspace.record_event(stage, details)
        self._snapshot = self._workspace.snapshot()

    def _phase(self, phase, plan_id, guard):
        source = self._workspace.read_source().data
        test = self._workspace.read_test().data
        capture = {
            "phase": phase,
            "plan_id": plan_id,
            "source": source,
            "test": test,
            "source_sha256": _sha(source),
            "test_sha256": _sha(test),
        }
        self._event(phase, {"status": "dispatch-intent", "plan_id": plan_id})
        guard()
        self._result["stages"][phase].update(status="dispatched", guest_dispatch_started=True)
        previous_recovery = self._result["recovery_required"]
        self._result.update(guest_cleanup_confirmed=None, recovery_required=True)
        # An exception gives no evidence that the isolated guests were removed.
        observed = self._dispatcher(dict(capture), guard=guard)
        if (
            type(observed) is not OwnerReadPhaseResult
            or type(observed.payload_json) is not str
            or len(observed.payload_json.encode("utf-8")) > MAX_RESULT_BYTES
        ):
            raise _Stop("invalid-phase-result")
        value = observed.to_dict()
        for name in ("phase", "plan_id", "source_sha256", "test_sha256"):
            if value.get(name) != capture[name]:
                raise _Stop("phase-identity-mismatch")
        try:
            retained = value["captures"]
            captures = {
                role: {
                    "exit_code": row["exit_code"],
                    "stdout": base64.b64decode(row["stdout_base64"], validate=True),
                    "stderr": base64.b64decode(row["stderr_base64"], validate=True),
                    "cleanup_confirmed": row["cleanup_confirmed"],
                }
                for role, row in retained.items()
            }
            checked = validate_owner_read_phase(
                phase=phase,
                plan_id=plan_id,
                source_sha256=capture["source_sha256"],
                test_sha256=capture["test_sha256"],
                captures=captures,
            ).to_dict()
            if canonical(value) != canonical(checked):
                raise _Stop("invalid-phase-result")
        except (KeyError, TypeError, ValueError, AttributeError):
            raise _Stop("invalid-phase-result") from None
        self._result[phase] = value
        self._result["guest_cleanup_confirmed"] = value["cleanup_confirmed"]
        if value["cleanup_confirmed"] is True:
            self._result["recovery_required"] = previous_recovery
        self._check()
        self._event(
            phase,
            {"status": value["status"], "plan_id": plan_id, "evidence_sha256": identity(value)},
        )
        guard()
        self._result["stages"][phase]["status"] = value["status"]
        if value["status"] != "matched":
            raise _Stop(phase + "-" + value["status"])

    def _restore(self, emit, read):
        plan_id, guard = self._decide("restore", emit, read)
        self._result["stages"]["restore"]["status"] = "dispatched"
        self._workspace.restore_source(self._workspace.read_source(), guard=guard)
        self._snapshot = self._workspace.snapshot()
        self._result.update(restoration_status="restored", recovery_required=False)
        self._result["stages"]["restore"].update(status="restored", plan_id=plan_id)

    def _workspace_failure(self, exc):
        result = self._result
        result["workspace_failure"] = {
            "path": str(exc.path) if exc.path is not None else None,
            "state": exc.state,
            "stage": exc.stage,
            "source_replace_attempted": exc.source_replace_attempted,
            "source_replaced": exc.source_replaced,
        }
        if exc.descriptor_cleanup_confirmed is not None:
            result["descriptor_cleanup_confirmed"] = exc.descriptor_cleanup_confirmed
        if exc.recovery_required:
            result["recovery_required"] = True

    def run(self, *, emit=print, read=input):
        if self._used:
            raise ValueError("An owner-read file session cannot run twice")
        self._used = True
        result = self._result
        try:
            if not copy_supported():
                raise _Stop("unsupported")
            _, guard = self._decide("copy", emit, read)
            proposal = self._current["proposal"]
            baseline = self._current["request"]["source"]["text"].encode("ascii")
            copied = stage_private_copy(
                baseline,
                proposal["test"].encode("ascii"),
                proposal["source"].encode("ascii"),
                guard=guard,
            )
            result["copy"] = copied
            result["stages"]["copy"]["status"] = copied["status"]
            if copied["status"] != "prepared":
                raise _Stop("copy-incomplete")
            self._workspace = OwnerReadWorkspace(
                copied,
                baseline,
                proposal["test"].encode("ascii"),
                proposal["source"].encode("ascii"),
                binding_id=self._binding,
            )
            self._snapshot = self._workspace.snapshot()
            plan_id, guard = self._decide("before", emit, read)
            self._phase("before", plan_id, guard)
            plan_id, guard = self._decide("diff", emit, read)
            guard()
            self._event(
                "diff",
                {
                    "status": "accepted",
                    "plan_id": plan_id,
                    "diffs_sha256": identity(self._current["diffs"]),
                },
            )
            guard()
            result["stages"]["diff"]["status"] = "accepted"
            _, guard = self._decide("apply", emit, read)
            # A failed write may have committed. Keep recovery unresolved until byte readback.
            result.update(
                patch_application="unconfirmed",
                restoration_status="required",
                recovery_required=True,
            )
            result["stages"]["apply"]["status"] = "dispatched"
            self._workspace.apply_source(self._workspace.read_source(), guard=guard)
            self._snapshot = self._workspace.snapshot()
            result["patch_application"] = "applied-to-copy"
            result["stages"]["apply"]["status"] = "applied"
            try:
                plan_id, guard = self._decide("after", emit, read)
                self._phase("after", plan_id, guard)
            except _Stop as exc:
                result["status"] = exc.status
                after = result["after"]
                no_dispatch = not result["stages"]["after"]["guest_dispatch_started"]
                if (after is not None and after["cleanup_confirmed"] is True) or no_dispatch:
                    self._restore(emit, read)
                raise
            self._restore(emit, read)
            result.update(status="completed", exit_code=0)
        except _Stop as exc:
            result["status"] = exc.status
            result["exit_code"] = 130 if exc.status == "cancelled" else 1
            if exc.status == "declined" and result["patch_application"] == "not-run":
                result["exit_code"] = 0
        except (EOFError, KeyboardInterrupt) as exc:
            result.update(status="cancelled", exit_code=130)
            failure = getattr(exc, "owner_read_workspace_error", None)
            if type(failure) is OwnerReadWorkspaceError:
                self._workspace_failure(failure)
        except OwnerReadWorkspaceError as exc:
            result.update(status="state-unconfirmed", exit_code=1)
            self._workspace_failure(exc)
        except (ContractError, OSError, ValueError):
            result.update(status="state-unconfirmed", exit_code=1)
        except Exception:
            result.update(status="dispatcher-failed", exit_code=1)
        finally:
            if self._active_stage is not None:
                stage_record = result["stages"][self._active_stage]
                if stage_record["status"] in ("awaiting-decision", "approved", "dispatched"):
                    stage_record.update(status="unconfirmed", reason=result["status"])
            if self._workspace is not None:
                try:
                    self._snapshot = self._workspace.snapshot()
                except OwnerReadWorkspaceError:
                    result["recovery_required"] = True
                    if result["status"] == "completed":
                        result.update(status="state-unconfirmed", exit_code=1)
                result["last_verified_workspace"] = self._snapshot
                result["workspace_state"] = self._workspace.state
                try:
                    self._workspace.close()
                    result["descriptor_cleanup_confirmed"] = True
                except OSError:
                    result.update(
                        status="descriptor-cleanup-unconfirmed",
                        descriptor_cleanup_confirmed=False,
                        recovery_required=True,
                        exit_code=1,
                    )
        return json.loads(canonical(result))
