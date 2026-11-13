"""Supplied data cannot select extra commands, mounts, identities or authority."""

from __future__ import annotations

import json
from hashlib import sha256

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.runner._generated_repair_runtime_profile import (
    ContainerCreatePlan,
    RuntimeProfile,
    build_container_create_plan,
    validate_runtime_profile,
)
from test_generated_repair_runtime_profile import (
    no_external_effects,  # noqa: F401
    profile,
    profile_data,
)


def plan(role="T", **changes):
    kwargs = {"session_nonce": "8" * 32, "role_nonce": "9" * 32}
    if role == "B":
        kwargs.update(application_container_id="a" * 64, remaining_ms=1000)
    else:
        kwargs.update(staging_root="/reviewed/staged-inputs", application_sha256="b" * 64)
        if role == "T":
            kwargs["test_sha256"] = "c" * 64
    kwargs.update(changes)
    return build_container_create_plan(profile(), role, **kwargs)


@pytest.mark.parametrize(
    "path",
    [(), ("engine",), ("images",), ("images", "T"), ("images", "A"), ("images", "B")],
    ids=["profile", "engine", "images", "T", "A", "B"],
)
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_every_declaration_schema_is_closed(path, mutation):
    data = profile_data()
    target = data
    for key in path:
        target = target[key]
    if mutation == "missing":
        target.pop(next(iter(target)))
    else:
        target["execution_authorized"] = True
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong-role", "stale"])
def test_asset_bindings_cannot_be_removed_extended_or_relabelled(role, mutation):
    data = profile_data()
    assets = data["images"][role]["assets"]
    if mutation == "missing":
        assets.pop(next(iter(assets)))
    elif mutation == "extra":
        assets["host_oracle.py"] = "f" * 64
    elif mutation == "wrong-role":
        data["images"][role]["assets"] = data["images"][{"T": "A", "A": "B", "B": "T"}[role]][
            "assets"
        ]
    else:
        assets[next(iter(assets))] = "f" * 64
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 1),
        ("schema_version", "1.1"),
        ("kind", "runtime-ready"),
        ("platform", "windows/amd64"),
        ("platform", "darwin/arm64"),
        ("platform", "linux/arm64/v8"),
        ("platform", True),
    ],
)
def test_unknown_declaration_version_and_platform_are_not_fallbacks(field, value):
    data = profile_data()
    data[field] = value
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    "path",
    [
        "relative/docker",
        "/",
        "/reviewed//docker",
        "/reviewed/./docker",
        "/reviewed/../docker",
        "/reviewed/docker/",
        "/reviewed/a,b/docker",
        "/reviewed/a:b/docker",
        "/reviewed/a b/docker",
        "/reviewed/a\nb/docker",
        "/reviewed/a\\b/docker",
        "/reviewed/한글/docker",
        "/reviewed/bin/python",
        None,
        True,
    ],
)
def test_executable_paths_have_one_bounded_argument_grammar(path):
    data = profile_data()
    data["engine"]["executable"] = path
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    "endpoint",
    [
        "tcp://127.0.0.1:2375",
        "ssh://local-host",
        "unix://relative.sock",
        "unix:////reviewed/run/docker.sock",
        "unix:///reviewed/run/../docker.sock",
        "unix:///reviewed/run/docker.sock?context=x",
        "unix:///reviewed/run/docker.sock#fragment",
        "unix:///reviewed/run/docker%2Esock",
        "unix:///reviewed/run/docker.sock\x00",
        "desktop-linux",
        None,
    ],
)
def test_endpoint_syntax_cannot_select_remote_context_or_url_options(endpoint):
    data = profile_data()
    data["engine"]["endpoint"] = endpoint
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("field", ["executable_sha256", "server_identity_sha256"])
@pytest.mark.parametrize("value", ["a" * 63, "A" * 64, "z" * 64, True, None, "sha256:" + "a" * 64])
def test_declared_client_and_server_hashes_have_exact_shape(field, value):
    data = profile_data()
    data["engine"][field] = value
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("contents", [b"{}", b"{ }\n", b'{"proxies":{}}\n', b'{"auths":{}}\n'])
def test_empty_config_byte_identity_is_not_inferred_from_json_meaning(contents):
    data = profile_data()
    data["engine"]["config_json_sha256"] = sha256(contents).hexdigest()
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("version", ["1.40", "1.100", "1.041", "v1.45", "1.45\n", 1.45, True])
def test_unsupported_api_declaration_does_not_negotiate_or_guess(version):
    data = profile_data()
    data["engine"]["api_version"] = version
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("version", ["1.41", "1.99"])
def test_valid_api_syntax_still_creates_no_readiness_receipt(version):
    data = profile_data()
    data["engine"]["api_version"] = version
    result = build_container_create_plan(
        validate_runtime_profile(canonical(data)),
        "B",
        session_nonce="8" * 32,
        role_nonce="9" * 32,
        application_container_id="a" * 64,
        remaining_ms=1,
    ).to_dict()
    assert result["environment"] == {"DOCKER_API_VERSION": version}
    assert result["status"] == "planned-not-executed"
    assert result["runtime_invoked"] is result["execution_authorized"] is False
    assert result["pending"] and result["verified_fix"] is False


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize(
    "image", ["image:latest", "image@sha256:" + "a" * 64, "a" * 64, "sha256:", None]
)
def test_only_immutable_local_image_id_syntax_is_allowed(role, image):
    data = profile_data()
    data["images"][role]["image_id"] = image
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("field", ["dependency_lock_sha256", "recipe_sha256"])
def test_missing_image_provenance_hash_is_not_a_ready_image(role, field):
    data = profile_data()
    data["images"][role][field] = "unavailable"
    with pytest.raises(ContractError):
        validate_runtime_profile(canonical(data))


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "[]",
        "null",
        '{"platform":"linux/arm64","platform":"linux/amd64"}',
        '{"number":NaN}',
        '{"x":' + "[" * 17 + "0" + "]" * 17 + "}",
        '{"x":"' + "a" * 16384 + '"}',
        '{"x":"' + "가" * 6000 + '"}',
        '{"x":"\ud800"}',
    ],
    ids=["nontext", "array", "null", "duplicate", "nonfinite", "deep", "long", "utf8", "surrogate"],
)
def test_raw_profile_shape_duplicate_depth_and_byte_budgets(raw):
    with pytest.raises(ContractError):
        validate_runtime_profile(raw)


@pytest.mark.parametrize("role", ["T", "A", "B"])
@pytest.mark.parametrize("field", ["session_nonce", "role_nonce"])
@pytest.mark.parametrize("value", ["x" * 32, "a" * 31, "A" * 32, "a,b", True, None])
def test_nonce_cannot_inject_names_labels_or_cli_fields(role, field, value):
    with pytest.raises(ContractError):
        plan(role, **{field: value})


@pytest.mark.parametrize(
    ("role", "field", "value"),
    [
        ("T", "application_container_id", "a" * 64),
        ("A", "application_container_id", "a" * 64),
        ("T", "remaining_ms", 1),
        ("A", "remaining_ms", 1),
        ("A", "test_sha256", "a" * 64),
        ("B", "staging_root", "/reviewed/staged-inputs"),
        ("B", "application_sha256", "a" * 64),
        ("B", "test_sha256", "a" * 64),
        ("T", "staging_root", None),
        ("A", "application_sha256", None),
        ("T", "test_sha256", None),
        ("B", "application_container_id", "short"),
        ("B", "remaining_ms", None),
    ],
)
def test_role_specific_inputs_are_not_silently_ignored(role, field, value):
    with pytest.raises(ContractError):
        plan(role, **{field: value})


@pytest.mark.parametrize(
    "value",
    [True, 0, -1, 40001, 1.0, "1", pytest.param(2**4096, id="huge-integer")],
)
def test_relay_budget_is_a_strict_bounded_integer_not_a_new_phase(value):
    with pytest.raises(ContractError):
        plan("B", remaining_ms=value)


@pytest.mark.parametrize(
    "root",
    [
        "/",
        "relative",
        "/reviewed/a,b",
        "/reviewed/a:ro",
        "/reviewed//input",
        "/reviewed/../input",
        "/reviewed/input/",
        "/reviewed/empty-docker-config",
        "/reviewed/empty-docker-config/child",
        "/reviewed",
        "/reviewed/bin/docker",
        "/reviewed/run/docker.sock",
    ],
)
def test_staging_paths_do_not_alias_config_client_socket_or_mount_grammar(root):
    with pytest.raises(ContractError):
        plan(staging_root=root)


def test_derived_file_paths_are_bounded_not_only_staging_parent():
    with pytest.raises(ContractError):
        plan(staging_root="/" + "s" * 490)


@pytest.mark.parametrize("role", ["T", "A", "B"])
def test_fixed_plan_limits_and_diagnostic_states_remain_declarations(role):
    data = plan(role).to_dict()
    argv = data["argv"]
    small = role == "B"
    memory = 134217728 if small else 536870912
    assert f"--memory={memory}" in argv and f"--memory-swap={memory}" in argv
    assert "--cpus=" + ("0.5" if small else "1") in argv
    assert "--pids-limit=" + ("32" if small else "64") in argv
    assert "--shm-size=8388608" in argv
    for flag in (
        "--read-only",
        "--user=65532:65532",
        "--ipc=private",
        "--cgroupns=private",
        "--init=false",
        "--restart=no",
        "--privileged=false",
        "--publish-all=false",
        "--interactive=false",
        "--tty=false",
        "--entrypoint=/usr/local/bin/python",
    ):
        assert argv.count(flag) == 1
    assert len([arg for arg in argv if arg.startswith("--label=")]) == 3
    assert (
        data["owned_name"] == "authzest-generated-" + "8" * 32 + "-" + role.lower() + "-" + "9" * 32
    )
    assert data["environment"] == {"DOCKER_API_VERSION": "1.45"}
    assert not {"HOME", "PATH", "DOCKER_CONTEXT", "HTTP_PROXY"} & data["environment"].keys()
    assert data["status"] == "planned-not-executed"
    assert data["runtime_invoked"] is data["execution_authorized"] is data["verified_fix"] is False
    assert not hasattr(ContainerCreatePlan, "start")
    assert not hasattr(RuntimeProfile, "prepare")


def test_identity_binds_input_bytes_path_nonce_and_declared_runtime():
    original = plan().plan_id
    assert original != plan(application_sha256="d" * 64).plan_id
    assert original != plan(staging_root="/another/declared-staging").plan_id
    assert original != plan(role_nonce="d" * 32).plan_id
    data = profile_data()
    data["images"]["T"]["image_id"] = "sha256:" + "d" * 64
    changed = build_container_create_plan(
        validate_runtime_profile(canonical(data)),
        "T",
        session_nonce="8" * 32,
        role_nonce="9" * 32,
        staging_root="/reviewed/staged-inputs",
        application_sha256="b" * 64,
        test_sha256="c" * 64,
    )
    assert original != changed.plan_id
    assert changed.to_dict()["execution_authorized"] is False


def test_profiles_can_be_json_reformatted_but_not_promoted_to_authority():
    pretty = json.dumps(profile_data(), indent=2)
    assert validate_runtime_profile(pretty) == profile()
    forged = RuntimeProfile('{"execution_authorized":true}')
    with pytest.raises(ContractError):
        build_container_create_plan(forged, "B", session_nonce="8" * 32, role_nonce="9" * 32)
