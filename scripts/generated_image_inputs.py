"""Check pinned candidate image inputs without downloading, building or running.

The default check observes maintained source/recipe bytes and declared upstream
metadata only. Even optional wheel-byte verification is not image attestation,
runtime readiness, execution permission or a bit-reproducible-build guarantee.
Dockerfiles describe a future minimal context, never the repository checkout.
"""

from __future__ import annotations

import argparse
import email.policy
import io
import json
import os
import re
import stat
import struct
import zipfile
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote, urlsplit

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version

from authzest.runner._generated_repair_runtime_profile import expected_assets

PLATFORMS = ("linux/amd64", "linux/arm64")
ROLES = ("T", "A", "B")
IMAGES = "runtime/generated_repair/images"
MAX_MANIFEST_BYTES = 1_048_576
MAX_WHEEL_BYTES = 16_777_216
MAX_WHEEL_INVENTORY_BYTES = 134_217_728
MAX_METADATA_BYTES = 262_144
_DIRECT = {"T": ["fastapi", "httpx", "pytest"], "A": ["fastapi", "uvicorn"], "B": []}
_SCRIPTS = {"T": "test_launcher.py", "A": "app_launcher.py", "B": "relay_launcher.py"}
_ASSET_PATHS = {
    "_guest_common.py": "runtime/generated_repair/_guest_common.py",
    "test_launcher.py": "runtime/generated_repair/test_launcher.py",
    "app_launcher.py": "runtime/generated_repair/app_launcher.py",
    "relay_launcher.py": "runtime/generated_repair/relay_launcher.py",
    "_generated_repair_http.py": "src/authzest/runner/_generated_repair_http.py",
}
_INDEX_MEDIA_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}
_MANIFEST_MEDIA_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}
_CONFIG_MEDIA_TYPES = {
    "application/vnd.oci.image.config.v1+json",
    "application/vnd.docker.container.image.v1+json",
}


class ImageInputsError(ValueError):
    """A closed input contract or observed file failed validation."""


def _fail(reason: str) -> None:
    raise ImageInputsError(reason)


def _object(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        _fail("Unexpected object fields")
    return value


def _text(value: object, limit: int = 4096) -> str:
    if (
        type(value) is not str
        or len(value) > limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        _fail("Invalid bounded text")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail("Invalid SHA-256")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _native_tree(value: object) -> None:
    """Bound even direct renderer inputs before equality/canonical serialization."""
    pending, count, characters = [(value, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 16_384 or depth > 16:
            _fail("Manifest exceeds shape bound")
        if type(item) is dict:
            if len(item) > 128 or any(type(key) is not str for key in item):
                _fail("Invalid native JSON object")
            pending.extend((child, depth + 1) for child in item.values())
            pending.extend((key, depth + 1) for key in item)
        elif type(item) is list:
            if len(item) > 128:
                _fail("Invalid bounded JSON array")
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            characters += len(item)
            if len(item) > 4096 or characters > MAX_MANIFEST_BYTES:
                _fail("Manifest exceeds text bound")
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ImageInputsError("Invalid Unicode JSON text") from exc
        elif type(item) is int:
            if not -999_999_999_999 <= item <= 999_999_999_999:
                _fail("Oversized JSON integer")
        elif type(item) not in {bool, type(None)}:
            _fail("Unsupported native JSON value")


def _decode(raw: bytes) -> dict:
    if len(raw) > MAX_MANIFEST_BYTES:
        _fail("Manifest exceeds byte bound")

    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                _fail("Duplicate JSON field")
            result[key] = value
        return result

    def integer(value: str) -> int:
        if len(value) > 12:
            _fail("Oversized JSON integer")
        return int(value)

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_int=integer,
            parse_constant=lambda _: _fail("Nonfinite JSON value"),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ImageInputsError("Invalid bounded JSON") from exc
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > 16_384 or depth > 16:
            _fail("Manifest exceeds shape bound")
        if type(item) is dict:
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)
        elif type(item) not in {str, int, bool, type(None)}:
            _fail("Unsupported JSON scalar")
    if type(value) is not dict:
        _fail("Manifest must be an object")
    return value


def _target(platform: str, python_version: str) -> dict[str, str]:
    return {
        "implementation_name": "cpython",
        "implementation_version": python_version,
        "os_name": "posix",
        "platform_machine": "x86_64" if platform.endswith("amd64") else "aarch64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": python_version,
        "python_version": "3.12",
        "sys_platform": "linux",
        "extra": "",
    }


def _active_dependencies(wheel: dict, platform: str, python_version: str) -> list[Requirement]:
    dependencies = []
    for raw in wheel["requires_dist"]:
        try:
            requirement = Requirement(raw)
        except InvalidRequirement as exc:
            raise ImageInputsError("Invalid dependency requirement") from exc
        # No target kernel/release is selected. Refuse those marker dimensions.
        if requirement.marker is not None:
            marker = str(requirement.marker)
            if re.search(r"\bplatform_(release|version)\b", marker):
                _fail("Unspecified target marker dimension")
            if not requirement.marker.evaluate(_target(platform, python_version)):
                continue
        if requirement.url is not None or requirement.extras:
            _fail("Active dependency extras and direct URLs are unsupported")
        dependencies.append(requirement)
    return dependencies


def _compatible_tag(tag: object, platform: str) -> bool:
    interpreter, abi, target = tag.interpreter, tag.abi, tag.platform
    if interpreter in {"py3", "py312"}:
        if abi != "none":
            return False
    elif interpreter.startswith("cp") and interpreter[2:].isdigit():
        abi3_interpreters = {
            "cp32",
            "cp33",
            "cp34",
            "cp35",
            "cp36",
            "cp37",
            "cp38",
            "cp39",
            "cp310",
            "cp311",
            "cp312",
        }
        if not (interpreter == "cp312" and abi in {"cp312", "abi3", "none"}) and not (
            abi == "abi3" and interpreter in abi3_interpreters
        ):
            return False
    else:
        return False
    if target == "any":
        return abi == "none"
    arch = "x86_64" if platform.endswith("amd64") else "aarch64"
    match = re.fullmatch(r"manylinux_2_(17|28)_" + arch, target)
    # Fixed reviewed manylinux baselines; no musl, generic linux or host-derived tags.
    return match is not None


def _wheel(name: str, version: str, value: object, platform: str, python_version: str) -> dict:
    wheel = _object(
        value, {"filename", "url", "sha256", "size", "requires_python", "requires_dist"}
    )
    filename = _text(wheel["filename"], 240)
    if re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", filename) is None:
        _fail("Invalid wheel filename")
    try:
        wheel_name, wheel_version, _, tags = parse_wheel_filename(filename)
        if wheel_name != name or wheel_version != Version(version):
            _fail("Wheel name/version mismatch")
        if not any(_compatible_tag(tag, platform) for tag in tags):
            _fail("Unsupported wheel target tags")
        specifier = SpecifierSet(_text(wheel["requires_python"]))
        if not specifier.contains(python_version, prereleases=True):
            _fail("Wheel excludes selected Python")
    except (InvalidWheelFilename, InvalidSpecifier, InvalidVersion) as exc:
        raise ImageInputsError("Invalid wheel version contract") from exc
    _digest(wheel["sha256"])
    if type(wheel["size"]) is not int or not 0 < wheel["size"] <= MAX_WHEEL_BYTES:
        _fail("Invalid wheel byte size")
    url = urlsplit(_text(wheel["url"], 2048))
    if (
        url.scheme != "https"
        or url.netloc != "files.pythonhosted.org"
        or not url.path.startswith("/packages/")
        or url.query
        or url.fragment
        or unquote(url.path.rsplit("/", 1)[-1]) != filename
        or "%" in url.path
        or "/../" in url.path
        or "/./" in url.path
    ):
        _fail("Unsupported upstream wheel URL")
    requirements = wheel["requires_dist"]
    if type(requirements) is not list or len(requirements) > 128:
        _fail("Invalid dependency list")
    for requirement in requirements:
        _text(requirement, 2048)
    if len(set(requirements)) != len(requirements):
        _fail("Duplicate dependency metadata")
    _active_dependencies(wheel, platform, python_version)
    return wheel


def _closure(manifest: dict, role: str, platform: str) -> list[str]:
    packages = manifest["packages"]
    pending, reached = list(_DIRECT[role]), set()
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        if name not in packages:
            _fail("Missing dependency package")
        reached.add(name)
        wheel = packages[name]["wheels"][platform]
        for dependency in _active_dependencies(wheel, platform, manifest["python_version"]):
            child = canonicalize_name(dependency.name)
            if child not in packages:
                _fail("Missing transitive dependency")
            if not dependency.specifier.contains(packages[child]["version"], prereleases=True):
                _fail("Pinned dependency violates requirement")
            pending.append(child)
    return sorted(reached)


def _validate(manifest: object) -> dict:
    _native_tree(manifest)
    data = _object(
        manifest,
        {
            "schema_version",
            "kind",
            "status",
            "python_version",
            "base",
            "packages",
            "roles",
            "image_ids",
            "contents_verified",
            "runtime_ready",
        },
    )
    if (
        data["schema_version"] != "1.0"
        or data["kind"] != "generated-repair-image-inputs"
        or data["status"] != "candidate-not-built"
        or data["image_ids"] is not None
        or data["contents_verified"] is not False
        or data["runtime_ready"] is not False
        or type(data["python_version"]) is not str
        or re.fullmatch(r"3\.12\.(0|[1-9][0-9]{0,2})", data["python_version"]) is None
    ):
        _fail("Unsupported candidate image contract")
    base = _object(data["base"], {"repository", "source_tag", "index_sha256", "platforms"})
    if base["repository"] != "docker.io/library/python":
        _fail("Unsupported base repository")
    tag = _text(base["source_tag"], 128)
    if re.fullmatch(r"[A-Za-z0-9_.-]+", tag) is None:
        _fail("Invalid source tag")
    _digest(base["index_sha256"])
    _object(base["platforms"], set(PLATFORMS))
    for platform in PLATFORMS:
        item = _object(
            base["platforms"][platform],
            {
                "manifest_sha256",
                "config_sha256",
                "os",
                "architecture",
                "variant",
            },
        )
        _digest(item["manifest_sha256"])
        _digest(item["config_sha256"])
        if (
            item["os"] != "linux"
            or item["architecture"] != platform.split("/")[1]
            or type(item["variant"]) is not str
            or item["variant"] not in ({""} if platform.endswith("amd64") else {"", "v8"})
        ):
            _fail("Base platform mismatch")
    packages = data["packages"]
    if type(packages) is not dict or not 1 <= len(packages) <= 128:
        _fail("Invalid package inventory")
    total_size = 0
    for name, package in packages.items():
        if type(name) is not str or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
            _fail("Noncanonical package name")
        _object(package, {"version", "wheels"})
        version = _text(package["version"], 64)
        try:
            parsed = Version(version)
        except InvalidVersion as exc:
            raise ImageInputsError("Invalid pinned version") from exc
        if str(parsed) != version or parsed.is_prerelease or parsed.is_devrelease or parsed.local:
            _fail("Unsupported pinned version")
        _object(package["wheels"], set(PLATFORMS))
        for platform in PLATFORMS:
            total_size += _wheel(
                name, version, package["wheels"][platform], platform, data["python_version"]
            )["size"]
    if total_size > MAX_WHEEL_INVENTORY_BYTES:
        _fail("Wheel inventory exceeds byte bound")
    _object(data["roles"], set(ROLES))
    used = set()
    for role in ROLES:
        item = _object(data["roles"][role], {"direct_requirements", "assets", "platforms"})
        if item["direct_requirements"] != _DIRECT[role] or item["assets"] != expected_assets(role):
            _fail("Maintained role requirements/assets mismatch")
        _object(item["platforms"], set(PLATFORMS))
        for platform in PLATFORMS:
            entry = _object(
                item["platforms"][platform],
                {
                    "packages",
                    "requirements_file",
                    "requirements_sha256",
                    "dockerfile",
                    "dockerfile_sha256",
                    "recipe_sha256",
                },
            )
            closure = _closure(data, role, platform)
            if type(entry["packages"]) is not list or entry["packages"] != closure:
                _fail("Role package inventory is not exact dependency closure")
            used.update(closure)
            stem = platform.replace("/", "-") + "-" + role
            if (
                entry["requirements_file"] != "locks/" + stem + ".txt"
                or entry["dockerfile"] != "dockerfiles/" + stem + ".Dockerfile"
            ):
                _fail("Unexpected image input path")
            for key in ("requirements_sha256", "dockerfile_sha256", "recipe_sha256"):
                _digest(entry[key])
    if used != set(packages):
        _fail("Unneeded package in manifest")
    return data


def _selected(manifest: object, role: str, platform: str) -> tuple[dict, dict]:
    if (
        type(role) is not str
        or role not in ROLES
        or type(platform) is not str
        or platform not in PLATFORMS
    ):
        _fail("Unsupported role/platform")
    data = _validate(manifest)
    return data, data["roles"][role]["platforms"][platform]


def _lock(data: dict, role: str, platform: str) -> str:
    names = data["roles"][role]["platforms"][platform]["packages"]
    if not names:
        return "# No additional Python wheels for the stdlib-only relay.\n"
    return "".join(
        name
        + "=="
        + data["packages"][name]["version"]
        + " --hash=sha256:"
        + data["packages"][name]["wheels"][platform]["sha256"]
        + "\n"
        for name in names
    )


def render_lock(manifest: dict, role: str, platform: str) -> str:
    """Render exact pins from declarations; do not open wheel files or install."""
    data, _ = _selected(manifest, role, platform)
    return _lock(data, role, platform)


def _dockerfile(data: dict, role: str, platform: str) -> str:
    base = (
        data["base"]["repository"]
        + "@sha256:"
        + data["base"]["platforms"][platform]["manifest_sha256"]
    )
    lines = ["# Candidate recipe; image contents and inherited base hooks are unverified."]
    if role != "B":
        lines += [
            "FROM " + base + " AS dependencies",
            "COPY requirements.txt /build/requirements.txt",
            "COPY wheels/ /build/wheels/",
            "RUN --network=none /usr/local/bin/python -I -m pip install "
            "--no-index --find-links=/build/wheels --only-binary=:all: --no-deps "
            "--require-hashes --no-compile --disable-pip-version-check "
            "--target=/build/site-packages -r /build/requirements.txt",
            "",
        ]
    lines.append("FROM " + base)
    if role != "B":
        lines.append(
            "COPY --from=dependencies /build/site-packages/ "
            "/usr/local/lib/python3.12/site-packages/"
        )
    for name in sorted(data["roles"][role]["assets"]):
        lines.append(
            "COPY --chown=0:0 --chmod=0444 assets/" + name + " /opt/authzest-guest/" + name
        )
    setup = "mkdir -p /opt/authzest-guest"
    directories = "/opt/authzest-guest"
    if role == "T":
        setup += " /input/tests && touch /input/app.py /input/tests/test_generated_ownership.py"
        setup += " && chmod 0444 /input/app.py /input/tests/test_generated_ownership.py"
        directories += " /input /input/tests"
    elif role == "A":
        setup += " /input && touch /input/app.py && chmod 0444 /input/app.py"
        directories += " /input"
    lines += [
        "RUN --network=none " + setup + " && chmod 0555 " + directories,
        "USER 65532:65532",
        "WORKDIR /tmp",
        'ENTRYPOINT ["/usr/local/bin/python","-I","-B","/opt/authzest-guest/'
        + _SCRIPTS[role]
        + '"]',
        "CMD []",
    ]
    return "\n".join(lines) + "\n"


def render_dockerfile(manifest: dict, role: str, platform: str) -> str:
    """Render maintained commands for a minimal future context, never execute."""
    data, _ = _selected(manifest, role, platform)
    return _dockerfile(data, role, platform)


def _recipe(data: dict, role: str, platform: str) -> str:
    names = data["roles"][role]["platforms"][platform]["packages"]
    domain = {
        "schema_version": "1.0",
        "kind": "generated-repair-image-recipe",
        "role": role,
        "platform": platform,
        "base_manifest_sha256": data["base"]["platforms"][platform]["manifest_sha256"],
        "python_version": data["python_version"],
        "requirements_sha256": sha256(_lock(data, role, platform).encode()).hexdigest(),
        "dockerfile_sha256": sha256(_dockerfile(data, role, platform).encode()).hexdigest(),
        "assets": data["roles"][role]["assets"],
        "wheels": [
            {
                key: data["packages"][name]["wheels"][platform][key]
                for key in ("filename", "size", "sha256")
            }
            for name in names
        ],
    }
    return sha256(_canonical(domain)).hexdigest()


def recipe_sha256(manifest: dict, role: str, platform: str) -> str:
    """Hash rendered inputs, not caller-supplied derived-hash declarations."""
    data, _ = _selected(manifest, role, platform)
    return _recipe(data, role, platform)


def _identity(value: os.stat_result) -> tuple:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _opened_binding(value: os.stat_result, *, windows: bool | None = None) -> tuple:
    """Compare only cross-method-compatible fields; full drift pins stay intact."""
    if windows is None:
        windows = os.name == "nt"
    if not windows:
        return _identity(value)
    # CPython 3.12 path stat copies birthtime into ctime, whereas fstat exposes
    # ChangeTime. Keep both full per-method identities and compare birthtime
    # across methods: cpython Modules/posixmodule.c win32_xstat and
    # Python/fileutils.c _Py_fstat_noraise / _Py_attribute_data_to_stat.
    birthtime = getattr(value, "st_birthtime_ns", None)
    if type(birthtime) is not int or birthtime < 0:
        _fail("Missing Windows file birthtime binding")
    return _identity(value)[:-1] + (birthtime,)


def _read_regular(root: Path, relative: str, limit: int) -> bytes:
    if type(relative) is not str or any(part in {"", ".", ".."} for part in relative.split("/")):
        _fail("Invalid fixed relative path")
    if relative.startswith("/") or "\\" in relative:
        _fail("Invalid fixed relative path")
    current = root
    parents = []
    for part in [None, *relative.split("/")[:-1]]:
        if part is not None:
            current /= part
        observed = current.lstat()
        if not stat.S_ISDIR(observed.st_mode):
            _fail("Input parent is not an ordinary directory")
        parents.append((current, _identity(observed)))
    path = root / relative
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
        _fail("Input is not a bounded single-link regular file")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened_before = os.fstat(descriptor)
        if _opened_binding(opened_before) != _opened_binding(before):
            _fail("Input changed before read")
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(descriptor, min(65_536, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > limit or size != before.st_size:
            _fail("Input changed/exceeded byte bound")
        if _identity(os.fstat(descriptor)) != _identity(opened_before) or _identity(
            path.lstat()
        ) != _identity(before):
            _fail("Input changed during read")
        for parent, identity in parents:
            if _identity(parent.lstat()) != identity:
                _fail("Input parent changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _manifest(root: Path) -> dict:
    return _validate(_decode(_read_regular(root, IMAGES + "/manifest.json", MAX_MANIFEST_BYTES)))


def _base_snapshot(root: Path, filename: str) -> tuple[dict, bytes]:
    raw = _read_regular(root, IMAGES + "/base/" + filename, MAX_MANIFEST_BYTES)
    return _decode(raw), raw


def _descriptor(value: object, raw: bytes, digest: str, media_types: set[str]) -> dict:
    if type(value) is not dict:
        _fail("Invalid base metadata descriptor")
    if (
        type(value.get("size")) is not int
        or value["size"] != len(raw)
        or type(value.get("digest")) is not str
        or value["digest"] != "sha256:" + digest
        or type(value.get("mediaType")) is not str
        or value["mediaType"] not in media_types
        or sha256(raw).hexdigest() != digest
    ):
        _fail("Base metadata descriptor bytes differ")
    return value


def _schema_two(value: dict, media_types: set[str]) -> None:
    if (
        type(value.get("schemaVersion")) is not int
        or value["schemaVersion"] != 2
        or type(value.get("mediaType")) is not str
        or value["mediaType"] not in media_types
    ):
        _fail("Unsupported base metadata media type/schema")


def _check_base_metadata(root: Path, data: dict) -> None:
    """Bind captured registry metadata bytes, without verifying layers/signatures."""
    index, raw_index = _base_snapshot(root, "index.json")
    if sha256(raw_index).hexdigest() != data["base"]["index_sha256"]:
        _fail("Base index byte identity mismatch")
    _schema_two(index, _INDEX_MEDIA_TYPES)
    descriptors = index.get("manifests")
    if type(descriptors) is not list or not 1 <= len(descriptors) <= 128:
        _fail("Invalid bounded base index descriptors")
    for platform in PLATFORMS:
        expected = data["base"]["platforms"][platform]
        selected = []
        for item in descriptors:
            if type(item) is not dict or type(item.get("platform")) is not dict:
                _fail("Invalid base platform descriptor")
            declared = item["platform"]
            os_name = _text(declared.get("os"), 32)
            architecture = _text(declared.get("architecture"), 32)
            variant = _text(declared.get("variant", ""), 32)
            if os_name == "linux" and architecture in {"x86_64", "aarch64"}:
                _fail("Noncanonical base platform architecture")
            if (
                os_name == "linux"
                and architecture == expected["architecture"]
                and variant == expected["variant"]
            ):
                selected.append(item)
        if len(selected) != 1:
            _fail("Missing/ambiguous selected base platform descriptor")
        stem = platform.replace("/", "-")
        child, raw_child = _base_snapshot(root, stem + ".manifest.json")
        descriptor = _descriptor(
            selected[0], raw_child, expected["manifest_sha256"], _MANIFEST_MEDIA_TYPES
        )
        _schema_two(child, _MANIFEST_MEDIA_TYPES)
        if child["mediaType"] != descriptor["mediaType"]:
            _fail("Base child media type differs from descriptor")
        config, raw_config = _base_snapshot(root, stem + ".config.json")
        _descriptor(child.get("config"), raw_config, expected["config_sha256"], _CONFIG_MEDIA_TYPES)
        if (
            config.get("os") != expected["os"]
            or config.get("architecture") != expected["architecture"]
        ):
            _fail("Base config platform differs from declaration")
        settings = config.get("config")
        if type(settings) is not dict:
            _fail("Missing base config settings")
        environment = settings.get("Env")
        if type(environment) is not list or len(environment) > 128:
            _fail("Invalid bounded base environment metadata")
        for variable in environment:
            _text(variable)
        python = [variable for variable in environment if variable.startswith("PYTHON_VERSION=")]
        if python != ["PYTHON_VERSION=" + data["python_version"]]:
            _fail("Base config Python patch differs from declaration")


def check_image_inputs(root: Path) -> dict:
    """Observe bounded source/recipe bytes; upstream wheel metadata is declared."""
    root = Path(root)
    manifest_raw = _read_regular(root, IMAGES + "/manifest.json", MAX_MANIFEST_BYTES)
    data = _validate(_decode(manifest_raw))
    manifest_digest = sha256(manifest_raw).hexdigest()
    _check_base_metadata(root, data)
    for name, relative in _ASSET_PATHS.items():
        expected = next(
            expected_assets(role)[name] for role in ROLES if name in expected_assets(role)
        )
        if sha256(_read_regular(root, relative, 65_536)).hexdigest() != expected:
            _fail("Maintained guest source bytes drifted")
    results = []
    for role in ROLES:
        for platform in PLATFORMS:
            entry = data["roles"][role]["platforms"][platform]
            for field, digest_field, rendered in (
                ("requirements_file", "requirements_sha256", _lock(data, role, platform)),
                ("dockerfile", "dockerfile_sha256", _dockerfile(data, role, platform)),
            ):
                raw = _read_regular(root, IMAGES + "/" + entry[field], 65_536)
                if (
                    raw != rendered.encode("utf-8")
                    or sha256(raw).hexdigest() != entry[digest_field]
                ):
                    _fail("Image input bytes/rendered digest mismatch")
            if entry["recipe_sha256"] != _recipe(data, role, platform):
                _fail("Recipe identity mismatch")
            results.append(
                {"role": role, "platform": platform, "recipe_sha256": entry["recipe_sha256"]}
            )
    if (
        sha256(_read_regular(root, IMAGES + "/manifest.json", MAX_MANIFEST_BYTES)).hexdigest()
        != manifest_digest
    ):
        _fail("Manifest changed during check")
    return {
        "schema_version": "1.0",
        "kind": "generated-repair-image-input-check",
        "status": "candidate-inputs-checked-not-built",
        "manifest_sha256": manifest_digest,
        "recipes": results,
        "source_bytes_verified": True,
        "base_metadata_bytes_verified": True,
        "wheel_bytes_verified": False,
        "dependency_metadata_provenance": "manifest-declared-unverified",
        "image_ids": None,
        "contents_verified": False,
        "runtime_ready": False,
        "runtime_invoked": False,
        "execution_authorized": False,
    }


def _zip_directory(raw: bytes) -> None:
    """Bound the actual central records before zipfile's eager allocations.

    A small ordinary EOCD count does not constrain ZipFile, and a ZIP64 locator
    can replace that EOCD's values. This slice accepts neither ZIP64 nor a
    concatenated/prefixed archive; it walks only the declared central directory.
    """
    end = raw.rfind(b"PK\x05\x06", max(0, len(raw) - 65_557))
    if end < 0 or end + 22 > len(raw):
        _fail("Missing bounded ZIP end record")
    (
        _,
        disk,
        directory_disk,
        disk_count,
        count,
        directory_size,
        directory_offset,
        comment,
    ) = struct.unpack("<4s4H2IH", raw[end : end + 22])
    if (
        disk != 0
        or directory_disk != 0
        or disk_count != count
        or disk_count == 0xFFFF
        or count == 0xFFFF
        or count > 4096
        or directory_size == 0xFFFFFFFF
        or directory_offset == 0xFFFFFFFF
        or directory_size > 2_097_152
        or directory_offset + directory_size != end
        or end + 22 + comment != len(raw)
        or (end >= 20 and raw[end - 20 : end - 16] == b"PK\x06\x07")
    ):
        _fail("Unsupported/oversized wheel ZIP directory")
    cursor, actual_count, local_offsets = directory_offset, 0, set()
    while cursor < end:
        if actual_count >= 4096 or cursor + 46 > end:
            _fail("Wheel central directory record bound exceeded")
        header = struct.unpack("<4s6H3I5H2I", raw[cursor : cursor + 46])
        filename_size, extra_size, comment_size = header[10:13]
        next_record = cursor + 46 + filename_size + extra_size + comment_size
        local_offset = header[16]
        if (
            header[0] != b"PK\x01\x02"
            or not 0 < filename_size <= 1024
            or next_record > end
            or header[13] != 0
            or header[8] == 0xFFFFFFFF
            or header[9] == 0xFFFFFFFF
            or local_offset == 0xFFFFFFFF
            or local_offset in local_offsets
            or local_offset + 30 > directory_offset
            or raw[local_offset : local_offset + 4] != b"PK\x03\x04"
        ):
            _fail("Unsupported/invalid wheel central directory record")
        extra_cursor = cursor + 46 + filename_size
        extra_end = extra_cursor + extra_size
        while extra_cursor < extra_end:
            if extra_cursor + 4 > extra_end:
                _fail("Truncated wheel central extra field")
            field_id, field_size = struct.unpack("<2H", raw[extra_cursor : extra_cursor + 4])
            extra_cursor += 4 + field_size
            if field_id == 1 or extra_cursor > extra_end:
                _fail("ZIP64/invalid wheel central extra field")
        local_offsets.add(local_offset)
        actual_count += 1
        cursor = next_record
    if cursor != end or actual_count != count or (local_offsets and min(local_offsets) != 0):
        _fail("Wheel central directory count/extent differs from EOCD")


def _metadata(raw: bytes, expected: dict, name: str, version: str, tags: set) -> None:
    _zip_directory(raw)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 4096:
                _fail("Wheel ZIP entry bound exceeded")
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                _fail("Duplicate wheel ZIP member")
            expanded = 0
            for entry in entries:
                parts = entry.filename.rstrip("/").split("/")
                mode = entry.external_attr >> 16
                expanded += entry.file_size
                if (
                    len(entry.filename) > 1024
                    or entry.filename.startswith("/")
                    or "\\" in entry.filename
                    or any(part in {"", ".", ".."} for part in parts)
                    or entry.flag_bits & 1
                    or stat.S_ISLNK(mode)
                    or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or expanded > 536_870_912
                ):
                    _fail("Unsafe/bounded wheel ZIP member")
            metadata = [
                entry
                for entry in entries
                if re.fullmatch(r"[^/]+\.dist-info/METADATA", entry.filename)
            ]
            wheel = [
                entry
                for entry in entries
                if re.fullmatch(r"[^/]+\.dist-info/WHEEL", entry.filename)
            ]
            if (
                len(metadata) != 1
                or len(wheel) != 1
                or metadata[0].filename.rsplit("/", 1)[0] != wheel[0].filename.rsplit("/", 1)[0]
            ):
                _fail("Ambiguous wheel metadata")
            parsed = []
            for entry in [metadata[0], wheel[0]]:
                mode = entry.external_attr >> 16
                if (
                    entry.flag_bits & 1
                    or stat.S_ISLNK(mode)
                    or entry.file_size > MAX_METADATA_BYTES
                ):
                    _fail("Unsafe/oversized wheel metadata")
                with archive.open(entry) as stream:
                    payload = stream.read(MAX_METADATA_BYTES + 1)
                if len(payload) > MAX_METADATA_BYTES or len(payload) != entry.file_size:
                    _fail("Wheel metadata byte bound exceeded")
                payload.decode("utf-8")
                message = BytesParser(policy=email.policy.default).parsebytes(payload)
                if message.defects:
                    _fail("Malformed wheel metadata headers")
                parsed.append(message)
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, NotImplementedError) as exc:
        raise ImageInputsError("Invalid inert wheel ZIP") from exc
    info, wheel_info = parsed
    for field, value in (
        ("Name", name),
        ("Version", version),
        ("Requires-Python", expected["requires_python"]),
    ):
        actual = info.get_all(field, [])
        if len(actual) != 1:
            _fail("Missing/duplicate wheel metadata field")
        observed = canonicalize_name(str(actual[0])) if field == "Name" else str(actual[0])
        if observed != value:
            _fail("Wheel metadata differs from manifest")
    if sorted(str(item) for item in info.get_all("Requires-Dist", [])) != sorted(
        expected["requires_dist"]
    ):
        _fail("Wheel dependency metadata differs from manifest")
    actual_tags = wheel_info.get_all("Tag", [])
    if not actual_tags or set(map(str, actual_tags)) != {str(tag) for tag in tags}:
        _fail("WHEEL tags differ from filename")
    if len(wheel_info.get_all("Wheel-Version", [])) != 1 or wheel_info["Wheel-Version"] != "1.0":
        _fail("Unsupported WHEEL metadata version")


def verify_wheelhouse(root: Path, wheelhouse: Path, role: str, platform: str) -> dict:
    """Read an exact existing wheel set and inert ZIP metadata, never import it."""
    checked = check_image_inputs(root)
    manifest_raw = _read_regular(Path(root), IMAGES + "/manifest.json", MAX_MANIFEST_BYTES)
    if sha256(manifest_raw).hexdigest() != checked["manifest_sha256"]:
        _fail("Manifest changed before wheel verification")
    data, entry = _selected(_validate(_decode(manifest_raw)), role, platform)
    wheelhouse = Path(wheelhouse)
    before = wheelhouse.lstat()
    if not stat.S_ISDIR(before.st_mode):
        _fail("Wheelhouse must be an ordinary directory")
    selected = [data["packages"][name]["wheels"][platform] for name in entry["packages"]]
    expected_names = {item["filename"] for item in selected}
    with os.scandir(wheelhouse) as iterator:
        observed_names = set()
        for item in iterator:
            if len(observed_names) >= len(expected_names) or item.name not in expected_names:
                _fail("Unexpected wheelhouse entry")
            observed_names.add(item.name)
    if observed_names != expected_names:
        _fail("Missing wheelhouse entry")
    for name in entry["packages"]:
        package = data["packages"][name]
        wheel = package["wheels"][platform]
        raw = _read_regular(wheelhouse, wheel["filename"], MAX_WHEEL_BYTES)
        if len(raw) != wheel["size"] or sha256(raw).hexdigest() != wheel["sha256"]:
            _fail("Wheel byte identity mismatch")
        _, _, _, tags = parse_wheel_filename(wheel["filename"])
        _metadata(raw, wheel, name, package["version"], tags)
    if _identity(wheelhouse.lstat()) != _identity(before):
        _fail("Wheelhouse changed during verification")
    if _manifest(Path(root)) != data:
        _fail("Manifest changed during wheel verification")
    return {
        **checked,
        "kind": "generated-repair-wheelhouse-check",
        "role": role,
        "platform": platform,
        "wheel_bytes_verified": True,
        "wheel_count": len(selected),
        "dependency_metadata_provenance": "observed-inert-wheel-zip",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check local candidate input files (default)"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = check_image_inputs(args.root)
    except (ImageInputsError, OSError) as exc:
        parser.exit(1, "Image input check failed: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
