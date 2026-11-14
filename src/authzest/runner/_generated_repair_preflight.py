"""Private Engine metadata observation, never generated-runtime readiness.

The pure normalizer accepts unverified supplied frames. The private observer
uses only the fixed AF_UNIX HTTP reader; it has no CLI, image provisioning,
container lifecycle, executor/session connection or execution-consent surface.
"""

from __future__ import annotations

import inspect
import math
import re
import stat
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.runner._generated_repair_engine_http import (
    MAX_WIRE_BYTES,
    EngineHTTPError,
    EngineResponse,
    WireBudget,
    read_engine,
)
from authzest.runner._generated_repair_runtime_profile import (
    RuntimeProfile,
    validate_runtime_profile,
)
from authzest.runner.generated_repair_controls import _bounded_decode

_OPERATIONS = ("version", "info", "image-T", "image-A", "image-B")
_MAX_BODY = 65_536
_CAPABILITIES = (
    "MemoryLimit",
    "SwapLimit",
    "CpuCfsPeriod",
    "CpuCfsQuota",
    "CPUShares",
    "CPUSet",
    "PidsLimit",
)
_PENDING = (
    "client-executable-and-empty-config-identity",
    "reviewed-image-dependency-locks-and-actual-guest-asset-contents",
    "effective-namespace-mount-seccomp-and-resource-enforcement",
    "current-staging-and-session-decision-bindings",
    "attach-before-start-capture-and-confirmed-exact-guest-cleanup",
    "separately-scoped-installed-generated-runtime-acceptance",
)


def _invalid() -> ContractError:
    return ContractError("Invalid unverified Engine metadata", code="validation-shape")


class _ClockError(ValueError):
    pass


def _text(value, maximum=256, *, empty=False):
    if (
        type(value) is not str
        or len(value) > maximum
        or (not value and not empty)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise _invalid()
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise _invalid() from exc
    return value


def engine_identity_sha256(engine_id: str) -> str:
    """Domain-separated digest of one bounded daemon ID, not attestation."""
    engine_id = _text(engine_id)
    return sha256(
        canonical(
            {
                "schema_version": "1.0",
                "kind": "generated-repair-engine-identity",
                "engine_id": engine_id,
            }
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeMetadataObservation:
    """Historical metadata only; construction/import cannot activate execution."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def observation_id(self) -> str:
        return "generated-repair-runtime-metadata-observation-" + identity(self.to_dict())


def _profile(profile):
    if type(profile) is not RuntimeProfile:
        raise _invalid()
    return validate_runtime_profile(getattr(profile, "payload_json", None))


def _api(value):
    if type(value) is not str or re.fullmatch(r"1\.[0-9]{2}", value) is None:
        raise _invalid()
    return int(value[2:])


def _pin(value):
    if type(value) is not dict or set(value) != {"socket_identity", "parent_chain_sha256"}:
        raise _invalid()
    entries, parent = value["socket_identity"], value["parent_chain_sha256"]
    if (
        type(entries) is not list
        or len(entries) != 9
        or any(type(item) is not int or not 0 <= item <= 2**64 - 1 for item in entries)
        or not stat.S_ISSOCK(entries[2])
        or entries[5] < 1
        or type(parent) is not str
        or len(parent) != 64
        or re.fullmatch(r"[0-9a-f]+", parent) is None
    ):
        raise _invalid()
    return {"socket_identity": list(entries), "parent_chain_sha256": parent}


def _strings(value, *, maximum=128):
    if value is None:
        return None
    if type(value) is not list or len(value) > maximum:
        raise _invalid()
    return [_text(item, 2048, empty=True) for item in value]


def _small_object(value):
    if value is None:
        return None
    if type(value) is not dict:
        raise _invalid()
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 128 or depth > 4:
            raise _invalid()
        if type(item) is dict:
            if len(item) > 32:
                raise _invalid()
            for key, child in item.items():
                _text(key, 256)
                pending.append((child, depth + 1))
        elif type(item) is list:
            if len(item) > 32:
                raise _invalid()
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            _text(item, 2048, empty=True)
        elif item is not None and type(item) is not bool:
            if type(item) is not int or not 0 <= item <= 2**63 - 1:
                raise _invalid()
    return decode(canonical({"value": value}))["value"]


def _projection(checked, frames):
    data = checked.to_dict()
    arch = data["platform"].split("/")[1]
    selected, bodies, pin = {}, [], None
    wire = 0
    for index, frame in enumerate(frames):
        if (
            type(frame) is not EngineResponse
            or type(frame.operation) is not str
            or frame.operation != _OPERATIONS[index]
        ):
            raise _invalid()
        if type(frame.body) is not bytes or not 0 < len(frame.body) <= _MAX_BODY:
            raise _invalid()
        if (
            type(frame.wire_bytes) is not int
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
        operation = frame.operation
        if operation == "version":
            version = _text(body.get("Version"), 128)
            api, minimum = body.get("ApiVersion"), body.get("MinAPIVersion")
            if (
                body.get("Os") != "linux"
                or body.get("Arch") != arch
                or not _api(minimum) <= _api(data["engine"]["api_version"]) <= _api(api)
            ):
                raise _invalid()
            selected["version"] = {
                "version": version,
                "api_version": api,
                "minimum_api_version": minimum,
                "os": "linux",
                "architecture": arch,
            }
        elif operation == "info":
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
                or architecture != arch
                or server_version != selected["version"]["version"]
                or engine_identity_sha256(engine_id) != data["engine"]["server_identity_sha256"]
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
        else:
            role = operation[-1]
            config = body.get("Config")
            if (
                body.get("Id") != data["images"][role]["image_id"]
                or body.get("Os") != "linux"
                or body.get("Architecture") != arch
                or type(config) is not dict
            ):
                raise _invalid()
            variant = body.get("Variant")
            if variant is not None:
                _text(variant, 32, empty=True)
            if variant not in ((None, "", "v8") if arch == "arm64" else (None, "")):
                raise _invalid()
            user = config.get("User")
            if user is not None:
                _text(user, 256, empty=True)
            selected.setdefault("images", {})[role] = {
                "image_id": body["Id"],
                "os": "linux",
                "architecture": arch,
                "variant": variant,
                "config": {
                    "environment": _strings(config.get("Env")),
                    "entrypoint": _strings(config.get("Entrypoint")),
                    "command": _strings(config.get("Cmd")),
                    "user": user,
                    "volumes": _small_object(config.get("Volumes")),
                    "healthcheck": _small_object(config.get("Healthcheck")),
                },
                "guest_contents_and_dependency_lock_verified": False,
            }
        bodies.append(
            {
                "operation": operation,
                "body_sha256": sha256(frame.body).hexdigest(),
                "wire_bytes": frame.wire_bytes,
            }
        )
    return {"metadata": selected, "responses": bodies, "endpoint_identity": pin, "wire_bytes": wire}


def _diagnostic(operation, exception):
    raw = (
        exception.diagnostic
        if type(exception) is EngineHTTPError
        else getattr(exception, "engine_http_observation", None)
    )
    if type(raw) is not dict:
        return None
    result = {"operation": operation}
    for key in ("contact_attempted", "cleanup_failure"):
        result[key] = raw.get(key) if type(raw.get(key)) is bool else None
    statuses = {
        "connection_status": {"not-attempted", "attempted-unconfirmed", "connected"},
        "request_status": {"not-attempted", "attempted-unconfirmed", "sent"},
        "socket_acquisition": {"not-attempted", "attempted-unconfirmed", "handle-returned"},
        "socket_cleanup": {"not-needed", "unconfirmed", "confirmed"},
    }
    for key, allowed in statuses.items():
        value = raw.get(key)
        result[key] = value if type(value) is str and value in allowed else "unreported"
    count = raw.get("bytes_received")
    result["bytes_received"] = (
        count if type(count) is int and 0 <= count <= MAX_WIRE_BYTES + 4096 else None
    )
    reason = raw.get("reason")
    result["reason"] = (
        reason
        if type(reason) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", reason) is not None
        else "unclassified-transport-failure"
    )
    return result


def _result(
    checked, projection, *, reason=None, queries=0, contact=None, wire_used=None, diagnostic=None
):
    value = {
        "schema_version": "1.0",
        "kind": "generated-repair-runtime-metadata-observation",
        "profile_id": None if checked is None else checked.profile_id,
        "status": "metadata-match" if reason is None else "failed",
        "failure_reason": reason,
        "response_count": len(projection["responses"]),
        "query_attempted": queries,
        "engine_contact_attempted": contact,
        "wire_bytes_used": wire_used,
        "transport_diagnostic": diagnostic,
        **projection,
        "provenance": "caller-supplied-unverified",
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
    try:
        decode(raw)
    except ContractError:
        if reason is None:
            raise
        # A failed observation must not lose its first reason/cleanup merely
        # because a large selected prefix no longer fits the record budget.
        value["metadata"] = {}
        value["metadata_omitted"] = True
        raw = canonical(value)
        decode(raw)
    return RuntimeMetadataObservation(raw)


def normalize_runtime_metadata(profile: RuntimeProfile, frames) -> RuntimeMetadataObservation:
    """Project exactly five bounded supplied responses, never contact an engine."""
    checked = _profile(profile)
    if type(frames) not in (list, tuple) or len(frames) != len(_OPERATIONS):
        raise _invalid()
    return _result(checked, _projection(checked, frames))


def observe_runtime_metadata(
    profile: RuntimeProfile, *, phase_deadline, setup_deadline, before_query=None
) -> RuntimeMetadataObservation:
    """Privately query five fixed API paths under the original host deadlines.

    The synchronous hook runs through the HTTP reader immediately before each
    connection. It is trusted coordination, not consent or a sandbox. No fresh
    allowance is granted for validation, another query or a transport retry.
    """
    checked = None
    frames, queries, contact = [], 0, False
    projection = {"metadata": {}, "responses": [], "endpoint_identity": None, "wire_bytes": 0}
    last = None
    budget, diagnostic = None, None
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
        if _profile(profile).payload_json != checked.payload_json:
            raise _invalid()

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
        stage = "profile-invalid"
        checked = _profile(profile)
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
                if before_query is not None:
                    answer = before_query()
                    if answer is not None:
                        if inspect.iscoroutine(answer):
                            answer.close()
                        raise _invalid()
                current()

            stage = "engine-query-failed"
            queries += 1
            try:
                response = read_engine(
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
            projected = _projection(checked, candidate)
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
            exc.runtime_metadata_observation = result
            raise
        return result
