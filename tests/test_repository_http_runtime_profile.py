"""Inert A/B HTTP profile/manifest checks; no Engine, guest or target run."""

from __future__ import annotations

import asyncio
import builtins
import copy
import json
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner import _repository_http_manifest as manifests
from authzest.runner import _repository_http_runtime_profile as runtime
from authzest.runner._repository_runtime_profile import RepositoryRuntimeProfile as OldProfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = b"from fastapi import FastAPI\napp = FastAPI()\n"
ASSET_PATHS = {
    "A": {
        "_guest_common.py": "runtime/repository_http/_guest_common.py",
        "repository_http_manifest.py": "src/authzest/runner/_repository_http_manifest.py",
        "app_launcher.py": "runtime/repository_http/app_launcher.py",
    },
    "B": {
        "_guest_common.py": "runtime/repository_http/_guest_common.py",
        "repository_http.py": "src/authzest/runner/_repository_http.py",
        "repository_http_transport.py": "src/authzest/runner/_repository_http_transport.py",
        "relay_launcher.py": "runtime/repository_http/relay_launcher.py",
    },
}
ASSETS = {
    role: {name: sha256((ROOT / path).read_bytes()).hexdigest() for name, path in paths.items()}
    for role, paths in ASSET_PATHS.items()
}
IMAGE_ROOT = ROOT / "runtime/repository_http/images"
IMAGE_INPUTS = json.loads((IMAGE_ROOT / "manifest.json").read_text())
IMAGE_FILES = {
    role: {
        "dockerfile": sha256((IMAGE_ROOT / entry["dockerfile"]).read_bytes()).hexdigest(),
        "lock": sha256((ROOT / entry["dependency_lock_path"]).read_bytes()).hexdigest(),
    }
    for role, role_data in IMAGE_INPUTS["roles"].items()
    for entry in [role_data["platforms"]["linux/arm64"]]
}
BASE_REFERENCE = sha256((ROOT / IMAGE_INPUTS["base_reference"]).read_bytes()).hexdigest()


def manifest():
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
    return manifests.build_guest_manifest(
        "repository-http-proposal-request-" + "a" * 64,
        interface,
        {"path": "main.py", "sha256": sha256(SOURCE).hexdigest(), "size_bytes": len(SOURCE)},
    )


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
            "config_json_sha256": runtime.EMPTY_CONFIG_SHA256,
            "server_identity_sha256": "2" * 64,
            "api_version": "1.47",
        },
        "images": {
            role: {
                "image_id": "sha256:" + ("3" if role == "A" else "4") * 64,
                **runtime.expected_recipe_pins("linux/arm64", role),
                "assets": runtime.expected_assets(role),
            }
            for role in ("A", "B")
        },
    }


def schedule():
    return {
        "schema_version": "2.0",
        "kind": "repository-http-observer-schedule",
        "plan_id": "repository-http-verification-plan-" + "b" * 64,
        "phase": "before",
        "requests": [
            {
                "case_id": str(i),
                "method": "GET",
                "path": "/notes/one",
                "headers": {"x-user-id": "test-owner"},
            }
            for i in range(4)
        ],
    }


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Runtime declarations must remain inert")

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


def test_manifest_and_profile_are_distinct_detached_declarations():
    data = manifest()
    assert manifests.validate_guest_manifest(canonical(data).encode()) == data
    assert manifests.expected_input_paths(data) == (
        "/input/manifest.json",
        "/input/project/main.py",
    )
    assert not {"test", "test_interface", "fixture", "source_files"} & data.keys()
    detached = manifests.validate_guest_manifest(data)
    detached["source"]["path"] = "other.py"
    assert data["source"]["path"] == "main.py"
    profile = runtime.validate_runtime_profile(canonical(profile_data()))
    assert profile.provenance == "caller-supplied-unverified"
    assert profile.profile_id.startswith("repository-http-runtime-profile-")
    with pytest.raises(FrozenInstanceError):
        profile.payload_json = "{}"


@pytest.mark.parametrize(
    "change",
    [
        "legacy-request",
        "legacy-interface",
        "nested",
        "keyword",
        "init",
        "bool-size",
        "zero-size",
        "oversize",
        "bad-hash",
        "factory",
        "src",
        "test-field",
        "stale-id",
    ],
)
def test_manifest_refuses_old_or_wider_material_even_if_rehashed(change):
    data = manifest()
    if change == "legacy-request":
        data["request_id"] = "repository-test-proposal-request-" + "a" * 64
    elif change == "legacy-interface":
        data["http_interface"]["interface_id"] = "repository-test-interface-" + "a" * 64
    elif change in {"nested", "keyword", "init"}:
        path = {"nested": "pkg/main.py", "keyword": "class.py", "init": "__init__.py"}[change]
        data["source"]["path"] = data["http_interface"]["entry_source"] = path
        data["http_interface"]["module"] = path.removesuffix(".py")
    elif change == "bool-size":
        data["source"]["size_bytes"] = True
    elif change == "zero-size":
        data["source"]["size_bytes"] = 0
    elif change == "oversize":
        data["source"]["size_bytes"] = 16385
    elif change == "bad-hash":
        data["source"]["sha256"] = "A" * 64
    elif change == "factory":
        data["http_interface"]["app_attribute"] = "create_app()"
    elif change == "src":
        data["http_interface"]["import_root"] = "src"
    elif change == "test-field":
        data["test"] = None
    else:
        data["source"]["sha256"] = "c" * 64
        with pytest.raises(ValueError):
            manifests.validate_guest_manifest(data)
        return
    body = {key: value for key, value in data["http_interface"].items() if key != "interface_id"}
    if change != "legacy-interface":
        data["http_interface"]["interface_id"] = "repository-http-interface-" + identity(body)
    data["manifest_id"] = "repository-http-guest-input-" + identity(
        {k: v for k, v in data.items() if k != "manifest_id"}
    )
    with pytest.raises(ValueError):
        manifests.validate_guest_manifest(data)


@pytest.mark.parametrize("kind", ["duplicates", "noncanonical", "oversize", "invalid", "nonfinite"])
def test_manifest_json_is_closed_and_bounded(kind):
    raw = canonical(manifest())
    if kind == "duplicates":
        raw = raw[:-1] + ',"schema_version":"2.0"}'
    elif kind == "noncanonical":
        raw += "\n"
    elif kind == "oversize":
        raw = "x" * 16385
    elif kind == "invalid":
        raw = "{"
    else:
        raw = '{"value":NaN}'
    with pytest.raises(ValueError):
        manifests.validate_guest_manifest(raw)


@pytest.mark.parametrize("kind", ["oversized", "wrong-type", "wrong-digest", "old-prefix"])
def test_bad_manifest_identity_is_rejected_before_serializing_supplied_object(monkeypatch, kind):
    data = manifest()
    if kind == "oversized":
        data["manifest_id"] = "repository-http-guest-input-" + "a" * 100_000
    elif kind == "wrong-type":
        data["manifest_id"] = {"oversized": "a" * 100_000}
    elif kind == "wrong-digest":
        data["manifest_id"] = "repository-http-guest-input-" + "0" * 64
    else:
        data["manifest_id"] = "repository-guest-input-" + "0" * 64
    canonical = manifests._canonical
    calls = []

    def checked(value):
        assert value is not data, "Unvalidated supplied identity reached serialization"
        calls.append(value)
        return canonical(value)

    monkeypatch.setattr(manifests, "_canonical", checked)
    with pytest.raises(ValueError):
        manifests.validate_guest_manifest(data)
    if kind != "wrong-digest":
        assert calls == []


def test_static_image_declarations_bind_only_new_assets_and_unchanged_dependencies():
    assert set(IMAGE_INPUTS["roles"]) == {"A", "B"}
    assert IMAGE_INPUTS["schema_version"] == "2.0"
    assert IMAGE_INPUTS["kind"] == "repository-http-image-inputs"
    assert IMAGE_INPUTS["image_ids"] is None
    assert IMAGE_INPUTS["runtime_ready"] is IMAGE_INPUTS["contents_verified"] is False
    assert IMAGE_INPUTS["base_reference_sha256"] == BASE_REFERENCE
    for role in ("A", "B"):
        entry = IMAGE_INPUTS["roles"][role]["platforms"]["linux/arm64"]
        assert set(IMAGE_INPUTS["roles"][role]["platforms"]) == {"linux/arm64"}
        assert (
            IMAGE_INPUTS["roles"][role]["assets"] == runtime.expected_assets(role) == ASSETS[role]
        )
        assert entry["dockerfile_sha256"] == IMAGE_FILES[role]["dockerfile"]
        assert entry["dependency_lock_sha256"] == IMAGE_FILES[role]["lock"]
        assert entry["recipe_sha256"] == identity(
            {k: v for k, v in entry.items() if k != "recipe_sha256"}
        )
        assert runtime.expected_recipe_pins("linux/arm64", role) == {
            "dependency_lock_sha256": entry["dependency_lock_sha256"],
            "recipe_sha256": entry["recipe_sha256"],
        }


def test_create_A_has_only_exact_readonly_manifest_and_source_mounts():
    profile = runtime.validate_runtime_profile(canonical(profile_data()))
    plan = runtime.build_container_create_plan(
        profile,
        "A",
        session_nonce="5" * 32,
        role_nonce="6" * 32,
        staging_root="/private/sealed/input",
        manifest=manifest(),
    )
    data = plan.to_dict()
    assert data["role"] == "A" and data["stdin"] is None
    assert [f["target"] for f in data["declared_files"]] == [
        "/input/manifest.json",
        "/input/project/main.py",
    ]
    assert len([arg for arg in data["argv"] if arg.startswith("--mount=")]) == 2
    assert "--network=none" in data["argv"]
    assert "--interactive=false" in data["argv"]
    assert data["argv"][-1] == "/opt/authzest-repository-http-guest/app_launcher.py"
    assert data["owned_name"].startswith("authzest-repository-http-")
    assert "--label=org.authzest.repository-http.role=A" in data["argv"]
    assert data["status"] == "planned-not-executed"
    assert data["runtime_invoked"] is data["execution_authorized"] is data["verified_fix"] is False
    assert data["authorization_status"] == "unknown"
    assert data["budgets"]["phase_seconds"] == 40 and data["budgets"]["cleanup_seconds"] == 10
    assert data["budgets"]["setup_seconds"] == 10
    assert SOURCE.decode() not in canonical(data)


def test_create_B_receives_only_schedule_and_A_network_namespace():
    profile = runtime.validate_runtime_profile(canonical(profile_data()))
    plan = runtime.build_container_create_plan(
        profile,
        "B",
        session_nonce="5" * 32,
        role_nonce="6" * 32,
        application_container_id="7" * 64,
        remaining_ms=12345,
        schedule=schedule(),
    )
    data = plan.to_dict()
    assert data["declared_files"] == [] and data["input_manifest"] is None
    assert data["stdin"]["value"] == schedule() and data["stdin"]["eof_required"] is True
    assert data["stdin"]["sha256"] == sha256(canonical(schedule()).encode()).hexdigest()
    assert not any(arg.startswith("--mount=") for arg in data["argv"])
    assert "--network=container:" + "7" * 64 in data["argv"]
    assert "--interactive=true" in data["argv"]
    assert data["argv"][-2:] == ["/opt/authzest-repository-http-guest/relay_launcher.py", "12345"]
    assert not any(arg.startswith(("--pid=", "--volume", "--publish=")) for arg in data["argv"])
    assert data["budgets"]["memory_bytes"] == 134217728 and data["budgets"]["pid_limit"] == 32
    detached = plan.to_dict()
    detached["stdin"]["value"]["requests"].clear()
    assert len(plan.to_dict()["stdin"]["value"]["requests"]) == 4


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "kind",
        "platform",
        "extra-T",
        "missing-B",
        "image",
        "asset",
        "recipe",
        "lock",
        "config",
        "endpoint",
        "overlap",
        "api",
    ],
)
def test_profile_rejects_wider_or_drifted_declarations(change):
    data = profile_data()
    if change == "version":
        data["schema_version"] = "1.0"
    elif change == "kind":
        data["kind"] = "repository-runtime-profile"
    elif change == "platform":
        data["platform"] = "linux/amd64"
    elif change == "extra-T":
        data["images"]["T"] = copy.deepcopy(data["images"]["A"])
    elif change == "missing-B":
        del data["images"]["B"]
    elif change == "image":
        data["images"]["A"]["image_id"] = "sha256:" + "A" * 64
    elif change == "asset":
        data["images"]["A"]["assets"]["app_launcher.py"] = "0" * 64
    elif change == "recipe":
        data["images"]["A"]["recipe_sha256"] = "0" * 64
    elif change == "lock":
        data["images"]["A"]["dependency_lock_sha256"] = "0" * 64
    elif change == "config":
        data["engine"]["config_json_sha256"] = "0" * 64
    elif change == "endpoint":
        data["engine"]["endpoint"] = "tcp://127.0.0.1:2375"
    elif change == "overlap":
        data["engine"]["config_dir"] = "/usr/local/bin"
    else:
        data["engine"]["api_version"] = "1.40"
    with pytest.raises(ContractError):
        runtime.validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    "change",
    [
        "old-type",
        "T",
        "path-space",
        "path-comma",
        "B-source",
        "B-empty-id",
        "B-zero-ms",
        "B-too-long",
        "B-bool-ms",
        "A-stdin",
        "nonce",
    ],
)
def test_create_plan_refuses_ambiguous_or_wrong_role_inputs(change):
    profile = runtime.validate_runtime_profile(canonical(profile_data()))
    role = "A"
    args = {
        "session_nonce": "5" * 32,
        "role_nonce": "6" * 32,
        "staging_root": "/private/sealed/input",
        "manifest": manifest(),
    }
    if change == "old-type":
        profile = OldProfile(profile.payload_json)
    elif change == "T":
        role = "T"
    elif change == "path-space":
        args["staging_root"] = "/private/sealed space"
    elif change == "path-comma":
        args["staging_root"] = "/private/sealed,input"
    elif change == "A-stdin":
        args["schedule"] = schedule()
    elif change == "nonce":
        args["session_nonce"] = "5" * 31
    else:
        role = "B"
        args = {
            "session_nonce": "5" * 32,
            "role_nonce": "6" * 32,
            "application_container_id": "7" * 64,
            "remaining_ms": 40000,
            "schedule": schedule(),
        }
        if change == "B-source":
            args["staging_root"] = "/private/sealed/input"
        elif change == "B-empty-id":
            args["application_container_id"] = ""
        elif change == "B-zero-ms":
            args["remaining_ms"] = 0
        elif change == "B-too-long":
            args["remaining_ms"] = 40001
        else:
            args["remaining_ms"] = True
    with pytest.raises((ContractError, ValueError)):
        runtime.build_container_create_plan(profile, role, **args)
