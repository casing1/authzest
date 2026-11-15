"""Adversarial inert metadata: no dependency imports, installers or Engine calls."""

from __future__ import annotations

import copy
import io
import json
import os
import socket
import struct
import subprocess
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest
from scripts import generated_image_inputs as inputs

from test_generated_image_inputs import manifest_data, wheel_bytes, write_inputs


@pytest.fixture(autouse=True)
def no_execution_or_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        pytest.fail("Inert image input verification must not execute or contact anything")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(os, "system", blocked)
    monkeypatch.setattr(os, "execve", blocked)


def test_committed_candidate_checks_only_input_bytes():
    result = inputs.check_image_inputs(Path(__file__).resolve().parents[1])
    assert result["base_metadata_bytes_verified"] is True
    assert result["source_bytes_verified"] is True
    assert result["wheel_bytes_verified"] is False
    assert result["image_ids"] is None
    assert result["contents_verified"] is result["runtime_ready"] is False
    assert result["runtime_invoked"] is result["execution_authorized"] is False


@pytest.mark.parametrize(
    "requirement",
    [
        "not-present; sys_platform == 'linux'",
        "not-present; platform_machine == 'x86_64'",
        "not-present; python_full_version == '3.12.10'",
        "not-present; implementation_name == 'cpython'",
        "starlette[unreviewed]>=1",
        "starlette @ https://example.invalid/foreign.whl",
        "starlette; platform_release == 'unknown'",
        "starlette; platform_version != 'unknown'",
    ],
)
def test_target_markers_and_active_dependency_boundaries(requirement):
    data = manifest_data()
    for platform in inputs.PLATFORMS:
        data["packages"]["fastapi"]["wheels"][platform]["requires_dist"] = [requirement]
    with pytest.raises(inputs.ImageInputsError):
        inputs.render_lock(data, "T", "linux/amd64")


def test_linux_target_does_not_use_host_platform_or_inactive_extras():
    data = manifest_data()
    for platform in inputs.PLATFORMS:
        data["packages"]["fastapi"]["wheels"][platform]["requires_dist"] += [
            "not-present; sys_platform == 'darwin'",
            "not-present; sys_platform == 'win32'",
            "not-present; extra == 'standard'",
            "not-present; python_full_version == '3.12.11'",
        ]
    assert "starlette==1.0" in inputs.render_lock(data, "T", "linux/arm64")


def test_unused_package_cannot_expand_the_fixed_inventory():
    data = manifest_data()
    extra = copy.deepcopy(data["packages"]["httpx"])
    for wheel in extra["wheels"].values():
        wheel["filename"] = "unused-1.0-py3-none-any.whl"
        wheel["url"] = "https://files.pythonhosted.org/packages/synthetic/" + wheel["filename"]
    data["packages"]["unused"] = extra
    with pytest.raises(inputs.ImageInputsError, match="Unneeded"):
        inputs.render_lock(data, "T", "linux/amd64")


@pytest.mark.parametrize("value", [True, -1, 0, 16_777_217])
def test_wheel_size_requires_positive_bounded_integer(value):
    data = manifest_data()
    data["packages"]["httpx"]["wheels"]["linux/amd64"]["size"] = value
    with pytest.raises(inputs.ImageInputsError):
        inputs.render_lock(data, "T", "linux/amd64")


@pytest.mark.parametrize("change", ["dockerfile", "recipe-hash", "base-link", "base-hardlink"])
def test_observed_recipe_and_base_file_aliases_are_refused(tmp_path, change):
    data = write_inputs(tmp_path, manifest_data())
    base = tmp_path / inputs.IMAGES
    if change == "dockerfile":
        target = base / "dockerfiles/linux-amd64-A.Dockerfile"
        target.write_bytes(target.read_bytes().replace(b"--network=none", b"--network=host"))
    elif change == "recipe-hash":
        data["roles"]["T"]["platforms"]["linux/amd64"]["recipe_sha256"] = "e" * 64
        (base / "manifest.json").write_text(json.dumps(data))
    else:
        target = base / "base/index.json"
        original = tmp_path / "original-index"
        target.rename(original)
        if change == "base-link":
            try:
                target.symlink_to(original)
            except OSError:
                if os.name == "nt":
                    pytest.skip("Windows symlink privilege is unavailable")
                raise
        else:
            target.hardlink_to(original)
    with pytest.raises(inputs.ImageInputsError):
        inputs.check_image_inputs(tmp_path)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"same":1,"same":2}',
        b'{"x":NaN}',
        b'{"x":1.5}',
        b'{"x":' + b"[" * 18 + b"0" + b"]" * 18 + b"}",
    ],
)
def test_unbounded_or_ambiguous_json_is_refused(tmp_path, raw):
    write_inputs(tmp_path, manifest_data())
    (tmp_path / inputs.IMAGES / "manifest.json").write_bytes(raw)
    with pytest.raises(inputs.ImageInputsError):
        inputs.check_image_inputs(tmp_path)


def _wheelhouse(tmp_path, raw=None):
    data = manifest_data()
    if raw is not None:
        data["packages"]["httpx"]["wheels"]["linux/amd64"].update(
            sha256=sha256(raw).hexdigest(), size=len(raw)
        )
    root = tmp_path / "repo"
    data = write_inputs(root, data)
    directory = tmp_path / "wheels"
    directory.mkdir()
    for name in data["roles"]["T"]["platforms"]["linux/amd64"]["packages"]:
        entry = data["packages"][name]["wheels"]["linux/amd64"]
        (directory / entry["filename"]).write_bytes(
            raw
            if name == "httpx" and raw is not None
            else wheel_bytes(name, requires_dist=tuple(entry["requires_dist"]))
        )
    return root, directory


@pytest.mark.parametrize("change", ["missing", "corrupt", "symlink", "hardlink", "directory"])
def test_wheelhouse_requires_exact_ordinary_pinned_files(tmp_path, change):
    root, directory = _wheelhouse(tmp_path)
    target = directory / "httpx-1.0-py3-none-any.whl"
    if change == "missing":
        target.unlink()
    elif change == "corrupt":
        target.write_bytes(target.read_bytes() + b"x")
    elif change == "directory":
        target.unlink()
        target.mkdir()
    else:
        original = tmp_path / "original-wheel"
        target.rename(original)
        if change == "symlink":
            try:
                target.symlink_to(original)
            except OSError:
                if os.name == "nt":
                    pytest.skip("Windows symlink privilege is unavailable")
                raise
        else:
            target.hardlink_to(original)
    with pytest.raises(inputs.ImageInputsError):
        inputs.verify_wheelhouse(root, directory, "T", "linux/amd64")


@pytest.mark.parametrize("change", ["dishonest-count", "zip64", "directory-offset"])
def test_zip_directory_limits_are_enforced_before_eager_parser(monkeypatch, change):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for number in range(4097 if change != "directory-offset" else 1):
            archive.writestr(str(number), b"")
    raw = output.getvalue()
    end = raw.rfind(b"PK\x05\x06")
    fields = list(struct.unpack("<4s4H2IH", raw[end:]))
    if change == "zip64":
        record = struct.pack(
            "<4sQ2H2L4Q",
            b"PK\x06\x06",
            44,
            45,
            45,
            0,
            0,
            fields[4],
            fields[4],
            fields[5],
            fields[6],
        )
        locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, end, 1)
        fields[3:7] = [0, 0, 0, 0]
        raw = raw[:end] + record + locator + struct.pack("<4s4H2IH", *fields)
    else:
        if change == "dishonest-count":
            fields[3:5] = [0, 0]
        else:
            fields[6] += 1
        raw = raw[:end] + struct.pack("<4s4H2IH", *fields)

    def eager_parser_forbidden(*_args, **_kwargs):
        pytest.fail("Invalid ZIP directory reached the eager parser")

    monkeypatch.setattr(inputs.zipfile, "ZipFile", eager_parser_forbidden)
    with pytest.raises(inputs.ImageInputsError):
        inputs._metadata(raw, {}, "httpx", "1.0", set())


@pytest.mark.parametrize(
    "change", ["path", "symlink", "duplicate-name", "dependency", "tags", "oversized-metadata"]
)
def test_matching_digest_does_not_bypass_zip_metadata_validation(tmp_path, change):
    initial = wheel_bytes("httpx")
    with zipfile.ZipFile(io.BytesIO(initial)) as archive:
        members = {entry.filename: archive.read(entry) for entry in archive.infolist()}
    if change == "dependency":
        members["httpx-1.0.dist-info/METADATA"] = members["httpx-1.0.dist-info/METADATA"].replace(
            b"Requires-Python: >=3.12\n", b"Requires-Python: >=3.12\nRequires-Dist: foreign>=1\n"
        )
    elif change == "tags":
        members["httpx-1.0.dist-info/WHEEL"] = members["httpx-1.0.dist-info/WHEEL"].replace(
            b"py3-none-any", b"cp312-cp312-macosx_14_0_arm64"
        )
    elif change == "oversized-metadata":
        members["httpx-1.0.dist-info/METADATA"] += b"x" * 262_145
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
        if change == "path":
            archive.writestr("../outside", b"inert")
        elif change == "symlink":
            info = zipfile.ZipInfo("linked")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            archive.writestr(info, b"outside")
        elif change == "duplicate-name":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr("httpx-1.0.dist-info/WHEEL", members["httpx-1.0.dist-info/WHEEL"])
    root, directory = _wheelhouse(tmp_path, output.getvalue())
    with pytest.raises(inputs.ImageInputsError):
        inputs.verify_wheelhouse(root, directory, "T", "linux/amd64")
