"""Observe inert rootfs exports and compare closed candidate image additions.

Never extract archives, resolve links on the host, import wheel code or contact an
engine. Catalogs are historical caller-supplied observations, not image identity,
configuration attestation, permission to execute, or runtime readiness.
"""

from __future__ import annotations

import configparser
import io
import os
import posixpath
import re
import stat
import zipfile
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path

from packaging.utils import canonicalize_name

from scripts import generated_image_inputs as inputs

MAX_ARCHIVE_BYTES = 268_435_456
MAX_ENTRIES = 16_384
CHUNK = 65_536
SITE = "usr/local/lib/python3.12/site-packages/"
_DOCKER_MANAGED = {"etc/hostname", "etc/hosts", "etc/resolv.conf"}


class ImageContentsError(ValueError):
    """Unsupported archive data or a closed comparison mismatch."""


def _fail(reason: str) -> None:
    raise ImageContentsError(reason)


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    path: str
    kind: str
    mode: int
    uid: int
    gid: int
    size: int
    sha256: str | None
    link_target: str | None
    metadata: bytes | None = None


@dataclass(frozen=True, slots=True)
class ArchiveCatalog:
    """Immutable observations only; constructing one grants no authority."""

    entries: tuple[ArchiveEntry, ...]
    archive_sha256: str
    byte_count: int

    def to_dict(self) -> dict:
        return {
            "archive_sha256": self.archive_sha256,
            "byte_count": self.byte_count,
            "entries": [
                {
                    key: getattr(entry, key)
                    for key in (
                        "path",
                        "kind",
                        "mode",
                        "uid",
                        "gid",
                        "size",
                        "sha256",
                        "link_target",
                    )
                }
                for entry in self.entries
            ],
        }


def _text(value: str, limit: int = 1024) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > limit
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or "\\" in value
    ):
        _fail("Invalid archive path/link text")
    return value


def _path(value: str) -> str:
    _text(value)
    if (
        value.startswith("/")
        or len(value.split("/")) > 64
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        _fail("Noncanonical archive path")
    return value


def _link(path: str, target: str, hard: bool) -> str:
    _text(target)
    if hard:
        return _path(target)
    normalized = posixpath.normpath(
        target if target.startswith("/") else posixpath.join(posixpath.dirname(path), target)
    )
    if normalized == ".." or normalized.startswith("../"):
        _fail("Archive symlink escapes rootfs")
    return target


def _field(raw: bytes) -> str:
    value, _, padding = raw.partition(b"\0")
    if padding.strip(b"\0"):
        _fail("Invalid tar text padding")
    try:
        return value.decode("utf-8")
    except UnicodeError as error:
        raise ImageContentsError("Non-UTF8 tar text") from error


def _octal(raw: bytes) -> int:
    value = raw.strip(b"\0 ")
    if not value or re.fullmatch(b"[0-7]+", value) is None or len(value) > 11:
        _fail("Unsupported tar numeric field")
    return int(value, 8)


class _Reader:
    def __init__(self, descriptor: int):
        self.descriptor, self.used, self.digest = descriptor, 0, sha256()

    def chunk(self, size: int) -> bytes:
        raw = os.read(self.descriptor, min(size, CHUNK))
        self.used += len(raw)
        if self.used > MAX_ARCHIVE_BYTES:
            _fail("Rootfs export exceeds byte bound")
        self.digest.update(raw)
        return raw

    def exact(self, size: int) -> bytes:
        chunks, used = [], 0
        while used < size:
            raw = self.chunk(size - used)
            if not raw:
                _fail("Truncated rootfs export")
            chunks.append(raw)
            used += len(raw)
        return b"".join(chunks)


def _pax(raw: bytes) -> dict[str, str]:
    result, offset = {}, 0
    while offset < len(raw):
        space = raw.find(b" ", offset, min(offset + 8, len(raw)))
        length = raw[offset:space] if space >= 0 else b""
        if not length.isdigit() or length.startswith(b"0") or len(result) >= 16:
            _fail("Invalid bounded PAX record")
        end = offset + int(length)
        if end <= space + 1 or end > len(raw) or raw[end - 1 : end] != b"\n":
            _fail("Invalid PAX extent")
        try:
            key, value = raw[space + 1 : end - 1].decode("utf-8").split("=", 1)
        except (UnicodeError, ValueError) as error:
            raise ImageContentsError("Invalid PAX text") from error
        if key in result or key not in {"path", "linkpath", "mtime", "atime", "ctime"}:
            _fail("Unsupported/duplicate PAX field")
        _text(value)
        if key.endswith("time") and re.fullmatch(r"-?[0-9]{1,12}(\.[0-9]{1,9})?", value) is None:
            _fail("Invalid PAX timestamp")
        result[key], offset = value, end
    return result


def _catalog_map(catalog: ArchiveCatalog) -> dict[str, ArchiveEntry]:
    if (
        type(catalog) is not ArchiveCatalog
        or type(catalog.entries) is not tuple
        or len(catalog.entries) > MAX_ENTRIES
        or type(catalog.byte_count) is not int
        or not 1024 <= catalog.byte_count <= MAX_ARCHIVE_BYTES
        or type(catalog.archive_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", catalog.archive_sha256) is None
    ):
        _fail("Invalid caller-supplied archive catalog")
    result = {}
    for item in catalog.entries:
        if type(item) is not ArchiveEntry or _path(item.path) in result:
            _fail("Invalid/duplicate catalog entry")
        if (
            type(item.kind) is not str
            or item.kind not in {"file", "directory", "symlink", "hardlink"}
            or any(
                type(number) is not int or number < 0
                for number in (item.mode, item.uid, item.gid, item.size)
            )
            or item.mode > 0o7777
            or item.size > MAX_ARCHIVE_BYTES
        ):
            _fail("Invalid archive entry metadata")
        if item.kind == "file":
            if (
                type(item.sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", item.sha256) is None
                or item.link_target is not None
            ):
                _fail("Invalid file digest/link metadata")
            if item.metadata is not None and (
                type(item.metadata) is not bytes
                or len(item.metadata) > inputs.MAX_METADATA_BYTES
                or len(item.metadata) != item.size
                or sha256(item.metadata).hexdigest() != item.sha256
            ):
                _fail("Invalid captured package metadata")
        elif (
            item.sha256 is not None
            or item.size != 0
            or item.metadata is not None
            or ((item.kind == "directory") != (item.link_target is None))
        ):
            _fail("Invalid non-file entry metadata")
        if item.link_target is not None:
            _link(item.path, item.link_target, item.kind == "hardlink")
        result[item.path] = item
    for path, item in result.items():
        parent = posixpath.dirname(path)
        while parent:
            if parent not in result or result[parent].kind != "directory":
                _fail("Missing/non-directory archive parent")
            parent = posixpath.dirname(parent)
        visited = set()
        while item.kind == "hardlink":
            if item.path in visited or len(visited) >= 64 or item.link_target not in result:
                _fail("Unresolved/cyclic archive hardlink")
            visited.add(item.path)
            item = result[item.link_target]
        if visited and item.kind != "file":
            _fail("Archive hardlink does not name a regular file")
    return result


def inventory_archive(path: Path) -> ArchiveCatalog:
    """Hash an uncompressed tar in 64 KiB chunks without extracting any entry."""
    path = Path(path)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 1024 <= before.st_size <= MAX_ARCHIVE_BYTES
        or before.st_size % 512
    ):
        _fail("Export must be a bounded single-link ordinary tar file")
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0),
    )
    try:
        opened = os.fstat(descriptor)
        if inputs._opened_binding(opened) != inputs._opened_binding(before):
            _fail("Export changed before read")
        reader, entries, pending, captured = _Reader(descriptor), [], None, 0
        for _ in range(MAX_ENTRIES + 1):
            header = reader.exact(512)
            if header == bytes(512):
                if pending is not None or reader.exact(512) != bytes(512):
                    _fail("Invalid tar end markers")
                while raw := reader.chunk(CHUNK):
                    if raw.strip(b"\0"):
                        _fail("Nonzero trailing export data")
                break
            checksum = sum(header[:148]) + 8 * 32 + sum(header[156:])
            if _octal(header[148:156]) != checksum or header[257:263] not in {
                b"ustar\0",
                b"ustar ",
            }:
                _fail("Unsupported tar header/checksum")
            name, prefix = _field(header[:100]), _field(header[345:500])
            name = prefix + "/" + name if prefix else name
            mode, uid, gid, size = (
                _octal(header[start:end])
                for start, end in ((100, 108), (108, 116), (116, 124), (124, 136))
            )
            kind = header[156:157]
            if kind == b"x":
                if pending is not None or size > 16_384:
                    _fail("Unsupported PAX expansion")
                _path(name.rstrip("/"))
                pending = _pax(reader.exact(size))
            else:
                if kind not in {b"0", b"\0", b"5", b"2", b"1"} or len(entries) >= MAX_ENTRIES:
                    _fail("Unsupported tar entry type/count")
                overrides, pending = pending or {}, None
                name = overrides.get("path", name)
                name = _path(name[:-1] if kind == b"5" and name.endswith("/") else name)
                target = overrides.get("linkpath", _field(header[157:257]))
                entry_kind = {
                    b"0": "file",
                    b"\0": "file",
                    b"5": "directory",
                    b"2": "symlink",
                    b"1": "hardlink",
                }[kind]
                if size > MAX_ARCHIVE_BYTES or (entry_kind != "file" and size != 0):
                    _fail("Unsupported tar entry size")
                digest, chunks, remaining = sha256(), [], size
                capture = name.startswith(SITE) and name.endswith(".dist-info/METADATA")
                if capture and (size > inputs.MAX_METADATA_BYTES or captured + size > 4_194_304):
                    _fail("Installed package metadata exceeds capture bound")
                while remaining:
                    raw = reader.exact(min(CHUNK, remaining))
                    digest.update(raw)
                    if capture:
                        chunks.append(raw)
                    remaining -= len(raw)
                captured += size if capture else 0
                entries.append(
                    ArchiveEntry(
                        name,
                        entry_kind,
                        mode,
                        uid,
                        gid,
                        size,
                        digest.hexdigest() if entry_kind == "file" else None,
                        _link(name, target, entry_kind == "hardlink")
                        if entry_kind in {"symlink", "hardlink"}
                        else None,
                        b"".join(chunks) if capture else None,
                    )
                )
            if reader.exact((-size) % 512).strip(b"\0"):
                _fail("Nonzero tar member padding")
        else:
            _fail("Tar header count exceeds bound")
        if (
            reader.used != before.st_size
            or inputs._identity(os.fstat(descriptor)) != inputs._identity(opened)
            or inputs._identity(path.lstat()) != inputs._identity(before)
        ):
            _fail("Export changed during read")
        result = ArchiveCatalog(
            tuple(sorted(entries, key=lambda entry: entry.path)),
            reader.digest.hexdigest(),
            reader.used,
        )
        _catalog_map(result)
        return result
    finally:
        os.close(descriptor)


def _package_metadata(raw: bytes) -> tuple[str, str]:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if message.defects:
        _fail("Malformed installed package metadata")
    values = []
    for key in ("Name", "Version"):
        fields = message.get_all(key, [])
        if len(fields) != 1 or not str(fields[0]) or len(str(fields[0])) > 128:
            _fail("Missing/ambiguous installed package identity")
        values.append(str(fields[0]))
    return canonicalize_name(values[0]), values[1]


def _packages(entries: dict[str, ArchiveEntry]) -> dict[str, str]:
    result = {}
    for entry in entries.values():
        if entry.path.startswith(SITE) and ".egg-info" in entry.path:
            _fail("Unsupported legacy package metadata")
        if entry.path.startswith(SITE) and entry.path.endswith(".dist-info/METADATA"):
            if entry.kind != "file" or entry.metadata is None:
                _fail("Missing observed installed METADATA bytes")
            name, version = _package_metadata(entry.metadata)
            if name in result:
                _fail("Duplicate installed distribution name")
            result[name] = version
    return result


def _wheel_files(
    data: dict, wheelhouse: Path, names: list[str], platform: str
) -> tuple[dict, set, set]:
    payloads, records, scripts, expanded, member_count = {}, set(), set(), 0, 0
    for name in names:
        wheel = data["packages"][name]["wheels"][platform]
        raw = inputs._read_regular(wheelhouse, wheel["filename"], inputs.MAX_WHEEL_BYTES)
        if len(raw) != wheel["size"] or sha256(raw).hexdigest() != wheel["sha256"]:
            _fail("Wheel changed after input verification")
        inputs._zip_directory(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            wheel_records = []
            metadata_paths = [
                member.filename
                for member in archive.infolist()
                if member.filename.endswith(".dist-info/METADATA")
            ]
            for member in archive.infolist():
                expanded += member.file_size
                member_count += 1
                if expanded > 134_217_728 or member_count > MAX_ENTRIES:
                    _fail("Selected wheel payload inventory exceeds bound")
                path = _path(member.filename.rstrip("/"))
                if any(part.endswith(".data") for part in path.split("/")):
                    _fail("Wheel .data relocation is unsupported")
                if member.is_dir():
                    continue
                if stat.S_IFMT(member.external_attr >> 16) not in {0, stat.S_IFREG}:
                    _fail("Unsupported wheel payload file type")
                target = SITE + path
                if path.endswith(".dist-info/RECORD"):
                    wheel_records.append(target)
                    records.add(target)
                    continue
                if target in payloads or member.file_size > 67_108_864:
                    _fail("Colliding/oversized wheel payload")
                digest, captured, size = sha256(), [], 0
                with archive.open(member) as stream:
                    while chunk := stream.read(CHUNK):
                        size += len(chunk)
                        if size > 67_108_864:
                            _fail("Wheel payload exceeds byte bound")
                        digest.update(chunk)
                        if path.endswith(".dist-info/entry_points.txt"):
                            if size > 65_536:
                                _fail("Wheel entrypoint metadata exceeds bound")
                            captured.append(chunk)
                if size != member.file_size:
                    _fail("Wheel payload size mismatch")
                mode = 0o755 if (member.external_attr >> 16) & 0o111 else 0o644
                payloads[target] = (size, digest.hexdigest(), mode)
                if captured:
                    parser = configparser.ConfigParser(interpolation=None, strict=True)
                    parser.optionxform = str
                    try:
                        parser.read_string(b"".join(captured).decode("utf-8"))
                    except (UnicodeError, configparser.Error) as error:
                        raise ImageContentsError("Malformed wheel entrypoint metadata") from error
                    for section in ("console_scripts", "gui_scripts"):
                        if section not in parser:
                            continue
                        for script in parser[section]:
                            if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}", script) is None:
                                _fail("Unsupported generated script name")
                            scripts.add(SITE + "bin/" + script)
            if len(metadata_paths) != 1 or wheel_records != [
                SITE + metadata_paths[0].rsplit("/", 1)[0] + "/RECORD"
            ]:
                _fail("Wheel must contain one installed RECORD path")
    if set(payloads) & (records | scripts):
        _fail("Generated pip files collide with ordinary wheel payloads")
    return payloads, records, scripts


def compare_image_contents(
    repo: Path,
    base_catalog: ArchiveCatalog,
    role_catalog: ArchiveCatalog,
    wheelhouse: Path,
    role: str,
    platform: str,
) -> dict:
    """Compare observed baseline and selected payloads, retaining granular limits."""
    if (
        type(role) is not str
        or role not in inputs.ROLES
        or type(platform) is not str
        or platform != "linux/arm64"
    ):
        _fail("Only maintained native Linux arm64 roles are supported")
    checked = inputs.verify_wheelhouse(repo, wheelhouse, role, platform)
    data = inputs._manifest(Path(repo))
    if (
        sha256(
            inputs._read_regular(
                Path(repo), inputs.IMAGES + "/manifest.json", inputs.MAX_MANIFEST_BYTES
            )
        ).hexdigest()
        != checked["manifest_sha256"]
    ):
        _fail("Manifest changed before contents comparison")
    baseline, observed = _catalog_map(base_catalog), _catalog_map(role_catalog)
    names = data["roles"][role]["platforms"][platform]["packages"]
    payloads, records, scripts = _wheel_files(data, Path(wheelhouse), names, platform)
    expected = {"opt/authzest-guest": ("directory", 0o555, 0, None)}
    for name, digest in data["roles"][role]["assets"].items():
        expected["opt/authzest-guest/" + name] = ("file", 0o444, None, digest)
    if role in {"T", "A"}:
        expected.update(
            {
                "input": ("directory", 0o555, 0, None),
                "input/app.py": ("file", 0o444, 0, sha256(b"").hexdigest()),
            }
        )
    if role == "T":
        expected.update(
            {
                "input/tests": ("directory", 0o555, 0, None),
                "input/tests/test_generated_ownership.py": (
                    "file",
                    0o444,
                    0,
                    sha256(b"").hexdigest(),
                ),
            }
        )
    for path, (size, digest, mode) in payloads.items():
        expected[path] = ("file", mode, size, digest)
    generated = {}
    for path in records:
        generated[path] = "pip-record"
        prefix = path.rsplit("/", 1)[0]
        expected[prefix + "/INSTALLER"] = ("file", 0o644, 4, sha256(b"pip\n").hexdigest())
        expected[prefix + "/REQUESTED"] = ("file", 0o644, 0, sha256(b"").hexdigest())
    generated.update(dict.fromkeys(scripts, "pip-entrypoint"))
    for path in list(expected) + list(generated):
        parent = posixpath.dirname(path)
        while parent:
            if parent not in baseline and parent not in expected:
                expected[parent] = ("directory", 0o755, 0, None)
            parent = posixpath.dirname(parent)
    for path, before in baseline.items():
        if path in expected or path in generated:
            _fail("Selected additions collide with baseline paths")
        if observed.get(path) != before:
            _fail("Baseline rootfs content/metadata changed: " + path)
    unverified = []
    for path, item in observed.items():
        if path in generated:
            expected_mode = 0o644 if generated[path] == "pip-record" else 0o755
            if (
                item.kind != "file"
                or item.mode != expected_mode
                or item.uid
                or item.gid
                or item.size > 1_048_576
            ):
                _fail("Unexpected pip-generated file metadata")
            unverified.append({"path": path, "sha256": item.sha256, "kind": generated[path]})
        elif path in expected:
            kind, mode, size, digest = expected[path]
            if (
                item.kind != kind
                or item.mode != mode
                or item.uid
                or item.gid
                or (size is not None and item.size != size)
                or item.sha256 != digest
            ):
                _fail("Selected rootfs payload/metadata mismatch: " + path)
        elif path not in baseline:
            _fail("Unexpected rootfs addition: " + path)
    if set(expected) - set(observed) or records - set(observed) or scripts - set(observed):
        _fail("Missing selected rootfs additions")
    base_packages = _packages(baseline)
    if set(base_packages) & set(names):
        _fail("Selected package overlaps baseline distribution")
    package_versions = {
        **base_packages,
        **{name: data["packages"][name]["version"] for name in names},
    }
    if _packages(observed) != package_versions:
        _fail("Installed distribution inventory differs from baseline plus exact lock")
    return {
        "schema_version": "1.0",
        "kind": "generated-repair-image-content-comparison",
        "role": role,
        "platform": platform,
        "status": "selected-payloads-compared",
        "base_archive_sha256": base_catalog.archive_sha256,
        "role_archive_sha256": role_catalog.archive_sha256,
        "manifest_sha256": checked["manifest_sha256"],
        "baseline_unchanged": True,
        "wheel_payloads_verified": True,
        "maintained_assets_verified": True,
        "installed_package_metadata_verified": True,
        "installed_packages": package_versions,
        "unverified_generated_files": sorted(unverified, key=lambda item: item["path"]),
        "docker_managed_exclusions": [],
        "docker_managed_files_compared": sorted(_DOCKER_MANAGED & set(baseline)),
        "contents_verified": False,
        "image_configuration_verified": False,
        "runtime_ready": False,
        "runtime_invoked": False,
        "execution_authorized": False,
        "authorization": "unknown",
        "verified_fix": False,
        "limitations": [
            "Caller-supplied exports are not authenticated image identities.",
            "Pip RECORD/entrypoint contents are observed, not independently validated.",
            "Timestamps, xattrs, signatures and effective runtime behavior are not attested.",
        ],
    }
