"""Closed source-only guest inputs; the same maintained file is a guest asset.

This module uses only the standard library. Parsing a manifest neither reads its
named files nor imports an application or grants execution authority.
"""

from __future__ import annotations

import hashlib
import json
import keyword
import re
import unicodedata

MAX_MANIFEST_BYTES = 16_384
MAX_FILE_BYTES = 16_384
MAX_SOURCE_BYTES = 65_536
PROJECT_ROOT = "/input/project"
MANIFEST_PATH = "/input/manifest.json"
TEST_PATH = "tests/test_authzest_regression.py"
_FIELDS = {
    "schema_version",
    "kind",
    "request_id",
    "interface_id",
    "test_interface",
    "source_files",
    "test",
    "manifest_id",
}
_INTERFACE_FIELDS = {
    "schema_version",
    "entry_source",
    "import_root",
    "module",
    "app_attribute",
    "fixture",
    "lifespan",
    "auth_overrides",
    "interface_id",
}


def _fail() -> None:
    raise ValueError("repository-guest-manifest")


def _canonical(value) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (ValueError, TypeError, RecursionError):
        _fail()


def _identity(value) -> str:
    try:
        return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()
    except UnicodeError:
        _fail()


def _object(value, fields):
    if type(value) is not dict or set(value) != fields:
        _fail()
    return value


def _digest(value) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _id(value, prefix) -> bool:
    return type(value) is str and value.startswith(prefix) and _digest(value[len(prefix) :])


def _identifier(value) -> bool:
    return (
        type(value) is str
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value) is not None
        and not keyword.iskeyword(value)
    )


def _key(value):
    return unicodedata.normalize("NFD", unicodedata.normalize("NFD", value).casefold())


def _path(value) -> str:
    if type(value) is not str:
        _fail()
    parts = value.split("/")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        _fail()
    if (
        not 1 <= size <= 512
        or len(parts) > 16
        or not value.endswith(".py")
        or any(not part or part.startswith(".") for part in parts)
        or any(unicodedata.category(char).startswith("C") for char in value)
        or "\\" in value
        or ":" in value
    ):
        _fail()
    return value


def _file(value, *, test=False):
    item = _object(value, {"path", "sha256", "size_bytes"})
    path = _path(item["path"])
    if (
        not _digest(item["sha256"])
        or type(item["size_bytes"]) is not int
        or not (1 if test else 0) <= item["size_bytes"] <= MAX_FILE_BYTES
        or test
        and path != TEST_PATH
    ):
        _fail()
    return dict(item)


def _interface(value, paths):
    item = _object(value, _INTERFACE_FIELDS)
    if (
        item["schema_version"] != "1.0"
        or item["fixture"] != "client"
        or item["lifespan"] != "off"
        or item["auth_overrides"] != "none"
        or type(item["import_root"]) is not str
        or item["import_root"] not in {".", "src"}
        or type(item["entry_source"]) is not str
        or item["entry_source"] not in paths
        or not _identifier(item["app_attribute"])
    ):
        _fail()
    root = item["import_root"]
    if root == "src" and any(not path.startswith("src/") for path in paths):
        _fail()
    modules = {}
    for path in paths:
        relative = path.removeprefix("src/") if root == "src" else path
        parts = relative.removesuffix(".py").split("/")
        package = parts[-1] == "__init__"
        names = parts[:-1] if package else parts
        if names:
            key = tuple(_key(part) for part in names)
            if key in modules:
                _fail()
            modules[key] = package
    for key, package in modules.items():
        if not package and any(other != key and other[: len(key)] == key for other in modules):
            _fail()
    relative = item["entry_source"].removeprefix("src/") if root == "src" else item["entry_source"]
    parts = relative.removesuffix(".py").split("/")
    package = parts[-1] == "__init__"
    names = parts[:-1] if package else parts
    if (
        not names
        or not all(_identifier(name) for name in names)
        or type(item["module"]) is not str
        or item["module"] != ".".join(names)
    ):
        _fail()
    prefix = "src/" if root == "src" else ""
    for depth in range(1, len(names) + (1 if package else 0)):
        if prefix + "/".join(names[:depth]) + "/__init__.py" not in paths:
            _fail()
    body = {key: value for key, value in item.items() if key != "interface_id"}
    if item["interface_id"] != "repository-test-interface-" + _identity(body):
        _fail()
    return dict(item)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def validate_guest_manifest(raw_or_dict, role) -> dict:
    """Rebuild a bounded manifest without trusting IDs or resolving file names."""
    if type(role) is not str or role not in {"T", "A"}:
        _fail()
    value = raw_or_dict
    if type(value) is bytes:
        if len(value) > MAX_MANIFEST_BYTES:
            _fail()
        try:
            value = value.decode("utf-8")
        except UnicodeError:
            _fail()
    if type(value) is str:
        try:
            if len(value.encode("utf-8")) > MAX_MANIFEST_BYTES:
                _fail()
            decoded = json.loads(value, object_pairs_hook=_pairs, parse_constant=lambda _: _fail())
            if value != _canonical(decoded):
                _fail()
            value = decoded
        except (ValueError, UnicodeError, RecursionError, TypeError):
            _fail()
    item = _object(value, _FIELDS)
    body = _checked_body(item, role)
    rebuilt = {**body, "manifest_id": "repository-guest-input-" + _identity(body)}
    try:
        if (
            _canonical(item) != _canonical(rebuilt)
            or len(_canonical(rebuilt).encode("utf-8")) > MAX_MANIFEST_BYTES
        ):
            _fail()
    except UnicodeError:
        _fail()
    return rebuilt


def _checked_body(item, role):
    if type(role) is not str or role not in {"T", "A"}:
        _fail()
    if (
        item["schema_version"] != "1.0"
        or item["kind"] != "repository-guest-input"
        or not _id(item["request_id"], "repository-test-proposal-request-")
        or type(item["source_files"]) is not list
        or not 1 <= len(item["source_files"]) <= 5
    ):
        _fail()
    files = [_file(file) for file in item["source_files"]]
    paths = [file["path"] for file in files]
    keys = [tuple(_key(part) for part in path.split("/")) for path in paths]
    if (
        sum(file["size_bytes"] for file in files) > MAX_SOURCE_BYTES
        or len(set(keys)) != len(keys)
        or any(left != right and right[: len(left)] == left for left in keys for right in keys)
    ):
        _fail()
    interface = _interface(item["test_interface"], paths)
    if item["interface_id"] != interface["interface_id"]:
        _fail()
    test = _file(item["test"], test=True) if role == "T" else None
    if role == "A" and item["test"] is not None:
        _fail()
    return {
        "schema_version": "1.0",
        "kind": "repository-guest-input",
        "request_id": item["request_id"],
        "interface_id": interface["interface_id"],
        "test_interface": interface,
        "source_files": files,
        "test": test,
    }


def build_guest_manifest(request_id, test_interface, source_files, test, *, role) -> dict:
    """Construct a data manifest; caller-owned current-input checks stay separate."""
    body = {
        "schema_version": "1.0",
        "kind": "repository-guest-input",
        "request_id": request_id,
        "interface_id": test_interface.get("interface_id")
        if type(test_interface) is dict
        else None,
        "test_interface": test_interface,
        "source_files": source_files,
        "test": test,
    }
    checked = _checked_body(body, role)
    return validate_guest_manifest(
        {**checked, "manifest_id": "repository-guest-input-" + _identity(checked)}, role
    )


def expected_input_paths(manifest, role) -> tuple[str, ...]:
    """Exact per-file bind targets; directory, policy and record mounts are absent."""
    checked = validate_guest_manifest(manifest, role)
    paths = [
        MANIFEST_PATH,
        *(PROJECT_ROOT + "/" + file["path"] for file in checked["source_files"]),
    ]
    if role == "T":
        paths.append("/input/" + TEST_PATH)
    return tuple(paths)
