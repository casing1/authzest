"""Captured owned-file worker source; constructing this module never runs it.

Registered constants validate the received file snapshot; only that received text
is compiled in the isolated child. No path, arbitrary source or expected labels are
accepted. The coordinator owns file reads, consent and lifecycle checks. Echoed
worker/file identities are host-bound metadata, not self-attestation.
"""

from authzest.codex.contracts import identity
from authzest.codex.owner_policy_repair_pair import (
    build_owner_policy_repair_pair,
    validate_owner_policy_repair_pair,
)

CHECK_ID = "owned-owner-file-repair-check-v1"
MAX_INPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 16 * 1024

_WORKER_TEMPLATE = r"""
import hashlib
import json
import re
import sys
import types

CHECK_ID = "owned-owner-file-repair-check-v1"
MAX_INPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 16 * 1024
MAX_DEPTH = 32
MAX_NODES = 8192
POLICY_SOURCES = __POLICY_SOURCES_LITERAL__
POLICY_SHA256 = __POLICY_SHA256_LITERAL__
REGISTERED_INPUT_ROWS = __INPUT_ROWS_LITERAL__
REGISTERED_INPUT_SHA256 = __INPUT_SHA256_LITERAL__


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _identity(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


def _number(_):
    # No numeric fields exist in this protocol, including identity metadata.
    raise ValueError("Unexpected number")


def _decode(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Invalid input size")
    text = raw.decode("utf-8")
    depth = 0
    quoted = False
    escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("Nesting limit")
        elif character in "]}":
            depth -= 1
            if depth < 0:
                raise ValueError("Invalid nesting")
    if depth or quoted:
        raise ValueError("Incomplete JSON")
    value = json.loads(
        text,
        object_pairs_hook=_pairs,
        parse_int=_number,
        parse_float=_number,
        parse_constant=_number,
    )
    pending = [(value, 0)]
    visited = 0
    while pending:
        item, item_depth = pending.pop()
        visited += 1
        if item_depth > MAX_DEPTH or visited > MAX_NODES:
            raise ValueError("Structural limit")
        if type(item) is dict:
            pending.extend((key, item_depth + 1) for key in item)
            pending.extend((child, item_depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, item_depth + 1) for child in item)
        elif type(item) is str:
            item.encode("utf-8")
            if any(ord(char) < 32 and char not in "\n\t\r" for char in item):
                raise ValueError("Invalid control character")
        elif item is not None and type(item) is not bool:
            raise ValueError("Unexpected JSON value")
    return value


def _object(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError("Unexpected fields")


def _digest(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("Invalid digest")


def _identifier(value):
    if value is None:
        return
    if type(value) is not str or len(value) > 128:
        raise ValueError("Invalid identifier")
    value.encode("utf-8")
    if any(ord(char) < 32 for char in value):
        raise ValueError("Invalid identifier control")


def _scope(value):
    if type(value) is not str or len(value) > 128 or not value.strip():
        raise ValueError("Invalid scope")
    value.encode("utf-8")
    if any(ord(char) < 32 for char in value):
        raise ValueError("Invalid scope control")


def _validate(payload):
    _object(payload, {
        "schema_version", "check_id", "plan_id", "session_id", "stage", "candidate",
        "file_state_sha256", "policy_source_sha256", "source_text",
        "worker_sha256", "input_sha256", "cases",
    })
    if payload["schema_version"] != "1.0" or payload["check_id"] != CHECK_ID:
        raise ValueError("Invalid protocol identity")
    if type(payload["plan_id"]) is not str or re.fullmatch(
        r"owner-file-check-[a-f0-9]{64}", payload["plan_id"]
    ) is None:
        raise ValueError("Invalid plan identity")
    if type(payload["session_id"]) is not str or re.fullmatch(
        r"[a-f0-9]{32}", payload["session_id"]
    ) is None:
        raise ValueError("Invalid session identity")
    _digest(payload["file_state_sha256"])
    candidate = payload["candidate"]
    if type(candidate) is not str or candidate not in {"before", "after"}:
        raise ValueError("Invalid candidate")
    if type(payload["stage"]) is not str or payload["stage"] != candidate + "-check":
        raise ValueError("Invalid check stage")
    source_text = payload["source_text"]
    if type(source_text) is not str or not source_text:
        raise ValueError("Invalid captured source")
    source_bytes = source_text.encode("utf-8")
    if len(source_bytes) > 32768 or source_text != POLICY_SOURCES[candidate]:
        raise ValueError("Unregistered captured source")
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != POLICY_SHA256[candidate] or payload["policy_source_sha256"] != source_hash:
        raise ValueError("Unexpected policy identity")
    # The worker cannot embed its own digest; this is an explicitly host-bound
    # identity echo. The coordinator must verify the actual launched bytes.
    _digest(payload["worker_sha256"])
    _digest(payload["input_sha256"])
    cases = payload["cases"]
    if type(cases) is not list or len(cases) != 8:
        raise ValueError("Invalid case count")
    identifiers = set()
    for case in cases:
        _object(case, {"case_id", "input_sha256", "principal", "report"})
        case_id = case["case_id"]
        if type(case_id) is not str or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", case_id
        ) is None or case_id in identifiers:
            raise ValueError("Invalid or repeated case identity")
        identifiers.add(case_id)
        _digest(case["input_sha256"])
        principal = case["principal"]
        if principal is not None:
            _object(principal, {"subject", "authenticated", "scopes"})
            _identifier(principal["subject"])
            if type(principal["authenticated"]) is not bool:
                raise ValueError("Invalid authentication input")
            scopes = principal["scopes"]
            if type(scopes) is not list or len(scopes) > 16:
                raise ValueError("Invalid scope count")
            for scope in scopes:
                _scope(scope)
            if len(set(scopes)) != len(scopes):
                raise ValueError("Repeated scope")
        report = case["report"]
        if report is not None:
            _object(report, {"report_id", "owner_id"})
            _identifier(report["report_id"])
            _identifier(report["owner_id"])
        input_row = {key: case[key] for key in ("case_id", "principal", "report")}
        if _identity(input_row) != case["input_sha256"]:
            raise ValueError("Case input identity mismatch")
    # Canonical equality is type-sensitive: Python's True == 1 is insufficient.
    # It also rejects reordered, alternative or rehashed caller-controlled cases.
    if _canonical(cases) != _canonical(REGISTERED_INPUT_ROWS):
        raise ValueError("Unregistered input cases")
    if (
        _identity(cases) != REGISTERED_INPUT_SHA256
        or payload["input_sha256"] != REGISTERED_INPUT_SHA256
    ):
        raise ValueError("Input identity mismatch")
    return cases


def _observe(source_text, cases):
    # This name and compilation label are trusted constants, never request data.
    name = "_authzest_owned_owner_file_policy"
    if name in sys.modules:
        raise ValueError("Unexpected policy module")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(
            compile(source_text, "<authzest-owned-file-policy>", "exec"),
            module.__dict__,
        )
        observations = []
        for case in cases:
            principal = case["principal"]
            if principal is not None:
                principal = module.Principal(
                    subject=principal["subject"],
                    authenticated=principal["authenticated"],
                    scopes=frozenset(principal["scopes"]),
                )
            report = case["report"]
            if report is not None:
                report = module.Report(report_id=report["report_id"], owner_id=report["owner_id"])
            observed = module.can_read_report(principal, report)
            if type(observed) is not bool:
                raise ValueError("Unexpected observation type")
            observations.append({
                "case_id": case["case_id"],
                "input_sha256": case["input_sha256"],
                "observed": observed,
            })
        return observations
    finally:
        if sys.modules.get(name) is module:
            del sys.modules[name]


def main():
    try:
        payload = _decode(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        cases = _validate(payload)
        observations = _observe(payload["source_text"], cases)
        result = {key: payload[key] for key in (
            "schema_version", "check_id", "plan_id", "session_id", "stage", "candidate",
            "file_state_sha256", "policy_source_sha256", "worker_sha256", "input_sha256",
        )}
        result["cases"] = observations
        raw = (_canonical(result) + "\n").encode("utf-8")
        if len(raw) > MAX_OUTPUT_BYTES:
            raise ValueError("Output limit")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        # No stderr, source/traceback leakage or fabricated denial on any failure.
        # A partial output write is nonzero and must be discarded by the host.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _build_worker_source() -> str:
    """Construct inert source text from the exact registration; never evaluate it."""
    pair = validate_owner_policy_repair_pair(build_owner_policy_repair_pair().payload_json)
    content = pair.to_dict()["content"]
    rows = []
    for case in content["cases"]:
        row = {key: case[key] for key in ("case_id", "principal", "report")}
        rows.append({**row, "input_sha256": identity(row)})
    replacements = {
        "__POLICY_SOURCES_LITERAL__": {
            candidate: content[candidate]["text"] for candidate in ("before", "after")
        },
        "__POLICY_SHA256_LITERAL__": {
            candidate: content[candidate]["sha256"] for candidate in ("before", "after")
        },
        "__INPUT_ROWS_LITERAL__": rows,
        "__INPUT_SHA256_LITERAL__": identity(rows),
    }
    source = _WORKER_TEMPLATE.lstrip()
    for marker, value in replacements.items():
        source = source.replace(marker, repr(value))
    return source


WORKER_SOURCE = _build_worker_source()
# This literal is an implementation pin, not a freshly calculated acceptance.
# Changing the template or registered material requires a reviewed new identity.
WORKER_SHA256 = "33413d680ac8e00f514d5897aca2289527cfccfd8a1fccdebb179c774377491d"
