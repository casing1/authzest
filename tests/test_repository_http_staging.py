"""HTTP A inputs from owned actual private bytes; no target, model or guest run."""

import builtins
import copy
import json
import os
import pickle
import socket
import stat
import subprocess
from contextlib import suppress
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from tests.helpers.repository_http_file_data import make_http_file_session, perform
from tests.helpers.repository_http_verification_data import AFTER, SOURCE

from authzest.codex.contracts import canonical
from authzest.runner import _repository_http_staging as module
from authzest.runner._repository_http_manifest import validate_guest_manifest
from authzest.runner._repository_http_staging import (
    RepositoryHttpInputStage,
    RepositoryHttpStageError,
    RepositoryHttpStageInitializationError,
)
from authzest.runner.repository_http_cases import build_repository_http_cases
from authzest.runner.repository_http_file_session import RepositoryHttpSessionError
from authzest.runner.repository_http_verification import build_repository_http_verification_plan
from test_repository_http_runtime_profile import profile_data

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX source-only sealed HTTP inputs")


@pytest.fixture(autouse=True)
def no_execution_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP staging may only copy and compare owned inert bytes")

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "fastapi", "httpx", "docker", "uvicorn", "openai"}:
            forbidden()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def setup(tmp_path):
    sessions, stages = [], []

    def create(*, phase="before", copied=True, stage=True, **kwargs):
        values = make_http_file_session(tmp_path, prefix="stage-" + str(len(sessions)))
        session, origin, _, request, response, cases, _ = values
        sessions.append(session)
        plan = build_repository_http_verification_plan(request, response, cases)
        if copied:
            perform(session, "copy")
            if phase == "after":
                perform(session, "accept-diff")
                perform(session, "apply")
        args = (session, request, response, cases, plan, phase)
        result = RepositoryHttpInputStage(*args, **kwargs) if stage else None
        if result is not None:
            stages.append(result)
        return result, args, origin

    yield create, stages
    for stage in stages:
        with suppress(RepositoryHttpStageError):
            stage.close()
    for session in sessions:
        with suppress(RepositoryHttpSessionError):
            session.close()
    # Production close preserves sealing. Restore only this test's own directory
    # permissions after assertions so pytest can remove even broken-link cases.
    for path in tmp_path.rglob("*"):
        with suppress(OSError):
            if stat.S_ISDIR(path.lstat().st_mode):
                path.chmod(0o700)


@pytest.mark.parametrize("phase", ["before", "after"])
def test_exact_A_only_sealed_source_and_host_record(setup, phase):
    create, _ = setup
    stage, args, origin = create(phase=phase)
    original = {f.path: (origin.snapshot.root / f.path).read_bytes() for f in origin.snapshot.files}
    snapshot = stage.snapshot()
    source = args[1].to_dict()["selection"]["source"]
    assert (stage.input_path / "project" / source).read_bytes() == (
        SOURCE if phase == "before" else AFTER
    ).encode()
    files = {
        p.relative_to(stage.input_path).as_posix()
        for p in stage.input_path.rglob("*")
        if p.is_file()
    }
    assert files == {"manifest.json", "project/" + source}
    assert stat.S_IMODE(stage.path.stat().st_mode) == 0o700
    assert stat.S_IMODE((stage.path / "record.json").stat().st_mode) == 0o600
    for path in [stage.input_path, *stage.input_path.rglob("*")]:
        assert stat.S_IMODE(path.stat().st_mode) == (0o555 if path.is_dir() else 0o444)
        if path.is_file():
            assert path.stat().st_nlink == 1
    manifest = validate_guest_manifest((stage.input_path / "manifest.json").read_bytes())
    assert stage.manifest == snapshot["manifest"] == manifest
    assert manifest["http_interface"] == args[1].to_dict()["http_interface"]
    assert snapshot["kind"] == "repository-http-input-stage-snapshot"
    assert snapshot["schema_version"] == "2.0" and snapshot["role"] == "A"
    assert snapshot["runtime_invoked"] is snapshot["verified_fix"] is False
    assert snapshot["execution_authorized"] is False
    assert snapshot["execution_status"] == "not-run"
    assert "HOST_ONLY_EXPECTATION" not in canonical(manifest)
    assert "policy" not in canonical(manifest) and "test" not in manifest
    assert (stage.path / "record.json").is_file()
    record = json.loads((stage.path / "record.json").read_bytes())
    assert record["verification_plan_id"] == args[4].plan_id
    assert record["checkpoint"]["session_id"] == stage._checkpoint.session_id
    snapshot["manifest"]["request_id"] = "changed-detached"
    assert stage.snapshot()["manifest"]["request_id"] == args[1].request_id
    assert {
        f.path: (origin.snapshot.root / f.path).read_bytes() for f in origin.snapshot.files
    } == original


def test_multiple_A_stages_share_current_checkpoint_without_adoption(setup):
    create, stages = setup
    first, args, _ = create()
    second = RepositoryHttpInputStage(*args)
    stages.append(second)
    assert first._checkpoint is second._checkpoint
    assert first.input_path != second.input_path
    first.assert_current()
    second.assert_current()
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            operation(first)


@pytest.mark.parametrize("role", ["T", "B"])
def test_no_other_role_can_be_staged(setup, role):
    create, _ = setup
    _, args, _ = create(stage=False)
    parent = Path(args[0].result()["private_root"]).parent
    before = set(parent.iterdir())
    with pytest.raises(TypeError):
        RepositoryHttpInputStage(*args, role=role)
    assert set(parent.iterdir()) == before


@pytest.mark.parametrize(
    "field", ["rationale", "assumptions", "uncertainties", "limitations", "after_text"]
)
def test_full_response_correspondence_before_allocation(setup, field):
    create, _ = setup
    _, args, _ = create(stage=False)
    session, request, response, cases, _, phase = args
    changed = copy.deepcopy(response)
    if field == "after_text":
        changed["proposal"][field] += "\n# changed repair bytes\n"
    elif field == "rationale":
        changed[field] += " Changed."
    else:
        changed[field].append("Changed supplied declaration.")
    plan = build_repository_http_verification_plan(request, changed, cases)
    parent = Path(session.result()["private_root"]).parent
    before = set(parent.iterdir())
    with pytest.raises(RepositoryHttpStageInitializationError) as error:
        RepositoryHttpInputStage(session, request, changed, cases, plan, phase)
    assert error.value.allocation_attempted is False
    assert set(parent.iterdir()) == before


def test_full_case_set_correspondence_before_allocation(setup):
    create, _ = setup
    _, args, _ = create(stage=False)
    session, request, response, cases, _, phase = args
    raw = cases.to_dict()
    raw.pop("case_set_id")
    raw["authorship"] += " Changed declaration."
    changed = build_repository_http_cases(raw)
    plan = build_repository_http_verification_plan(request, response, changed)
    with pytest.raises(RepositoryHttpStageInitializationError) as error:
        RepositoryHttpInputStage(session, request, response, changed, plan, phase)
    assert error.value.allocation_attempted is False


@pytest.mark.parametrize(
    "state", ["captured", "diff-accepted", "restored-before", "closed", "pending"]
)
def test_unavailable_session_never_allocates_stage(setup, state):
    create, _ = setup
    _, args, _ = create(copied=state != "captured", stage=False)
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
    with pytest.raises(RepositoryHttpStageInitializationError) as error:
        RepositoryHttpInputStage(*args)
    assert error.value.allocation_attempted is False


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "inode",
        "extra",
        "test",
        "symlink",
        "hardlink",
        "directory-mode",
        "file-mode",
        "record",
        "private",
    ],
)
def test_changed_tree_refuses_and_retains_artifacts(setup, change):
    create, _ = setup
    stage, args, _ = create()
    source = stage.input_path / "project" / stage.manifest["source"]["path"]
    if change == "private":
        (
            Path(args[0].result()["private_root"]) / "project" / stage.manifest["source"]["path"]
        ).write_bytes(b"# changed private\n")
    elif change == "directory-mode":
        source.parent.chmod(0o700)
    elif change == "file-mode":
        source.chmod(0o600)
    elif change == "record":
        (stage.path / "record.json").write_bytes(b"{}")
    else:
        source.parent.chmod(0o700)
        if change == "extra":
            (source.parent / "extra.py").write_bytes(b"# extra\n")
        elif change == "test":
            (source.parent / "test_unexpected.py").write_bytes(b"# not an input\n")
        elif change == "bytes":
            source.chmod(0o600)
            source.write_bytes(b"# changed source\n")
        elif change == "inode":
            content = source.read_bytes()
            source.unlink()
            source.write_bytes(content)
            source.chmod(0o444)
        elif change == "symlink":
            source.unlink()
            source.symlink_to("missing.py")
        else:
            os.link(source, source.parent / "alias.py")
        source.parent.chmod(0o555)
    with pytest.raises(RepositoryHttpStageError):
        stage.snapshot()
    assert stage.state == "state-unconfirmed" and stage.path.exists()


@pytest.mark.parametrize("transition", ["pending", "accept", "apply", "restore", "closed"])
def test_live_revision_and_state_invalidate_prior_stage(setup, transition):
    create, _ = setup
    stage, args, _ = create()
    session = args[0]
    if transition == "pending":
        session.prepare("accept-diff")
    elif transition == "closed":
        session.close()
    else:
        perform(session, "accept-diff")
        if transition in {"apply", "restore"}:
            perform(session, "apply")
        if transition == "restore":
            perform(session, "restore")
    with pytest.raises(RepositoryHttpStageError):
        stage.assert_current()


def test_checkpoint_clone_is_not_an_issued_live_object(setup):
    create, _ = setup
    stage, _, _ = create()
    stage._checkpoint = replace(stage._checkpoint)
    with pytest.raises(RepositoryHttpStageError):
        stage.assert_current()


def test_original_edit_after_copy_does_not_change_private_observation(setup):
    create, _ = setup
    _, args, origin = create(stage=False)
    selected = origin.snapshot.source
    (origin.snapshot.root / selected).write_bytes(b"# later original edit\n")
    stage = RepositoryHttpInputStage(*args)
    setup[1].append(stage)
    assert (stage.input_path / "project" / selected).read_bytes() == SOURCE.encode()
    assert (origin.snapshot.root / selected).read_bytes() == b"# later original edit\n"


@pytest.mark.parametrize("result", [True, object()])
def test_non_none_allocation_hook_refuses_before_mkdir(setup, result):
    create, _ = setup
    _, args, _ = create(stage=False)
    with pytest.raises(RepositoryHttpStageInitializationError) as error:
        RepositoryHttpInputStage(*args, _before_create=lambda: result)
    assert error.value.allocation_attempted is False


def test_allocation_hook_rechecks_changed_private_bytes_before_mkdir(setup):
    create, _ = setup
    _, args, _ = create(stage=False)
    private = (
        Path(args[0].result()["private_root"])
        / "project"
        / args[1].to_dict()["selection"]["source"]
    )

    def edit():
        private.write_bytes(b"# changed during hook\n")

    with pytest.raises(RepositoryHttpStageInitializationError) as error:
        RepositoryHttpInputStage(*args, _before_create=edit)
    assert error.value.allocation_attempted is False


def test_real_closed_create_projection_remains_unexecuted(setup):
    from authzest.runner._repository_http_runtime_profile import validate_runtime_profile

    create, _ = setup
    stage, _args, _ = create()
    profile = validate_runtime_profile(canonical(profile_data()))
    result = stage.prepare_create(profile, "1" * 32, "2" * 32)
    data = result.to_dict()
    assert data["kind"] == "repository-http-staged-create-plan"
    assert data["schema_version"] == "2.0"
    assert result.plan_id.startswith("repository-http-staged-create-plan-")
    assert data["runtime_invoked"] is data["execution_authorized"] is data["verified_fix"] is False
    command = data["container_create_plan"]
    assert command["role"] == "A"
    assert "--network=none" in command["argv"]
    assert len(command["declared_files"]) == 2
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "changed"


@pytest.mark.parametrize(
    "behavior", ["mutate-return", "mutate-raise", "manifest-return", "manifest-raise", "reenter"]
)
def test_builder_cannot_hide_private_mutation_or_reentry(setup, monkeypatch, behavior):
    create, _ = setup
    stage, args, _ = create()
    private = Path(args[0].result()["private_root"]) / "project" / stage.manifest["source"]["path"]

    class Plan:
        def to_dict(self):
            return {"status": "planned-not-executed"}

    def builder(*_args, **_kwargs):
        if behavior == "reenter":
            with pytest.raises(RepositoryHttpStageError):
                stage.snapshot()
        elif behavior.startswith("manifest"):
            changed = stage.manifest
            changed["source"]["sha256"] = "0" * 64
            replacement = module.build_guest_manifest(
                changed["request_id"], changed["http_interface"], changed["source"]
            )
            stage._manifest.clear()
            stage._manifest.update(replacement)
            if behavior == "manifest-raise":
                raise RuntimeError("trusted fake builder failed after changing declaration")
        else:
            private.write_bytes(b"# builder changed private source\n")
            if behavior == "mutate-raise":
                raise RuntimeError("trusted fake builder failed")
        return Plan()

    monkeypatch.setattr(module, "build_container_create_plan", builder)
    with pytest.raises(RepositoryHttpStageError):
        stage.prepare_create("fake-profile", "1" * 32, "2" * 32)
    assert stage.state == "state-unconfirmed"


def test_close_releases_only_descriptors_and_preserves_sealed_files(setup):
    create, _ = setup
    stage, _, _ = create()
    source = stage.input_path / "project" / stage.manifest["source"]["path"]
    before = source.read_bytes()
    stage.close()
    assert stage.state == "closed" and stage.descriptor_cleanup_confirmed is True
    assert source.read_bytes() == before and stat.S_IMODE(source.stat().st_mode) == 0o444
    with pytest.raises(RepositoryHttpStageError):
        stage.snapshot()
