"""Pure declared runtime profiles and fixed argv; no Docker or generated code."""

from __future__ import annotations

import asyncio
import builtins
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.runner._generated_repair_runtime_profile import (
    EMPTY_CONFIG_SHA256,
    ContainerCreatePlan,
    RuntimeProfile,
    build_container_create_plan,
    expected_assets,
    validate_runtime_profile,
)

# Read maintained source only during collection, before effect guards. These are
# digest regressions, never imports/compilation of an application or test input.
_REPO = Path(__file__).resolve().parents[1]
_ATTRIBUTES = (_REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
_ASSET_DIGESTS = {
    path.name: sha256(path.read_bytes()).hexdigest()
    for path in (
        _REPO / "runtime/generated_repair/_guest_common.py",
        _REPO / "runtime/generated_repair/test_launcher.py",
        _REPO / "runtime/generated_repair/app_launcher.py",
        _REPO / "runtime/generated_repair/relay_launcher.py",
        _REPO / "src/authzest/runner/_generated_repair_http.py",
    )
}


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch, request):
    assert len(request.node.nodeid) < 512
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        pytest.fail("Runtime declarations must remain data-only")

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app",
            "docker",
            "fastapi",
            "httpx",
            "openai",
            "requests",
            "uvicorn",
        } or name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for name in ("open", "eval", "exec", "compile"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


def profile_data():
    """Clearly synthetic declarations, not observed installed engine/images."""
    return {
        "schema_version": "1.0",
        "kind": "generated-repair-runtime-profile",
        "platform": "linux/arm64",
        "engine": {
            "executable": "/reviewed/bin/docker",
            "executable_sha256": "1" * 64,
            "endpoint": "unix:///reviewed/run/docker.sock",
            "config_dir": "/reviewed/empty-docker-config",
            "config_json_sha256": EMPTY_CONFIG_SHA256,
            "server_identity_sha256": "2" * 64,
            "api_version": "1.45",
        },
        "images": {
            role: {
                "image_id": "sha256:" + digit * 64,
                "dependency_lock_sha256": "6" * 64,
                "recipe_sha256": "7" * 64,
                "assets": expected_assets(role),
            }
            for role, digit in (("T", "3"), ("A", "4"), ("B", "5"))
        },
    }


def profile():
    return validate_runtime_profile(canonical(profile_data()))


def test_expected_assets_are_current_source_bindings_not_image_observations():
    for role in ("T", "A", "B"):
        assets = expected_assets(role)
        assert assets == {name: _ASSET_DIGESTS[name] for name in assets}
        assets.clear()
        assert expected_assets(role)
    assert sha256(b"{}\n").hexdigest() == EMPTY_CONFIG_SHA256


@pytest.mark.parametrize(
    "relative_path",
    [
        "runtime/generated_repair/_guest_common.py",
        "runtime/generated_repair/app_launcher.py",
        "runtime/generated_repair/relay_launcher.py",
        "runtime/generated_repair/test_launcher.py",
        "src/authzest/runner/_generated_repair_http.py",
    ],
)
def test_inventoried_guest_bytes_keep_lf_on_windows_checkout(relative_path):
    assert relative_path + " text eol=lf" in _ATTRIBUTES


def test_profile_is_immutable_canonical_declaration_without_runtime_receipt():
    result = profile()
    assert result.to_dict() == profile_data()
    assert result.profile_id == "generated-repair-runtime-profile-" + identity(profile_data())
    assert result.provenance == "caller-supplied-unverified"
    assert validate_runtime_profile(result.payload_json) == result
    changed = result.to_dict()
    changed["engine"]["endpoint"] = "tcp://not-an-observation"
    assert result.to_dict() == profile_data()
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_stale_guest_asset_hash_is_refused(role):
    data = profile_data()
    assets = data["images"][role]["assets"]
    assets[next(iter(assets))] = "0" * 64
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_fixed_create_data_has_exact_role_inputs_and_no_effects(role):
    parameters = {"session_nonce": "8" * 32, "role_nonce": "9" * 32}
    if role == "B":
        parameters.update(application_container_id="a" * 64, remaining_ms=40000)
    else:
        parameters.update(staging_root="/reviewed/staged-inputs", application_sha256="b" * 64)
        if role == "T":
            parameters["test_sha256"] = "c" * 64
    result = build_container_create_plan(profile(), role, **parameters)
    data = result.to_dict()
    assert data["status"] == "planned-not-executed"
    assert data["provenance"] == "caller-supplied-unverified"
    assert data["runtime_invoked"] is data["execution_authorized"] is data["verified_fix"] is False
    assert data["authorization_status"] == "unknown" and data["pending"]
    assert data["environment"] == {"DOCKER_API_VERSION": "1.45"}
    argv = data["argv"]
    assert argv[:5] == [
        "/reviewed/bin/docker",
        "--config=/reviewed/empty-docker-config",
        "--host=unix:///reviewed/run/docker.sock",
        "container",
        "create",
    ]
    assert "--pull=never" in argv and "--cap-drop=ALL" in argv
    assert "--log-driver=none" in argv and "--no-healthcheck" in argv
    assert not {"run", "start", "pull", "build", "rm", "sh", "bash"}.intersection(argv)
    assert not any(value.startswith(("--publish=", "--volume=", "--env=")) for value in argv)
    assert not any(value.startswith(("--pid=", "--security-opt=seccomp")) for value in argv)
    mounts = [value for value in argv if value.startswith("--mount=")]
    assert len(mounts) == {"T": 2, "A": 1, "B": 0}[role]
    assert all(value.endswith(",readonly,bind-propagation=rprivate") for value in mounts)
    if role == "B":
        assert "--network=container:" + "a" * 64 in argv
        assert data["declared_files"] == []
        assert argv[-4:] == ["-I", "-B", "/opt/authzest-guest/relay_launcher.py", "40000"]
    else:
        assert "--network=none" in argv
        assert data["declared_files"][0]["source"] == "/reviewed/staged-inputs/app.py"
        assert argv[-3:-1] == ["-I", "-B"]
    assert result.plan_id == "generated-repair-container-create-plan-" + identity(data)
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"


def test_forged_profile_wrapper_does_not_bypass_revalidation():
    with pytest.raises(ContractError):
        build_container_create_plan(
            RuntimeProfile("{}"),
            "B",
            session_nonce="8" * 32,
            role_nonce="9" * 32,
            application_container_id="a" * 64,
            remaining_ms=1,
        )
    assert not hasattr(ContainerCreatePlan, "execute")
    assert not hasattr(RuntimeProfile, "execute")
