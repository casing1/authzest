"""Exact data envelopes for the maintained generated-source proposal contract.

These pure operations neither share data nor establish consent, model authorship,
served-model identity, code safety or runtime observations. Caller-supplied usage
and identity metadata remain unverified; generated Python is never executed here.
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
from .generated_repair import (
    PROMPT_VERSION,
    build_generated_repair_request,
    generated_repair_output_schema,
    generated_repair_prompt,
    validate_generated_repair_proposal,
    validate_generated_repair_request,
)

GENERATED_REPAIR_TRANSPORT_SCHEMA_VERSION = "1.0"
GENERATED_REPAIR_MODEL_IDENTITY_BASIS = (
    "negotiated-thread-model; not independently served-model attestation"
)
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
    "generation_request_id",
    "identity",
    "identity_basis",
    "usage",
    "proposal",
    "proposal_id",
}


@dataclass(frozen=True, slots=True)
class GeneratedRepairTransportRequest:
    """Detached content, not a sharing decision or authenticated authorization."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def request_id(self) -> str:
        return "generated-repair-transport-" + identity(self.to_dict())


@dataclass(frozen=True, slots=True)
class GeneratedRepairTransportResult:
    """Host-bound, untrusted data; direct construction attests no provider origin."""

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)


def build_generated_repair_transport_request(model: str) -> GeneratedRepairTransportRequest:
    """Bind the fixed scenario, prompt/schema and an explicit valid model label."""
    config = AdapterConfig(
        provider="codex-app-server",
        model=model,
        adapter_version="0.1",
        prompt_version=PROMPT_VERSION,
        temperature=None,
    )
    request = build_generated_repair_request()
    raw = canonical(
        {
            "schema_version": GENERATED_REPAIR_TRANSPORT_SCHEMA_VERSION,
            "kind": "generated-repair-transport-request",
            "config": asdict(config),
            "request_id": request.request_id,
            "request": request.to_dict(),
            "host_instructions": HOST_INSTRUCTIONS,
            "prompt": generated_repair_prompt(request),
            "output_schema": generated_repair_output_schema(request),
        }
    )
    decode(raw)
    return GeneratedRepairTransportRequest(raw)


def validate_generated_repair_transport_request(raw: str) -> GeneratedRepairTransportRequest:
    """Reconstruct every field; rehashing caller changes cannot extend the scope."""
    data = _object(decode(raw), _REQUEST_FIELDS)
    validate_generated_repair_request(canonical(data["request"]))
    config = _object(data["config"], set(AdapterConfig.__dataclass_fields__))
    expected = build_generated_repair_transport_request(config["model"])
    if canonical(data) != expected.payload_json:
        raise ContractError("Generated repair transport mismatch", code="validation-identity")
    return expected


def _request_context(request: GeneratedRepairTransportRequest) -> GeneratedRepairTransportRequest:
    if type(request) is not GeneratedRepairTransportRequest:
        raise ContractError("Unexpected generated transport type", code="validation-shape")
    return validate_generated_repair_transport_request(getattr(request, "payload_json", None))


def prepare_generated_repair_transport_result(
    raw: str,
    request: GeneratedRepairTransportRequest,
    *,
    usage: dict[str, int | None] | None,
) -> GeneratedRepairTransportResult:
    """Validate proposal data and bind supplied metadata, not served-model truth."""
    checked = _request_context(request)
    context = checked.to_dict()
    inner = validate_generated_repair_request(canonical(context["request"]))
    proposal = validate_generated_repair_proposal(raw, inner)
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
            "schema_version": GENERATED_REPAIR_TRANSPORT_SCHEMA_VERSION,
            "kind": "generated-repair-transport-result",
            "request_id": checked.request_id,
            "generation_request_id": inner.request_id,
            "identity": {
                field: context["config"][field]
                for field in ("provider", "model", "adapter_version", "prompt_version")
            },
            "identity_basis": GENERATED_REPAIR_MODEL_IDENTITY_BASIS,
            "usage": usage,
            "proposal": proposal.to_dict(),
            "proposal_id": proposal.proposal_id,
        }
    )
    decode(result)
    return GeneratedRepairTransportResult(result)


def validate_generated_repair_transport_result(
    result: GeneratedRepairTransportResult, request: GeneratedRepairTransportRequest
) -> GeneratedRepairTransportResult:
    """Recheck returned envelopes; caller-built metadata has no authenticated origin."""
    if type(result) is not GeneratedRepairTransportResult:
        raise ContractError("Unexpected generated result type", code="validation-shape")
    data = _object(decode(getattr(result, "payload_json", None)), _RESULT_FIELDS)
    expected = prepare_generated_repair_transport_result(
        canonical(data["proposal"]), request, usage=data["usage"]
    )
    if canonical(data) != expected.payload_json:
        raise ContractError("Generated result identity mismatch", code="validation-identity")
    return expected
