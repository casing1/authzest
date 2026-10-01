"""Offline examples of the output-schema/host boundary, not a provider acceptance test.

The JSON Schema validator is a development-only dependency. Citation coverage,
uniqueness, terminal identifier newlines and the final UTF-8 budget deliberately
remain stricter host checks.
"""

import builtins
import copy
import json
import socket
import subprocess

import pytest
from jsonschema import Draft202012Validator

from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical
from authzest.codex.owner_policy_review import (
    OWNER_POLICY_PROMPT_VERSION,
    build_owner_policy_request,
    owner_policy_output_schema,
    validate_owner_policy_draft,
)
from authzest.runner import codex_owner_review as workflow


@pytest.fixture
def request_context():
    return build_owner_policy_request("owner-schema-offline-model")


@pytest.fixture
def schema_validator(request_context):
    schema = owner_policy_output_schema(request_context)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture
def draft(request_context):
    evidence = request_context.to_dict()["evidence"]
    return {
        "answers": [
            {
                "question_id": "review",
                "status": "hypothesis",
                "answer": "Authenticated owners with the exact scope are intended to read.",
                "explanation": "This is a source observation, not an execution result.",
                "evidence_ids": [
                    item["id"] for item in evidence if item["kind"] in ("source", "policy")
                ],
                "assumptions": [],
                "unknowns": ["Trusted endpoint authentication has not been evaluated."],
                "review_questions": [],
            }
        ],
        "cases": [
            {
                "id": "owner-read",
                "principal": {
                    "subject": "alice",
                    "authenticated": True,
                    "scopes": ["reports:read"],
                },
                "report": {"report_id": "report-001", "owner_id": "alice"},
                "expected": True,
                "reason": "A synthetic trusted owner has the exact required scope.",
                "evidence_ids": [
                    item["id"]
                    for item in evidence
                    if item["kind"] == "policy"
                    or (item["kind"] == "source" and item["data"]["path"] == "policy.py")
                ],
            }
        ],
    }


def replace(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


def assert_both_accept(validator, data, request):
    validator.validate(data)
    return validate_owner_policy_draft(canonical(data), request, usage=None).to_dict()


def assert_both_reject(validator, data, request):
    assert not validator.is_valid(data)
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(data), request, usage=None)


def test_baseline_hypothesis_and_unknown_satisfy_schema_and_host(
    schema_validator, draft, request_context
):
    assert_both_accept(schema_validator, draft, request_context)
    draft["answers"][0].update(status="unknown", answer=None)
    draft["cases"][0].update(principal=None, report=None, expected=False)
    assert_both_accept(schema_validator, draft, request_context)


@pytest.mark.parametrize("mutation", ["nonnull-unknown", "empty-unknowns", "null-hypothesis"])
def test_answer_status_constraints_agree(schema_validator, draft, request_context, mutation):
    answer = draft["answers"][0]
    if mutation == "nonnull-unknown":
        answer["status"] = "unknown"
    elif mutation == "empty-unknowns":
        answer.update(status="unknown", answer=None, unknowns=[])
    else:
        answer["answer"] = None
    assert_both_reject(schema_validator, draft, request_context)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("answers",), []),
        (("answers", 0, "status"), "confirmed"),
        (("answers", 0, "question_id"), "unapproved-question"),
        (("answers", 0, "explanation"), ""),
        (("answers", 0, "explanation"), "a" * 4097),
        (("answers", 0, "assumptions"), ["bounded"] * 33),
        (("answers", 0, "unknowns"), "not-an-array"),
        (("cases",), []),
        (("cases", 0, "id"), ""),
        (("cases", 0, "id"), "a" * 65),
        (("cases", 0, "id"), "owner/read"),
        (("cases", 0, "expected"), 1),
        (("cases", 0, "expected"), "false"),
        (("cases", 0, "principal"), []),
        (("cases", 0, "principal", "authenticated"), 0),
        (("cases", 0, "principal", "subject"), 7),
        (("cases", 0, "principal", "subject"), "a" * 129),
        (("cases", 0, "principal", "scopes"), "reports:read"),
        (("cases", 0, "principal", "scopes"), [None]),
        (("cases", 0, "principal", "scopes"), ["s" * 129]),
        (("cases", 0, "principal", "scopes"), [f"scope-{i}" for i in range(17)]),
        (("cases", 0, "report", "report_id"), False),
        (("cases", 0, "reason"), "a" * 4097),
        (("cases", 0, "evidence_ids"), ["unknown", "also-unknown"]),
    ],
    ids=[
        "no-answer",
        "unapproved-status",
        "wrong-question",
        "empty-explanation",
        "long-explanation",
        "too-many-assumptions",
        "unknowns-not-array",
        "no-cases",
        "empty-case-id",
        "long-case-id",
        "invalid-case-id",
        "integer-label",
        "string-label",
        "principal-not-object",
        "integer-authenticated",
        "integer-subject",
        "long-subject",
        "scopes-not-array",
        "null-scope",
        "long-scope",
        "too-many-scopes",
        "boolean-report-id",
        "long-reason",
        "unknown-citations",
    ],
)
def test_shapes_types_and_bounds_agree(schema_validator, draft, request_context, path, value):
    replace(draft, path, value)
    assert_both_reject(schema_validator, draft, request_context)


@pytest.mark.parametrize("where", ["root", "answer", "case", "principal", "report"])
@pytest.mark.parametrize("mutation", ["extra", "missing"])
def test_every_model_object_is_closed_and_all_fields_required(
    schema_validator, draft, request_context, where, mutation
):
    target = {
        "root": draft,
        "answer": draft["answers"][0],
        "case": draft["cases"][0],
        "principal": draft["cases"][0]["principal"],
        "report": draft["cases"][0]["report"],
    }[where]
    if mutation == "extra":
        target["executed"] = True
    else:
        target.pop(next(iter(target)))
    assert_both_reject(schema_validator, draft, request_context)


@pytest.mark.parametrize("blank", [" ", "\t\n\r", "\u001c", "\u0085", "\u00a0", "\u3000"])
@pytest.mark.parametrize("field", ["scope", "reason"])
def test_ascii_and_unicode_blank_text_is_rejected_by_both(
    schema_validator, draft, request_context, blank, field
):
    if field == "scope":
        draft["cases"][0]["principal"]["scopes"] = [blank]
    else:
        draft["cases"][0]["reason"] = blank
    assert_both_reject(schema_validator, draft, request_context)


@pytest.mark.parametrize("bad", ["alice\t", "alice\r", "alice\x00"])
def test_identifier_control_characters_are_rejected_by_both(
    schema_validator, draft, request_context, bad
):
    draft["cases"][0]["principal"]["subject"] = bad
    assert_both_reject(schema_validator, draft, request_context)


@pytest.mark.parametrize("bad", ["reason\x00", "reason\x1f"])
def test_text_disallowed_controls_are_rejected_by_both(
    schema_validator, draft, request_context, bad
):
    draft["cases"][0]["reason"] = bad
    assert_both_reject(schema_validator, draft, request_context)


@pytest.mark.parametrize(
    "path",
    [("cases", 0, "reason"), ("cases", 0, "principal", "subject")],
    ids=["text", "identifier"],
)
@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"], ids=["high", "low"])
def test_lone_surrogates_remain_a_host_utf8_constraint(
    schema_validator, draft, request_context, path, surrogate
):
    # A surrogate-range exclusion in a regex can reject legitimate astral text
    # in UTF-16 engines without a Unicode flag. Keep UTF-8 validity host-owned.
    replace(draft, path, "invalid" + surrogate)
    schema_validator.validate(draft)
    with pytest.raises(ContractError):
        validate_owner_policy_draft(
            json.dumps(draft, ensure_ascii=True), request_context, usage=None
        )


@pytest.mark.parametrize(
    "path",
    [("cases", 0, "id"), ("cases", 0, "principal", "subject")],
    ids=["case-id", "nullable-synthetic-id"],
)
def test_terminal_identifier_newline_remains_an_explicit_host_only_check(
    schema_validator, draft, request_context, path
):
    # Portable `$` patterns may match before a terminal newline; do not mistake
    # schema acceptance for the host's stricter full-match/control check.
    replace(draft, path, "owner-read\n")
    schema_validator.validate(draft)
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(draft), request_context, usage=None)


@pytest.mark.parametrize("value", [None, "", " ", "\u0085\u3000", " alice ", "\U0001f600" * 128])
def test_nullable_and_blank_synthetic_ids_are_intentional_unmodified_inputs(
    schema_validator, draft, request_context, value
):
    case = draft["cases"][0]
    case["principal"]["subject"] = value
    case["report"].update(report_id=value, owner_id=value)
    result = assert_both_accept(schema_validator, draft, request_context)
    assert result["cases"][0]["principal"]["subject"] == value
    assert result["cases"][0]["report"] == {"report_id": value, "owner_id": value}


def test_allowed_text_controls_non_bmp_and_exact_limits_remain_valid(
    schema_validator, draft, request_context
):
    answer = draft["answers"][0]
    answer["explanation"] = "\tObservation\n\r\U0001f600"
    answer["assumptions"] = ["bounded assumption"] * 32
    case = draft["cases"][0]
    case["id"] = "a" * 64
    case["reason"] = "\U0001f600" * 4096
    case["principal"]["scopes"] = ["\U0001f600" * 128] + [f"scope-{i}" for i in range(15)]
    draft["cases"] = [copy.deepcopy(case) for _ in range(16)]
    for index, item in enumerate(draft["cases"]):
        item["id"] = str(index).ljust(64, "a")
        # Keep the aggregate UTF-8 representation below the separate host budget.
        if index:
            item["reason"] = "bounded reason"
    assert_both_accept(schema_validator, draft, request_context)


@pytest.mark.parametrize("where", ["answer", "case"])
def test_required_citation_coverage_is_an_explicit_host_only_constraint(
    schema_validator, draft, request_context, where
):
    evidence = request_context.to_dict()["evidence"]
    if where == "answer":
        omitted = next(
            item["id"]
            for item in evidence
            if item["kind"] == "source" and item["data"]["path"] == "main.py"
        )
        draft["answers"][0]["evidence_ids"] = [
            item["id"] for item in evidence if item["id"] != omitted
        ][:3]
    else:
        draft["cases"][0]["evidence_ids"] = [
            item["id"] for item in evidence if item["kind"] in ("route", "limitations")
        ]
    schema_validator.validate(draft)
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(draft), request_context, usage=None)


@pytest.mark.parametrize("where", ["answer-citation", "case-citation", "scope", "case-id"])
def test_uniqueness_is_an_explicit_host_only_constraint(
    schema_validator, draft, request_context, where
):
    case = draft["cases"][0]
    if where == "answer-citation":
        values = draft["answers"][0]["evidence_ids"]
    elif where == "case-citation":
        values = case["evidence_ids"]
    elif where == "scope":
        values = case["principal"]["scopes"]
    else:
        values = draft["cases"]
    values.append(copy.deepcopy(values[0]))
    schema_validator.validate(draft)
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(draft), request_context, usage=None)


def test_utf8_byte_budget_is_separate_from_schema_character_limits(
    schema_validator, draft, request_context
):
    draft["answers"][0]["assumptions"] = ["\U0001f600" * 4096] * 32
    schema_validator.validate(draft)
    raw = canonical(draft)
    assert len(raw) < MAX_JSON_BYTES < len(raw.encode("utf-8"))
    with pytest.raises(ContractError):
        validate_owner_policy_draft(raw, request_context, usage=None)


def test_final_host_metadata_also_counts_toward_the_separate_budget(
    schema_validator, draft, request_context
):
    answer = draft["answers"][0]
    answer["assumptions"] = ["a" * 4096] * 32
    answer["unknowns"] = ["a" * 4096] * 31
    remaining = MAX_JSON_BYTES - len(canonical(draft).encode("utf-8")) - 3
    assert 1 <= remaining <= 4096
    answer["unknowns"].append("a" * remaining)
    schema_validator.validate(draft)
    raw = canonical(draft)
    assert len(raw.encode("utf-8")) == MAX_JSON_BYTES
    with pytest.raises(ContractError):
        validate_owner_policy_draft(raw, request_context, usage=None)


def test_schema_nested_answer_branches_remain_closed_objects(schema_validator):
    schema = schema_validator.schema
    assert schema["type"] == "object"
    assert "anyOf" not in schema
    branches = schema["properties"]["answers"]["items"]["anyOf"]
    assert len(branches) == 2
    pending = [schema]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("type") == "object":
                assert item["additionalProperties"] is False
                assert set(item["properties"]) == set(item["required"])
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def test_schema_acceptance_never_promotes_labels_or_executes_sources(
    schema_validator, draft, request_context, monkeypatch
):
    original_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        assert not name.startswith("examples.fastapi_owner_policy")
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Structural conformance must not run processes or contact a provider")

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    # Deliberately not the intended policy result: neither validator grades labels.
    draft["cases"][0]["expected"] = False
    result = assert_both_accept(schema_validator, draft, request_context)
    assert result["cases"][0]["expected"] is False
    assert result["case_authorship"] == "model-authored"
    assert result["case_review_status"] == "unreviewed"
    assert result["execution_status"] == "not-run"
    assert result["authorization_status"] == "unknown"


def test_prompt_v2_and_schema_changes_require_a_different_sharing_identity(monkeypatch):
    assert OWNER_POLICY_PROMPT_VERSION == "owner-policy-review-v2"
    preview = workflow.build_owner_review_preview("gpt-6-astra")
    assert preview["sharing_id"] != (
        "share-eb98405cadcdc6234501d513dec8be6c37f1e4c06a50438b260ab40d38c481a7"
    )
    original_schema = workflow.owner_policy_output_schema

    def changed_schema(request):
        schema = original_schema(request)
        schema["description"] = "An altered output contract requires fresh sharing consent."
        return schema

    monkeypatch.setattr(workflow, "owner_policy_output_schema", changed_schema)
    assert workflow.build_owner_review_preview("gpt-6-astra")["sharing_id"] != preview["sharing_id"]
