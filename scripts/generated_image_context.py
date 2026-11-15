"""Prepare a fresh minimal private image context; never build or run anything.

Only maintained recipes/assets and already verified opaque wheels are copied.
Receipts are historical file observations, not provenance, consent or execution
capabilities. A trusted operator must exclude concurrent same-user writers; file
checks and synchronous OS calls are not atomic compare-and-swap or a wall cap.
"""

from __future__ import annotations

import os
import re
import stat
import sys
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import decode
from scripts import generated_image_inputs as inputs

MAX_FILES = 64
MAX_RECEIPT_BYTES = 262_144


class ImageContextError(ValueError):
    """Preparation/verification failed; created output is retained, never retried."""


@dataclass(frozen=True, slots=True)
class PreparedImageContext:
    context_path: Path
    receipt_path: Path
    payload_json: str
    receipt_identity: tuple

    def to_dict(self) -> dict:
        raw = self.payload_json.encode("utf-8", errors="strict")
        if len(raw) > MAX_RECEIPT_BYTES:
            raise ImageContextError("Context receipt is oversized")
        return decode(self.payload_json)


def _supported() -> bool:
    return (
        os.name == "posix"
        and not getattr(sys, "frozen", False)
        and all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY"))
        and os.open in os.supports_dir_fd
        and os.mkdir in os.supports_dir_fd
    )


def _directory(path: Path, *, private=False) -> tuple:
    if not path.is_absolute() or ".." in path.parts or len(path.parts) > 64:
        raise ImageContextError("An explicit bounded ordinary absolute directory is required")
    for current in (*reversed(path.parents), path):
        value = current.lstat()
        if not stat.S_ISDIR(value.st_mode):
            raise ImageContextError("Directory aliases and special files are unsupported")
    if private and (value.st_uid != os.geteuid() or stat.S_IMODE(value.st_mode) != 0o700):
        raise ImageContextError("Output directory must be private and owned")
    return inputs._identity(value)


def _overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _members(path: Path, expected: set[str]) -> None:
    before = _directory(path, private=True)
    seen = set()
    with os.scandir(path) as entries:
        for item in entries:
            if len(seen) >= len(expected) or item.name not in expected or item.name in seen:
                raise ImageContextError("Unexpected context directory entry")
            seen.add(item.name)
    if seen != expected or _directory(path, private=True) != before:
        raise ImageContextError("Context directory membership changed")


def _open_output(*args, **kwargs):
    try:
        return os.open(*args, **kwargs)
    except BaseException as exc:
        exc.context_descriptor_cleanup_unconfirmed = True
        raise


def _write_file(directory: int, name: str, raw: bytes) -> tuple:
    descriptor = _open_output(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600,
        dir_fd=directory,
    )
    primary = None
    try:
        pending = memoryview(raw)
        while pending:
            count = os.write(descriptor, pending)
            if type(count) is not int or not 0 < count <= len(pending):
                raise ImageContextError("Context file write is incomplete")
            pending = pending[count:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or observed.st_uid != os.geteuid()
            or observed.st_size != len(raw)
            or stat.S_IMODE(observed.st_mode) != 0o600
            or inputs._identity(os.stat(name, dir_fd=directory, follow_symlinks=False))
            != inputs._identity(observed)
        ):
            raise ImageContextError("Created file identity is unconfirmed")
        return inputs._identity(observed)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            os.close(descriptor)
        except BaseException as cleanup:
            cleanup.context_descriptor_cleanup_unconfirmed = True
            if primary is not None:
                primary.context_descriptor_cleanup_unconfirmed = True
                primary.context_cleanup_failure = cleanup
                if not isinstance(cleanup, Exception) and isinstance(primary, Exception):
                    cleanup.context_primary_failure = primary
                    raise
                raise primary from cleanup
            raise


def _read_private(root: Path, relative: str, limit: int) -> tuple[bytes, tuple]:
    value = (root / relative).lstat()
    if value.st_uid != os.geteuid() or stat.S_IMODE(value.st_mode) != 0o600:
        raise ImageContextError("Context file ownership or permissions changed")
    before = inputs._identity(value)
    try:
        raw = inputs._read_regular(root, relative, limit)
    except BaseException as exc:
        # The shared reader does not expose a close receipt on its failure path.
        exc.context_descriptor_cleanup_unconfirmed = True
        raise
    if inputs._identity((root / relative).lstat()) != before:
        raise ImageContextError("Context file identity changed")
    return raw, before


def _source_files(repo: Path, wheelhouse: Path, data: dict, role: str, platform: str):
    entry = data["roles"][role]["platforms"][platform]
    for name, field, digest in (
        ("Dockerfile", "dockerfile", "dockerfile_sha256"),
        ("requirements.txt", "requirements_file", "requirements_sha256"),
    ):
        raw = inputs._read_regular(repo, inputs.IMAGES + "/" + entry[field], 65_536)
        yield name, raw, entry[digest]
    for name, digest in sorted(data["roles"][role]["assets"].items()):
        yield (
            "assets/" + name,
            inputs._read_regular(repo, inputs._ASSET_PATHS[name], 65_536),
            digest,
        )
    for name in entry["packages"]:
        wheel = data["packages"][name]["wheels"][platform]
        raw = inputs._read_regular(wheelhouse, wheel["filename"], inputs.MAX_WHEEL_BYTES)
        if len(raw) != wheel["size"]:
            raise ImageContextError("Selected wheel size changed")
        yield "wheels/" + wheel["filename"], raw, wheel["sha256"]


def prepare_image_context(repo, wheelhouse, parent, role, platform) -> PreparedImageContext:
    """Copy one selected context under an existing private parent; retain failures."""
    if not _supported():
        raise ImageContextError("Context writes require supported POSIX Python source")
    repo, wheelhouse, parent = Path(repo), Path(wheelhouse), Path(parent)
    _directory(repo)
    _directory(wheelhouse)
    parent_pin = _directory(parent, private=True)
    if _overlap(parent, repo) or _overlap(parent, wheelhouse):
        raise ImageContextError("Output parent must be separate from both input roots")
    checked = inputs.check_image_inputs(repo)
    verified = inputs.verify_wheelhouse(repo, wheelhouse, role, platform)
    data, entry = inputs._selected(inputs._manifest(repo), role, platform)
    if verified["manifest_sha256"] != checked["manifest_sha256"]:
        raise ImageContextError("Input manifest changed before preparation")
    bundle = parent / ("authzest-image-context-" + uuid.uuid4().hex)
    descriptors, inventory = {}, []
    created = allocation_attempted = ownership_uncertain = False
    stage = "open-private-parent"
    failure = None
    try:
        descriptors["parent"] = _open_output(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if inputs._identity(os.fstat(descriptors["parent"])) != parent_pin:
            raise ImageContextError("Private output parent changed")
        stage, allocation_attempted = "allocate-bundle", True
        try:
            os.mkdir(bundle.name, 0o700, dir_fd=descriptors["parent"])
        except FileExistsError:
            raise
        except BaseException:
            ownership_uncertain = True
            raise
        created = True
        descriptors["bundle"] = _open_output(
            bundle.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=descriptors["parent"],
        )
        os.fchmod(descriptors["bundle"], 0o700)
        for name, key in (("context", "bundle"), ("assets", "context"), ("wheels", "context")):
            stage = "allocate-" + name
            os.mkdir(name, 0o700, dir_fd=descriptors[key])
            descriptors[name] = _open_output(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptors[key]
            )
            os.fchmod(descriptors[name], 0o700)
        context = bundle / "context"
        for relative, raw, expected in _source_files(repo, wheelhouse, data, role, platform):
            stage = "copy-" + relative
            if len(inventory) >= MAX_FILES or sha256(raw).hexdigest() != expected:
                raise ImageContextError("Selected source bytes changed")
            kind, leaf = relative.split("/", 1) if "/" in relative else ("context", relative)
            pin = _write_file(descriptors[kind], leaf, raw)
            observed, observed_pin = _read_private(context, relative, inputs.MAX_WHEEL_BYTES)
            if observed != raw or observed_pin != pin:
                raise ImageContextError("Prepared file did not read back exactly")
            inventory.append(
                {
                    "path": relative,
                    "size": len(raw),
                    "sha256": expected,
                    "identity": list(pin),
                    "mode": 0o600,
                }
            )
        if inputs.check_image_inputs(repo)["manifest_sha256"] != checked["manifest_sha256"]:
            raise ImageContextError("Inputs changed during preparation")
        for fd in descriptors.values():
            os.fsync(fd)
        value = {
            "schema_version": "1.0",
            "kind": "generated-repair-image-context",
            "status": "prepared-not-built",
            "role": role,
            "platform": platform,
            "manifest_sha256": checked["manifest_sha256"],
            "recipe_sha256": entry["recipe_sha256"],
            "requirements_sha256": entry["requirements_sha256"],
            "bundle_core_identity": list(inputs._identity(os.fstat(descriptors["bundle"]))[:5]),
            "directories": {
                name: list(inputs._identity(os.fstat(descriptors[name])))
                for name in ("context", "assets", "wheels")
            },
            "files": inventory,
            "wheel_count": verified["wheel_count"],
            "image_built": False,
            "build_invoked": False,
            "runtime_invoked": False,
            "runtime_ready": False,
            "ready": False,
            "execution_authorized": False,
        }
        payload = inputs._canonical(value)
        if len(payload) > MAX_RECEIPT_BYTES:
            raise ImageContextError("Prepared receipt exceeds its bound")
        stage = "write-external-receipt"
        receipt_pin = _write_file(descriptors["bundle"], "receipt.json", payload)
        os.fsync(descriptors["bundle"])
        result = PreparedImageContext(
            context, bundle / "receipt.json", payload.decode(), receipt_pin
        )
        check_prepared_context(context, result)
    except BaseException as exc:
        failure = exc
    cleanup = []
    for descriptor in reversed(list(descriptors.values())):
        try:
            os.close(descriptor)
        except BaseException as exc:
            cleanup.append(exc)
    if failure is not None or cleanup:
        causes = ([failure] if failure is not None else []) + cleanup
        primary = next((exc for exc in causes if not isinstance(exc, Exception)), causes[0])
        error = ImageContextError("Context preparation failed; preserve partial output")
        error.planned_bundle = bundle
        error.created_bundle = bundle if created else None
        error.allocation_attempted = allocation_attempted
        error.ownership_uncertain = ownership_uncertain
        error.stage, error.inventory = stage, inventory
        error.output_descriptor_cleanup_confirmed = not cleanup and not getattr(
            failure, "context_descriptor_cleanup_unconfirmed", False
        )
        error.primary_failure, error.cleanup_failures = causes[0], cleanup
        if not isinstance(primary, Exception):
            primary.image_context_preparation = error
            raise primary
        raise error from primary
    return result


def check_prepared_context(root, receipt: PreparedImageContext) -> dict:
    """Recheck exact current output facts; this does not authorize a build/run."""
    if not _supported() or type(receipt) is not PreparedImageContext:
        raise ImageContextError("A supported owned context receipt is required")
    root = Path(root)
    if root != receipt.context_path or receipt.receipt_path != root.parent / "receipt.json":
        raise ImageContextError("Context/receipt location mismatch")
    data = receipt.to_dict()
    fields = {
        "schema_version",
        "kind",
        "status",
        "role",
        "platform",
        "manifest_sha256",
        "recipe_sha256",
        "requirements_sha256",
        "bundle_core_identity",
        "directories",
        "files",
        "wheel_count",
        "image_built",
        "build_invoked",
        "runtime_invoked",
        "runtime_ready",
        "ready",
        "execution_authorized",
    }
    if (
        set(data) != fields
        or data["schema_version"] != "1.0"
        or data["kind"] != "generated-repair-image-context"
    ):
        raise ImageContextError("Invalid context receipt shape")
    if (
        data["status"] != "prepared-not-built"
        or data["role"] not in inputs.ROLES
        or data["platform"] not in inputs.PLATFORMS
        or any(
            data[key] is not False
            for key in (
                "image_built",
                "build_invoked",
                "runtime_invoked",
                "runtime_ready",
                "ready",
                "execution_authorized",
            )
        )
    ):
        raise ImageContextError("Context receipt cannot grant runtime authority")
    for key in ("manifest_sha256", "recipe_sha256", "requirements_sha256"):
        inputs._digest(data[key])
    _members(root.parent, {"context", "receipt.json"})
    if list(_directory(root.parent, private=True)[:5]) != data["bundle_core_identity"]:
        raise ImageContextError("Context bundle identity changed")
    raw, pin = _read_private(root.parent, "receipt.json", MAX_RECEIPT_BYTES)
    if raw != receipt.payload_json.encode() or pin != receipt.receipt_identity:
        raise ImageContextError("External receipt bytes/identity changed")
    directories = {"context": root, "assets": root / "assets", "wheels": root / "wheels"}
    if type(data["directories"]) is not dict or set(data["directories"]) != set(directories):
        raise ImageContextError("Invalid context directory inventory")
    if type(data["files"]) is not list or not 2 <= len(data["files"]) <= MAX_FILES:
        raise ImageContextError("Invalid context file inventory")
    names, memberships = set(), {name: set() for name in directories}
    memberships["context"].update({"assets", "wheels"})
    for entry in data["files"]:
        inputs._object(entry, {"path", "size", "sha256", "identity", "mode"})
        name = entry["path"]
        if type(name) is not str or name in names:
            raise ImageContextError("Duplicate or invalid context file")
        kind, leaf = name.split("/", 1) if "/" in name else ("context", name)
        if kind not in memberships or not re.fullmatch(r"[A-Za-z0-9_.+-]+", leaf):
            raise ImageContextError("Unexpected context file path")
        if kind == "context" and leaf not in {"Dockerfile", "requirements.txt"}:
            raise ImageContextError("Unexpected root context file")
        if kind == "assets" and leaf not in inputs.expected_assets(data["role"]):
            raise ImageContextError("Unexpected guest asset")
        if kind == "wheels" and not leaf.endswith(".whl"):
            raise ImageContextError("Unexpected wheel filename")
        if type(entry["size"]) is not int or not 0 <= entry["size"] <= inputs.MAX_WHEEL_BYTES:
            raise ImageContextError("Invalid context file byte bound")
        inputs._digest(entry["sha256"])
        raw, observed = _read_private(root, name, entry["size"])
        if (
            len(raw) != entry["size"]
            or sha256(raw).hexdigest() != entry["sha256"]
            or list(observed) != entry["identity"]
            or entry["mode"] != 0o600
        ):
            raise ImageContextError("Prepared context file changed")
        names.add(name)
        memberships[kind].add(leaf)
    if (
        memberships["context"] != {"Dockerfile", "requirements.txt", "assets", "wheels"}
        or memberships["assets"] != set(inputs.expected_assets(data["role"]))
        or type(data["wheel_count"]) is not int
        or data["wheel_count"] != len(memberships["wheels"])
    ):
        raise ImageContextError("Incomplete selected context inventory")
    for kind, path in directories.items():
        _members(path, memberships[kind])
        if list(_directory(path, private=True)) != data["directories"][kind]:
            raise ImageContextError("Prepared context directory identity changed")
    return {**data, "status": "context-checked-not-built", "source_paths_disclosed": False}
