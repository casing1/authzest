"""Supplied synthetic inspect reports only; no Engine or generated execution."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.runner._generated_repair_container_inspect import validate_stopped_container
from authzest.runner._generated_repair_runtime_profile import (
    ContainerCreatePlan,
    build_container_create_plan,
    validate_runtime_profile,
)
from test_generated_repair_runtime_profile import no_external_effects, profile_data  # noqa: F401

CID = "d" * 64
ENVIRONMENT = ["PATH=/usr/local/bin:/usr/bin", "LANG=C.UTF-8", "PYTHON_VERSION=3.12.16"]
ZERO_TIME = "0001-01-01T00:00:00Z"


def example(role="T", architecture="arm64"):
    declaration = profile_data()
    declaration["platform"] = "linux/" + architecture
    declaration["engine"]["api_version"] = "1.51"
    profile = validate_runtime_profile(canonical(declaration))
    options = {"session_nonce": "8" * 32, "role_nonce": "9" * 32}
    if role == "B":
        options.update(application_container_id="a" * 64, remaining_ms=1234)
    else:
        options.update(staging_root="/reviewed/staged-inputs", application_sha256="b" * 64)
        if role == "T":
            options["test_sha256"] = "c" * 64
    plan = build_container_create_plan(profile, role, **options)
    data, small = plan.to_dict(), role == "B"
    image = declaration["images"][role]["image_id"]
    command = [
        "-I",
        "-B",
        "/opt/authzest-guest/"
        + {"T": "test_launcher.py", "A": "app_launcher.py", "B": "relay_launcher.py"}[role],
    ] + (["1234"] if small else [])
    value = {
        "Id": CID,
        "Name": "/" + data["owned_name"],
        "Image": image,
        "Platform": "linux",
        "Path": "/usr/local/bin/python",
        "Args": command,
        "RestartCount": 0,
        "State": {
            "Status": "created",
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "Dead": False,
            "OOMKilled": False,
            "Pid": 0,
            "ExitCode": 0,
            "Error": "",
            "StartedAt": ZERO_TIME,
            "FinishedAt": ZERO_TIME,
        },
        "Config": {
            "Image": image,
            "User": "65532:65532",
            "WorkingDir": "/tmp",
            "Entrypoint": ["/usr/local/bin/python"],
            "Cmd": command,
            "Env": ENVIRONMENT[:],
            "Healthcheck": {"Test": ["NONE"]},
            "Volumes": None,
            "OpenStdin": False,
            "AttachStdin": False,
            "AttachStdout": True,
            "AttachStderr": True,
            "StdinOnce": False,
            "Tty": False,
            "Labels": {
                "org.authzest.generated.session": "8" * 32,
                "org.authzest.generated.role": role,
                "org.authzest.generated.nonce": "9" * 32,
            },
        },
        "HostConfig": {
            "Privileged": False,
            "ReadonlyRootfs": True,
            "PublishAllPorts": False,
            "AutoRemove": False,
            "Init": False,
            "CapAdd": None,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "PidMode": "",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "UTSMode": "",
            "UsernsMode": "",
            "Runtime": "runc",
            "Isolation": "",
            "CgroupParent": "",
            "Cgroup": "",
            "LogConfig": {"Type": "none", "Config": {}},
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "NetworkMode": "container:" + "a" * 64 if small else "none",
            "Binds": None,
            "VolumesFrom": None,
            "PortBindings": {},
            "Devices": [],
            "DeviceRequests": None,
            "DeviceCgroupRules": None,
            "GroupAdd": None,
            "Links": None,
            "Dns": None,
            "DnsOptions": [],
            "DnsSearch": [],
            "ExtraHosts": None,
            "Memory": 134_217_728 if small else 536_870_912,
            "MemorySwap": 134_217_728 if small else 536_870_912,
            "NanoCpus": 500_000_000 if small else 1_000_000_000,
            "PidsLimit": 32 if small else 64,
            "ShmSize": 8_388_608,
            "MemoryReservation": 0,
            "MemorySwappiness": None,
            "OomKillDisable": False,
            "OomScoreAdj": 0,
            "CpuPeriod": 0,
            "CpuQuota": 0,
            "CpuShares": 0,
            "CpuRealtimePeriod": 0,
            "CpuRealtimeRuntime": 0,
            "CpuCount": 0,
            "CpuPercent": 0,
            "CpusetCpus": "",
            "CpusetMems": "",
            "Ulimits": [],
            "MaskedPaths": [
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
            ],
            "ReadonlyPaths": [
                "/proc/bus",
                "/proc/fs",
                "/proc/irq",
                "/proc/sys",
                "/proc/sysrq-trigger",
            ],
            "Tmpfs": {
                "/tmp": "rw,noexec,nosuid,nodev,size="
                + str(8_388_608 if small else 33_554_432)
                + ",uid=65532,gid=65532,mode=0700"
            },
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": entry["source"],
                    "Target": entry["target"],
                    "ReadOnly": True,
                    "BindOptions": {"Propagation": "rprivate"},
                }
                for entry in data["declared_files"]
            ],
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": entry["source"],
                "Destination": entry["target"],
                "RW": False,
                "Propagation": "rprivate",
                "Mode": "",
            }
            for entry in data["declared_files"]
        ],
        "NetworkSettings": {
            "Ports": {},
            "SandboxID": "",
            "SandboxKey": "",
            "Networks": {}
            if small
            else {
                "none": {
                    "NetworkID": "",
                    "EndpointID": "",
                    "Gateway": "",
                    "IPAddress": "",
                    "MacAddress": "",
                    "IPPrefixLen": 0,
                    "IPv6Gateway": "",
                    "GlobalIPv6Address": "",
                    "GlobalIPv6PrefixLen": 0,
                }
            },
        },
        "ImageManifestDescriptor": {
            "digest": image,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "size": 2048,
            "platform": {"os": "linux", "architecture": architecture},
        },
    }
    return plan, value


def validate(plan, value, **options):
    return validate_stopped_container(
        plan,
        canonical(value),
        container_id=options.get("container_id", CID),
        image_environment=options.get("image_environment", ENVIRONMENT),
    )


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("architecture", ["amd64", "arm64"])
def test_stopped_report_matches_only_declarations_and_cannot_establish_isolation(
    role, architecture
):
    plan, value = example(role, architecture)
    result = validate(plan, value)
    data = result.to_dict()
    assert data["status"] == "daemon-reported-stopped-config-match"
    assert data["role"] == role and data["platform"] == "linux/" + architecture
    assert data["plan_id"] == plan.plan_id and data["never_started_reported"] is True
    assert data["inspect_sha256"] == sha256(canonical(value).encode()).hexdigest()
    for key in (
        "effective_kernel_isolation_verified",
        "effective_mounts_verified",
        "seccomp_enforcement_verified",
        "resource_enforcement_established",
        "ready",
        "runtime_ready",
        "execution_authorized",
        "generated_runtime_invoked",
        "verified_fix",
    ):
        assert data[key] is False
    assert data["provenance"] == "caller-supplied-unverified"
    data["ready"] = True
    assert result.to_dict()["ready"] is False
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"


@pytest.mark.parametrize(
    "path,bad",
    [
        (("Id",), "e" * 64),
        (("Name",), "/unowned"),
        (("Image",), "sha256:" + "f" * 64),
        (("Platform",), "windows"),
        (("RestartCount",), True),
        (("Path",), "/bin/sh"),
        (("Args",), []),
        (("State", "Status"), "exited"),
        (("State", "Running"), True),
        (("State", "Paused"), True),
        (("State", "Pid"), True),
        (("State", "Pid"), 1),
        (("State", "ExitCode"), 1),
        (("State", "StartedAt"), "2026-01-01T00:00:00Z"),
        (("State", "OOMKilled"), True),
        (("State", "Error"), "failed"),
        (("Config", "User"), "root"),
        (("Config", "WorkingDir"), "/input"),
        (("Config", "Entrypoint"), ["/bin/sh"]),
        (("Config", "Cmd"), ["app.py"]),
        (("Config", "Env"), []),
        (("Config", "Labels", "org.authzest.generated.nonce"), "0" * 32),
        (("Config", "AttachStdout"), False),
        (("Config", "OpenStdin"), True),
        (("Config", "Tty"), True),
        (("Config", "Volumes"), {"/var/run/docker.sock": {}}),
        (("Config", "Healthcheck"), {"Test": ["CMD", "curl", "localhost"]}),
        (("HostConfig", "Privileged"), True),
        (("HostConfig", "ReadonlyRootfs"), False),
        (("HostConfig", "Init"), None),
        (("HostConfig", "CapAdd"), ["SYS_ADMIN"]),
        (("HostConfig", "CapDrop"), []),
        (("HostConfig", "SecurityOpt"), ["seccomp:unconfined"]),
        (("HostConfig", "PidMode"), "host"),
        (("HostConfig", "IpcMode"), "host"),
        (("HostConfig", "CgroupnsMode"), "host"),
        (("HostConfig", "UsernsMode"), "host"),
        (("HostConfig", "UTSMode"), "host"),
        (("HostConfig", "Runtime"), "unknown-runtime"),
        (("HostConfig", "CgroupParent"), "/caller"),
        (("HostConfig", "Binds"), ["/:/host"]),
        (("HostConfig", "VolumesFrom"), ["unowned"]),
        (("HostConfig", "Devices"), [{}]),
        (("HostConfig", "DeviceRequests"), [{}]),
        (("HostConfig", "GroupAdd"), ["0"]),
        (("HostConfig", "NetworkMode"), "bridge"),
        (("HostConfig", "PortBindings"), {"80/tcp": [{}]}),
        (("HostConfig", "PublishAllPorts"), True),
        (("HostConfig", "Dns"), ["1.1.1.1"]),
        (("HostConfig", "LogConfig"), {"Type": "json-file", "Config": {}}),
        (("HostConfig", "RestartPolicy"), {"Name": "always", "MaximumRetryCount": 0}),
        (("HostConfig", "AutoRemove"), True),
        (("HostConfig", "Memory"), 0),
        (("HostConfig", "MemorySwap"), -1),
        (("HostConfig", "NanoCpus"), 0),
        (("HostConfig", "PidsLimit"), -1),
        (("HostConfig", "ShmSize"), 67_108_864),
        (("HostConfig", "OomKillDisable"), True),
        (("HostConfig", "CpuQuota"), 1),
        (("HostConfig", "MaskedPaths"), []),
        (("HostConfig", "ReadonlyPaths"), []),
        (("HostConfig", "Tmpfs"), {}),
        (("Mounts",), []),
        (("NetworkSettings", "Ports"), {"80/tcp": [{}]}),
        (("NetworkSettings", "Networks", "none", "IPAddress"), "172.18.0.2"),
        (("ImageManifestDescriptor", "digest"), "sha256:" + "f" * 64),
        (("ImageManifestDescriptor", "platform", "architecture"), "amd64"),
    ],
)
def test_security_identity_state_resource_and_network_mismatches_refuse(path, bad):
    plan, value = example()
    target = value
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = bad
    with pytest.raises(ContractError):
        validate(plan, value)


@pytest.mark.parametrize(
    "change",
    [
        "configured-source",
        "resolved-source",
        "readonly",
        "rw",
        "propagation",
        "duplicate",
        "unknown-option",
        "tmpfs-duplicate",
        "tmpfs-unknown",
        "tmpfs-uid",
        "health-unknown",
    ],
)
def test_mount_and_option_normalization_has_no_alias_or_duplicate_fallback(change):
    plan, value = example()
    host = value["HostConfig"]
    if change == "configured-source":
        host["Mounts"][0]["Source"] = "/other/app.py"
    elif change == "resolved-source":
        value["Mounts"][0]["Source"] = "/alias/reviewed/staged-inputs/app.py"
    elif change == "readonly":
        host["Mounts"][0]["ReadOnly"] = False
    elif change == "rw":
        value["Mounts"][0]["RW"] = True
    elif change == "propagation":
        value["Mounts"][0]["Propagation"] = "rshared"
    elif change == "duplicate":
        host["Mounts"][1] = copy.deepcopy(host["Mounts"][0])
    elif change == "unknown-option":
        host["Mounts"][0]["BindOptions"]["Unreviewed"] = True
    elif change == "tmpfs-duplicate":
        host["Tmpfs"]["/tmp"] += ",rw"
    elif change == "tmpfs-unknown":
        host["Tmpfs"]["/tmp"] += ",exec"
    elif change == "tmpfs-uid":
        host["Tmpfs"]["/tmp"] = host["Tmpfs"]["/tmp"].replace("uid=65532", "uid=0")
    else:
        value["Config"]["Healthcheck"]["Unreviewed"] = True
    with pytest.raises(ContractError):
        validate(plan, value)


def test_known_normalizations_and_irrelevant_display_metadata_are_accepted_without_leaking_them():
    plan, value = example()
    value["HostConfig"]["SecurityOpt"] = ["no-new-privileges=true"]
    value["HostConfig"]["Tmpfs"]["/tmp"] = ",".join(
        reversed(value["HostConfig"]["Tmpfs"]["/tmp"].split(","))
    )
    value["HostConfig"]["MaskedPaths"].reverse()
    value["Config"]["Healthcheck"]["Interval"] = 0
    value["UnrelatedDisplayField"] = "synthetic-ignored-text"
    result = validate_stopped_container(
        plan.to_dict(), canonical([value]), container_id=CID, image_environment=ENVIRONMENT
    )
    assert result.to_dict()["never_started_reported"] is True
    assert "synthetic-ignored-text" not in result.payload_json


@pytest.mark.parametrize("change", ["wrong-target", "self-target", "extra-mount", "role-size"])
def test_relay_binds_only_declared_application_namespace_without_source_mounts(change):
    plan, value = example("B")
    cid = CID
    if change == "wrong-target":
        value["HostConfig"]["NetworkMode"] = "container:" + "b" * 64
    elif change == "self-target":
        cid = "a" * 64
        value["Id"] = cid
    elif change == "extra-mount":
        value["Mounts"].append({"Type": "bind", "Source": "/secret", "Destination": "/input"})
    else:
        value["HostConfig"]["Memory"] = 536_870_912
    with pytest.raises(ContractError):
        validate(plan, value, container_id=cid)


@pytest.mark.parametrize(
    "change", ["argv", "declared-hash", "name", "readiness", "profile", "wrapper"]
)
def test_forged_plans_are_reconstructed_rather_than_trusted(change):
    plan, value = example()
    data = plan.to_dict()
    if change == "argv":
        data["argv"].append("--privileged")
    elif change == "declared-hash":
        data["declared_files"][0]["sha256"] = "x" * 64
    elif change == "name":
        data["owned_name"] = "caller"
    elif change == "readiness":
        data["execution_authorized"] = True
    elif change == "profile":
        data["profile"]["images"]["T"]["assets"]["test_launcher.py"] = "0" * 64
    else:
        data = ContainerCreatePlan("{}")
    with pytest.raises(ContractError):
        validate(data, value)


@pytest.mark.parametrize(
    "change", ["oversized", "deep", "duplicate", "empty-list", "two-list", "missing"]
)
def test_bounded_json_cannot_hide_missing_duplicate_or_multiple_inspections(change):
    plan, value = example()
    raw = canonical(value)
    if change == "oversized":
        raw += " " * 65_537
    elif change == "deep":
        raw = '{"x":' + "[" * 17 + "0" + "]" * 17 + "}"
    elif change == "duplicate":
        raw = raw.replace('"Id":', '"Id":"untrusted","Id":', 1)
    elif change == "empty-list":
        raw = "[]"
    elif change == "two-list":
        raw = canonical([value, value])
    else:
        del value["HostConfig"]["Init"]
        raw = canonical(value)
    with pytest.raises(ContractError):
        validate_stopped_container(plan, raw, container_id=CID, image_environment=ENVIRONMENT)


@pytest.mark.parametrize(
    "environment", [None, ["NO_EQUALS"], ["PATH=a", "PATH=b"], ["X=bad\nvalue"]]
)
def test_expected_environment_is_bounded_and_unambiguous(environment):
    plan, value = example()
    with pytest.raises(ContractError):
        validate(plan, value, image_environment=environment)


@pytest.mark.parametrize(
    "path,bad",
    [
        (("State",), []),
        (("Config",), False),
        (("Config", "Labels"), []),
        (("HostConfig", "Mounts"), {}),
        (("HostConfig", "Tmpfs"), []),
        (("HostConfig", "VolumeDriver"), "unreviewed"),
        (("HostConfig", "SecurityOpt"), [{"unreviewed": True}]),
        (("ImageManifestDescriptor", "mediaType"), []),
        (("ImageManifestDescriptor", "platform"), []),
        (("NetworkSettings", "Networks", "none", "IPAMConfig"), {"IPv4Address": "172.18.0.2"}),
        (("NetworkSettings", "Networks", "none", "Aliases"), ["unreviewed"]),
    ],
)
def test_non_native_or_ambiguous_critical_shapes_fail_with_the_closed_contract(path, bad):
    plan, value = example()
    selected = value
    for component in path[:-1]:
        selected = selected[component]
    selected[path[-1]] = bad
    with pytest.raises(ContractError):
        validate(plan, value)
