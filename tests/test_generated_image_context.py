"""Minimal build contexts from maintained inert files, never Docker or Python inputs."""

from __future__ import annotations

import ast
import builtins
import copy
import encodings.cp437  # noqa: F401 -- trusted ZIP codec loaded before execution guards
import os
import stat
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from scripts import generated_image_context as contexts
from scripts import generated_image_inputs as inputs

from test_generated_image_inputs import (
    manifest_data,
    no_execution_or_network,  # noqa: F401
    wheel_bytes,
    write_inputs,
)

pytestmark = pytest.mark.skipif(not contexts._supported(), reason="POSIX private context writes")


@pytest.fixture(autouse=True)
def no_generated_execution(monkeypatch, tmp_path):
    assert tmp_path.is_dir()
    original = builtins.__import__
    original_compile = builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Context tests may only copy maintained inert bytes")

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "fastapi", "httpx", "openai", "uvicorn", "docker"}:
            forbidden()
        return original(name, *args, **kwargs)

    def ast_only_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    for name in ("eval", "exec"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)


@pytest.fixture
def source(tmp_path):
    repo, wheels, parent = (tmp_path / name for name in ("repo", "wheels", "output"))
    for path in (repo, wheels, parent):
        path.mkdir(mode=0o700)
    data = write_inputs(repo, manifest_data())

    def selected(role="T", platform="linux/arm64"):
        for existing in wheels.iterdir():
            existing.unlink()
        for name in data["roles"][role]["platforms"][platform]["packages"]:
            package = data["packages"][name]
            wheel = package["wheels"][platform]
            (wheels / wheel["filename"]).write_bytes(
                wheel_bytes(name, package["version"], tuple(wheel["requires_dist"]))
            )
        return repo, wheels, parent, role, platform

    selected.data = data
    return selected


@pytest.mark.parametrize("role", inputs.ROLES)
@pytest.mark.parametrize("platform", inputs.PLATFORMS)
def test_fresh_context_contains_only_fixed_selected_inputs(source, role, platform):
    args = source(role, platform)
    result = contexts.prepare_image_context(*args)
    checked = contexts.check_prepared_context(result.context_path, result)
    assert checked["status"] == "context-checked-not-built"
    assert result.receipt_path.parent == result.context_path.parent
    assert result.receipt_path not in result.context_path.parents
    assert result.receipt_path.read_bytes() == result.payload_json.encode()
    assert checked["role"] == role and checked["platform"] == platform
    assert checked["wheel_count"] == len(
        source.data["roles"][role]["platforms"][platform]["packages"]
    )
    assert set(path.name for path in result.context_path.iterdir()) == {
        "Dockerfile",
        "requirements.txt",
        "assets",
        "wheels",
    }
    assert set(path.name for path in (result.context_path / "assets").iterdir()) == set(
        inputs.expected_assets(role)
    )
    assert set(path.name for path in (result.context_path / "wheels").iterdir()) == {
        source.data["packages"][name]["wheels"][platform]["filename"]
        for name in source.data["roles"][role]["platforms"][platform]["packages"]
    }
    for item in checked["files"]:
        value = (result.context_path / item["path"]).lstat()
        assert stat.S_IMODE(value.st_mode) == 0o600
        assert stat.S_ISREG(value.st_mode) and value.st_nlink == 1
        assert value.st_uid == os.geteuid()
    for path in (
        result.context_path.parent,
        result.context_path,
        result.context_path / "wheels",
        result.context_path / "assets",
    ):
        assert stat.S_IMODE(path.lstat().st_mode) == 0o700
    assert not any(
        name in result.payload_json for name in (str(args[0]), str(args[1]), str(args[2]))
    )
    for key in (
        "image_built",
        "build_invoked",
        "runtime_invoked",
        "runtime_ready",
        "ready",
        "execution_authorized",
    ):
        assert checked[key] is False
    with pytest.raises(FrozenInstanceError):
        result.context_path = Path("/different")


def test_distinct_calls_never_reuse_or_delete_a_previous_context(source):
    args = source("B")
    first = contexts.prepare_image_context(*args)
    second = contexts.prepare_image_context(*args)
    assert first.context_path != second.context_path
    assert first.receipt_path.read_bytes() == first.payload_json.encode()
    assert contexts.check_prepared_context(first.context_path, first)["image_built"] is False
    assert contexts.check_prepared_context(second.context_path, second)["image_built"] is False


@pytest.mark.parametrize("change", ["bytes", "mode", "extra", "link", "record", "record-inode"])
def test_changed_context_or_external_receipt_is_refused(source, change):
    result = contexts.prepare_image_context(*source("B"))
    target = result.context_path / "Dockerfile"
    if change == "bytes":
        target.write_bytes(b"# changed inert recipe\n")
    elif change == "mode":
        target.chmod(0o644)
    elif change == "extra":
        (result.context_path / "unexpected.py").write_bytes(b"# inert extra\n")
    elif change == "link":
        target.unlink()
        target.symlink_to(result.receipt_path)
    elif change == "record":
        result.receipt_path.write_bytes(b"{}")
    else:
        alternate = result.receipt_path.parent / "replacement.json"
        alternate.write_bytes(result.receipt_path.read_bytes())
        alternate.chmod(0o600)
        os.replace(alternate, result.receipt_path)
    with pytest.raises((contexts.ImageContextError, inputs.ImageInputsError)):
        contexts.check_prepared_context(result.context_path, result)


@pytest.mark.parametrize("overlap", ["source-child", "wheel-child", "ancestor"])
def test_output_parent_cannot_overlap_either_source_root(source, overlap):
    repo, wheels, parent, role, platform = source("B")
    if overlap == "ancestor":
        parent = repo.parent
        parent.chmod(0o700)
    else:
        parent = (repo if overlap == "source-child" else wheels) / "private-output"
        parent.mkdir(mode=0o700)
    before = set(parent.iterdir())
    with pytest.raises(contexts.ImageContextError):
        contexts.prepare_image_context(repo, wheels, parent, role, platform)
    assert set(parent.iterdir()) == before


def test_partial_write_failure_is_retained_without_touching_existing_files(source, monkeypatch):
    args = source("B")
    marker = args[2] / "existing-user-file"
    marker.write_bytes(b"owned test marker")
    original = contexts._write_file
    count = []

    def fail(directory, name, raw):
        count.append(name)
        if len(count) == 2:
            raise OSError("controlled preparation failure")
        return original(directory, name, raw)

    monkeypatch.setattr(contexts, "_write_file", fail)
    with pytest.raises(contexts.ImageContextError) as caught:
        contexts.prepare_image_context(*args)
    failure = caught.value
    assert failure.created_bundle.is_dir() and failure.allocation_attempted
    assert (failure.created_bundle / "context/Dockerfile").is_file()
    assert not (failure.created_bundle / "receipt.json").exists()
    assert failure.output_descriptor_cleanup_confirmed is True
    assert marker.read_bytes() == b"owned test marker"


def test_existing_collision_is_not_opened_reused_or_deleted(source, monkeypatch):
    args = source("B")
    name = "authzest-image-context-" + "a" * 32
    target = args[2] / name
    target.mkdir(mode=0o700)
    marker = target / "user-file"
    marker.write_bytes(b"keep existing output")
    monkeypatch.setattr(contexts.uuid, "uuid4", lambda: type("Nonce", (), {"hex": "a" * 32})())
    with pytest.raises(contexts.ImageContextError) as caught:
        contexts.prepare_image_context(*args)
    assert caught.value.created_bundle is None and caught.value.ownership_uncertain is False
    assert marker.read_bytes() == b"keep existing output"


def test_constructed_receipt_with_execution_flags_is_refused(source):
    result = contexts.prepare_image_context(*source("B"))
    forged = copy.deepcopy(result.to_dict())
    forged["runtime_ready"] = True
    altered = replace(result, payload_json=inputs._canonical(forged).decode())
    with pytest.raises(contexts.ImageContextError):
        contexts.check_prepared_context(result.context_path, altered)


def test_unreturned_allocation_is_not_reported_as_no_files(source, monkeypatch):
    args = source("B")
    original = os.mkdir

    def mkdir(name, *more, **kwargs):
        result = original(name, *more, **kwargs)
        if str(name).startswith("authzest-image-context-"):
            raise OSError("after controlled directory creation")
        return result

    with monkeypatch.context() as change:
        change.setattr(contexts, "_supported", lambda: True)
        change.setattr(os, "mkdir", mkdir)
        with pytest.raises(contexts.ImageContextError) as caught:
            contexts.prepare_image_context(*args)
    failure = caught.value
    assert failure.created_bundle is None and failure.planned_bundle.is_dir()
    assert failure.allocation_attempted and failure.ownership_uncertain


def test_file_close_uncertainty_is_not_erased_by_directory_cleanup(source, monkeypatch):
    args = source("B")
    original_write, original_close = contexts._write_file, os.close

    def write(*arguments):
        failed = []

        def close(fd):
            value = os.fstat(fd)
            original_close(fd)
            if stat.S_ISREG(value.st_mode) and not failed:
                failed.append(True)
                raise OSError("after controlled file close")

        with monkeypatch.context() as fault:
            fault.setattr(os, "close", close)
            return original_write(*arguments)

    monkeypatch.setattr(contexts, "_write_file", write)
    with pytest.raises(contexts.ImageContextError) as caught:
        contexts.prepare_image_context(*args)
    assert caught.value.created_bundle.is_dir()
    assert caught.value.output_descriptor_cleanup_confirmed is False


def test_windows_write_scope_is_explicitly_unsupported(source, monkeypatch):
    args = source("B")
    before = set(args[2].iterdir())
    with monkeypatch.context() as change:
        change.setattr(contexts.os, "name", "nt")
        with pytest.raises(contexts.ImageContextError):
            contexts.prepare_image_context(*args)
    assert set(args[2].iterdir()) == before
