"""Supplied synthetic HTTP inspections only; no Engine or target execution."""

from __future__ import annotations

import asyncio
import builtins
import copy
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
from tests.helpers.repository_http_container_data import CID, ENVIRONMENT, example

from authzest.codex.contracts import ContractError, canonical
from authzest.runner._generated_repair_runtime_profile import ContainerCreatePlan as LegacyPlan
from authzest.runner._repository_http_container_inspect import validate_stopped_container
from authzest.runner._repository_http_runtime_profile import RepositoryHttpCreatePlan


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Supplied stopped metadata must remain inert")

    for owner, names in (
        (builtins, ("open", "eval", "exec")),
        (os, ("open", "system")),
        (subprocess, ("Popen",)),
        (socket, ("socket", "create_connection")),
        (asyncio, ("create_subprocess_exec", "create_subprocess_shell")),
        (Path, ("open", "read_bytes", "read_text", "write_bytes", "write_text")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)


def validate(plan, value, **options):
    return validate_stopped_container(
        plan,
        canonical(value),
        container_id=options.get("container_id", CID),
        image_environment=options.get("image_environment", ENVIRONMENT),
    )


@pytest.mark.parametrize("role", ["A", "B"])
def test_stopped_report_matches_only_declarations_and_cannot_establish_isolation(role):
    plan, value = example(role)
    result = validate(plan, value)
    data = result.to_dict()
    assert data["status"] == "daemon-reported-stopped-config-match"
    assert data["role"] == role and data["platform"] == "linux/arm64"
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
        (("Config", "Labels", "org.authzest.repository-http.nonce"), "0" * 32),
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
        plan, canonical([value]), container_id=CID, image_environment=ENVIRONMENT
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
        data["profile"]["images"]["A"]["assets"]["app_launcher.py"] = "0" * 64
    else:
        data = RepositoryHttpCreatePlan("{}")
    with pytest.raises(ContractError):
        validate(RepositoryHttpCreatePlan(canonical(data)) if type(data) is dict else data, value)


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


@pytest.mark.parametrize("role", ["A", "B"])
@pytest.mark.parametrize("field", ["OpenStdin", "AttachStdin", "StdinOnce"])
def test_only_relay_is_interactive_and_closes_stdin_at_attached_client_disconnect(role, field):
    plan, value = example(role)
    assert value["Config"][field] is (role == "B")
    value["Config"][field] = role != "B"
    with pytest.raises(ContractError):
        validate(plan, value)


@pytest.mark.parametrize("change", ["manifest-only", "source-only", "root-mount", "test-mount"])
def test_application_has_exactly_manifest_and_selected_flat_source_mounts(change):
    plan, value = example("A")
    data = plan.to_dict()
    assert [entry["target"] for entry in data["declared_files"]] == [
        "/input/manifest.json",
        "/input/project/main.py",
    ]
    if change in {"manifest-only", "source-only"}:
        index = 0 if change == "manifest-only" else 1
        value["HostConfig"]["Mounts"] = value["HostConfig"]["Mounts"][index : index + 1]
        value["Mounts"] = value["Mounts"][index : index + 1]
    else:
        index = 0 if change == "root-mount" else 1
        target = "/input" if change == "root-mount" else "/input/test_generated.py"
        value["HostConfig"]["Mounts"][index]["Target"] = target
        value["Mounts"][index]["Destination"] = target
    with pytest.raises(ContractError):
        validate(plan, value)


@pytest.mark.parametrize("role", ["A", "B"])
@pytest.mark.parametrize("change", ["dict", "legacy", "duck", "subclass"])
def test_old_saved_or_lookalike_plans_do_not_cross_the_explicit_http_type(role, change):
    plan, value = example(role)
    if change == "dict":
        supplied = plan.to_dict()
    elif change == "legacy":
        supplied = LegacyPlan(plan.payload_json)
    elif change == "duck":

        class Duck:
            payload_json = plan.payload_json

            def to_dict(self):
                pytest.fail("A duck plan was consulted")

        supplied = Duck()
    else:

        class Subclass(RepositoryHttpCreatePlan):
            pass

        supplied = Subclass(plan.payload_json)
    with pytest.raises(ContractError):
        validate(supplied, value)


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "role-T",
        "missing-manifest",
        "manifest-hash",
        "manifest-size",
        "source-hash",
        "source-size",
        "staging-root",
        "source-target",
        "extra-file",
        "profile-id",
        "budget",
        "environment",
        "stdin",
        "pending",
        "plan-kind",
    ],
)
def test_complete_application_plan_is_reconstructed_before_comparison(change):
    plan, value = example("A")
    data = plan.to_dict()
    if change == "schema":
        data["schema_version"] = "1.0"
    elif change == "role-T":
        data["role"] = "T"
    elif change == "missing-manifest":
        data["input_manifest"] = None
    elif change in {"manifest-hash", "manifest-size", "source-hash", "source-size"}:
        item = data["declared_files"][int(change.startswith("source"))]
        item["sha256" if change.endswith("hash") else "utf8_bytes"] = (
            "b" * 64 if change.endswith("hash") else 1
        )
    elif change == "staging-root":
        data["declared_files"][0]["source"] = "/other/manifest.json"
    elif change == "source-target":
        data["declared_files"][1]["target"] = "/input/project/app.py"
    elif change == "extra-file":
        data["declared_files"].append(copy.deepcopy(data["declared_files"][1]))
    elif change == "profile-id":
        data["profile_id"] = "repository-http-runtime-profile-" + "f" * 64
    elif change == "budget":
        data["budgets"]["phase_seconds"] = 41
    elif change == "environment":
        data["environment"]["DOCKER_HOST"] = "tcp://remote:2375"
    elif change == "stdin":
        data["stdin"] = {}
    elif change == "pending":
        data["pending"] = []
    else:
        data["kind"] = "container-create-plan"
    with pytest.raises(ContractError):
        validate(RepositoryHttpCreatePlan(canonical(data)), value)


@pytest.mark.parametrize(
    "change",
    [
        "schedule-path",
        "schedule-case",
        "schedule-oracle",
        "schedule-count",
        "schedule-kind",
        "stdin-hash",
        "stdin-size",
        "stdin-eof",
        "a-id",
        "duration",
        "manifest",
        "files",
    ],
)
def test_relay_plan_binds_request_schedule_and_explicit_eof_without_mounts(change):
    plan, value = example("B")
    data = plan.to_dict()
    if change in {"schedule-path", "schedule-case"}:
        key = "path" if change == "schedule-path" else "case_id"
        data["stdin"]["value"]["requests"][0][key] = "/changed" if key == "path" else "changed"
    elif change == "schedule-oracle":
        data["stdin"]["value"]["requests"][0]["expected_status"] = 200
    elif change == "schedule-count":
        data["stdin"]["value"]["requests"] = []
    elif change == "schedule-kind":
        data["stdin"]["value"]["kind"] = "generated-test-schedule"
    elif change == "stdin-hash":
        data["stdin"]["sha256"] = "f" * 64
    elif change == "stdin-size":
        data["stdin"]["utf8_bytes"] = True
    elif change == "stdin-eof":
        data["stdin"]["eof_required"] = False
    elif change == "a-id":
        data["application_container_id"] = "b" * 64
    elif change == "duration":
        data["remaining_ms"] = 1200
    elif change == "manifest":
        data["input_manifest"] = {}
    else:
        data["declared_files"] = [{"source": "/secret", "target": "/input"}]
    with pytest.raises(ContractError):
        validate(RepositoryHttpCreatePlan(canonical(data)), value)


@pytest.mark.parametrize("raw", [None, {}, b"{}", "\ud800", '{"State":NaN}', "{}\x00"])
def test_non_text_nonunicode_and_nonfinite_inspect_values_refuse(raw):
    plan, _ = example()
    with pytest.raises(ContractError):
        validate_stopped_container(plan, raw, container_id=CID, image_environment=ENVIRONMENT)


def test_supplied_reports_never_become_current_phase_or_authorization_evidence():
    plan, value = example("B")
    result = validate(plan, value)
    data = result.to_dict()
    assert data["schema_version"] == "2.0"
    assert data["kind"] == "repository-http-stopped-container-observation"
    assert result.observation_id.startswith("repository-http-stopped-container-observation-")
    assert data["authorization_status"] == "unknown"
    assert data["runtime_invoked"] is False
    assert not {"T", "test", "pytest", "session_revision", "checkpoint_id"} & data.keys()
