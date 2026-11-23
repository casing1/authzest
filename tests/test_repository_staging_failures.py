"""Additional retained-failure tests over owned inert staging trees."""

import os
from pathlib import Path

import pytest
from tests.test_repository_staging import no_process_or_network as no_process_or_network
from tests.test_repository_staging import setup as setup

from authzest.runner import _repository_staging as module
from authzest.runner._repository_staging import (
    RepositoryInputStage,
    RepositoryStageError,
    RepositoryStageInitializationError,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX source-only sealed inputs")


@pytest.mark.parametrize("phase,role", [(None, "T"), ("before", "B"), ("after", []), (True, "A")])
def test_closed_phase_and_role_contract_before_any_capture(setup, phase, role):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    before = set(parent.iterdir())
    with pytest.raises(RepositoryStageError):
        RepositoryInputStage(*args[:-2], phase, role)
    assert set(parent.iterdir()) == before


def test_stage_subclass_and_unavailable_platform_do_not_allocate(setup, monkeypatch):
    _, parent, create, _ = setup
    _, args = create(stage=False)

    class Child(RepositoryInputStage):
        pass

    with pytest.raises(RepositoryStageError):
        Child(*args)
    monkeypatch.setattr(module, "supported", lambda: False)
    with pytest.raises(RepositoryStageError):
        RepositoryInputStage(*args)
    assert len(list(parent.iterdir())) == 1


def test_async_hook_rejected_without_invocation(setup):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    called = []

    async def hook():
        called.append(True)

    with pytest.raises(RepositoryStageError):
        RepositoryInputStage(*args, _before_create=hook)
    assert not called and len(list(parent.iterdir())) == 1


def test_hook_returning_coroutine_closes_it_before_allocation(setup):
    _, parent, create, _ = setup
    _, args = create(stage=False)

    async def result():
        raise AssertionError("Coroutine body must not run")

    coroutine = result()
    with pytest.raises(RepositoryStageInitializationError):
        RepositoryInputStage(*args, _before_create=lambda: coroutine)
    assert coroutine.cr_frame is None and len(list(parent.iterdir())) == 1


def test_parent_replacement_in_hook_is_refused_before_allocation(setup):
    _, parent, create, _ = setup
    _, args = create(stage=False)
    moved = parent.with_name("private-retained")

    def replace():
        parent.rename(moved)
        parent.mkdir(mode=0o700)

    with pytest.raises(RepositoryStageInitializationError) as error:
        RepositoryInputStage(*args, _before_create=replace)
    assert error.value.allocation_attempted is False
    assert list(parent.iterdir()) == [] and len(list(moved.iterdir())) == 1


@pytest.mark.parametrize("fault", [OSError, KeyboardInterrupt])
def test_close_attempts_all_held_descriptors_even_after_failure(setup, monkeypatch, fault):
    _, _, create, _ = setup
    stage, _ = create()
    held = set(stage._fds.values())
    original = os.close
    calls = []

    def close(fd):
        calls.append(fd)
        result = original(fd)
        if len(calls) == 1:
            raise fault("inert close uncertainty")
        return result

    assert stage.descriptor_cleanup_confirmed is False
    monkeypatch.setattr(module.os, "close", close)
    expected = RepositoryStageError if fault is OSError else KeyboardInterrupt
    with pytest.raises(expected):
        stage.close()
    assert set(calls) == held and len(calls) == len(held)
    assert stage.state == "state-unconfirmed"
    assert stage.descriptor_cleanup_confirmed is False
    assert stage.path.exists()
    for fd in held:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_successful_close_reports_only_host_descriptor_cleanup(setup):
    _, _, create, _ = setup
    stage, _ = create()
    stage.close()
    assert stage.descriptor_cleanup_confirmed
    assert stage.path.exists()


def test_reentrant_snapshot_during_projection_permanently_refuses_stage(setup, monkeypatch):
    _, _, create, _ = setup
    stage, _ = create()

    def build(*args, **kwargs):
        with pytest.raises(RepositoryStageError):
            stage.snapshot()
        return None

    monkeypatch.setattr(module, "build_container_create_plan", build)
    with pytest.raises(RepositoryStageError):
        stage.prepare_create(None, "a" * 32, "b" * 32)
    assert stage.state == "state-unconfirmed"
    with pytest.raises(RepositoryStageError):
        stage.assert_current()


@pytest.mark.parametrize("operation", ["assert_current", "snapshot", "prepare_create"])
def test_reentry_during_last_checkpoint_callback_cannot_return_healthy_once(
    setup, monkeypatch, operation
):
    _, _, create, _ = setup
    stage, args = create()
    session, calls = args[0], []
    original = session._recheck_runtime_checkpoint

    class Plan:
        def to_dict(self):
            return {"status": "planned-not-executed"}

    monkeypatch.setattr(module, "build_container_create_plan", lambda *a, **k: Plan())

    def invoke():
        if operation == "prepare_create":
            return stage.prepare_create(None, "a" * 32, "b" * 32)
        return getattr(stage, operation)()

    def count(checkpoint):
        calls.append(checkpoint)
        return original(checkpoint)

    monkeypatch.setattr(session, "_recheck_runtime_checkpoint", count)
    invoke()
    last = len(calls)
    assert last > 0
    calls.clear()

    def reenter(checkpoint):
        calls.append(checkpoint)
        result = original(checkpoint)
        if len(calls) == last:
            with pytest.raises(RepositoryStageError):
                stage.close()
        return result

    monkeypatch.setattr(session, "_recheck_runtime_checkpoint", reenter)
    with pytest.raises(RepositoryStageError):
        invoke()
    assert stage.state == "state-unconfirmed"


def test_creation_interrupt_retains_partial_file_and_cleanup_facts(setup, monkeypatch):
    _, _, create, _ = setup
    _, args = create(stage=False)
    original = module.RepositoryInputStage._create_file

    def create_file(self, name, content):
        original(self, name, content)
        if name.endswith("manifest.json"):
            raise KeyboardInterrupt("inert interruption after durable file")

    monkeypatch.setattr(module.RepositoryInputStage, "_create_file", create_file)
    with pytest.raises(KeyboardInterrupt) as error:
        RepositoryInputStage(*args)
    failure = error.value.repository_stage_initialization
    assert failure.file_states["input/manifest.json"] == "confirmed"
    assert (failure.created_path / "input/manifest.json").is_file()
    assert failure.descriptor_cleanup_confirmed
    assert not (failure.created_path / "record.json").exists()


def test_origin_changes_after_private_copy_do_not_change_staged_bytes(setup):
    root, _, create, _ = setup
    _, args = create(stage=False)
    (root / "src/pkg/app.py").write_text("# independently edited original\n")
    stage = RepositoryInputStage(*args)
    try:
        private = Path(args[0].result()["private_root"])
        assert (stage.input_path / "project/src/pkg/app.py").read_bytes() == (
            private / "project/src/pkg/app.py"
        ).read_bytes()
        stage.assert_current()
    finally:
        stage.close()
