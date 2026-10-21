"""Guarded scripted selection contracts, never model, execution or approval evidence."""

import asyncio
import builtins
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex import owner_policy_recommendation as s1
from authzest.codex import owner_policy_repair_pair as pair_contract
from authzest.codex import owner_policy_repair_recommendation as contract
from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    ContractError,
    canonical,
    contract_failure_code,
    identity,
)
from authzest.codex.diagnostics import VALIDATION_CODES

RESULT_FIELDS = {
    "schema_version",
    "request_id",
    "status",
    "rationale",
    "evidence_ids",
    "case_ids",
    "assumptions",
    "uncertainties",
    "expected_effects",
    "limitations",
    "change_pair_id",
}
TEXT_LISTS = ("assumptions", "uncertainties", "expected_effects", "limitations")


@pytest.fixture(autouse=True)
def forbid_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "Repair selection contracts must not use I/O, providers, processes or evaluation"
        )

    original_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn", "openai", "httpx", "requests"}:
            forbidden()
        if name.startswith(("authzest.runner", "authzest.codex.app_server")):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)


@pytest.fixture
def request_context():
    return contract.build_owner_policy_repair_recommendation_request()


def draft(request, status="registered-change"):
    data = request.to_dict()
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted test-only selection; not a provider or maintainer decision.",
        "evidence_ids": list(data["evidence_ids"].values()),
        "case_ids": [case["case_id"] for case in data["content"]["cases"]],
        "assumptions": ["The synthetic principal and ownership inputs are already trusted."],
        "uncertainties": ["No endpoint or policy evaluation was performed."]
        if status == "unknown"
        else [],
        "expected_effects": ["The selected registered source would restore its ownership check."],
        "limitations": ["Structural validation does not establish model quality or authorization."],
        "change_pair_id": data["registry"]["pair_id"] if status == "registered-change" else None,
    }


def validate(data, request):
    return contract.validate_owner_policy_repair_recommendation(canonical(data), request)


def preview(data, request):
    return contract.prepare_owner_policy_repair_recommendation_preview(
        validate(data, request), request
    )


def replace(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


def sized_draft(request, target_bytes):
    data = draft(request)
    for field in TEXT_LISTS:
        data[field] = ["a"] * 32
    remaining = target_bytes - len(canonical(data).encode("utf-8"))
    assert remaining >= 0
    for field in TEXT_LISTS:
        for index in range(32):
            extra = min(4095, remaining)
            data[field][index] += "a" * extra
            remaining -= extra
    assert remaining == 0
    assert len(canonical(data).encode("utf-8")) == target_bytes
    return data


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_request_is_an_exact_registered_content_snapshot_with_candidate_binding(candidate):
    request = contract.build_owner_policy_repair_recommendation_request(candidate=candidate)
    data = request.to_dict()
    pair = pair_contract.build_owner_policy_repair_pair()
    registered = pair.to_dict()
    assert set(data) == {
        "schema_version",
        "kind",
        "candidate",
        "prompt",
        "registry",
        "content",
        "evidence_ids",
    }
    assert data["schema_version"] == contract.REPAIR_RECOMMENDATION_SCHEMA_VERSION == "1.0"
    assert data["kind"] == "owner-policy-repair-recommendation-request"
    assert data["candidate"] == candidate
    assert data["content"] == registered["content"]
    assert data["registry"] == {
        "version": registered["registry_version"],
        "pair_id": pair.pair_id,
        "content_sha256": registered["review_binding"]["content_sha256"],
        "review_record_sha256": registered["review_binding"]["review_record_sha256"],
    }
    assert set(data["prompt"]) == {"version", "text"}
    assert data["prompt"]["version"] == "owner-repair-selection-v1"
    assert data["prompt"]["text"]
    assert set(data["evidence_ids"]) == {"before", "after", "criteria", "cases"}
    assert data["evidence_ids"] == {
        field: "owner-repair-evidence-" + identity({"kind": field, "data": data["content"][field]})
        for field in ("before", "after", "criteria", "cases")
    }
    assert request.request_id == "owner-repair-request-" + identity(data)
    assert (
        contract.validate_owner_policy_repair_recommendation_request(
            json.dumps(data, indent=2, ensure_ascii=True)
        )
        == request
    )
    assert contract.build_owner_policy_repair_recommendation_request(candidate=candidate) == request


def test_candidate_changes_identity_but_not_registered_content_or_registry():
    before = contract.build_owner_policy_repair_recommendation_request()
    after = contract.build_owner_policy_repair_recommendation_request(candidate="after")
    assert before.to_dict()["candidate"] == "before"
    assert before.request_id != after.request_id
    for field in ("content", "registry", "evidence_ids", "prompt"):
        assert before.to_dict()[field] == after.to_dict()[field]


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_prompt_contains_exact_bound_request_and_identity_without_sending(candidate):
    request = contract.build_owner_policy_repair_recommendation_request(candidate=candidate)
    expected = (
        request.to_dict()["prompt"]["text"]
        + "\nREQUEST_JSON:\n"
        + request.payload_json
        + "\nREQUEST_ID:\n"
        + request.request_id
        + "\n"
    )
    assert contract.owner_policy_repair_recommendation_prompt(request) == expected
    assert len(expected.encode("utf-8")) <= MAX_JSON_BYTES
    assert contract.owner_policy_repair_recommendation_prompt(request) == expected


def test_complete_prompt_utf8_budget_includes_both_instructions_and_request(monkeypatch):
    # Simulate a future maintained prompt update; callers cannot supply instructions.
    monkeypatch.setattr(contract, "_INSTRUCTIONS", contract._INSTRUCTIONS + "\U0001f600" * 40_000)
    request = contract.build_owner_policy_repair_recommendation_request()
    assert len(request.payload_json.encode("utf-8")) < MAX_JSON_BYTES
    with pytest.raises(ContractError) as caught:
        contract.owner_policy_repair_recommendation_prompt(request)
    assert contract_failure_code(caught.value) == "validation-budget"


@pytest.mark.parametrize("value", [None, True, 0, [], {}, "", "BEFORE", "before ", "policy.py"])
def test_candidate_is_an_exact_closed_choice(value):
    with pytest.raises(ContractError):
        contract.build_owner_policy_repair_recommendation_request(candidate=value)


@pytest.mark.parametrize("option", ["source", "path", "registry", "cases", "model", "callback"])
def test_no_source_registry_provider_or_execution_options_are_supported(option):
    with pytest.raises(TypeError):
        contract.build_owner_policy_repair_recommendation_request(**{option: None})


@pytest.mark.parametrize(
    ("candidate", "status"),
    [
        ("before", "registered-change"),
        ("before", "no-change"),
        ("before", "unknown"),
        ("after", "no-change"),
        ("after", "unknown"),
    ],
)
def test_scripted_results_have_closed_fields_and_no_authority_preview(candidate, status):
    request = contract.build_owner_policy_repair_recommendation_request(candidate=candidate)
    raw = draft(request, status)
    recommendation = validate(raw, request)
    assert recommendation.to_dict() == raw
    assert set(recommendation.to_dict()) == RESULT_FIELDS
    assert recommendation.recommendation_id == "owner-repair-recommendation-" + identity(raw)
    data = preview(raw, request).to_dict()
    assert set(data) == {
        "schema_version",
        "kind",
        "request_id",
        "recommendation_id",
        "request",
        "recommendation",
        "pair_preview",
        "provider_calls",
        "execution_status",
        "patch_application",
        "restoration_status",
        "observations",
        "comparison_status",
        "authorization_status",
        "provenance",
    }
    assert data["schema_version"] == "1.0"
    assert data["kind"] == "owner-policy-repair-recommendation-preview"
    assert data["request_id"] == request.request_id
    assert data["recommendation_id"] == recommendation.recommendation_id
    assert data["request"] == request.to_dict()
    assert data["recommendation"] == raw
    assert data["provider_calls"] == 0
    for field in ("execution_status", "patch_application", "restoration_status"):
        assert data[field] == "not-run"
    assert data["authorization_status"] == "unknown"
    assert data["observations"] == {"before": None, "after": None}
    assert data["comparison_status"] == "not-evaluated"
    assert data["provenance"] == {"kind": "caller-supplied-data", "authenticated": False}
    if status == "registered-change":
        assert (
            data["pair_preview"]
            == pair_contract.prepare_owner_policy_repair_pair_preview(
                pair_contract.build_owner_policy_repair_pair()
            ).to_dict()
        )
        assert data["pair_preview"]["observations"] == {"before": None, "after": None}
        assert data["pair_preview"]["comparison_status"] == "not-evaluated"
    else:
        assert data["pair_preview"] is None


def test_after_candidate_never_selects_the_registered_change():
    request = contract.build_owner_policy_repair_recommendation_request(candidate="after")
    with pytest.raises(ContractError):
        validate(draft(request), request)


def test_snapshots_are_frozen_slotted_and_detached(request_context):
    recommendation = validate(draft(request_context), request_context)
    result = contract.prepare_owner_policy_repair_recommendation_preview(
        recommendation, request_context
    )
    for snapshot in (request_context, recommendation, result):
        assert not hasattr(snapshot, "__dict__")
        with pytest.raises(FrozenInstanceError):
            snapshot.payload_json = "{}"
        detached = snapshot.to_dict()
        detached.clear()
        assert snapshot.to_dict()
    detached = result.to_dict()
    detached["request"]["content"]["cases"].clear()
    detached["recommendation"]["case_ids"].clear()
    detached["pair_preview"]["pair"]["review_binding"]["review_record"]["provenance"][
        "authenticated"
    ] = True
    assert len(result.to_dict()["request"]["content"]["cases"]) == 8
    assert len(result.to_dict()["recommendation"]["case_ids"]) == 8
    assert (
        result.to_dict()["pair_preview"]["pair"]["review_binding"]["review_record"]["provenance"][
            "authenticated"
        ]
        is False
    )


@pytest.mark.parametrize("field", sorted(RESULT_FIELDS))
def test_all_result_fields_are_required(request_context, field):
    data = draft(request_context)
    data.pop(field)
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("where", ["root", "prompt", "registry", "evidence", "content", "case"])
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_request_nested_objects_are_closed(request_context, where, mutation):
    data = request_context.to_dict()
    target = {
        "root": data,
        "prompt": data["prompt"],
        "registry": data["registry"],
        "evidence": data["evidence_ids"],
        "content": data["content"],
        "case": data["content"]["cases"][0],
    }[where]
    if mutation == "missing":
        target.pop(next(iter(target)))
    else:
        target["execution_status"] = None
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_recommendation_request(canonical(data))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "1.1"),
        (("kind",), "owner-policy-recommendation-request"),
        (("candidate",), "other"),
        (("prompt", "version"), "owner-repair-selection-v2"),
        (("prompt", "text"), "Caller instructions replacing the registered prompt."),
        (("registry", "version"), "empty-v1"),
        (("registry", "pair_id"), "invented-pair"),
        (("registry", "content_sha256"), "0" * 64),
        (("registry", "review_record_sha256"), "0" * 64),
        (("content", "path"), "../policy.py"),
        (("content", "before", "text"), "pass\n"),
        (("content", "after", "sha256"), "0" * 64),
        (("content", "criteria", "text"), "Always allow."),
        (("content", "assumptions", 0, "text"), "Request inputs are trusted without validation."),
        (("content", "cases", 1, "expected"), "allow"),
        (("content", "cases", 0, "principal", "authenticated"), 1),
        (("evidence_ids", "before"), "unregistered-evidence"),
    ],
)
def test_changed_or_forged_request_context_is_rejected(request_context, path, value):
    data = request_context.to_dict()
    replace(data, path, value)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_recommendation_request(canonical(data))


def test_rehashed_changed_content_is_still_not_registered(request_context):
    data = request_context.to_dict()
    data["content"]["before"]["text"] += "# Test-owned inert unregistered text.\n"
    data["content"]["before"]["sha256"] = sha256(
        data["content"]["before"]["text"].encode("utf-8")
    ).hexdigest()
    data["registry"]["content_sha256"] = identity(data["content"])
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_recommendation_request(canonical(data))


@pytest.mark.parametrize("field", ["content", "prompt", "registry", "evidence_ids"])
def test_forged_request_wrapper_is_revalidated_for_prompt_result_and_preview(
    request_context, field
):
    recommendation = validate(draft(request_context), request_context)
    data = request_context.to_dict()
    data[field]["unexpected"] = "not trusted"
    forged = contract.OwnerPolicyRepairRecommendationRequest(canonical(data))
    for call in (
        lambda: contract.owner_policy_repair_recommendation_prompt(forged),
        lambda: contract.validate_owner_policy_repair_recommendation(
            canonical(draft(request_context)), forged
        ),
        lambda: contract.prepare_owner_policy_repair_recommendation_preview(recommendation, forged),
    ):
        with pytest.raises(ContractError):
            call()


def test_before_result_cannot_be_replayed_against_after_context(request_context):
    after = contract.build_owner_policy_repair_recommendation_request(candidate="after")
    raw = draft(request_context, "no-change")
    result = validate(raw, request_context)
    with pytest.raises(ContractError):
        validate(raw, after)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_repair_recommendation_preview(result, after)


@pytest.mark.parametrize("change", ["prompt-text", "prompt-version", "schema", "registration"])
def test_changed_host_registration_invalidates_preexisting_artifacts(
    request_context, monkeypatch, change
):
    raw = draft(request_context)
    recommendation = validate(raw, request_context)
    if change == "prompt-text":
        monkeypatch.setattr(
            contract, "_INSTRUCTIONS", contract._INSTRUCTIONS + "\nNew instructions."
        )
    elif change == "prompt-version":
        monkeypatch.setattr(contract, "REPAIR_RECOMMENDATION_PROMPT_VERSION", "selection-updated")
    elif change == "schema":
        monkeypatch.setattr(contract, "REPAIR_RECOMMENDATION_SCHEMA_VERSION", "1.1")
    else:
        build_pair = contract.build_owner_policy_repair_pair

        def changed_registration():
            data = build_pair().to_dict()
            data["registry_version"] = "test-only-host-registration-update"
            return pair_contract.OwnerPolicyRepairPair(canonical(data))

        monkeypatch.setattr(contract, "build_owner_policy_repair_pair", changed_registration)
    current = contract.build_owner_policy_repair_recommendation_request()
    assert current.request_id != request_context.request_id
    for call in (
        lambda: contract.validate_owner_policy_repair_recommendation_request(
            request_context.payload_json
        ),
        lambda: contract.owner_policy_repair_recommendation_prompt(request_context),
        lambda: validate(raw, request_context),
        lambda: validate(raw, current),
        lambda: contract.prepare_owner_policy_repair_recommendation_preview(
            recommendation, request_context
        ),
    ):
        with pytest.raises(ContractError):
            call()


@pytest.mark.parametrize("value", ["stale-request", "", 0, False, None])
def test_result_is_bound_to_the_exact_current_request(request_context, value):
    data = draft(request_context)
    data["request_id"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("value", ["change", "confirmed", "fixed", "passed", "", True, 0, None])
def test_status_is_a_closed_choice_not_an_execution_claim(request_context, value):
    data = draft(request_context)
    data["status"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("value", [None, "invented-pair", "", [], {}, 0, False])
def test_registered_change_requires_exact_registered_pair_id(request_context, value):
    data = draft(request_context)
    data["change_pair_id"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("status", ["no-change", "unknown"])
def test_non_change_statuses_cannot_carry_a_pair_selection(request_context, status):
    data = draft(request_context, status)
    data["change_pair_id"] = request_context.to_dict()["registry"]["pair_id"]
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("mutation", ["missing", "extra", "unknown", "duplicate", "text", "number"])
def test_evidence_requires_all_four_distinct_registered_ids(request_context, mutation):
    data = draft(request_context)
    refs = data["evidence_ids"]
    data["evidence_ids"] = {
        "missing": refs[:-1],
        "extra": [*refs, "unregistered-evidence"],
        "unknown": [*refs[:-1], "unregistered-evidence"],
        "duplicate": [*refs[:-1], refs[0]],
        "text": refs[0],
        "number": [*refs[:-1], 1],
    }[mutation]
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("value", [[], ["unknown"], ["owner-control"] * 2, None, "non-owner", [1]])
def test_case_references_are_nonempty_unique_registered_ids(request_context, value):
    data = draft(request_context)
    data["case_ids"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_registered_case_subsets_and_reference_order_are_preserved(request_context):
    data = draft(request_context)
    data["case_ids"] = ["non-owner"]
    data["evidence_ids"].reverse()
    assert validate(data, request_context).to_dict() == data
    data["case_ids"] = list(reversed(draft(request_context)["case_ids"]))
    assert validate(data, request_context).to_dict() == data
    data["case_ids"].append("owner-control")
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", ["evidence_ids", "case_ids"])
@pytest.mark.parametrize("value", ["", " ", "x" * 129, "x\x00", True])
def test_reference_items_are_strict_nonblank_bounded_text(request_context, field, value):
    data = draft(request_context)
    data[field][-1] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", TEXT_LISTS)
@pytest.mark.parametrize(
    "value", [None, "not-list", [None], [True], [""], ["x" * 4097], ["x"] * 33]
)
def test_text_lists_are_strict_nonblank_bounded_data(request_context, field, value):
    data = draft(request_context)
    data[field] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", ["assumptions", "expected_effects", "limitations"])
@pytest.mark.parametrize("status", ["registered-change", "no-change", "unknown"])
def test_each_status_requires_assumptions_effects_and_limitations(request_context, field, status):
    data = draft(request_context, status)
    data[field] = []
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_only_unknown_requires_an_explicit_uncertainty(request_context):
    data = draft(request_context, "unknown")
    data["uncertainties"] = []
    with pytest.raises(ContractError):
        validate(data, request_context)
    data["status"] = "no-change"
    assert validate(data, request_context).to_dict()["uncertainties"] == []


@pytest.mark.parametrize(
    "field",
    [
        "replacement_source",
        "patch",
        "diff",
        "command",
        "model",
        "observations",
        "labels",
        "approval",
        "execution_status",
        "provenance",
    ],
)
def test_result_rejects_even_empty_source_execution_and_authority_fields(request_context, field):
    data = draft(request_context)
    data[field] = None
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", ["schema_version", "request_id", "rationale"])
@pytest.mark.parametrize("value", [None, False, 1, [], {}])
def test_result_scalar_types_are_not_coerced(request_context, field, value):
    data = draft(request_context)
    data[field] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("value", ["", " \t\r\n", "\u0085\u00a0", "x" * 4097, "x\x00", "x\x1b"])
def test_blank_long_and_control_text_is_rejected(request_context, value):
    data = draft(request_context)
    data["rationale"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_explanation_and_instruction_like_text_stays_inert_data(request_context):
    data = draft(request_context)
    text = "$(never-run)\n__import__('os').system('never-run')\n```python\npass\n```"
    data["rationale"] = text
    for field in TEXT_LISTS:
        data[field] = [text]
    result = preview(data, request_context).to_dict()
    assert result["recommendation"] == data
    assert result["provider_calls"] == 0
    assert result["execution_status"] == "not-run"


@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"], ids=["high", "low"])
def test_escaped_lone_surrogates_fail_after_decoding(request_context, surrogate):
    data = draft(request_context)
    data["rationale"] = "invalid" + surrogate
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_recommendation(
            json.dumps(data, ensure_ascii=True), request_context
        )


def test_forged_result_snapshot_is_revalidated_before_preview(request_context):
    data = draft(request_context)
    original = validate(data, request_context)
    data["rationale"] += " Another scripted explanation."
    assert validate(data, request_context).recommendation_id != original.recommendation_id
    data["status"] = "confirmed"
    forged = contract.OwnerPolicyRepairRecommendation(canonical(data))
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_repair_recommendation_preview(forged, request_context)


@pytest.mark.parametrize("value", [None, {}, [], "{}"])
def test_raw_objects_are_not_trusted_artifact_wrappers(request_context, value):
    result = validate(draft(request_context), request_context)
    for call in (
        lambda: contract.owner_policy_repair_recommendation_prompt(value),
        lambda: contract.validate_owner_policy_repair_recommendation(
            canonical(draft(request_context)), value
        ),
        lambda: contract.prepare_owner_policy_repair_recommendation_preview(value, request_context),
        lambda: contract.prepare_owner_policy_repair_recommendation_preview(result, value),
    ):
        with pytest.raises(ContractError):
            call()


def test_wrong_snapshot_kinds_and_subclasses_are_not_reinterpreted_as_trusted_inputs(
    request_context,
):
    class RequestSubclass(contract.OwnerPolicyRepairRecommendationRequest):
        pass

    class ResultSubclass(contract.OwnerPolicyRepairRecommendation):
        pass

    raw = draft(request_context)
    result = validate(raw, request_context)
    prepared = contract.prepare_owner_policy_repair_recommendation_preview(result, request_context)
    for value in (
        result,
        prepared,
        RequestSubclass(request_context.payload_json),
        pair_contract.build_owner_policy_repair_pair(),
    ):
        with pytest.raises(ContractError):
            contract.validate_owner_policy_repair_recommendation(canonical(raw), value)
        with pytest.raises(ContractError):
            contract.owner_policy_repair_recommendation_prompt(value)
    for value in (request_context, prepared, ResultSubclass(result.payload_json)):
        with pytest.raises(ContractError):
            contract.prepare_owner_policy_repair_recommendation_preview(value, request_context)


@pytest.mark.parametrize(
    ("raw", "expected_code"),
    [
        ("[]", "validation-shape"),
        ("null", "validation-shape"),
        ("{broken", "validation-json"),
        ('{"duplicate":0,"duplicate":1}', "validation-duplicate"),
        ('{"x":NaN}', "validation-json"),
        ('{"x":Infinity}', "validation-json"),
        ('{"x":1e999}', "validation-json"),
        (" " * (MAX_JSON_BYTES + 1), "validation-budget"),
        ('{"x":' + "[" * 33 + "0" + "]" * 33 + "}", "validation-budget"),
        (canonical({"x": ["a"] * 8193}), "validation-budget"),
    ],
    ids=[
        "array",
        "null",
        "syntax",
        "duplicate",
        "nan",
        "infinity",
        "overflow",
        "bytes",
        "depth",
        "nodes",
    ],
)
def test_json_and_global_structural_budgets_apply_before_artifact_shape(
    request_context, raw, expected_code
):
    for call in (
        lambda: contract.validate_owner_policy_repair_recommendation_request(raw),
        lambda: contract.validate_owner_policy_repair_recommendation(raw, request_context),
    ):
        with pytest.raises(ContractError) as caught:
            call()
        assert contract_failure_code(caught.value) == expected_code


def test_utf8_budget_is_independent_of_character_limit(request_context):
    data = draft(request_context)
    for field in TEXT_LISTS:
        data[field] = ["\U0001f600" * 4096] * 15
    raw = canonical(data)
    assert len(raw) < MAX_JSON_BYTES < len(raw.encode("utf-8"))
    with pytest.raises(ContractError) as caught:
        contract.validate_owner_policy_repair_recommendation(raw, request_context)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_raw_result_budget_does_not_exempt_completed_host_preview(request_context):
    result = validate(sized_draft(request_context, MAX_JSON_BYTES), request_context)
    assert len(result.payload_json.encode("utf-8")) == MAX_JSON_BYTES
    with pytest.raises(ContractError) as caught:
        contract.prepare_owner_policy_repair_recommendation_preview(result, request_context)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_full_preview_accepts_exact_byte_boundary_but_rejects_one_byte_over(request_context):
    small = validate(draft(request_context), request_context)
    baseline = contract.prepare_owner_policy_repair_recommendation_preview(small, request_context)
    overhead = len(baseline.payload_json.encode("utf-8")) - len(small.payload_json.encode("utf-8"))
    assert overhead > 0
    exact = validate(sized_draft(request_context, MAX_JSON_BYTES - overhead), request_context)
    completed = contract.prepare_owner_policy_repair_recommendation_preview(exact, request_context)
    assert len(completed.payload_json.encode("utf-8")) == MAX_JSON_BYTES
    above = validate(sized_draft(request_context, MAX_JSON_BYTES - overhead + 1), request_context)
    with pytest.raises(ContractError) as caught:
        contract.prepare_owner_policy_repair_recommendation_preview(above, request_context)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_failure_diagnostics_are_closed_and_do_not_echo_untrusted_payload(request_context):
    sentinel = "DO-NOT-ECHO-REPAIR-SELECTION-SENTINEL"
    data = draft(request_context)
    data["forbidden_source"] = sentinel
    request = request_context.to_dict()
    request["content"]["before"]["text"] = sentinel
    for call in (
        lambda: contract.validate_owner_policy_repair_recommendation_request(canonical(request)),
        lambda: contract.validate_owner_policy_repair_recommendation(
            canonical(data), request_context
        ),
    ):
        with pytest.raises(ContractError) as caught:
            call()
        assert caught.value.code in VALIDATION_CODES
        assert contract_failure_code(caught.value) in VALIDATION_CODES
        assert sentinel not in str(caught.value)


def test_s1_empty_registry_remains_separate_and_rejects_new_repair_selection(request_context):
    legacy = s1.build_owner_policy_recommendation_request()
    assert legacy.to_dict()["registry"] == {"version": "empty-v1", "pairs": []}
    assert legacy.to_dict()["kind"] == "owner-policy-recommendation-request"
    with pytest.raises(ContractError):
        s1.validate_owner_policy_recommendation(canonical(draft(request_context)), legacy)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_recommendation(
            canonical(draft(request_context)), legacy
        )
