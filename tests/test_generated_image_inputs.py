"""Synthetic pinned input recipes; no wheels imported, installed or executed."""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest
from scripts import generated_image_inputs as inputs

from authzest.runner._generated_repair_runtime_profile import expected_assets

REPOSITORY = Path(__file__).resolve().parents[1]


def base_snapshot_data(
    python_version: str = "3.12.10", *, environment: list[str] | None = None
) -> tuple[dict, dict[str, bytes]]:
    """Synthetic registry-shaped metadata, containing no layers or executables."""
    documents = {}
    platforms = {}
    descriptors = []
    for platform in inputs.PLATFORMS:
        architecture = platform.split("/")[1]
        stem = platform.replace("/", "-")
        config = {
            "os": "linux",
            "architecture": architecture,
            "config": {
                "Env": environment
                if environment is not None
                else [
                    "PATH=/usr/local/bin:/usr/bin",
                    "PYTHON_VERSION=" + python_version,
                ]
            },
        }
        raw_config = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        child = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": "sha256:" + sha256(raw_config).hexdigest(),
                "size": len(raw_config),
            },
            "layers": [],
        }
        raw_child = json.dumps(child, sort_keys=True, separators=(",", ":")).encode()
        documents[stem + ".config.json"] = raw_config
        documents[stem + ".manifest.json"] = raw_child
        platforms[platform] = {
            "manifest_sha256": sha256(raw_child).hexdigest(),
            "config_sha256": sha256(raw_config).hexdigest(),
            "os": "linux",
            "architecture": architecture,
            "variant": "",
        }
        descriptors.append(
            {
                "mediaType": child["mediaType"],
                "digest": "sha256:" + sha256(raw_child).hexdigest(),
                "size": len(raw_child),
                "platform": {"os": "linux", "architecture": architecture},
            }
        )
    index = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": descriptors,
    }
    documents["index.json"] = json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    return {
        "repository": "docker.io/library/python",
        "source_tag": python_version + "-slim-bookworm",
        "index_sha256": sha256(documents["index.json"]).hexdigest(),
        "platforms": platforms,
    }, documents


def wheel_bytes(name: str, version: str = "1.0", requires_dist: tuple[str, ...] = ()) -> bytes:
    """Create metadata-only synthetic ZIP bytes, with no Python source."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        prefix = name.replace("-", "_") + "-" + version + ".dist-info/"
        metadata = (
            "Metadata-Version: 2.3\nName: "
            + name
            + "\nVersion: "
            + version
            + "\nRequires-Python: >=3.12\n"
            + "".join("Requires-Dist: " + item + "\n" for item in requires_dist)
            + "\n"
        )
        for name, content in (
            (prefix + "METADATA", metadata),
            (prefix + "WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n"),
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content)
    return output.getvalue()


def test_synthetic_wheel_bytes_are_independent_of_current_zip_clock(monkeypatch) -> None:
    monkeypatch.setattr(zipfile.time, "localtime", lambda *_: (2026, 11, 15, 0, 0, 0, 0, 319, 0))
    first = wheel_bytes("httpx")
    monkeypatch.setattr(zipfile.time, "localtime", lambda *_: (2026, 11, 15, 0, 0, 2, 0, 319, 0))
    assert wheel_bytes("httpx") == first


def manifest_data() -> dict:
    """Fully synthetic digests/versions, never claimed to identify real images."""
    data = {
        "schema_version": "1.0",
        "kind": "generated-repair-image-inputs",
        "status": "candidate-not-built",
        "python_version": "3.12.10",
        "base": base_snapshot_data()[0],
        "packages": {},
        "roles": {},
        "image_ids": None,
        "contents_verified": False,
        "runtime_ready": False,
    }
    dependencies = {
        "fastapi": ("starlette>=1.0", "ignored-extra; extra == 'all'"),
        "httpx": (),
        "pytest": (),
        "uvicorn": (),
        "starlette": (),
    }
    for name, requirements in dependencies.items():
        raw = wheel_bytes(name, requires_dist=requirements)
        filename = name + "-1.0-py3-none-any.whl"
        wheel = {
            "filename": filename,
            "url": "https://files.pythonhosted.org/packages/synthetic/" + filename,
            "sha256": sha256(raw).hexdigest(),
            "size": len(raw),
            "requires_python": ">=3.12",
            "requires_dist": list(requirements),
        }
        data["packages"][name] = {
            "version": "1.0",
            "wheels": {platform: copy.deepcopy(wheel) for platform in inputs.PLATFORMS},
        }
    direct = {"T": ["fastapi", "httpx", "pytest"], "A": ["fastapi", "uvicorn"], "B": []}
    for role in inputs.ROLES:
        packages = sorted(direct[role] + (["starlette"] if role != "B" else []))
        data["roles"][role] = {
            "direct_requirements": direct[role],
            "assets": expected_assets(role),
            "platforms": {},
        }
        for platform in inputs.PLATFORMS:
            stem = platform.replace("/", "-") + "-" + role
            data["roles"][role]["platforms"][platform] = {
                "packages": packages[:],
                "requirements_file": "locks/" + stem + ".txt",
                "requirements_sha256": "0" * 64,
                "dockerfile": "dockerfiles/" + stem + ".Dockerfile",
                "dockerfile_sha256": "0" * 64,
                "recipe_sha256": "0" * 64,
            }
    return data


def write_inputs(root: Path, manifest: dict) -> dict:
    """Write inert test inputs, deriving expected hashes through public renderers."""
    data = copy.deepcopy(manifest)
    _, documents = base_snapshot_data(data["python_version"])
    for filename, raw in documents.items():
        target = root / inputs.IMAGES / "base" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for relative in inputs._ASSET_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, target)
    for role in inputs.ROLES:
        for platform in inputs.PLATFORMS:
            entry = data["roles"][role]["platforms"][platform]
            lock = inputs.render_lock(data, role, platform).encode()
            dockerfile = inputs.render_dockerfile(data, role, platform).encode()
            for field, raw in (("requirements_file", lock), ("dockerfile", dockerfile)):
                target = root / inputs.IMAGES / entry[field]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            entry["requirements_sha256"] = sha256(lock).hexdigest()
            entry["dockerfile_sha256"] = sha256(dockerfile).hexdigest()
            entry["recipe_sha256"] = inputs.recipe_sha256(data, role, platform)
    (root / inputs.IMAGES / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.fixture(autouse=True)
def no_execution_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Image input tests must not execute or contact anything")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(os, "system", blocked)
    monkeypatch.setattr(os, "execve", blocked)


def test_rendered_roles_and_platforms_are_closed() -> None:
    data = manifest_data()
    for role in inputs.ROLES:
        for platform in inputs.PLATFORMS:
            lock = inputs.render_lock(data, role, platform)
            recipe = inputs.render_dockerfile(data, role, platform)
            assert lock.endswith("\n") and "\r" not in lock
            assert recipe.endswith("\n") and "\r" not in recipe
            assert "USER 65532:65532\nWORKDIR /tmp\n" in recipe
            assert "@sha256:" + data["base"]["platforms"][platform]["manifest_sha256"] in recipe
            assert '"-I","-B"' in recipe
            assert all(
                item not in recipe
                for item in ("EXPOSE", "VOLUME", "ONBUILD", "HEALTHCHECK", "apt", "curl")
            )
            if role == "B":
                assert "pip install" not in recipe and "/input" not in recipe
                assert lock.startswith("# No additional")
            else:
                assert recipe.count("FROM ") == 2 and "--no-deps --require-hashes" in recipe
                assert "COPY --from=dependencies /build/site-packages/" in recipe
                assert "COPY --from=dependencies /build/wheels" not in recipe
            assert ("/input/tests" in recipe) is (role == "T")


def test_check_observes_sources_but_never_claims_images(tmp_path: Path) -> None:
    write_inputs(tmp_path, manifest_data())
    result = inputs.check_image_inputs(tmp_path)
    assert len(result["recipes"]) == 6
    assert result["source_bytes_verified"] is True
    assert result["base_metadata_bytes_verified"] is True
    for field in (
        "wheel_bytes_verified",
        "contents_verified",
        "runtime_ready",
        "runtime_invoked",
        "execution_authorized",
    ):
        assert result[field] is False
    assert result["image_ids"] is None


@pytest.mark.parametrize(
    "change",
    ["missing", "raw", "python", "duplicate-python", "descriptor-count", "descriptor-size"],
)
def test_base_snapshot_chain_and_python_patch_are_checked(tmp_path: Path, change: str) -> None:
    data = manifest_data()
    base, documents = base_snapshot_data()
    if change == "python":
        base, documents = base_snapshot_data("3.12.11")
    elif change == "duplicate-python":
        base, documents = base_snapshot_data(environment=["PYTHON_VERSION=3.12.10"] * 2)
    elif change in {"descriptor-count", "descriptor-size"}:
        index = json.loads(documents["index.json"])
        if change == "descriptor-count":
            index["manifests"].append(copy.deepcopy(index["manifests"][0]))
        else:
            index["manifests"][0]["size"] += 1
        documents["index.json"] = json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
        base["index_sha256"] = sha256(documents["index.json"]).hexdigest()
    data["base"] = base
    write_inputs(tmp_path, data)
    for filename, raw in documents.items():
        (tmp_path / inputs.IMAGES / "base" / filename).write_bytes(raw)
    target = tmp_path / inputs.IMAGES / "base/linux-amd64.config.json"
    if change == "missing":
        target.unlink()
    elif change == "raw":
        target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises((inputs.ImageInputsError, FileNotFoundError)):
        inputs.check_image_inputs(tmp_path)


def test_recipe_recomputes_derived_hashes_and_binds_platform() -> None:
    data = manifest_data()
    before = inputs.recipe_sha256(data, "T", "linux/amd64")
    data["roles"]["T"]["platforms"]["linux/amd64"]["recipe_sha256"] = "f" * 64
    assert inputs.recipe_sha256(data, "T", "linux/amd64") == before
    assert inputs.recipe_sha256(data, "T", "linux/arm64") != before
    data["packages"]["httpx"]["wheels"]["linux/amd64"]["sha256"] = "f" * 64
    assert inputs.recipe_sha256(data, "T", "linux/amd64") != before


@pytest.mark.parametrize("interpreter", ["cp40", "cp99", "cp100", "cp313"])
def test_abi3_tags_do_not_infer_python_compatibility_from_integer_order(interpreter: str) -> None:
    data = manifest_data()
    wheel = data["packages"]["httpx"]["wheels"]["linux/amd64"]
    filename = "httpx-1.0-" + interpreter + "-abi3-manylinux_2_17_x86_64.whl"
    wheel.update(
        filename=filename, url="https://files.pythonhosted.org/packages/synthetic/" + filename
    )
    with pytest.raises(inputs.ImageInputsError, match="target tags"):
        inputs.render_lock(data, "T", "linux/amd64")


@pytest.mark.parametrize("interpreter", ["cp32", "cp39", "cp310", "cp311", "cp312"])
def test_explicit_supported_abi3_interpreters(interpreter: str) -> None:
    data = manifest_data()
    wheel = data["packages"]["httpx"]["wheels"]["linux/amd64"]
    filename = "httpx-1.0-" + interpreter + "-abi3-manylinux_2_17_x86_64.whl"
    wheel.update(
        filename=filename, url="https://files.pythonhosted.org/packages/synthetic/" + filename
    )
    assert "httpx==1.0" in inputs.render_lock(data, "T", "linux/amd64")


def test_wheel_file_and_aggregate_byte_bounds_are_small() -> None:
    data = manifest_data()
    data["packages"]["httpx"]["wheels"]["linux/amd64"]["size"] = 16_777_217
    with pytest.raises(inputs.ImageInputsError, match="byte size"):
        inputs.render_lock(data, "T", "linux/amd64")
    data = manifest_data()
    for package in data["packages"].values():
        for wheel in package["wheels"].values():
            wheel["size"] = 16_777_216
    with pytest.raises(inputs.ImageInputsError, match="inventory exceeds"):
        inputs.render_lock(data, "T", "linux/amd64")


@pytest.mark.parametrize(
    "change", ["closure", "constraint", "extras", "tag", "asset", "path", "boolean"]
)
def test_invalid_declarations_refused(change: str) -> None:
    data = manifest_data()
    if change == "closure":
        data["roles"]["T"]["platforms"]["linux/amd64"]["packages"].remove("starlette")
    elif change in {"constraint", "extras"}:
        requirement = "starlette>=2" if change == "constraint" else "starlette[extra]>=1"
        data["packages"]["fastapi"]["wheels"]["linux/amd64"]["requires_dist"] = [requirement]
    elif change == "tag":
        data["packages"]["httpx"]["wheels"]["linux/amd64"]["filename"] = (
            "httpx-1.0-cp312-cp312-linux_x86_64.whl"
        )
    elif change == "asset":
        data["roles"]["B"]["assets"]["_guest_common.py"] = "e" * 64
    elif change == "path":
        data["roles"]["T"]["platforms"]["linux/amd64"]["requirements_file"] = "../outside"
    else:
        data["runtime_ready"] = 0
    with pytest.raises(inputs.ImageInputsError):
        inputs.render_dockerfile(data, "T", "linux/amd64")


@pytest.mark.parametrize("change", ["lock", "asset", "symlink", "hardlink", "duplicate-json"])
def test_observed_drift_and_aliases_refused(tmp_path: Path, change: str) -> None:
    data = write_inputs(tmp_path, manifest_data())
    path = tmp_path / inputs.IMAGES / "locks/linux-amd64-T.txt"
    if change == "lock":
        path.write_bytes(path.read_bytes() + b"\n")
    elif change == "asset":
        (tmp_path / inputs._ASSET_PATHS["app_launcher.py"]).write_bytes(b"# drift\n")
    elif change in {"symlink", "hardlink"}:
        original = tmp_path / "original"
        path.rename(original)
        if change == "symlink":
            try:
                path.symlink_to(original)
            except (NotImplementedError, OSError) as error:
                if os.name != "nt":
                    raise
                pytest.skip(f"Symlinks unavailable: {error}")
        else:
            path.hardlink_to(original)
    else:
        path = tmp_path / inputs.IMAGES / "manifest.json"
        path.write_text('{"schema_version":"other",' + json.dumps(data)[1:])
    with pytest.raises(inputs.ImageInputsError):
        inputs.check_image_inputs(tmp_path)


def test_optional_wheelhouse_verifies_inert_metadata(tmp_path: Path) -> None:
    data = write_inputs(tmp_path / "repo", manifest_data())
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    for name in data["roles"]["T"]["platforms"]["linux/amd64"]["packages"]:
        wheel = data["packages"][name]["wheels"]["linux/amd64"]
        (wheelhouse / wheel["filename"]).write_bytes(
            wheel_bytes(name, requires_dist=tuple(wheel["requires_dist"]))
        )
    result = inputs.verify_wheelhouse(tmp_path / "repo", wheelhouse, "T", "linux/amd64")
    assert result["wheel_bytes_verified"] is True and result["wheel_count"] == 4
    assert result["contents_verified"] is result["runtime_ready"] is False
    (wheelhouse / "unexpected.whl").write_bytes(b"not a wheel")
    with pytest.raises(inputs.ImageInputsError, match="Unexpected wheelhouse"):
        inputs.verify_wheelhouse(tmp_path / "repo", wheelhouse, "T", "linux/amd64")


def test_wheel_zip_metadata_must_match_even_if_declared_hash_matches(tmp_path: Path) -> None:
    data = manifest_data()
    raw = wheel_bytes("wrong-name")
    wheel = data["packages"]["uvicorn"]["wheels"]["linux/amd64"]
    wheel.update(sha256=sha256(raw).hexdigest(), size=len(raw))
    data = write_inputs(tmp_path / "repo", data)
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    for name in data["roles"]["A"]["platforms"]["linux/amd64"]["packages"]:
        item = data["packages"][name]["wheels"]["linux/amd64"]
        (wheelhouse / item["filename"]).write_bytes(
            raw
            if name == "uvicorn"
            else wheel_bytes(name, requires_dist=tuple(item["requires_dist"]))
        )
    with pytest.raises(inputs.ImageInputsError, match="metadata differs"):
        inputs.verify_wheelhouse(tmp_path / "repo", wheelhouse, "A", "linux/amd64")


def test_cli_default_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_inputs(tmp_path, manifest_data())
    assert inputs.main(["--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["runtime_ready"] is False
