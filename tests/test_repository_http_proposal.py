"""Portable inert HTTP-proposal checks; no target, provider or guest is run."""

import json
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.analyzer.repository_input import CapturedFile, RepositoryInput
from authzest.codex import repository_http_proposal as contract
from authzest.codex import repository_proposal as legacy
from authzest.codex import repository_test_interface as test_interface
from authzest.codex.contracts import ContractError, canonical, identity

SOURCE = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    '@app.get("/things/{thing_id}")\n'
    "def get_thing(thing_id: str, reader: str):\n"
    '    return {"owner": reader}\n'
)
AFTER = SOURCE.replace('{"owner": reader}', '{"owner": reader, "checked": True}')
POLICY = "Only the authenticated owner may read a thing; other readers must be denied.\n"


def _file(path, text):
    try:
        digest = sha256(text.encode()).hexdigest()
    except UnicodeError:
        # A caller can forge the dataclass even though the filesystem loader
        # would never capture invalid UTF-8. Validation must reject it too.
        digest = "0" * 64
    return CapturedFile(path, text, digest)


def _snapshot(*, source=SOURCE, policy=POLICY, path="main.py"):
    return RepositoryInput(
        Path("/unshared/nonexistent/private-project"),
        path,
        "policy.md",
        (),
        (_file(path, source), _file("policy.md", policy)),
    )


@pytest.fixture
def request_data():
    return contract.build_repository_http_request(_snapshot(), "offline-model")


def _response(request, **changes):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "2.0",
        "kind": "repository-http-proposal",
        "request_id": request.request_id,
        "status": "proposed-change",
        "rationale": "A scripted candidate for a bounded ownership review.",
        "assumptions": ["Synthetic identities require independent review."],
        "uncertainties": [],
        "limitations": ["No observed HTTP response or verified repair is asserted."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": AFTER,
            "poc": {
                "method": "GET",
                "path": "/things/one",
                "headers": [{"name": "x-user-id", "value": "test-other"}],
            },
        },
    } | changes


def test_new_request_has_explicit_http_identity_and_no_local_oracle(request_data):
    data = request_data.to_dict()
    assert data["schema_version"] == "2.0"
    assert data["kind"] == "repository-http-proposal-request"
    assert request_data.request_id.startswith("repository-http-proposal-request-")
    assert data["selection"]["files"][0]["text"] == SOURCE
    assert data["selection"]["contexts"] == []
    assert "/things/{thing_id}" in canonical(data["evidence"])
    assert "/unshared/nonexistent" not in request_data.payload_json
    assert "available_to_owner" not in request_data.payload_json
    assert not {"test_path", "test_interface", "base_request_id", "cases", "expected"} & data.keys()
    interface = data["http_interface"]
    assert interface["entry_source"] == "main.py"
    assert interface["module"] == "main"
    assert interface["import_root"] == "."
    assert interface["app_attribute"] == "app"
    assert interface["lifespan"] == "off" and interface["auth_overrides"] == "none"
    assert interface["interface_id"].startswith("repository-http-interface-")
    assert data["output_schema"]["properties"]["request_id"]["enum"] == [request_data.request_id]
    assert contract.validate_repository_http_request(request_data) == request_data


def test_content_model_policy_and_app_entry_bind_identity(request_data):
    variants = [
        contract.build_repository_http_request(_snapshot(source=AFTER), "offline-model"),
        contract.build_repository_http_request(
            _snapshot(policy=POLICY + "No anonymous reads."), "offline-model"
        ),
        contract.build_repository_http_request(_snapshot(), "different-model"),
        contract.build_repository_http_request(_snapshot(), "offline-model", app_attribute="api"),
    ]
    assert len({request_data.request_id, *(item.request_id for item in variants)}) == 5
    same = contract.build_repository_http_request(
        replace(_snapshot(), root=Path("/another/unshared/root")), "offline-model"
    )
    assert same == request_data
    detached = request_data.to_dict()
    detached["selection"]["files"][0]["text"] = "changed"
    detached["http_interface"]["app_attribute"] = "changed"
    assert request_data.to_dict()["selection"]["files"][0]["text"] == SOURCE
    assert request_data.to_dict()["http_interface"]["app_attribute"] == "app"
    with pytest.raises(FrozenInstanceError):
        request_data.payload_json = "{}"


@pytest.mark.parametrize(
    "field",
    ["prompt", "host_instructions", "evidence", "output_schema", "http_interface", "request_id"],
)
def test_rehashed_supplied_request_cannot_redefine_the_protocol(request_data, field):
    data = request_data.to_dict()
    data[field] = {} if isinstance(data[field], dict) else "PRIVATE_FAKE_UNREVIEWED"
    data["request_id"] = "repository-http-proposal-request-" + identity(data)
    with pytest.raises(ContractError) as caught:
        contract.validate_repository_http_request(contract.RepositoryHttpRequest(canonical(data)))
    assert "PRIVATE_FAKE_UNREVIEWED" not in str(caught.value)


@pytest.mark.parametrize("field", ["schema_version", "kind", "request_id"])
def test_response_is_bound_to_this_mode_and_request(request_data, field):
    with pytest.raises(ContractError):
        contract.validate_repository_http_response(
            canonical(_response(request_data, **{field: "foreign"})), request_data
        )


def test_old_modes_cannot_be_silently_rewrapped_as_http_requests(request_data):
    previous = legacy.build_repository_request(_snapshot(), "offline-model")
    previous_test = test_interface.build_repository_test_request(previous, entry_source="main.py")
    old_json, test_json = previous.payload_json, previous_test.payload_json
    for old in (previous, previous_test, previous.to_dict(), request_data.to_dict()):
        with pytest.raises(ContractError):
            contract.validate_repository_http_request(old)
    for old_json_value in (old_json, test_json):
        with pytest.raises(ContractError):
            contract.validate_repository_http_request(
                contract.RepositoryHttpRequest(old_json_value)
            )
    with pytest.raises(ContractError):
        legacy.validate_repository_request(request_data)
    with pytest.raises(ContractError):
        test_interface.validate_repository_test_request(request_data)
    assert legacy.build_repository_request(_snapshot(), "offline-model").payload_json == old_json
    assert (
        test_interface.build_repository_test_request(previous, entry_source="main.py").payload_json
        == test_json
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/main.py",
        "pkg/main.py",
        "__init__.py",
        "class.py",
        "a-b.py",
        "é.py",
        "../other.py",
        "/main.py",
        ".hidden.py",
        "a\\main.py",
    ],
    ids=[
        "src",
        "package",
        "initializer",
        "keyword",
        "hyphen",
        "unicode",
        "traversal",
        "absolute",
        "hidden",
        "backslash",
    ],
)
def test_unsupported_source_layouts_are_rejected(path):
    with pytest.raises(ContractError):
        contract.build_repository_http_request(_snapshot(path=path), "offline-model")


@pytest.mark.parametrize("attribute", ["", "factory()", "obj.app", "class", "é", 1])
def test_app_attribute_is_one_explicit_plain_identifier(attribute):
    with pytest.raises(ContractError):
        contract.build_repository_http_request(
            _snapshot(), "offline-model", app_attribute=attribute
        )


def test_contexts_extra_files_and_rehashed_selected_bytes_are_not_adopted(request_data):
    snapshot = replace(
        _snapshot(), contexts=("auth.py",), files=(*_snapshot().files, _file("auth.py", SOURCE))
    )
    with pytest.raises(ContractError):
        contract.build_repository_http_request(snapshot, "offline-model")
    for mutation in ("extra-file", "wrong-digest", "stale-source"):
        data = request_data.to_dict()
        if mutation == "extra-file":
            data["selection"]["files"].append(_file("other.py", SOURCE).to_dict())
        elif mutation == "wrong-digest":
            data["selection"]["files"][0]["sha256"] = "0" * 64
        else:
            data["selection"]["files"][0] = _file("main.py", AFTER).to_dict()
        with pytest.raises(ContractError):
            contract.validate_repository_http_request(
                contract.RepositoryHttpRequest(canonical(data))
            )


@pytest.mark.parametrize(
    "source,policy",
    [
        ("x" * 16_385, POLICY),
        (SOURCE + "#" + "é" * 8200, POLICY),
        (SOURCE, "é" * 4097),
        (SOURCE, ""),
        (SOURCE, "\ud800"),
        ("\0" + SOURCE, POLICY),
        ("not valid ???", POLICY),
    ],
    ids=[
        "source-bytes",
        "source-utf8",
        "policy-utf8",
        "empty-policy",
        "surrogate-policy",
        "source-control",
        "invalid-python",
    ],
)
def test_selected_byte_text_and_python_bounds_precede_any_use(source, policy):
    with pytest.raises(ContractError):
        contract.build_repository_http_request(
            _snapshot(source=source, policy=policy), "offline-model"
        )


@pytest.mark.parametrize(
    "source",
    ["def ordinary():\n    return 1\n", SOURCE.replace("@app.get(", "@app.post(")],
    ids=["no-fastapi", "post-only"],
)
def test_no_supported_get_evidence_does_not_fall_back_to_a_fixed_demo(source):
    with pytest.raises(ContractError):
        contract.build_repository_http_request(_snapshot(source=source), "offline-model")


@pytest.mark.parametrize(
    "source",
    ["value=0\n" * 1200, "value=" + "not " * 70 + "True\n"],
    ids=["nodes", "depth"],
)
def test_selected_ast_budget_is_not_bypassed_by_http_mode(source):
    with pytest.raises(ContractError):
        contract.build_repository_http_request(_snapshot(source=SOURCE + source), "offline-model")


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_nonchange_artifacts_are_null_and_uncertainty_is_explicit(request_data, status):
    response = _response(
        request_data, status=status, proposal=None, uncertainties=["Insufficient reviewed context."]
    )
    assert contract.validate_repository_http_response(canonical(response), request_data) == response
    preview = contract.prepare_repository_http_preview(response, request_data)
    assert preview["changes"] == [] and preview["poc"] is None and preview["poc_sha256"] is None
    with pytest.raises(ContractError):
        contract.validate_repository_http_response(
            canonical(response | {"proposal": _response(request_data)["proposal"]}), request_data
        )
    if status in {"unknown", "refused"}:
        with pytest.raises(ContractError):
            contract.validate_repository_http_response(
                canonical(response | {"uncertainties": []}), request_data
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "success"),
        ("status", True),
        ("rationale", ""),
        ("assumptions", []),
        ("limitations", []),
        ("rationale", "é" * 4097),
    ],
    ids=["status", "status-type", "rationale", "assumptions", "limitations", "prose-bytes"],
)
def test_response_explanations_are_bounded_and_never_a_success_status(request_data, field, value):
    with pytest.raises(ContractError):
        contract.validate_repository_http_response(
            canonical(_response(request_data, **{field: value})), request_data
        )


@pytest.mark.parametrize("field", ["source_path", "before_sha256"])
def test_repair_cannot_retarget_another_source(request_data, field):
    response = _response(request_data)
    response["proposal"][field] = "PRIVATE_FAKE_FOREIGN_SOURCE"
    with pytest.raises(ContractError) as caught:
        contract.validate_repository_http_response(canonical(response), request_data)
    assert "PRIVATE_FAKE_FOREIGN_SOURCE" not in str(caught.value)


@pytest.mark.parametrize(
    "after",
    [
        SOURCE,
        "",
        "x" * 16_385,
        "x='é'" * 3000,
        "x='\0'",
        "\ud800",
        "value=0\n" * 1200,
        "PRIVATE_FAKE_INVALID ???",
    ],
    ids=["identical", "blank", "bytes", "utf8", "control", "surrogate", "nodes", "syntax"],
)
def test_generated_source_is_changed_bounded_inert_python(request_data, after):
    response = _response(request_data)
    response["proposal"]["after_text"] = after
    with pytest.raises(ContractError) as caught:
        contract.validate_repository_http_response(json.dumps(response), request_data)
    assert "PRIVATE_FAKE_INVALID" not in str(caught.value)


@pytest.mark.parametrize(
    "path",
    [
        "https://example.invalid/x",
        "//host/x",
        "/../x",
        "/x/./y",
        "/x?query=yes",
        "/x#fragment",
        "/x%2fy",
        "/x\\y",
        "/é",
        "/x\r\nInjected: yes",
        "x",
        "/" + "x" * 512,
    ],
    ids=[
        "url",
        "authority",
        "parent",
        "dot",
        "query",
        "fragment",
        "encoding",
        "backslash",
        "unicode",
        "control",
        "relative",
        "bytes",
    ],
)
def test_poc_paths_cannot_expand_network_or_request_scope(request_data, path):
    response = _response(request_data)
    response["proposal"]["poc"]["path"] = path
    with pytest.raises(ContractError):
        contract.validate_repository_http_response(canonical(response), request_data)


@pytest.mark.parametrize("method", ["POST", "HEAD", "get", "GET\r\n", 1, None])
def test_poc_method_is_exact_literal_get(request_data, method):
    response = _response(request_data)
    response["proposal"]["poc"]["method"] = method
    with pytest.raises(ContractError):
        contract.validate_repository_http_response(canonical(response), request_data)


@pytest.mark.parametrize(
    "headers",
    [
        {"x-user": "test-owner"},
        [{"name": "Authorization", "value": "test-token"}],
        [{"name": "cookie", "value": "test-cookie"}],
        [{"name": "host", "value": "test-host"}],
        [{"name": "X-User", "value": "test-owner"}],
        [{"name": "x-user", "value": "owner"}],
        [{"name": "x-user", "value": "test-"}],
        [{"name": "x-user", "value": "test-a\r\nHost:x"}],
        [{"name": "x-user", "value": "test-é"}],
        [{"name": "x-user", "value": "test-" + "a" * 60}],
        [{"name": "x-user", "value": "test-owner", "script": "run"}],
        [{"name": "x-user", "value": "test-owner"}] * 2,
        [{"name": "x-user", "value": "test-owner"}] * 4,
    ],
    ids=[
        "mapping",
        "authorization",
        "cookie",
        "host",
        "case",
        "real-looking-value",
        "empty",
        "injection",
        "unicode",
        "bytes",
        "extra",
        "duplicate",
        "count",
    ],
)
def test_headers_are_unique_bounded_synthetic_data_only(request_data, headers):
    response = _response(request_data)
    response["proposal"]["poc"]["headers"] = headers
    with pytest.raises(ContractError):
        contract.validate_repository_http_response(canonical(response), request_data)


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [
            {"name": "x-user", "value": "test-owner"},
            {"name": "x-user-id", "value": "test-1"},
            {"name": "x-role", "value": "test-reader"},
        ],
    ],
    ids=["anonymous", "all-synthetic"],
)
def test_allowed_synthetic_requests_are_detached_data_not_observations(request_data, headers):
    response = _response(request_data)
    response["proposal"]["poc"]["headers"] = headers
    assert contract.validate_repository_http_response(canonical(response), request_data) == response
    preview = contract.prepare_repository_http_preview(response, request_data)
    preview["poc"]["headers"].append({"name": "x-user", "value": "test-edited"})
    assert (
        contract.prepare_repository_http_preview(response, request_data)["poc"]
        == response["proposal"]["poc"]
    )


@pytest.mark.parametrize("field", ["expected", "response", "assertion", "python", "command", "url"])
def test_model_poc_cannot_supply_its_own_oracle_or_program(request_data, field):
    response = _response(request_data)
    response["proposal"]["poc"][field] = "PRIVATE_FAKE_AUTHORITY"
    with pytest.raises(ContractError) as caught:
        contract.validate_repository_http_response(canonical(response), request_data)
    assert "PRIVATE_FAKE_AUTHORITY" not in str(caught.value)


def test_closed_json_rejects_extra_fields_duplicates_nonfinite_and_oversize(request_data):
    response = _response(request_data)
    for raw in (
        canonical(response | {"verified_fix": True}),
        '{"status":"unknown",' + canonical(response)[1:],
        canonical(response).replace('"proposal":{', '"proposal":{"extra":NaN,', 1),
        canonical(response) + " " * 262_144,
        "[]",
    ):
        with pytest.raises(ContractError):
            contract.validate_repository_http_response(raw, request_data)


def test_preview_binds_full_response_and_poc_but_has_no_execution_authority(request_data):
    response = _response(request_data)
    preview = contract.prepare_repository_http_preview(response, request_data)
    assert preview["response_id"] == "repository-http-proposal-response-" + identity(response)
    assert preview["poc_sha256"] == identity(response["proposal"]["poc"])
    assert preview["poc"] == response["proposal"]["poc"]
    assert len(preview["changes"]) == 1
    source = preview["changes"][0]
    assert source["path"] == "main.py"
    assert source["before_sha256"] == sha256(SOURCE.encode()).hexdigest()
    assert source["after_sha256"] == sha256(AFTER.encode()).hexdigest()
    assert '-    return {"owner": reader}\n' in source["diff"]
    assert '+    return {"owner": reader, "checked": True}\n' in source["diff"]
    assert (
        preview["execution_status"]
        == preview["patch_application"]
        == preview["restoration_status"]
        == "not-run"
    )
    assert preview["authorization_status"] == "unknown" and preview["verified_fix"] is False
    assert (
        not {"test_path", "test_path_checked", "test_results", "pytest", "T", "decision"}
        & preview.keys()
    )
    changed = deepcopy(response)
    changed["rationale"] += " A different claim."
    assert (
        contract.prepare_repository_http_preview(changed, request_data)["response_id"]
        != preview["response_id"]
    )
    changed = deepcopy(response)
    changed["proposal"]["poc"]["path"] = "/things/two"
    assert (
        contract.prepare_repository_http_preview(changed, request_data)["poc_sha256"]
        != preview["poc_sha256"]
    )


def test_complete_output_schema_is_closed_and_header_objects_have_explicit_keys(request_data):
    schema = request_data.to_dict()["output_schema"]
    pending = [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)


def test_ast_only_data_and_host_diff_never_open_import_or_execute_target(tmp_path, monkeypatch):
    marker = tmp_path / "must-not-exist"
    trap = f"open({str(marker)!r}, 'w').write('executed')\nraise RuntimeError('target trap')\n"
    snapshot = _snapshot(source=SOURCE + trap)

    def forbidden(*_args, **_kwargs):
        pytest.fail("The HTTP contract must not open target or artifact files")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        request = contract.build_repository_http_request(snapshot, "offline-model")
        response = _response(request)
        response["proposal"]["after_text"] = AFTER + trap
        preview = contract.prepare_repository_http_preview(response, request)
    assert not marker.exists()
    assert preview["execution_status"] == "not-run" and preview["verified_fix"] is False


def test_source_diff_preserves_exact_missing_final_lf():
    request = contract.build_repository_http_request(
        _snapshot(source=SOURCE.rstrip("\n")), "offline-model"
    )
    response = _response(request)
    response["proposal"]["after_text"] = AFTER.rstrip("\n")
    source = contract.prepare_repository_http_preview(response, request)["changes"][0]
    assert source["diff"].count("\\ No newline at end of file\n") == 2
    assert source["after_sha256"] == sha256(AFTER.rstrip("\n").encode()).hexdigest()
    assert source["after_sha256"] != sha256(AFTER.encode()).hexdigest()
