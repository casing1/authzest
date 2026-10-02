"""Offline exact-data contracts; test-owned choices are NOT maintainer approval."""

import asyncio
import builtins
import copy
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex import owner_case_plan as contract
from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical, decode, identity
from authzest.codex.mock import scripted_response
from authzest.codex.owner_policy_review import (
    OWNER_POLICY_SOURCE,
    OwnerPolicyReview,
    build_owner_policy_request,
    validate_owner_policy_draft,
)

REFERENCE = Path(__file__).parent / "fixtures/owner_case_review/proposed_review.json"
EXPECTED_DIGEST = "7d6296c07ec57b57b217a6fc03bd6fa48304cfe475c1adaf9dbd1d9b285ea598"


@pytest.fixture
def context(monkeypatch):
    # Read only the preserved public fixture before blocking contract side effects.
    original = json.loads(REFERENCE.read_text(encoding="utf-8"))
    request = build_owner_policy_request(original["origin"]["identity"]["model"])
    answers = decode(scripted_response(request, {"review": None}))["answers"]
    for answer in answers:
        answer["evidence_ids"] = [item["id"] for item in request.to_dict()["evidence"]]
    draft = validate_owner_policy_draft(
        canonical({"answers": answers, "cases": original["cases"]}), request, usage=None
    )  # The answer is scripted; only the ten case inputs retain recorded model provenance.

    def forbidden(*args, **kwargs):
        pytest.fail("Offline review/plan contracts must not perform I/O, import or execute targets")

    original_import = builtins.__import__

    def imports(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    case_set = contract.prepare_owner_case_set(
        draft, request, origin={key: original["origin"][key] for key in ("code_head", "date")}
    )
    return original, request, draft, case_set


def decisions(case_set, state="approved"):
    return {
        case["id"]: {
            "decision": state,
            "expected": case["expected"]
            if state == "approved"
            else not case["expected"]
            if state == "changed"
            else None,
            "reason": None if state == "pending" else "Test-owned label choice; not user approval",
        }
        for case in case_set.to_dict()["cases"]
    }


def reviewed(context, state="approved"):
    _, request, draft, case_set = context
    return contract.review_owner_cases(
        case_set, draft, request, decisions=decisions(case_set, state), reviewer="offline-test"
    )


def test_exact_ten_case_reference_and_bindings_are_preserved(context):
    original, request, draft, case_set = context
    assert identity(original) == EXPECTED_DIGEST
    data = case_set.to_dict()
    assert data["cases"] == original["cases"] and len(data["cases"]) == 10
    assert data["request_id"] == original["origin"]["request_id"] == request.request_id
    for field in ("source_identity", "prompt_sha256", "output_schema_sha256"):
        assert data[field] == original["origin"][field]
    assert data["source_sha256"] == original["source_sha256"]
    assert data["model_identity"] == original["origin"]["identity"]
    assert data["draft_sha256"] == identity(draft.to_dict())
    assert data["origin"]["authenticated"] is False
    assert data["label_review_status"] == "pending"
    assert data["execution_status"] == "not-run" and data["authorization_status"] == "unknown"


@pytest.mark.parametrize("state", ["pending", "approved", "changed", "declined"])
def test_review_states_and_plan_readiness_never_claim_execution_or_security_pass(context, state):
    _, request, draft, case_set = context
    labels = reviewed(context, state)
    plan = contract.prepare_owner_policy_plan(labels, case_set, draft, request)
    data = plan.to_dict()
    assert labels.to_dict()["label_review_status"] == state
    assert labels.to_dict()["reviewer_authenticated"] is False
    assert data["planning_status"] == (
        "reviewed-preview" if state in {"approved", "changed"} else "blocked-" + state
    )
    assert (
        data["execution_available"] is False
        and data["requires_separate_execution_approval"] is True
    )
    assert data["execution_status"] == "not-run" and data["authorization_status"] == "unknown"
    assert data["provider_calls"] == 0 and data["patch_application"] == "not-run"
    assert data["policy_source"] == OWNER_POLICY_SOURCE
    assert data["source_sha256"]["policy.py"] == sha256(OWNER_POLICY_SOURCE.encode()).hexdigest()
    assert data["harness_recipe_sha256"] == identity(data["harness_recipe"])
    assert data["cases"] == case_set.to_dict()["cases"]
    assert data["label_review"]["case_authorship"] == "model-authored"
    assert (
        contract.validate_owner_case_review(labels.payload_json, case_set, draft, request) == labels
    )
    assert (
        contract.validate_owner_policy_plan(plan.payload_json, labels, case_set, draft, request)
        == plan
    )


def test_omitted_decision_stays_pending_and_changed_label_keeps_original_authorship(context):
    original, request, draft, case_set = context
    choices = decisions(case_set)
    first = original["cases"][0]
    choices.pop(first["id"])
    labels = contract.review_owner_cases(case_set, draft, request, decisions=choices)
    assert labels.to_dict()["decisions"][0] == {
        "case_id": first["id"],
        "case_sha256": identity(first),
        "decision": "pending",
        "expected": None,
        "reason": None,
    }
    assert labels.to_dict()["all_labels_reviewed"] is False
    changed = reviewed(context, "changed").to_dict()
    assert changed["decisions"][0]["expected"] is not first["expected"]
    assert case_set.to_dict()["cases"][0]["expected"] is first["expected"]


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "missing",
        "unknown",
        "approved-wrong",
        "changed-same",
        "integer",
        "pending-label",
        "declined-label",
        "pending-reason",
        "blank-reason",
        "surrogate",
        "control",
        "oversize",
        "state-type",
    ],
)
def test_invalid_review_choices_rejected_without_coercion(context, change):
    _, request, draft, case_set = context
    choices = decisions(case_set)
    key = next(iter(choices))
    choice = choices[key]
    if change == "extra":
        choice["command"] = "never execute"
    elif change == "missing":
        choice.pop("reason")
    elif change == "unknown":
        choices["not-a-case"] = choices.pop(key)
    elif change == "approved-wrong":
        choice["expected"] = not choice["expected"]
    elif change == "changed-same":
        choice["decision"] = "changed"
    elif change == "integer":
        choice["expected"] = 1
    elif change in {"pending-label", "declined-label"}:
        choice["decision"] = change.split("-")[0]
    elif change == "pending-reason":
        choice.update(decision="pending", expected=None)
    elif change == "blank-reason":
        choice["reason"] = " \t\n"
    elif change == "surrogate":
        choice["reason"] = "\ud800"
    elif change == "control":
        choice["reason"] = "\x1b[2J"
    elif change == "oversize":
        choice["reason"] = "x" * 4097
    else:
        choice["decision"] = []
    with pytest.raises(ContractError):
        contract.review_owner_cases(case_set, draft, request, decisions=choices)


@pytest.mark.parametrize(
    "field",
    [
        "request_id",
        "source_identity",
        "source_sha256",
        "model_identity",
        "cases",
        "evidence",
        "label_review_status",
        "execution_status",
        "authorization_status",
        "origin",
        "extra",
    ],
)
def test_case_set_forged_bindings_and_host_status_are_rejected(context, field):
    _, request, draft, case_set = context
    value = case_set.to_dict()
    value[field] = "forged"
    with pytest.raises(ContractError):
        contract.validate_owner_case_set(canonical(value), draft, request)


@pytest.mark.parametrize(
    "field",
    [
        "case_set_id",
        "case_authorship",
        "reviewer_authenticated",
        "label_review_status",
        "all_labels_reviewed",
        "execution_status",
        "authorization_status",
        "extra",
    ],
)
def test_review_forged_host_metadata_is_rejected(context, field):
    _, request, draft, case_set = context
    value = reviewed(context).to_dict()
    value[field] = "forged"
    with pytest.raises(ContractError):
        contract.validate_owner_case_review(canonical(value), case_set, draft, request)


@pytest.mark.parametrize(
    "change", ["duplicate", "missing", "order", "case-sha", "case-id", "extra"]
)
def test_duplicate_incomplete_or_changed_case_decisions_cannot_collapse(context, change):
    _, request, draft, case_set = context
    value = reviewed(context).to_dict()
    rows = value["decisions"]
    if change == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif change == "missing":
        rows.pop()
    elif change == "order":
        rows.reverse()
    elif change == "case-sha":
        rows[0]["case_sha256"] = "0" * 64
    elif change == "case-id":
        rows[0]["case_id"] += "x"
    else:
        rows[0]["command"] = "not allowed"
    with pytest.raises(ContractError):
        contract.validate_owner_case_review(canonical(value), case_set, draft, request)


@pytest.mark.parametrize("change", ["input", "expected", "reason", "evidence", "source", "model"])
def test_stale_data_or_labels_require_new_review(context, change):
    _, request, draft, case_set = context
    labels = reviewed(context)
    raw = draft.to_dict()
    if change == "source":
        from authzest.codex.contracts import CodexAnalysisRequest

        payload = request.to_dict()
        source = next(item for item in payload["evidence"] if item["kind"] == "source")
        source["data"]["text"] += "\n# changed\n"
        with pytest.raises(ContractError):
            other_request = CodexAnalysisRequest(canonical(payload))
            contract.prepare_owner_policy_plan(labels, case_set, draft, other_request)
        return
    if change == "model":
        other_request = build_owner_policy_request("different-offline-model")
        with pytest.raises(ContractError):
            contract.prepare_owner_policy_plan(labels, case_set, draft, other_request)
        return
    first = raw["cases"][0]
    if change == "input":
        first["principal"]["subject"] += " "
    elif change == "expected":
        first["expected"] = not first["expected"]
    elif change == "reason":
        first["reason"] += " Changed."
    else:
        first["evidence_ids"].append("ev-not-present")
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_plan(
            labels, case_set, OwnerPolicyReview(canonical(raw)), request
        )


@pytest.mark.parametrize(
    "field",
    [
        "case_set_id",
        "label_review_id",
        "request_id",
        "source_identity",
        "source_sha256",
        "policy_source",
        "policy_evidence_id",
        "cases",
        "label_review",
        "harness_recipe",
        "harness_recipe_sha256",
        "planning_status",
        "execution_available",
        "requires_separate_execution_approval",
        "execution_status",
        "authorization_status",
        "provider_calls",
        "extra",
    ],
)
def test_changed_preview_recipe_policy_cases_limits_or_status_is_rejected(context, field):
    _, request, draft, case_set = context
    labels = reviewed(context)
    plan = contract.prepare_owner_policy_plan(labels, case_set, draft, request)
    value = plan.to_dict()
    value[field] = "forged"
    with pytest.raises(ContractError):
        contract.validate_owner_policy_plan(canonical(value), labels, case_set, draft, request)


def test_json_wrappers_are_immutable_but_never_a_trust_boundary(context):
    _, request, draft, case_set = context
    with pytest.raises(FrozenInstanceError):
        case_set.payload_json = "{}"
    copy_data = case_set.to_dict()
    copy_data["cases"][0]["expected"] = False
    assert copy_data != case_set.to_dict()
    for forged in (contract.OwnerCaseSet("{}"), "not a typed artifact"):
        with pytest.raises(ContractError):
            contract.review_owner_cases(forged, draft, request, decisions={})
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_plan(
            contract.OwnerCaseLabelReview("{}"), case_set, draft, request
        )


@pytest.mark.parametrize(
    "raw",
    ['{"origin":null,"origin":null}', '{"x":NaN}', "{}", "[]", "{" + " " * MAX_JSON_BYTES + "}"],
    # Keep raw byte-budget probes out of pytest's node ID / PYTEST_CURRENT_TEST.
    # Windows cannot store a 256 KiB parameter representation in that env value.
    ids=["duplicate-keys", "nonfinite", "incomplete-object", "nonobject-array", "oversize-bytes"],
)
def test_invalid_duplicate_nonfinite_and_oversize_json(context, raw):
    _, request, draft, case_set = context
    labels = reviewed(context)
    for validate in (
        lambda: contract.validate_owner_case_set(raw, draft, request),
        lambda: contract.validate_owner_case_review(raw, case_set, draft, request),
        lambda: contract.validate_owner_policy_plan(raw, labels, case_set, draft, request),
    ):
        with pytest.raises(ContractError):
            validate()


def test_model_and_reviewer_text_remains_inert_data(context):
    _, request, draft, case_set = context
    choices = decisions(case_set)
    for choice in choices.values():
        choice["reason"] = "$(never-run)\n__import__('os').system('never-run')\u202e"
    labels = contract.review_owner_cases(
        case_set, draft, request, decisions=choices, reviewer="test-only"
    )
    plan = contract.prepare_owner_policy_plan(labels, case_set, draft, request)
    assert (
        plan.to_dict()["label_review"]["decisions"][0]["reason"]
        == next(iter(choices.values()))["reason"]
    )
    assert plan.to_dict()["execution_status"] == "not-run"


@pytest.mark.parametrize("change", ["input", "expected", "reason"])
def test_new_valid_case_set_cannot_reuse_old_label_review(context, change):
    _, request, draft, case_set = context
    labels = reviewed(context)
    raw = draft.to_dict()
    if change == "input":
        raw["cases"][0]["principal"]["subject"] += " "
    elif change == "expected":
        raw["cases"][0]["expected"] = not raw["cases"][0]["expected"]
    else:
        raw["cases"][0]["reason"] += " Changed."
    new_draft = OwnerPolicyReview(canonical(raw))
    new_set = contract.prepare_owner_case_set(new_draft, request)
    assert new_set.case_set_id != case_set.case_set_id
    with pytest.raises(ContractError):
        contract.validate_owner_case_review(labels.payload_json, new_set, new_draft, request)
    with pytest.raises(ContractError):
        contract.prepare_owner_policy_plan(labels, new_set, new_draft, request)


@pytest.mark.parametrize("change", ["label", "reason", "reviewer"])
def test_new_caller_review_invalidates_old_plan(context, change):
    _, request, draft, case_set = context
    old_labels = reviewed(context)
    old_plan = contract.prepare_owner_policy_plan(old_labels, case_set, draft, request)
    choices = decisions(case_set)
    reviewer = "offline-test"
    first = choices[next(iter(choices))]
    if change == "label":
        first.update(decision="changed", expected=not first["expected"])
    elif change == "reason":
        first["reason"] += " New review note."
    else:
        reviewer = "another-test-only-caller"
    new_labels = contract.review_owner_cases(
        case_set, draft, request, decisions=choices, reviewer=reviewer
    )
    new_plan = contract.prepare_owner_policy_plan(new_labels, case_set, draft, request)
    assert new_labels.label_review_id != old_labels.label_review_id
    assert new_plan.plan_id != old_plan.plan_id
    with pytest.raises(ContractError):
        contract.validate_owner_policy_plan(
            old_plan.payload_json, new_labels, case_set, draft, request
        )


@pytest.mark.parametrize(
    "origin",
    [
        [],
        {},
        {"code_head": "A" * 40, "date": None},
        {"code_head": "a" * 39, "date": None},
        {"code_head": 1, "date": None},
        {"code_head": None, "date": "2026-02-30"},
        {"code_head": None, "date": "2026-1-1"},
        {"code_head": None, "date": 20261001},
        {"code_head": None, "date": None, "authenticated": True},
    ],
)
def test_invalid_declared_provenance_is_rejected(context, origin):
    _, request, draft, _ = context
    with pytest.raises(ContractError):
        contract.prepare_owner_case_set(draft, request, origin=origin)


@pytest.mark.parametrize("state", ["pending", "declined"])
def test_mixed_review_states_cannot_claim_all_labels_reviewed(context, state):
    _, request, draft, case_set = context
    choices = decisions(case_set)
    choices[next(iter(choices))] = decisions(case_set, state)[next(iter(choices))]
    labels = contract.review_owner_cases(case_set, draft, request, decisions=choices)
    assert labels.to_dict()["label_review_status"] == state
    assert labels.to_dict()["all_labels_reviewed"] is False
    plan = contract.prepare_owner_policy_plan(labels, case_set, draft, request)
    assert plan.to_dict()["planning_status"] == "blocked-" + state
