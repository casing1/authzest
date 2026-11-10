"""Owned temporary-file tests only; generated Python text is never executed."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.codex.generated_repair import (
    build_generated_repair_request,
    validate_generated_repair_proposal,
)
from authzest.runner import _generated_repair_workspace as workspace
from authzest.runner.generated_repair_verification import (
    GeneratedRepairVerificationPreview,
    build_generated_repair_verification_preview,
)

pytestmark = pytest.mark.skipif(not workspace.supported(), reason="POSIX private-copy operations")


def _preview(status="proposed-change"):
    request = build_generated_repair_request()
    data = request.to_dict()
    source = data["scenario"]["source"]
    proposal = validate_generated_repair_proposal(
        canonical(
            {
                "schema_version": "1.0",
                "request_id": request.request_id,
                "status": status,
                "rationale": "Maintained inert filesystem fixture, not a repair.",
                "evidence_ids": list(data["evidence_ids"].values()),
                "assumptions": ["No generated text is executed."],
                "uncertainties": ["No runtime observation exists."],
                "limitations": ["Private file I/O only."],
                "proposal": {
                    "source_path": "app.py",
                    "before_sha256": source["sha256"],
                    "after_text": source["text"] + "\n# Maintained inert file-I/O candidate.\n",
                    "test_path": "tests/test_generated_ownership.py",
                    "test_text": "# Maintained inert test text.\n",
                }
                if status == "proposed-change"
                else None,
            }
        ),
        request,
    )
    return build_generated_repair_verification_preview(request, proposal)


def test_fresh_copy_has_exact_private_files_and_closed_non_runtime_record(tmp_path):
    preview = _preview()
    copy = workspace.GeneratedRepairWorkspace(preview, _parent=tmp_path)
    try:
        assert copy.path.parent == tmp_path
        assert stat.S_IMODE(copy.path.stat().st_mode) == 0o700
        assert stat.S_IMODE((copy.path / "tests").stat().st_mode) == 0o700
        assert copy.state == "ready-before"
        source = copy.read_source()
        assert (
            source.data
            == build_generated_repair_request().to_dict()["scenario"]["source"]["text"].encode()
        )
        assert copy.read_test().data == b"# Maintained inert test text.\n"
        for name in workspace._FILES:
            info = (copy.path / name).stat()
            assert stat.S_IMODE(info.st_mode) == 0o600
            assert info.st_nlink == 1
            assert info.st_uid == os.geteuid()
        assert (copy.path / "before.txt").read_bytes() == source.data
        assert (copy.path / "test.txt").read_bytes() == copy.read_test().data
        record = json.loads(copy.read_record().data)
        assert record["kind"] == "generated-repair-private-workspace-record"
        assert record["schema_version"] == "1.0"
        assert record["verification_preview_id"] == preview.verification_preview_id
        assert record["phase"] == "ready-before"
        assert record["execution_status"] == "not-run"
        assert record["authorization_status"] == "unknown"
        assert record["approval"] == "not-provided"
        assert record["verified_fix"] is False
        assert record["source_application"] == "not-run"
        assert record["test_materialization"] == "materialized-private-copy"
        assert sum((copy.path / name).stat().st_size for name in workspace._FILES) < 2_097_152
    finally:
        copy.close()
    assert (copy.path / "app.py").is_file()
    with pytest.raises(workspace.WorkspaceError, match="integrity"):
        copy.read_source()


def test_apply_and_restore_are_exact_source_only_single_use_with_independent_guards(tmp_path):
    copy = workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    try:
        before, test = copy.read_source(), copy.read_test()
        calls = []
        after = copy.apply_source(before, guard=lambda: calls.append("apply"))
        assert calls == ["apply"]
        assert copy.state == "applied-after"
        assert after.data == (copy.path / "after.txt").read_bytes()
        assert after.identity != before.identity
        assert copy.read_test() == test
        assert json.loads(copy.read_record().data)["source_application"] == "applied-copy-only"
        with pytest.raises(workspace.WorkspaceError, match="phase"):
            copy.apply_source(after, guard=lambda: calls.append("not-called"))
        restored = copy.restore_source(after, guard=lambda: calls.append("restore"))
        assert calls == ["apply", "restore"]
        assert restored.data == before.data
        assert restored.identity != before.identity
        assert copy.read_test() == test
        assert copy.state == "restored-before"
        record = json.loads(copy.read_record().data)
        assert record["restoration"] == "restored-before"
        assert record["execution_status"] == "not-run"
        with pytest.raises(workspace.WorkspaceError, match="phase"):
            copy.apply_source(restored, guard=lambda: None)
        with pytest.raises(workspace.WorkspaceError, match="phase"):
            copy.restore_source(restored, guard=lambda: None)
    finally:
        copy.close()


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_non_change_is_rejected_before_allocating_any_directory(tmp_path, status):
    with pytest.raises(workspace.WorkspaceError, match="proposed change"):
        workspace.GeneratedRepairWorkspace(_preview(status), _parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_forged_preview_rejected_before_any_directory(tmp_path):
    value = _preview().to_dict()
    value["verified_fix"] = True
    forged = GeneratedRepairVerificationPreview(canonical(value))
    with pytest.raises(ContractError):
        workspace.GeneratedRepairWorkspace(forged, _parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_construction_retains_partial_copy_with_initialization_stage(monkeypatch, tmp_path):
    original = workspace.os.open

    def fail_after(name, flags, *args, **kwargs):
        if name == "after.txt":
            raise OSError("Maintained fault injection")
        return original(name, flags, *args, **kwargs)

    monkeypatch.setattr(workspace.os, "open", fail_after)
    monkeypatch.setattr(workspace, "supported", lambda: True)
    with pytest.raises(workspace.WorkspaceInitializationError) as captured:
        workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    error = captured.value
    assert error.initialization_stage == "create-after.txt"
    assert error.file_states["app.py"] == "confirmed"
    assert error.file_states["after.txt"] == "creation-attempted"
    assert error.file_states["record.json"] == "not-created"
    assert error.created_path.is_dir()
    assert (error.created_path / "app.py").is_file()
    assert not (error.created_path / "after.txt").exists()


def test_two_copies_are_fresh_and_do_not_reopen_existing_content(tmp_path):
    first = workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    second = workspace.GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    try:
        assert first.path != second.path
        first.apply_source(first.read_source(), guard=lambda: None)
        assert second.state == "ready-before"
        assert first.read_source().data != second.read_source().data
    finally:
        first.close()
        second.close()


def test_module_remains_private_and_has_no_destination_or_execution_api():
    import inspect

    parameters = inspect.signature(workspace.GeneratedRepairWorkspace).parameters
    assert set(parameters) == {"preview", "_parent"}
    assert not any(
        hasattr(workspace.GeneratedRepairWorkspace, name)
        for name in ("execute", "resume", "write_record", "approve", "run")
    )
    assert not issubclass(workspace.GeneratedRepairWorkspace, Path)
