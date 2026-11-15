"""Private two-query Engine identity bootstrap, never a runnable image profile.

No expected server identity or image IDs are invented. Metadata is unpinned and
unattested, even when two local responses agree. This module has no CLI, image,
guest, executor, session, approval or release integration.
"""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.runner import _generated_repair_engine_http as engine_http
from authzest.runner._generated_repair_engine_http import (
    MAX_WIRE_BYTES,
    EngineResponse,
    WireBudget,
    _bootstrap_endpoint,
    read_engine_bootstrap,
)
from authzest.runner._generated_repair_preflight import (
    _CAPABILITIES,
    _api,
    _diagnostic,
    _invalid,
    _pin,
    _strings,
    _text,
    engine_identity_sha256,
)
from authzest.runner.generated_repair_controls import _bounded_decode

API_VERSION = "1.51"
_OPERATIONS = ("version", "info")
_PENDING = (
    "operator-reviewed-daemon-identity-pin",
    "reviewed-preprovisioned-image-ids-and-dependency-locks",
    "actual-image-guest-assets-and-effective-runtime-enforcement",
    "current-staging-session-decisions-and-installed-runtime-acceptance",
)


class _Unsupported(ValueError):
    pass


class _ClockError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EngineBootstrapObservation:
    """Historical unpinned metadata; construction/import grants no authority."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def observation_id(self) -> str:
        return "generated-repair-engine-bootstrap-observation-" + identity(self.to_dict())


def _projection(frames):
    selected, bodies, pin, wire = {}, [], None, 0
    for index, frame in enumerate(frames):
        if (
            type(frame) is not EngineResponse
            or type(frame.operation) is not str
            or frame.operation != _OPERATIONS[index]
            or type(frame.body) is not bytes
            or not 0 < len(frame.body) <= 65_536
            or type(frame.wire_bytes) is not int
            or not len(frame.body) <= frame.wire_bytes <= MAX_WIRE_BYTES
        ):
            raise _invalid()
        wire += frame.wire_bytes
        if wire > MAX_WIRE_BYTES:
            raise _invalid()
        current_pin = _pin(frame.endpoint_identity)
        if pin is not None and current_pin != pin:
            raise ContractError("Engine endpoint identity changed", code="validation-identity")
        pin = current_pin
        try:
            body = _bounded_decode(frame.body.decode("utf-8", errors="strict"))
        except UnicodeError as exc:
            raise _invalid() from exc
        if frame.operation == "version":
            version = _text(body.get("Version"), 128)
            maximum, minimum = body.get("ApiVersion"), body.get("MinAPIVersion")
            low, high = _api(minimum), _api(maximum)
            if low > high:
                raise _invalid()
            if not low <= _api(API_VERSION) <= high:
                raise _Unsupported("api-version-unsupported")
            operating_system = _text(body.get("Os"), 32)
            architecture = _text(body.get("Arch"), 32)
            if operating_system != "linux" or architecture not in {"amd64", "arm64"}:
                raise _Unsupported("engine-platform-unsupported")
            selected["version"] = {
                "version": version,
                "api_version": maximum,
                "minimum_api_version": minimum,
                "selected_api_version": API_VERSION,
                "os": "linux",
                "architecture": architecture,
            }
        else:
            engine_id = _text(body.get("ID"))
            server_version = _text(body.get("ServerVersion"), 128)
            architecture = {
                "amd64": "amd64",
                "x86_64": "amd64",
                "arm64": "arm64",
                "aarch64": "arm64",
            }.get(_text(body.get("Architecture"), 32))
            if (
                body.get("OSType") != "linux"
                or architecture != selected["version"]["architecture"]
                or server_version != selected["version"]["version"]
            ):
                raise _invalid()
            capabilities = {}
            for name in _CAPABILITIES:
                if name in body:
                    if type(body[name]) is not bool:
                        raise _invalid()
                    capabilities[name] = body[name]
            selected["engine"] = {
                "engine_id": engine_id,
                "observed_identity_sha256": engine_identity_sha256(engine_id),
                "server_version": server_version,
                "os": "linux",
                "architecture": architecture,
                "cgroup_version": _text(body.get("CgroupVersion"), 64),
                "cgroup_driver": _text(body.get("CgroupDriver"), 64),
                "default_runtime": _text(body.get("DefaultRuntime"), 128),
                "security_options": _strings(body.get("SecurityOptions"), maximum=32),
                "reported_capabilities": capabilities,
                "resource_enforcement_established": False,
            }
        bodies.append(
            {
                "operation": frame.operation,
                "body_sha256": sha256(frame.body).hexdigest(),
                "wire_bytes": frame.wire_bytes,
            }
        )
    return {"metadata": selected, "responses": bodies, "endpoint_identity": pin, "wire_bytes": wire}


def _result(
    endpoint, projection, *, reason=None, queries=0, contact=None, wire_used=None, diagnostic=None
):
    value = {
        "schema_version": "1.0",
        "kind": "generated-repair-engine-bootstrap-observation",
        "endpoint": endpoint,
        "selected_api_version": API_VERSION,
        "status": "metadata-observed-unpinned"
        if reason is None
        else (
            "unsupported"
            if reason in {"api-version-unsupported", "engine-platform-unsupported"}
            else "failed"
        ),
        "failure_reason": reason,
        "response_count": len(projection["responses"]),
        "query_attempted": queries,
        "engine_contact_attempted": contact,
        "wire_bytes_used": wire_used,
        "transport_diagnostic": diagnostic,
        **projection,
        "provenance": "caller-supplied-unverified",
        "identity_pinned": False,
        "images_inspected": False,
        "profile_created": False,
        "runtime_invoked": False,
        "generated_runtime_invoked": False,
        "execution_authorized": False,
        "authorization_status": "unknown",
        "verified_fix": False,
        "ready": False,
        "readiness": "not-established",
        "pending": list(_PENDING),
    }
    raw = canonical(value)
    decode(raw)
    return EngineBootstrapObservation(raw)


def normalize_engine_bootstrap(endpoint: str, frames) -> EngineBootstrapObservation:
    """Project two bounded supplied frames, without contacting an endpoint."""
    endpoint = _bootstrap_endpoint(endpoint)
    if type(frames) not in (list, tuple) or len(frames) != 2:
        raise _invalid()
    return _result(endpoint, _projection(frames))


def observe_engine_bootstrap(
    endpoint: str, *, phase_deadline, setup_deadline, before_query=None
) -> EngineBootstrapObservation:
    """Read version then fixed API1.51 info under one original deadline/budget.

    No negotiation, retry or image lookup is performed. The trusted synchronous
    hook is coordination, not consent. Unpinned observations cannot create a
    RuntimeProfile or unlock the disabled executor.
    """
    checked, last, budget, diagnostic = None, None, None, None
    frames, queries, contact = [], 0, False
    projection = {"metadata": {}, "responses": [], "endpoint_identity": None, "wire_bytes": 0}
    stage = "clock-invalid"

    def tick():
        nonlocal last
        value = monotonic()
        if (
            type(value) not in (int, float)
            or not 0 <= value <= 2**48
            or not math.isfinite(value)
            or last is not None
            and value < last
        ):
            if inspect.iscoroutine(value):
                value.close()
            raise _ClockError
        last = float(value)
        return last

    def current():
        if tick() >= deadline:
            raise TimeoutError
        if _bootstrap_endpoint(endpoint) != checked:
            raise _invalid()

    def continuous_endpoint():
        previous = projection["endpoint_identity"]
        if previous is not None and _pin(engine_http._endpoint_identity(checked[7:])) != previous:
            raise ContractError("Engine endpoint identity changed", code="validation-identity")

    try:
        started = tick()
        stage = "deadline-invalid"
        for limit, maximum in ((phase_deadline, 40), (setup_deadline, 10)):
            if (
                type(limit) not in (int, float)
                or not 0 < limit <= 2**48
                or not math.isfinite(limit)
                or not 0 < limit - started <= maximum
            ):
                if inspect.iscoroutine(limit):
                    limit.close()
                raise _invalid()
        deadline = min(phase_deadline, setup_deadline)
        stage = "endpoint-invalid"
        checked = _bootstrap_endpoint(endpoint)
        if before_query is not None and (
            not callable(before_query) or inspect.iscoroutinefunction(before_query)
        ):
            raise _invalid()
        budget = WireBudget()
        for operation in _OPERATIONS:
            stage = "query-precondition-failed"
            current()
            guard_ran = False

            def guard():
                nonlocal guard_ran
                if guard_ran:
                    raise _invalid()
                guard_ran = True
                current()
                continuous_endpoint()
                current()
                if before_query is not None:
                    answer = before_query()
                    if answer is not None:
                        if inspect.iscoroutine(answer):
                            answer.close()
                        raise _invalid()
                current()
                continuous_endpoint()
                current()

            stage = "engine-query-failed"
            queries += 1
            try:
                response = read_engine_bootstrap(
                    checked, operation, deadline=deadline, budget=budget, before_connect=guard
                )
            except BaseException as exc:
                diagnostic = _diagnostic(operation, exc)
                attempted = None if diagnostic is None else diagnostic["contact_attempted"]
                if attempted is True:
                    contact = True
                elif attempted is not False and contact is not True:
                    contact = None
                raise
            if type(response) is EngineResponse:
                contact = True
            elif contact is not True:
                contact = None
            if inspect.iscoroutine(response):
                response.close()
            stage = "metadata-invalid"
            if not guard_ran:
                raise _invalid()
            current()
            candidate = [*frames, response]
            projected = _projection(candidate)
            if type(budget.used) is not int or budget.used != projected["wire_bytes"]:
                raise _invalid()
            current()
            frames, projection = candidate, projected
        current()
        result = _result(
            checked, projection, queries=queries, contact=contact, wire_used=budget.used
        )
        current()
        return result
    except BaseException as exc:
        if isinstance(exc, TimeoutError):
            stage = "deadline-expired"
        elif isinstance(exc, _ClockError):
            stage = "clock-invalid"
        elif type(exc) is _Unsupported:
            stage = str(exc)
        used = 0 if budget is None else budget.used
        if type(used) is not int or not 0 <= used <= MAX_WIRE_BYTES + 4096:
            used = None
        result = _result(
            checked,
            projection,
            reason=stage,
            queries=queries,
            contact=contact,
            wire_used=used,
            diagnostic=diagnostic,
        )
        if not isinstance(exc, Exception):
            exc.engine_bootstrap_observation = result
            raise
        return result
