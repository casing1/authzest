"""Owned inert byte trees and fake create projections; never import app/test code."""

import copy
import json
import os
import pickle
import socket
import stat
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest
from tests.helpers.repository_verification_data import AFTER, POLICY, SOURCE, TEST, case_data

from authzest.analyzer.repository_origin import capture_repository_origin
from authzest.codex.contracts import canonical
from authzest.codex.repository_copy_plan import prepare_repository_copy_plan
from authzest.codex.repository_proposal import TEST_PATH, build_repository_request
from authzest.codex.repository_test_interface import build_repository_test_request
from authzest.runner import _repository_staging as module
from authzest.runner._repository_manifest import validate_guest_manifest
from authzest.runner._repository_runtime_profile import (
    EMPTY_CONFIG_SHA256,
    expected_assets,
    expected_recipe_pins,
    validate_runtime_profile,
)
from authzest.runner._repository_staging import (
    RepositoryInputStage,
    RepositoryStageError,
    RepositoryStageInitializationError,
)
from authzest.runner.repository_cases import build_repository_cases
from authzest.runner.repository_file_session import RepositoryFileSession, RepositorySessionError
from authzest.runner.repository_verification import build_repository_verification_plan

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX source-only sealed inputs")


def perform(session, step):
    plan = session.prepare(step)
    return session.perform(session.decide(plan, plan.to_dict()["confirmation"]))


@pytest.fixture(autouse=True)
def no_process_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Staging must never start a process or use the network")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def setup(tmp_path):
    root = (tmp_path / "origin").resolve()
    (root / "src/pkg").mkdir(parents=True)
    source = "src/pkg/app.py"
    (root / source).write_text(SOURCE)
    (root / "src/pkg/__init__.py").write_bytes(b"")
    (root / "src/pkg/auth.py").write_bytes(b'NAME = "test-owner"\r\n')
    (root / "policy.md").write_text(POLICY)
    parent = (tmp_path / "private").resolve()
    parent.mkdir(mode=0o700)
    sessions, stages = [], []

    def create(*, phase="before", role="T", copied=True, **kwargs):
        origin = capture_repository_origin(
            root, source, "policy.md", ("src/pkg/__init__.py", "src/pkg/auth.py")
        )
        base = build_repository_request(origin.snapshot, "offline-model")
        request = build_repository_test_request(base, entry_source=source, import_root="src")
        response = {
            "schema_version": "1.1",
            "request_id": request.request_id,
            "status": "proposed-change",
            "rationale": "Owned inert transition.",
            "assumptions": ["Synthetic test material."],
            "uncertainties": ["Nothing was executed."],
            "limitations": ["No runtime proof."],
            "proposal": {
                "source_path": source,
                "before_sha256": base.to_dict()["selection"]["files"][0]["sha256"],
                "after_text": AFTER,
                "test_path": TEST_PATH,
                "test_text": TEST,
            },
        }
        legacy = {**response, "schema_version": "1.0", "request_id": base.request_id}
        session = RepositoryFileSession(
            origin, base, legacy, prepare_repository_copy_plan(base, legacy), _parent=parent
        )
        sessions.append(session)
        cases = build_repository_cases(case_data(request))
        plan = build_repository_verification_plan(request, response, cases)
        if copied:
            perform(session, "copy")
            if phase == "after":
                perform(session, "accept-diff")
                perform(session, "apply")
        args = (session, request, response, cases, plan, phase, role)
        if kwargs.pop("stage", True):
            result = RepositoryInputStage(*args, **kwargs)
            stages.append(result)
        else:
            result = None
        return result, args

    yield root, parent, create, stages
    for stage in stages:
        with suppress(RepositoryStageError):
            stage.close()
    for session in sessions:
        with suppress(RepositorySessionError):
            session.close()


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("role", ["T", "A"])
def test_exact_nested_sealed_inputs_and_host_only_record(setup, phase, role):
    root, _, create, _ = setup
    originals = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    stage, args = create(phase=phase, role=role)
    snapshot = stage.snapshot()
    assert stage.state == "staged-" + phase
    assert (stage.input_path / "project/src/pkg/app.py").read_bytes() == (
        SOURCE if phase == "before" else AFTER
    ).encode()
    assert (stage.input_path / "project/src/pkg/__init__.py").read_bytes() == b""
    assert (stage.input_path / "project/src/pkg/auth.py").read_bytes().endswith(b"\r\n")
    expected = {
        "manifest.json",
        "project/src/pkg/app.py",
        "project/src/pkg/__init__.py",
        "project/src/pkg/auth.py",
    }
    if role == "T":
        expected.add("tests/test_authzest_regression.py")
        assert (
            stage.input_path / "tests/test_authzest_regression.py"
        ).read_bytes() == TEST.encode()
    actual = {
        str(p.relative_to(stage.input_path)) for p in stage.input_path.rglob("*") if p.is_file()
    }
    assert actual == expected
    assert stat.S_IMODE(stage.path.stat().st_mode) == 0o700
    assert stat.S_IMODE((stage.path / "record.json").stat().st_mode) == 0o600
    for p in stage.input_path.rglob("*"):
        assert stat.S_IMODE(p.stat().st_mode) == (0o555 if p.is_dir() else 0o444)
        if p.is_file():
            assert p.stat().st_nlink == 1
    assert stat.S_IMODE(stage.input_path.stat().st_mode) == 0o555
    manifest = validate_guest_manifest((stage.input_path / "manifest.json").read_bytes(), role)
    assert manifest == stage.manifest == snapshot["manifest"]
    assert manifest["test_interface"] == args[1].to_dict()["test_interface"]
    assert snapshot["execution_status"] == "not-run"
    assert snapshot["verified_fix"] is snapshot["runtime_invoked"] is False
    assert "policy" not in canonical(manifest) and "HOST_ONLY_EXPECTATION" not in canonical(
        manifest
    )
    assert {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    } == originals
    saved = json.loads((stage.path / "record.json").read_bytes())
    assert saved["verification_plan_id"] == args[4].plan_id
    snapshot["manifest"]["request_id"] = "changed-detached"
    assert stage.snapshot()["manifest"]["request_id"] == args[1].request_id


def test_t_and_a_share_fresh_checkpoint_without_invalidating_each_other(setup):
    _, _, create, stages = setup
    t, args = create()
    a = RepositoryInputStage(*args[:-1], "A")
    stages.append(a)
    assert t._checkpoint is a._checkpoint
    t.assert_current()
    a.assert_current()
    assert t.input_path != a.input_path
    assert a.manifest["test"] is None


@pytest.mark.parametrize("field", ["rationale", "assumptions", "after_text", "test_text"])
def test_full_response_correspondence_rejects_valid_but_different_proposal(setup, field):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    session, request, response, cases, _, phase, role = args
    changed = copy.deepcopy(response)
    if field in {"after_text", "test_text"}:
        changed["proposal"][field] += "\n# changed\n"
    elif field == "assumptions":
        changed[field].append("Another assumption.")
    else:
        changed[field] += " Changed."
    plan = build_repository_verification_plan(request, changed, cases)
    with pytest.raises(RepositoryStageInitializationError) as error:
        RepositoryInputStage(session, request, changed, cases, plan, phase, role)
    assert error.value.allocation_attempted is False
    assert len(list(parent.iterdir())) == 1


def test_selected_app_interface_requires_full_request_correspondence(setup):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    session, request, response, cases, plan, phase, role = args
    changed = copy.deepcopy(request.to_dict())
    changed["base_request_id"] = "repository-proposal-request-" + "0" * 64
    malformed = type(request)(canonical(changed))
    with pytest.raises(RepositoryStageInitializationError):
        RepositoryInputStage(session, malformed, response, cases, plan, phase, role)
    assert len(list(parent.iterdir())) == 1


@pytest.mark.parametrize(
    "state", ["captured", "diff-accepted", "restored-before", "closed", "pending"]
)
def test_unavailable_session_never_allocates_stage(setup, state):
    _, parent, create, _ = setup
    _, args = create(copied=state != "captured", stage=False)
    session = args[0]
    if state == "diff-accepted":
        perform(session, "accept-diff")
    elif state == "restored-before":
        for step in ("accept-diff", "apply", "restore"):
            perform(session, step)
    elif state == "closed":
        session.close()
    elif state == "pending":
        session.prepare("accept-diff")
    before = set(parent.iterdir())
    with pytest.raises(RepositoryStageInitializationError):
        RepositoryInputStage(*args)
    assert set(parent.iterdir()) == before


@pytest.mark.parametrize(
    "kind",
    [
        "source-edit",
        "extra",
        "symlink",
        "hardlink",
        "directory-mode",
        "file-mode",
        "record-edit",
        "private-edit",
    ],
)
def test_changed_tree_refuses_and_retains_artifacts(setup, kind):
    _, _, create, _ = setup
    stage, args = create()
    source = stage.input_path / "project/src/pkg/app.py"
    if kind == "private-edit":
        private = Path(args[0].result()["private_root"]) / "project/src/pkg/app.py"
        private.write_bytes(b"# changed private\n")
    elif kind == "directory-mode":
        source.parent.chmod(0o700)
    elif kind == "file-mode":
        source.chmod(0o600)
    elif kind == "record-edit":
        (stage.path / "record.json").write_bytes(b"{}")
    else:
        source.parent.chmod(0o700)
        if kind == "extra":
            (source.parent / "extra.py").write_bytes(b"# extra\n")
        elif kind == "source-edit":
            source.chmod(0o600)
            source.write_bytes(b"# changed\n")
        elif kind == "symlink":
            source.unlink()
            source.symlink_to("auth.py")
        else:
            os.link(source, source.parent / "linked.py")
        source.parent.chmod(0o555)
    with pytest.raises(RepositoryStageError):
        stage.snapshot()
    assert stage.state == "state-unconfirmed" and stage.path.exists()


def test_private_state_transition_invalidates_already_sealed_stage(setup):
    _, _, create, _ = setup
    stage, args = create()
    perform(args[0], "accept-diff")
    with pytest.raises(RepositoryStageError):
        stage.assert_current()
    assert stage.path.exists()


def test_allocation_hook_rechecks_private_bytes_before_mkdir(setup):
    _, parent, create, _ = setup
    _, args = create(stage=False)

    def edit():
        (Path(args[0].result()["private_root"]) / "project/src/pkg/app.py").write_bytes(
            b"# changed\n"
        )

    with pytest.raises(RepositoryStageInitializationError) as error:
        RepositoryInputStage(*args, _before_create=edit)
    assert error.value.allocation_attempted is False
    assert len(list(parent.iterdir())) == 1


@pytest.mark.parametrize("hook", [lambda: True, lambda: object()])
def test_hook_return_value_cannot_allocate(setup, hook):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    with pytest.raises(RepositoryStageInitializationError):
        RepositoryInputStage(*args, _before_create=hook)
    assert len(list(parent.iterdir())) == 1


def test_stopped_create_projection_rechecks_and_remains_inert(setup, monkeypatch):
    _, _, create, _ = setup
    stage, _ = create()
    calls = []

    class Plan:
        def to_dict(self):
            return {"status": "planned-not-executed", "argv": ["fake-engine", "create"]}

    def build(profile, role, **kwargs):
        calls.append((profile, role, kwargs))
        return Plan()

    monkeypatch.setattr(module, "build_container_create_plan", build)
    result = stage.prepare_create("fake-profile", "1" * 32, "2" * 32).to_dict()
    assert result["verified_fix"] is result["runtime_invoked"] is False
    assert result["status"] == "planned-not-executed"
    assert calls[0][2]["manifest"] == stage.manifest
    assert calls[0][2]["staging_root"] == str(stage.input_path)


@pytest.mark.parametrize("role", ["T", "A"])
def test_real_static_profile_projects_individual_verified_files(setup, role):
    _, _, create, _ = setup
    stage, _ = create(role=role)
    profile = validate_runtime_profile(
        canonical(
            {
                "schema_version": "1.0",
                "kind": "repository-runtime-profile",
                "platform": "linux/arm64",
                "engine": {
                    "executable": "/owned/docker",
                    "executable_sha256": "1" * 64,
                    "endpoint": "unix:///owned/engine.sock",
                    "config_dir": "/owned/config",
                    "config_json_sha256": EMPTY_CONFIG_SHA256,
                    "server_identity_sha256": "2" * 64,
                    "api_version": "1.45",
                },
                "images": {
                    r: {
                        "image_id": "sha256:" + "3" * 64,
                        **expected_recipe_pins("linux/arm64", r),
                        "assets": expected_assets(r),
                    }
                    for r in ("T", "A", "B")
                },
            }
        )
    )
    result = stage.prepare_create(profile, "1" * 32, "2" * 32)
    assert result.plan_id.startswith("repository-staged-create-plan-")
    plan = result.to_dict()["container_create_plan"]
    files = plan["declared_files"]
    targets = {item["target"] for item in files}
    expected = {
        "/input/manifest.json",
        "/input/project/src/pkg/app.py",
        "/input/project/src/pkg/__init__.py",
        "/input/project/src/pkg/auth.py",
    }
    if role == "T":
        expected.add("/input/tests/test_authzest_regression.py")
    assert targets == expected
    for item in files:
        assert Path(item["source"]).is_relative_to(stage.input_path)
        data = Path(item["source"]).read_bytes()
        assert module._hash(data) == item["sha256"]
        assert len(data) == item["utf8_bytes"]
    assert "--network=none" in plan["argv"]
    assert plan["runtime_invoked"] is False


def test_create_builder_mutation_is_detected_even_when_builder_raises(setup, monkeypatch):
    _, _, create, _ = setup
    stage, _ = create()

    def change(*args, **kwargs):
        (stage.path / "record.json").write_bytes(b"{}")
        raise ValueError("fake projection failure")

    monkeypatch.setattr(module, "build_container_create_plan", change)
    with pytest.raises(RepositoryStageError):
        stage.prepare_create(None, "1" * 32, "2" * 32)
    assert stage.state == "state-unconfirmed"


def test_close_retains_sealed_tree_and_saved_data_cannot_reopen(setup):
    _, _, create, _ = setup
    stage, _ = create()
    before = stage.snapshot()
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            operation(stage)
    stage.close()
    stage.close()
    assert stage.state == "closed" and stage.path.exists()
    assert stat.S_IMODE(stage.input_path.stat().st_mode) == 0o555
    with pytest.raises(RepositoryStageError):
        stage.snapshot()
    with pytest.raises(RepositoryStageError):
        RepositoryInputStage(before, None, None, None, None, "before", "T")


@pytest.mark.parametrize("operation", ["write", "sync", "interrupt"])
def test_partial_creation_retains_failure_facts_and_original_interrupt(
    setup, monkeypatch, operation
):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    original_write, original_sync = os.write, os.fsync

    def write(fd, data):
        if operation == "write":
            return 0
        original_write(fd, data[:1])
        raise KeyboardInterrupt()

    def sync(fd):
        if any(p.name.startswith("authzest-repository-inputs-") for p in parent.iterdir()):
            raise OSError("inert durability failure")
        return original_sync(fd)

    if operation == "sync":
        monkeypatch.setattr(module.os, "fsync", sync)
    else:
        monkeypatch.setattr(module.os, "write", write)
    expected = KeyboardInterrupt if operation == "interrupt" else RepositoryStageInitializationError
    with pytest.raises(expected) as error:
        RepositoryInputStage(*args)
    failure = (
        error.value.repository_stage_initialization if operation == "interrupt" else error.value
    )
    assert failure.allocation_attempted and failure.creation_confirmed
    assert failure.created_path.exists()
    assert failure.descriptor_cleanup_confirmed
    assert any(value != "not-created" for value in failure.file_states.values())


def test_complete_short_write_loop_keeps_exact_bytes(setup, monkeypatch):
    _, _, create, _ = setup
    original = os.write
    monkeypatch.setattr(module.os, "write", lambda fd, data: original(fd, data[:7]))
    stage, _ = create()
    assert (stage.input_path / "project/src/pkg/app.py").read_bytes() == SOURCE.encode()
