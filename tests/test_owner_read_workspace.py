"""Current maintained owner-read bytes in temporary files; no model or guest."""

import copy
import hashlib
import json
import os
import stat
from importlib.resources import files
from pathlib import Path

import pytest

from authzest.runner import _owner_read_copy_files as copies
from authzest.runner import _owner_read_workspace as workspaces

pytestmark = pytest.mark.skipif(not copies.copy_supported(), reason="POSIX private copies only")

BASELINE = files("authzest.owner_read_demo").joinpath("availability.py").read_bytes()
TEST = (
    b"def test_owner_archive(owner_client):\n"
    b'    assert owner_client.get("/records/archived-note").status_code == 200\n'
)
PROPOSED = (
    b'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(copies, "_TEMP_PARENT", tmp_path)
    result = copies.stage_private_copy(BASELINE, TEST, PROPOSED, guard=lambda: None)
    assert result["status"] == "prepared"
    return result


def _adopt(prepared):
    return workspaces.OwnerReadWorkspace(prepared, BASELINE, TEST, PROPOSED, binding_id="current")


@pytest.fixture
def workspace(prepared):
    value = _adopt(prepared)
    try:
        yield value
    finally:
        value.close()


def _journal(workspace):
    return json.loads((workspace.path / "record.json").read_text())


def test_apply_restore_retain_exact_bytes_and_journal(workspace, monkeypatch):
    initial = workspace.snapshot()
    before = workspace.read_source()
    test = workspace.read_test()
    actual_replace = os.replace
    observations = []

    def observe(src, dst, **kwargs):
        if dst == copies.FILES[0]:
            record = _journal(workspace)
            observations.append(record["pending_operation"])
            assert record["state"] == "state-unconfirmed"
            assert record["files"][copies.FILES[0]]["identity"] == list(
                workspace.read_source().identity
            )
        return actual_replace(src, dst, **kwargs)

    monkeypatch.setattr(os, "replace", observe)
    applied = workspace.apply_source(before, guard=lambda: None)
    assert applied.data == PROPOSED and workspace.state == "applied-after"
    assert applied.identity[:2] != before.identity[:2]
    assert workspace.read_test() == test
    assert _journal(workspace)["state"] == "applied-after"
    restored = workspace.restore_source(applied, guard=lambda: None)
    assert restored.data == BASELINE and workspace.state == "restored-before"
    assert restored.identity[:2] != applied.identity[:2]
    assert workspace.read_test() == test
    record = _journal(workspace)
    assert record["pending_operation"] is None and record["state"] == "restored-before"
    assert record["restoration_status"] == "restored-before"
    assert record["binding_id"] == initial["binding_id"]
    assert record["files"][copies.FILES[0]]["sha256"] == _sha(BASELINE)
    assert record["files"][copies.FILES[1]]["identity"] == list(test.identity)
    assert observations == ["apply", "restore"]
    path = workspace.path
    workspace.close()
    assert {p.name for p in path.iterdir()} == {*copies.FILES, "record.json"}
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in path.iterdir())
    assert (path / copies.FILES[0]).read_bytes() == BASELINE
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        workspace.read_source()


def test_early_expiry_has_no_source_or_journal_effect_and_no_retry(workspace):
    before = workspace.read_source()
    record = workspace.read_record()

    def expire():
        raise TimeoutError

    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.apply_source(before, guard=expire)
    assert not caught.value.recovery_required and not caught.value.source_replace_attempted
    assert workspace.read_source() == before and workspace.read_record() == record
    assert {p.name for p in workspace.path.iterdir()} == {*copies.FILES, "record.json"}
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        workspace.apply_source(before, guard=lambda: pytest.fail("reused decision"))


def test_commit_guard_expiry_after_durable_intent_retains_pending(workspace):
    before = workspace.read_source()
    calls = []

    def guard():
        calls.append(_journal(workspace)["pending_operation"])

    def expired_commit():
        calls.append(_journal(workspace)["pending_operation"])
        raise TimeoutError

    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.apply_source(before, guard=guard, commit_guard=expired_commit)
    assert calls == [None, "apply"]
    assert caught.value.recovery_required and not caught.value.source_replace_attempted
    assert workspace.read_source() == before
    assert _journal(workspace)["pending_operation"] == "apply"
    assert workspace.state == "state-unconfirmed"
    assert any(p.name.startswith(".source-") for p in workspace.path.iterdir())


@pytest.mark.parametrize("change", ["edit", "inode", "symlink", "fifo", "hardlink", "mode"])
@pytest.mark.parametrize("name", copies.FILES)
def test_changed_artifacts_before_adoption_are_preserved(prepared, tmp_path, change, name):
    path = Path(prepared["path"])
    target = path / name
    original = target.read_bytes()
    if change == "edit":
        target.write_bytes(b"operator edit")
    elif change in {"inode", "symlink", "fifo", "hardlink"}:
        old = tmp_path / "kept-original"
        target.rename(old)
        if change == "inode":
            target.write_bytes(original)
            target.chmod(0o600)
        elif change == "symlink":
            target.symlink_to(old)
        elif change == "fifo":
            os.mkfifo(target, mode=0o600)
        else:
            os.link(old, target)
    else:
        target.chmod(0o644)
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        _adopt(prepared)
    assert not (path / "record.json").exists()
    if change == "edit":
        assert target.read_bytes() == b"operator edit"


@pytest.mark.parametrize("name", (*copies.FILES, "record.json"))
def test_user_edits_after_adoption_refuse_apply_without_overwrite(workspace, name):
    before = workspace.read_source()
    target = workspace.path / name
    target.write_bytes(b"operator edit")
    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.apply_source(before, guard=lambda: pytest.fail("changed input reached guard"))
    assert caught.value.recovery_required
    assert target.read_bytes() == b"operator edit"
    assert not caught.value.source_replace_attempted


def test_extra_entry_is_preserved_and_refuses_adoption(prepared):
    path = Path(prepared["path"])
    (path / "operator.txt").write_text("operator note")
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        _adopt(prepared)
    assert (path / "operator.txt").read_text() == "operator note"
    assert not (path / "record.json").exists()


def test_directory_path_substitution_refuses_source_write(workspace, tmp_path):
    before = workspace.read_source()
    original = workspace.path
    saved = tmp_path / "original-directory"
    original.rename(saved)
    original.mkdir(mode=0o700)
    (original / copies.FILES[0]).write_bytes(b"replacement directory")
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        workspace.apply_source(before, guard=lambda: pytest.fail("changed path"))
    assert (saved / copies.FILES[0]).read_bytes() == BASELINE
    assert (original / copies.FILES[0]).read_bytes() == b"replacement directory"


@pytest.mark.parametrize("phase", ["intent", "source", "completion"])
def test_rename_failures_retain_exact_pending_source_state(workspace, monkeypatch, phase):
    before = workspace.read_source()
    actual = os.replace
    record_renames = 0

    def fail(src, dst, **kwargs):
        nonlocal record_renames
        if dst == "record.json":
            record_renames += 1
        if (
            phase == "intent"
            and record_renames == 1
            or phase == "source"
            and dst == copies.FILES[0]
            or phase == "completion"
            and record_renames == 2
        ):
            raise OSError("maintainer failure seam")
        return actual(src, dst, **kwargs)

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.apply_source(before, guard=lambda: None)
    assert caught.value.recovery_required
    assert caught.value.source_replace_attempted == (phase != "intent")
    assert caught.value.source_replaced == (phase == "completion")
    expected = PROPOSED if phase == "completion" else BASELINE
    assert (workspace.path / copies.FILES[0]).read_bytes() == expected
    record = _journal(workspace)
    assert record["state"] == ("ready-before" if phase == "intent" else "state-unconfirmed")
    assert record["pending_operation"] == (None if phase == "intent" else "apply")


def test_failed_initial_journal_retains_partial_record_and_closes(prepared, monkeypatch):
    def fail(_fd, _view):
        raise OSError("write refused")

    monkeypatch.setattr(os, "write", fail)
    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        _adopt(prepared)
    assert caught.value.stage == "create-initial-record"
    assert caught.value.descriptor_cleanup_confirmed
    path = Path(prepared["path"])
    assert (path / "record.json").read_bytes() == b""
    assert (path / copies.FILES[0]).read_bytes() == BASELINE


def test_partial_source_stage_retains_failure_and_never_claims_ready(workspace, monkeypatch):
    before = workspace.read_source()

    def fail(_fd, _view):
        raise OSError("write refused")

    monkeypatch.setattr(os, "write", fail)
    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.apply_source(before, guard=lambda: pytest.fail("partial input"))
    assert caught.value.recovery_required
    assert (workspace.path / copies.FILES[0]).read_bytes() == BASELINE
    assert any(p.name.startswith(".source-") for p in workspace.path.iterdir())


def test_restore_preserves_operator_edit(workspace):
    after = workspace.apply_source(workspace.read_source(), guard=lambda: None)
    source = workspace.path / copies.FILES[0]
    source.write_bytes(b"operator fix")
    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.restore_source(after, guard=lambda: pytest.fail("operator edit"))
    assert source.read_bytes() == b"operator fix" and caught.value.recovery_required


def test_reading_guard_can_verify_actual_current_files(workspace):
    before = workspace.read_source()
    test = workspace.read_test()
    calls = []

    def check():
        calls.append(True)
        assert workspace.read_source() == before
        assert workspace.read_test() == test
        assert workspace.snapshot()["files"][copies.FILES[0]]["sha256"] == _sha(BASELINE)

    workspace.apply_source(before, guard=check)
    assert calls == [True, True]


def test_short_writes_complete_without_losing_bytes(workspace, monkeypatch):
    actual = os.write
    monkeypatch.setattr(os, "write", lambda fd, view: actual(fd, view[:5]))
    applied = workspace.apply_source(workspace.read_source(), guard=lambda: None)
    assert applied.data == PROPOSED
    assert workspace.restore_source(applied, guard=lambda: None).data == BASELINE


def test_journal_events_are_detached_bounded_and_preserve_artifacts(workspace):
    source, test = workspace.read_source(), workspace.read_test()
    details = {"plan_id": "before-current", "observation": {"status": "pending"}}
    workspace.record_event("before-dispatch", details)
    details["observation"]["status"] = "edited"
    record = _journal(workspace)
    assert record["history"] == [
        {
            "sequence": 0,
            "stage": "before-dispatch",
            "details": {"plan_id": "before-current", "observation": {"status": "pending"}},
        }
    ]
    assert workspace.state == "ready-before"
    assert workspace.read_source() == source and workspace.read_test() == test
    for _ in range(31):
        workspace.record_event("bounded-event", {"status": "kept"})
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        workspace.record_event("extra-event", {})
    assert len(_journal(workspace)["history"]) == 32
    assert (workspace.path / "record.json").stat().st_size < 65_536


def test_oversize_event_is_refused_before_a_write(workspace):
    record = workspace.read_record()
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        workspace.record_event("capture", {"stdout": "x" * 4096})
    assert workspace.read_record() == record and workspace.state == "ready-before"


def test_event_failure_is_uncertain_and_preserves_source(workspace, monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("journal rename refused")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(workspaces.OwnerReadWorkspaceError) as caught:
        workspace.record_event("before-dispatch", {"status": "pending"})
    assert caught.value.recovery_required and workspace.state == "state-unconfirmed"
    assert (workspace.path / copies.FILES[0]).read_bytes() == BASELINE


@pytest.mark.parametrize("field", ["status", "exit_code", "stage", "interrupted", "identity"])
def test_forged_preparation_shape_never_creates_a_record(prepared, field):
    changed = copy.deepcopy(prepared)
    if field == "identity":
        changed["files"][copies.FILES[0]]["identity"][0] = True
    else:
        changed[field] = None
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        _adopt(changed)
    assert not (Path(prepared["path"]) / "record.json").exists()


def test_stale_reviewed_source_never_reaches_guard(workspace):
    source = workspace.read_source()
    wrong = workspaces.FileState(source.data, (*source.identity[:-1], source.identity[-1] + 1))
    with pytest.raises(workspaces.OwnerReadWorkspaceError):
        workspace.apply_source(wrong, guard=lambda: pytest.fail("stale reviewed source"))
    assert (workspace.path / copies.FILES[0]).read_bytes() == BASELINE
