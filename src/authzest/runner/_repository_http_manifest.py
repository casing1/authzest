"""Closed single-source HTTP guest metadata; never filesystem or run authority.

Stdlib-only so the same reviewed bytes can be copied into a guest image. Caller
IDs and hashes remain declarations; this module performs no input-file reads.
"""

from __future__ import annotations

import hashlib
import json
import keyword
import re

MAX_MANIFEST_BYTES = 16_384
MAX_FILE_BYTES = 16_384
PROJECT_ROOT = "/input/project"
MANIFEST_PATH = "/input/manifest.json"
_FIELDS = {"schema_version", "kind", "request_id", "http_interface", "source", "manifest_id"}
_INTERFACE_FIELDS = {
    "schema_version",
    "entry_source",
    "import_root",
    "module",
    "app_attribute",
    "lifespan",
    "auth_overrides",
    "interface_id",
}


def _fail():
    raise ValueError("repository-http-guest-manifest")


def _canonical(value):
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (ValueError, TypeError, RecursionError):
        _fail()


def _identity(value):
    try:
        return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()
    except UnicodeError:
        _fail()


def _object(value, fields):
    if (
        type(value) is not dict
        or len(value) != len(fields)
        or any(type(key) is not str for key in value)
        or set(value) != fields
    ):
        _fail()
    return value


def _digest(value):
    return (
        type(value) is str and len(value) == 64 and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _id(value, prefix):
    return (
        type(value) is str
        and len(value) == len(prefix) + 64
        and value.startswith(prefix)
        and _digest(value[len(prefix) :])
    )


def _identifier(value):
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value) is not None
        and not keyword.iskeyword(value)
    )


def _source(value):
    item = _object(value, {"path", "sha256", "size_bytes"})
    path = item["path"]
    if (
        type(path) is not str
        or not 4 <= len(path) <= 131
        or not path.endswith(".py")
        or not _identifier(path.removesuffix(".py"))
        or path == "__init__.py"
        or not _digest(item["sha256"])
        or type(item["size_bytes"]) is not int
        or not 1 <= item["size_bytes"] <= MAX_FILE_BYTES
    ):
        _fail()
    return dict(item)


def _interface(value, path):
    item = _object(value, _INTERFACE_FIELDS)
    if (
        item["schema_version"] != "1.0"
        or item["entry_source"] != path
        or item["import_root"] != "."
        or item["module"] != path.removesuffix(".py")
        or not _identifier(item["app_attribute"])
        or item["lifespan"] != "off"
        or item["auth_overrides"] != "none"
    ):
        _fail()
    body = {key: val for key, val in item.items() if key != "interface_id"}
    if item["interface_id"] != "repository-http-interface-" + _identity(body):
        _fail()
    return dict(item)


def _checked_body(item):
    if (
        item["schema_version"] != "2.0"
        or item["kind"] != "repository-http-guest-input"
        or not _id(item["request_id"], "repository-http-proposal-request-")
    ):
        _fail()
    source = _source(item["source"])
    interface = _interface(item["http_interface"], source["path"])
    return {
        "schema_version": "2.0",
        "kind": "repository-http-guest-input",
        "request_id": item["request_id"],
        "http_interface": interface,
        "source": source,
    }


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def validate_guest_manifest(raw_or_dict):
    """Detach strict canonical metadata without resolving or opening any named file."""
    value = raw_or_dict
    if type(value) is bytes:
        if len(value) > MAX_MANIFEST_BYTES:
            _fail()
        try:
            value = value.decode("utf-8")
        except UnicodeError:
            _fail()
    if type(value) is str:
        if len(value) > MAX_MANIFEST_BYTES:
            _fail()
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
    if not _id(item["manifest_id"], "repository-http-guest-input-"):
        _fail()
    body = _checked_body(item)
    rebuilt = {**body, "manifest_id": "repository-http-guest-input-" + _identity(body)}
    if item["manifest_id"] != rebuilt["manifest_id"]:
        _fail()
    try:
        if (
            _canonical(item) != _canonical(rebuilt)
            or len(_canonical(rebuilt).encode("utf-8")) > MAX_MANIFEST_BYTES
        ):
            _fail()
    except UnicodeError:
        _fail()
    # Decode the already bounded rebuilt text to avoid returning caller containers.
    return json.loads(_canonical(rebuilt))


def build_guest_manifest(request_id, http_interface, source):
    """Construct metadata only; freshness, review and live staging stay separate."""
    body = _checked_body(
        {
            "schema_version": "2.0",
            "kind": "repository-http-guest-input",
            "request_id": request_id,
            "http_interface": http_interface,
            "source": source,
        }
    )
    return validate_guest_manifest(
        {**body, "manifest_id": "repository-http-guest-input-" + _identity(body)}
    )


def expected_input_paths(manifest):
    checked = validate_guest_manifest(manifest)
    return MANIFEST_PATH, PROJECT_ROOT + "/" + checked["source"]["path"]
