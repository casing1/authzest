"""Inert rootfs/wheel archives only; no engine, extraction or generated imports."""

from __future__ import annotations

import copy
import io
import socket
import stat
import subprocess
import tarfile
import zipfile
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
from scripts import generated_image_contents as contents
from scripts import generated_image_inputs as inputs

from test_generated_image_inputs import manifest_data, wheel_bytes, write_inputs


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Contents tests must not extract, execute or contact anything")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extract", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extractall", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extract", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbidden)


def archive_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, (kind, mode, payload) in entries.items():
            item = tarfile.TarInfo(name)
            item.mode, item.uid, item.gid, item.mtime = mode, 0, 0, 0
            item.type = {
                "file": tarfile.REGTYPE,
                "directory": tarfile.DIRTYPE,
                "symlink": tarfile.SYMTYPE,
                "hardlink": tarfile.LNKTYPE,
            }[kind]
            item.size = len(payload) if kind == "file" else 0
            if kind in {"symlink", "hardlink"}:
                item.linkname = payload
            archive.addfile(item, io.BytesIO(payload) if kind == "file" else None)
    return output.getvalue()


def write_archive(path, entries):
    full = dict(entries)
    for name in entries:
        parent = Path(name).parent.as_posix()
        while parent != ".":
            full.setdefault(parent, ("directory", 0o755, b""))
            parent = Path(parent).parent.as_posix()
    path.write_bytes(archive_bytes(dict(sorted(full.items()))))
    return contents.inventory_archive(path)


def comparison_case(tmp_path, role="T"):
    data, wheel_payloads = manifest_data(), {}
    for name, package in data["packages"].items():
        declaration = package["wheels"]["linux/arm64"]
        original = wheel_bytes(name, requires_dist=tuple(declaration["requires_dist"]))
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            members = {item.filename: archive.read(item) for item in archive.infolist()}
        prefix = name.replace("-", "_") + "-1.0.dist-info/"
        members[prefix + "RECORD"] = b"synthetic-original-record\n"
        members[name.replace("-", "_") + ".py"] = b"raise AssertionError('never execute')\n"
        if name == "pytest":
            members[prefix + "entry_points.txt"] = b"[console_scripts]\npytest = pytest:main\n"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for path, raw in members.items():
                item = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                item.create_system, item.external_attr = 3, (stat.S_IFREG | 0o644) << 16
                archive.writestr(item, raw)
        raw = output.getvalue()
        wheel_payloads[name] = raw
        for wheel in package["wheels"].values():
            wheel.update(size=len(raw), sha256=sha256(raw).hexdigest())
    repo = tmp_path / "repo"
    data = write_inputs(repo, data)
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    base = {
        "usr/lib/base.txt": ("file", 0o644, b"baseline\n"),
        "etc/hostname": ("file", 0o644, b"base-host\n"),
        "opt": ("directory", 0o755, b""),
        contents.SITE.rstrip("/"): ("directory", 0o755, b""),
    }
    observed = copy.deepcopy(base)
    observed["etc/hostname"] = ("file", 0o644, b"role-host\n")
    observed["opt/authzest-guest"] = ("directory", 0o555, b"")
    for name in data["roles"][role]["assets"]:
        observed["opt/authzest-guest/" + name] = (
            "file",
            0o444,
            (repo / inputs._ASSET_PATHS[name]).read_bytes(),
        )
    if role in {"T", "A"}:
        observed.update({"input": ("directory", 0o555, b""), "input/app.py": ("file", 0o444, b"")})
    if role == "T":
        observed.update(
            {
                "input/tests": ("directory", 0o555, b""),
                "input/tests/test_generated_ownership.py": ("file", 0o444, b""),
            }
        )
    for name in data["roles"][role]["platforms"]["linux/arm64"]["packages"]:
        wheel = data["packages"][name]["wheels"]["linux/arm64"]
        (wheelhouse / wheel["filename"]).write_bytes(wheel_payloads[name])
        with zipfile.ZipFile(io.BytesIO(wheel_payloads[name])) as archive:
            for member in archive.infolist():
                observed[contents.SITE + member.filename] = ("file", 0o644, archive.read(member))
        prefix = contents.SITE + name.replace("-", "_") + "-1.0.dist-info/"
        observed[prefix + "RECORD"] = ("file", 0o644, b"synthetic-installed-record\n")
        observed[prefix + "INSTALLER"] = ("file", 0o644, b"pip\n")
        observed[prefix + "REQUESTED"] = ("file", 0o644, b"")
        if name == "pytest":
            observed[contents.SITE + "bin/pytest"] = (
                "file",
                0o755,
                b"# generated template not attested\n",
            )
    return repo, wheelhouse, base, observed


def test_catalog_hashes_regular_files_and_keeps_links_inert(tmp_path):
    entries = {
        "usr/lib/base": ("file", 0o644, b"baseline"),
        "usr/lib/hard": ("hardlink", 0o644, "usr/lib/base"),
        "usr/bin/link": ("symlink", 0o777, "../lib/base"),
    }
    path = tmp_path / "rootfs.tar"
    catalog = write_archive(path, entries)
    mapping = {entry.path: entry for entry in catalog.entries}
    assert mapping["usr/lib/base"].sha256 == sha256(b"baseline").hexdigest()
    assert mapping["usr/lib/hard"].link_target == "usr/lib/base"
    assert mapping["usr/bin/link"].link_target == "../lib/base"
    assert catalog.archive_sha256 == sha256(path.read_bytes()).hexdigest()
    assert not (tmp_path / "usr").exists()
    with pytest.raises(FrozenInstanceError):
        catalog.byte_count = 0


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_comparison_verifies_selected_parts_without_promoting_full_contents(tmp_path, role):
    repo, wheelhouse, base, observed = comparison_case(tmp_path, role)
    before = write_archive(tmp_path / "base.tar", base)
    after = write_archive(tmp_path / "role.tar", observed)
    result = contents.compare_image_contents(repo, before, after, wheelhouse, role, "linux/arm64")
    assert result["baseline_unchanged"] is True
    assert result["wheel_payloads_verified"] is result["maintained_assets_verified"] is True
    assert result["installed_package_metadata_verified"] is True
    assert result["contents_verified"] is result["runtime_ready"] is False
    assert result["runtime_invoked"] is result["execution_authorized"] is False
    assert result["docker_managed_exclusions"] == ["etc/hostname"]
    assert bool(result["unverified_generated_files"]) is (role != "B")


@pytest.mark.parametrize(
    "change", ["baseline", "payload", "extra", "missing", "permissions", "installer"]
)
def test_comparison_refuses_changed_or_unexpected_bytes(tmp_path, change):
    repo, wheelhouse, base, observed = comparison_case(tmp_path)
    target = contents.SITE + "httpx.py"
    if change == "baseline":
        observed["usr/lib/base.txt"] = ("file", 0o644, b"different")
    elif change == "payload":
        observed[target] = ("file", 0o644, b"different")
    elif change == "extra":
        observed["usr/local/bin/foreign"] = ("file", 0o755, b"unapproved")
    elif change == "missing":
        del observed[target]
    elif change == "permissions":
        observed[target] = ("file", 0o777, observed[target][2])
    else:
        observed[contents.SITE + "httpx-1.0.dist-info/INSTALLER"] = ("file", 0o644, b"evil")
    with pytest.raises(contents.ImageContentsError):
        contents.compare_image_contents(
            repo,
            write_archive(tmp_path / "base.tar", base),
            write_archive(tmp_path / "role.tar", observed),
            wheelhouse,
            "T",
            "linux/arm64",
        )


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a/../outside", "a\\outside", "a//b"])
def test_unsafe_tar_paths_are_refused_without_extraction(tmp_path, name):
    path = tmp_path / "unsafe.tar"
    path.write_bytes(archive_bytes({name: ("file", 0o644, b"inert")}))
    with pytest.raises(contents.ImageContentsError):
        contents.inventory_archive(path)


def test_duplicate_and_device_members_are_refused(tmp_path):
    raw = archive_bytes({"entry": ("file", 0o644, b"inert")})
    path = tmp_path / "duplicate.tar"
    path.write_bytes(raw[:1024] + raw)
    with pytest.raises(contents.ImageContentsError, match="duplicate"):
        contents.inventory_archive(path)
    item = tarfile.TarInfo("device")
    item.type = tarfile.CHRTYPE
    path.write_bytes(item.tobuf(format=tarfile.USTAR_FORMAT) + bytes(1024))
    with pytest.raises(contents.ImageContentsError, match="type"):
        contents.inventory_archive(path)


def test_tar_checksum_and_pax_expansion_refuse_before_payload(tmp_path):
    raw = bytearray(archive_bytes({"entry": ("file", 0o644, b"inert")}))
    raw[0] ^= 1
    path = tmp_path / "invalid.tar"
    path.write_bytes(raw)
    with pytest.raises(contents.ImageContentsError, match="checksum"):
        contents.inventory_archive(path)
    item = tarfile.TarInfo("PaxHeaders/inert")
    item.type, item.size = tarfile.XHDTYPE, 16_385
    path.write_bytes(item.tobuf(format=tarfile.USTAR_FORMAT) + bytes(512))
    with pytest.raises(contents.ImageContentsError, match="PAX"):
        contents.inventory_archive(path)


def test_bounded_pax_path_override_is_cataloged_without_expansion_on_host(tmp_path):
    name = "a" * 110
    body = ("path=" + name + "\n").encode()
    length = len(body) + 2
    while len(str(length)) + 1 + len(body) != length:
        length = len(str(length)) + 1 + len(body)
    raw = str(length).encode() + b" " + body
    header = tarfile.TarInfo("PaxHeaders/entry")
    header.type, header.size = tarfile.XHDTYPE, len(raw)
    member = tarfile.TarInfo("placeholder")
    path = tmp_path / "pax.tar"
    path.write_bytes(
        header.tobuf(format=tarfile.USTAR_FORMAT)
        + raw
        + bytes((-len(raw)) % 512)
        + member.tobuf(format=tarfile.USTAR_FORMAT)
        + bytes(1024)
    )
    catalog = contents.inventory_archive(path)
    assert [entry.path for entry in catalog.entries] == [name]
    assert not (tmp_path / name).exists()


def test_cyclic_hardlinks_and_non_directory_parents_are_refused(tmp_path):
    path = tmp_path / "links.tar"
    path.write_bytes(archive_bytes({"a": ("hardlink", 0o644, "b"), "b": ("hardlink", 0o644, "a")}))
    with pytest.raises(contents.ImageContentsError, match="cyclic"):
        contents.inventory_archive(path)
    path.write_bytes(
        archive_bytes({"a": ("symlink", 0o777, "b"), "a/child": ("file", 0o644, b"inert")})
    )
    with pytest.raises(contents.ImageContentsError, match="parent"):
        contents.inventory_archive(path)


def test_stream_limits_and_trailing_bytes_are_enforced(tmp_path, monkeypatch):
    path = tmp_path / "rootfs.tar"
    raw = archive_bytes({"entry": ("file", 0o644, b"inert")})
    path.write_bytes(raw + b"not-another-archive".ljust(512, b"\0"))
    with pytest.raises(contents.ImageContentsError, match="trailing"):
        contents.inventory_archive(path)
    path.write_bytes(raw)
    monkeypatch.setattr(contents, "MAX_ARCHIVE_BYTES", 1024)
    with pytest.raises(contents.ImageContentsError, match="bounded"):
        contents.inventory_archive(path)
