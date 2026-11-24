"""Owned synthetic HTTP plan/inspect reports, never a daemon or target run."""

from hashlib import sha256

from authzest.codex.contracts import canonical, identity
from authzest.runner._repository_http_manifest import build_guest_manifest
from authzest.runner._repository_http_runtime_profile import (
    EMPTY_CONFIG_SHA256,
    build_container_create_plan,
    expected_assets,
    expected_recipe_pins,
    validate_runtime_profile,
)

CID = "d" * 64
ENVIRONMENT = ["PATH=/usr/local/bin:/usr/bin", "LANG=C.UTF-8", "PYTHON_VERSION=3.12.16"]
MANIFEST_DIGESTS = {"A": "sha256:" + "5" * 64, "B": "sha256:" + "6" * 64}
ZERO_TIME = "0001-01-01T00:00:00Z"


def profile_data():
    return {
        "schema_version": "2.0",
        "kind": "repository-http-runtime-profile",
        "platform": "linux/arm64",
        "engine": {
            "executable": "/usr/local/bin/docker",
            "executable_sha256": "1" * 64,
            "endpoint": "unix:///private/runtime/docker.sock",
            "config_dir": "/private/config",
            "config_json_sha256": EMPTY_CONFIG_SHA256,
            "server_identity_sha256": "2" * 64,
            "api_version": "1.47",
        },
        "images": {
            role: {
                "image_id": "sha256:" + ("3" if role == "A" else "4") * 64,
                **expected_recipe_pins("linux/arm64", role),
                "assets": expected_assets(role),
            }
            for role in ("A", "B")
        },
    }


def manifest():
    source = b'raise RuntimeError("INERT SOURCE MUST NEVER EXECUTE")\n'
    interface = {
        "schema_version": "1.0",
        "entry_source": "main.py",
        "import_root": ".",
        "module": "main",
        "app_attribute": "app",
        "lifespan": "off",
        "auth_overrides": "none",
    }
    interface["interface_id"] = "repository-http-interface-" + identity(interface)
    return build_guest_manifest(
        "repository-http-proposal-request-" + "a" * 64,
        interface,
        {"path": "main.py", "sha256": sha256(source).hexdigest(), "size_bytes": len(source)},
    )


def schedule():
    return {
        "schema_version": "2.0",
        "kind": "repository-http-observer-schedule",
        "plan_id": "repository-http-verification-plan-" + "b" * 64,
        "phase": "before",
        "requests": [
            {"case_id": name, "method": "GET", "path": "/items/one", "headers": {}}
            for name in ("owner", "other", "anonymous", "normal")
        ],
    }


def example(role="A"):
    architecture = "arm64"
    profile = validate_runtime_profile(canonical(profile_data()))
    options = {"session_nonce": "8" * 32, "role_nonce": "9" * 32}
    if role == "B":
        options.update(application_container_id="a" * 64, remaining_ms=1234, schedule=schedule())
    else:
        options.update(staging_root="/reviewed/http-input", manifest=manifest())
    plan = build_container_create_plan(profile, role, **options)
    declaration = profile.to_dict()
    data, small = plan.to_dict(), role == "B"
    image = declaration["images"][role]["image_id"]
    command = [
        "-I",
        "-B",
        "/opt/authzest-repository-http-guest/"
        + {"A": "app_launcher.py", "B": "relay_launcher.py"}[role],
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
            "OpenStdin": small,
            "AttachStdin": small,
            "AttachStdout": True,
            "AttachStderr": True,
            "StdinOnce": small,
            "Tty": False,
            "Labels": {
                "org.authzest.repository-http.session": "8" * 32,
                "org.authzest.repository-http.role": role,
                "org.authzest.repository-http.nonce": "9" * 32,
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
            "digest": MANIFEST_DIGESTS[role],
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "size": 2048,
            "platform": {"os": "linux", "architecture": architecture},
        },
    }
    return plan, value
