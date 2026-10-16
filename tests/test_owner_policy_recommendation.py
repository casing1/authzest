"""Guarded pure contracts using test-owned data, never model or approval evidence."""

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

from authzest.codex import owner_policy_recommendation as contract
from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    ContractError,
    canonical,
    contract_failure_code,
    identity,
)
from authzest.codex.diagnostics import VALIDATION_CODES
from authzest.codex.owner_policy_review import OWNER_POLICY_SOURCE

CRITERIA = (
    "Allow a report read only for an already trusted principal whose authenticated value is "
    "exactly true, whose scopes contain the literal reports:read value, and whose subject exactly "
    "matches a trusted report owner. Deny missing or malformed principal/report context, blank "
    "identifiers or malformed scopes. Do not normalize identifiers. There is no administrator, "
    "wildcard or ownership exception. This pure predicate does not authenticate inputs or prove "
    "HTTP enforcement."
)
ASSUMPTIONS = [
    {
        "id": "trusted-principal",
        "text": "The caller supplies an already trusted principal; constructing a dataclass does "
        "not authenticate identity, scopes or authentication claims.",
    },
    {
        "id": "trusted-ownership",
        "text": "Report ownership and report identity come from a trusted lookup, not "
        "request-supplied claims.",
    },
    {
        "id": "synthetic-pure-policy",
        "text": "Only the maintained synthetic pure predicate is in scope; HTTP, "
        "authentication-provider, database and endpoint enforcement are not evaluated.",
    },
]
RESULT_FIELDS = {
    "schema_version",
    "request_id",
    "status",
    "rationale",
    "evidence_ids",
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
        pytest.fail("Recommendation contracts must not use I/O, providers, processes or evaluation")

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
    return contract.build_owner_policy_recommendation_request()


def draft(request, status="no-change"):
    data = request.to_dict()
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Test-owned explanation; not a model answer or maintainer decision.",
        "evidence_ids": [data["source"]["evidence_id"], data["criteria"]["evidence_id"]],
        "assumptions": ["This test assumes previously trusted principal and ownership inputs."],
        "uncertainties": ["Endpoint enforcement has not been evaluated."]
        if status == "unknown"
        else [],
        "expected_effects": ["No source is changed by this structural artifact."],
        "limitations": [
            "This scripted contract test proves neither model quality nor authorization."
        ],
        "change_pair_id": None,
    }


def validate(data, request):
    return contract.validate_owner_policy_recommendation(canonical(data), request)


def preview(data, request):
    return contract.prepare_owner_policy_recommendation_preview(validate(data, request), request)


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


def test_builder_contains_only_exact_registered_source_criteria_and_empty_registry(request_context):
    data = request_context.to_dict()
    assert set(data) == {
        "schema_version",
        "kind",
        "scenario_id",
        "source",
        "criteria",
        "assumptions",
        "registry",
    }
    assert data["schema_version"] == "1.0"
    assert data["kind"] == "owner-policy-recommendation-request"
    assert data["scenario_id"] == "owned-report-read-policy-v1"
    source = {
        "path": "policy.py",
        "text": OWNER_POLICY_SOURCE,
        "sha256": sha256(OWNER_POLICY_SOURCE.encode("utf-8")).hexdigest(),
    }
    criteria = {"text": CRITERIA, "sha256": sha256(CRITERIA.encode("utf-8")).hexdigest()}
    assert data["source"] == {
        **source,
        "evidence_id": "owner-recommendation-source-" + identity(source),
    }
    assert data["criteria"] == {
        **criteria,
        "evidence_id": "owner-recommendation-criteria-" + identity(criteria),
    }
    assert data["criteria"]["text"].endswith(".") and not CRITERIA.endswith("\n")
    assert data["assumptions"] == ASSUMPTIONS
    assert data["registry"] == {"version": "empty-v1", "pairs": []}
    assert request_context.request_id == "owner-recommendation-request-" + identity(data)
    assert contract.build_owner_policy_recommendation_request() == request_context
    assert (
        contract.validate_owner_policy_recommendation_request(
            json.dumps(data, indent=2, ensure_ascii=True)
        )
        == request_context
    )


@pytest.mark.parametrize(
    "option",
    [
        "path",
        "source",
        "repository",
        "model",
        "callback",
        "cases",
        "labels",
        "observations",
        "registry",
    ],
)
def test_builder_accepts_no_caller_selected_input_or_registry_option(option):
    with pytest.raises(TypeError):
        contract.build_owner_policy_recommendation_request(**{option: None})


@pytest.mark.parametrize("status", ["no-change", "unknown"])
def test_valid_scripted_statuses_have_only_raw_fields_and_non_authority_preview(
    request_context, status
):
    raw = draft(request_context, status)
    recommendation = validate(raw, request_context)
    assert set(recommendation.to_dict()) == RESULT_FIELDS
    assert recommendation.to_dict() == raw
    assert recommendation.recommendation_id == "owner-recommendation-" + identity(raw)
    data = contract.prepare_owner_policy_recommendation_preview(
        recommendation, request_context
    ).to_dict()
    assert data == {
        "schema_version": "1.0",
        "kind": "owner-policy-recommendation-preview",
        "request_id": request_context.request_id,
        "recommendation_id": recommendation.recommendation_id,
        "request": request_context.to_dict(),
        "recommendation": raw,
        "source_sha256": request_context.to_dict()["source"]["sha256"],
        "criteria_sha256": request_context.to_dict()["criteria"]["sha256"],
        "registry_version": "empty-v1",
        "changes": [],
        "diffs": [],
        "provider_calls": 0,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
        "provenance": {"kind": "caller-supplied-data", "authenticated": False},
    }


def test_all_snapshots_are_frozen_slotted_and_return_detached_dictionaries(request_context):
    recommendation = validate(draft(request_context), request_context)
    result = contract.prepare_owner_policy_recommendation_preview(recommendation, request_context)
    for snapshot in (request_context, recommendation, result):
        assert not hasattr(snapshot, "__dict__")
        with pytest.raises(FrozenInstanceError):
            snapshot.payload_json = "{}"
        detached = snapshot.to_dict()
        detached.clear()
        assert snapshot.to_dict()
    data = result.to_dict()
    data["request"]["registry"]["pairs"].append("not-registered")
    data["recommendation"]["assumptions"].clear()
    data["provenance"]["authenticated"] = True
    assert result.to_dict()["request"]["registry"]["pairs"] == []
    assert result.to_dict()["recommendation"]["assumptions"]
    assert result.to_dict()["provenance"]["authenticated"] is False


@pytest.mark.parametrize("field", sorted(RESULT_FIELDS))
def test_every_result_field_is_required(request_context, field):
    data = draft(request_context)
    data.pop(field)
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("where", ["root", "source", "criteria", "assumption", "registry"])
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_request_objects_are_closed_with_all_fields_required(request_context, where, mutation):
    data = request_context.to_dict()
    target = {
        "root": data,
        "source": data["source"],
        "criteria": data["criteria"],
        "assumption": data["assumptions"][0],
        "registry": data["registry"],
    }[where]
    if mutation == "missing":
        target.pop(next(iter(target)))
    else:
        target["execution_status"] = None
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation_request(canonical(data))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "1.1"),
        (("schema_version",), 1),
        (("kind",), "caller-policy"),
        (("scenario_id",), "other-scenario"),
        (("source",), []),
        (("source", "path"), "../policy.py"),
        (("source", "sha256"), "0" * 64),
        (("source", "evidence_id"), "unknown"),
        (("source", "text"), "x" * 32769),
        (("criteria", "text"), CRITERIA + "\n"),
        (("criteria", "sha256"), None),
        (("criteria", "evidence_id"), True),
        (("assumptions",), []),
        (("assumptions", 0, "id"), "changed"),
        (("assumptions", 0, "text"), "Changed trust assumption."),
        (("registry", "version"), "empty-v2"),
        (("registry", "pairs"), None),
        (("registry", "pairs"), ["invented-pair"]),
    ],
    ids=[
        "version",
        "numeric-version",
        "kind",
        "scenario",
        "source-type",
        "path",
        "source-hash",
        "source-evidence",
        "source-budget",
        "criteria-newline",
        "criteria-hash",
        "criteria-evidence",
        "no-assumptions",
        "assumption-id",
        "assumption-text",
        "registry-version",
        "registry-type",
        "registry-not-empty",
    ],
)
def test_unregistered_request_changes_are_rejected(request_context, path, value):
    data = request_context.to_dict()
    replace(data, path, value)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation_request(canonical(data))


@pytest.mark.parametrize("field", ["source", "criteria"])
def test_matching_rehashed_modified_text_still_is_not_the_registered_request(
    request_context, field
):
    data = request_context.to_dict()
    part = data[field]
    part["text"] += "\n# Test-owned unregistered source or criteria, never executed.\n"
    part["sha256"] = sha256(part["text"].encode("utf-8")).hexdigest()
    part["evidence_id"] = (
        "owner-recommendation-"
        + field
        + "-"
        + identity({key: value for key, value in part.items() if key != "evidence_id"})
    )
    assert "owner-recommendation-request-" + identity(data) != request_context.request_id
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation_request(canonical(data))


@pytest.mark.parametrize("field", ["source", "criteria", "assumptions", "registry"])
def test_forged_request_wrapper_is_revalidated_before_result_or_preview(request_context, field):
    data = request_context.to_dict()
    if field in {"source", "criteria"}:
        data[field]["text"] += "\n"
    elif field == "assumptions":
        data[field].reverse()
    else:
        data[field]["version"] = "invented"
    raw = canonical(data)
    recommendation = validate(draft(request_context), request_context)
    with pytest.raises(ContractError):
        forged = contract.OwnerPolicyRecommendationRequest(raw)
        contract.validate_owner_policy_recommendation(canonical(draft(request_context)), forged)
    with pytest.raises(ContractError):
        forged = contract.OwnerPolicyRecommendationRequest(raw)
        contract.prepare_owner_policy_recommendation_preview(recommendation, forged)


@pytest.mark.parametrize(
    "change", ["source-newline", "criteria-newline", "assumptions", "schema", "registry"]
)
def test_changed_registration_makes_preexisting_requests_and_recommendations_stale(
    request_context, monkeypatch, change
):
    # Simulate a maintained registration update in memory, not a public input option.
    raw = draft(request_context)
    recommendation = validate(raw, request_context)
    if change == "source-newline":
        monkeypatch.setattr(contract, "OWNER_POLICY_SOURCE", OWNER_POLICY_SOURCE + "\n")
    elif change == "criteria-newline":
        monkeypatch.setattr(contract, "OWNER_POLICY_RECOMMENDATION_CRITERIA", CRITERIA + "\n")
    elif change == "assumptions":
        updated = tuple(
            (item["id"], item["text"] + " Changed registration.") for item in ASSUMPTIONS
        )
        monkeypatch.setattr(contract, "_ASSUMPTIONS", updated)
    elif change == "schema":
        monkeypatch.setattr(contract, "OWNER_POLICY_RECOMMENDATION_SCHEMA_VERSION", "1.1")
    else:
        registered = contract._registered_payload

        def changed_registry():
            payload = registered()
            payload["registry"]["version"] = "empty-v2"
            return payload

        monkeypatch.setattr(contract, "_registered_payload", changed_registry)
    current = contract.build_owner_policy_recommendation_request()
    assert current.request_id != request_context.request_id
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation_request(request_context.payload_json)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation(canonical(raw), request_context)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation(canonical(raw), current)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_recommendation_preview(recommendation, request_context)


@pytest.mark.parametrize("value", ["stale-request", "", 0, False, None])
def test_result_requires_exact_current_request_identity(request_context, value):
    data = draft(request_context)
    data["request_id"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("value", ["recommend", "confirmed", "passed", "fixed", "", True, 0, None])
def test_result_status_is_a_closed_two_value_choice(request_context, value):
    data = draft(request_context)
    data["status"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("value", ["registered-looking-v1", "", [], {}, 0, False, True])
def test_every_non_null_change_pair_id_is_rejected(request_context, value):
    data = draft(request_context)
    data["change_pair_id"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "source-only",
        "criteria-only",
        "unknown",
        "duplicate",
        "text",
        "null",
        "integer",
        "oversize-id",
    ],
)
def test_evidence_is_exactly_both_distinct_registered_ids(request_context, mutation):
    data = draft(request_context)
    refs = data["evidence_ids"]
    data["evidence_ids"] = {
        "none": [],
        "source-only": refs[:1],
        "criteria-only": refs[1:],
        "unknown": [refs[0], "unregistered-evidence"],
        "duplicate": [refs[0], refs[0]],
        "text": refs[0],
        "null": None,
        "integer": [refs[0], 1],
        "oversize-id": [refs[0], "x" * 129],
    }[mutation]
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_evidence_order_is_not_approval_and_preserved_as_data(request_context):
    data = draft(request_context)
    data["evidence_ids"].reverse()
    assert validate(data, request_context).to_dict() == data


@pytest.mark.parametrize("field", TEXT_LISTS)
@pytest.mark.parametrize(
    "value",
    [None, "not-a-list", [None], [True], [0], [""], ["x" * 4097], ["item"] * 33],
    ids=[
        "null",
        "text",
        "null-item",
        "boolean-item",
        "integer-item",
        "blank-item",
        "long-item",
        "too-many",
    ],
)
def test_text_lists_are_strict_bounded_lists_of_nonblank_text(request_context, field, value):
    data = draft(request_context)
    data[field] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", ["assumptions", "expected_effects", "limitations"])
@pytest.mark.parametrize("status", ["no-change", "unknown"])
def test_required_text_lists_cannot_be_empty(request_context, field, status):
    data = draft(request_context, status)
    data[field] = []
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_unknown_requires_uncertainty_but_no_change_does_not(request_context):
    data = draft(request_context, "unknown")
    data["uncertainties"] = []
    with pytest.raises(ContractError):
        validate(data, request_context)
    data["status"] = "no-change"
    assert validate(data, request_context).to_dict()["uncertainties"] == []


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "replacement_source",
        "after_text",
        "changes",
        "diff",
        "diffs",
        "patch",
        "patches",
        "command",
        "commands",
        "tests",
        "cases",
        "labels",
        "observations",
        "provider",
        "model",
        "identity",
        "approval",
        "decision",
        "execution_status",
        "patch_application",
        "restoration_status",
        "authorization_status",
        "provenance",
    ],
)
@pytest.mark.parametrize(
    "value", [None, "", [], {}], ids=["null", "empty-text", "empty-list", "empty-object"]
)
def test_forbidden_extras_are_rejected_even_when_empty(request_context, field, value):
    data = draft(request_context)
    data[field] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", ["rationale", "request_id", "schema_version"])
@pytest.mark.parametrize("value", [None, False, 1, [], {}])
def test_scalar_types_are_never_coerced(request_context, field, value):
    data = draft(request_context)
    data[field] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize(
    "value",
    ["", " ", "\t\r\n", "\u0085\u00a0\u3000", "a" * 4097, "text\x00", "text\x1b[31m", "text\x1f"],
)
def test_blank_oversized_and_disallowed_control_text_is_rejected(request_context, value):
    data = draft(request_context)
    data["rationale"] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize(
    "value",
    ["\tTest-owned\n\rtext", "\U0001f600" * 4096, "Inert bidi \u202e and zero-width \u200b text."],
    ids=["permitted-c0", "non-bmp-exact-character-limit", "inert-format-controls"],
)
def test_allowed_text_controls_non_bmp_and_exact_character_limit_are_preserved(
    request_context, value
):
    data = draft(request_context)
    data["rationale"] = value
    result = preview(data, request_context).to_dict()
    assert result["recommendation"]["rationale"] == value
    assert (
        result["execution_status"] == "not-run" and result["provenance"]["authenticated"] is False
    )


def test_instruction_or_code_like_text_stays_inert_bounded_scripted_data(request_context):
    data = draft(request_context)
    text = "$(never-run)\n__import__('os').system('never-run')\n```python\npass\n```"
    data["rationale"] = text
    for field in TEXT_LISTS:
        data[field] = [text]
    result = preview(data, request_context).to_dict()
    assert result["recommendation"] == data
    assert result["changes"] == result["diffs"] == [] and result["provider_calls"] == 0


@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"], ids=["high", "low"])
def test_json_escaped_lone_surrogates_are_rejected_after_decoding(request_context, surrogate):
    data = draft(request_context)
    data["rationale"] = "invalid" + surrogate
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation(
            json.dumps(data, ensure_ascii=True), request_context
        )


@pytest.mark.parametrize("field", ["status", "rationale", "evidence_ids", "uncertainties"])
def test_every_result_change_changes_identity_and_forged_snapshot_is_revalidated(
    request_context, field
):
    raw = draft(request_context)
    original = validate(raw, request_context)
    if field == "status":
        raw.update(status="unknown", uncertainties=["Unverified input trust."])
    elif field == "rationale":
        raw[field] += " Another test-owned explanation."
    elif field == "evidence_ids":
        raw[field].reverse()
    else:
        raw[field].append("Another bounded test-owned uncertainty.")
    assert validate(raw, request_context).recommendation_id != original.recommendation_id
    raw["execution_status"] = "completed"
    with pytest.raises(ContractError):
        forged = contract.OwnerPolicyRecommendation(canonical(raw))
        contract.prepare_owner_policy_recommendation_preview(forged, request_context)


@pytest.mark.parametrize("value", ["{}", None, {}, []])
def test_untyped_requests_and_results_never_grant_preview_authority(request_context, value):
    recommendation = validate(draft(request_context), request_context)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_recommendation(canonical(draft(request_context)), value)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_recommendation_preview(value, request_context)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_recommendation_preview(recommendation, value)


@pytest.mark.parametrize(
    ("raw", "expected_code"),
    [
        ("[]", "validation-shape"),
        ("null", "validation-shape"),
        ("true", "validation-shape"),
        ("0", "validation-shape"),
        ('"text"', "validation-shape"),
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
        "bool",
        "number",
        "string",
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
def test_invalid_json_and_global_structural_budgets_apply_to_both_artifacts(
    request_context, raw, expected_code
):
    for call in (
        lambda: contract.validate_owner_policy_recommendation_request(raw),
        lambda: contract.validate_owner_policy_recommendation(raw, request_context),
    ):
        with pytest.raises(ContractError) as caught:
            call()
        # A schema-shape rejection must not mask a missing global budget check.
        assert contract_failure_code(caught.value) == expected_code


def test_utf8_budget_is_distinct_from_character_limits(request_context):
    data = draft(request_context)
    for field in TEXT_LISTS:
        data[field] = ["\U0001f600" * 4096] * 15
    raw = canonical(data)
    assert len(raw) < MAX_JSON_BYTES < len(raw.encode("utf-8"))
    with pytest.raises(ContractError) as caught:
        contract.validate_owner_policy_recommendation(raw, request_context)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_raw_result_at_byte_budget_is_valid_but_host_preview_growth_is_bounded(request_context):
    data = sized_draft(request_context, MAX_JSON_BYTES)
    recommendation = validate(data, request_context)
    assert len(recommendation.payload_json.encode("utf-8")) == MAX_JSON_BYTES
    with pytest.raises(ContractError) as caught:
        contract.prepare_owner_policy_recommendation_preview(recommendation, request_context)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_completed_preview_exact_byte_boundary_and_one_byte_over(request_context):
    baseline = validate(draft(request_context), request_context)
    small_preview = contract.prepare_owner_policy_recommendation_preview(baseline, request_context)
    overhead = len(small_preview.payload_json.encode("utf-8")) - len(
        baseline.payload_json.encode("utf-8")
    )
    assert overhead > 0
    exact = validate(sized_draft(request_context, MAX_JSON_BYTES - overhead), request_context)
    result = contract.prepare_owner_policy_recommendation_preview(exact, request_context)
    assert len(result.payload_json.encode("utf-8")) == MAX_JSON_BYTES
    above = validate(sized_draft(request_context, MAX_JSON_BYTES - overhead + 1), request_context)
    with pytest.raises(ContractError) as caught:
        contract.prepare_owner_policy_recommendation_preview(above, request_context)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_exact_text_list_bounds_remain_valid_when_total_budget_allows_them(request_context):
    data = draft(request_context)
    for field in TEXT_LISTS:
        data[field] = ["bounded item"] * 32
    assert validate(data, request_context).to_dict() == data


def test_failure_diagnostics_are_closed_and_do_not_echo_source_or_payload(request_context):
    sentinel = "DO-NOT-ECHO-TEST-SENTINEL-81"
    raw = draft(request_context)
    raw["forbidden_source"] = sentinel + OWNER_POLICY_SOURCE
    request = request_context.to_dict()
    request["source"]["text"] = sentinel + OWNER_POLICY_SOURCE
    for call in (
        lambda: contract.validate_owner_policy_recommendation_request(canonical(request)),
        lambda: contract.validate_owner_policy_recommendation(canonical(raw), request_context),
    ):
        with pytest.raises(ContractError) as caught:
            call()
        assert caught.value.code in VALIDATION_CODES
        assert contract_failure_code(caught.value) in VALIDATION_CODES
        assert sentinel not in str(caught.value) and OWNER_POLICY_SOURCE not in str(caught.value)
