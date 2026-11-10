"""Inert generated-repair verification planning and disabled executor preparation.

This first slice has no live session, file capture, approval, process or execute API.
Image and file identities remain unbound. Even valid previews and fake readiness
records are data, never authority or observations of a PoC, repair or restoration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from authzest.codex.contracts import ContractError, _object, canonical, decode, identity
from authzest.codex.generated_repair import (
    GeneratedRepairProposal,
    GeneratedRepairRequest,
    build_generated_repair_request,
    prepare_generated_repair_preview,
    validate_generated_repair_proposal,
    validate_generated_repair_request,
)
from authzest.runner.generated_repair_controls import build_generated_repair_controls

SCHEMA_VERSION = "1.0"
_STAGES = ("copy", "before", "source-diff", "source-apply", "after", "restore")


@dataclass(frozen=True, slots=True)
class GeneratedRepairVerificationPreview:
    """A current-content snapshot, not a captured-file plan or live approval."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def verification_preview_id(self) -> str:
        return "generated-repair-verification-preview-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class GeneratedRepairExecutorReadiness:
    """Preparation-only data; this version can represent no ready/executed state."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


class GeneratedRepairVerificationExecutor(Protocol):
    """Trusted caller seam for preparation only; deliberately no execute method.

    An injected Python implementation already has the caller's ambient authority.
    This interface and its return validation are not an isolation boundary.
    """

    def prepare(
        self, preview: GeneratedRepairVerificationPreview
    ) -> GeneratedRepairExecutorReadiness: ...


def _snapshot(data: dict, kind):
    raw = canonical(data)
    decode(raw)  # Enforce whole-document byte, node and depth budgets as well.
    return kind(raw)


def _recipe() -> dict:
    """Proposed constraints only, with no runnable command or runtime identity."""
    return {
        "recipe_version": "generated-repair-isolation-draft-v1",
        "status": "proposed-not-enforced",
        "platform_scope": "posix-non-frozen-local-linux-engine",
        "image_ids": None,
        "engine_identity": None,
        "launcher_sha256": None,
        "relay_sha256": None,
        "roles": {
            "T": {"purpose": "generated-test", "network": "none", "source": True, "test": True},
            "A": {"purpose": "application", "network": "none", "source": True, "test": False},
            "B": {
                "purpose": "maintained-http-relay",
                "network": "exact-A-network-namespace-only",
                "source": False,
                "test": False,
            },
        },
        "schedule": "T-then-fresh-A-and-B-per-phase",
        "oracle": "host-maintained-expectations-and-verdicts",
        "generated_reports": "untrusted-auxiliary-not-proof",
        "requires": [
            "reviewed-local-engine-and-pinned-preprovisioned-images",
            "pull-never-no-build-or-install",
            "non-root-read-only-cap-drop-all-no-new-privileges",
            "default-seccomp-private-pid-and-ipc",
            "verified-cpu-memory-swap-and-pid-enforcement",
            "exact-read-only-staged-input-mounts-only",
            "no-host-ports-external-network-or-host-gateway",
            "no-home-credentials-checkout-record-or-socket-mounts",
            "no-inherited-host-environment",
            "disable-healthchecks-reject-anonymous-volumes",
            "attach-before-start-no-daemon-output-logging",
            "persist-owned-name-and-nonce-before-create",
            "exact-owned-id-cleanup-confirmed",
        ],
        "limits": {
            "decision_seconds": 300,
            "shared_phase_seconds": 40,
            "phase_clock_origin": "first-setup-or-create-dispatch-through-capture",
            "cumulative_readiness_seconds_within_phase": 10,
            "extra_cleanup_seconds": 10,
            "phase_output_bytes": 262_144,
            "retained_session_bytes": 2_097_152,
            "T_and_A": {"cpu": 1, "memory_mib": 512, "swap_mib": 512, "pids": 64},
            "B": {"cpu": 0.5, "memory_mib": 128, "swap_mib": 128, "pids": 32},
            "T_and_A_tmpfs_mib": 32,
            "B_tmpfs_mib": 8,
            "per_role_shared_memory_mib": 8,
            "application_retries": 0,
        },
        "budgets_measured": False,
        "universal_wall_clock_guarantee": False,
        "escape_proof_sandbox": False,
        "host_execution_fallback": False,
    }


def _context(request, proposal):
    if type(request) is not GeneratedRepairRequest or type(proposal) is not GeneratedRepairProposal:
        raise ContractError("Unexpected verification artifact type", code="validation-shape")
    checked_request = validate_generated_repair_request(getattr(request, "payload_json", None))
    checked_proposal = validate_generated_repair_proposal(
        getattr(proposal, "payload_json", None), checked_request
    )
    return checked_request, checked_proposal


def build_generated_repair_verification_preview(
    request: GeneratedRepairRequest, proposal: GeneratedRepairProposal
) -> GeneratedRepairVerificationPreview:
    """Rebuild an offline preview; do not inspect files or prepare an executable plan."""
    request, proposal = _context(request, proposal)
    controls = build_generated_repair_controls()
    proposed = proposal.to_dict()["status"] == "proposed-change"
    return _snapshot(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "generated-repair-verification-preview",
            "request_id": request.request_id,
            "proposal_id": proposal.proposal_id,
            "scenario_id": request.to_dict()["scenario"]["scenario_id"],
            "proposal_status": proposal.to_dict()["status"],
            "proposal_preview": prepare_generated_repair_preview(proposal, request).to_dict(),
            "controls_id": controls.controls_id,
            "controls": controls.to_dict(),
            "recipe": _recipe(),
            "planning_status": "offline-only",
            "execution_boundary": "unimplemented",
            "stages": list(_STAGES) if proposed else [],
            "copy": {
                "status": "planned-only" if proposed else "not-planned",
                "workspace_identity": None,
                "file_snapshots": None,
                "test_absence_observed": False,
                "baseline": "before-source-plus-generated-test" if proposed else None,
                "copy_materializes_test": proposed,
                "later_apply_scope": "source-replacement-only" if proposed else None,
                "restore_target": "copy-created-before-app-and-unchanged-test"
                if proposed
                else None,
                "test_retained_on_restore": proposed,
                "original_checkout_is_target": False,
                "atomic_two_file_transaction": False,
            },
            "design_review": "maintainer-accepted-offline-design",
            "runtime_approval": "not-granted",
            "approval": "not-requested",
            "execution_authorized": False,
            "execution_status": "not-run",
            "test_materialization": "not-run",
            "source_application": "not-run",
            "restoration_status": "not-run",
            "authorization_status": "unknown",
            "provider_calls_made_by_this_function": 0,
            "provenance": "caller-supplied-unverified",
            "verified_fix": False,
        },
        GeneratedRepairVerificationPreview,
    )


def validate_generated_repair_verification_preview(
    raw: str, request: GeneratedRepairRequest, proposal: GeneratedRepairProposal
) -> GeneratedRepairVerificationPreview:
    """Validate current content only; imported data cannot restore a live session."""
    data = decode(raw)
    expected = build_generated_repair_verification_preview(request, proposal)
    if canonical(data) != expected.payload_json:
        raise ContractError("Verification preview mismatch", code="validation-identity")
    return expected


def _checked_preview(preview):
    if type(preview) is not GeneratedRepairVerificationPreview:
        raise ContractError("Unexpected verification preview type", code="validation-shape")
    data = decode(getattr(preview, "payload_json", None))
    # Derive the current request independently; preview-carried identities grant no trust.
    request = build_generated_repair_request()
    proposal_preview = data.get("proposal_preview")
    if type(proposal_preview) is not dict:
        raise ContractError("Missing verification proposal", code="validation-shape")
    proposal = validate_generated_repair_proposal(
        canonical(proposal_preview.get("proposal")), request
    )
    return validate_generated_repair_verification_preview(preview.payload_json, request, proposal)


def _readiness(preview, reason):
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "generated-repair-executor-readiness",
        "verification_preview_id": preview.verification_preview_id,
        "status": "not-ready",
        "reason": reason,
        "runtime_invoked": False,
        "filesystem_observed": False,
        "execution_status": "not-run",
        "test_materialization": "not-run",
        "source_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
        "execution_authorized": False,
        "provider_calls_made_by_this_function": 0,
        "verified_fix": False,
    }


def validate_generated_repair_executor_readiness(
    raw: str, preview: GeneratedRepairVerificationPreview
) -> GeneratedRepairExecutorReadiness:
    """There is deliberately no ready/executed/approved result in this schema."""
    checked = _checked_preview(preview)
    data = decode(raw)
    expected = _readiness(checked, "runtime-not-implemented")
    _object(data, set(expected))
    reason = data["reason"]
    if type(reason) is not str or reason not in {"runtime-not-implemented", "unsupported-runtime"}:
        raise ContractError("Invalid executor readiness reason", code="validation-shape")
    expected["reason"] = reason
    if canonical(data) != canonical(expected):
        raise ContractError("Invalid executor readiness state", code="validation-identity")
    return _snapshot(expected, GeneratedRepairExecutorReadiness)


class DisabledGeneratedRepairExecutor:
    """The production default does not probe Docker, files, processes or accounts."""

    def prepare(
        self, preview: GeneratedRepairVerificationPreview
    ) -> GeneratedRepairExecutorReadiness:
        checked = _checked_preview(preview)
        return _snapshot(
            _readiness(checked, "runtime-not-implemented"), GeneratedRepairExecutorReadiness
        )


def prepare_generated_repair_executor(
    preview: GeneratedRepairVerificationPreview,
    executor: GeneratedRepairVerificationExecutor | None = None,
) -> GeneratedRepairExecutorReadiness:
    """Call a trusted preparation seam and validate its strictly non-executing result.

    Supplying Python code here is not sandboxing that code. Untrusted artifacts
    cannot select the implementation; this is not exposed as a CLI/plugin option.
    """
    checked = _checked_preview(preview)
    adapter = DisabledGeneratedRepairExecutor() if executor is None else executor
    prepare = getattr(adapter, "prepare", None)
    if not callable(prepare):
        raise ContractError("Invalid preparation interface", code="validation-shape")
    result = prepare(checked)
    if type(result) is not GeneratedRepairExecutorReadiness:
        raise ContractError("Invalid preparation result type", code="validation-shape")
    return validate_generated_repair_executor_readiness(
        getattr(result, "payload_json", None), checked
    )
