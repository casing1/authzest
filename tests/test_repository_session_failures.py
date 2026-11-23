"""Session failure evidence over owned inert files; no target or generated code runs."""

import json
import os
import stat
import threading
from contextlib import suppress
from pathlib import Path

import pytest

from authzest.analyzer.repository_origin import RepositoryOrigin, capture_repository_origin
from authzest.codex.repository_copy_plan import prepare_repository_copy_plan
from authzest.codex.repository_proposal import TEST_PATH, build_repository_request
from authzest.runner import _repository_files as files_module
from authzest.runner.repository_file_session import (
    RepositoryFileSession,
    RepositorySessionEffectError,
    RepositorySessionError,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX source-only file boundary")

SOURCE = (
    "from fastapi import FastAPI\napp = FastAPI()\n"
    '@app.get("/items")\n'
    'def read():\n    return {"owner": False}\n'
    'raise RuntimeError("INERT SOURCE MUST NEVER EXECUTE")\n'
)
AFTER = SOURCE.replace('"owner": False', '"owner": True')
TEST = 'raise RuntimeError("INERT TEST MUST NEVER EXECUTE")\n'


class Clock:
    value = 10.0

    def __call__(self):
        return self.value


@pytest.fixture
def setup(tmp_path):
    origin_root = (tmp_path / "origin").resolve()
    origin_root.mkdir()
    (origin_root / "app.py").write_text(SOURCE)
    (origin_root / "policy.md").write_text("Only an authenticated owner may read an item.\n")
    parent = (tmp_path / "private").resolve()
    parent.mkdir(mode=0o700)
    origin = capture_repository_origin(origin_root, "app.py", "policy.md")
    request = build_repository_request(origin.snapshot, "offline-model")
    response = {
        "schema_version": "1.0",
        "request_id": request.request_id,
        "status": "proposed-change",
        "rationale": "Owned inert file transition only.",
        "assumptions": ["Only owned temporary bytes are used."],
        "uncertainties": ["No runtime observation."],
        "limitations": ["No execution or repair assurance."],
        "proposal": {
            "source_path": "app.py",
            "before_sha256": request.to_dict()["selection"]["files"][0]["sha256"],
            "after_text": AFTER,
            "test_path": TEST_PATH,
            "test_text": TEST,
        },
    }
    clock = Clock()
    session = RepositoryFileSession(
        origin,
        request,
        response,
        prepare_repository_copy_plan(request, response),
        _clock=clock,
        _parent=parent,
    )
    yield session, origin_root, parent, origin, clock
    with suppress(RepositorySessionError):
        session.close()


def _decision(session, step):
    plan = session.prepare(step)
    return session.decide(plan, plan.to_dict()["confirmation"])


def _perform(session, step):
    return session.perform(_decision(session, step))


def _ready_for_apply(session):
    private = Path(_perform(session, "copy")["private_root"])
    _perform(session, "accept-diff")
    return private


def _failure_result(error):
    if isinstance(error, RepositorySessionEffectError):
        return error.result
    return error.repository_session_result


@pytest.mark.parametrize("signal", [OSError, KeyboardInterrupt, SystemExit])
def test_partial_material_creation_retains_location_states_and_original(setup, monkeypatch, signal):
    session, original, parent, _, _ = setup
    decision = _decision(session, "copy")
    write_new = files_module.RepositoryFiles._write_new
    fault = signal("synthetic partial creation fault")

    def fail_test_material(files, name, data):
        if name == "project/" + TEST_PATH:
            raise fault
        return write_new(files, name, data)

    monkeypatch.setattr(files_module.RepositoryFiles, "_write_new", fail_test_material)
    expected = RepositorySessionEffectError if signal is OSError else signal
    with pytest.raises(expected) as caught:
        session.perform(decision)
    result = _failure_result(caught.value)
    path = Path(result["private_root"])
    assert path.parent == parent and path.is_dir()
    assert list(parent.iterdir()) == [path]
    assert (path / "project/app.py").read_bytes() == SOURCE.encode()
    assert not (path / "project" / TEST_PATH).exists()
    assert (original / "app.py").read_bytes() == SOURCE.encode()
    assert result["state"] == "recovery-required"
    assert result["failure"]["initialization_file_states"]["project/app.py"] == "verified"
    assert result["failure"]["initialization_cleanup_confirmed"] is True
    assert result["execution_status"] == "not-run" and result["verified_fix"] is False
    if signal is not OSError:
        assert caught.value is fault
    with pytest.raises(RepositorySessionError):
        session.perform(decision)


@pytest.mark.parametrize("signal", [OSError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("kernel_completed", [False, True])
def test_source_rename_interruption_never_infers_rollback_or_loses_attempt(
    setup, monkeypatch, signal, kernel_completed
):
    session, original, _, _, _ = setup
    path = _ready_for_apply(session)
    decision = _decision(session, "apply")
    replace = files_module.os.replace
    fault = signal("synthetic source rename fault")

    def fail_source(source, destination, **kwargs):
        if destination == "app.py":
            if kernel_completed:
                replace(source, destination, **kwargs)
            raise fault
        return replace(source, destination, **kwargs)

    monkeypatch.setattr(files_module.os, "replace", fail_source)
    expected = RepositorySessionEffectError if signal is OSError else signal
    with pytest.raises(expected) as caught:
        session.perform(decision)
    result = _failure_result(caught.value)
    assert result["state"] == "recovery-required"
    assert result["failure"]["phase"] == "source-replacement"
    assert result["failure"]["commit_attempted"] is True
    # The replacement call did not return: actual kernel completion is not inferred.
    assert result["failure"]["committed"] is False
    assert result["source_observation"]["status"] == "before"
    assert result["source_observation"]["basis"] == "last-confirmed-not-refreshed-by-result"
    assert (path / "project/app.py").read_bytes() == (
        AFTER if kernel_completed else SOURCE
    ).encode()
    assert (original / "app.py").read_bytes() == SOURCE.encode()
    assert json.loads((path / "record.json").read_bytes())["pending_operation"] == "apply"
    assert result["verified_fix"] is False
    for step in ("apply", "restore"):
        with pytest.raises(RepositorySessionError):
            session.prepare(step)


@pytest.mark.parametrize("failure_point", ["sync", "readback"])
def test_completion_failure_retains_confirmed_after_but_never_claims_completed(
    setup, monkeypatch, failure_point
):
    session, original, _, _, _ = setup
    path = _ready_for_apply(session)
    decision = _decision(session, "apply")
    replace_file = files_module.RepositoryFiles.replace
    replace_name = files_module.os.replace
    sync = files_module.os.fsync
    read_current = files_module.RepositoryFiles._read_current
    phase = {"completion": False, "renamed": False}

    def mark_completion(files, name, data, *, guard):
        phase["completion"] = name == "record.json" and json.loads(data)["state"] == "applied-after"
        try:
            return replace_file(files, name, data, guard=guard)
        finally:
            phase["completion"] = False

    def mark_rename(source, destination, **kwargs):
        result = replace_name(source, destination, **kwargs)
        if phase["completion"] and destination == "record.json":
            phase["renamed"] = True
        return result

    def fail_sync(fd):
        if (
            failure_point == "sync"
            and phase["completion"]
            and phase["renamed"]
            and stat.S_ISDIR(os.fstat(fd).st_mode)
        ):
            raise OSError("synthetic completion durability fault")
        return sync(fd)

    def fail_readback(files, name, maximum):
        if (
            failure_point == "readback"
            and phase["completion"]
            and phase["renamed"]
            and name == "record.json"
        ):
            raise OSError("synthetic completion readback fault")
        return read_current(files, name, maximum)

    monkeypatch.setattr(files_module.RepositoryFiles, "replace", mark_completion)
    monkeypatch.setattr(files_module.os, "replace", mark_rename)
    monkeypatch.setattr(files_module.os, "fsync", fail_sync)
    monkeypatch.setattr(files_module.RepositoryFiles, "_read_current", fail_readback)
    with pytest.raises(RepositorySessionEffectError) as caught:
        session.perform(decision)
    result = caught.value.result
    assert result["failure"]["phase"] == "completion-journal"
    assert result["failure"]["commit_attempted"] is result["failure"]["committed"] is True
    assert (
        result["failure"]["stage"]
        == {"sync": "sync-replacement", "readback": "readback-replacement"}[failure_point]
    )
    assert result["state"] == "recovery-required"
    assert result["source_observation"]["status"] == "after"
    assert result["history"][-1]["status"] == "failed"
    assert (path / "project/app.py").read_bytes() == AFTER.encode()
    assert (original / "app.py").read_bytes() == SOURCE.encode()
    assert result["execution_status"] == "not-run" and result["verified_fix"] is False


def test_private_edit_after_restore_decision_is_not_overwritten(setup):
    session, original, _, _, _ = setup
    path = _ready_for_apply(session)
    _perform(session, "apply")
    decision = _decision(session, "restore")
    edited = b"# later private user edit\n"
    (path / "project/app.py").write_bytes(edited)
    with pytest.raises(RepositorySessionError):
        session.perform(decision)
    assert (path / "project/app.py").read_bytes() == edited
    assert (original / "app.py").read_bytes() == SOURCE.encode()
    assert session.state == "recovery-required"
    assert session.result()["failure"]["status"] == "input-integrity-unconfirmed"


def test_backward_clock_after_copy_is_latched_without_new_journal_write(setup):
    session, _, _, _, clock = setup
    path = Path(_perform(session, "copy")["private_root"])
    journal = (path / "record.json").read_bytes()
    clock.value = 1.0
    with pytest.raises(RepositorySessionError, match="clock"):
        session.prepare("accept-diff")
    assert session.state == "recovery-required"
    assert session.result()["failure"]["status"] == "clock-unconfirmed"
    assert (path / "record.json").read_bytes() == journal
    clock.value = 500.0
    with pytest.raises(RepositorySessionError):
        session.prepare("accept-diff")


@pytest.mark.parametrize("operation", ["prepare", "decide", "perform"])
def test_foreign_thread_cannot_dispatch_or_consume_the_live_decision(setup, operation):
    session, _, parent, _, _ = setup
    plan = session.prepare("copy")
    decision = (
        None if operation != "perform" else session.decide(plan, plan.to_dict()["confirmation"])
    )
    operations = {
        "prepare": lambda: session.prepare("copy"),
        "decide": lambda: session.decide(plan, plan.to_dict()["confirmation"]),
        "perform": lambda: session.perform(decision),
    }
    errors = []

    def run():
        try:
            operations[operation]()
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], RepositorySessionError)
    assert list(parent.iterdir()) == [] and session.state == "captured"
    if decision is None:
        decision = session.decide(plan, plan.to_dict()["confirmation"])
    assert session.perform(decision)["state"] == "copied-before"


@pytest.mark.parametrize("target", ["private", "origin"])
@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
def test_close_propagates_original_interrupt_after_attempting_all_owned_closures(
    setup, monkeypatch, target, signal
):
    session, _, _, origin, _ = setup
    path = Path(_perform(session, "copy")["private_root"])
    close_files = files_module.RepositoryFiles.close
    close_origin = RepositoryOrigin.close
    calls = []
    fault = signal("synthetic cleanup interruption")

    def private_close(files):
        close_files(files)
        calls.append("private")
        if target == "private":
            raise fault

    def origin_close(held_origin):
        close_origin(held_origin)
        calls.append("origin")
        if target == "origin":
            raise fault

    monkeypatch.setattr(files_module.RepositoryFiles, "close", private_close)
    monkeypatch.setattr(RepositoryOrigin, "close", origin_close)
    with pytest.raises(signal) as caught:
        session.close()
    assert caught.value is fault
    assert calls == ["private", "origin"]
    result = caught.value.repository_session_result
    assert result["closed"] is True
    assert result["descriptor_cleanup"] == "unconfirmed"
    assert result["state"] == "recovery-required"
    assert session.closed and origin.closed
    assert path.is_dir() and (path / "project/app.py").read_bytes() == SOURCE.encode()
