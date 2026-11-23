"""Fresh private-file observations over inert owned bytes, never a target import."""

import copy
import json
import os
import pickle
from dataclasses import FrozenInstanceError, replace

import pytest

from authzest.runner.repository_file_session import RepositorySessionError
from test_repository_file_session import AFTER, SOURCE, TEST, copy_ready, perform
from test_repository_file_session import setup as setup

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX private-file checkpoint")


def test_current_checkpoint_is_frozen_private_bytes_without_runtime_or_write_authority(setup):
    _, parent, create = setup
    session, path, _, _, _ = copy_ready(create)
    before_result = session.result()
    checkpoint = session._capture_runtime_checkpoint("before")
    assert session._capture_runtime_checkpoint("before") is checkpoint
    session._recheck_runtime_checkpoint(checkpoint)
    assert checkpoint.private_root == path
    assert checkpoint.session_id == before_result["session_id"]
    assert checkpoint.revision == 1
    assert dict(checkpoint.materials) == {
        "pkg/app.py": SOURCE.encode(),
        "pkg/__init__.py": b"",
        "auth.py": 'ROLE = "소유자"\r\n'.encode(),
    }
    assert checkpoint.test_path == "tests/test_authzest_regression.py"
    assert checkpoint.test_bytes == TEST.encode()
    assert "record.json" in dict(checkpoint.file_identities)
    journal = json.loads(checkpoint.journal_bytes)
    assert journal["revision"] == checkpoint.revision and journal["pending_operation"] is None
    assert list(parent.iterdir()) == [path]
    assert session.result() == before_result
    assert session.result()["execution_status"] == "not-run"
    assert not session.result()["verified_fix"]
    detached = checkpoint.response
    detached["proposal"]["after_text"] = "changed"
    assert checkpoint.response["proposal"]["after_text"] == AFTER
    with pytest.raises(FrozenInstanceError):
        checkpoint.phase = "after"


def test_after_checkpoint_replaces_issued_before_and_never_accepts_restored_or_old_objects(setup):
    root, _, create = setup
    session, _, _, _, _ = copy_ready(create)
    before = session._capture_runtime_checkpoint("before")
    perform(session, "accept-diff")
    with pytest.raises(RepositorySessionError):
        session._recheck_runtime_checkpoint(before)
    perform(session, "apply")
    after = session._capture_runtime_checkpoint("after")
    assert after is not before and after.revision == 3
    assert dict(after.materials)["pkg/app.py"] == AFTER.encode()
    session._recheck_runtime_checkpoint(after)
    with pytest.raises(RepositorySessionError):
        session._recheck_runtime_checkpoint(before)
    perform(session, "restore")
    for phase in ("before", "after"):
        with pytest.raises(RepositorySessionError):
            session._capture_runtime_checkpoint(phase)
    with pytest.raises(RepositorySessionError):
        session._recheck_runtime_checkpoint(after)
    assert (root / "pkg/app.py").read_bytes() == SOURCE.encode()


def test_equal_cloned_or_cross_session_checkpoint_cannot_be_adopted(setup):
    _, _, create = setup
    first, _, _, _, _ = copy_ready(create)
    second, _, _, _, _ = copy_ready(create)
    checkpoint = first._capture_runtime_checkpoint("before")
    second._capture_runtime_checkpoint("before")
    forged = replace(checkpoint)
    assert forged == checkpoint and forged is not checkpoint
    with pytest.raises(RepositorySessionError):
        first._recheck_runtime_checkpoint(forged)
    with pytest.raises(RepositorySessionError):
        second._recheck_runtime_checkpoint(checkpoint)
    first._recheck_runtime_checkpoint(checkpoint)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            operation(checkpoint)


@pytest.mark.parametrize("phase", ["after", "later", None, [], True])
def test_capture_wrong_phase_is_a_refusal_without_changing_a_healthy_copy(setup, phase):
    _, _, create = setup
    session, _, _, _, _ = copy_ready(create)
    with pytest.raises(RepositorySessionError):
        session._capture_runtime_checkpoint(phase)
    assert session.state == "copied-before"
    session._capture_runtime_checkpoint("before")


def test_pending_or_decided_file_operation_cannot_be_used_as_a_runtime_checkpoint(setup):
    _, _, create = setup
    session, _, _, _, _ = copy_ready(create)
    checkpoint = session._capture_runtime_checkpoint("before")
    plan = session.prepare("accept-diff")
    for _ in range(2):
        with pytest.raises(RepositorySessionError):
            session._capture_runtime_checkpoint("before")
        with pytest.raises(RepositorySessionError):
            session._recheck_runtime_checkpoint(checkpoint)
        if session._decision is None:
            session.decide(plan, plan.to_dict()["confirmation"])
    assert session.state == "copied-before"


@pytest.mark.parametrize("path", ["project/pkg/app.py", "project/auth.py", "record.json"])
def test_private_edit_latches_unconfirmed_state_and_preserves_edited_bytes(setup, path):
    _, _, create = setup
    session, root, _, _, _ = copy_ready(create)
    checkpoint = session._capture_runtime_checkpoint("before")
    target = root / path
    target.write_bytes(b"USER EDIT MUST SURVIVE")
    with pytest.raises(RepositorySessionError, match="integrity"):
        session._recheck_runtime_checkpoint(checkpoint)
    assert session.state == "recovery-required"
    assert target.read_bytes() == b"USER EDIT MUST SURVIVE"
    assert session.result()["failure"]["step"] == "runtime-checkpoint"
    with pytest.raises(RepositorySessionError):
        session._capture_runtime_checkpoint("before")


def test_same_bytes_different_inode_is_not_the_issued_current_checkpoint(setup):
    _, _, create = setup
    session, root, _, _, _ = copy_ready(create)
    checkpoint = session._capture_runtime_checkpoint("before")
    target = root / "project/pkg/app.py"
    other = root / "replacement"
    other.write_bytes(target.read_bytes())
    other.chmod(0o600)
    other.replace(target)
    with pytest.raises(RepositorySessionError):
        session._recheck_runtime_checkpoint(checkpoint)
    assert session.state == "recovery-required"


def test_original_drift_after_copy_does_not_reopen_or_override_the_private_binding(setup):
    origin, _, create = setup
    session, _, _, _, _ = copy_ready(create)
    checkpoint = session._capture_runtime_checkpoint("before")
    (origin / "pkg/app.py").write_text("EDITED ORIGINAL")
    session._recheck_runtime_checkpoint(checkpoint)
    assert dict(checkpoint.materials)["pkg/app.py"] == SOURCE.encode()
    assert (origin / "pkg/app.py").read_text() == "EDITED ORIGINAL"


def test_interrupted_verification_retains_primary_interrupt_and_clears_busy(setup, monkeypatch):
    _, _, create = setup
    session, path, _, _, _ = copy_ready(create)
    checkpoint = session._capture_runtime_checkpoint("before")

    def stop():
        raise KeyboardInterrupt("owned fake interruption")

    with monkeypatch.context() as patch:
        patch.setattr(session._files, "verify", stop)
        with pytest.raises(KeyboardInterrupt) as caught:
            session._recheck_runtime_checkpoint(checkpoint)
    assert caught.value.repository_session_result["state"] == "recovery-required"
    assert not session._busy and path.is_dir()


def test_closed_and_foreign_process_or_thread_cannot_recheck_live_objects(setup, monkeypatch):
    _, _, create = setup
    session, _, _, _, _ = copy_ready(create)
    checkpoint = session._capture_runtime_checkpoint("before")
    for name in ("_pid", "_thread"):
        with monkeypatch.context() as patch:
            patch.setattr(session, name, -1)
            with pytest.raises(RepositorySessionError):
                session._recheck_runtime_checkpoint(checkpoint)
    session._recheck_runtime_checkpoint(checkpoint)
    session.close()
    with pytest.raises(RepositorySessionError):
        session._recheck_runtime_checkpoint(checkpoint)
