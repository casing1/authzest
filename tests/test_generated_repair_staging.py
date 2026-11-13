"""Owned temporary inert bytes only; no generated import, pytest or engine."""

from __future__ import annotations

import ast
import asyncio
import builtins
import json
import os
import socket
import stat
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from authzest.runner import _generated_repair_staging as staging
from authzest.runner._generated_repair_workspace import GeneratedRepairWorkspace
from test_generated_repair_runtime_profile import profile
from test_generated_repair_workspace import _preview

pytestmark = pytest.mark.skipif(not staging.supported(), reason="POSIX descriptor staging")

# Teardown must remain usable while a test deliberately replaces staging's OS
# functions. These captured native calls only restore this test's ordinary owned
# directories so pytest can remove its synthetic readonly snapshots later.
_NATIVE_OPEN, _NATIVE_CLOSE, _NATIVE_FSTAT = os.open, os.close, os.fstat
_NATIVE_FCHMOD = getattr(os, "fchmod", None)
_NATIVE_GETEUID = getattr(os, "geteuid", None)
_NATIVE_SCANDIR = os.scandir


@pytest.fixture(autouse=True)
def restore_stage_permissions(tmp_path):
    yield
    if _NATIVE_FCHMOD is None or _NATIVE_GETEUID is None:
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK

    def owned_directory(name, *, parent=None, restore=True):
        try:
            fd = _NATIVE_OPEN(name, flags, **({} if parent is None else {"dir_fd": parent}))
        except OSError:
            return None
        info = _NATIVE_FSTAT(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != _NATIVE_GETEUID():
            _NATIVE_CLOSE(fd)
            return None
        if restore:
            _NATIVE_FCHMOD(fd, 0o700)
        return fd

    parent_fd = owned_directory(tmp_path, restore=False)
    if parent_fd is None:
        return
    try:
        with _NATIVE_SCANDIR(parent_fd) as entries:
            names = [entry.name for entry in entries]
        prefix = "authzest-generated-inputs-"
        for name in names:
            if (
                not name.startswith(prefix)
                or len(name) != len(prefix) + 32
                or any(char not in "0123456789abcdef" for char in name[len(prefix) :])
            ):
                continue
            root_fd = owned_directory(name, parent=parent_fd)
            if root_fd is None:
                continue
            try:
                input_fd = owned_directory("input", parent=root_fd)
                if input_fd is None:
                    continue
                try:
                    tests_fd = owned_directory("tests", parent=input_fd)
                    if tests_fd is not None:
                        _NATIVE_CLOSE(tests_fd)
                finally:
                    _NATIVE_CLOSE(input_fd)
            finally:
                _NATIVE_CLOSE(root_fd)
    finally:
        _NATIVE_CLOSE(parent_fd)


@pytest.fixture(autouse=True)
def keep_generated_text_inert(monkeypatch, request, tmp_path):
    assert len(request.node.nodeid) < 512
    assert ast.unparse(ast.Constant(value=None)) == "None"
    original_import, original_compile = builtins.__import__, builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Input-stage tests may only manage maintained temporary inert bytes")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app",
            "docker",
            "fastapi",
            "httpx",
            "openai",
            "requests",
            "uvicorn",
        } or name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    def ast_only_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.mark.parametrize("role", ["T", "A"])
@pytest.mark.parametrize("candidate", ["before", "after"])
def test_fresh_private_stage_has_exact_role_bytes_permissions_and_no_original_writes(
    tmp_path, role, candidate
):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    if candidate == "after":
        copy.apply_source(copy.read_source(), guard=lambda: None)
    original = (copy.read_source(), copy.read_test(), copy.read_record())
    stage = staging.GeneratedRepairInputStage(copy, candidate, role)
    try:
        assert stage.path.parent == copy.path.parent
        assert stage.path != copy.path and stage.path not in copy.path.parents
        assert stage.state == "staged-" + candidate
        assert stat.S_IMODE(stage.path.stat().st_mode) == 0o700
        assert stat.S_IMODE(stage.input_path.stat().st_mode) == 0o555
        assert set(path.name for path in stage.path.iterdir()) == {"input", "record.json"}
        source = stage.input_path / "app.py"
        assert source.read_bytes() == original[0].data
        assert stat.S_IMODE(source.stat().st_mode) == 0o444
        assert source.stat().st_nlink == 1 and source.stat().st_uid == os.geteuid()
        assert stat.S_IMODE((stage.path / "record.json").stat().st_mode) == 0o600
        if role == "T":
            assert set(path.name for path in stage.input_path.iterdir()) == {"app.py", "tests"}
            tests = stage.input_path / "tests"
            assert stat.S_IMODE(tests.stat().st_mode) == 0o555
            generated = tests / "test_generated_ownership.py"
            assert generated.read_bytes() == original[1].data
            assert stat.S_IMODE(generated.stat().st_mode) == 0o444
            assert generated.stat().st_nlink == 1
        else:
            assert set(path.name for path in stage.input_path.iterdir()) == {"app.py"}
            assert not (stage.input_path / "tests").exists()
        stage.assert_current()
        snapshot = stage.snapshot()
        assert snapshot["candidate"] == candidate and snapshot["role"] == role
        assert snapshot["filesystem_observed"] is True
        assert snapshot["runtime_invoked"] is False
        assert snapshot["execution_authorized"] is False
        assert snapshot["authorization_status"] == "unknown" and snapshot["verified_fix"] is False
        assert snapshot["original_checkpoint"]["source"]["identity"] == list(original[0].identity)
        record = json.loads((stage.path / "record.json").read_bytes())
        assert record["input_files"]["app.py"]["sha256"] == sha256(original[0].data).hexdigest()
        assert "record.json" not in record["input_files"]
        assert len(record["outer_core_identity"]) == 5
        assert (copy.read_source(), copy.read_test(), copy.read_record()) == original
    finally:
        stage.close()
        copy.close()


@pytest.mark.parametrize("role", ["T", "A"])
def test_staged_create_plan_binds_observed_stage_but_keeps_profile_unverified(tmp_path, role):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    stage = staging.GeneratedRepairInputStage(copy, "before", role)
    try:
        snapshot = stage.snapshot()
        plan = stage.prepare_create(profile(), "8" * 32, "9" * 32)
        data = plan.to_dict()
        assert data["stage_snapshot"] == snapshot
        assert data["status"] == "planned-not-executed"
        assert data["runtime_invoked"] is data["execution_authorized"] is False
        assert data["verified_fix"] is False and data["filesystem_observed"] is True
        create = data["container_create_plan"]
        assert create["role"] == role and create["runtime_invoked"] is False
        assert create["provenance"] == "caller-supplied-unverified"
        assert create["declared_files"][0]["source"] == str(stage.input_path / "app.py")
        assert create["declared_files"][0]["sha256"] == sha256(copy.read_source().data).hexdigest()
        assert all(str(copy.path) not in argument for argument in create["argv"])
        assert all(str(stage.path / "record.json") not in argument for argument in create["argv"])
        assert plan.plan_id.startswith("generated-repair-staged-create-plan-")
        with pytest.raises(FrozenInstanceError):
            plan.payload_json = "{}"
        stage.assert_current()
    finally:
        stage.close()
        copy.close()


def test_close_retains_all_stage_files_and_does_not_export_reopen_authority(tmp_path):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    stage = staging.GeneratedRepairInputStage(copy, "before", "T")
    snapshot = stage.snapshot()
    stage.close()
    stage.close()
    assert stage.state == "closed"
    assert stage.path.is_dir() and (stage.path / "record.json").is_file()
    assert (stage.input_path / "app.py").read_bytes() == copy.read_source().data
    assert snapshot["runtime_invoked"] is False
    with pytest.raises(staging.StageError):
        stage.snapshot()
    assert not hasattr(staging.GeneratedRepairInputStage, "resume")
    assert not hasattr(staging.GeneratedRepairInputStage, "execute")
    copy.close()


def test_allocation_guard_refusal_keeps_only_the_original_copy(tmp_path):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    original = set(tmp_path.iterdir())

    def refuse():
        raise ValueError("maintained refusal")

    try:
        with pytest.raises(staging.StageInitializationError) as captured:
            staging.GeneratedRepairInputStage(copy, "before", "T", _before_create=refuse)
        failure = captured.value
        assert failure.created_path is None and failure.stage == "allocation-guard"
        assert failure.allocation_attempted is False and failure.creation_confirmed is False
        assert failure.descriptor_cleanup_confirmed is True
        assert set(tmp_path.iterdir()) == original
        copy.read_source()
    finally:
        copy.close()


def test_a_stage_also_pins_the_original_test_and_record_checkpoint(tmp_path):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    stage = staging.GeneratedRepairInputStage(copy, "before", "A")
    try:
        (copy.path / "tests/test_generated_ownership.py").write_bytes(b"# edited inert text\n")
        with pytest.raises(staging.StageError):
            stage.assert_current()
        assert stage.state == "state-unconfirmed"
    finally:
        stage.close()
        copy.close()


def test_wrong_phase_and_relay_role_are_refused_before_allocation(tmp_path):
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    original = set(tmp_path.iterdir())
    try:
        with pytest.raises(staging.StageError):
            staging.GeneratedRepairInputStage(copy, "after", "T")
        with pytest.raises(staging.StageError):
            staging.GeneratedRepairInputStage(copy, "before", "B")
        assert set(tmp_path.iterdir()) == original
    finally:
        copy.close()
