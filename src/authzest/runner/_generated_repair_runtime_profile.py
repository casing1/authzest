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
from authzest.runner.generated_repair_controls import _bounded_decode

MAX_PROFILE_BYTES = 16_384
EMPTY_CONFIG_SHA256 = sha256(b"{}\n").hexdigest()
_ROLES = ("T", "A", "B")
_ROOT = "/opt/authzest-guest/"
_COMMON = "65ae40e704b8c7d2d4c695a322fa6eeb4830e4df208a7658bdcc6096cf21dc4b"
_ASSETS = {
    "T": {
        "_guest_common.py": _COMMON,
        "test_launcher.py": "90c69083d0a875262e72b02474ea5e91678d80f823ac1e4adc7b87d664059916",
    },
    "A": {
        "_guest_common.py": _COMMON,
        "app_launcher.py": "a6929decc9c8d528ef5342bd783fc4454fbf4074c279bb4eba2d9e79f138f215",
    },
    "B": {
        "_guest_common.py": _COMMON,
        "relay_launcher.py": "6ac463f74c68ec10c676cfb4bb88a09017412c427ea6ee24c1d2613713f6ceaf",
        "_generated_repair_http.py": (
            "8bf5048d83d50f288bdbce8dc6dd2763416d7d153b3f30f082a7579c2b14b930"
        ),
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


def _decode(raw: object) -> dict:
    if type(raw) is not str or len(raw) > MAX_PROFILE_BYTES:
        raise _invalid()
    try:
        if len(raw.encode("utf-8")) > MAX_PROFILE_BYTES:
            raise _invalid()
    except UnicodeError as exc:
        raise _invalid() from exc
    return _bounded_decode(raw)


def _hex(value: object, length: int = 64) -> str:
    if type(value) is not str or len(value) != length or re.fullmatch(r"[0-9a-f]+", value) is None:
        raise _invalid()
    return value


def _path(value: object) -> str:
    if (
        type(value) is not str
        or not 1 < len(value) <= 512
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


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """A closed caller-supplied declaration; no runtime readiness is represented."""

    payload_json: str

    def to_dict(self) -> dict:
        return _decode(self.payload_json)

    @property
    def profile_id(self) -> str:
        return "generated-repair-runtime-profile-" + identity(self.to_dict())

    @property
    def provenance(self) -> str:
        return "caller-supplied-unverified"


@dataclass(frozen=True, slots=True)
class ContainerCreatePlan:
    """Immutable command data only, never a dispatch, consent or owned guest."""

    payload_json: str

    def to_dict(self) -> dict:
        return _decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return "generated-repair-container-create-plan-" + identity(self.to_dict())


def validate_runtime_profile(raw: str) -> RuntimeProfile:
    """Check syntax and maintained asset declarations without probing anything."""
    data = _decode(raw)
    _object(data, _PROFILE_FIELDS)
    if (
        data["schema_version"] != "1.0"
        or data["kind"] != "generated-repair-runtime-profile"
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
        assets = _object(image["assets"], set(_ASSETS[role]))
        if assets != _ASSETS[role]:
            raise ContractError("Maintained guest source drift", code="validation-identity")
    return RuntimeProfile(canonical(data))


def build_container_create_plan(
    profile: RuntimeProfile,
    role: str,
    *,
    session_nonce: str,
    role_nonce: str,
    staging_root: str | None = None,
    application_sha256: str | None = None,
    test_sha256: str | None = None,
    application_container_id: str | None = None,
    remaining_ms: int | None = None,
) -> ContainerCreatePlan:
    """Build fixed stopped-create argv, never execute it or validate real files.

    The future dispatcher must freshly verify executable/socket/config/image and
    staging identities, persist the owned name, inspect effective create state,
    attach before start, enforce original host budgets and confirm exact cleanup.
    """
    if type(profile) is not RuntimeProfile or type(role) is not str or role not in _ROLES:
        raise _invalid()
    checked = validate_runtime_profile(getattr(profile, "payload_json", None))
    data = checked.to_dict()
    engine = data["engine"]
    _hex(session_nonce, 32)
    _hex(role_nonce, 32)
    files = []
    if role == "B":
        if staging_root is not None or application_sha256 is not None or test_sha256 is not None:
            raise _invalid()
        _hex(application_container_id)
        if type(remaining_ms) is not int or not 1 <= remaining_ms <= 40000:
            raise _invalid()
        network = "container:" + application_container_id
    else:
        if application_container_id is not None or remaining_ms is not None:
            raise _invalid()
        root = _path(staging_root)
        if any(
            _overlap(root, path)
            for path in (engine["config_dir"], engine["executable"], engine["endpoint"][7:])
        ):
            raise _invalid()
        _hex(application_sha256)
        files.append(
            {
                "source": _path(root + "/app.py"),
                "target": "/input/app.py",
                "sha256": application_sha256,
            }
        )
        if role == "T":
            _hex(test_sha256)
            files.append(
                {
                    "source": _path(root + "/tests/test_generated_ownership.py"),
                    "target": "/input/tests/test_generated_ownership.py",
                    "sha256": test_sha256,
                }
            )
        elif test_sha256 is not None:
            raise _invalid()
        network = "none"
    name = f"authzest-generated-{session_nonce}-{role.lower()}-{role_nonce}"
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
        "--label=org.authzest.generated.session=" + session_nonce,
        "--label=org.authzest.generated.role=" + role,
        "--label=org.authzest.generated.nonce=" + role_nonce,
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
        "--interactive=false",
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
    for file in files:
        argv.append(
            "--mount=type=bind,src="
            + file["source"]
            + ",dst="
            + file["target"]
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
        "kind": "generated-repair-container-create-plan",
        "profile_id": checked.profile_id,
        "profile": data,
        "role": role,
        "owned_name": name,
        "session_nonce": session_nonce,
        "role_nonce": role_nonce,
        "argv": argv,
        "environment": {"DOCKER_API_VERSION": engine["api_version"]},
        "declared_files": files,
        "application_container_id": application_container_id,
        "remaining_ms": remaining_ms,
        "status": "planned-not-executed",
        "provenance": "caller-supplied-unverified",
        "runtime_invoked": False,
        "execution_authorized": False,
        "authorization_status": "unknown",
        "verified_fix": False,
        "pending": [
            "fresh-executable-socket-config-and-daemon-identity-verification",
            "reviewed-preprovisioned-images-locks-and-effective-image-contents",
            "actual-staging-byte-and-file-identity-rechecks",
            "persist-unique-owned-name-before-create",
            "effective-stopped-create-namespace-mount-seccomp-and-resource-inspection",
            "attach-before-start-and-original-host-time-output-budget-enforcement",
            "durable-capture-and-confirmed-exact-guest-cleanup",
            "current-session-decisions-and-installed-runtime-acceptance",
        ],
    }
    raw = canonical(result)
    _decode(raw)
    return ContainerCreatePlan(raw)
