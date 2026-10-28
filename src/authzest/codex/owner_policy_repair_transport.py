"""Bounded transport envelopes for the registered repair-selection contract.

Construction and validation are pure data operations, not sharing consent. The
model-independent recommendation identity remains unchanged; a separate transport
identity binds its exact input, model configuration, prompt and output schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .contracts import (
    AdapterConfig,
    ContractError,
    _integer,
    _object,
    canonical,
    decode,
    identity,
)
from .fixture_draft import HOST_INSTRUCTIONS
from .owner_policy_repair_recommendation import (
    REPAIR_RECOMMENDATION_PROMPT_VERSION,
    REPAIR_RECOMMENDATION_SCHEMA_VERSION,
    OwnerPolicyRepairRecommendationRequest,
    build_owner_policy_repair_recommendation_request,
    owner_policy_repair_recommendation_prompt,
    validate_owner_policy_repair_recommendation,
    validate_owner_policy_repair_recommendation_request,
)

REPAIR_TRANSPORT_SCHEMA_VERSION = "1.0"
REPAIR_MODEL_IDENTITY_BASIS = "negotiated-thread-model; not independently served-model attestation"
_REQUEST_FIELDS = {
    "schema_version",
    "kind",
    "config",
    "request_id",
    "request",
    "host_instructions",
    "prompt",
    "output_schema",
}
_RESULT_FIELDS = {
    "schema_version",
    "kind",
    "request_id",
    "recommendation_request_id",
    "identity",
    "identity_basis",
    "usage",
    "recommendation",
    "recommendation_id",
}


@dataclass(frozen=True, slots=True)
class OwnerPolicyRepairTransportRequest:
    """Detached data, not an authenticated approval or permission to share."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def request_id(self) -> str:
        return "owner-repair-transport-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class OwnerPolicyRepairTransportResult:
    """Host-bound metadata; direct construction proves neither origin nor truth."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


def _inner_request(
    request: OwnerPolicyRepairRecommendationRequest,
) -> OwnerPolicyRepairRecommendationRequest:
    if type(request) is not OwnerPolicyRepairRecommendationRequest:
        raise ContractError("Unexpected repair request type", code="validation-shape")
    return validate_owner_policy_repair_recommendation_request(
        getattr(request, "payload_json", None)
    )


def owner_policy_repair_output_schema(
    request: OwnerPolicyRepairRecommendationRequest,
) -> dict[str, Any]:
    """Provider guidance; the host still enforces cross-field rules and budgets."""
    checked = _inner_request(request)
    context = checked.to_dict()
    text = {"type": "string", "minLength": 1, "maxLength": 4096}

    def texts(minimum: int = 0) -> dict[str, Any]:
        return {"type": "array", "items": dict(text), "minItems": minimum, "maxItems": 32}

    statuses = ["no-change", "unknown"]
    pair: dict[str, Any] = {"type": "null"}
    if context["candidate"] == "before":
        statuses.insert(0, "registered-change")
        pair = {
            "anyOf": [
                {"type": "string", "enum": [context["registry"]["pair_id"]]},
                {"type": "null"},
            ]
        }
    fields = {
        "schema_version": {"type": "string", "enum": [REPAIR_RECOMMENDATION_SCHEMA_VERSION]},
        "request_id": {"type": "string", "enum": [checked.request_id]},
        "status": {"type": "string", "enum": statuses},
        "rationale": dict(text),
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string", "enum": list(context["evidence_ids"].values())},
            "minItems": 4,
            "maxItems": 4,
        },
        "case_ids": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [case["case_id"] for case in context["content"]["cases"]],
            },
            "minItems": 1,
            "maxItems": 8,
        },
        "assumptions": texts(1),
        "uncertainties": texts(),
        "expected_effects": texts(1),
        "limitations": texts(1),
        "change_pair_id": pair,
    }
    return {
        "title": "AuthZest registered owner-policy repair selection",
        "description": (
            "Untrusted static reasoning only. The host additionally validates nonblank "
            "UTF-8 text, unique citations, exact evidence coverage, status/pair consistency, "
            "unknown uncertainties and complete JSON budgets. No source or checks execute."
        ),
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def build_owner_policy_repair_transport_request(
    model: str, *, candidate: str = "before"
) -> OwnerPolicyRepairTransportRequest:
    """Bind only registered input and one explicit model; no account or filesystem reads."""
    config = AdapterConfig(
        provider="codex-app-server",
        model=model,
        adapter_version="0.1",
        prompt_version=REPAIR_RECOMMENDATION_PROMPT_VERSION,
        temperature=None,
    )
    request = build_owner_policy_repair_recommendation_request(candidate)
    raw = canonical(
        {
            "schema_version": REPAIR_TRANSPORT_SCHEMA_VERSION,
            "kind": "owner-policy-repair-transport-request",
            "config": asdict(config),
            "request_id": request.request_id,
            "request": request.to_dict(),
            "host_instructions": HOST_INSTRUCTIONS,
            "prompt": owner_policy_repair_recommendation_prompt(request),
            "output_schema": owner_policy_repair_output_schema(request),
        }
    )
    decode(raw)
    return OwnerPolicyRepairTransportRequest(raw)


def validate_owner_policy_repair_transport_request(raw: str) -> OwnerPolicyRepairTransportRequest:
    """Rebuild every displayed/sent field; rehashed caller changes remain invalid."""
    data = _object(decode(raw), _REQUEST_FIELDS)
    request = validate_owner_policy_repair_recommendation_request(canonical(data["request"]))
    config = _object(data["config"], set(AdapterConfig.__dataclass_fields__))
    expected = build_owner_policy_repair_transport_request(
        config["model"], candidate=request.to_dict()["candidate"]
    )
    if canonical(data) != expected.payload_json:
        raise ContractError("Repair transport request mismatch", code="validation-identity")
    return expected


def _request_context(
    request: OwnerPolicyRepairTransportRequest,
) -> OwnerPolicyRepairTransportRequest:
    if type(request) is not OwnerPolicyRepairTransportRequest:
        raise ContractError("Unexpected repair transport type", code="validation-shape")
    return validate_owner_policy_repair_transport_request(getattr(request, "payload_json", None))


def prepare_owner_policy_repair_transport_result(
    raw: str,
    request: OwnerPolicyRepairTransportRequest,
    *,
    usage: dict[str, int | None] | None,
) -> OwnerPolicyRepairTransportResult:
    """Bind validated untrusted text and supplied transport metadata, not runtime facts."""
    checked = _request_context(request)
    context = checked.to_dict()
    inner = validate_owner_policy_repair_recommendation_request(canonical(context["request"]))
    recommendation = validate_owner_policy_repair_recommendation(raw, inner)
    if usage is not None:
        try:
            _object(usage, {"input_tokens", "output_tokens"})
            for value in usage.values():
                if value is not None:
                    _integer(value)
        except ContractError as exc:
            raise ContractError("Invalid usage metadata", code="validation-usage") from exc
    result = canonical(
        {
            "schema_version": REPAIR_TRANSPORT_SCHEMA_VERSION,
            "kind": "owner-policy-repair-transport-result",
            "request_id": checked.request_id,
            "recommendation_request_id": inner.request_id,
            "identity": {
                field: context["config"][field]
                for field in ("provider", "model", "adapter_version", "prompt_version")
            },
            "identity_basis": REPAIR_MODEL_IDENTITY_BASIS,
            "usage": usage,
            "recommendation": recommendation.to_dict(),
            "recommendation_id": recommendation.recommendation_id,
        }
    )
    decode(result)
    return OwnerPolicyRepairTransportResult(result)


def validate_owner_policy_repair_transport_result(
    result: OwnerPolicyRepairTransportResult, request: OwnerPolicyRepairTransportRequest
) -> OwnerPolicyRepairTransportResult:
    """Recheck a returned wrapper; caller construction does not establish transport origin."""
    if type(result) is not OwnerPolicyRepairTransportResult:
        raise ContractError("Unexpected repair result type", code="validation-shape")
    data = _object(decode(getattr(result, "payload_json", None)), _RESULT_FIELDS)
    expected = prepare_owner_policy_repair_transport_result(
        canonical(data["recommendation"]), request, usage=data["usage"]
    )
    if canonical(data) != expected.payload_json:
        raise ContractError("Repair transport result mismatch", code="validation-identity")
    return expected
