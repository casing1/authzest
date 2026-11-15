"""Pure comparisons of supplied stopped-container metadata with fixed plans.

There is no Engine, socket, process, filesystem or generated-code operation here.
A matching daemon report is neither authenticated observation nor evidence that
kernel namespaces, mounts, seccomp or resource controllers enforce these values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.runner._generated_repair_runtime_profile import (
    ContainerCreatePlan,
    build_container_create_plan,
    validate_runtime_profile,
)
from authzest.runner.generated_repair_controls import _bounded_decode

MAX_INSPECT_BYTES = 65_536
_ZERO_TIME = "0001-01-01T00:00:00Z"
_MASKED = {
    "/proc/acpi",
    "/proc/asound",
    "/proc/interrupts",
    "/proc/kcore",
    "/proc/keys",
    "/proc/latency_stats",
    "/proc/sched_debug",
    "/proc/scsi",
    "/proc/timer_list",
    "/proc/timer_stats",
    "/sys/devices/virtual/powercap",
    "/sys/firmware",
}
_READONLY = {"/proc/bus", "/proc/fs", "/proc/irq", "/proc/sys", "/proc/sysrq-trigger"}


def _invalid() -> ContractError:
    return ContractError("Invalid unverified stopped-container metadata", code="validation-shape")


def _object(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value):
        raise _invalid()
    if optional is not None and set(value) - set(required) - set(optional):
        raise _invalid()
    return value


def _text(value, maximum=4096):
    if (
        type(value) is not str
        or len(value) > maximum
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise _invalid()
    return value


def _integer(value, expected):
    if type(value) is not int or value != expected:
        raise _invalid()


def _empty(value, kinds):
    if not any(type(value) is kind and not value for kind in kinds):
        raise _invalid()


def _native_plan(value):
    pending, count, characters = [(value, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 1024 or depth > 12:
            raise _invalid()
        if type(item) is dict:
            if len(item) > 64 or any(type(key) is not str for key in item):
                raise _invalid()
            pending.extend((child, depth + 1) for child in item.values())
            pending.extend((key, depth + 1) for key in item)
        elif type(item) is list:
            if len(item) > 128:
                raise _invalid()
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            characters += len(item)
            if len(item) > 16_384 or characters > 16_384:
                raise _invalid()
        elif type(item) is int:
            if abs(item) > 2**63 - 1:
                raise _invalid()
        elif type(item) not in (bool, type(None)):
            raise _invalid()


def _plan(value):
    if type(value) is ContainerCreatePlan:
        data = value.to_dict()
    elif type(value) is dict:
        _native_plan(value)
        data = _bounded_decode(canonical(value))
    else:
        raise _invalid()
    try:
        profile = validate_runtime_profile(canonical(data["profile"]))
        role, files = data["role"], data["declared_files"]
        if type(role) is not str or role not in {"T", "A", "B"} or type(files) is not list:
            raise _invalid()
        parameters = {"session_nonce": data["session_nonce"], "role_nonce": data["role_nonce"]}
        if role == "B":
            parameters.update(
                application_container_id=data["application_container_id"],
                remaining_ms=data["remaining_ms"],
            )
        else:
            if len(files) != (2 if role == "T" else 1):
                raise _invalid()
            first = _object(files[0], {"source", "target", "sha256"})
            source = _text(first["source"], 512)
            if not source.endswith("/app.py"):
                raise _invalid()
            parameters.update(staging_root=source[:-7], application_sha256=first["sha256"])
            if role == "T":
                parameters["test_sha256"] = _object(files[1], {"source", "target", "sha256"})[
                    "sha256"
                ]
        expected = build_container_create_plan(profile, role, **parameters)
    except (KeyError, TypeError, IndexError) as exc:
        raise _invalid() from exc
    if canonical(data) != expected.payload_json:
        raise _invalid()
    return expected, data


def _inspect(raw):
    if type(raw) is not str or len(raw) > MAX_INSPECT_BYTES:
        raise _invalid()
    try:
        if len(raw.encode("utf-8")) > MAX_INSPECT_BYTES:
            raise _invalid()
    except UnicodeError as exc:
        raise _invalid() from exc
    value = _bounded_decode('{"inspect":' + raw + "}")["inspect"]
    if type(value) is list:
        if len(value) != 1:
            raise _invalid()
        value = value[0]
    return _object(
        value,
        {
            "Id",
            "Name",
            "Image",
            "Platform",
            "Path",
            "Args",
            "State",
            "Config",
            "HostConfig",
            "Mounts",
            "NetworkSettings",
            "RestartCount",
            "ImageManifestDescriptor",
        },
        None,
    )


def _environment(value):
    if type(value) is not list or len(value) > 32:
        raise _invalid()
    seen = set()
    for variable in value:
        variable = _text(variable)
        name, separator, _ = variable.partition("=")
        if not separator or re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) is None or name in seen:
            raise _invalid()
        seen.add(name)
    return list(value)


def _state(value):
    state = _object(
        value,
        {
            "Status",
            "Running",
            "Paused",
            "Restarting",
            "Dead",
            "Pid",
            "OOMKilled",
            "ExitCode",
            "Error",
            "StartedAt",
            "FinishedAt",
        },
        None,
    )
    if state["Status"] != "created" or state["Error"] != "":
        raise _invalid()
    for key in ("Running", "Paused", "Restarting", "Dead", "OOMKilled"):
        if state[key] is not False:
            raise _invalid()
    for key in ("Pid", "ExitCode"):
        _integer(state[key], 0)
    if state["StartedAt"] != _ZERO_TIME or state["FinishedAt"] != _ZERO_TIME:
        raise _invalid()


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
    role = data["role"]
    labels = {
        "org.authzest.generated.session": data["session_nonce"],
        "org.authzest.generated.role": role,
        "org.authzest.generated.nonce": data["role_nonce"],
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
    for key in ("OpenStdin", "AttachStdin", "StdinOnce", "Tty"):
        if config[key] is not False:
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


def _tmpfs(value, small):
    value = _object(value, {"/tmp"})
    tokens = _text(value["/tmp"], 256).split(",")
    expected = {
        "rw",
        "noexec",
        "nosuid",
        "nodev",
        "uid=65532",
        "gid=65532",
        "mode=0700",
        "size=" + str(8_388_608 if small else 33_554_432),
    }
    if len(tokens) != len(expected) or set(tokens) != expected:
        raise _invalid()


def _mounts(host, resolved, files):
    configured = host.get("Mounts")
    if configured is None and not files:
        configured = []
    if type(configured) is not list or type(resolved) is not list:
        raise _invalid()
    if len(configured) != len(files) or len(resolved) != len(files):
        raise _invalid()
    expected = {entry["target"]: entry["source"] for entry in files}
    seen = set()
    for mount in configured:
        mount = _object(
            mount, {"Type", "Source", "Target", "ReadOnly", "BindOptions"}, {"Consistency"}
        )
        target = mount["Target"]
        if (
            type(target) is not str
            or target in seen
            or target not in expected
            or mount["Source"] != expected[target]
            or mount["Type"] != "bind"
            or mount["ReadOnly"] is not True
            or mount.get("Consistency", "") != ""
        ):
            raise _invalid()
        options = _object(
            mount["BindOptions"],
            {"Propagation"},
            {"NonRecursive", "CreateMountpoint", "ReadOnlyNonRecursive", "ReadOnlyForceRecursive"},
        )
        if options["Propagation"] != "rprivate":
            raise _invalid()
        for key in set(options) - {"Propagation"}:
            if options[key] is not False:
                raise _invalid()
        seen.add(target)
    seen = set()
    for mount in resolved:
        mount = _object(
            mount,
            {"Type", "Source", "Destination", "RW", "Propagation", "Mode"},
            {"Name", "Driver"},
        )
        target = mount["Destination"]
        if (
            type(target) is not str
            or target in seen
            or target not in expected
            or mount["Source"] != expected[target]
            or mount["Type"] != "bind"
            or mount["RW"] is not False
            or mount["Propagation"] != "rprivate"
            or mount["Mode"] not in ("", "ro")
            or mount.get("Name", "") != ""
            or mount.get("Driver", "") != ""
        ):
            raise _invalid()
        seen.add(target)


def _host(value, data, resolved):
    host = _object(
        value,
        {
            "Privileged",
            "ReadonlyRootfs",
            "PublishAllPorts",
            "AutoRemove",
            "Init",
            "CapAdd",
            "CapDrop",
            "SecurityOpt",
            "PidMode",
            "IpcMode",
            "CgroupnsMode",
            "UTSMode",
            "UsernsMode",
            "Runtime",
            "Isolation",
            "CgroupParent",
            "Cgroup",
            "LogConfig",
            "RestartPolicy",
            "NetworkMode",
            "Binds",
            "VolumesFrom",
            "PortBindings",
            "Devices",
            "DeviceRequests",
            "DeviceCgroupRules",
            "GroupAdd",
            "Links",
            "Dns",
            "DnsOptions",
            "DnsSearch",
            "ExtraHosts",
            "Memory",
            "MemorySwap",
            "NanoCpus",
            "PidsLimit",
            "ShmSize",
            "MemoryReservation",
            "MemorySwappiness",
            "OomKillDisable",
            "OomScoreAdj",
            "CpuPeriod",
            "CpuQuota",
            "CpuShares",
            "CpuRealtimePeriod",
            "CpuRealtimeRuntime",
            "CpuCount",
            "CpuPercent",
            "CpusetCpus",
            "CpusetMems",
            "Ulimits",
            "MaskedPaths",
            "ReadonlyPaths",
            "Tmpfs",
        },
        None,
    )
    for key in ("Privileged", "PublishAllPorts", "AutoRemove", "Init", "OomKillDisable"):
        if host[key] is not False:
            raise _invalid()
    if host["ReadonlyRootfs"] is not True or host["CapDrop"] != ["ALL"]:
        raise _invalid()
    if host["SecurityOpt"] not in (["no-new-privileges:true"], ["no-new-privileges=true"]):
        raise _invalid()
    for key in (
        "PidMode",
        "UTSMode",
        "UsernsMode",
        "Isolation",
        "CgroupParent",
        "Cgroup",
        "CpusetCpus",
        "CpusetMems",
    ):
        if host[key] != "":
            raise _invalid()
    if (
        host["IpcMode"] != "private"
        or host["CgroupnsMode"] != "private"
        or host["Runtime"] != "runc"
    ):
        raise _invalid()
    for key in (
        "CapAdd",
        "Binds",
        "VolumesFrom",
        "Devices",
        "DeviceRequests",
        "DeviceCgroupRules",
        "GroupAdd",
        "Links",
        "Dns",
        "DnsOptions",
        "DnsSearch",
        "ExtraHosts",
        "Ulimits",
    ):
        _empty(host[key], (type(None), list))
    for key in ("PortBindings", "StorageOpt"):
        _empty(host.get(key), (type(None), dict))
    if host.get("VolumeDriver", "") != "":
        raise _invalid()
    log = _object(host["LogConfig"], {"Type", "Config"})
    if log["Type"] != "none":
        raise _invalid()
    _empty(log["Config"], (dict,))
    restart = _object(host["RestartPolicy"], {"Name", "MaximumRetryCount"})
    if restart["Name"] != "no":
        raise _invalid()
    _integer(restart["MaximumRetryCount"], 0)
    small = data["role"] == "B"
    memory = 134_217_728 if small else 536_870_912
    for key, number in {
        "Memory": memory,
        "MemorySwap": memory,
        "NanoCpus": 500_000_000 if small else 1_000_000_000,
        "PidsLimit": 32 if small else 64,
        "ShmSize": 8_388_608,
    }.items():
        _integer(host[key], number)
    for key in (
        "MemoryReservation",
        "OomScoreAdj",
        "CpuPeriod",
        "CpuQuota",
        "CpuShares",
        "CpuRealtimePeriod",
        "CpuRealtimeRuntime",
        "CpuCount",
        "CpuPercent",
    ):
        _integer(host[key], 0)
    if host["MemorySwappiness"] is not None:
        raise _invalid()
    for key in (
        "KernelMemory",
        "KernelMemoryTCP",
        "BlkioWeight",
        "IOMaximumIOps",
        "IOMaximumBandwidth",
    ):
        if key in host:
            _integer(host[key], 0)
    for key in (
        "BlkioWeightDevice",
        "BlkioDeviceReadBps",
        "BlkioDeviceWriteBps",
        "BlkioDeviceReadIOps",
        "BlkioDeviceWriteIOps",
    ):
        if key in host:
            _empty(host[key], (type(None), list))
    for key, expected in (("MaskedPaths", _MASKED), ("ReadonlyPaths", _READONLY)):
        paths = host[key]
        if (
            type(paths) is not list
            or any(type(path) is not str for path in paths)
            or len(paths) != len(expected)
            or set(paths) != expected
        ):
            raise _invalid()
    network = "container:" + data["application_container_id"] if small else "none"
    if host["NetworkMode"] != network:
        raise _invalid()
    _tmpfs(host["Tmpfs"], small)
    _mounts(host, resolved, data["declared_files"])
    return {
        "network_mode": network,
        "memory_bytes": memory,
        "memory_swap_total_bytes": memory,
        "nano_cpus": host["NanoCpus"],
        "pids_limit": host["PidsLimit"],
        "shm_bytes": host["ShmSize"],
        "tmpfs": dict(host["Tmpfs"]),
        "runtime": "runc",
        "seccomp_selection": "daemon-default-unverified",
        "pid_mode": "daemon-default",
        "ipc_mode": "private",
        "cgroupns_mode": "private",
    }


def _network(value, small):
    network = _object(value, {"Ports", "Networks", "SandboxID", "SandboxKey"}, None)
    _empty(network["Ports"], (type(None), dict))
    if network["SandboxID"] != "" or network["SandboxKey"] != "":
        raise _invalid()
    if small:
        _empty(network["Networks"], (type(None), dict))
    else:
        selected = _object(network["Networks"], {"none"})
        detail = _object(
            selected["none"],
            {
                "NetworkID",
                "EndpointID",
                "Gateway",
                "IPAddress",
                "MacAddress",
                "IPPrefixLen",
                "IPv6Gateway",
                "GlobalIPv6Address",
                "GlobalIPv6PrefixLen",
            },
            None,
        )
        for key in (
            "NetworkID",
            "EndpointID",
            "Gateway",
            "IPAddress",
            "MacAddress",
            "IPv6Gateway",
            "GlobalIPv6Address",
        ):
            if detail[key] != "":
                raise _invalid()
        _integer(detail["IPPrefixLen"], 0)
        _integer(detail["GlobalIPv6PrefixLen"], 0)
        for key in ("IPAMConfig", "DriverOpts"):
            _empty(detail.get(key), (type(None), dict))
        for key in ("Links", "Aliases", "DNSNames"):
            _empty(detail.get(key), (type(None), list))
        if "GwPriority" in detail:
            _integer(detail["GwPriority"], 0)


@dataclass(frozen=True, slots=True)
class StoppedContainerObservation:
    """Supplied daemon metadata only; no readiness or execution capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def observation_id(self) -> str:
        return "generated-repair-stopped-container-observation-" + identity(self.to_dict())


def validate_stopped_container(
    plan: ContainerCreatePlan | dict,
    raw: str,
    *,
    container_id: str,
    image_environment: list[str],
) -> StoppedContainerObservation:
    """Compare one bounded Engine object or one-element CLI array, without I/O.

    All expectations remain caller-supplied declarations. The adapter must still
    own this exact container, freshly check staging/Engine/image identities, and
    enforce original time/output/cleanup budgets independently of these reports.
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
    architecture = profile["platform"].split("/")[1]
    if platform["os"] != "linux" or platform["architecture"] != architecture:
        raise _invalid()
    if platform.get("variant", "") not in (("", "v8") if architecture == "arm64" else ("",)):
        raise _invalid()
    host = _host(value["HostConfig"], data, value["Mounts"])
    _network(value["NetworkSettings"], role == "B")
    projection = {
        "schema_version": "1.0",
        "kind": "generated-repair-stopped-container-observation",
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
        "execution_authorized": False,
        "generated_runtime_invoked": False,
        "verified_fix": False,
        "pending": [
            "fresh-staging-engine-and-image-identities",
            "effective-runtime-enforcement",
            "attach-before-start-and-original-shared-budgets",
            "confirmed-owned-cleanup",
        ],
    }
    result = canonical(projection)
    decode(result)
    return StoppedContainerObservation(result)
