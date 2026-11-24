"""Private HTTP-only Engine metadata reads using maintained bounded primitives.

Only version/info/A/B-image GETs are supported. No CLI, subprocess, image
provisioning or guest lifecycle is exposed. Endpoint observations cannot
authenticate a peer or make connect atomic against hostile same-user writers;
synchronous OS calls and close have no universal preemption guarantee.
"""

from __future__ import annotations

import inspect
import os
import socket
import sys
import threading

from authzest.runner._generated_repair_engine_http import (
    MAX_WIRE_BYTES,
    EngineHTTPError,
    EngineResponse,
    WireBudget,
    _budget,
    _Clock,
    _endpoint_identity,
    _Failure,
    _Reader,
    _response,
    _set_timeout,
)
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpRuntimeProfile,
    validate_runtime_profile,
)

_OPERATIONS = ("version", "info", "image-A", "image-B")
_ACTIVE = threading.local()


def read_engine(
    profile: RepositoryHttpRuntimeProfile,
    operation: str,
    *,
    deadline: float,
    budget: WireBudget,
    before_connect=None,
) -> EngineResponse:
    """Read one fixed metadata GET once; nested dispatch is refused."""
    if getattr(_ACTIVE, "running", False):
        raise EngineHTTPError(
            {
                "operation": operation
                if type(operation) is str and operation in _OPERATIONS
                else "invalid",
                "reason": "metadata-query-reentrant",
                "contact_attempted": False,
                "connection_status": "not-attempted",
                "request_status": "not-attempted",
                "socket_acquisition": "not-attempted",
                "socket_cleanup": "not-needed",
                "bytes_received": 0,
                "cleanup_failure": False,
            }
        )
    _ACTIVE.running = True
    try:
        return _read_engine(
            profile, operation, deadline=deadline, budget=budget, before_connect=before_connect
        )
    finally:
        _ACTIVE.running = False


def _read_engine(
    profile: RepositoryHttpRuntimeProfile,
    operation: str,
    *,
    deadline: float,
    budget: WireBudget,
    before_connect=None,
) -> EngineResponse:
    """Read one of four closed metadata paths; never create or start a guest.

    The caller supplies the original setup/phase deadline and current guards.
    Supplied profiles, responses and matching metadata are not execution consent.
    """
    diagnostic = {
        "operation": operation
        if type(operation) is str and operation in _OPERATIONS
        else "invalid",
        "contact_attempted": False,
        "connection_status": "not-attempted",
        "request_status": "not-attempted",
        "socket_acquisition": "not-attempted",
        "socket_cleanup": "not-needed",
        "bytes_received": 0,
    }
    connection = None
    primary = cleanup_failure = None
    response = pin = clock = None
    start_used = 0
    valid_handle = False
    try:
        clock = _Clock(deadline)
        _budget(budget)
        start_used = budget.used
        if start_used == MAX_WIRE_BYTES:
            raise _Failure("wire-budget-exhausted")
        if os.name != "posix" or getattr(sys, "frozen", False) or not hasattr(socket, "AF_UNIX"):
            raise _Failure("unsupported-platform")
        if type(operation) is not str:
            raise _Failure("invalid-runtime-request")
        if type(profile) is not RepositoryHttpRuntimeProfile:
            raise _Failure("invalid-runtime-request")
        checked = validate_runtime_profile(profile.payload_json)
        data = checked.to_dict()
        if operation not in _OPERATIONS:
            raise _Failure("invalid-runtime-request")
        path = data["engine"]["endpoint"][7:]
        target = "/version" if operation == "version" else "/v" + data["engine"]["api_version"]
        if operation == "info":
            target += "/info"
        elif operation.startswith("image-"):
            target += "/images/" + data["images"][operation[-1]]["image_id"] + "/json"

        def current():
            if validate_runtime_profile(profile.payload_json).payload_json != checked.payload_json:
                raise _Failure("runtime-profile-changed")

        if before_connect is not None and (
            not callable(before_connect) or inspect.iscoroutinefunction(before_connect)
        ):
            raise _Failure("invalid-preconnect-hook")
        pin = _endpoint_identity(path)
        clock.remaining()
        if before_connect is not None:
            result = before_connect()
            if result is not None:
                if inspect.iscoroutine(result):
                    result.close()
                raise _Failure("preconnect-hook-not-confirmed")
        clock.remaining()
        current()
        if _endpoint_identity(path) != pin:
            raise _Failure("endpoint-changed-before-connect")
        if budget.used != start_used:
            raise _Failure("wire-budget-changed-before-connect")
        clock.remaining()
        diagnostic["socket_acquisition"] = "attempted-unconfirmed"
        diagnostic["socket_cleanup"] = "unconfirmed"
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if inspect.iscoroutine(connection) or not all(
            callable(getattr(connection, name, None))
            for name in ("settimeout", "connect", "sendall", "recv", "close")
        ):
            raise _Failure("socket-acquisition-unconfirmed")
        valid_handle = True
        diagnostic["socket_acquisition"] = "handle-returned"
        _set_timeout(connection, clock)
        diagnostic["contact_attempted"] = True
        diagnostic["connection_status"] = "attempted-unconfirmed"
        result = connection.connect(path)
        if result is not None:
            if inspect.iscoroutine(result):
                result.close()
            raise _Failure("connect-result-unconfirmed")
        diagnostic["connection_status"] = "connected"
        clock.remaining()
        request = (
            "GET " + target + " HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        _set_timeout(connection, clock)
        diagnostic["request_status"] = "attempted-unconfirmed"
        result = connection.sendall(request)
        if result is not None:
            if inspect.iscoroutine(result):
                result.close()
            raise _Failure("send-result-unconfirmed")
        diagnostic["request_status"] = "sent"
        clock.remaining()
        body = _response(_Reader(connection, clock, budget))
        clock.remaining()
        current()
        response = EngineResponse(operation, body, budget.used - start_used, pin)
    except BaseException as exc:
        primary = exc
    finally:
        if connection is not None:
            try:
                result = connection.close()
                if result is not None:
                    if inspect.iscoroutine(result):
                        result.close()
                    raise _Failure("socket-close-unconfirmed")
                if valid_handle:
                    diagnostic["socket_cleanup"] = "confirmed"
            except BaseException as exc:
                cleanup_failure = exc
                diagnostic["socket_cleanup"] = "unconfirmed"
                if primary is None:
                    primary = exc
                elif not isinstance(exc, Exception) and isinstance(primary, Exception):
                    exc.engine_http_primary_failure = primary
                    primary = exc
        if pin is not None:
            try:
                if _endpoint_identity(path) != pin:
                    raise _Failure("endpoint-changed-after-close")
                clock.remaining()
                current()
            except BaseException as exc:
                if primary is None:
                    primary = exc
                elif not isinstance(exc, Exception) and isinstance(primary, Exception):
                    exc.engine_http_primary_failure = primary
                    primary = exc
        if type(budget) is WireBudget and type(budget.used) is int:
            diagnostic["bytes_received"] = max(0, budget.used - start_used)
    if cleanup_failure is not None:
        if primary is None:
            primary = cleanup_failure
        elif not isinstance(cleanup_failure, Exception) and isinstance(primary, Exception):
            cleanup_failure.engine_http_primary_failure = primary
            primary = cleanup_failure
    if primary is not None:
        diagnostic["reason"] = str(primary) if type(primary) is _Failure else "operation-failed"
        diagnostic["cleanup_failure"] = cleanup_failure is not None
        if not isinstance(primary, Exception):
            primary.engine_http_observation = diagnostic
            raise primary
        raise EngineHTTPError(diagnostic) from primary
    return response
