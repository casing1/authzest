"""Offline planning/readiness only; no generated Python or executor runs."""

from __future__ import annotations

import ast
import asyncio
import builtins
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.generated_repair import (
    GeneratedRepairProposal,
    GeneratedRepairRequest,
    build_generated_repair_request,
    validate_generated_repair_proposal,
)
from authzest.runner import generated_repair_verification as contract
from authzest.runner.generated_repair_controls import build_generated_repair_controls


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch, request):
    # pytest exports this ID via PYTEST_CURRENT_TEST; Windows caps environment
    # values at 32,767 characters. Large test inputs must never become IDs.
    assert len(request.node.nodeid) < 512

    # Python 3.14 lazily initializes its standard-library unparser on first use.
    # Warm only this maintained AST before blocking exec/module initialization;
    # never initialize it by parsing or executing generated application text.
    assert ast.unparse(ast.Constant(value=None)) == "None"

    def forbidden(*args, **kwargs):
        pytest.fail("Offline verification must not access files, providers or runtime")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"fastapi", "uvicorn", "openai", "httpx", "requests", "docker"}:
            forbidden()
        if name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


def test_stdlib_unparser_works_after_all_execution_guards_are_installed():
    assert ast.unparse(ast.Constant(value=None)) == "None"
    assert ast.unparse(ast.Name(id="maintained_ast", ctx=ast.Load())) == "maintained_ast"
    with pytest.raises(pytest.fail.Exception):
        builtins.exec("raise AssertionError('blocked generated execution')")
    with pytest.raises(pytest.fail.Exception):
        builtins.eval("1 + 1")


def _proposal(request, status="proposed-change"):
    data = request.to_dict()
    source = data["scenario"]["source"]
    return validate_generated_repair_proposal(
        canonical(
            {
                "schema_version": "1.0",
                "request_id": request.request_id,
                "status": status,
                "rationale": "Scripted offline text, not a generated or verified repair.",
                "evidence_ids": list(data["evidence_ids"].values()),
                "assumptions": ["The new runtime boundary is unimplemented."],
                "uncertainties": ["No runtime observation exists."],
                "limitations": ["Only offline artifact validation."],
                "proposal": {
                    "source_path": "app.py",
                    "before_sha256": source["sha256"],
                    "after_text": source["text"] + "\n# Scripted inert candidate.\n",
                    "test_path": "tests/test_generated_ownership.py",
                    "test_text": (
                        "def test_scripted():\n    raise RuntimeError('must stay inert')\n"
                    ),
                }
                if status == "proposed-change"
                else None,
            }
        ),
        request,
    )


@pytest.fixture
def context():
    request = build_generated_repair_request()
    proposal = _proposal(request)
    preview = contract.build_generated_repair_verification_preview(request, proposal)
    return request, proposal, preview


def _forged(kind, payload):
    value = object.__new__(kind)
    object.__setattr__(value, "payload_json", payload)
    return value


def test_complete_preview_rebuilds_current_source_proposal_controls_and_diffs(context):
    request, proposal, preview = context
    data = preview.to_dict()
    assert data["schema_version"] == "1.0"
    assert data["kind"] == "generated-repair-verification-preview"
    assert data["request_id"] == request.request_id
    assert data["proposal_id"] == proposal.proposal_id
    assert preview.verification_preview_id == "generated-repair-verification-preview-" + identity(
        data
    )
    assert data["controls_id"] == build_generated_repair_controls().controls_id
    assert data["controls"] == build_generated_repair_controls().to_dict()
    changes = data["proposal_preview"]["changes"]
    assert [row["path"] for row in changes] == ["app.py", "tests/test_generated_ownership.py"]
    assert changes[0]["before_sha256"] == request.to_dict()["scenario"]["source"]["sha256"]
    assert changes[1]["before_state"] == "absent-in-planned-copy"
    assert "must stay inert" in data["proposal_preview"]["proposal"]["proposal"]["test_text"]
    assert (
        contract.validate_generated_repair_verification_preview(
            json.dumps(data, indent=2), request, proposal
        )
        == preview
    )
    assert contract.build_generated_repair_verification_preview(request, proposal) == preview


def test_copy_is_only_planned_and_restoration_keeps_the_materialized_test(context):
    _, _, preview = context
    data = preview.to_dict()
    assert data["copy"] == {
        "status": "planned-only",
        "workspace_identity": None,
        "file_snapshots": None,
        "test_absence_observed": False,
        "baseline": "before-source-plus-generated-test",
        "copy_materializes_test": True,
        "later_apply_scope": "source-replacement-only",
        "restore_target": "copy-created-before-app-and-unchanged-test",
        "test_retained_on_restore": True,
        "original_checkout_is_target": False,
        "atomic_two_file_transaction": False,
    }
    assert data["stages"] == ["copy", "before", "source-diff", "source-apply", "after", "restore"]
    assert data["planning_status"] == "offline-only"
    assert data["execution_boundary"] == "unimplemented"
    assert data["approval"] == "not-requested"
    assert data["runtime_approval"] == "not-granted"
    assert data["execution_authorized"] is False
    assert data["verified_fix"] is False
    assert data["authorization_status"] == "unknown"
    for field in (
        "execution_status",
        "test_materialization",
        "source_application",
        "restoration_status",
    ):
        assert data[field] == "not-run"


def test_recipe_remains_unbound_non_runnable_and_not_measured(context):
    recipe = context[2].to_dict()["recipe"]
    assert recipe["status"] == "proposed-not-enforced"
    for key in ("image_ids", "engine_identity", "launcher_sha256", "relay_sha256"):
        assert recipe[key] is None
    assert recipe["roles"]["T"]["network"] == recipe["roles"]["A"]["network"] == "none"
    assert recipe["roles"]["B"]["network"] == "exact-A-network-namespace-only"
    assert recipe["roles"]["A"]["test"] is False
    assert recipe["roles"]["B"]["source"] is recipe["roles"]["B"]["test"] is False
    assert recipe["limits"]["shared_phase_seconds"] == 40
    assert recipe["limits"]["cumulative_readiness_seconds_within_phase"] == 10
    assert recipe["limits"]["extra_cleanup_seconds"] == 10
    assert recipe["limits"]["decision_seconds"] == 300
    assert recipe["limits"]["phase_output_bytes"] == 262_144
    assert recipe["limits"]["retained_session_bytes"] == 2_097_152
    for key in (
        "budgets_measured",
        "universal_wall_clock_guarantee",
        "escape_proof_sandbox",
        "host_execution_fallback",
    ):
        assert recipe[key] is False
    assert "command" not in canonical(recipe)


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_non_change_results_keep_all_effects_unplanned(status):
    context = build_generated_repair_request()
    proposal = _proposal(context, status)
    preview = contract.build_generated_repair_verification_preview(context, proposal)
    data = preview.to_dict()
    assert data["proposal_status"] == status
    assert data["stages"] == []
    assert data["copy"]["status"] == "not-planned"
    assert data["copy"]["baseline"] is None
    assert data["copy"]["copy_materializes_test"] is False
    assert data["copy"]["test_retained_on_restore"] is False
    assert data["proposal_preview"]["changes"] == []
    assert contract.prepare_generated_repair_executor(preview).to_dict()["status"] == "not-ready"


@pytest.mark.parametrize(
    "field,value",
    [
        ("execution_authorized", True),
        ("verified_fix", True),
        ("execution_status", "completed"),
        ("source_application", "completed"),
        ("restoration_status", "completed"),
        ("authorization_status", "enforced"),
        ("test_materialization", "completed"),
        ("runtime_approval", "approved"),
        ("approval", "approved"),
        ("planning_status", "ready"),
        ("execution_boundary", "implemented"),
        ("schema_version", "2.0"),
        ("request_id", "other"),
        ("proposal_id", "other"),
        ("controls_id", "other"),
        ("provider_calls_made_by_this_function", False),
        ("stages", ["apply"]),
        ("copy", {}),
        ("recipe", {}),
        ("extra", "untrusted"),
    ],
)
def test_tampered_preview_cannot_gain_authority_or_change_bindings(context, field, value):
    request, proposal, preview = context
    data = preview.to_dict()
    data[field] = value
    with pytest.raises(ContractError):
        contract.validate_generated_repair_verification_preview(canonical(data), request, proposal)
    forged = _forged(contract.GeneratedRepairVerificationPreview, canonical(data))
    with pytest.raises(ContractError):
        contract.prepare_generated_repair_executor(forged)


@pytest.mark.parametrize(
    "path,value",
    [
        (("recipe", "roles", "T", "network"), "bridge"),
        (("recipe", "roles", "B", "source"), True),
        (("recipe", "limits", "shared_phase_seconds"), 400),
        (("copy", "test_absence_observed"), True),
        (("copy", "original_checkout_is_target"), True),
        (("copy", "workspace_identity"), {"path": "/tmp/untrusted"}),
        (("copy", "restore_target"), "original-checkout"),
        (("controls", "review"), "runtime-approved"),
        (("proposal_preview", "changes"), []),
    ],
)
def test_nested_changes_are_rebuilt_not_accepted_after_rehash(context, path, value):
    request, proposal, preview = context
    data = preview.to_dict()
    item = data
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    with pytest.raises(ContractError):
        contract.validate_generated_repair_verification_preview(canonical(data), request, proposal)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "[]",
        "null",
        "{",
        '{"x":1,"x":2}',
        '{"x":NaN}',
        '{"x":' + "[" * 40 + "0" + "]" * 40 + "}",
        " " * 262_145,
    ],
    ids=["non-text", "array", "null", "incomplete", "duplicate", "nonfinite", "deep", "oversize"],
)
def test_preview_json_shape_and_budgets(context, raw):
    with pytest.raises(ContractError):
        contract.validate_generated_repair_verification_preview(raw, context[0], context[1])


def test_public_wrappers_are_immutable_but_never_trusted_without_revalidation(context):
    request, proposal, preview = context
    with pytest.raises(FrozenInstanceError):
        preview.payload_json = "{}"
    data = preview.to_dict()
    data["controls"]["case_count"] = 0
    assert preview.to_dict()["controls"]["case_count"] == 17
    for bad_request, bad_proposal in (
        (None, proposal),
        (request, None),
        (_forged(GeneratedRepairRequest, "{}"), proposal),
        (request, _forged(GeneratedRepairProposal, "{}")),
    ):
        with pytest.raises(ContractError):
            contract.build_generated_repair_verification_preview(bad_request, bad_proposal)
    with pytest.raises(ContractError):
        contract.prepare_generated_repair_executor(None)


def test_default_executor_has_no_run_api_and_always_stays_disabled(context):
    preview = context[2]
    executor = contract.DisabledGeneratedRepairExecutor()
    assert not hasattr(executor, "run")
    assert not hasattr(executor, "execute")
    result = contract.prepare_generated_repair_executor(preview)
    assert result == executor.prepare(preview)
    data = result.to_dict()
    assert data["status"] == "not-ready"
    assert data["reason"] == "runtime-not-implemented"
    assert data["verification_preview_id"] == preview.verification_preview_id
    assert data["runtime_invoked"] is data["filesystem_observed"] is False
    assert data["verified_fix"] is data["execution_authorized"] is False
    assert (
        contract.validate_generated_repair_executor_readiness(json.dumps(data, indent=2), preview)
        == result
    )
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"


def test_mock_preparation_is_trusted_injection_but_cannot_supply_a_success_state(context):
    calls = []

    class Fake:
        def prepare(self, preview):
            calls.append(preview.verification_preview_id)
            result = contract.DisabledGeneratedRepairExecutor().prepare(preview).to_dict()
            result["reason"] = "unsupported-runtime"
            return contract.GeneratedRepairExecutorReadiness(canonical(result))

    result = contract.prepare_generated_repair_executor(context[2], Fake()).to_dict()
    assert calls == [context[2].verification_preview_id]
    assert result["status"] == "not-ready"
    assert result["reason"] == "unsupported-runtime"
    assert result["runtime_invoked"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "ready"),
        ("status", "completed"),
        ("runtime_invoked", True),
        ("filesystem_observed", True),
        ("execution_authorized", True),
        ("verified_fix", True),
        ("execution_status", "completed"),
        ("test_materialization", "completed"),
        ("source_application", "completed"),
        ("restoration_status", "completed"),
        ("authorization_status", "enforced"),
        ("verification_preview_id", "stale"),
        ("reason", "mock-passed"),
        ("reason", []),
        ("reason", None),
        ("provider_calls_made_by_this_function", False),
        ("extra", "unexpected"),
    ],
)
def test_fake_executor_cannot_forge_effects_or_ready_result(context, field, value):
    class Fake:
        def prepare(self, preview):
            data = contract.DisabledGeneratedRepairExecutor().prepare(preview).to_dict()
            data[field] = value
            return _forged(contract.GeneratedRepairExecutorReadiness, canonical(data))

    with pytest.raises(ContractError):
        contract.prepare_generated_repair_executor(context[2], Fake())


@pytest.mark.parametrize("result", [None, {}, "{}", object()])
def test_fake_executor_requires_exact_wrapper_type(context, result):
    class Fake:
        def prepare(self, preview):
            return result

    with pytest.raises(ContractError):
        contract.prepare_generated_repair_executor(context[2], Fake())


def test_preview_is_revalidated_before_any_injected_method_call(context):
    calls = []

    class Fake:
        def prepare(self, preview):
            calls.append(preview)
            raise AssertionError("must not be called")

    data = context[2].to_dict()
    data["controls"]["case_count"] = 0
    forged = _forged(contract.GeneratedRepairVerificationPreview, canonical(data))
    with pytest.raises(ContractError):
        contract.prepare_generated_repair_executor(forged, Fake())
    assert calls == []
    with pytest.raises(ContractError):
        contract.prepare_generated_repair_executor(context[2], object())


def test_unchanged_generation_policy_review_is_not_rewritten(context):
    assert context[0].to_dict()["scenario"]["policy_review"] == "pending-maintainer-review"
    data = context[2].to_dict()
    assert (
        data["design_review"] == data["controls"]["review"] == "maintainer-accepted-offline-design"
    )
    assert data["runtime_approval"] == data["controls"]["runtime_approval"] == "not-granted"
