"""HTTP-only supplied rootfs comparisons use inert TAR/ZIP bytes, never guests."""

from __future__ import annotations

import builtins
import copy
import io
import socket
import stat
import subprocess
import tarfile
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from scripts import generated_image_contents as common
from scripts import repository_http_image_contents as contents
from scripts import repository_http_image_inputs as inputs
from tests.helpers.repository_http_image_data import make_http_fixture

from test_generated_image_contents import write_archive
from test_generated_image_inputs import manifest_data, wheel_bytes

GUEST = "opt/authzest-repository-http-guest"
PLATFORM = "linux/arm64"


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("HTTP contents checks only observe inert archive/ZIP bytes")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "fastapi", "httpx", "uvicorn", "docker", "openai"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extract", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extractall", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extract", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbidden)


def comparison_case(tmp_path, monkeypatch, role="A"):
    base_data, wheel_payloads = manifest_data(), {}
    for name, package in base_data["packages"].items():
        declaration = package["wheels"][PLATFORM]
        raw = wheel_bytes(name, package["version"], tuple(declaration["requires_dist"]))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = {item.filename: archive.read(item) for item in archive.infolist()}
        prefix = name.replace("-", "_") + "-1.0.dist-info/"
        members[prefix + "RECORD"] = b"inert-original-record\n"
        members[name.replace("-", "_") + ".py"] = b"raise AssertionError('never import')\n"
        if name == "uvicorn":
            members[prefix + "entry_points.txt"] = b"[console_scripts]\nuvicorn = uvicorn:main\n"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for path, payload in members.items():
                item = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                item.create_system = 3
                item.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(item, payload)
        wheel_payloads[name] = output.getvalue()
    fixture = make_http_fixture(
        tmp_path, monkeypatch, role=role, base_data=base_data, wheel_payloads=wheel_payloads
    )
    baseline = {
        "usr/lib/base.txt": ("file", 0o644, b"baseline\n"),
        "etc/hostname": ("file", 0o755, b""),
        "etc/hosts": ("file", 0o755, b""),
        "etc/resolv.conf": ("file", 0o755, b""),
        "opt": ("directory", 0o755, b""),
        contents.SITE.rstrip("/"): ("directory", 0o755, b""),
    }
    observed = copy.deepcopy(baseline)
    observed[GUEST] = ("directory", 0o555, b"")
    observed["input"] = ("directory", 0o555, b"")
    if role == "A":
        observed["input/project"] = ("directory", 0o555, b"")
    role_data = fixture.data["roles"][role]
    for name, relative in role_data["asset_sources"].items():
        observed[GUEST + "/" + name] = ("file", 0o444, (fixture.repo / relative).read_bytes())
    for name in fixture.base["roles"][role]["platforms"][PLATFORM]["packages"]:
        raw = wheel_payloads[name]
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for member in archive.infolist():
                observed[contents.SITE + member.filename] = ("file", 0o644, archive.read(member))
        prefix = contents.SITE + name.replace("-", "_") + "-1.0.dist-info/"
        observed[prefix + "RECORD"] = ("file", 0o644, b"inert-installed-record\n")
        observed[prefix + "INSTALLER"] = ("file", 0o644, b"pip\n")
        observed[prefix + "REQUESTED"] = ("file", 0o644, b"")
        if name == "uvicorn":
            observed[contents.SITE + "bin/uvicorn"] = (
                "file",
                0o755,
                b"# observed generated entrypoint\n",
            )
    return fixture, baseline, observed


def compare(tmp_path, fixture, baseline, observed, role="A"):
    return contents.compare_image_contents(
        fixture.repo,
        write_archive(tmp_path / "base.tar", baseline),
        write_archive(tmp_path / "role.tar", observed),
        fixture.wheelhouse,
        role,
        PLATFORM,
    )


@pytest.mark.parametrize("role", ["A", "B"])
def test_http_layout_and_exact_selected_payloads_remain_supplied_unverified(
    tmp_path, monkeypatch, role
):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, role)
    result = compare(tmp_path, fixture, baseline, observed, role)
    assert result["schema_version"] == "2.0"
    assert result["kind"] == "repository-http-image-content-comparison"
    assert result["provenance"] == "caller-supplied-unverified"
    assert result["authorization"] == "unknown"
    assert result["role"] == role and result["platform"] == PLATFORM
    entry = fixture.data["roles"][role]["platforms"][PLATFORM]
    assert result["recipe_sha256"] == entry["recipe_sha256"]
    assert result["dependency_lock_sha256"] == entry["dependency_lock_sha256"]
    assert result["base_reference_sha256"] == fixture.data["base_reference_sha256"]
    assert result["baseline_unchanged"] is True
    assert result["maintained_assets_verified"] is True
    assert result["wheel_payloads_verified"] is True
    assert result["installed_package_metadata_verified"] is True
    for field in (
        "image_identity_verified",
        "image_built",
        "build_invoked",
        "contents_verified",
        "image_configuration_verified",
        "runtime_ready",
        "ready",
        "runtime_invoked",
        "execution_authorized",
        "verified_fix",
    ):
        assert result[field] is False
    assert result["docker_managed_exclusions"] == []
    assert result["docker_managed_files_compared"] == [
        "etc/hostname",
        "etc/hosts",
        "etc/resolv.conf",
    ]
    assert bool(result["unverified_generated_files"]) is (role == "A")
    assert not (tmp_path / "usr").exists()


@pytest.mark.parametrize(
    "role,platform", [("T", PLATFORM), ("A", "linux/amd64"), (True, PLATFORM), ("B", None)]
)
def test_non_http_selections_fail_before_input_or_archive_access(monkeypatch, role, platform):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported selection must fail before reading files")

    monkeypatch.setattr(inputs, "verify_wheelhouse", forbidden)
    with pytest.raises(contents.ImageContentsError, match="HTTP A/B"):
        contents.compare_image_contents(
            Path("missing"), None, None, Path("missing"), role, platform
        )


@pytest.mark.parametrize("role", ["A", "B"])
@pytest.mark.parametrize(
    "path",
    [
        "input/app.py",
        "input/tests/test_generated_ownership.py",
        "opt/authzest-guest/app_launcher.py",
        "input/policy.md",
        "input/cases.json",
        "root/.codex/auth.json",
    ],
)
def test_old_placeholders_and_unselected_inputs_are_refused(tmp_path, monkeypatch, role, path):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, role)
    observed[path] = ("file", 0o444, b"inert extra\n")
    with pytest.raises(contents.ImageContentsError, match="Unexpected rootfs addition"):
        compare(tmp_path, fixture, baseline, observed, role)


@pytest.mark.parametrize("role", ["A", "B"])
def test_only_application_has_an_empty_project_mount_directory(tmp_path, monkeypatch, role):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, role)
    if role == "A":
        del observed["input/project"]
    else:
        observed["input/project"] = ("directory", 0o555, b"")
    with pytest.raises(contents.ImageContentsError, match="Missing|Unexpected"):
        compare(tmp_path, fixture, baseline, observed, role)


@pytest.mark.parametrize("change", ["bytes", "mode", "uid", "gid", "missing", "added"])
def test_docker_managed_paths_are_not_exempt_from_baseline_comparison(
    tmp_path, monkeypatch, change
):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, "B")
    target = "etc/hostname"
    if change == "bytes":
        observed[target] = ("file", 0o755, b"changed")
    elif change == "mode":
        observed[target] = ("file", 0o644, b"")
    elif change == "missing":
        del observed[target]
    elif change == "added":
        del baseline[target]
    before = write_archive(tmp_path / "base.tar", baseline)
    after = write_archive(tmp_path / "role.tar", observed)
    if change in {"uid", "gid"}:
        after = replace(
            after,
            entries=tuple(
                replace(e, **{change: 1}) if e.path == target else e for e in after.entries
            ),
        )
    with pytest.raises(contents.ImageContentsError, match="Baseline|Unexpected rootfs"):
        contents.compare_image_contents(
            fixture.repo, before, after, fixture.wheelhouse, "B", PLATFORM
        )


@pytest.mark.parametrize(
    "change", ["bytes", "mode", "missing", "symlink", "hardlink", "uid", "gid", "size"]
)
def test_maintained_asset_identity_and_metadata_are_exact(tmp_path, monkeypatch, change):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, "B")
    target = GUEST + "/relay_launcher.py"
    if change == "bytes":
        observed[target] = ("file", 0o444, b"changed")
    elif change == "mode":
        observed[target] = ("file", 0o644, observed[target][2])
    elif change == "missing":
        del observed[target]
    elif change in {"symlink", "hardlink"}:
        observed[target] = (change, 0o444, "usr/lib/base.txt")
    before = write_archive(tmp_path / "base.tar", baseline)
    after = write_archive(tmp_path / "role.tar", observed)
    if change in {"uid", "gid", "size"}:
        after = replace(
            after,
            entries=tuple(
                replace(e, **{change: e.size + 1 if change == "size" else 1})
                if e.path == target
                else e
                for e in after.entries
            ),
        )
    with pytest.raises(contents.ImageContentsError, match="payload|Missing"):
        contents.compare_image_contents(
            fixture.repo, before, after, fixture.wheelhouse, "B", PLATFORM
        )


@pytest.mark.parametrize(
    "change", ["bytes", "mode", "missing", "installer", "requested", "metadata", "extra-package"]
)
def test_locked_dependency_payloads_and_installed_metadata_are_exact(tmp_path, monkeypatch, change):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch)
    target = contents.SITE + "fastapi.py"
    if change == "bytes":
        observed[target] = ("file", 0o644, b"changed")
    elif change == "mode":
        observed[target] = ("file", 0o777, observed[target][2])
    elif change == "missing":
        del observed[target]
    elif change == "extra-package":
        observed[contents.SITE + "foreign-1.0.dist-info/METADATA"] = (
            "file",
            0o644,
            b"Name: foreign\nVersion: 1.0\n",
        )
    else:
        leaf = {"installer": "INSTALLER", "requested": "REQUESTED", "metadata": "METADATA"}[change]
        observed[contents.SITE + "fastapi-1.0.dist-info/" + leaf] = ("file", 0o644, b"changed")
    with pytest.raises(contents.ImageContentsError):
        compare(tmp_path, fixture, baseline, observed)


@pytest.mark.parametrize(
    "leaf,change",
    [
        ("RECORD", "bytes"),
        ("RECORD", "mode"),
        ("RECORD", "oversized"),
        ("bin/uvicorn", "bytes"),
        ("bin/uvicorn", "mode"),
        ("bin/uvicorn", "oversized"),
    ],
)
def test_pip_generated_files_remain_observed_not_attested(tmp_path, monkeypatch, leaf, change):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch)
    target = contents.SITE + ("uvicorn-1.0.dist-info/RECORD" if leaf == "RECORD" else leaf)
    kind, mode, raw = observed[target]
    if change == "bytes":
        observed[target] = (kind, mode, b"other bounded generated template\n")
        result = compare(tmp_path, fixture, baseline, observed)
        assert target in {e["path"] for e in result["unverified_generated_files"]}
        assert result["contents_verified"] is result["image_identity_verified"] is False
    else:
        observed[target] = (
            kind,
            0o777 if change == "mode" else mode,
            b"x" * (1_048_577 if change == "oversized" else len(raw)),
        )
        with pytest.raises(contents.ImageContentsError, match="generated file metadata"):
            compare(tmp_path, fixture, baseline, observed)


def test_baseline_links_are_kept_inert_and_unchanged(tmp_path, monkeypatch):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, "B")
    additions = {
        "usr/lib/base-link": ("symlink", 0o777, "base.txt"),
        "usr/lib/base-hard": ("hardlink", 0o644, "usr/lib/base.txt"),
    }
    baseline.update(additions)
    observed.update(additions)
    assert compare(tmp_path, fixture, baseline, observed, "B")["baseline_unchanged"] is True
    observed["usr/lib/base-link"] = ("symlink", 0o777, "base-hard")
    with pytest.raises(contents.ImageContentsError, match="Baseline"):
        compare(tmp_path, fixture, baseline, observed, "B")


def test_selected_additions_cannot_replace_baseline_paths(tmp_path, monkeypatch):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, "B")
    baseline[GUEST] = observed[GUEST]
    with pytest.raises(contents.ImageContentsError, match="collide"):
        compare(tmp_path, fixture, baseline, observed, "B")


@pytest.mark.parametrize("change", ["http", "base", "asset", "wheel", "wheel-extra"])
def test_current_inputs_and_wheelhouse_are_rechecked_after_comparison(
    tmp_path, monkeypatch, change
):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch)
    original = common._wheel_files

    def changed(*args):
        result = original(*args)
        if change in {"http", "base"}:
            relative = (
                inputs.IMAGES + "/manifest.json"
                if change == "http"
                else fixture.data["base_reference"]
            )
            path = fixture.repo / relative
            path.write_bytes(path.read_bytes() + b"\n")
        elif change == "asset":
            path = fixture.repo / fixture.data["roles"]["A"]["asset_sources"]["app_launcher.py"]
            path.write_bytes(path.read_bytes() + b"# changed\n")
        elif change == "wheel":
            path = next(fixture.wheelhouse.iterdir())
            path.write_bytes(path.read_bytes() + b"changed")
        else:
            (fixture.wheelhouse / "extra.whl").write_bytes(b"inert")
        return result

    monkeypatch.setattr(common, "_wheel_files", changed)
    with pytest.raises((contents.ImageContentsError, inputs.ImageInputsError)):
        compare(tmp_path, fixture, baseline, observed)


def test_supplied_catalog_and_old_result_dict_cannot_be_used_as_archive_facts(
    tmp_path, monkeypatch
):
    fixture, baseline, observed = comparison_case(tmp_path, monkeypatch, "B")
    before = write_archive(tmp_path / "base.tar", baseline)
    after = write_archive(tmp_path / "role.tar", observed)
    result = contents.compare_image_contents(
        fixture.repo, before, after, fixture.wheelhouse, "B", PLATFORM
    )
    with pytest.raises(contents.ImageContentsError, match="caller-supplied archive catalog"):
        contents.compare_image_contents(
            fixture.repo, before, result, fixture.wheelhouse, "B", PLATFORM
        )
    with pytest.raises(contents.ImageContentsError, match="caller-supplied archive catalog"):
        contents.compare_image_contents(
            fixture.repo, result, after, fixture.wheelhouse, "B", PLATFORM
        )
    malformed = replace(after, entries=after.entries + (after.entries[0],))
    with pytest.raises(contents.ImageContentsError, match="duplicate"):
        contents.compare_image_contents(
            fixture.repo, before, malformed, fixture.wheelhouse, "B", PLATFORM
        )
