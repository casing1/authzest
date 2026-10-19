"""Guarded offline registry contracts, not policy execution or new approval evidence."""

import asyncio
import builtins
import copy
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex import contracts as shared
from authzest.codex import owner_policy_recommendation as s1
from authzest.codex import owner_policy_repair_pair as contract
from authzest.codex.contracts import ContractError, canonical, contract_failure_code, identity
from authzest.codex.diagnostics import VALIDATION_CODES
from authzest.codex.owner_policy_review import OWNER_POLICY_SOURCE

WARNING = "# INTENTIONALLY INCORRECT TEST-ONLY: ownership comparison deliberately omitted.\n"
CORRECT_LINE = '    return subject == owner_id and "reports:read" in scopes\n'
INCORRECT_LINE = '    return "reports:read" in scopes\n'
BEFORE_SHA256 = "54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950"
AFTER_SHA256 = "faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04"
CASES_SHA256 = "96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3"
DESIGN_HEAD = "35ebe17d96c07540cf2753f2e53625d138ded0aa"
RECORD_URL = "https://github.com/casing1/authzest/pull/100#issuecomment-6258235318"
GOLDEN_DIFF = (
    "--- a/policy.py\n+++ b/policy.py\n@@ -1,4 +1,3 @@\n"
    "-"
    + WARNING
    + ' """Pure policy for a maintained synthetic example, not an authentication provider.\n'
    + " \n"
    + " The caller must supply an already trusted principal and report ownership context.\n"
    + "@@ -51,4 +50,4 @@\n"
    + "         return False\n"
    + "     if not all(_nonblank_string(scope) for scope in scopes):\n"
    + "         return False\n"
    + "-"
    + INCORRECT_LINE
    + "+"
    + CORRECT_LINE
)


def approved_cases():
    """Mirror the reviewed data; do not evaluate or adjust labels to match a candidate."""
    principal = {"subject": "alice", "authenticated": True, "scopes": ["reports:read"]}
    report = {"report_id": "report-001", "owner_id": "alice"}
    names = [
        "owner-control",
        "non-owner",
        "missing-read-scope",
        "unauthenticated-owner",
        "missing-principal",
        "missing-report",
        "wildcard-is-not-read",
        "exact-owner-no-normalization",
    ]
    cases = [
        {
            "case_id": name,
            "principal": copy.deepcopy(principal),
            "report": dict(report),
            "expected": "allow" if index == 0 else "deny",
        }
        for index, name in enumerate(names)
    ]
    cases[1]["principal"]["subject"] = "bob"
    cases[2]["principal"]["scopes"] = []
    cases[3]["principal"]["authenticated"] = False
    cases[4]["principal"] = None
    cases[5]["report"] = None
    cases[6]["principal"]["scopes"] = ["reports:*"]
    cases[7]["principal"]["subject"] = " alice"
    return cases


@pytest.fixture(autouse=True)
def forbid_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Repair-pair contracts must not use I/O, providers, processes or evaluation")

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
def pair():
    return contract.build_owner_policy_repair_pair()


def rebind(data):
    """Rehash forged data without making it registered or approved."""
    content = data["content"]
    for field in ("before", "after", "criteria"):
        content[field]["sha256"] = sha256(content[field]["text"].encode("utf-8")).hexdigest()
    content["cases_sha256"] = identity(content["cases"])
    binding = data["review_binding"]
    binding["content_sha256"] = identity(content)
    binding["review_record"]["content_sha256"] = binding["content_sha256"]
    binding["review_record"]["cases_sha256"] = content["cases_sha256"]
    binding["review_record_sha256"] = identity(binding["review_record"])
    return data


def replace(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


def test_exact_registered_pair_and_content_addressed_review_binding(pair):
    data = pair.to_dict()
    assert set(data) == {"schema_version", "kind", "registry_version", "content", "review_binding"}
    assert data["schema_version"] == "1.0" and data["kind"] == "owner-policy-repair-pair"
    assert data["registry_version"] == "owned-synthetic-v1"
    source = s1.build_owner_policy_recommendation_request().to_dict()
    assert OWNER_POLICY_SOURCE.count(CORRECT_LINE) == 1
    before = WARNING + OWNER_POLICY_SOURCE.replace(CORRECT_LINE, INCORRECT_LINE, 1)
    content = data["content"]
    assert content == {
        "version": "test-only-v1",
        "scenario_id": "synthetic-owner-omission-v1",
        "path": "policy.py",
        "before": {"text": before, "sha256": BEFORE_SHA256},
        "after": {"text": OWNER_POLICY_SOURCE, "sha256": AFTER_SHA256},
        "criteria": {"text": source["criteria"]["text"], "sha256": source["criteria"]["sha256"]},
        "assumptions": source["assumptions"],
        "cases": approved_cases(),
        "cases_sha256": CASES_SHA256,
    }
    assert len(before.encode("utf-8")) == 2016
    assert len(OWNER_POLICY_SOURCE.encode("utf-8")) == 1960
    for field in ("before", "after", "criteria"):
        assert (
            sha256(content[field]["text"].encode("utf-8")).hexdigest() == content[field]["sha256"]
        )
    assert identity(approved_cases()) == content["cases_sha256"] == CASES_SHA256
    record = {
        "schema_version": "1.0",
        "kind": "recorded-owner-policy-pair-review",
        "design_head": DESIGN_HEAD,
        "decision_date": "2026-10-19",
        "decision": "accept-scenario-and-case-expectations",
        "content_sha256": identity(content),
        "cases_sha256": CASES_SHA256,
        "record_url": RECORD_URL,
        "provenance": {"kind": "recorded-maintainer-chat", "authenticated": False},
    }
    assert data["review_binding"] == {
        "content_sha256": identity(content),
        "review_record_sha256": identity(record),
        "review_record": record,
    }
    assert identity(content) == "2cbbc004b46ac2bc65b98c3e3b4b3e1e5919dd3d1b35920871372432c23203fb"
    assert identity(record) == "3540dd3578ee838b1bfb34f3c02019286716b47664ec942da46e8dac25d4b7e8"
    assert pair.pair_id == "owner-repair-pair-" + identity(data)
    assert pair.pair_id == (
        "owner-repair-pair-a4f764f8cbff25089bd40076c5f4a5cc76775312c973e3e22e9b9f353038ba08"
    )
    assert contract.validate_owner_policy_repair_pair(json.dumps(data, indent=2)) == pair
    assert contract.build_owner_policy_repair_pair() == pair


def test_complete_host_diff_is_exact_and_preview_is_non_authority(pair):
    result = contract.prepare_owner_policy_repair_pair_preview(pair)
    assert result.to_dict() == {
        "schema_version": "1.0",
        "kind": "owner-policy-repair-pair-preview",
        "pair_id": pair.pair_id,
        "pair": pair.to_dict(),
        "recipe_version": "unified-v1-context-3",
        "diff": GOLDEN_DIFF,
        "diff_sha256": sha256(GOLDEN_DIFF.encode("utf-8")).hexdigest(),
        "provider_calls": 0,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
        "comparison_status": "not-evaluated",
        "observations": {"before": None, "after": None},
        "provenance": {"kind": "registered-test-only-template", "authenticated": False},
    }
    assert type(result.to_dict()["provider_calls"]) is int
    assert result.to_dict()["provenance"]["authenticated"] is False
    assert len(GOLDEN_DIFF.encode("utf-8")) == 520
    assert result.to_dict()["diff_sha256"] == (
        "0358127d2373c7a729c0b656c1c9cbcb698dc5f04073a917f848280d0c8be75d"
    )


def test_eight_reviewed_labels_remain_criteria_not_observations(pair):
    cases = pair.to_dict()["content"]["cases"]
    assert len(cases) == 8 and sum(case["expected"] == "allow" for case in cases) == 1
    assert all(case["expected"] == "deny" for case in cases[1:])
    assert cases[7]["principal"]["subject"] == " alice"
    assert cases[7]["report"]["owner_id"] == "alice"
    assert cases[4]["principal"] is None and cases[5]["report"] is None
    assert all(set(case) == {"case_id", "principal", "report", "expected"} for case in cases)


def test_snapshots_are_frozen_slotted_detached_and_not_execution_inputs(pair):
    preview = contract.prepare_owner_policy_repair_pair_preview(pair)
    for snapshot in (pair, preview):
        assert not hasattr(snapshot, "__dict__")
        with pytest.raises(FrozenInstanceError):
            snapshot.payload_json = "{}"
        snapshot.to_dict().clear()
        assert snapshot.to_dict()
    detached = preview.to_dict()
    detached["pair"]["content"]["cases"][0]["expected"] = "deny"
    detached["observations"]["before"] = True
    assert pair.to_dict()["content"]["cases"][0]["expected"] == "allow"
    assert preview.to_dict()["observations"]["before"] is None
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_repair_pair_preview(preview)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(preview.payload_json)


@pytest.mark.parametrize(
    "option",
    [
        "path",
        "source",
        "before",
        "after",
        "cases",
        "labels",
        "registry",
        "review_record",
        "provider",
        "model",
    ],
)
def test_builder_accepts_no_caller_source_registry_or_approval_option(option):
    with pytest.raises(TypeError):
        contract.build_owner_policy_repair_pair(**{option: None})


OBJECT_PATHS = [
    (),
    ("content",),
    ("content", "before"),
    ("content", "after"),
    ("content", "criteria"),
    ("content", "assumptions", 0),
    ("content", "cases", 0),
    ("content", "cases", 0, "principal"),
    ("content", "cases", 0, "report"),
    ("review_binding",),
    ("review_binding", "review_record"),
    ("review_binding", "review_record", "provenance"),
]


@pytest.mark.parametrize("path", OBJECT_PATHS)
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_every_object_is_closed_and_all_fields_required(pair, path, mutation):
    data = pair.to_dict()
    target = data
    for part in path:
        target = target[part]
    if mutation == "missing":
        target.pop(next(iter(target)))
    else:
        target["command"] = None
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))


@pytest.mark.parametrize("path", OBJECT_PATHS[1:])
@pytest.mark.parametrize("value", [None, [], "object", True, 0])
def test_nested_objects_are_exact_objects_without_type_coercion(pair, path, value):
    data = pair.to_dict()
    replace(data, path, value)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "2.0"),
        (("schema_version",), 1),
        (("kind",), "owner-policy-recommendation-request"),
        (("registry_version",), "empty-v1"),
        (("content", "version"), "test-only-v2"),
        (("content", "scenario_id"), "other-scenario"),
        (("content", "path"), "../policy.py"),
        (("content", "path"), "/policy.py"),
        (("content", "path"), "C:/policy.py"),
        (("content", "path"), "policy.py\n"),
        (("content", "before", "sha256"), "0" * 64),
        (("content", "after", "sha256"), None),
        (("content", "criteria", "sha256"), True),
        (("content", "cases_sha256"), "0" * 64),
        (("content", "assumptions"), []),
        (("content", "assumptions", 0, "id"), "other-trust"),
        (("content", "assumptions", 0, "text"), "Changed assumption."),
        (("content", "cases", 0, "case_id"), "owner-control\n"),
        (("content", "cases", 0, "principal", "authenticated"), 1),
        (("content", "cases", 0, "principal", "scopes"), "reports:read"),
        (("content", "cases", 0, "report", "report_id"), None),
        (("review_binding", "content_sha256"), "0" * 64),
        (("review_binding", "review_record_sha256"), "0" * 64),
        (("review_binding", "review_record", "design_head"), "0" * 40),
        (("review_binding", "review_record", "decision_date"), "2026-10-18"),
        (("review_binding", "review_record", "decision"), "execute-and-apply"),
        (("review_binding", "review_record", "record_url"), "https://example.com/forged"),
        (("review_binding", "review_record", "content_sha256"), "0" * 64),
        (("review_binding", "review_record", "cases_sha256"), "0" * 64),
        (("review_binding", "review_record", "provenance", "kind"), "authenticated-approval"),
        (("review_binding", "review_record", "provenance", "authenticated"), True),
        (("review_binding", "review_record", "provenance", "authenticated"), 0),
    ],
)
def test_changed_values_or_bindings_are_rejected(pair, path, value):
    data = pair.to_dict()
    replace(data, path, value)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))


@pytest.mark.parametrize("field", ["before", "after"])
@pytest.mark.parametrize("change", ["crlf", "bom", "no-final-lf", "extra-comment", "no-warning"])
def test_source_bytes_are_exact_without_normalization_even_when_rehashed(pair, field, change):
    data = pair.to_dict()
    text = data["content"][field]["text"]
    if change == "crlf":
        text = text.replace("\n", "\r\n")
    elif change == "bom":
        text = "\ufeff" + text
    elif change == "no-final-lf":
        text = text[:-1]
    elif change == "extra-comment":
        text += "# Different unregistered source.\n"
    else:
        text = text.removeprefix(WARNING) if field == "before" else WARNING + text
    data["content"][field]["text"] = text
    rebind(data)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "order",
        "label",
        "boolean-label",
        "unknown-label",
        "normalized-subject",
        "scope",
        "criteria",
        "assumption-order",
        "swapped-source",
        "record",
    ],
)
def test_rehashing_forged_content_or_review_never_registers_it(pair, mutation):
    data = pair.to_dict()
    content = data["content"]
    cases = content["cases"]
    if mutation == "missing":
        cases.pop()
    elif mutation == "duplicate":
        cases[1] = copy.deepcopy(cases[0])
    elif mutation == "order":
        cases.reverse()
    elif mutation == "label":
        cases[1]["expected"] = "allow"
    elif mutation == "boolean-label":
        cases[1]["expected"] = False
    elif mutation == "unknown-label":
        cases[1]["expected"] = "unknown"
    elif mutation == "normalized-subject":
        cases[7]["principal"]["subject"] = "alice"
    elif mutation == "scope":
        cases[1]["principal"]["scopes"] = ["reports:*"]
    elif mutation == "criteria":
        content["criteria"]["text"] += "\n"
    elif mutation == "assumption-order":
        content["assumptions"].reverse()
    elif mutation == "swapped-source":
        content["before"], content["after"] = content["after"], content["before"]
    else:
        data["review_binding"]["review_record"]["record_url"] = "https://example.com/forged"
    rebind(data)
    assert "owner-repair-pair-" + identity(data) != pair.pair_id
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))
    with pytest.raises(ContractError):
        forged = contract.OwnerPolicyRepairPair(canonical(data))
        contract.prepare_owner_policy_repair_pair_preview(forged)


@pytest.mark.parametrize(
    "change",
    ["registry", "schema", "s1-source", "s1-criteria", "case-label", "content-hash", "review-hash"],
)
def test_current_registration_is_rebuilt_and_old_artifacts_cannot_bypass_changes(
    pair, monkeypatch, change
):
    if change == "registry":
        monkeypatch.setattr(contract, "REPAIR_PAIR_REGISTRY_VERSION", "owned-synthetic-v2")
    elif change == "schema":
        monkeypatch.setattr(contract, "REPAIR_PAIR_SCHEMA_VERSION", "1.1")
    elif change == "s1-source":
        monkeypatch.setattr(s1, "OWNER_POLICY_SOURCE", OWNER_POLICY_SOURCE + "\n")
    elif change == "s1-criteria":
        monkeypatch.setattr(
            s1,
            "OWNER_POLICY_RECOMMENDATION_CRITERIA",
            s1.OWNER_POLICY_RECOMMENDATION_CRITERIA + "\n",
        )
    elif change == "case-label":
        envelope = json.loads(contract._CASE_ENVELOPE)
        envelope["cases"][1]["expected"] = "allow"
        monkeypatch.setattr(contract, "_CASE_ENVELOPE", canonical(envelope))
    else:
        constant = "_CONTENT_SHA256" if change == "content-hash" else "_REVIEW_RECORD_SHA256"
        monkeypatch.setattr(contract, constant, "0" * 64)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(pair.payload_json)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_repair_pair_preview(pair)


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "after_text",
        "replacement_source",
        "changes",
        "diff",
        "diffs",
        "patch",
        "command",
        "commands",
        "tests",
        "provider",
        "model",
        "approval",
        "execution_status",
        "observations",
    ],
)
@pytest.mark.parametrize(
    "value", [None, "", [], {}], ids=["null", "empty-text", "empty-list", "empty-object"]
)
def test_external_source_diff_command_and_authority_fields_are_forbidden(pair, field, value):
    data = pair.to_dict()
    data[field] = value
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))


@pytest.mark.parametrize("value", [None, {}, [], "{}", True])
def test_preview_requires_exact_typed_pair_and_revalidates_its_payload(pair, value):
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_repair_pair_preview(value)
    with pytest.raises(ContractError):
        forged = contract.OwnerPolicyRepairPair(value)
        contract.prepare_owner_policy_repair_pair_preview(forged)


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("[]", "validation-shape"),
        ("null", "validation-shape"),
        ("true", "validation-shape"),
        ("{bad", "validation-json"),
        ('{"x":0,"x":1}', "validation-duplicate"),
        ('{"x":NaN}', "validation-json"),
        ('{"x":1e999}', "validation-json"),
        (" " * (shared.MAX_JSON_BYTES + 1), "validation-budget"),
        ('{"x":' + "[" * 33 + "0" + "]" * 33 + "}", "validation-budget"),
        (canonical({"x": ["a"] * 8193}), "validation-budget"),
    ],
    ids=[
        "array",
        "null",
        "bool",
        "syntax",
        "duplicate",
        "nan",
        "overflow",
        "bytes",
        "depth",
        "nodes",
    ],
)
def test_shared_json_and_structure_limits_apply_before_registration_checks(raw, code):
    with pytest.raises(ContractError) as caught:
        contract.validate_owner_policy_repair_pair(raw)
    assert contract_failure_code(caught.value) == code


@pytest.mark.parametrize("raw", [None, 0, False, b"{}", {}, []])
def test_raw_validator_does_not_coerce_non_json_text_inputs(raw):
    with pytest.raises(ContractError) as caught:
        contract.validate_owner_policy_repair_pair(raw)
    assert contract_failure_code(caught.value) == "validation-json"


@pytest.mark.parametrize(
    "bad",
    ["\x00", "\x1b", "\ud800", "\udfff"],
    ids=["nul", "escape", "high-surrogate", "low-surrogate"],
)
def test_controls_and_invalid_unicode_are_rejected_without_echo(pair, bad):
    data = pair.to_dict()
    data["content"]["before"]["text"] = "NO-ECHO-SOURCE-81" + bad
    with pytest.raises(ContractError) as caught:
        contract.validate_owner_policy_repair_pair(json.dumps(data, ensure_ascii=True))
    assert "NO-ECHO-SOURCE-81" not in str(caught.value)


@pytest.mark.parametrize("field", ["before", "after", "criteria"])
def test_oversized_registered_text_fields_are_rejected_without_evaluation(pair, field):
    data = pair.to_dict()
    data["content"][field]["text"] = "x" * (32769 if field != "criteria" else 4097)
    with pytest.raises(ContractError):
        contract.validate_owner_policy_repair_pair(canonical(data))


def test_utf8_total_bytes_are_bounded_even_when_source_character_limits_are_not_exceeded(pair):
    data = pair.to_dict()
    data["content"]["before"]["text"] = "\U0001f600" * 32768
    data["content"]["after"]["text"] = "\U0001f600" * 32768
    raw = canonical(data)
    assert len(raw) < shared.MAX_JSON_BYTES < len(raw.encode("utf-8"))
    with pytest.raises(ContractError) as caught:
        contract.validate_owner_policy_repair_pair(raw)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_completed_preview_budget_includes_diff_and_host_metadata(pair, monkeypatch):
    result = contract.prepare_owner_policy_repair_pair_preview(pair)
    pair_size = len(pair.payload_json.encode("utf-8"))
    preview_size = len(result.payload_json.encode("utf-8"))
    assert pair_size < preview_size < shared.MAX_JSON_BYTES
    # A reduced shared limit probes fixed-artifact boundaries without registering
    # another source pair or adding unreviewed free-form text fields to this API.
    monkeypatch.setattr(shared, "MAX_JSON_BYTES", preview_size)
    assert contract.prepare_owner_policy_repair_pair_preview(pair) == result
    monkeypatch.setattr(shared, "MAX_JSON_BYTES", preview_size - 1)
    assert contract.validate_owner_policy_repair_pair(pair.payload_json) == pair
    with pytest.raises(ContractError) as caught:
        contract.prepare_owner_policy_repair_pair_preview(pair)
    assert contract_failure_code(caught.value) == "validation-budget"


def test_registered_pair_snapshot_is_subject_to_the_shared_byte_budget(pair, monkeypatch):
    size = len(pair.payload_json.encode("utf-8"))
    monkeypatch.setattr(shared, "MAX_JSON_BYTES", size)
    assert contract.build_owner_policy_repair_pair() == pair
    monkeypatch.setattr(shared, "MAX_JSON_BYTES", size - 1)
    with pytest.raises(ContractError) as caught:
        contract.build_owner_policy_repair_pair()
    assert contract_failure_code(caught.value) == "validation-budget"


def test_original_correct_source_and_s1_acceptance_remain_unchanged(pair):
    request = s1.build_owner_policy_recommendation_request()
    before = request.payload_json
    s1_data = request.to_dict()
    assert request.request_id == (
        "owner-recommendation-request-56213e7526d3e3d483a342695027761bed08251e70701cbccf010e80d830a8e4"
    )
    assert s1_data["registry"] == {"version": "empty-v1", "pairs": []}
    assert (
        s1_data["source"]["text"]
        == OWNER_POLICY_SOURCE
        == pair.to_dict()["content"]["after"]["text"]
    )
    for status in ("no-change", "unknown"):
        raw = {
            "schema_version": "1.0",
            "request_id": request.request_id,
            "status": status,
            "rationale": "Test-owned structural result, not model or approval evidence.",
            "evidence_ids": [s1_data["source"]["evidence_id"], s1_data["criteria"]["evidence_id"]],
            "assumptions": ["Trusted inputs are assumed, not authenticated."],
            "uncertainties": ["Endpoint enforcement is unknown."],
            "expected_effects": ["No source is changed."],
            "limitations": ["No policy was run."],
            "change_pair_id": None,
        }
        assert s1.validate_owner_policy_recommendation(canonical(raw), request).to_dict() == raw
        raw["change_pair_id"] = pair.pair_id
        with pytest.raises(ContractError):
            s1.validate_owner_policy_recommendation(canonical(raw), request)
    contract.prepare_owner_policy_repair_pair_preview(pair)
    assert s1.build_owner_policy_recommendation_request().payload_json == before


def test_rejection_codes_do_not_echo_unregistered_source_or_record_data(pair):
    sentinel = "NO-ECHO-PAIR-SENTINEL-81"
    data = pair.to_dict()
    data["content"]["after"]["text"] = sentinel + OWNER_POLICY_SOURCE
    for raw in (canonical(data), canonical({"commands": sentinel})):
        with pytest.raises(ContractError) as caught:
            contract.validate_owner_policy_repair_pair(raw)
        assert caught.value.code in VALIDATION_CODES
        assert sentinel not in str(caught.value) and OWNER_POLICY_SOURCE not in str(caught.value)
