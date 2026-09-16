"""Pure, read-only composition of evidence-linked proposal preview artifacts."""

from dataclasses import dataclass
from typing import Any

from .contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    _object,
    canonical,
    decode,
    identity,
    validate_response,
)
from .expectations import (
    ValidatedExpectationManifest,
    expectation_preview,
    validate_expectation_manifest,
)
from .proposals import ValidatedProposal, proposal_preview, validate_proposal

PREVIEW_SCHEMA_VERSION = "1.0"
_FIELDS = {"schema_version", "request", "review", "proposal", "manifest"}


@dataclass(frozen=True, slots=True)
class ValidatedPreviewBundle:
    """Canonical artifact container; consumers must revalidate even this wrapper."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def bundle_id(self) -> str:
        return "preview-" + identity(self.to_dict())


def _artifacts(
    data: dict[str, Any],
) -> tuple[
    CodexAnalysisRequest,
    ValidatedResponse,
    ValidatedProposal,
    ValidatedExpectationManifest,
]:
    _object(data, _FIELDS)
    if data["schema_version"] != PREVIEW_SCHEMA_VERSION:
        raise ContractError("Unsupported preview bundle schema")
    if any(type(data[field]) is not dict for field in _FIELDS - {"schema_version"}):
        raise ContractError("Preview bundle artifacts must be objects")
    request = CodexAnalysisRequest(canonical(data["request"]))
    review = validate_response(canonical(data["review"]), request)
    proposal = validate_proposal(canonical(data["proposal"]), request, review)
    manifest = validate_expectation_manifest(canonical(data["manifest"]), request, review, proposal)
    return request, review, proposal, manifest


def validate_preview_bundle(raw: str) -> ValidatedPreviewBundle:
    """Revalidate all artifacts within the existing aggregate bounded-JSON budget."""
    data = decode(raw)
    try:
        _artifacts(data)
    except (KeyError, TypeError, OverflowError) as exc:
        # Nested legacy contracts can fail before producing ContractError. Keep
        # malformed bundles inside this boundary without exposing parser locals.
        raise ContractError("Invalid preview artifact structure") from exc
    return ValidatedPreviewBundle(canonical(data))


def prepare_preview_bundle(
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    proposal: ValidatedProposal,
    manifest: ValidatedExpectationManifest,
) -> ValidatedPreviewBundle:
    """Package supplied artifacts; do not read sources, infer approval or execute checks."""
    return validate_preview_bundle(
        canonical(
            {
                "schema_version": PREVIEW_SCHEMA_VERSION,
                "request": request.to_dict(),
                "review": review.to_dict(),
                "proposal": proposal.to_dict(),
                "manifest": manifest.to_dict(),
            }
        )
    )


def preview_bundle(bundle: ValidatedPreviewBundle) -> dict[str, Any]:
    """Return detached display data, not an executable plan or observed result."""
    bundle = validate_preview_bundle(bundle.payload_json)
    request, review, proposal, manifest = _artifacts(bundle.to_dict())
    metadata = request.to_dict()
    evidence = metadata.pop("evidence")
    metadata["request_id"] = request.request_id
    return {
        "schema_version": PREVIEW_SCHEMA_VERSION,
        "bundle_id": bundle.bundle_id,
        "status": "draft",
        "applied": False,
        "verification_status": "not-run",
        "authorization_verdict": "unknown",
        "request": metadata,
        "review": review.to_dict(),
        "proposal": proposal_preview(proposal, request, review),
        "expectations": expectation_preview(manifest, request, review, proposal),
        "evidence": evidence,
        "limitations": [
            "Supplied snapshots are not checked against current filesystem or Git state.",
            "Structural consistency and citations do not establish semantic support.",
            "Policy intent and source declarations do not prove authorization enforcement.",
            "This preview grants no sharing, application, verification or restoration approval.",
            "No provider call, source execution, file change or test run is performed.",
        ],
    }
