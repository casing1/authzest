"""Synthetic in-memory checks, never account/configuration RPC or process evidence."""

from __future__ import annotations

import builtins
import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_preflight as preflight
from scripts import evaluation_trial_plan as planner


def configuration(**values):
    return planner.TrialConfig(
        **{
            "model": "proposed-model",
            "effort": "high",
            "repetitions": 1,
            "timeout_seconds": 30,
            **values,
        }
    )


def candidate(*, servers=None):
    # An independent fixture projection produces nested response paths, not the
    # flat dotted CLI/config override map itself.
    config = {}
    for path, value in recipe.descriptor(configuration())["process_config"].items():
        parts = path.split(".")
        cursor = config
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = copy.deepcopy(value)
    config["mcp_servers"] = {} if servers is None else servers
    return {"config": config, "origins": {}}


def check(result, *, phase="discovery", selected=None):
    return preflight.check_config(
        result, configuration() if selected is None else selected, phase=phase
    )


def assert_no_execution(value):
    for key in (
        "runtime_observed",
        "provider_freshness_verified",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "live_benchmark_ready",
        "safe_to_launch",
    ):
        assert value[key] is False
    assert value["provider_calls_by_this_tool"] == 0
    assert value["target_execution"] == "not-run"
    assert value["transport_status"] == "not-implemented"


@pytest.mark.parametrize("phase", ["discovery", "generation"])
def test_explicit_empty_mcp_map_matches_recipe_without_runtime_or_launch_claims(phase):
    result = check(candidate(), phase=phase)
    assert result["phase"] == phase
    assert result["supplied_recipe_values_match"] is True
    assert result["mcp_servers_count"] == result["origins_entries_count"] == 0
    assert result["required_recipe_fields_count"] == len(
        recipe.descriptor(configuration())["process_config"]
    )
    assert result["input_provenance"] == "caller-supplied-unverified"
    for key in (
        "startup_behavior_verified",
        "harness_isolation_verified",
        "full_protocol_conformance_verified",
        "origins_metadata_retained",
        "configuration_values_exported",
        "private_names_exported",
    ):
        assert result[key] is False
    assert_no_execution(result)


def test_pair_checks_exact_names_and_explicit_false_generation_markers():
    before = candidate(servers={"second": {"command": "private"}, "first": {"enabled": True}})
    after = candidate(servers={"first": {"enabled": False}, "second": {"enabled": False}})
    result = preflight.compare_configs(before, after, configuration())
    assert result["supplied_mcp_names_match"] is True
    assert (
        result["discovery"]["mcp_servers_count"] == result["generation"]["mcp_servers_count"] == 2
    )
    assert_no_execution(result)
    assert_no_execution(result["discovery"])
    assert_no_execution(result["generation"])


def test_output_and_closed_errors_never_echo_private_values_names_keys_or_config_hashes():
    result = candidate(servers={"private-server-name": {"url": "private-secret-url"}})
    result["origins"] = {
        "private-origin-key": {
            "name": {"type": "user", "file": "/private/path", "profile": "private-profile"},
            "version": "private-version",
        }
    }
    output = check(result)
    encoded = json.dumps(output)
    assert "private-" not in encoded and "/private/path" not in encoded
    assert "sha256" not in encoded and "digest" not in encoded
    assert output["origins_entries_count"] == 1
    assert any("profiles/provenance are not assessed" in item for item in output["limitations"])
    result["config"]["private-unreviewed-key"] = "private-secret-value"
    with pytest.raises(preflight.PreflightError) as error:
        check(result)
    assert str(error.value) == "unreviewed-config-fields"
    assert "private" not in repr(error.value)


def test_inputs_unchanged_and_returned_metadata_detached_even_when_pair_rechecked():
    before, after = candidate(), candidate()
    saved = copy.deepcopy((before, after))
    first = preflight.compare_configs(before, after, configuration())
    first["limitations"].append("changed")
    first["discovery"]["limitations"].clear()
    second = preflight.compare_configs(before, after, configuration())
    assert "changed" not in second["limitations"]
    assert second["discovery"]["limitations"]
    assert (before, after) == saved
    assert second["runtime_observed"] is False  # Rechecking is not one-use or live evidence.


def test_every_required_recipe_leaf_must_be_present_and_exact_not_defaulted():
    for path in recipe.descriptor(configuration())["process_config"]:
        result = candidate()
        parts = path.split(".")
        cursor = result["config"]
        for part in parts[:-1]:
            cursor = cursor[part]
        original = cursor.pop(parts[-1])
        with pytest.raises(preflight.PreflightError, match="recipe-value-mismatch"):
            check(result)
        cursor[parts[-1]] = None
        with pytest.raises(preflight.PreflightError, match="recipe-value-mismatch"):
            check(result)
        cursor[parts[-1]] = original
        check(result)


@pytest.mark.parametrize(
    "path,value",
    [
        ("project_doc_max_bytes", False),
        ("analytics.enabled", 0),
        ("features.apps", 0),
        ("model", "different-model"),
        ("model_reasoning_effort", "medium"),
        ("approvals_reviewer", "auto_review"),
        ("notify", ["private-command"]),
    ],
)
def test_recipe_comparison_rejects_bool_int_aliases_different_settings_and_notify(path, value):
    result = candidate()
    parts = path.split(".")
    cursor = result["config"]
    for part in parts[:-1]:
        cursor = cursor[part]
    cursor[parts[-1]] = value
    with pytest.raises(preflight.PreflightError, match="recipe-value-mismatch"):
        check(result)


def test_tuple_notify_is_not_the_reported_json_list():
    result = candidate()
    result["config"]["notify"] = ()
    with pytest.raises(preflight.PreflightError, match="invalid-input-type"):
        check(result)


@pytest.mark.parametrize("field", sorted(preflight.INACTIVE_OPTIONAL_FIELDS))
def test_each_reviewed_inactive_field_accepts_only_missing_or_null(field):
    result = candidate()
    result["config"][field] = None
    check(result)
    for nonnull in (False, 0, "", [], {}):
        result["config"][field] = nonnull
        with pytest.raises(preflight.PreflightError, match="inactive-override-set"):
            check(result)


@pytest.mark.parametrize("field", ["profile", "profiles", "model_providers", "unknown"])
def test_unreviewed_root_overrides_rejected_even_null(field):
    result = candidate()
    result["config"][field] = None
    with pytest.raises(preflight.PreflightError, match="unreviewed-config-fields"):
        check(result)


def test_unknown_nested_paths_and_flat_dotted_aliases_cannot_bypass_nested_policy():
    for location in ("features", "analytics", "memories", "otel", "history"):
        result = candidate()
        result["config"][location]["unknown"] = None
        with pytest.raises(preflight.PreflightError, match="unreviewed-config-fields"):
            check(result)
    result = candidate()
    result["config"]["features.apps"] = False
    with pytest.raises(preflight.PreflightError, match="unreviewed-config-fields"):
        check(result)


@pytest.mark.parametrize("phase", [None, True, "", "Generation", "other"])
def test_phase_is_explicit_closed_string_not_bool_or_default(phase):
    with pytest.raises(preflight.PreflightError, match="invalid-phase"):
        check(candidate(), phase=phase)


@pytest.mark.parametrize("value", [None, {}, True])
def test_configuration_must_be_owned_strict_trial_config(value):
    with pytest.raises(preflight.PreflightError, match="invalid-configuration"):
        preflight.check_config(candidate(), value, phase="discovery")


def test_frozen_configuration_mutation_is_revalidated():
    selected = configuration()
    object.__setattr__(selected, "timeout_seconds", True)
    with pytest.raises(preflight.PreflightError, match="invalid-configuration"):
        check(candidate(), selected=selected)


def test_required_root_shapes_and_unknown_result_fields_are_not_ignored():
    for key, code in (
        ("config", "missing-effective-config"),
        ("origins", "missing-config-origins"),
    ):
        for bad in (None, [], "private-value", False):
            result = candidate()
            result[key] = bad
            with pytest.raises(preflight.PreflightError, match=code):
                check(result)
        result = candidate()
        del result[key]
        with pytest.raises(preflight.PreflightError, match=code):
            check(result)
    result = candidate()
    result["private-root-key"] = None
    with pytest.raises(preflight.PreflightError, match="unreviewed-result-fields"):
        check(result)
    for value in (None, [], "private", False):
        with pytest.raises(preflight.PreflightError, match="invalid-result"):
            check(value)


def test_layers_include_false_request_accepts_only_missing_or_null_not_empty_array():
    result = candidate()
    result["layers"] = None
    check(result)
    for bad in ([], {}, False, "private", 0):
        result["layers"] = bad
        with pytest.raises(preflight.PreflightError, match="unexpected-config-layers"):
            check(result)


def test_mcp_map_must_be_reported_not_assumed_empty():
    result = candidate()
    del result["config"]["mcp_servers"]
    with pytest.raises(preflight.PreflightError, match="missing-mcp-configuration"):
        check(result)
    for value in (None, [], "private", False):
        result["config"]["mcp_servers"] = value
        with pytest.raises(preflight.PreflightError, match="invalid-mcp-configuration"):
            check(result)


@pytest.mark.parametrize("name", ["", "has.dot", "has space", "bad/id", "한글", "x" * 129])
def test_mcp_names_are_safe_bounded_internal_labels(name):
    with pytest.raises(preflight.PreflightError, match="invalid-mcp-name"):
        check(candidate(servers={name: {}}))


def test_mcp_name_and_count_boundaries():
    servers = {"x" * 128: {}, **{f"server-{index}": {} for index in range(63)}}
    assert check(candidate(servers=servers))["mcp_servers_count"] == 64
    servers["one-more"] = {}
    with pytest.raises(preflight.PreflightError, match="invalid-mcp-configuration"):
        check(candidate(servers=servers))


def test_mcp_bodies_are_bounded_opaque_dicts_in_discovery_not_startup_validation():
    result = candidate(servers={"server": {"unknown": [{"private": "value"}], "enabled": None}})
    assert check(result)["startup_behavior_verified"] is False
    for value in (None, False, "private", []):
        result["config"]["mcp_servers"]["server"] = value
        with pytest.raises(preflight.PreflightError, match="invalid-mcp-configuration"):
            check(result)


@pytest.mark.parametrize("value", [True, None, 0, "false", [], {}])
def test_generation_requires_enabled_exactly_false_not_falsy(value):
    with pytest.raises(preflight.PreflightError, match="mcp-not-explicitly-disabled"):
        check(candidate(servers={"server": {"enabled": value}}), phase="generation")


def test_generation_missing_enabled_marker_is_not_disabled():
    with pytest.raises(preflight.PreflightError, match="mcp-not-explicitly-disabled"):
        check(candidate(servers={"server": {}}), phase="generation")


@pytest.mark.parametrize("after_names", [(), ("different",), ("server", "extra")])
def test_pair_rejects_missing_added_or_replaced_discovered_names(after_names):
    before = candidate(servers={"server": {}})
    after = candidate(servers={name: {"enabled": False} for name in after_names})
    with pytest.raises(preflight.PreflightError, match="mcp-name-mismatch"):
        preflight.compare_configs(before, after, configuration())


def test_pair_rechecks_both_recipe_candidates_and_generation_flags():
    for side in (0, 1):
        results = [candidate(), candidate()]
        results[side]["config"]["model_reasoning_effort"] = "medium"
        with pytest.raises(preflight.PreflightError, match="recipe-value-mismatch"):
            preflight.compare_configs(*results, configuration())
    before = candidate(servers={"server": {"enabled": False}})
    after = candidate(servers={"server": {"enabled": True}})
    with pytest.raises(preflight.PreflightError, match="mcp-not-explicitly-disabled"):
        preflight.compare_configs(before, after, configuration())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_rejected_before_opaque_metadata_is_discarded(value):
    result = candidate()
    result["origins"] = {"private": value}
    with pytest.raises(preflight.PreflightError, match="nonfinite-input-number"):
        check(result)


def test_json_type_key_utf8_and_number_bounds_have_closed_redacted_errors():
    for value, code in (
        (b"private", "invalid-input-type"),
        (("private",), "invalid-input-type"),
        ({1: "private"}, "invalid-input-key"),
        ("\ud800private", "invalid-input-utf8"),
        (1 << preflight.MAX_INTEGER_BITS, "input-number-limit"),
    ):
        result = candidate()
        result["origins"] = {"private": value}
        with pytest.raises(preflight.PreflightError) as error:
            check(result)
        assert str(error.value) == code
        assert "private" not in repr(error.value)


def test_cyclic_input_fails_closed_without_recursive_private_repr():
    result = candidate()
    result["origins"]["private"] = result
    with pytest.raises(preflight.PreflightError, match="cyclic-input"):
        check(result)


def test_depth_and_node_bounds_are_checked_before_metadata_is_discarded(monkeypatch):
    result = candidate()
    nested = None
    for _ in range(preflight.MAX_DEPTH + 1):
        nested = [nested]
    result["origins"] = {"private": nested}
    with pytest.raises(preflight.PreflightError, match="input-too-deep"):
        check(result)
    result["origins"] = {"private": [None] * preflight.MAX_NODES}
    with pytest.raises(preflight.PreflightError, match="input-too-many-nodes"):
        check(result)
    monkeypatch.setattr(preflight, "MAX_NODES", 1)
    with pytest.raises(preflight.PreflightError, match="input-too-many-nodes"):
        check(candidate())


def test_depth_boundary_includes_root_containers_and_scalar_leaf():
    result = candidate()
    nested = None
    for _ in range(preflight.MAX_DEPTH - 2):
        nested = [nested]
    result["origins"] = {"private": nested}
    check(result)
    result["origins"] = {"private": [nested]}
    with pytest.raises(preflight.PreflightError, match="input-too-deep"):
        check(result)


def test_node_boundary_counts_dict_keys_as_well_as_values_and_containers(monkeypatch):
    def nodes(value):
        if type(value) is dict:
            return 1 + sum(nodes(key) + nodes(child) for key, child in value.items())
        if type(value) is list:
            return 1 + sum(nodes(child) for child in value)
        return 1

    result = candidate()
    result["origins"] = {"private": [{"metadata": "discarded"}, None, True, 1.5]}
    count = nodes(result)
    monkeypatch.setattr(preflight, "MAX_NODES", count)
    check(result)
    monkeypatch.setattr(preflight, "MAX_NODES", count - 1)
    with pytest.raises(preflight.PreflightError, match="input-too-many-nodes"):
        check(result)


def test_builtin_subclasses_and_user_objects_are_not_invoked_or_coerced():
    class DangerousDict(dict):
        def items(self):
            pytest.fail("custom dictionary behavior must not run")

    class DangerousString(str):
        def encode(self, *args, **kwargs):
            pytest.fail("custom string behavior must not run")

    class DangerousObject:
        def __repr__(self):
            pytest.fail("private object representation must not run")

    for value in (DangerousDict(), DangerousString("private"), DangerousObject()):
        result = candidate()
        result["origins"] = {"private": value}
        with pytest.raises(preflight.PreflightError, match="invalid-input-type"):
            check(result)
    result = candidate()
    result["origins"] = {DangerousString("private"): None}
    with pytest.raises(preflight.PreflightError, match="invalid-input-key"):
        check(result)


def test_size_limit_counts_actual_compact_utf8_escaped_json_bytes(monkeypatch):
    result = candidate()
    result["origins"] = {"private": "한국어\n\t"}
    size = len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    monkeypatch.setattr(preflight, "MAX_BYTES", size)
    check(result)
    monkeypatch.setattr(preflight, "MAX_BYTES", size - 1)
    with pytest.raises(preflight.PreflightError, match="input-too-large"):
        check(result)


def test_oversized_string_fails_before_full_serialization():
    result = candidate()
    result["origins"] = {"private": "x" * (preflight.MAX_BYTES + 1)}
    with pytest.raises(preflight.PreflightError, match="input-too-large"):
        check(result)


def test_checker_and_pair_perform_no_io_process_network_account_or_reference_access(monkeypatch):
    before, after, selected = candidate(), candidate(), configuration()

    def forbidden(*args, **kwargs):
        pytest.fail("pure preflight cannot access files, processes, network or evaluation answers")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(planner, "build_trial_plan", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "score_reference", forbidden)
    assert preflight.check_config(before, selected, phase="discovery")["mcp_servers_count"] == 0
    assert preflight.compare_configs(before, after, selected)["supplied_mcp_names_match"] is True
