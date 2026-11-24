"""HTTP-only pinned declarations and opaque ZIPs; no build or target execution."""

from __future__ import annotations

import copy
import io
import json
import os
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest
from scripts import generated_image_inputs as shared
from scripts import repository_http_image_inputs as inputs

from helpers.repository_http_image_data import make_http_fixture
from test_generated_image_inputs import (
    no_execution_or_network,  # noqa: F401
    wheel_bytes,
)


def write_manifest(fixture):
    (fixture.repo / inputs.IMAGES / "manifest.json").write_text(json.dumps(fixture.data))


def test_maintained_inputs_and_default_cli_are_source_only(capsys):
    assert inputs.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["kind"] == "repository-http-image-input-check"
    assert report["schema_version"] == "2.0"
    assert report["base_reference_sha256"] == inputs.BASE_REFERENCE_SHA256
    assert [item["role"] for item in report["recipes"]] == ["A", "B"]
    assert report["image_ids"] is None
    for field in (
        "wheel_bytes_verified",
        "contents_verified",
        "runtime_ready",
        "runtime_invoked",
        "build_invoked",
        "execution_authorized",
    ):
        assert report[field] is False


@pytest.mark.parametrize("role", inputs.ROLES)
def test_synthetic_selected_wheel_set_is_observed_but_never_ready(tmp_path, monkeypatch, role):
    f = make_http_fixture(tmp_path, monkeypatch, role)
    data, base, entry = inputs.selected_inputs(f.repo, role, "linux/arm64")
    assert data == f.data and base == f.base
    assert entry == data["roles"][role]["platforms"]["linux/arm64"]
    report = inputs.verify_wheelhouse(f.repo, f.wheelhouse, role, "linux/arm64")
    assert report["kind"] == "repository-http-wheelhouse-check"
    assert report["role"] == role and report["platform"] == "linux/arm64"
    assert report["wheel_count"] == len(base["roles"][role]["platforms"]["linux/arm64"]["packages"])
    assert report["wheel_bytes_verified"] is True
    assert report["runtime_ready"] is False and report["execution_authorized"] is False
    assert (
        report["manifest_sha256"]
        == sha256((f.repo / inputs.IMAGES / "manifest.json").read_bytes()).hexdigest()
    )
    assert (
        report["base_reference_sha256"]
        == sha256((f.repo / inputs.BASE_REFERENCE).read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "role,platform",
    [
        ("T", "linux/arm64"),
        ("A", "linux/amd64"),
        ("B", "darwin/arm64"),
        (None, "linux/arm64"),
        ([], "linux/arm64"),
        ("A", {}),
    ],
)
def test_unsupported_selection_refused_before_input_reads(monkeypatch, role, platform):
    def forbidden(*args):
        pytest.fail("Unsupported mode must not inspect inputs")

    monkeypatch.setattr(inputs, "_load", forbidden)
    with pytest.raises(inputs.ImageInputsError):
        inputs.selected_inputs(Path("/nonexistent"), role, platform)
    with pytest.raises(inputs.ImageInputsError):
        inputs.verify_wheelhouse(Path("/nonexistent"), Path("/nonexistent"), role, platform)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "1.0"),
        ("kind", "generated-repair-image-inputs"),
        ("status", "candidate-not-built"),
        ("image_ids", {}),
        ("contents_verified", True),
        ("contents_verified", 0),
        ("runtime_ready", True),
        ("base_reference", "../manifest.json"),
        ("base_reference_sha256", "0" * 64),
    ],
)
def test_closed_http_header_rejects_old_or_tampered_declarations(tmp_path, monkeypatch, key, value):
    f = make_http_fixture(tmp_path, monkeypatch)
    f.data[key] = value
    write_manifest(f)
    with pytest.raises(inputs.ImageInputsError):
        inputs.check_image_inputs(f.repo)


@pytest.mark.parametrize(
    "change",
    [
        "extra-role",
        "missing-role",
        "source-path",
        "asset",
        "extra-platform",
        "schema",
        "kind",
        "role",
        "platform",
        "base",
        "lock-path",
        "lock-hash",
        "dockerfile",
        "dockerfile-hash",
        "recipe-hash",
        "recipe-assets",
        "extra-field",
    ],
)
def test_closed_http_role_and_recipe_binding(tmp_path, monkeypatch, change):
    f = make_http_fixture(tmp_path, monkeypatch)
    role = f.data["roles"]["A"]
    entry = role["platforms"]["linux/arm64"]
    if change == "extra-role":
        f.data["roles"]["T"] = copy.deepcopy(role)
    elif change == "missing-role":
        del f.data["roles"]["B"]
    elif change == "source-path":
        role["asset_sources"]["app_launcher.py"] = "app.py"
    elif change == "asset":
        role["assets"]["app_launcher.py"] = "0" * 64
    elif change == "extra-platform":
        role["platforms"]["linux/amd64"] = copy.deepcopy(entry)
    elif change == "schema":
        entry["schema_version"] = "1.0"
    elif change == "kind":
        entry["kind"] = "repository-image-recipe"
    elif change == "role":
        entry["role"] = "T"
    elif change == "platform":
        entry["platform"] = "linux/amd64"
    elif change == "base":
        entry["base_manifest_sha256"] = "0" * 64
    elif change == "lock-path":
        entry["dependency_lock_path"] = "runtime/other-lock.txt"
    elif change == "lock-hash":
        entry["dependency_lock_sha256"] = "0" * 64
    elif change == "dockerfile":
        entry["dockerfile"] = "../Dockerfile"
    elif change == "dockerfile-hash":
        entry["dockerfile_sha256"] = "0" * 64
    elif change == "recipe-hash":
        entry["recipe_sha256"] = "0" * 64
    elif change == "recipe-assets":
        entry["assets"] = {}
    else:
        entry["unexpected"] = False
    write_manifest(f)
    with pytest.raises(inputs.ImageInputsError):
        inputs.check_image_inputs(f.repo)


@pytest.mark.parametrize(
    "relative",
    [
        "runtime/repository_http/_guest_common.py",
        "runtime/repository_http/app_launcher.py",
        "runtime/repository_http/relay_launcher.py",
        "src/authzest/runner/_repository_http_manifest.py",
        "src/authzest/runner/_repository_http.py",
        "src/authzest/runner/_repository_http_transport.py",
        "runtime/repository_http/images/Dockerfile.linux-arm64-A",
        "runtime/repository_http/images/Dockerfile.linux-arm64-B",
        "runtime/generated_repair/images/locks/linux-arm64-A.txt",
        "runtime/generated_repair/images/locks/linux-arm64-B.txt",
        "runtime/generated_repair/images/manifest.json",
        "runtime/generated_repair/images/base/index.json",
    ],
)
def test_current_asset_recipe_lock_and_base_byte_drift_is_rejected(tmp_path, monkeypatch, relative):
    f = make_http_fixture(tmp_path, monkeypatch)
    with (f.repo / relative).open("ab") as stream:
        stream.write(b"\n# changed inert bytes\n")
    with pytest.raises(inputs.ImageInputsError):
        inputs.check_image_inputs(f.repo)


@pytest.mark.parametrize("change", ["missing", "extra", "bytes", "size"])
def test_selected_wheel_membership_and_bytes_are_exact(tmp_path, monkeypatch, change):
    f = make_http_fixture(tmp_path, monkeypatch)
    first = next(f.wheelhouse.iterdir())
    if change == "missing":
        first.unlink()
    elif change == "extra":
        (f.wheelhouse / "unexpected.txt").write_bytes(b"inert")
    elif change == "bytes":
        first.write_bytes(bytes([first.read_bytes()[0] ^ 1]) + first.read_bytes()[1:])
    else:
        first.write_bytes(first.read_bytes() + b"x")
    with pytest.raises(inputs.ImageInputsError):
        inputs.verify_wheelhouse(f.repo, f.wheelhouse, "A", "linux/arm64")


@pytest.mark.skipif(os.name != "posix", reason="POSIX link fixtures")
@pytest.mark.parametrize("hard", [False, True])
@pytest.mark.parametrize("member", ["source", "base", "wheel"])
def test_input_and_wheel_links_refused(tmp_path, monkeypatch, hard, member):
    f = make_http_fixture(tmp_path, monkeypatch)
    target = (
        f.repo / "runtime/repository_http/app_launcher.py"
        if member == "source"
        else f.repo / inputs.BASE_REFERENCE
        if member == "base"
        else next(f.wheelhouse.iterdir())
    )
    kept = tmp_path / "kept"
    target.rename(kept)
    if hard:
        os.link(kept, target)
    else:
        target.symlink_to(kept)
    with pytest.raises(inputs.ImageInputsError):
        inputs.verify_wheelhouse(f.repo, f.wheelhouse, "A", "linux/arm64")


def changed_wheel(change):
    original = wheel_bytes("uvicorn")
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(output, "w") as target:
        for member in source.infolist():
            raw = source.read(member)
            if change == "name" and member.filename.endswith("METADATA"):
                raw = raw.replace(b"Name: uvicorn", b"Name: impostor")
            elif change == "dependencies" and member.filename.endswith("METADATA"):
                raw = raw.replace(b"\n\n", b"\nRequires-Dist: unexpected>=1\n\n")
            elif change == "tag" and member.filename.endswith("WHEEL"):
                raw = raw.replace(b"py3-none-any", b"cp312-none-any")
            target.writestr(member, raw)
        if change == "unsafe-path":
            target.writestr("../unsafe", b"inert")
    return output.getvalue()


@pytest.mark.parametrize("change", ["name", "dependencies", "tag", "unsafe-path"])
def test_declared_zip_hash_cannot_hide_wrong_metadata_or_members(tmp_path, monkeypatch, change):
    f = make_http_fixture(tmp_path, monkeypatch, wheel_payloads={"uvicorn": changed_wheel(change)})
    with pytest.raises(inputs.ImageInputsError):
        inputs.verify_wheelhouse(f.repo, f.wheelhouse, "A", "linux/arm64")


def test_reformatted_manifest_during_wheel_observation_is_not_same_identity(tmp_path, monkeypatch):
    f = make_http_fixture(tmp_path, monkeypatch)
    original = shared._metadata

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        (f.repo / inputs.IMAGES / "manifest.json").write_text(json.dumps(f.data, indent=4))
        return result

    monkeypatch.setattr(shared, "_metadata", mutate)
    with pytest.raises(inputs.ImageInputsError, match="changed during wheel"):
        inputs.verify_wheelhouse(f.repo, f.wheelhouse, "A", "linux/arm64")


def test_cli_existing_wheels_and_invalid_options(tmp_path, monkeypatch, capsys):
    f = make_http_fixture(tmp_path, monkeypatch, "B")
    args = ["--root", str(f.repo), "--wheelhouse", str(f.wheelhouse), "--role", "B"]
    assert inputs.main(args) == 0
    assert json.loads(capsys.readouterr().out)["wheel_count"] == 0
    for extra in (["--role", "A"], ["--wheelhouse", str(f.wheelhouse)], ["--role", "T"]):
        with pytest.raises(SystemExit) as raised:
            inputs.main(["--root", str(f.repo), *extra])
        assert raised.value.code == 2
