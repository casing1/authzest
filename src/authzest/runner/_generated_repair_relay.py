"""Host-only validation of unverified request-only relay data; no execution gate."""

from __future__ import annotations

import base64
import binascii

from authzest.codex.contracts import ContractError, _object, canonical
from authzest.runner._generated_repair_http import (
    MAX_CAPTURE_BYTES,
    MAX_RECV_CALLS,
    HTTPProfileError,
    HTTPResponseParser,
    fixed_requests,
)
from authzest.runner.generated_repair_controls import (
    GeneratedRepairControls,
    GeneratedRepairControlsComparison,
    _bounded_decode,
    compare_generated_repair_observations,
    validate_generated_repair_controls,
)

_CAPTURE_FIELDS = {
    "schema_version",
    "kind",
    "status",
    "request_count",
    "facts",
    "failure",
    "failed_request_index",
    "wire_bytes",
    "call_count",
    "close_status",
    "close_failure",
    "cancellation",
    "provenance",
    "execution_status",
    "authorization_status",
    "verified_fix",
}


def _invalid() -> ContractError:
    return ContractError("Invalid unverified HTTP relay capture", code="validation-shape")


def compare_generated_repair_relay_capture(
    raw: str, controls: GeneratedRepairControls, *, candidate: str
) -> GeneratedRepairControlsComparison:
    """Validate complete data and compare with host-owned labels, never run code.

    The current host controls must project to the guest's exact request-only
    schedule. Neither guest results nor caller identifiers select oracle values.
    A matching result remains caller-supplied, unauthenticated data; no baseline,
    source-write permission, isolation claim, or runtime authority is created.
    """
    if type(controls) is not GeneratedRepairControls:
        raise _invalid()
    checked = validate_generated_repair_controls(controls.payload_json)
    requests = [row for case in checked.to_dict()["cases"] for row in case["requests"]]
    projection = [
        {
            "request_id": row["request_id"],
            "method": row["method"],
            "path": row["path"],
            "headers": row["headers"],
        }
        for row in requests
    ]
    guest = [
        {
            "request_id": row.request_id,
            "method": "GET",
            "path": row.path,
            "headers": [list(pair) for pair in row.headers],
        }
        for row in fixed_requests()
    ]
    if canonical(projection) != canonical(guest):
        raise ContractError("HTTP request schedule drift", code="validation-identity")
    data = _bounded_decode(raw)
    _object(data, _CAPTURE_FIELDS)
    if (
        data["schema_version"] != "1.0"
        or data["kind"] != "generated-repair-relay-capture"
        or data["status"] != "complete"
        or type(data["request_count"]) is not int
        or data["request_count"] != 21
        or data["failure"] is not None
        or data["failed_request_index"] is not None
        or data["close_status"] != "closed"
        or data["close_failure"] is not None
        or data["cancellation"] is not None
        or data["provenance"] != "caller-supplied-unverified"
        or data["execution_status"] != "not-established"
        or data["authorization_status"] != "unknown"
        or data["verified_fix"] is not False
        or type(data["wire_bytes"]) is not int
        or not 0 < data["wire_bytes"] <= MAX_CAPTURE_BYTES
        or type(data["call_count"]) is not int
        or not 42 <= data["call_count"] <= MAX_RECV_CALLS
        or type(data["facts"]) is not list
        or len(data["facts"]) != 21
    ):
        raise _invalid()
    minimum_wire_bytes = 0
    for fact, request in zip(data["facts"], requests, strict=True):
        _object(fact, {"request_id", "status_code", "headers", "body_base64"})
        if (
            fact["request_id"] != request["request_id"]
            or type(fact["status_code"]) is not int
            or not 200 <= fact["status_code"] <= 599
            or type(fact["headers"]) is not list
            or len(fact["headers"]) > 32
            or type(fact["body_base64"]) is not str
            or len(fact["body_base64"]) > 10_924
        ):
            raise _invalid()
        try:
            body = base64.b64decode(fact["body_base64"], validate=True)
            if base64.b64encode(body).decode("ascii") != fact["body_base64"]:
                raise _invalid()
            headers = []
            for pair in fact["headers"]:
                if (
                    type(pair) is not list
                    or len(pair) != 2
                    or any(type(part) is not str or len(part) > 4096 for part in pair)
                ):
                    raise _invalid()
                headers.append((pair[0] + ": " + pair[1] + "\r\n").encode("ascii"))
            wire = (
                f"HTTP/1.1 {fact['status_code']} \r\n".encode("ascii")
                + b"".join(headers)
                + b"\r\n"
                + body
            )
            parser = HTTPResponseParser(request["request_id"])
            parser.feed(wire)
            if canonical(parser.finish()) != canonical(fact):
                raise _invalid()
        except (HTTPProfileError, UnicodeError, ValueError, binascii.Error) as exc:
            raise _invalid() from exc
        # A valid wire may use no SP after ':'; normalized facts use ': '.
        # Reason phrases and optional whitespace cannot make this lower bound
        # larger than the actual response bytes retained by the guest parser.
        minimum_wire_bytes += (
            len(f"HTTP/1.1 {fact['status_code']} \r\n".encode("ascii"))
            + sum(len(name) + len(value) + 3 for name, value in fact["headers"])
            + 2
            + len(body)
        )
    if minimum_wire_bytes > data["wire_bytes"] or data["call_count"] > data["wire_bytes"] + 21:
        raise _invalid()
    return compare_generated_repair_observations(
        canonical(
            {
                "schema_version": "1.0",
                "kind": "generated-repair-http-facts",
                "controls_id": checked.controls_id,
                "candidate": candidate,
                "facts": data["facts"],
            }
        ),
        checked,
        candidate=candidate,
    )
