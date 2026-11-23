"""Copy-plan data contracts never open a target, invoke a model or run supplied code."""

import builtins
import io
import os
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.analyzer.repository_input import CapturedFile, RepositoryInput
from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.repository_copy_plan import (
    RepositoryCopyPlan,
    prepare_repository_copy_plan,
    validate_repository_copy_plan,
)
from authzest.codex.repository_proposal import (
    TEST_PATH,
    RepositoryProposalRequest,
    build_repository_request,
    prepare_repository_preview,
)

SOURCE = (
    "from fastapi import FastAPI\napp = FastAPI()\n"
    '@app.get("/items/{item_id}")\n'
    'def read(item_id: str):\n    return {"id": item_id}\n'
)
AFTER = SOURCE.replace('{"id": item_id}', '{"id": item_id, "checked": True}')
TEST = 'def test_item(client):\n    assert client.get("/items/one").status_code == 200\n'
POLICY = "Only an authenticated owner may read an item.\n"


def _hash(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _keys(value):
    if isinstance(value, dict):
        return set(value).union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value))
    return set()


def _snapshot(*, source=SOURCE, source_path="main.py", policy=POLICY, contexts=()):
    items = [(source_path, source), ("policy.md", policy), *contexts]
    return RepositoryInput(
        Path("/unused/private/root"),
        source_path,
        "policy.md",
        tuple(path for path, _ in contexts),
        tuple(CapturedFile(path, text, _hash(text)) for path, text in items),
    )


def _request(**kwargs):
    return build_repository_request(_snapshot(**kwargs), "offline-model")


def _response(request, *, status="proposed-change", after=AFTER, test=TEST):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": status,
        "rationale": "Proposed source change and regression test.",
        "assumptions": ["A representative client fixture will be supplied later."],
        "uncertainties": ["Runtime behavior is unverified."],
        "limitations": ["No execution or policy assurance."],
        "proposal": (
            {
                "source_path": source["path"],
                "before_sha256": source["sha256"],
                "after_text": after,
                "test_path": TEST_PATH,
                "test_text": test,
            }
            if status == "proposed-change"
            else None
        ),
    }


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected filesystem, network, process or code execution")

    # Imports above are complete. ast.parse's compile-to-AST operation remains allowed.
    for owner, names in (
        (builtins, ("open", "eval", "exec")),
        (io, ("open",)),
        (os, ("open", "system", "fork", "execv", "execve", "posix_spawn")),
        (socket, ("socket", "create_connection")),
        (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
    ):
        for name in names:
            if hasattr(owner, name):
                monkeypatch.setattr(owner, name, forbidden)


def test_layout_preserves_exact_selected_bytes_and_has_no_material_text():
    contexts = (("pkg/__init__.py", ""), ("pkg/권한.py", 'ROLE = "소유자"\r\n'))
    request = _request(source_path="app/main.py", contexts=contexts)
    response = _response(request)
    plan = prepare_repository_copy_plan(request, response)
    data = plan.to_dict()
    expected = [
        ("selected-source", "project/app/main.py", SOURCE, "app/main.py"),
        ("selected-context", "project/pkg/__init__.py", "", "pkg/__init__.py"),
        ("selected-context", "project/pkg/권한.py", contexts[1][1], "pkg/권한.py"),
        ("generated-test", "project/" + TEST_PATH, TEST, None),
        ("policy-snapshot", "evidence/policy.txt", POLICY, "policy.md"),
        ("source-before", "evidence/source.before", SOURCE, "app/main.py"),
        ("source-after", "evidence/source.after", AFTER, "app/main.py"),
        ("test-snapshot", "evidence/test.txt", TEST, None),
    ]
    assert data["files"] == [
        {
            "role": role,
            "workspace_path": path,
            "origin_relative_path": origin,
            "utf8_bytes": len(text.encode("utf-8")),
            "sha256": _hash(text),
        }
        for role, path, text, origin in expected
    ]
    assert data["material_utf8_bytes"] == sum(len(text.encode()) for _, _, text, _ in expected)
    assert data["layout_version"] == data["schema_version"] == "1.0"
    assert "/unused" not in plan.payload_json
    assert all(text not in plan.payload_json for text in (SOURCE, POLICY, AFTER, TEST))
    assert not {
        "text",
        "diff",
        "prompt",
        "before_text",
        "after_text",
        "test_text",
        "output_schema",
    }.intersection(_keys(data))


def test_transition_and_diff_identities_are_host_derived_not_materializing_authority():
    request = _request()
    response = _response(request)
    data = prepare_repository_copy_plan(request, response).to_dict()
    assert data["source_transition"] == {
        "workspace_path": "project/main.py",
        "before_sha256": _hash(SOURCE),
        "after_sha256": _hash(AFTER),
        "restore_sha256": _hash(SOURCE),
    }
    preview = prepare_repository_preview(response, request)
    assert data["diff_identities"] == [
        {
            "path": change["path"],
            "before_sha256": change["before_sha256"],
            "after_sha256": change["after_sha256"],
            "diff_sha256": _hash(change["diff"]),
        }
        for change in preview["changes"]
    ]
    assert data["generated_test"] == {
        "workspace_path": "project/" + TEST_PATH,
        "basis": "private-new-artifact",
        "original_path_status": "uninspected",
        "original_absence_established": False,
    }
    assert data["diff_identities"][1]["before_sha256"] is None


def test_journal_is_separate_bounded_host_metadata_with_no_identity_cycle():
    request = _request()
    response = _response(request)
    plan = prepare_repository_copy_plan(request, response)
    data = plan.to_dict()
    assert data["request_identity"] == identity(request.to_dict())
    assert data["response_identity"] == identity(response)
    assert data["journal"]["workspace_path"] == "record.json"
    assert data["journal"]["max_utf8_bytes"] == 65_536
    assert data["journal"]["authority"] == "none"
    assert "sha256" not in data["journal"]
    assert all(file["workspace_path"] != "record.json" for file in data["files"])
    data.pop("plan_id")
    assert plan.plan_id == "repository-copy-plan-" + identity(data)


def test_plan_is_inert_detached_and_does_not_claim_live_binding_or_permission():
    request = _request()
    response = _response(request, test='raise RuntimeError("must never run")\n')
    plan = prepare_repository_copy_plan(request, response)
    assert validate_repository_copy_plan(plan, request, response) == plan
    assert plan.to_dict()["effects"] == {
        "workspace": "not-created",
        "original_files": "not-read-or-written",
        "copy": "not-run",
        "execution": "not-run",
        "patch_application": "not-run",
        "restoration": "not-run",
        "approvals": "not-issued",
        "authorization": "unknown",
    }
    assert "not-bound" in plan.to_dict()["requirements"]["fresh_root"]
    assert "no-open-or-reopen" in plan.to_dict()["requirements"]["live_session"]
    assert "300-seconds-not-issued" in plan.to_dict()["requirements"]["decisions"]
    detached = plan.to_dict()
    detached["files"][0]["sha256"] = "altered"
    assert plan.to_dict()["files"][0]["sha256"] == _hash(SOURCE)
    with pytest.raises(FrozenInstanceError):
        plan.payload_json = "{}"
    assert not any(hasattr(plan, name) for name in ("open", "read", "apply", "approve", "resume"))


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_valid_nonchange_statuses_produce_no_plan(status):
    request = _request()
    response = _response(request, status=status)
    assert prepare_repository_copy_plan(request, response) is None
    with pytest.raises(ContractError):
        validate_repository_copy_plan(RepositoryCopyPlan("{}"), request, response)
    response["proposal"] = _response(request)["proposal"]
    with pytest.raises(ContractError):
        prepare_repository_copy_plan(request, response)


@pytest.mark.parametrize(
    "field", ["source", "policy", "context", "model", "rationale", "assumptions", "test", "after"]
)
def test_old_plan_rejected_when_any_current_bound_input_changes(field):
    request = _request(contexts=(("auth.py", "ROLE = 'owner'\n"),))
    response = _response(request)
    plan = prepare_repository_copy_plan(request, response)
    if field in {"source", "policy", "context", "model"}:
        kwargs = {"contexts": (("auth.py", "ROLE = 'owner'\n"),)}
        if field == "source":
            kwargs["source"] = SOURCE + "# selected edit\n"
        if field == "policy":
            kwargs["policy"] = POLICY + "No anonymous readers.\n"
        if field == "context":
            kwargs["contexts"] = (("auth.py", "ROLE = 'member'\n"),)
        request = build_repository_request(
            _snapshot(**kwargs), "other-model" if field == "model" else "offline-model"
        )
        response = _response(request)
    elif field == "rationale":
        response["rationale"] += " Revised rationale."
    elif field == "assumptions":
        response["assumptions"].append("The schema must be reviewed.")
    elif field == "test":
        response["proposal"]["test_text"] += "# revised test\n"
    else:
        response["proposal"]["after_text"] += "# revised source\n"
    current = prepare_repository_copy_plan(request, response)
    assert current.plan_id != plan.plan_id
    with pytest.raises(ContractError, match="copy plan mismatch"):
        validate_repository_copy_plan(plan, request, response)


@pytest.mark.parametrize("field", ["files", "source_transition", "effects", "diff_identities"])
def test_rehashing_tampered_metadata_does_not_make_it_valid(field):
    request = _request()
    response = _response(request)
    plan = prepare_repository_copy_plan(request, response)
    data = plan.to_dict()
    if field == "files":
        data[field][0]["workspace_path"] = "project/other.py"
    elif field == "source_transition":
        data[field]["restore_sha256"] = _hash(AFTER)
    elif field == "effects":
        data[field]["approvals"] = "issued"
    else:
        data[field][0]["diff_sha256"] = "0" * 64
    data.pop("plan_id")
    data["plan_id"] = "repository-copy-plan-" + identity(data)
    with pytest.raises(ContractError, match="copy plan mismatch"):
        validate_repository_copy_plan(RepositoryCopyPlan(canonical(data)), request, response)


def test_validation_does_not_freeze_mutable_response_or_accept_unvalidated_request():
    request = _request()
    response = _response(request)
    checked = validate_repository_copy_plan(
        prepare_repository_copy_plan(request, response), request, response
    )
    response["limitations"].append("An additional unresolved limitation.")
    with pytest.raises(ContractError):
        validate_repository_copy_plan(checked, request, response)
    request_data = request.to_dict()
    request_data["prompt"] += " altered instructions"
    forged_request = RepositoryProposalRequest(canonical(request_data))
    with pytest.raises(ContractError):
        prepare_repository_copy_plan(forged_request, _response(request))
    with pytest.raises(ContractError):
        validate_repository_copy_plan(checked.to_dict(), request, _response(request))


@pytest.mark.parametrize(
    "source_path,contexts",
    [
        (TEST_PATH + "/child.py", ()),
        ("main.py", ((TEST_PATH + "/child.py", ""),)),
        ("pkg.py", (("pkg.py/child.py", ""),)),
        ("Main.py", (("main.py", ""),)),
        ("caf\u00e9.py", (("cafe\u0301.py", ""),)),
        ("\u0390.py", (("\u03aa\u0301.py", ""),)),
        ("main.py", (("tests/TEST_AUTHZEST_REGRESSION.PY/child.py", ""),)),
    ],
)
def test_file_directory_or_host_alias_collision_rejected_before_copy(source_path, contexts):
    request = _request(source_path=source_path, contexts=contexts)
    with pytest.raises(ContractError, match="workspace paths overlap"):
        prepare_repository_copy_plan(request, _response(request))


def test_empty_source_is_preserved_when_context_supplies_the_declaration():
    request = _request(source="", contexts=(("pkg/routes.py", SOURCE),))
    data = prepare_repository_copy_plan(request, _response(request)).to_dict()
    assert data["files"][0]["utf8_bytes"] == 0
    assert data["files"][0]["sha256"] == _hash("")
    assert data["source_transition"]["restore_sha256"] == _hash("")


def _pad(text, size):
    return text + "#" + "x" * (size - len(text.encode()) - 1)


def test_exact_total_and_per_file_byte_boundaries_remain_supported():
    request = _request(
        source=_pad(SOURCE, 16_384),
        policy=_pad(POLICY, 8192),
        contexts=(
            ("first.py", _pad("", 16_384)),
            ("second.py", _pad("", 16_384)),
            ("third.py", _pad("", 8192)),
        ),
    )
    response = _response(request, after=_pad(AFTER, 16_384), test=_pad(TEST, 16_384))
    data = prepare_repository_copy_plan(request, response).to_dict()
    assert data["material_utf8_bytes"] == data["material_max_utf8_bytes"] == 131_072
    selection = request.to_dict()["selection"]
    contexts = tuple((file["path"], file["text"]) for file in selection["files"][2:])
    with pytest.raises(ContractError):
        _request(
            source=selection["files"][0]["text"],
            policy=selection["files"][1]["text"],
            contexts=(*contexts[:-1], (contexts[-1][0], contexts[-1][1] + "x")),
        )


@pytest.mark.parametrize("field", ["source", "policy", "context", "after", "test"])
def test_oversized_utf8_inputs_are_rejected_without_any_materialization(field):
    kwargs = {}
    if field == "source":
        kwargs["source"] = SOURCE + "#" + "é" * 8192
    elif field == "policy":
        kwargs["policy"] = "é" * 4097
    elif field == "context":
        kwargs["contexts"] = (("ctx.py", "#" + "é" * 8192),)
    with pytest.raises(ContractError):
        request = _request(**kwargs)
        response = _response(request)
        if field in {"after", "test"}:
            response["proposal"][field + "_text"] = "#" + "é" * 8192
        prepare_repository_copy_plan(request, response)


@pytest.mark.parametrize("field", ["after_text", "test_text"])
def test_blank_or_nonpython_generated_artifacts_rejected(field):
    request = _request()
    response = _response(request)
    for invalid in ("", "   \n", "def broken(:\n"):
        candidate = deepcopy(response)
        candidate["proposal"][field] = invalid
        with pytest.raises(ContractError):
            prepare_repository_copy_plan(request, candidate)
    with pytest.raises(ContractError):
        prepare_repository_copy_plan(request, _response(request, after=SOURCE))
