"""HTTP-only supplied or privately read Engine metadata, never live authority.

Matching reports do not establish image contents, kernel isolation, current
operator decisions, before/after observations or a verified authorization fix.
No product entry point or executor adopts these historical observation objects.
"""

from __future__ import annotations

import inspect
import math
import re
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.runner._generated_repair_preflight import (
    _CAPABILITIES,
    _api,
    _ClockError,
    _diagnostic,
    _pin,
    _small_object,
    _strings,
    _text,
    engine_identity_sha256,
)
from authzest.runner._repository_http_engine_http import (
    MAX_WIRE_BYTES,
    EngineResponse,
    WireBudget,
    read_engine,
)
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpRuntimeProfile,
    validate_runtime_profile,
)
from authzest.runner.generated_repair_controls import _bounded_decode

_OPERATIONS = ("version", "info", "image-A", "image-B")
_MAX_BODY = 65_536
_PENDING = (
    "client-executable-and-empty-config-identity",
    "reviewed-http-image-inputs-and-actual-guest-contents",
    "independently-reviewed-platform-manifest-pin-and-config-id-correspondence",
    "effective-namespace-mount-seccomp-and-resource-enforcement",
    "current-http-staging-checkpoint-and-session-decisions",
    "host-owned-direct-A-B-phase-and-exact-cleanup",
    "installed-external-acceptance-and-final-original-correction",
)


def _invalid() -> ContractError:
    return ContractError("Invalid unverified HTTP Engine metadata", code="validation-shape")


@dataclass(frozen=True, slots=True)
class RepositoryHttpMetadataObservation:
    """Unverified historical metadata, not a current runtime capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def observation_id(self) -> str:
        return "repository-http-runtime-metadata-observation-" + identity(self.to_dict())


def _profile(profile):
    if type(profile) is not RepositoryHttpRuntimeProfile:
        raise _invalid()
    return validate_runtime_profile(getattr(profile, "payload_json", None))


def _manifest_descriptor(value, architecture):
    """Select reported manifest metadata separately from the image config ID.

    Descriptor may identify an index/list and may omit a platform. Even an
    explicit matching platform manifest remains an unverified daemon report;
    no pin is synthesized from Id, a list, an absent platform or this projection.
    """
    if value is None:
        return None, False
    if type(value) is not dict or not {"digest", "mediaType", "size"} <= set(value):
        raise _invalid()
    digest, media_type, size = value["digest"], value["mediaType"], value["size"]
    if (
        type(digest) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        or type(size) is not int
        or not 0 < size <= 1_048_576
    ):
        raise _invalid()
    media_type = _text(media_type, 128)
    platform = value.get("platform")
    if platform is not None:
        if (
            type(platform) is not dict
            or not {"os", "architecture"} <= set(platform)
            or set(platform)
            - {"os", "architecture", "variant", "os.version", "os.features", "features"}
        ):
            raise _invalid()
        selected = {
            "os": _text(platform["os"], 32),
            "architecture": _text(platform["architecture"], 32),
        }
        for key, maximum in (("variant", 32), ("os.version", 128)):
            if key in platform:
                selected[key] = _text(platform[key], maximum, empty=True)
        for key in ("os.features", "features"):
            if key in platform:
                items = platform[key]
                if type(items) is not list or len(items) > 32:
                    raise _invalid()
                selected[key] = [_text(item, 128) for item in items]
        platform = selected
    manifest = media_type in {
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    }
    reported = bool(
        manifest
        and platform is not None
        and platform["os"] == "linux"
        and platform["architecture"] == architecture
        and platform.get("variant", "") in ("", "v8")
    )
    return {"digest": digest, "mediaType": media_type, "size": size, "platform": platform}, reported


def _projection(checked, frames):
    if type(frames) not in (tuple, list) or len(frames) > len(_OPERATIONS):
        raise _invalid()
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
            descriptor, platform_manifest = _manifest_descriptor(body.get("Descriptor"), arch)
            selected.setdefault("images", {})[role] = {
                "image_id": body["Id"],
                "manifest_descriptor": descriptor,
                "platform_manifest_reported": platform_manifest,
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


def _result(
    checked, projection, *, reason=None, queries=0, contact=None, wire_used=None, diagnostic=None
):
    value = {
        "schema_version": "2.0",
        "kind": "repository-http-runtime-metadata-observation",
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
    return RepositoryHttpMetadataObservation(raw)


def normalize_runtime_metadata(
    profile: RepositoryHttpRuntimeProfile, frames
) -> RepositoryHttpMetadataObservation:
    """Project exactly four bounded supplied responses, never contact an engine."""
    checked = _profile(profile)
    if type(frames) not in (list, tuple) or len(frames) != len(_OPERATIONS):
        raise _invalid()
    return _result(checked, _projection(checked, frames))


def observe_runtime_metadata(
    profile: RepositoryHttpRuntimeProfile, *, phase_deadline, setup_deadline, before_query=None
) -> RepositoryHttpMetadataObservation:
    """Privately query four fixed API paths under the original host deadlines.

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
