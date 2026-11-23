"""Pure versioned interfaces; target/test text and fixture declarations never run."""

import builtins
import io
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.analyzer.repository_input import CapturedFile, RepositoryInput
from authzest.codex import repository_proposal as legacy
from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.repository_test_interface import (
    RepositoryTestRequest,
    build_repository_test_request,
    prepare_repository_test_preview,
    validate_repository_test_request,
    validate_repository_test_response,
)

SOURCE = (
    "from fastapi import FastAPI\napp = FastAPI()\n"
    '@app.get("/items")\ndef read():\n    return {"allowed": False}\n'
)
POLICY = "Only an authenticated owner may read an item.\n"
AFTER = SOURCE.replace("False", "True")
TEST = 'raise RuntimeError("INERT TEST MUST NEVER EXECUTE")\n'


def _file(path, text):
    return CapturedFile(path, text, sha256(text.encode("utf-8")).hexdigest())


def _base(
    *, source_path="main.py", source=SOURCE, contexts=(), model="offline-model", policy=POLICY
):
    snapshot = RepositoryInput(
        Path("/unused/private/root"),
        source_path,
        "policy.md",
        tuple(path for path, _ in contexts),
        (
            _file(source_path, source),
            _file("policy.md", policy),
            *(_file(path, text) for path, text in contexts),
        ),
    )
    return legacy.build_repository_request(snapshot, model)


def _request(**kwargs):
    return build_repository_test_request(
        _base(**kwargs), entry_source=kwargs.get("source_path", "main.py")
    )


def _response(request, *, status="proposed-change"):
    source = request.to_dict()["selection"]["files"][0]
    return {
        "schema_version": "1.1",
        "request_id": request.request_id,
        "status": status,
        "rationale": "A synthetic source and client-fixture regression proposal.",
        "assumptions": ["The declared client fixture is provided later, not observed here."],
        "uncertainties": ["No imports or runtime checks."],
        "limitations": ["No policy or safety assurance."],
        "proposal": (
            {
                "source_path": source["path"],
                "before_sha256": source["sha256"],
                "after_text": AFTER,
                "test_path": legacy.TEST_PATH,
                "test_text": TEST,
            }
            if status == "proposed-change"
            else None
        ),
    }


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected filesystem, network, process or code execution")

    # All imports are complete; ast.parse's compile-to-AST remains supported.
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


def test_v1_0_golden_identity_and_payload_stay_unchanged_after_opt_in():
    base = _base()
    before = base.payload_json
    assert base.request_id == (
        "repository-proposal-request-ce033a18d787a15fcb2e1075200926967231bfa216ecf8b993635621d7b0f0f1"
    )
    assert (
        sha256(before.encode()).hexdigest()
        == "75b37f0aad1fd6b3d09d058f28d9fc61cb5abfe32ac7d6f505114d4c529e080f"
    )
    request = build_repository_test_request(base, entry_source="main.py")
    assert base.payload_json == before == _base().payload_json
    assert request.request_id != base.request_id
    assert legacy.validate_repository_request(base) == base
    with pytest.raises(ContractError):
        legacy.validate_repository_request(request)
    with pytest.raises(ContractError):
        validate_repository_test_request(base)


def test_complete_model_visible_interface_and_host_schema_are_bound_without_cases():
    base = _base(contexts=(("auth.py", "ROLE = 'test-owner'\n"),))
    request = build_repository_test_request(base, entry_source="main.py")
    data = request.to_dict()
    body = {
        "schema_version": "1.0",
        "entry_source": "main.py",
        "import_root": ".",
        "module": "main",
        "app_attribute": "app",
        "fixture": "client",
        "lifespan": "off",
        "auth_overrides": "none",
    }
    assert data["test_interface"] == {
        **body,
        "interface_id": "repository-test-interface-" + identity(body),
    }
    assert data["schema_version"] == "1.1"
    assert data["kind"] == "repository-test-proposal-request"
    assert data["base_request_id"] == base.request_id
    assert data["selection"] == base.to_dict()["selection"]
    assert data["evidence"] == base.to_dict()["evidence"]
    assert data["config"]["prompt_version"] == "external-repository-test-proposal-v1.1"
    assert data["config"]["model"] == "offline-model"
    assert data["output_schema"]["properties"]["schema_version"]["enum"] == ["1.1"]
    assert data["output_schema"]["properties"]["request_id"]["enum"] == [request.request_id]
    assert data["prompt"].endswith("REQUEST_ID: " + request.request_id)
    assert "trusted in-process client fixture named client" in data["prompt"]
    assert "no authentication overrides" in data["prompt"]
    assert "remain unverified until runtime" in data["prompt"]
    assert "Independent policy expectations are host-only" in data["prompt"]
    assert "Do not use tools" in data["host_instructions"]
    assert "base_request" not in data and "cases" not in data and "expected_answers" not in data
    assert base.to_dict()["prompt"] not in data["prompt"]
    assert "/unused/private/root" not in request.payload_json
    assert validate_repository_test_request(request) == request


@pytest.mark.parametrize(
    "source_path,contexts,entry,root,module",
    [
        ("main.py", (), "main.py", ".", "main"),
        ("pkg/api.py", (("pkg/__init__.py", ""),), "pkg/api.py", ".", "pkg.api"),
        ("pkg/__init__.py", (), "pkg/__init__.py", ".", "pkg"),
        ("pkg/main.py", (("pkg/__init__.py", ""),), "pkg/__init__.py", ".", "pkg"),
        ("src/api.py", (), "src/api.py", "src", "api"),
        ("src/pkg/api.py", (("src/pkg/__init__.py", ""),), "src/pkg/api.py", "src", "pkg.api"),
        ("src/pkg/__init__.py", (), "src/pkg/__init__.py", "src", "pkg"),
        (
            "pkg/deep/api.py",
            (("pkg/__init__.py", ""), ("pkg/deep/__init__.py", "")),
            "pkg/deep/api.py",
            ".",
            "pkg.deep.api",
        ),
    ],
)
def test_explicit_module_derivation_and_selected_initializers(
    source_path, contexts, entry, root, module
):
    base = _base(source_path=source_path, contexts=contexts)
    request = build_repository_test_request(
        base, entry_source=entry, import_root=root, app_attribute="asgi_app"
    )
    interface = request.to_dict()["test_interface"]
    assert interface["module"] == module
    assert interface["app_attribute"] == "asgi_app"
    assert validate_repository_test_request(request) == request


@pytest.mark.parametrize(
    "source_path,contexts,settings",
    [
        ("main.py", (), {"entry_source": "unselected.py"}),
        ("main.py", (), {"entry_source": True}),
        ("main.py", (), {"entry_source": "main.py", "import_root": True}),
        ("main.py", (), {"entry_source": "main.py", "import_root": "/tmp"}),
        ("main.py", (), {"entry_source": "main.py", "import_root": "src"}),
        ("main.py", (), {"entry_source": "main.py", "app_attribute": True}),
        ("main.py", (), {"entry_source": "main.py", "app_attribute": "app()"}),
        ("main.py", (), {"entry_source": "main.py", "app_attribute": "factory:app"}),
        ("main.py", (), {"entry_source": "main.py", "app_attribute": "module.app"}),
        ("main.py", (), {"entry_source": "main.py", "app_attribute": "class"}),
        ("main.py", (), {"entry_source": "main.py", "app_attribute": "앱"}),
        ("pkg/main.py", (), {"entry_source": "pkg/main.py"}),
        ("pkg/deep/main.py", (("pkg/__init__.py", ""),), {"entry_source": "pkg/deep/main.py"}),
        ("pkg/deep/main.py", (("pkg/deep/__init__.py", ""),), {"entry_source": "pkg/deep/main.py"}),
        ("__init__.py", (), {"entry_source": "__init__.py"}),
        ("src/__init__.py", (), {"entry_source": "src/__init__.py", "import_root": "src"}),
        ("src/main.py", (("auth.py", ""),), {"entry_source": "src/main.py", "import_root": "src"}),
        ("pkg-name/main.py", (("pkg-name/__init__.py", ""),), {"entry_source": "pkg-name/main.py"}),
        ("class.py", (), {"entry_source": "class.py"}),
        ("앱.py", (), {"entry_source": "앱.py"}),
        ("Main.py", (("main.py", ""),), {"entry_source": "Main.py"}),
        ("pkg.py", (("pkg.py/child.py", ""),), {"entry_source": "pkg.py"}),
        ("main.py", ((legacy.TEST_PATH + "/child.py", ""),), {"entry_source": "main.py"}),
    ],
)
def test_unsupported_namespace_path_factory_or_setup_is_rejected(source_path, contexts, settings):
    with pytest.raises(ContractError):
        build_repository_test_request(_base(source_path=source_path, contexts=contexts), **settings)


@pytest.mark.parametrize(
    "field",
    [
        "request_id",
        "base_request_id",
        "schema_version",
        "kind",
        "host_instructions",
        "prompt",
        "evidence",
        "test_path",
        "output_schema",
    ],
)
def test_host_derived_request_material_cannot_be_tampered_even_when_rehashed(field):
    request = _request()
    data = request.to_dict()
    data[field] = {} if type(data[field]) is dict else "tampered"
    data["request_id"] = "repository-test-proposal-request-" + identity(data)
    with pytest.raises(ContractError):
        validate_repository_test_request(RepositoryTestRequest(canonical(data)))


@pytest.mark.parametrize(
    "field", ["module", "fixture", "lifespan", "auth_overrides", "interface_id", "schema_version"]
)
def test_derived_interface_fields_reconstruct_exactly(field):
    data = _request().to_dict()
    data["test_interface"][field] = "tampered"
    body = {k: v for k, v in data["test_interface"].items() if k != "interface_id"}
    if field != "interface_id":
        data["test_interface"]["interface_id"] = "repository-test-interface-" + identity(body)
    with pytest.raises(ContractError):
        validate_repository_test_request(RepositoryTestRequest(canonical(data)))


@pytest.mark.parametrize("field", ["model", "policy", "source", "context", "app", "entry", "root"])
def test_interface_request_ids_bind_every_current_declared_input(field):
    base = _base(contexts=(("other.py", ""),))
    first = build_repository_test_request(base, entry_source="main.py")
    if field == "model":
        second = _request(model="different-model", contexts=(("other.py", ""),))
    elif field == "policy":
        second = _request(policy=POLICY + "No anonymous readers.\n", contexts=(("other.py", ""),))
    elif field == "source":
        second = _request(source=SOURCE + "# captured edit\n", contexts=(("other.py", ""),))
    elif field == "context":
        second = _request(contexts=(("other.py", "ROLE = 'test-other'\n"),))
    elif field == "app":
        second = build_repository_test_request(
            base, entry_source="main.py", app_attribute="application"
        )
    elif field == "entry":
        second = build_repository_test_request(base, entry_source="other.py")
    else:
        src = _base(source_path="src/main.py", contexts=(("src/__init__.py", ""),))
        first = build_repository_test_request(src, entry_source="src/main.py", import_root="src")
        second = build_repository_test_request(src, entry_source="src/main.py", import_root=".")
    assert first.request_id != second.request_id


def test_extra_cases_setup_and_adapter_options_are_not_accepted_or_model_visible():
    request = _request()
    for field in (
        "expected_answers",
        "cases",
        "case_ids",
        "dependency_install",
        "runtime_approved",
    ):
        data = request.to_dict()
        data[field] = ["host-only-marker"]
        with pytest.raises(ContractError):
            validate_repository_test_request(RepositoryTestRequest(canonical(data)))
        data = request.to_dict()
        data["test_interface"][field] = True
        with pytest.raises(ContractError):
            validate_repository_test_request(RepositoryTestRequest(canonical(data)))
    data = request.to_dict()
    data["config"]["temperature"] = 0.1
    with pytest.raises(ContractError):
        validate_repository_test_request(RepositoryTestRequest(canonical(data)))
    with pytest.raises(TypeError):
        build_repository_test_request(_base(), entry_source="main.py", expected_answers=[])


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_all_response_statuses_keep_1_1_identity_without_runtime_or_file_authority(status):
    request = _request()
    response = _response(request, status=status)
    assert validate_repository_test_response(canonical(response), request) == response
    preview = prepare_repository_test_preview(response, request)
    assert preview["schema_version"] == "1.1"
    assert preview["request_id"] == request.request_id
    assert preview["test_interface"] == request.to_dict()["test_interface"]
    assert preview["proposal_status"] == status
    assert preview["execution_status"] == preview["patch_application"] == "not-run"
    assert (
        preview["restoration_status"] == "not-run" and preview["authorization_status"] == "unknown"
    )
    assert preview["test_path_checked"] is False
    assert len(preview["changes"]) == (2 if status == "proposed-change" else 0)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "request_id",
        "source_path",
        "before_sha256",
        "test_path",
        "after_text",
        "test_text",
        "extra",
        "empty_assumptions",
        "wrong_status_payload",
    ],
)
def test_response_version_identity_and_structural_restrictions_still_apply(field):
    request = _request()
    response = _response(request)
    if field == "schema_version":
        response[field] = "1.0"
    elif field == "request_id":
        response[field] = request.to_dict()["base_request_id"]
    elif field in {"source_path", "before_sha256", "test_path"}:
        response["proposal"][field] = "tampered"
    elif field == "after_text":
        response["proposal"][field] = SOURCE
    elif field == "test_text":
        response["proposal"][field] = "def broken(\n"
    elif field == "empty_assumptions":
        response["assumptions"] = []
    elif field == "wrong_status_payload":
        response["status"] = "no-change"
    else:
        response["runtime_success"] = True
    with pytest.raises(ContractError):
        validate_repository_test_response(canonical(response), request)


def test_inert_source_is_not_executed_and_json_objects_are_detached_frozen():
    request = _request(source=SOURCE + 'raise RuntimeError("DO NOT EXECUTE SOURCE")\n')
    assert validate_repository_test_request(request) == request
    response = _response(request)
    preview = prepare_repository_test_preview(response, request)
    assert preview["changes"][1]["after_text"] == TEST
    detached = request.to_dict()
    detached["test_interface"]["fixture"] = "forged"
    assert request.to_dict()["test_interface"]["fixture"] == "client"
    with pytest.raises(FrozenInstanceError):
        request.payload_json = "{}"
    assert not any(hasattr(request, name) for name in ("run", "approve", "apply", "open", "resume"))


@pytest.mark.parametrize(
    "source_path,contexts,entry,root",
    [
        ("pkg.py", (("pkg/__init__.py", ""),), "pkg.py", "."),
        ("pkg.py", (("pkg/__init__.py", ""),), "pkg/__init__.py", "."),
        ("main.py", (("main/__init__.py", ""),), "main.py", "."),
        ("src/pkg.py", (("src/pkg/__init__.py", ""),), "src/pkg.py", "src"),
        ("src/main.py", (("src/main/__init__.py", ""),), "src/main/__init__.py", "src"),
        ("pkg.py", (("pkg/child.py", ""),), "pkg.py", "."),
        ("src/pkg.py", (("src/pkg/child.py", ""),), "src/pkg.py", "src"),
        ("Main.py", (("main/__init__.py", ""),), "Main.py", "."),
        (
            "pkg/main.py",
            (("pkg/__init__.py", ""), ("pkg/main/__init__.py", "")),
            "pkg/main.py",
            ".",
        ),
    ],
)
def test_selected_file_package_and_submodule_aliases_are_rejected(
    source_path, contexts, entry, root
):
    base = _base(source_path=source_path, contexts=contexts)
    with pytest.raises(ContractError, match="ambiguous|submodules"):
        build_repository_test_request(base, entry_source=entry, import_root=root)


def test_distinct_package_with_selected_children_remains_supported():
    base = _base(
        source_path="src/pkg/main.py",
        contexts=(("src/pkg/__init__.py", ""), ("src/pkg/child.py", "")),
    )
    request = build_repository_test_request(base, entry_source="src/pkg/main.py", import_root="src")
    assert request.to_dict()["test_interface"]["module"] == "pkg.main"
