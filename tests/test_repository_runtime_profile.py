"""Pure external profile/argv declarations; no Engine, target, or guest execution."""

from __future__ import annotations

import ast
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
from authzest.runner import _repository_runtime_profile as module
from authzest.runner._generated_repair_runtime_profile import RuntimeProfile as FixedRuntimeProfile
from authzest.runner._repository_manifest import build_guest_manifest
from authzest.runner._repository_runtime_profile import (
    EMPTY_CONFIG_SHA256,
    RepositoryCreatePlan,
    RepositoryRuntimeProfile,
    build_container_create_plan,
    expected_assets,
    validate_runtime_profile,
)

# Collection reads only maintained source bytes for digest drift regressions.
# Tests forbid filesystem, compilation, process, and network operations below.
_REPO = Path(__file__).resolve().parents[1]
_ASSET_DIGESTS = {
    "_guest_common.py": sha256(
        (_REPO / "runtime/repository/_guest_common.py").read_bytes()
    ).hexdigest(),
    "_repository_manifest.py": sha256(
        (_REPO / "src/authzest/runner/_repository_manifest.py").read_bytes()
    ).hexdigest(),
    "repository_http.py": sha256(
        (_REPO / "src/authzest/runner/_repository_http.py").read_bytes()
    ).hexdigest(),
    **{
        name: sha256((_REPO / "runtime/repository" / name).read_bytes()).hexdigest()
        for name in ("test_launcher.py", "app_launcher.py", "relay_launcher.py")
    },
}


_IMAGE_ROOT = _REPO / "runtime/repository/images"
_IMAGE_DATA = json.loads((_IMAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))
_BASE_MANIFEST_DIGEST = sha256((_REPO / _IMAGE_DATA["base_reference"]).read_bytes()).hexdigest()
_RECIPE_FACTS = {
    (platform, role): {
        "lock_sha256": sha256((_REPO / recipe["dependency_lock_path"]).read_bytes()).hexdigest(),
        "dockerfile_sha256": sha256((_IMAGE_ROOT / recipe["dockerfile"]).read_bytes()).hexdigest(),
    }
    for role, role_data in _IMAGE_DATA["roles"].items()
    for platform, recipe in role_data["platforms"].items()
}


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    original_import = builtins.__import__
    original_compile = builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Repository runtime declarations must remain inert data")

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

    def ast_only_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)
    for name in ("open", "eval", "exec"):
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


def _profile_data(platform="linux/arm64"):
    return {
        "schema_version": "1.0",
        "kind": "repository-runtime-profile",
        "platform": platform,
        "engine": {
            "executable": "/reviewed/bin/docker",
            "executable_sha256": "1" * 64,
            "endpoint": "unix:///reviewed/run/docker.sock",
            "config_dir": "/reviewed/empty-config",
            "config_json_sha256": EMPTY_CONFIG_SHA256,
            "server_identity_sha256": "2" * 64,
            "api_version": "1.45",
        },
        "images": {
            role: {
                "image_id": "sha256:" + digit * 64,
                **module.expected_recipe_pins(platform, role),
                "assets": expected_assets(role),
            }
            for role, digit in (("T", "3"), ("A", "4"), ("B", "5"))
        },
    }


def _profile(platform="linux/arm64"):
    return validate_runtime_profile(canonical(_profile_data(platform)))


def _manifest(role, count=1):
    entry = "src/pkg/app.py" if count > 1 else "app.py"
    paths = [entry]
    if count > 1:
        paths += ["src/pkg/__init__.py", "src/pkg/auth.py", "src/pkg/data.py", "src/pkg/util.py"]
        paths = paths[:count]
    interface = {
        "schema_version": "1.0",
        "entry_source": entry,
        "import_root": "src" if count > 1 else ".",
        "module": "pkg.app" if count > 1 else "app",
        "app_attribute": "app",
        "fixture": "client",
        "lifespan": "off",
        "auth_overrides": "none",
    }
    interface["interface_id"] = "repository-test-interface-" + identity(interface)
    files = [{"path": path, "sha256": "b" * 64, "size_bytes": 16} for path in paths]
    test = (
        {"path": "tests/test_authzest_regression.py", "sha256": "c" * 64, "size_bytes": 32}
        if role == "T"
        else None
    )
    return build_guest_manifest(
        "repository-test-proposal-request-" + "a" * 64, interface, files, test, role=role
    )


def _schedule(count=4):
    return {
        "schema_version": "1.0",
        "kind": "repository-observer-schedule",
        "plan_id": "repository-verification-plan-" + "d" * 64,
        "phase": "before",
        "requests": [
            {"case_id": f"case-{n}", "method": "GET", "path": f"/items/{n}", "headers": {}}
            for n in range(count)
        ],
    }


def _parameters(role, count=1):
    params = {"session_nonce": "8" * 32, "role_nonce": "9" * 32}
    if role == "B":
        params.update(application_container_id="a" * 64, remaining_ms=40000, schedule=_schedule())
    else:
        params.update(staging_root="/reviewed/stage/input", manifest=_manifest(role, count))
    return params


@pytest.mark.parametrize("platform", ["linux/arm64", "linux/amd64"])
def test_maintained_assets_pins_are_detached_source_bindings_not_observations(platform):
    for role in ("T", "A", "B"):
        assets = expected_assets(role)
        assert assets == {name: _ASSET_DIGESTS[name] for name in assets}
        assets.clear()
        assert expected_assets(role)
        pins = module.expected_recipe_pins(platform, role)
        assert set(pins) == {"dependency_lock_sha256", "recipe_sha256"}
        assert all(len(value) == 64 for value in pins.values())
        pins.clear()
        assert module.expected_recipe_pins(platform, role)
    assert sha256(b"{}\n").hexdigest() == EMPTY_CONFIG_SHA256


def test_profile_is_canonical_immutable_and_unverified():
    profile = _profile()
    assert profile.to_dict() == _profile_data()
    assert profile.profile_id == "repository-runtime-profile-" + identity(_profile_data())
    assert profile.provenance == "caller-supplied-unverified"
    assert validate_runtime_profile(profile.payload_json) == profile
    detached = profile.to_dict()
    detached["engine"]["endpoint"] = "tcp://new-host"
    assert profile.to_dict() == _profile_data()
    with pytest.raises(FrozenInstanceError):
        profile.payload_json = "{}"
    assert not hasattr(profile, "execute")
    assert not hasattr(profile, "runtime_ready")


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("platform", ["linux/arm64", "linux/amd64"])
def test_fixed_create_argv_and_effect_intent_have_no_runtime_claims(role, platform):
    result = build_container_create_plan(_profile(platform), role, **_parameters(role))
    data = result.to_dict()
    argv = data["argv"]
    assert data["status"] == "planned-not-executed"
    assert data["provenance"] == "caller-supplied-unverified"
    assert data["runtime_invoked"] is data["execution_authorized"] is data["verified_fix"] is False
    assert data["authorization_status"] == "unknown"
    assert data["pending"]
    assert data["environment"] == {"DOCKER_API_VERSION": "1.45"}
    assert argv[:5] == [
        "/reviewed/bin/docker",
        "--config=/reviewed/empty-config",
        "--host=unix:///reviewed/run/docker.sock",
        "container",
        "create",
    ]
    assert "--platform=" + platform in argv
    assert "--user=65532:65532" in argv and "--read-only" in argv
    assert "--cap-drop=ALL" in argv and "--security-opt=no-new-privileges=true" in argv
    assert "--ipc=private" in argv and "--cgroupns=private" in argv
    assert "--init=false" in argv and "--restart=no" in argv
    assert "--pull=never" in argv and "--log-driver=none" in argv
    assert "--no-healthcheck" in argv and "--privileged=false" in argv
    assert "--publish-all=false" in argv and "--tty=false" in argv
    assert "--shm-size=8388608" in argv and "--workdir=/tmp" in argv
    assert not {"run", "start", "pull", "build", "rm", "sh", "bash"}.intersection(argv)
    assert not any(
        value.startswith(("--publish=", "--volume=", "--env=", "--pid=")) for value in argv
    )
    assert not any(value.startswith("--security-opt=seccomp") for value in argv)
    assert "--entrypoint=/usr/local/bin/python" in argv
    assert (
        data["owned_name"]
        == "authzest-repository-" + "8" * 32 + "-" + role.lower() + "-" + "9" * 32
    )
    assert result.plan_id == "repository-container-create-plan-" + identity(data)
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"
    assert not hasattr(RepositoryCreatePlan, "execute")


@pytest.mark.parametrize("role", ["T", "A"])
@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_t_a_only_selected_readonly_files_and_test_separation(role, count):
    params = _parameters(role, count)
    data = build_container_create_plan(_profile(), role, **params).to_dict()
    assert "--network=none" in data["argv"]
    assert "--interactive=false" in data["argv"]
    assert data["stdin"] is data["application_container_id"] is data["remaining_ms"] is None
    assert data["input_manifest"] == params["manifest"]
    files = data["declared_files"]
    assert len(files) == count + 1 + (role == "T")
    assert files[0]["target"] == "/input/manifest.json"
    assert files[0]["sha256"] == sha256(canonical(params["manifest"]).encode()).hexdigest()
    assert files[0]["utf8_bytes"] == len(canonical(params["manifest"]).encode())
    source_targets = {"/input/project/" + f["path"] for f in params["manifest"]["source_files"]}
    assert {item["target"] for item in files[1 : 1 + count]} == source_targets
    assert all(f["source"].startswith("/reviewed/stage/input/") for f in files)
    assert not any("record.json" in f["source"] or "policy" in f["source"] for f in files)
    assert not any(f["target"] in {"/input", "/input/project", "/input/tests"} for f in files)
    if role == "T":
        assert files[-1]["target"] == "/input/tests/test_authzest_regression.py"
    else:
        assert not any("/input/tests/" in f["target"] for f in files)
    mounts = [value for value in data["argv"] if value.startswith("--mount=")]
    assert len(mounts) == len(files)
    assert all(value.endswith(",readonly,bind-propagation=rprivate") for value in mounts)
    assert data["argv"][-3:] == [
        "-I",
        "-B",
        "/opt/authzest-repository-guest/" + ("test" if role == "T" else "app") + "_launcher.py",
    ]


@pytest.mark.parametrize("remaining", [1, 39, 40000])
@pytest.mark.parametrize("count", [4, 8])
def test_b_has_request_only_stdin_no_mounts_and_exact_network_namespace(remaining, count):
    params = _parameters("B")
    params.update(remaining_ms=remaining, schedule=_schedule(count))
    data = build_container_create_plan(_profile(), "B", **params).to_dict()
    assert data["declared_files"] == [] and data["input_manifest"] is None
    assert not any(value.startswith("--mount=") for value in data["argv"])
    assert "--interactive=true" in data["argv"]
    assert "--network=container:" + "a" * 64 in data["argv"]
    assert data["argv"][-4:] == [
        "-I",
        "-B",
        "/opt/authzest-repository-guest/relay_launcher.py",
        str(remaining),
    ]
    stdin = data["stdin"]
    assert stdin == {
        "kind": "repository-observer-schedule",
        "value": params["schedule"],
        "sha256": sha256(canonical(params["schedule"]).encode()).hexdigest(),
        "utf8_bytes": len(canonical(params["schedule"]).encode()),
        "eof_required": True,
    }
    assert stdin["utf8_bytes"] <= 16384
    assert (
        not {"expected", "before", "after", "source", "test", "policy", "cleanup"}
        & stdin["value"].keys()
    )
    params["schedule"]["requests"][0]["path"] = "/changed"
    assert data["stdin"]["value"]["requests"][0]["path"] == "/items/0"


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_resource_output_and_time_budgets_are_explicit_declared_intent(role):
    data = build_container_create_plan(_profile(), role, **_parameters(role)).to_dict()
    small = role == "B"
    memory, pids, tmp = (134217728, 32, 8388608) if small else (536870912, 64, 33554432)
    assert data["budgets"] == {
        "phase_seconds": 40,
        "cleanup_seconds": 10,
        "combined_output_bytes": 262144,
        "relay_output_bytes": 131072,
        "memory_bytes": memory,
        "tmpfs_bytes": tmp,
        "pid_limit": pids,
        "pid_namespace": "private-default",
    }
    assert f"--memory={memory}" in data["argv"]
    assert f"--memory-swap={memory}" in data["argv"]
    assert f"--pids-limit={pids}" in data["argv"]
    assert "--cpus=" + ("0.5" if small else "1") in data["argv"]
    assert (
        f"--tmpfs=/tmp:rw,noexec,nosuid,nodev,size={tmp},uid=65532,gid=65532,mode=0700"
        in data["argv"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("executable", "/reviewed/bin/podman"),
        ("executable", "docker"),
        ("executable", "/reviewed/../docker"),
        ("executable", "/reviewed//docker"),
        ("endpoint", "tcp://127.0.0.1:2375"),
        ("endpoint", "ssh://host"),
        ("endpoint", "unix:///reviewed/run/../docker.sock"),
        ("endpoint", "unix:///"),
        ("config_dir", "/reviewed/with space"),
        ("config_dir", "/reviewed/config,other"),
        ("config_dir", "/reviewed/conf\nig"),
        pytest.param("config_dir", "/" + "x" * 513, id="oversize-config-path"),
        ("config_json_sha256", "0" * 64),
        ("executable_sha256", "A" * 64),
        ("server_identity_sha256", True),
        ("api_version", "1.40"),
        ("api_version", "1.100"),
        ("api_version", 1.45),
        ("api_version", "01.45"),
    ],
)
def test_profile_engine_rejects_unsafe_paths_versions_and_types(field, value):
    data = _profile_data()
    data["engine"][field] = value
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    "changes",
    [
        {"config_dir": "/reviewed/bin"},
        {"config_dir": "/reviewed/bin/docker"},
        {"config_dir": "/reviewed/bin/docker/sub"},
        {"config_dir": "/reviewed/run"},
        {"config_dir": "/reviewed/run/docker.sock/sub"},
        {"endpoint": "unix:///reviewed/bin/docker"},
        {"endpoint": "unix:///reviewed/bin/docker/sub"},
    ],
)
def test_profile_refuses_any_path_containment_overlap(changes):
    data = _profile_data()
    data["engine"].update(changes)
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "1.1"),
        ("kind", "generated-repair-runtime-profile"),
        ("platform", "darwin/arm64"),
        ("platform", "linux/386"),
        ("platform", True),
    ],
)
def test_profile_identity_and_platform_are_closed(field, value):
    data = _profile_data()
    data[field] = value
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("field", ["image_id", "dependency_lock_sha256", "recipe_sha256"])
def test_image_or_recipe_tampering_is_refused(role, field):
    data = _profile_data()
    data["images"][role][field] = ("sha256:" if field == "image_id" else "") + "g" * 64
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))
    if field != "image_id":
        data["images"][role][field] = "0" * 64  # valid digest syntax, wrong maintained recipe
        with pytest.raises(ContractError):
            validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_asset_or_unknown_profile_metadata_cannot_create_proof(role):
    original = _profile_data()
    for mutate in (
        lambda d: d.update(runtime_ready=True),
        lambda d: d["engine"].update(credentials="private"),
        lambda d: d["images"][role].update(approved=True),
        lambda d: d["images"][role]["assets"].update(unlisted="0" * 64),
        lambda d: d["images"][role]["assets"].update({next(iter(expected_assets(role))): "0" * 64}),
    ):
        data = copy.deepcopy(original)
        mutate(data)
        with pytest.raises(ContractError):
            validate_runtime_profile(canonical(data))


def test_profile_duplicate_json_keys_byte_budget_and_nonfinite_are_refused():
    raw = canonical(_profile_data())
    with pytest.raises(ContractError):
        validate_runtime_profile(raw.replace('"platform":', '"platform":"linux/amd64","platform":'))
    for invalid in (" " * (16384 + 1), raw.replace('"platform":"linux/arm64"', '"platform":NaN')):
        with pytest.raises(ContractError):
            validate_runtime_profile(invalid)


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_old_or_forged_profile_objects_are_not_runtime_capabilities(role):
    for profile in (
        FixedRuntimeProfile(canonical(_profile_data())),
        RepositoryRuntimeProfile("{}"),
        {},
    ):
        with pytest.raises(ContractError):
            build_container_create_plan(profile, role, **_parameters(role))
    assert not hasattr(RepositoryRuntimeProfile, "execute")
    assert not hasattr(RepositoryCreatePlan, "execute")


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("session_nonce", True),
        ("session_nonce", "a" * 31),
        ("role_nonce", "g" * 32),
        ("role_nonce", "a" * 100000),
    ],
    ids=[
        "boolean-session-nonce",
        "short-session-nonce",
        "nonhex-role-nonce",
        "oversize-role-nonce",
    ],
)
def test_create_identity_tokens_are_exact_bounded_native_strings(role, field, value):
    params = _parameters(role)
    params[field] = value
    with pytest.raises(ContractError):
        build_container_create_plan(_profile(), role, **params)


@pytest.mark.parametrize("role", ["T", "A"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("application_container_id", "a" * 64),
        ("remaining_ms", 1),
        ("schedule", {}),
        ("staging_root", "/reviewed/empty-config/sub"),
        ("staging_root", "/reviewed/bin"),
        ("staging_root", "/reviewed/run/docker.sock"),
        ("staging_root", "/reviewed"),
        ("staging_root", "/reviewed/stage,other"),
        ("staging_root", None),
    ],
)
def test_t_a_refuse_cross_role_inputs_and_conflicting_stage_paths(role, field, value):
    params = _parameters(role)
    params[field] = value
    with pytest.raises((ContractError, ValueError)):
        build_container_create_plan(_profile(), role, **params)


@pytest.mark.parametrize(
    "field,value",
    [
        ("staging_root", "/reviewed/stage"),
        ("manifest", {}),
        ("application_container_id", "name"),
        ("application_container_id", True),
        ("remaining_ms", 0),
        ("remaining_ms", 40001),
        ("remaining_ms", True),
        ("remaining_ms", 1.0),
        ("schedule", None),
    ],
)
def test_b_refuses_cross_role_inputs_invalid_cid_duration_and_absent_schedule(field, value):
    params = _parameters("B")
    params[field] = value
    with pytest.raises((ContractError, ValueError)):
        build_container_create_plan(_profile(), "B", **params)


@pytest.mark.parametrize("count", [3, 9])
def test_b_schedule_bound_and_no_oracle_injection(count):
    params = _parameters("B")
    params["schedule"] = _schedule(count)
    with pytest.raises(ValueError):
        build_container_create_plan(_profile(), "B", **params)
    params["schedule"] = _schedule()
    params["schedule"]["expected"] = {}
    with pytest.raises(ValueError):
        build_container_create_plan(_profile(), "B", **params)


def test_manifests_are_rebuilt_and_cannot_be_tampered_or_swapped_between_roles():
    for role in ("T", "A"):
        params = _parameters(role)
        params["manifest"]["source_files"][0]["sha256"] = "f" * 64
        with pytest.raises(ValueError):
            build_container_create_plan(_profile(), role, **params)
        params["manifest"] = _manifest("A" if role == "T" else "T")
        with pytest.raises(ValueError):
            build_container_create_plan(_profile(), role, **params)


def test_output_plan_is_detached_and_current_profile_is_revalidated():
    profile = _profile()
    data = profile.to_dict()
    data["images"]["T"]["assets"]["test_launcher.py"] = "0" * 64
    forged = RepositoryRuntimeProfile(canonical(data))
    with pytest.raises(ContractError):
        build_container_create_plan(forged, "T", **_parameters("T"))
    result = build_container_create_plan(profile, "T", **_parameters("T"))
    exported = result.to_dict()
    exported["argv"].append("--privileged=true")
    assert "--privileged=true" not in result.to_dict()["argv"]
    assert len(result.payload_json.encode()) <= module.MAX_CREATE_BYTES


@pytest.mark.parametrize("path", ["src/pkg/with space.py", "src/pkg/한글.py"])
def test_valid_static_contexts_outside_runtime_ascii_mount_subset_fail_closed(path):
    manifest = _manifest("T", 3)
    files = manifest["source_files"]
    files[-1]["path"] = path
    manifest = build_guest_manifest(
        manifest["request_id"], manifest["test_interface"], files, manifest["test"], role="T"
    )
    params = _parameters("T")
    params["manifest"] = manifest
    with pytest.raises(ContractError):
        build_container_create_plan(_profile(), "T", **params)


@pytest.mark.parametrize("version", ["1.41", "1.99"])
def test_supported_engine_api_version_boundaries(version):
    data = _profile_data()
    data["engine"]["api_version"] = version
    assert validate_runtime_profile(canonical(data)).to_dict()["engine"]["api_version"] == version


@pytest.mark.parametrize("role", ["", "t", "C", True, 1])
def test_unknown_role_cannot_select_assets_or_argv(role):
    with pytest.raises(ContractError):
        expected_assets(role)
    with pytest.raises(ContractError):
        module.expected_recipe_pins("linux/arm64", role)
    with pytest.raises(ContractError):
        build_container_create_plan(_profile(), role, **_parameters("B"))


@pytest.mark.parametrize("platform", ["linux/amd64", "linux/arm64"])
@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_recipe_manifest_and_maintained_bytes_do_not_drift(platform, role):
    recipe = _IMAGE_DATA["roles"][role]["platforms"][platform]
    actual = _RECIPE_FACTS[platform, role]
    pins = module.expected_recipe_pins(platform, role)
    assert (
        pins["dependency_lock_sha256"] == recipe["dependency_lock_sha256"] == actual["lock_sha256"]
    )
    assert recipe["dockerfile_sha256"] == actual["dockerfile_sha256"]
    assert pins["recipe_sha256"] == recipe["recipe_sha256"]
    assert recipe["recipe_sha256"] == identity(
        {key: value for key, value in recipe.items() if key != "recipe_sha256"}
    )
    assert recipe["assets"] == expected_assets(role)
    assert _IMAGE_DATA["roles"][role]["assets"] == expected_assets(role)
    assert _IMAGE_DATA["base_reference_sha256"] == _BASE_MANIFEST_DIGEST
    assert _IMAGE_DATA["contents_verified"] is _IMAGE_DATA["runtime_ready"] is False
    assert _IMAGE_DATA["image_ids"] is None
    assert _IMAGE_DATA["status"] == "declared-not-built"


def test_equal_profile_subclass_is_not_the_exact_runtime_declaration_type():
    class Lookalike(RepositoryRuntimeProfile):
        pass

    with pytest.raises(ContractError):
        build_container_create_plan(Lookalike(_profile().payload_json), "T", **_parameters("T"))


def test_plan_identity_binds_input_hashes_phase_schedule_cid_and_nonces():
    base = _parameters("B")
    initial = build_container_create_plan(_profile(), "B", **base)
    changes = [
        {"application_container_id": "b" * 64},
        {"remaining_ms": 30000},
        {"session_nonce": "7" * 32},
        {"role_nonce": "6" * 32},
        {"schedule": {**_schedule(), "phase": "after"}},
    ]
    for changed in changes:
        result = build_container_create_plan(_profile(), "B", **{**base, **changed})
        assert result.plan_id != initial.plan_id
        assert result.to_dict()["execution_authorized"] is False
    params = _parameters("T")
    first = build_container_create_plan(_profile(), "T", **params)
    manifest = params["manifest"]
    files = copy.deepcopy(manifest["source_files"])
    files[0]["sha256"] = "f" * 64
    params["manifest"] = build_guest_manifest(
        manifest["request_id"], manifest["test_interface"], files, manifest["test"], role="T"
    )
    second = build_container_create_plan(_profile(), "T", **params)
    assert first.plan_id != second.plan_id
    assert first.to_dict()["declared_files"] != second.to_dict()["declared_files"]
