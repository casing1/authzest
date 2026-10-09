"""Fixed stdlib-only owner-policy worker; supplied JSON is data, never code.

This is a trusted internal execution primitive, not an authenticated approval
barrier. The coordinator owns fresh exact-plan approval and attempt consumption.
No frozen or hidden CLI entry point is provided in this initial source-only slice.
"""

from hashlib import sha256

from authzest.codex.owner_policy_review import OWNER_POLICY_SOURCE

CHECK_ID = "owned-owner-policy-check-v1"
MAX_INPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 16 * 1024

# Only this maintained constant is compiled. Caller input never supplies source,
# module names, filenames, imports, commands, paths, or executable expressions.
WORKER_SOURCE = r"""
import hashlib
import json
import re
import sys
import types

CHECK_ID = "owned-owner-policy-check-v1"
MAX_INPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 16 * 1024
MAX_DEPTH = 32
MAX_NODES = 8192
POLICY_SOURCE = __POLICY_SOURCE_LITERAL__
POLICY_SHA256 = hashlib.sha256(POLICY_SOURCE.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


def _number(_):
    # This protocol has no numeric fields. Reject numbers before converting them.
    raise ValueError("Unexpected number")


def _decode(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Invalid input size")
    text = raw.decode("utf-8")
    # Bound parser nesting before json.loads, without interpreting string data.
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
            item.encode("utf-8")  # Reject JSON escapes containing lone surrogates.
            if any(ord(char) < 32 and char not in "\t\n\r" for char in item):
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
    # Match the existing case contract: null/empty/blank are denial inputs;
    # identifiers are never normalized and U+0000 through U+001F are forbidden.
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
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise ValueError("Invalid scope control")


def _validate(payload):
    _object(
        payload,
        {
            "schema_version", "check_id", "plan_id", "policy_source_sha256",
            "worker_sha256", "input_sha256", "cases",
        },
    )
    if payload["schema_version"] != "1.0" or payload["check_id"] != CHECK_ID:
        raise ValueError("Invalid protocol identity")
    if type(payload["plan_id"]) is not str or re.fullmatch(
        r"owner-policy-check-[a-f0-9]{64}", payload["plan_id"]
    ) is None:
        raise ValueError("Invalid plan identity")
    if payload["policy_source_sha256"] != POLICY_SHA256:
        raise ValueError("Unexpected policy identity")
    _digest(payload["worker_sha256"])
    _digest(payload["input_sha256"])
    cases = payload["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= 16:
        raise ValueError("Invalid case count")
    identifiers = set()
    for case in cases:
        _object(case, {"id", "case_sha256", "principal", "report"})
        case_id = case["id"]
        if type(case_id) is not str or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", case_id
        ) is None or case_id in identifiers:
            raise ValueError("Invalid or repeated case identity")
        identifiers.add(case_id)
        # Original-case hashes are coordinator-bound metadata: the stripped
        # transport cannot reconstruct model reasons, labels or evidence.
        _digest(case["case_sha256"])
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
    if hashlib.sha256(_canonical(cases).encode("utf-8")).hexdigest() != payload["input_sha256"]:
        raise ValueError("Input identity mismatch")
    return cases


def _observe(cases):
    # Registration is required by dataclasses with slots. The module name and
    # compilation label are fixed trusted text; neither comes from the request.
    name = "_authzest_owned_owner_policy"
    if name in sys.modules:
        raise ValueError("Unexpected policy module")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(POLICY_SOURCE, "<authzest-owned-policy>", "exec"), module.__dict__)
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
            observations.append(
                {"id": case["id"], "case_sha256": case["case_sha256"], "observed": observed}
            )
        return observations
    finally:
        if sys.modules.get(name) is module:
            del sys.modules[name]


def main():
    try:
        payload = _decode(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        cases = _validate(payload)  # Reject every malformed case before compiling.
        observations = _observe(cases)
        result = {key: payload[key] for key in (
            "schema_version", "check_id", "plan_id", "policy_source_sha256",
            "worker_sha256", "input_sha256",
        )}
        # worker_sha256 is a coordinator-supplied identity echo, not executable
        # attestation. Observations are not authentication or endpoint evidence.
        result["cases"] = observations
        raw = (_canonical(result) + "\n").encode("utf-8")
        if len(raw) > MAX_OUTPUT_BYTES:
            raise ValueError("Output limit")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        # Never fabricate denial observations. A partial I/O failure is nonzero,
        # so the coordinator must reject that stream instead of claiming success.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
""".lstrip().replace("__POLICY_SOURCE_LITERAL__", repr(OWNER_POLICY_SOURCE))

WORKER_SHA256 = sha256(WORKER_SOURCE.encode("utf-8")).hexdigest()


def main() -> int:
    """Run the fixed trusted worker, never treating supplied JSON as executable text."""
    namespace = {"__name__": "authzest_fixed_owner_policy_worker"}
    exec(compile(WORKER_SOURCE, "<authzest-fixed-owner-policy-worker>", "exec"), namespace)
    return namespace["main"]()
