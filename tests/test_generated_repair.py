"""Scripted offline artifacts, not real generation, safe code or a validated repair."""

from __future__ import annotations

import ast
import builtins
import copy
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import jsonschema
import pytest

from authzest.codex import generated_repair as contract
from authzest.codex.contracts import MAX_JSON_BYTES, ContractError, canonical, identity


@pytest.fixture(autouse=True)
def forbid_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "generated proposal contracts cannot import targets, access I/O or execute code"
        )

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"fastapi", "uvicorn", "openai", "httpx", "requests", "examples"}:
            forbidden()
        if name.startswith(("authzest.runner", "authzest.codex.app_server")):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)


@pytest.fixture
def request_context():
    return contract.build_generated_repair_request()


def draft(request, status="proposed-change"):
    context = request.to_dict()
    source = context["scenario"]["source"]
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Scripted candidate, not model output or a verified repair.",
        "evidence_ids": list(context["evidence_ids"].values()),
        "assumptions": ["Policy remains pending maintainer review."],
        "uncertainties": ["No execution or safety check performed."]
        if status in ("unknown", "refused")
        else [],
        "limitations": ["AST parsing is not compilation, correctness, safety or approval."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": source["text"] + "\n# Scripted candidate text, not an implemented fix.\n",
            "test_path": context["scenario"]["test_path"],
            "test_text": "def test_scripted_candidate():\n    assert True\n",
        }
        if status == "proposed-change"
        else None,
    }


def validate(data, request):
    return contract.validate_generated_repair_proposal(canonical(data), request)


def preview(data, request):
    return contract.prepare_generated_repair_preview(validate(data, request), request).to_dict()


def forged(kind, raw):
    value = object.__new__(kind)
    object.__setattr__(value, "payload_json", raw)
    return value


def test_fixed_request_binds_prompt_schema_source_policy_declarations_and_pending_authorship(
    request_context,
):
    data = request_context.to_dict()
    scenario = data["scenario"]
    assert scenario["scenario_id"] == "owned-fastapi-document-ownership-v1"
    assert scenario["source"]["path"] == "app.py"
    assert scenario["test_path"] == "tests/test_generated_ownership.py"
    assert scenario["test_before"] == "absent-in-planned-copy"
    assert scenario["policy_authorship"] == "assistant"
    assert scenario["policy_review"] == "pending-maintainer-review"
    assert "after" not in scenario and "registry" not in data
    assert request_context.request_id == "generated-repair-request-" + identity(data)
    assert scenario["source"]["sha256"] == sha256(scenario["source"]["text"].encode()).hexdigest()
    assert len(data["evidence_ids"]) == len(set(data["evidence_ids"].values())) == 3
    assert contract.build_generated_repair_request() == request_context
    assert contract.validate_generated_repair_request(json.dumps(data, indent=2)) == request_context


def test_prompt_and_output_schema_are_deterministically_bound_detached_and_bounded(request_context):
    data = request_context.to_dict()
    schema = contract.generated_repair_output_schema(request_context)
    prompt = contract.generated_repair_prompt(request_context)
    assert prompt == (
        data["prompt"]["text"]
        + "\nREQUEST_JSON:\n"
        + request_context.payload_json
        + "\nREQUEST_ID:\n"
        + request_context.request_id
        + "\nOUTPUT_SCHEMA:\n"
        + canonical(schema)
        + "\n"
    )
    assert len(prompt.encode()) <= MAX_JSON_BYTES
    assert "model-authored complete replacement source" in prompt
    assert "no after solution or repair registry" in prompt
    assert "Use no tools, files, commands, network" in prompt
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert schema["properties"]["request_id"]["enum"] == [request_context.request_id]
    assert "oneOf" not in schema and "anyOf" not in schema
    schema["properties"].clear()
    data["scenario"]["source"]["text"] = "changed"
    assert contract.generated_repair_output_schema(request_context)["properties"]
    assert request_context.to_dict()["scenario"]["source"]["text"] != "changed"


def test_wrappers_are_frozen_and_return_mapping_copies(request_context):
    proposal = validate(draft(request_context), request_context)
    with pytest.raises(FrozenInstanceError):
        request_context.payload_json = "{}"
    with pytest.raises(FrozenInstanceError):
        proposal.payload_json = "{}"
    data = proposal.to_dict()
    data["proposal"]["after_text"] = "changed"
    assert proposal.to_dict()["proposal"]["after_text"] != "changed"


@pytest.mark.parametrize("status", contract.STATUSES)
def test_all_statuses_match_closed_schema_and_preview_has_no_authority(request_context, status):
    data = draft(request_context, status)
    proposal = validate(data, request_context)
    assert proposal.to_dict() == data
    assert proposal.proposal_id == "generated-repair-proposal-" + identity(data)
    # jsonschema may lazily import its own internals; it never imports the target.
    jsonschema.Draft202012Validator(
        contract.generated_repair_output_schema(request_context)
    ).validate(data)
    result = contract.prepare_generated_repair_preview(proposal, request_context).to_dict()
    assert result["status"] == status
    assert result["applied"] is False and result["execution"] == "not-run"
    assert result["provider_calls_made_by_this_function"] == 0 and result["trust"] == "unverified"
    assert result["python_validation"] == "ast-parse-only"
    assert result["code_safety"] == result["policy_correctness"] == "not-assessed"
    assert result["provenance"] == {"kind": "caller-supplied-unverified", "authenticated": False}
    assert result["sharing_authorized"] is result["execution_authorized"] is False
    assert result["approval"] == "not-requested"
    assert len(result["changes"]) == (2 if status == "proposed-change" else 0)


@pytest.mark.parametrize(
    "field", ["prompt", "scenario", "evidence_ids", "response_schema", "kind", "schema_version"]
)
def test_current_request_reconstruction_rejects_tampered_content_not_just_hashes(
    request_context, field
):
    data = request_context.to_dict()
    data[field] = None
    with pytest.raises(ContractError):
        contract.GeneratedRepairRequest(canonical(data))
    with pytest.raises(ContractError):
        contract.generated_repair_prompt(forged(contract.GeneratedRepairRequest, canonical(data)))


def test_host_preview_revalidates_forged_proposal_and_current_request(request_context):
    raw = draft(request_context)
    raw["proposal"]["before_sha256"] = "0" * 64
    bad = forged(contract.GeneratedRepairProposal, canonical(raw))
    with pytest.raises(ContractError):
        contract.prepare_generated_repair_preview(bad, request_context)
    for value in (None, {}, "raw", forged(contract.GeneratedRepairRequest, "{}")):
        with pytest.raises(ContractError):
            contract.prepare_generated_repair_preview(
                validate(draft(request_context), request_context), value
            )
    with pytest.raises(ContractError):
        contract.prepare_generated_repair_preview({}, request_context)


def test_request_builder_accepts_no_arbitrary_sources_paths_models_or_execution_options():
    for field in ("source", "path", "test_path", "policy", "model", "callback", "registry"):
        with pytest.raises(TypeError):
            contract.build_generated_repair_request(**{field: None})


@pytest.mark.parametrize("status", ["unknown", "refused"])
def test_abstentions_require_uncertainty_and_null_proposal(request_context, status):
    data = draft(request_context, status)
    data["uncertainties"] = []
    with pytest.raises(ContractError):
        validate(data, request_context)
    data = draft(request_context, status)
    data["proposal"] = draft(request_context)["proposal"]
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_output_schema_is_shaping_only_host_enforces_cross_fields_and_unique_evidence(
    request_context,
):
    validator = jsonschema.Draft202012Validator(
        contract.generated_repair_output_schema(request_context)
    )
    for data in (
        draft(request_context, "unknown"),
        draft(request_context),
        draft(request_context, "no-change"),
    ):
        if data["status"] == "unknown":
            data["uncertainties"] = []
        elif data["status"] == "proposed-change":
            data["evidence_ids"] = [data["evidence_ids"][0]] * 3
        else:
            data["proposal"] = draft(request_context)["proposal"]
        validator.validate(data)
        with pytest.raises(ContractError):
            validate(data, request_context)


@pytest.mark.parametrize(
    "field",
    [
        "request_id",
        "schema_version",
        "status",
        "rationale",
        "evidence_ids",
        "assumptions",
        "limitations",
        "proposal",
    ],
)
def test_missing_extra_or_wrong_response_fields_fail_closed(request_context, field):
    data = draft(request_context)
    del data[field]
    with pytest.raises(ContractError):
        validate(data, request_context)
    data = draft(request_context)
    data[field] = None
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_path", "./app.py"),
        ("source_path", "../app.py"),
        ("source_path", "/app.py"),
        ("source_path", "APP.py"),
        ("test_path", "tests\\test_generated_ownership.py"),
        ("test_path", "tests/./test_generated_ownership.py"),
        ("test_path", "other.py"),
        ("before_sha256", "0" * 64),
    ],
)
def test_proposal_targets_and_source_hash_are_exact_not_path_aliases(request_context, field, value):
    data = draft(request_context)
    data["proposal"][field] = value
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_shape_duplicate_json_nonfinite_and_extra_keys_never_leak_source(request_context):
    raw = canonical(draft(request_context))
    for bad in (
        raw[:-1] + ',"status":"unknown"}',
        raw[:-1] + ',"private":NaN}',
        raw[:-1] + ',"private":1e9999}',
        raw[:-1] + ',"private":"data"}',
        raw + "{}",
    ):
        with pytest.raises(ContractError) as error:
            contract.validate_generated_repair_proposal(bad, request_context)
        assert "private" not in str(error.value)
    data = draft(request_context)
    data["proposal"]["private"] = None
    with pytest.raises(ContractError):
        validate(data, request_context)


def test_evidence_is_exactly_all_current_unique_ids(request_context):
    for ids in (
        [],
        ["foreign"],
        list(request_context.to_dict()["evidence_ids"].values())[:2],
        [next(iter(request_context.to_dict()["evidence_ids"].values()))] * 3,
    ):
        data = draft(request_context)
        data["evidence_ids"] = ids
        with pytest.raises(ContractError):
            validate(data, request_context)


@pytest.mark.parametrize("field", ["after_text", "test_text"])
def test_generated_utf8_byte_limit_is_checked_before_ast_parse(request_context, field, monkeypatch):
    data = draft(request_context)
    text = "#" + "🍋" * 4096 + "\n"
    data["proposal"][field] = text
    original_parse = ast.parse

    def guarded_parse(source, *args, **kwargs):
        assert source != text, "oversized generated bytes must not reach AST parsing"
        return original_parse(source, *args, **kwargs)

    monkeypatch.setattr(contract.ast, "parse", guarded_parse)
    with pytest.raises(ContractError) as error:
        validate(data, request_context)
    assert error.value.code == "validation-budget"


def test_exact_generated_byte_limit_allowed_but_one_more_rejected(request_context):
    data = draft(request_context)
    data["proposal"]["after_text"] = "#" + "x" * (contract.MAX_GENERATED_BYTES - 2) + "\n"
    assert len(data["proposal"]["after_text"].encode()) == contract.MAX_GENERATED_BYTES
    validate(data, request_context)
    data["proposal"]["after_text"] += "\n"
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("text", ["def private_bad(:\n", "\x00private", " ", "\ud800private"])
def test_generated_text_syntax_controls_and_unicode_fail_closed(request_context, text):
    data = draft(request_context)
    data["proposal"]["after_text"] = text
    with pytest.raises(ContractError) as error:
        validate(data, request_context)
    assert "private" not in str(error.value)


def test_noop_after_source_is_not_a_change(request_context):
    data = draft(request_context)
    data["proposal"]["after_text"] = request_context.to_dict()["scenario"]["source"]["text"]
    with pytest.raises(ContractError):
        validate(data, request_context)


@pytest.mark.parametrize("field", ["after_text", "test_text"])
def test_ast_node_and_depth_budgets_apply_to_both_generated_files(request_context, field):
    for text in ("0\n" * 2200, "x = " + "1+" * 70 + "1\n"):
        data = draft(request_context)
        data["proposal"][field] = text
        with pytest.raises(ContractError) as error:
            validate(data, request_context)
        assert error.value.code == "validation-budget"


def test_parse_only_acceptance_is_not_compilation_pytest_or_safety(request_context):
    data = draft(request_context)
    data["proposal"]["after_text"] = "return 1\n"  # AST-valid, not a compilable module.
    data["proposal"]["test_text"] = "import os\nos.system('must-not-run')\n"
    result = preview(data, request_context)
    assert result["python_validation"] == "ast-parse-only"
    assert result["code_safety"] == "not-assessed" and result["applied"] is False


def test_host_hashes_and_lf_aware_new_file_diff_preserve_crlf_and_missing_final_newline(
    request_context,
):
    data = draft(request_context)
    after = 'x = "a\u2028b"\r\n# exact CRLF\r\n'
    test = "def test_new():\n    assert True"
    data["proposal"].update(after_text=after, test_text=test)
    result = preview(data, request_context)
    source, new_test = result["changes"]
    assert source["after_sha256"] == sha256(after.encode()).hexdigest()
    assert new_test["after_sha256"] == sha256(test.encode()).hexdigest()
    assert '+x = "a\u2028b"\r\n' in source["diff"]
    assert new_test["before_sha256"] is None
    assert new_test["before_state"] == "absent-in-planned-copy"
    assert new_test["diff"].startswith("--- /dev/null\n+++ b/tests/test_generated_ownership.py\n")
    assert "\\ No newline at end of file\n" in new_test["diff"]
    assert result["proposal"]["proposal"]["after_text"] == after
    assert result["test_absence"] == "planned-copy-state-not-filesystem-observation"


def test_distinct_supplied_source_and_test_candidates_change_proposal_identity(request_context):
    first = draft(request_context)
    second = copy.deepcopy(first)
    second["proposal"]["after_text"] = "x = 42\n"
    second["proposal"]["test_text"] = "def test_other():\n    assert 2 == 2\n"
    assert (
        validate(first, request_context).proposal_id
        != validate(second, request_context).proposal_id
    )


def test_full_json_and_complete_prompt_remain_bounded(request_context, monkeypatch):
    with pytest.raises(ContractError):
        contract.validate_generated_repair_proposal(" " * (MAX_JSON_BYTES + 1), request_context)
    monkeypatch.setattr(contract, "_INSTRUCTIONS", contract._INSTRUCTIONS + "🍋" * 40_000)
    current = contract.build_generated_repair_request()
    assert len(current.payload_json.encode()) < MAX_JSON_BYTES
    with pytest.raises(ContractError) as error:
        contract.generated_repair_prompt(current)
    assert error.value.code == "validation-budget"
