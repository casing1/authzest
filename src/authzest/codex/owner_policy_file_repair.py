"""Pure registered file-repair application data, never writes, execution or consent.

The caller-supplied recommendation is fully revalidated against the current
registration. A wrapper or imported JSON grants no live session or authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ContractError, _object, canonical, decode, identity
from .owner_policy_repair_recommendation import (
    OwnerPolicyRepairRecommendation,
    OwnerPolicyRepairRecommendationRequest,
    prepare_owner_policy_repair_recommendation_preview,
)

FILE_REPAIR_APPLICATION_SCHEMA_VERSION = "1.0"
_APPLICATION_FIELDS = {
    "schema_version",
    "kind",
    "request_id",
    "recommendation_id",
    "request",
    "recommendation",
    "pair_preview",
    "status",
    "provider_calls",
    "execution_status",
    "patch_application",
    "restoration_status",
    "authorization_status",
    "comparison_status",
    "provenance",
}


@dataclass(frozen=True, slots=True)
class OwnerPolicyFileRepairApplication:
    """Detached data; construction alone establishes neither validity nor authority."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def application_id(self) -> str:
        return "owner-file-application-" + identity(self.to_dict())


def prepare_owner_policy_file_repair(
    request: OwnerPolicyRepairRecommendationRequest,
    recommendation: OwnerPolicyRepairRecommendation,
) -> OwnerPolicyFileRepairApplication:
    """Rebuild a registered application preview without any side effect or decision."""
    if (
        type(request) is not OwnerPolicyRepairRecommendationRequest
        or type(recommendation) is not OwnerPolicyRepairRecommendation
    ):
        raise ContractError("Unexpected file repair artifact type", code="validation-shape")
    # This existing preparer revalidates both complete payloads and regenerates
    # any diff from the current registry, not from model explanations or a path.
    preview = prepare_owner_policy_repair_recommendation_preview(recommendation, request).to_dict()
    data = {
        "schema_version": FILE_REPAIR_APPLICATION_SCHEMA_VERSION,
        "kind": "owner-policy-file-repair-application",
        "request_id": preview["request_id"],
        "recommendation_id": preview["recommendation_id"],
        "request": preview["request"],
        "recommendation": preview["recommendation"],
        "pair_preview": preview["pair_preview"],
        "status": preview["recommendation"]["status"],
        "provider_calls": 0,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
        "comparison_status": "not-evaluated",
        "provenance": {"kind": "caller-supplied-data", "authenticated": False},
    }
    raw = canonical(data)
    decode(raw)  # Bound the complete composed output, not only its inputs.
    return OwnerPolicyFileRepairApplication(raw)


def validate_owner_policy_file_repair(raw: str) -> OwnerPolicyFileRepairApplication:
    """Rebuild all data from the current registration; never restore a live session."""
    data = decode(raw)
    _object(data, _APPLICATION_FIELDS)
    request = OwnerPolicyRepairRecommendationRequest(canonical(data["request"]))
    recommendation = OwnerPolicyRepairRecommendation(canonical(data["recommendation"]))
    expected = prepare_owner_policy_file_repair(request, recommendation)
    if canonical(data) != expected.payload_json:
        raise ContractError(
            "Registered file repair application mismatch", code="validation-identity"
        )
    return expected
