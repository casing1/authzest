"""Pure HTTP A/B stopped-container comparisons, never live runtime evidence.

The exact HTTP create declaration is reconstructed before supplied metadata is
compared. Matching daemon text cannot establish ownership, a current file stage,
kernel enforcement, consent or a direct before/after observation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.runner._generated_repair_container_inspect import (
    _empty,
    _environment,
    _host,
    _inspect,
    _integer,
    _network,
    _object,
    _state,
    _text,
)
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpCreatePlan,
    build_container_create_plan,
    validate_runtime_profile,
)


def _invalid() -> ContractError:
    return ContractError("Invalid unverified HTTP stopped metadata", code="validation-shape")


def _plan(value):
    # Exact new type only: saved dicts and all T/v1 declarations remain inert.
    if type(value) is not RepositoryHttpCreatePlan:
        raise _invalid()
    data = value.to_dict()
    try:
        profile = validate_runtime_profile(canonical(data["profile"]))
        role, files = data["role"], data["declared_files"]
        if type(role) is not str or role not in {"A", "B"} or type(files) is not list:
            raise _invalid()
        parameters = {"session_nonce": data["session_nonce"], "role_nonce": data["role_nonce"]}
        if role == "A":
            if len(files) != 2:
                raise _invalid()
            first = _object(files[0], {"source", "target", "sha256", "utf8_bytes"})
            path = _text(first["source"], 4096)
            if not path.endswith("/manifest.json"):
                raise _invalid()
            parameters.update(
                staging_root=path.removesuffix("/manifest.json"),
                manifest=data["input_manifest"],
            )
        else:
            parameters.update(
                application_container_id=data["application_container_id"],
                remaining_ms=data["remaining_ms"],
                schedule=_object(
                    data["stdin"],
                    {"kind", "value", "sha256", "utf8_bytes", "eof_required"},
                )["value"],
            )
        expected = build_container_create_plan(profile, role, **parameters)
    except ContractError:
        raise
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise _invalid() from exc
    if canonical(data) != expected.payload_json:
        raise _invalid()
    return expected, data


def _config(value, data, environment, image_id):
    config = _object(
        value,
        {
            "Image",
            "Labels",
            "User",
            "WorkingDir",
            "Entrypoint",
            "Cmd",
            "Env",
            "Healthcheck",
            "OpenStdin",
            "AttachStdin",
            "AttachStdout",
            "AttachStderr",
            "StdinOnce",
            "Tty",
            "Volumes",
        },
        None,
    )
    labels = {
        "org.authzest.repository-http.session": data["session_nonce"],
        "org.authzest.repository-http.role": data["role"],
        "org.authzest.repository-http.nonce": data["role_nonce"],
    }
    if (
        config["Image"] != image_id
        or type(config["Labels"]) is not dict
        or config["Labels"] != labels
        or config["User"] != "65532:65532"
        or config["WorkingDir"] != "/tmp"
        or config["Entrypoint"] != ["/usr/local/bin/python"]
        or _environment(config["Env"]) != environment
    ):
        raise _invalid()
    position = data["argv"].index(image_id)
    arguments = data["argv"][position + 1 :]
    if type(config["Cmd"]) is not list or config["Cmd"] != arguments:
        raise _invalid()
    # docker create --interactive sets OpenStdin and AttachStdin; Docker CLI
    # consequently sets StdinOnce. All three must be false for A, true for B.
    for key in ("OpenStdin", "AttachStdin", "StdinOnce"):
        if config[key] is not (data["role"] == "B"):
            raise _invalid()
    if config["Tty"] is not False:
        raise _invalid()
    for key in ("AttachStdout", "AttachStderr"):
        if config[key] is not True:
            raise _invalid()
    for key in ("Volumes", "ExposedPorts"):
        _empty(config.get(key), (type(None), dict))
    _empty(config.get("OnBuild"), (type(None), list))
    health = _object(
        config["Healthcheck"],
        {"Test"},
        {"Interval", "Timeout", "StartPeriod", "StartInterval", "Retries"},
    )
    if health["Test"] != ["NONE"]:
        raise _invalid()
    for key in set(health) - {"Test"}:
        _integer(health[key], 0)
    return arguments


@dataclass(frozen=True, slots=True)
class RepositoryHttpStoppedContainerObservation:
    """Supplied unverified daemon text, never a live capability or phase result."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def observation_id(self) -> str:
        return "repository-http-stopped-container-observation-" + identity(self.to_dict())


def validate_stopped_container(
    plan: RepositoryHttpCreatePlan,
    raw: str,
    *,
    container_id: str,
    image_environment: list[str],
) -> RepositoryHttpStoppedContainerObservation:
    """Compare one bounded supplied object/one-element array without any I/O.

    Current ownership, staged bytes, executable/config/endpoint/image identities,
    invocation deadlines and cleanup need separate direct host observations.
    """
    if type(container_id) is not str or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise _invalid()
    checked, data = _plan(plan)
    environment = _environment(image_environment)
    value = _inspect(raw)
    role, profile = data["role"], data["profile"]
    image_id = profile["images"][role]["image_id"]
    if (
        value["Id"] != container_id
        or value["Name"] != "/" + data["owned_name"]
        or value["Image"] != image_id
        or value["Platform"] != "linux"
        or (role == "B" and data["application_container_id"] == container_id)
    ):
        raise _invalid()
    _state(value["State"])
    _integer(value["RestartCount"], 0)
    arguments = _config(value["Config"], data, environment, image_id)
    if value["Path"] != "/usr/local/bin/python" or value["Args"] != arguments:
        raise _invalid()
    descriptor = _object(
        value["ImageManifestDescriptor"],
        {"digest", "mediaType", "size", "platform"},
        {"annotations"},
    )
    if descriptor["digest"] != image_id or _text(descriptor["mediaType"], 128) not in {
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    }:
        raise _invalid()
    if type(descriptor["size"]) is not int or not 0 < descriptor["size"] <= 1_048_576:
        raise _invalid()
    platform = _object(descriptor["platform"], {"os", "architecture"}, {"variant"})
    if (
        platform["os"] != "linux"
        or platform["architecture"] != "arm64"
        or platform.get("variant", "") not in ("", "v8")
    ):
        raise _invalid()
    host = _host(value["HostConfig"], data, value["Mounts"])
    _network(value["NetworkSettings"], role == "B")
    projection = {
        "schema_version": "2.0",
        "kind": "repository-http-stopped-container-observation",
        "status": "daemon-reported-stopped-config-match",
        "provenance": "caller-supplied-unverified",
        "plan_id": checked.plan_id,
        "profile_id": data["profile_id"],
        "container_id": container_id,
        "owned_name": data["owned_name"],
        "role": role,
        "platform": profile["platform"],
        "image_id": image_id,
        "inspect_sha256": sha256(raw.encode("utf-8")).hexdigest(),
        "image_environment_sha256": identity(environment),
        "reported_host_configuration": host,
        "declared_files": data["declared_files"],
        "never_started_reported": True,
        "effective_kernel_isolation_verified": False,
        "effective_mounts_verified": False,
        "seccomp_enforcement_verified": False,
        "resource_enforcement_established": False,
        "ready": False,
        "runtime_ready": False,
        "runtime_invoked": False,
        "generated_runtime_invoked": False,
        "execution_authorized": False,
        "authorization_status": "unknown",
        "verified_fix": False,
        "pending": [
            "fresh-owned-container-and-current-file-stage",
            "fresh-executable-empty-config-endpoint-and-image-identities",
            "effective-runtime-enforcement",
            "attach-before-start-and-original-shared-budgets",
            "direct-live-phase-and-confirmed-owned-cleanup",
        ],
    }
    result = canonical(projection)
    decode(result)
    return RepositoryHttpStoppedContainerObservation(result)
