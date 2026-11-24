"""Compare supplied HTTP-only A/B rootfs observations without executing an image.

The shared TAR/ZIP primitives only hash inert bytes. This entry accepts current
HTTP image inputs, never an old comparison receipt as image/runtime authority.
A matching catalog is still caller-supplied, unauthenticated historical data.
"""

from __future__ import annotations

import posixpath
from hashlib import sha256
from pathlib import Path

from scripts import generated_image_contents as common
from scripts import repository_http_image_inputs as inputs

# Archive facts have no mode/execution identity; reuse the unchanged bounded
# format parser, immutable records and errors rather than forking that parser.
ArchiveCatalog = common.ArchiveCatalog
ArchiveEntry = common.ArchiveEntry
ImageContentsError = common.ImageContentsError
inventory_archive = common.inventory_archive
SITE = common.SITE
_DOCKER_MANAGED = common._DOCKER_MANAGED


def _fail(reason: str) -> None:
    raise ImageContentsError(reason)


def _check_binding(repo: Path, data: dict, checked: dict) -> None:
    for relative, expected in (
        (inputs.IMAGES + "/manifest.json", checked["manifest_sha256"]),
        (data["base_reference"], checked["base_reference_sha256"]),
    ):
        raw = inputs._read_regular(repo, relative, inputs.MAX_MANIFEST_BYTES)
        if sha256(raw).hexdigest() != expected:
            _fail("HTTP/base manifest changed before contents comparison")


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
        _fail("Only HTTP A/B Linux arm64 roles are supported")
    checked = inputs.verify_wheelhouse(repo, wheelhouse, role, platform)
    data, base, entry = inputs.selected_inputs(Path(repo), role, platform)
    _check_binding(Path(repo), data, checked)
    baseline, observed = common._catalog_map(base_catalog), common._catalog_map(role_catalog)
    names = base["roles"][role]["platforms"][platform]["packages"]
    payloads, records, scripts = common._wheel_files(base, Path(wheelhouse), names, platform)
    expected = {"opt/authzest-repository-http-guest": ("directory", 0o555, 0, None)}
    for name, digest in data["roles"][role]["assets"].items():
        raw = inputs._read_regular(Path(repo), data["roles"][role]["asset_sources"][name], 65_536)
        if sha256(raw).hexdigest() != digest:
            _fail("Maintained HTTP asset changed before contents comparison")
        expected["opt/authzest-repository-http-guest/" + name] = ("file", 0o444, len(raw), digest)
    expected["input"] = ("directory", 0o555, 0, None)
    if role == "A":
        expected["input/project"] = ("directory", 0o555, 0, None)
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
    base_packages = common._packages(baseline)
    if set(base_packages) & set(names):
        _fail("Selected package overlaps baseline distribution")
    package_versions = {
        **base_packages,
        **{name: base["packages"][name]["version"] for name in names},
    }
    if common._packages(observed) != package_versions:
        _fail("Installed distribution inventory differs from baseline plus exact lock")
    final = inputs.verify_wheelhouse(Path(repo), Path(wheelhouse), role, platform)
    if any(final[key] != checked[key] for key in ("manifest_sha256", "base_reference_sha256")):
        _fail("HTTP/base input identities changed during contents comparison")
    _check_binding(Path(repo), data, checked)
    return {
        "schema_version": "2.0",
        "kind": "repository-http-image-content-comparison",
        "role": role,
        "platform": platform,
        "status": "selected-payloads-compared",
        "base_archive_sha256": base_catalog.archive_sha256,
        "role_archive_sha256": role_catalog.archive_sha256,
        "manifest_sha256": checked["manifest_sha256"],
        "base_reference_sha256": checked["base_reference_sha256"],
        "recipe_sha256": entry["recipe_sha256"],
        "dependency_lock_sha256": entry["dependency_lock_sha256"],
        "provenance": "caller-supplied-unverified",
        "image_identity_verified": False,
        "baseline_unchanged": True,
        "wheel_payloads_verified": True,
        "maintained_assets_verified": True,
        "installed_package_metadata_verified": True,
        "installed_packages": package_versions,
        "unverified_generated_files": sorted(unverified, key=lambda item: item["path"]),
        "docker_managed_exclusions": [],
        "docker_managed_files_compared": sorted(_DOCKER_MANAGED & set(baseline)),
        "image_built": False,
        "build_invoked": False,
        "contents_verified": False,
        "image_configuration_verified": False,
        "runtime_ready": False,
        "ready": False,
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
