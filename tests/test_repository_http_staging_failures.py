"""Retained HTTP A-stage failures over owned files and fake callbacks only."""

import os

import pytest
from tests.test_repository_http_staging import no_execution_or_network as no_execution_or_network
from tests.test_repository_http_staging import setup as setup

from authzest.runner import _repository_http_staging as module
from authzest.runner._repository_http_staging import (
    RepositoryHttpInputStage,
    RepositoryHttpStageError,
    RepositoryHttpStageInitializationError,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX source-only HTTP staging")


@pytest.mark.parametrize("phase", [None, True, [], "restored", "T"])
def test_closed_phase_before_capture_or_allocation(setup, phase):
    create, _ = setup
    _, args, _ = create(stage=False)
    with pytest.raises(RepositoryHttpStageError):
        RepositoryHttpInputStage(*args[:-1], phase)


def test_subclass_and_unsupported_platform_refuse_before_allocation(setup, monkeypatch):
    create, _ = setup
    _, args, _ = create(stage=False)

    class Child(RepositoryHttpInputStage):
        pass

    with pytest.raises(RepositoryHttpStageError):
        Child(*args)
    monkeypatch.setattr(module, "supported", lambda: False)
    with pytest.raises(RepositoryHttpStageError):
        RepositoryHttpInputStage(*args)


def test_async_allocation_hook_is_never_called(setup):
    create, _ = setup
    _, args, _ = create(stage=False)
    called = []

    async def hook():
        called.append(True)

    with pytest.raises(RepositoryHttpStageError):
        RepositoryHttpInputStage(*args, _before_create=hook)
    assert not called


def test_coroutine_hook_result_is_closed_without_dispatch(setup):
    create, _ = setup
    _, args, _ = create(stage=False)

    async def body():
        raise AssertionError("No async hook work may execute")

    coroutine = body()
    with pytest.raises(RepositoryHttpStageInitializationError) as error:
        RepositoryHttpInputStage(*args, _before_create=lambda: coroutine)
    assert error.value.allocation_attempted is False
    assert coroutine.cr_frame is None


@pytest.mark.parametrize("fault", [OSError, KeyboardInterrupt])
def test_close_attempts_every_held_descriptor_after_failure(setup, monkeypatch, fault):
    create, _ = setup
    stage, _, _ = create()
    held = set(stage._fds.values())
    close = os.close
    calls = []

    def uncertain(fd):
        calls.append(fd)
        value = close(fd)
        if len(calls) == 1:
            raise fault("owned descriptor close uncertainty")
        return value

    with monkeypatch.context() as patch:
        patch.setattr(module.os, "close", uncertain)
        with pytest.raises(RepositoryHttpStageError if fault is OSError else KeyboardInterrupt):
            stage.close()
    assert set(calls) == held and len(calls) == len(held)
    assert stage.descriptor_cleanup_confirmed is False
    assert stage.state == "state-unconfirmed" and stage.path.exists()
    for fd in held:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize("fault", [OSError, KeyboardInterrupt])
def test_creation_interrupt_preserves_partial_input_and_close_facts(setup, monkeypatch, fault):
    create, _ = setup
    _, args, _ = create(stage=False)
    original = module.RepositoryHttpInputStage._create_file

    def fail_after_write(self, name, content):
        original(self, name, content)
        if name == "input/manifest.json":
            raise fault("owned interruption after durable write")

    with monkeypatch.context() as patch:
        patch.setattr(module.RepositoryHttpInputStage, "_create_file", fail_after_write)
        if fault is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt) as error:
                RepositoryHttpInputStage(*args)
            failure = error.value.repository_http_stage_initialization
        else:
            with pytest.raises(RepositoryHttpStageInitializationError) as error:
                RepositoryHttpInputStage(*args)
            failure = error.value
    assert failure.file_states["input/manifest.json"] == "confirmed"
    assert failure.descriptor_cleanup_confirmed is True
    assert (failure.created_path / "input/manifest.json").is_file()
    assert not (failure.created_path / "record.json").exists()


@pytest.mark.parametrize("value", [0, None, True])
def test_invalid_write_result_retains_incomplete_file(setup, monkeypatch, value):
    create, _ = setup
    _, args, _ = create(stage=False)
    with monkeypatch.context() as patch:
        patch.setattr(module.os, "write", lambda *_: value)
        with pytest.raises(RepositoryHttpStageInitializationError) as error:
            RepositoryHttpInputStage(*args)
    failure = error.value
    assert failure.file_states["input/manifest.json"] == "created-unconfirmed"
    assert (failure.created_path / "input/manifest.json").read_bytes() == b""
    assert failure.descriptor_cleanup_confirmed is True


@pytest.mark.parametrize("operation", ["assert_current", "snapshot", "prepare_create"])
def test_reentry_in_last_checkpoint_callback_cannot_return_healthy(setup, monkeypatch, operation):
    create, _ = setup
    stage, args, _ = create()
    session = args[0]
    original = session._recheck_runtime_checkpoint
    calls = []

    class Plan:
        def to_dict(self):
            return {"status": "planned-not-executed"}

    monkeypatch.setattr(module, "build_container_create_plan", lambda *_a, **_k: Plan())

    def invoke():
        return (
            stage.prepare_create(None, "a" * 32, "b" * 32)
            if operation == "prepare_create"
            else getattr(stage, operation)()
        )

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
        value = original(checkpoint)
        if len(calls) == last:
            with pytest.raises(RepositoryHttpStageError):
                stage.close()
        return value

    monkeypatch.setattr(session, "_recheck_runtime_checkpoint", reenter)
    with pytest.raises(RepositoryHttpStageError):
        invoke()
    assert stage.state == "state-unconfirmed"
