"""External captured-source contracts without importing, sharing or executing code."""

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.analyzer.repository_input import CapturedFile, RepositoryInput
from authzest.codex import repository_proposal as contract
from authzest.codex.contracts import ContractError, canonical

SOURCE = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n"
    '@app.get("/things/{thing_id}")\n'
    "def get_thing(thing_id: str, reader: str):\n"
    '    return {"owner": reader}\n'
)
AFTER = SOURCE.replace('{"owner": reader}', '{"owner": reader, "checked": True}')
TEST = 'def test_owner_access(client):\n    assert client.get("/things/one").status_code == 200\n'
POLICY = "Only the authenticated owner may read a thing; other readers must be denied.\n"


def _file(path, text):
    return CapturedFile(path, text, sha256(text.encode()).hexdigest())


def _snapshot(*, root=Path("/unshared/private/root"), source=SOURCE, context=None):
    contexts = ("auth.py",) if context is not None else ()
    files = (_file("main.py", source), _file("policy.md", POLICY))
    if context is not None:
        files += (_file("auth.py", context),)
    return RepositoryInput(root, "main.py", "policy.md", contexts, files)


@pytest.fixture
def request_data():
    return contract.build_repository_request(_snapshot(), "offline-model")


def _response(request, **changes):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": "proposed-change",
        "rationale": "Proposed owner-access regression and a source adjustment.",
        "assumptions": ["The caller must supply a client fixture with representative identities."],
        "uncertainties": [],
        "limitations": ["No target import, runtime check or policy verification was performed."],
        "proposal": {
            "source_path": source["path"],
            "before_sha256": source["sha256"],
            "after_text": AFTER,
            "test_path": contract.TEST_PATH,
            "test_text": TEST,
        },
    } | changes


def test_actual_selected_bytes_and_context_drive_the_request_without_local_root(request_data):
    data = request_data.to_dict()
    assert data["selection"]["files"][0]["text"] == SOURCE
    assert "/things/{thing_id}" in canonical(data["evidence"])
    assert data["evidence"]["scope"] == "selected-file-declarations-only"
    assert data["evidence"]["analysis_status"] == "partial"
    assert "/unshared/private/root" not in request_data.payload_json
    assert "owner-archived-read" not in request_data.payload_json
    assert "available_to_owner" not in request_data.payload_json
    assert data["host_instructions"] == contract.REPOSITORY_HOST_INSTRUCTIONS
    assert data["output_schema"]["properties"]["request_id"]["enum"] == [request_data.request_id]

    same_bytes_other_root = contract.build_repository_request(
        _snapshot(root=Path("/another/project")), "offline-model"
    )
    assert same_bytes_other_root == request_data
    changed = contract.build_repository_request(_snapshot(source=AFTER), "offline-model")
    related = contract.build_repository_request(
        _snapshot(context="def authenticate(reader):\n    return reader\n"), "offline-model"
    )
    assert changed.request_id != request_data.request_id
    assert related.request_id != request_data.request_id
    assert related.to_dict()["selection"]["files"][2]["path"] == "auth.py"


def test_request_identity_binds_model_policy_and_every_selected_file(request_data):
    other_model = contract.build_repository_request(_snapshot(), "other-model")
    policy_changed = replace(
        _snapshot(),
        files=(_file("main.py", SOURCE), _file("policy.md", POLICY + "No anonymous reads.")),
    )
    other_policy = contract.build_repository_request(policy_changed, "offline-model")
    assert len({request_data.request_id, other_model.request_id, other_policy.request_id}) == 3
    assert contract.validate_repository_request(request_data) == request_data
    detached = request_data.to_dict()
    detached["selection"]["files"][0]["text"] = "not Python"
    assert request_data.to_dict()["selection"]["files"][0]["text"] == SOURCE


def test_router_expansion_is_rejected_inside_the_parser_budget():
    # Only the fixed bounded path is called; the old unbounded graph is not run.
    source = (
        "from fastapi import APIRouter\nr0 = APIRouter()\n"
        "@r0.get('/item')\ndef item():\n    return 1\n"
    )
    for index in range(1, 25):
        source += (
            f"r{index} = APIRouter()\n"
            f"r{index}.include_router(r{index - 1})\n"
            f"r{index}.include_router(r{index - 1})\n"
        )
    with pytest.raises(ContractError) as error:
        contract.build_repository_request(_snapshot(source=source), "offline-model")
    assert error.value.code == "validation-budget"
    assert str(error.value) == "Selected source inventory budget exceeded"


def test_selected_source_diagnostics_are_rejected_inside_the_parser_budget():
    source = "from fastapi import FastAPI\napp = FastAPI()\n" + "".join(
        f"@app.get(dynamic_path)\ndef item_{index}():\n    return {index}\n" for index in range(65)
    )
    with pytest.raises(ContractError) as error:
        contract.build_repository_request(_snapshot(source=source), "offline-model")
    assert error.value.code == "validation-budget"
    assert str(error.value) == "Selected source inventory budget exceeded"


@pytest.mark.parametrize(
    "field", ["request_id", "host_instructions", "prompt", "evidence", "test_path", "output_schema"]
)
def test_rehashed_or_changed_wire_fields_cannot_extend_the_contract(request_data, field):
    data = request_data.to_dict()
    data[field] = {} if isinstance(data[field], dict) else "changed"
    forged = contract.RepositoryProposalRequest(canonical(data))
    with pytest.raises(ContractError):
        contract.validate_repository_request(forged)


@pytest.mark.parametrize("name", ["source_path", "before_sha256", "test_path"])
def test_response_cannot_change_an_unselected_path_or_source_binding(request_data, name):
    response = _response(request_data)
    response["proposal"][name] = "../unselected.py"
    with pytest.raises(ContractError) as caught:
        contract.validate_repository_response(canonical(response), request_data)
    assert caught.value.code == "validation-identity"
    assert "unselected" not in str(caught.value)


@pytest.mark.parametrize("field", ["request_id", "schema_version"])
def test_response_identity_must_match_current_request(request_data, field):
    response = _response(request_data, **{field: "wrong"})
    with pytest.raises(ContractError):
        contract.validate_repository_response(canonical(response), request_data)


def test_exact_host_diff_and_hashes_do_not_read_a_proposed_test_file(request_data, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("A pure contract must never open target files")

    monkeypatch.setattr(Path, "open", forbidden)
    response = _response(request_data)
    checked = contract.validate_repository_response(canonical(response), request_data)
    preview = contract.prepare_repository_preview(checked, request_data)
    source, test = preview["changes"]
    assert source["before_text"] == SOURCE and source["after_text"] == AFTER
    assert source["after_sha256"] == sha256(AFTER.encode()).hexdigest()
    assert '-    return {"owner": reader}\n' in source["diff"]
    assert '+    return {"owner": reader, "checked": True}\n' in source["diff"]
    assert test["after_sha256"] == sha256(TEST.encode()).hexdigest()
    assert test["before_sha256"] is None and test["before_text"] is None
    assert test["basis"] == "empty-artifact-not-target-file"
    assert "<uninspected-test-path>" in test["diff"]
    assert preview["test_path_checked"] is False
    assert preview["execution_status"] == preview["patch_application"] == "not-run"
    assert preview["authorization_status"] == "unknown"


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_non_change_results_require_null_artifacts_and_unknown_requires_uncertainty(
    request_data, status
):
    response = _response(
        request_data, status=status, proposal=None, uncertainties=["Missing context."]
    )
    assert contract.validate_repository_response(canonical(response), request_data) == response
    assert contract.prepare_repository_preview(response, request_data)["changes"] == []
    with pytest.raises(ContractError):
        contract.validate_repository_response(
            canonical(response | {"proposal": _response(request_data)["proposal"]}), request_data
        )
    if status in {"unknown", "refused"}:
        with pytest.raises(ContractError):
            contract.validate_repository_response(
                canonical(response | {"uncertainties": []}), request_data
            )


@pytest.mark.parametrize("field", ["assumptions", "limitations", "rationale"])
def test_missing_explanations_are_not_accepted_as_a_proposal(request_data, field):
    with pytest.raises(ContractError):
        contract.validate_repository_response(
            canonical(_response(request_data, **{field: [] if field != "rationale" else ""})),
            request_data,
        )


@pytest.mark.parametrize("field", ["after_text", "test_text"])
@pytest.mark.parametrize(
    "code", ["x" * 16_385, "\ud800", "private-secret ???", "x = '\x00'", "x = 'é'" * 3000]
)
def test_bad_or_oversized_generated_python_is_rejected_without_echo(request_data, field, code):
    response = _response(request_data)
    response["proposal"][field] = code
    with pytest.raises(ContractError) as caught:
        contract.validate_repository_response(json.dumps(response, ensure_ascii=True), request_data)
    assert "private-secret" not in str(caught.value)


def test_ast_parsing_is_not_execution_or_a_claim_of_safety(request_data, tmp_path):
    marker = tmp_path / "executed"
    hostile = f"open({str(marker)!r}, 'w').write('executed')\n"
    selection = _snapshot(source=SOURCE + hostile)
    captured = contract.build_repository_request(selection, "offline-model")
    response = _response(captured)
    response["proposal"]["after_text"] = AFTER + hostile
    response["proposal"]["test_text"] = hostile + TEST
    preview = contract.prepare_repository_preview(response, captured)
    assert not marker.exists()
    assert preview["execution_status"] == "not-run"
    assert any("not compiled" in text for text in preview["limitations"])


def test_invalid_selected_python_and_unsupported_source_never_fall_back_to_fixture():
    for text in ("private-secret invalid ???", "def ordinary():\n    return True\n"):
        with pytest.raises(ContractError) as caught:
            contract.build_repository_request(_snapshot(source=text), "offline-model")
        assert "private-secret" not in str(caught.value)
    related = _snapshot(source="def authorize(reader):\n    return True\n", context=SOURCE)
    assert contract.build_repository_request(related, "offline-model").to_dict()["evidence"][
        "routes"
    ]


def test_source_warnings_do_not_print_captured_text(capsys):
    snapshot = _snapshot(source=SOURCE + "secret = 'private\\q'\n")
    contract.build_repository_request(snapshot, "offline-model")
    assert capsys.readouterr().err == ""


def test_request_manifest_rejects_tampered_or_extra_files(request_data):
    original = request_data.to_dict()
    variants = []
    data = request_data.to_dict()
    data["selection"]["files"][0]["sha256"] = "0" * 64
    variants.append(data)
    data = request_data.to_dict()
    data["selection"]["files"].append(_file("unselected.py", SOURCE).to_dict())
    variants.append(data)
    data = request_data.to_dict()
    data["selection"]["contexts"] = ["main.py"]
    variants.append(data)
    for changed in variants:
        with pytest.raises(ContractError):
            contract.validate_repository_request(
                contract.RepositoryProposalRequest(canonical(changed))
            )
    assert original == request_data.to_dict()


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "/absolute.py",
        "a/./main.py",
        ".hidden.py",
        "a\\main.py",
        "a:main.py",
        "a/\u202emain.py",
        contract.TEST_PATH,
    ],
)
def test_pure_request_construction_also_rejects_unsafe_selected_paths(path):
    snapshot = replace(
        _snapshot(), source=path, files=(_file(path, SOURCE), _file("policy.md", POLICY))
    )
    with pytest.raises(ContractError):
        contract.build_repository_request(snapshot, "offline-model")


def test_response_extras_duplicate_keys_and_oversize_are_rejected(request_data):
    response = _response(request_data)
    for raw in (
        canonical(response | {"execute": "now"}),
        '{"status":"unknown",' + canonical(response)[1:],
        canonical(response) + " " * 262_144,
    ):
        with pytest.raises(ContractError):
            contract.validate_repository_response(raw, request_data)


@pytest.mark.parametrize("extra", ["value = 0\n" * 1200, "value = " + "not " * 70 + "True\n"])
def test_large_or_deep_selected_ast_fails_before_inventory(extra):
    with pytest.raises(ContractError) as caught:
        contract.build_repository_request(_snapshot(source=SOURCE + extra), "offline-model")
    assert caught.value.code == "validation-budget"


def test_escaping_expansion_must_also_fit_the_complete_transport_budget():
    # The selected raw files fit their individual and total limits. Nested JSON
    # escaping of the exact prompt/envelope still has its own smaller effective bound.
    padding = "payload = " + repr("\\" * 7000) + "\n"
    contexts = ("a.py", "b.py", "c.py")
    snapshot = replace(
        _snapshot(source=SOURCE + padding),
        contexts=contexts,
        files=(
            _file("main.py", SOURCE + padding),
            _file("policy.md", POLICY),
            *(_file(path, padding) for path in contexts),
        ),
    )
    assert sum(len(file.text.encode()) for file in snapshot.files) < 65_536
    with pytest.raises(ContractError) as caught:
        contract.build_repository_request(snapshot, "offline-model")
    assert caught.value.code == "validation-budget"


def test_generated_identical_source_is_no_change_not_a_proposed_change(request_data):
    response = _response(request_data)
    response["proposal"]["after_text"] = SOURCE
    with pytest.raises(ContractError):
        contract.validate_repository_response(canonical(response), request_data)


def test_exact_diff_retains_missing_final_lf_and_does_not_change_raw_hashes():
    request = contract.build_repository_request(
        _snapshot(source=SOURCE.rstrip("\n")), "offline-model"
    )
    response = _response(request)
    response["proposal"]["after_text"] = AFTER.rstrip("\n")
    response["proposal"]["test_text"] = TEST.rstrip("\n")
    source, test = contract.prepare_repository_preview(response, request)["changes"]
    assert source["diff"].count("\\ No newline at end of file\n") == 2
    assert test["diff"].count("\\ No newline at end of file\n") == 1
    assert source["after_sha256"] == sha256(AFTER.rstrip("\n").encode()).hexdigest()
    assert source["after_sha256"] != sha256(AFTER.encode()).hexdigest()


@pytest.mark.parametrize("blank", ["", " \t\n\r\n"])
def test_blank_selected_python_is_preserved_when_another_selected_file_has_a_route(blank):
    context_snapshot = _snapshot(context=blank)
    context_request = contract.build_repository_request(context_snapshot, "offline-model")
    context_file = context_request.to_dict()["selection"]["files"][2]
    assert context_file["text"] == blank
    assert context_file["sha256"] == sha256(blank.encode()).hexdigest()
    assert contract.validate_repository_request(context_request) == context_request

    source_request = contract.build_repository_request(
        _snapshot(source=blank, context=SOURCE), "offline-model"
    )
    source_data = source_request.to_dict()
    assert source_data["selection"]["files"][0]["text"] == blank
    assert source_data["evidence"]["routes"][0]["file"] == "auth.py"
    assert contract.validate_repository_request(source_request) == source_request


@pytest.mark.parametrize("blank", ["", " \t\n\r\n"])
def test_all_blank_selected_python_still_fails_without_fastapi_evidence(blank):
    with pytest.raises(ContractError) as caught:
        contract.build_repository_request(_snapshot(source=blank, context=blank), "offline-model")
    assert caught.value.code == "validation-evidence"


@pytest.mark.parametrize("blank", ["", " \t\n\r\n"])
def test_blank_policy_and_generated_python_remain_rejected(request_data, blank):
    snapshot = replace(_snapshot(), files=(_file("main.py", SOURCE), _file("policy.md", blank)))
    with pytest.raises(ContractError):
        contract.build_repository_request(snapshot, "offline-model")
    for key in ("after_text", "test_text"):
        response = _response(request_data)
        response["proposal"][key] = blank
        with pytest.raises(ContractError):
            contract.validate_repository_response(canonical(response), request_data)


@pytest.mark.parametrize("invalid", ["\0", "\x0c", "\ud800"])
def test_selected_python_allow_blank_keeps_control_and_utf8_validation(invalid):
    snapshot = _snapshot(context="")
    snapshot = replace(
        snapshot, files=(*snapshot.files[:2], replace(snapshot.files[2], text=invalid))
    )
    with pytest.raises(ContractError):
        contract.build_repository_request(snapshot, "offline-model")
