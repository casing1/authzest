"""Owned-file failures and clocks only; retained state is never runtime proof."""

import os
from contextlib import suppress
from pathlib import Path

import pytest
from tests.helpers.repository_http_file_data import make_http_file_session, perform
from tests.helpers.repository_http_verification_data import AFTER, SOURCE

from authzest.runner import _repository_http_files as files_module
from authzest.runner.repository_http_file_session import (
    RepositoryHttpSessionEffectError,
    RepositoryHttpSessionError,
)
from test_repository_http_file_session import no_target_or_external_effects  # noqa: F401

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX HTTP private files")


@pytest.fixture
def setup(tmp_path):
    values = make_http_file_session(tmp_path)
    yield values
    with suppress(RepositoryHttpSessionError):
        values[0].close()


def choose(session, step):
    plan = session.prepare(step)
    return session.decide(plan, plan.to_dict()["confirmation"])


def failure_result(error):
    if isinstance(error, RepositoryHttpSessionEffectError):
        return error.result
    return error.repository_http_session_result


@pytest.mark.parametrize("fault_type", [OSError, KeyboardInterrupt, SystemExit])
def test_partial_copy_retains_material_states_and_attempts_descriptor_cleanup(
    setup, monkeypatch, fault_type
):
    session, origin, *_ = setup
    chosen = choose(session, "copy")
    original = files_module.RepositoryHttpFiles._write_new
    fault = fault_type("owned material write fault")

    def fail(files, name, raw):
        if name == "evidence/source.after":
            raise fault
        return original(files, name, raw)

    monkeypatch.setattr(files_module.RepositoryHttpFiles, "_write_new", fail)
    with pytest.raises(
        RepositoryHttpSessionEffectError if fault_type is OSError else fault_type
    ) as caught:
        session.perform(chosen)
    result = failure_result(caught.value)
    assert result["state"] == "recovery-required"
    root = Path(result["private_root"])
    assert root.is_dir() and (root / "project/app.py").read_bytes() == SOURCE.encode()
    assert result["failure"]["initialization_cleanup_confirmed"] is True
    assert (
        result["failure"]["initialization_file_states"]["evidence/source.after"]
        == "creation-attempted"
    )
    assert (origin.snapshot.root / "app.py").read_bytes() == SOURCE.encode()
    with pytest.raises(RepositoryHttpSessionError):
        session.prepare("copy")


@pytest.mark.parametrize("operation", ["apply", "restore"])
def test_expiry_after_durable_intent_refuses_source_replacement(setup, monkeypatch, operation):
    session, origin, clock, *_ = setup
    perform(session, "copy")
    perform(session, "accept-diff")
    if operation == "restore":
        perform(session, "apply")
    root = Path(session.result()["private_root"])
    before = (root / "project/app.py").read_bytes()
    chosen = choose(session, operation)
    original = files_module.RepositoryHttpFiles.replace

    def expire_after_intent(files, path, raw, *, guard):
        value = original(files, path, raw, guard=guard)
        if path == "record.json" and b'"pending_operation":"' + operation.encode() + b'"' in raw:
            clock.value += 300
        return value

    monkeypatch.setattr(files_module.RepositoryHttpFiles, "replace", expire_after_intent)
    with pytest.raises(RepositoryHttpSessionEffectError) as caught:
        session.perform(chosen)
    assert (root / "project/app.py").read_bytes() == before
    assert caught.value.result["state"] == "recovery-required"
    assert caught.value.result["failure"]["phase"] == "source-replacement"
    assert (origin.snapshot.root / "app.py").read_bytes() == SOURCE.encode()


@pytest.mark.parametrize("fault_type", [OSError, KeyboardInterrupt, SystemExit])
def test_unclassified_failure_after_committed_source_is_unknown_not_false_rollback(
    setup, monkeypatch, fault_type
):
    session, origin, *_ = setup
    perform(session, "copy")
    perform(session, "accept-diff")
    chosen = choose(session, "apply")
    original = files_module.RepositoryHttpFiles.replace

    def fail_after_source(files, path, raw, *, guard):
        value = original(files, path, raw, guard=guard)
        if path == "project/app.py":
            raise fault_type("owned post-commit fault")
        return value

    monkeypatch.setattr(files_module.RepositoryHttpFiles, "replace", fail_after_source)
    with pytest.raises(
        RepositoryHttpSessionEffectError if fault_type is OSError else fault_type
    ) as caught:
        session.perform(chosen)
    result = failure_result(caught.value)
    assert result["state"] == "recovery-required"
    assert result["failure"]["status"] == "effect-unconfirmed"
    assert result["failure"]["committed"] is None
    assert result["failure"]["commit_attempted"] is None
    assert (Path(result["private_root"]) / "project/app.py").read_bytes() == AFTER.encode()
    assert (origin.snapshot.root / "app.py").read_bytes() == SOURCE.encode()
    with pytest.raises(RepositoryHttpSessionError):
        session.prepare("restore")


def test_expiry_during_copy_allocation_prevents_the_first_file_effect(setup, monkeypatch):
    session, _, clock, *_ = setup
    chosen = choose(session, "copy")
    original = files_module.RepositoryHttpFiles._open_parent

    def late_parent(files, path):
        value = original(files, path)
        clock.value += 300
        return value

    monkeypatch.setattr(files_module.RepositoryHttpFiles, "_open_parent", late_parent)
    with pytest.raises(RepositoryHttpSessionEffectError) as caught:
        session.perform(chosen)
    assert caught.value.result["state"] == "refused"
    assert caught.value.result["private_root"] is None
    assert not list(session._parent.iterdir())


def test_clock_reentry_cannot_allocate_a_second_copy(setup):
    session, *_ = setup
    calls = []

    def clock():
        calls.append(1)
        session.prepare("copy")
        return 10

    session._clock = clock
    with pytest.raises(RepositoryHttpSessionError):
        session.prepare("copy")
    assert len(calls) == 1 and session.result()["private_root"] is None
    assert not list(session._parent.iterdir())


def test_close_attempts_origin_even_if_private_descriptor_cleanup_fails(setup, monkeypatch):
    session, origin, *_ = setup
    perform(session, "copy")
    root = Path(session.result()["private_root"])
    original_close = files_module.RepositoryHttpFiles.close

    def fail_after_close(files):
        original_close(files)
        raise OSError("owned close receipt fault")

    monkeypatch.setattr(files_module.RepositoryHttpFiles, "close", fail_after_close)
    with pytest.raises(RepositoryHttpSessionError):
        session.close()
    result = session.result()
    assert session.closed and origin.closed
    assert result["descriptor_cleanup"] == "unconfirmed"
    assert result["state"] == "recovery-required" and root.exists()
    assert (root / "project/app.py").read_bytes() == SOURCE.encode()
