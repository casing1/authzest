"""Offline runtime declarations and fixed create-argv data, never an executor.

Nothing here observes an executable, socket, config directory, image or staged
file. Declarations and hashes are bindings for later review, not attestation,
capability evidence, consent, a before baseline or authority to run this argv.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import ContractError, _object, canonical, identity
from authzest.runner._repository_http import validate_observer_schedule
from authzest.runner._repository_manifest import validate_guest_manifest
from authzest.runner.generated_repair_controls import _bounded_decode

MAX_PROFILE_BYTES = 16_384
MAX_CREATE_BYTES = 65_536
EMPTY_CONFIG_SHA256 = sha256(b"{}\n").hexdigest()
_ROLES = ("T", "A", "B")
_ROOT = "/opt/authzest-repository-guest/"
_ASSETS = {
    "A": {
        "_guest_common.py": "2ae13fe5b7a80d931256e8f81b23f5a31a7d39337d736764f11d7ab9d2b5aa5b",
        "_repository_manifest.py": (
            "17de5d1e01a0faeefa573631b7bffd48fb1f14b714ea67ad6b12b90cde2a42b5"
        ),
        "app_launcher.py": "cb1539f447a8820c466c585c6537e6cee5e284e19bab24e2d5b880c1d4e843b1",
    },
    "B": {
        "_guest_common.py": "2ae13fe5b7a80d931256e8f81b23f5a31a7d39337d736764f11d7ab9d2b5aa5b",
        "relay_launcher.py": "a62d1ff4466563a399e663a67157f55dac6bd718f178a1255034cdef556e0fbf",
        "repository_http.py": "497c3b09a6a51911c3695e9b9ffdbed0384d02e43c24d631bc1d7773eb123dbf",
    },
    "T": {
        "_guest_common.py": "2ae13fe5b7a80d931256e8f81b23f5a31a7d39337d736764f11d7ab9d2b5aa5b",
        "_repository_manifest.py": (
            "17de5d1e01a0faeefa573631b7bffd48fb1f14b714ea67ad6b12b90cde2a42b5"
        ),
        "test_launcher.py": "cde96e9a6a8f847fa21d495a186f3c4ed26d87f607d437886e19e314511f5422",
    },
}
_RECIPE_PINS = {
    "linux/amd64": {
        "A": {
            "dependency_lock_sha256": (
                "d5e47e336f638d33f90d8241f76ebe58cecb45d7e910ce9d7fe487efd8e636bb"
            ),
            "recipe_sha256": "df8e83abc10908cdc980271110fc4858f89a042eedb5afa4c26dd0436a69eddd",
        },
        "B": {
            "dependency_lock_sha256": (
                "15ede46cc460b1a15b005f8bc0dcf46515c6ee96242ee0a22617c7af89d4908e"
            ),
            "recipe_sha256": "0ec59587c8b42cc3728c13ed5d67018024107f25488d7fc86755ad24128914ef",
        },
        "T": {
            "dependency_lock_sha256": (
                "8f87350f05c065015a9f2c7633aee604afc31c6d02cc96459b6fcd09520718fc"
            ),
            "recipe_sha256": "6d10cb02133f0b741bd9a3ad94bc92831f2afd21e4f766c35ea129bab509b2d4",
        },
    },
    "linux/arm64": {
        "A": {
            "dependency_lock_sha256": (
                "4fe83c082c5db3d478c0b40f39d626b3c687182d0c28efd818d5cffea93699b8"
            ),
            "recipe_sha256": "7001ddb5f6fc8a36d9fb29aacdb969b15943990742f80bd765d920c954672ddc",
        },
        "B": {
            "dependency_lock_sha256": (
                "15ede46cc460b1a15b005f8bc0dcf46515c6ee96242ee0a22617c7af89d4908e"
            ),
            "recipe_sha256": "e49c8e4dd0b794d6e26af2367eb3b813ec78c5e110b5bd1bbe93fc4e77e684d9",
        },
        "T": {
            "dependency_lock_sha256": (
                "e2a56894eeff0a0ef1433ec9eecf99e75339e52e92f9fe39ea9e015618f030cf"
            ),
            "recipe_sha256": "8bce064f8930cdce97bc0a0dfd7f759fb131bb10a4fe7b86701d08d2593e3337",
        },
    },
}
_SCRIPTS = {"T": "test_launcher.py", "A": "app_launcher.py", "B": "relay_launcher.py"}
_PROFILE_FIELDS = {"schema_version", "kind", "platform", "engine", "images"}
_ENGINE_FIELDS = {
    "executable",
    "executable_sha256",
    "endpoint",
    "config_dir",
    "config_json_sha256",
    "server_identity_sha256",
    "api_version",
}
_IMAGE_FIELDS = {"image_id", "dependency_lock_sha256", "recipe_sha256", "assets"}


def _invalid() -> ContractError:
    return ContractError("Invalid unverified runtime declaration", code="validation-shape")


def _decode(raw: object, limit: int = MAX_PROFILE_BYTES) -> dict:
    if type(raw) is not str or len(raw) > limit:
        raise _invalid()
    try:
        if len(raw.encode("utf-8")) > limit:
            raise _invalid()
    except UnicodeError as exc:
        raise _invalid() from exc
    return _bounded_decode(raw)


def _hex(value: object, length: int = 64) -> str:
    if type(value) is not str or len(value) != length or re.fullmatch(r"[0-9a-f]+", value) is None:
        raise _invalid()
    return value


def _path(value: object, maximum: int = 512) -> str:
    if (
        type(value) is not str
        or not 1 < len(value) <= maximum
        or re.fullmatch(r"/[A-Za-z0-9._/-]+", value, re.ASCII) is None
        or any(part in {"", ".", ".."} for part in value[1:].split("/"))
    ):
        raise _invalid()
    return value


def _overlap(first: str, second: str) -> bool:
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def expected_assets(role: str) -> dict[str, str]:
    """Return maintained source digests, not a claim about any image's bytes."""
    if type(role) is not str or role not in _ROLES:
        raise _invalid()
    return dict(_ASSETS[role])


def expected_recipe_pins(platform: str, role: str) -> dict[str, str]:
    """Maintained static recipe/lock declarations, not a claim about built images."""
    if (
        type(platform) is not str
        or platform not in _RECIPE_PINS
        or type(role) is not str
        or role not in _ROLES
    ):
        raise _invalid()
    return dict(_RECIPE_PINS[platform][role])


@dataclass(frozen=True, slots=True)
class RepositoryRuntimeProfile:
    """A closed caller-supplied declaration; no runtime readiness is represented."""

    payload_json: str

    def to_dict(self) -> dict:
        return _decode(self.payload_json)

    @property
    def profile_id(self) -> str:
        return "repository-runtime-profile-" + identity(self.to_dict())

    @property
    def provenance(self) -> str:
        return "caller-supplied-unverified"


@dataclass(frozen=True, slots=True)
class RepositoryCreatePlan:
    """Immutable command data only, never a dispatch, consent or owned guest."""

    payload_json: str

    def to_dict(self) -> dict:
        return _decode(self.payload_json, MAX_CREATE_BYTES)

    @property
    def plan_id(self) -> str:
        return "repository-container-create-plan-" + identity(self.to_dict())


def validate_runtime_profile(raw: str) -> RepositoryRuntimeProfile:
    """Check syntax and maintained asset declarations without probing anything."""
    data = _decode(raw)
    _object(data, _PROFILE_FIELDS)
    if (
        data["schema_version"] != "1.0"
        or data["kind"] != "repository-runtime-profile"
        or type(data["platform"]) is not str
        or data["platform"] not in {"linux/amd64", "linux/arm64"}
    ):
        raise _invalid()
    engine = _object(data["engine"], _ENGINE_FIELDS)
    executable = _path(engine["executable"])
    config_dir = _path(engine["config_dir"])
    if executable.rsplit("/", 1)[1] != "docker":
        raise _invalid()
    endpoint = engine["endpoint"]
    if type(endpoint) is not str or not endpoint.startswith("unix://"):
        raise _invalid()
    socket_path = _path(endpoint[7:])
    if any(
        _overlap(first, second)
        for first, second in (
            (config_dir, executable),
            (config_dir, socket_path),
            (executable, socket_path),
        )
    ):
        raise _invalid()
    for field in ("executable_sha256", "config_json_sha256", "server_identity_sha256"):
        _hex(engine[field])
    if engine["config_json_sha256"] != EMPTY_CONFIG_SHA256:
        raise _invalid()
    version = engine["api_version"]
    if type(version) is not str or re.fullmatch(r"1\.[0-9]{2}", version) is None:
        raise _invalid()
    if not 41 <= int(version[2:]) <= 99:
        raise _invalid()
    images = _object(data["images"], set(_ROLES))
    for role in _ROLES:
        image = _object(images[role], _IMAGE_FIELDS)
        image_id = image["image_id"]
        if type(image_id) is not str or not image_id.startswith("sha256:"):
            raise _invalid()
        _hex(image_id[7:])
        for field in ("dependency_lock_sha256", "recipe_sha256"):
            _hex(image[field])
        pins = expected_recipe_pins(data["platform"], role)
        if any(image[field] != digest for field, digest in pins.items()):
            raise ContractError("Maintained repository recipe drift", code="validation-identity")
        assets = _object(image["assets"], set(_ASSETS[role]))
        if assets != _ASSETS[role]:
            raise ContractError("Maintained guest source drift", code="validation-identity")
    return RepositoryRuntimeProfile(canonical(data))


def build_container_create_plan(
    profile: RepositoryRuntimeProfile,
    role: str,
    *,
    session_nonce: str,
    role_nonce: str,
    staging_root: str | None = None,
    manifest: dict | None = None,
    application_container_id: str | None = None,
    remaining_ms: int | None = None,
    schedule: dict | None = None,
) -> RepositoryCreatePlan:
    """Produce closed stopped-create data; never probe, invoke or adopt runtime evidence."""
    if type(profile) is not RepositoryRuntimeProfile or type(role) is not str or role not in _ROLES:
        raise _invalid()
    checked = validate_runtime_profile(profile.payload_json)
    data = checked.to_dict()
    engine = data["engine"]
    _hex(session_nonce, 32)
    _hex(role_nonce, 32)
    files = []
    stdin = None
    if role == "B":
        if staging_root is not None or manifest is not None:
            raise _invalid()
        _hex(application_container_id)
        if type(remaining_ms) is not int or not 1 <= remaining_ms <= 40000:
            raise _invalid()
        schedule = validate_observer_schedule(schedule)
        stdin_text = canonical(schedule)
        stdin = {
            "kind": "repository-observer-schedule",
            "value": schedule,
            "sha256": sha256(stdin_text.encode("utf-8")).hexdigest(),
            "utf8_bytes": len(stdin_text.encode("utf-8")),
            "eof_required": True,
        }
        network = "container:" + application_container_id
        manifest = None
    else:
        if application_container_id is not None or remaining_ms is not None or schedule is not None:
            raise _invalid()
        root = _path(staging_root, 4096)
        if any(
            _overlap(root, path)
            for path in (engine["config_dir"], engine["executable"], engine["endpoint"][7:])
        ):
            raise _invalid()
        manifest = validate_guest_manifest(manifest, role)
        raw_manifest = canonical(manifest).encode("utf-8")
        descriptors = [
            {
                "path": "manifest.json",
                "sha256": sha256(raw_manifest).hexdigest(),
                "size_bytes": len(raw_manifest),
            },
            *[{**item, "path": "project/" + item["path"]} for item in manifest["source_files"]],
        ]
        if role == "T":
            descriptors.append(manifest["test"])
        for item in descriptors:
            files.append(
                {
                    "source": _path(root + "/" + item["path"], 4096),
                    "target": _path("/input/" + item["path"], 4096),
                    "sha256": item["sha256"],
                    "utf8_bytes": item["size_bytes"],
                }
            )
        network = "none"
    name = f"authzest-repository-{session_nonce}-{role.lower()}-{role_nonce}"
    image = data["images"][role]
    small = role == "B"
    memory = 134_217_728 if small else 536_870_912
    tmpfs = 8_388_608 if small else 33_554_432
    argv = [
        engine["executable"],
        "--config=" + engine["config_dir"],
        "--host=" + engine["endpoint"],
        "container",
        "create",
        "--name=" + name,
        "--label=org.authzest.repository.session=" + session_nonce,
        "--label=org.authzest.repository.role=" + role,
        "--label=org.authzest.repository.nonce=" + role_nonce,
        "--pull=never",
        "--platform=" + data["platform"],
        "--user=65532:65532",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--ipc=private",
        "--cgroupns=private",
        "--init=false",
        "--restart=no",
        "--log-driver=none",
        "--no-healthcheck",
        "--privileged=false",
        "--publish-all=false",
        "--interactive=" + ("true" if small else "false"),
        "--tty=false",
        "--workdir=/tmp",
        f"--memory={memory}",
        f"--memory-swap={memory}",
        "--cpus=" + ("0.5" if small else "1"),
        "--pids-limit=" + ("32" if small else "64"),
        "--shm-size=8388608",
        f"--tmpfs=/tmp:rw,noexec,nosuid,nodev,size={tmpfs},uid=65532,gid=65532,mode=0700",
        "--network=" + network,
    ]
    for item in files:
        argv.append(
            "--mount=type=bind,src="
            + item["source"]
            + ",dst="
            + item["target"]
            + ",readonly,bind-propagation=rprivate"
        )
    argv.extend(
        [
            "--entrypoint=/usr/local/bin/python",
            image["image_id"],
            "-I",
            "-B",
            _ROOT + _SCRIPTS[role],
        ]
    )
    if small:
        argv.append(str(remaining_ms))
    result = {
        "schema_version": "1.0",
        "kind": "repository-container-create-plan",
        "profile_id": checked.profile_id,
        "profile": data,
        "role": role,
        "owned_name": name,
        "session_nonce": session_nonce,
        "role_nonce": role_nonce,
        "argv": argv,
        "environment": {"DOCKER_API_VERSION": engine["api_version"]},
        "declared_files": files,
        "input_manifest": manifest,
        "stdin": stdin,
        "application_container_id": application_container_id,
        "remaining_ms": remaining_ms,
        "budgets": {
            "phase_seconds": 40,
            "cleanup_seconds": 10,
            "combined_output_bytes": 262144,
            "relay_output_bytes": 131072,
            "memory_bytes": memory,
            "tmpfs_bytes": tmpfs,
            "pid_limit": 32 if small else 64,
            "pid_namespace": "private-default",
        },
        "status": "planned-not-executed",
        "provenance": "caller-supplied-unverified",
        "runtime_invoked": False,
        "execution_authorized": False,
        "authorization_status": "unknown",
        "verified_fix": False,
        "pending": [
            "fresh-engine-executable-endpoint-config-and-server-identity",
            "separately-reviewed-built-images-locks-and-effective-contents",
            "fresh-staging-bytes-identities-and-effective-read-only-file-mounts",
            "persist-owned-names-before-create-and-inspect-stopped-configuration",
            "attach-before-start-and-send-exact-schedule-then-eof-for-B",
            "original-host-phase-output-budget-and-effective-network-pid-mount-controls",
            "direct-live-phase-assembly-and-confirmed-exact-guest-cleanup",
            "current-user-decisions-and-installed-external-acceptance",
        ],
    }
    raw = canonical(result)
    _decode(raw, MAX_CREATE_BYTES)
    return RepositoryCreatePlan(raw)
