"""Check HTTP-only A/B inputs and opaque wheels, never build, import or run them.

The pinned older manifest supplies dependency/base metadata only. Its receipts or
runtime roles are not adopted by this mode. Observations are not image identity,
attestation, execution permission or a reproducible-build guarantee.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
from hashlib import sha256
from pathlib import Path

from authzest.runner._repository_http_runtime_profile import expected_assets, expected_recipe_pins
from scripts import generated_image_inputs as shared

ROLES = ("A", "B")
PLATFORMS = ("linux/arm64",)
IMAGES = "runtime/repository_http/images"
BASE_REFERENCE = "runtime/generated_repair/images/manifest.json"
BASE_REFERENCE_SHA256 = "e0c3339143457ae9c57b50e5bf61b77440a4a2e872e4f8b34105d0306743b4e5"
MAX_MANIFEST_BYTES = shared.MAX_MANIFEST_BYTES
MAX_WHEEL_BYTES = shared.MAX_WHEEL_BYTES
ImageInputsError = shared.ImageInputsError
_read_regular = shared._read_regular
_identity = shared._identity
_object = shared._object
_digest = shared._digest
_canonical = shared._canonical
_fail = shared._fail
_ASSET_PATHS = {
    "A": {
        "_guest_common.py": "runtime/repository_http/_guest_common.py",
        "app_launcher.py": "runtime/repository_http/app_launcher.py",
        "repository_http_manifest.py": "src/authzest/runner/_repository_http_manifest.py",
    },
    "B": {
        "_guest_common.py": "runtime/repository_http/_guest_common.py",
        "relay_launcher.py": "runtime/repository_http/relay_launcher.py",
        "repository_http.py": "src/authzest/runner/_repository_http.py",
        "repository_http_transport.py": "src/authzest/runner/_repository_http_transport.py",
    },
}
_ORDER = {
    "A": ("_guest_common.py", "repository_http_manifest.py", "app_launcher.py"),
    "B": (
        "_guest_common.py",
        "repository_http.py",
        "repository_http_transport.py",
        "relay_launcher.py",
    ),
}
_SCRIPTS = {"A": "app_launcher.py", "B": "relay_launcher.py"}


def _role_platform(role: str, platform: str) -> None:
    if (
        type(role) is not str
        or role not in ROLES
        or type(platform) is not str
        or platform not in PLATFORMS
    ):
        _fail("Only HTTP-only A/B on linux/arm64 are supported")


def _header(data: object) -> dict:
    shared._native_tree(data)
    data = _object(
        data,
        {
            "schema_version",
            "kind",
            "status",
            "base_reference",
            "base_reference_sha256",
            "roles",
            "image_ids",
            "contents_verified",
            "runtime_ready",
        },
    )
    if (
        data["schema_version"] != "2.0"
        or data["kind"] != "repository-http-image-inputs"
        or data["status"] != "declared-not-built"
        or data["image_ids"] is not None
        or data["contents_verified"] is not False
        or data["runtime_ready"] is not False
        or data["base_reference"] != BASE_REFERENCE
        or data["base_reference_sha256"] != BASE_REFERENCE_SHA256
    ):
        _fail("Unsupported HTTP image-input declarations")
    return data


def _dockerfile(data: dict, base: dict, role: str, platform: str) -> bytes:
    """Render the maintained exact recipe from already bounded declarations."""
    _role_platform(role, platform)
    digest = base["base"]["platforms"][platform]["manifest_sha256"]
    prefix = "# Separate HTTP-only A/B candidate; not built or runtime accepted.\n"
    reference = "docker.io/library/python@sha256:" + digest
    if role == "A":
        prefix += (
            "FROM " + reference + " AS dependencies\n"
            "COPY requirements.txt /build/requirements.txt\n"
            "COPY wheels/ /build/wheels/\n"
            "RUN --network=none /usr/local/bin/python -I -m pip install --no-index "
            "--find-links=/build/wheels --only-binary=:all: --no-deps --require-hashes "
            "--no-compile --disable-pip-version-check --target=/build/site-packages "
            "-r /build/requirements.txt\n\n"
        )
    prefix += "FROM " + reference + "\n"
    if role == "A":
        prefix += (
            "COPY --from=dependencies /build/site-packages/ "
            "/usr/local/lib/python3.12/site-packages/\n"
        )
    guest = "/opt/authzest-repository-http-guest"
    for name in _ORDER[role]:
        prefix += "COPY --chown=0:0 --chmod=0444 assets/" + name + " " + guest + "/" + name + "\n"
    directories = guest + " /input" + (" /input/project" if role == "A" else "")
    prefix += "RUN --network=none mkdir -p " + directories + " && chmod 0555 " + directories + "\n"
    prefix += "USER 65532:65532\nWORKDIR /tmp\n"
    prefix += (
        'ENTRYPOINT ["/usr/local/bin/python","-I","-B","'
        + guest
        + "/"
        + _SCRIPTS[role]
        + '"]\nCMD []\n'
    )
    return prefix.encode("utf-8")


def _recipe(entry: dict) -> str:
    return sha256(
        _canonical({key: value for key, value in entry.items() if key != "recipe_sha256"})
    ).hexdigest()


def _validate(data: object, base: dict) -> dict:
    data = _header(data)
    _object(data["roles"], set(ROLES))
    for role in ROLES:
        item = _object(data["roles"][role], {"asset_sources", "assets", "platforms"})
        if item["asset_sources"] != _ASSET_PATHS[role] or item["assets"] != expected_assets(role):
            _fail("HTTP maintained source/asset declarations differ")
        _object(item["platforms"], set(PLATFORMS))
        entry = _object(
            item["platforms"]["linux/arm64"],
            {
                "schema_version",
                "kind",
                "role",
                "platform",
                "base_manifest_sha256",
                "dependency_lock_path",
                "dependency_lock_sha256",
                "dockerfile",
                "dockerfile_sha256",
                "assets",
                "recipe_sha256",
            },
        )
        old = base["roles"][role]["platforms"]["linux/arm64"]
        pins = expected_recipe_pins("linux/arm64", role)
        if (
            entry["schema_version"] != "2.0"
            or entry["kind"] != "repository-http-image-recipe"
            or entry["role"] != role
            or entry["platform"] != "linux/arm64"
            or entry["base_manifest_sha256"]
            != base["base"]["platforms"]["linux/arm64"]["manifest_sha256"]
            or entry["dependency_lock_path"] != shared.IMAGES + "/" + old["requirements_file"]
            or entry["dependency_lock_sha256"] != old["requirements_sha256"]
            or entry["dependency_lock_sha256"] != pins["dependency_lock_sha256"]
            or entry["dockerfile"] != "Dockerfile.linux-arm64-" + role
            or entry["assets"] != item["assets"]
            or entry["dockerfile_sha256"]
            != sha256(_dockerfile(data, base, role, "linux/arm64")).hexdigest()
            or entry["recipe_sha256"] != _recipe(entry)
            or entry["recipe_sha256"] != pins["recipe_sha256"]
        ):
            _fail("HTTP dependency/recipe binding differs")
    return data


def _load(root: Path) -> tuple[dict, dict, str, str]:
    root = Path(root)
    raw = _read_regular(root, IMAGES + "/manifest.json", MAX_MANIFEST_BYTES)
    data = _header(shared._decode(raw))
    base_raw = _read_regular(root, BASE_REFERENCE, MAX_MANIFEST_BYTES)
    if sha256(base_raw).hexdigest() != data["base_reference_sha256"]:
        _fail("Pinned base-reference manifest bytes differ")
    base = shared._validate(shared._decode(base_raw))
    shared._check_base_metadata(root, base)
    data = _validate(data, base)
    for role in ROLES:
        item = data["roles"][role]
        entry = item["platforms"]["linux/arm64"]
        lock = _read_regular(root, entry["dependency_lock_path"], 65_536)
        if (
            lock != shared._lock(base, role, "linux/arm64").encode()
            or sha256(lock).hexdigest() != entry["dependency_lock_sha256"]
        ):
            _fail("HTTP dependency lock bytes differ")
        dockerfile = _read_regular(root, IMAGES + "/" + entry["dockerfile"], 65_536)
        if (
            dockerfile != _dockerfile(data, base, role, "linux/arm64")
            or sha256(dockerfile).hexdigest() != entry["dockerfile_sha256"]
        ):
            _fail("HTTP Dockerfile bytes differ")
        for name, relative in item["asset_sources"].items():
            if sha256(_read_regular(root, relative, 65_536)).hexdigest() != item["assets"][name]:
                _fail("HTTP maintained guest asset bytes differ")
    if (
        _read_regular(root, IMAGES + "/manifest.json", MAX_MANIFEST_BYTES) != raw
        or _read_regular(root, BASE_REFERENCE, MAX_MANIFEST_BYTES) != base_raw
    ):
        _fail("HTTP/base manifests changed during input check")
    return data, base, sha256(raw).hexdigest(), sha256(base_raw).hexdigest()


def load_image_inputs(root: Path) -> tuple[dict, dict]:
    """Observe exact HTTP and pinned dependency/base declarations; no images."""
    data, base, _, _ = _load(Path(root))
    return data, base


def selected_inputs(root: Path, role: str, platform: str) -> tuple[dict, dict, dict]:
    """Reject old roles/platforms before reading any selected inputs."""
    _role_platform(role, platform)
    data, base = load_image_inputs(root)
    return data, base, data["roles"][role]["platforms"][platform]


def _report(data: dict, digest: str, base_digest: str) -> dict:
    return {
        "schema_version": "2.0",
        "kind": "repository-http-image-input-check",
        "status": "declared-inputs-checked-not-built",
        "manifest_sha256": digest,
        "base_reference_sha256": base_digest,
        "recipes": [
            {
                "role": role,
                "platform": "linux/arm64",
                "recipe_sha256": data["roles"][role]["platforms"]["linux/arm64"]["recipe_sha256"],
            }
            for role in ROLES
        ],
        "source_bytes_verified": True,
        "base_metadata_bytes_verified": True,
        "wheel_bytes_verified": False,
        "dependency_metadata_provenance": "pinned-manifest-declared-unverified",
        "image_ids": None,
        "contents_verified": False,
        "runtime_ready": False,
        "runtime_invoked": False,
        "build_invoked": False,
        "execution_authorized": False,
    }


def check_image_inputs(root: Path) -> dict:
    """Check only maintained source, locks and captured registry metadata bytes."""
    data, _, digest, base_digest = _load(Path(root))
    return _report(data, digest, base_digest)


def verify_wheelhouse(root: Path, wheelhouse: Path, role: str, platform: str) -> dict:
    """Read an exact selected inert ZIP set; never install or import its files."""
    _role_platform(role, platform)
    data, base, digest, base_digest = _load(Path(root))
    entry = base["roles"][role]["platforms"][platform]
    wheelhouse = Path(wheelhouse)
    before = wheelhouse.lstat()
    if not stat.S_ISDIR(before.st_mode):
        _fail("Wheelhouse must be an ordinary directory")
    selected = [base["packages"][name]["wheels"][platform] for name in entry["packages"]]
    expected = {item["filename"] for item in selected}
    seen = set()
    with os.scandir(wheelhouse) as iterator:
        for item in iterator:
            if len(seen) >= len(expected) or item.name not in expected or item.name in seen:
                _fail("Unexpected HTTP wheelhouse entry")
            seen.add(item.name)
    if seen != expected:
        _fail("Missing HTTP wheelhouse entry")
    for name in entry["packages"]:
        package = base["packages"][name]
        wheel = package["wheels"][platform]
        raw = _read_regular(wheelhouse, wheel["filename"], MAX_WHEEL_BYTES)
        if len(raw) != wheel["size"] or sha256(raw).hexdigest() != wheel["sha256"]:
            _fail("HTTP wheel byte identity differs")
        _, _, _, tags = shared.parse_wheel_filename(wheel["filename"])
        shared._metadata(raw, wheel, name, package["version"], tags)
    if _identity(wheelhouse.lstat()) != _identity(before):
        _fail("HTTP wheelhouse changed during verification")
    current, current_base, current_digest, current_base_digest = _load(Path(root))
    if (
        current != data
        or current_base != base
        or current_digest != digest
        or current_base_digest != base_digest
    ):
        _fail("HTTP/base input manifests changed during wheel verification")
    return {
        **_report(data, digest, base_digest),
        "kind": "repository-http-wheelhouse-check",
        "role": role,
        "platform": platform,
        "wheel_bytes_verified": True,
        "wheel_count": len(selected),
        "dependency_metadata_provenance": "observed-inert-wheel-zip",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wheelhouse", type=Path, help="Check an existing exact opaque wheel set")
    parser.add_argument("--role", choices=ROLES)
    parser.add_argument("--platform", choices=PLATFORMS, default="linux/arm64")
    args = parser.parse_args(argv)
    if (args.wheelhouse is None) != (args.role is None):
        parser.error("--wheelhouse and --role must be supplied together")
    try:
        result = (
            check_image_inputs(args.root)
            if args.wheelhouse is None
            else verify_wheelhouse(args.root, args.wheelhouse, args.role, args.platform)
        )
    except (ImageInputsError, OSError) as exc:
        parser.exit(1, "HTTP image input check failed: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
