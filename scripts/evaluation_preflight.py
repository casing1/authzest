"""Check caller-supplied configuration candidates without accessing any runtime.

This deliberately narrow offline policy is not the complete generated Config schema.
Origins and MCP bodies are bounded opaque JSON, not evidence of selected-profile
absence, safe startup, server behavior or harness isolation. Nothing here launches,
authorizes, reads or changes an account, process, configuration file or provider.
"""

from __future__ import annotations

import json
import math
import re

from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_trial_plan as planner

POLICY_VERSION = "offline-config-read-candidate-v1"
CONFIG_SCHEMA_SHA256 = "96a04a3f7fff2dc7fafc9f831e8bcd422e021d697dd2c14c801f098a9f21396d"
MAX_BYTES = 256 * 1024
MAX_DEPTH = 16
MAX_NODES = 4096
MAX_INTEGER_BITS = 4096
MAX_MCP_SERVERS = 64
MAX_MCP_NAME_CHARACTERS = 128

# Reviewed representations of unset optional fields, never proof of disabled tools.
# Unknown fields (even null) are unsupported. Required recipe fields cannot use this
# exception. Do not expand this list merely to accept an observed user configuration.
INACTIVE_OPTIONAL_FIELDS = frozenset(
    {
        "openai_base_url",
        "model_instructions_file",
        "experimental_compact_prompt_file",
        "model_catalog_json",
        "experimental_thread_store_endpoint",
        "apps",
        "browser_use",
        "compact_prompt",
        "computer_use",
        "desktop",
        "forced_chatgpt_workspace_id",
        "forced_login_method",
        "model_auto_compact_token_limit",
        "model_auto_compact_token_limit_scope",
        "model_context_window",
        "model_reasoning_summary",
        "model_verbosity",
        "review_model",
        "sandbox_workspace_write",
        "service_tier",
        "tools",
    }
)
LIMITATIONS = (
    "Caller-supplied candidates only; no authenticated process/configuration observation.",
    "Narrow recipe policy, not complete generated-protocol or provider conformance.",
    "Origins are discarded opaque metadata; selected profiles/provenance are not assessed.",
    "MCP names and disabled markers do not establish startup behavior or safe MCP bodies.",
    "A matching pair does not prove the same process, environment or unmodified runtime.",
    "No launch safety, harness isolation, execution authority or live freeze is established.",
)


class PreflightError(ValueError):
    """Closed diagnostics; input paths, keys, values and private hashes are not echoed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PreflightError(code)


def _bounded(value: object) -> None:
    """Bound a JSON-like value before interpreting it, with exact built-in types.

    This accepts already-decoded values, not raw JSON text. It cannot detect duplicate
    keys discarded by another parser. Size counts compact UTF-8 JSON including escapes.
    """
    nodes = 0
    size = 0
    ancestors: set[int] = set()

    def charge(amount: int) -> None:
        nonlocal size
        size += amount
        _require(size <= MAX_BYTES, "input-too-large")

    def visit(node: object, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        _require(nodes <= MAX_NODES, "input-too-many-nodes")
        _require(depth <= MAX_DEPTH, "input-too-deep")
        kind = type(node)
        if kind is str:
            _require(len(node) <= MAX_BYTES, "input-too-large")
            _require(
                not any(0xD800 <= ord(character) <= 0xDFFF for character in node),
                "invalid-input-utf8",
            )
            charge(len(json.dumps(node, ensure_ascii=False).encode("utf-8")))
        elif node is None or kind is bool:
            charge(len(json.dumps(node)))
        elif kind is int:
            _require(node.bit_length() <= MAX_INTEGER_BITS, "input-number-limit")
            charge(len(str(node)))
        elif kind is float:
            _require(math.isfinite(node), "nonfinite-input-number")
            charge(len(json.dumps(node)))
        elif kind in (dict, list):
            _require(id(node) not in ancestors, "cyclic-input")
            _require(nodes + len(node) <= MAX_NODES, "input-too-many-nodes")
            ancestors.add(id(node))
            charge(2 + max(0, len(node) - 1))
            if kind is dict:
                for key, child in node.items():
                    _require(type(key) is str, "invalid-input-key")
                    visit(key, depth + 1)
                    charge(1)
                    visit(child, depth + 1)
            else:
                for child in node:
                    visit(child, depth + 1)
            ancestors.remove(id(node))
        else:
            raise PreflightError("invalid-input-type")

    visit(value, 0)


def _expected(configuration: planner.TrialConfig) -> tuple[dict, int]:
    try:
        flat = recipe.descriptor(configuration)["process_config"]
    except recipe.RecipeError:
        raise PreflightError("invalid-configuration") from None
    nested: dict = {}
    for path, value in flat.items():
        container = nested
        parts = path.split(".")
        for part in parts[:-1]:
            container = container.setdefault(part, {})
        container[parts[-1]] = value
    return nested, len(flat)


def _match(actual: dict, expected: dict, *, root: bool = False) -> None:
    for key, expected_value in expected.items():
        _require(key in actual, "recipe-value-mismatch")
        actual_value = actual[key]
        _require(type(actual_value) is type(expected_value), "recipe-value-mismatch")
        if type(expected_value) is dict:
            _match(actual_value, expected_value)
        else:
            _require(actual_value == expected_value, "recipe-value-mismatch")
    for key in actual.keys() - expected.keys():
        if root and key == "mcp_servers":
            continue
        if root and key in INACTIVE_OPTIONAL_FIELDS:
            _require(actual[key] is None, "inactive-override-set")
        else:
            raise PreflightError("unreviewed-config-fields")


def _inspect(result: dict, configuration: planner.TrialConfig, phase: str) -> tuple[dict, tuple]:
    _require(type(phase) is str and phase in ("discovery", "generation"), "invalid-phase")
    expected, count = _expected(configuration)
    _bounded(result)
    _require(type(result) is dict, "invalid-result")
    _require(set(result) <= {"config", "origins", "layers"}, "unreviewed-result-fields")
    _require("config" in result and type(result["config"]) is dict, "missing-effective-config")
    _require("origins" in result and type(result["origins"]) is dict, "missing-config-origins")
    _require(result.get("layers") is None, "unexpected-config-layers")
    config = result["config"]
    _match(config, expected, root=True)
    _require("mcp_servers" in config, "missing-mcp-configuration")
    servers = config["mcp_servers"]
    _require(
        type(servers) is dict and len(servers) <= MAX_MCP_SERVERS,
        "invalid-mcp-configuration",
    )
    for name, body in servers.items():
        _require(
            re.fullmatch(rf"[A-Za-z0-9_-]{{1,{MAX_MCP_NAME_CHARACTERS}}}", name) is not None,
            "invalid-mcp-name",
        )
        _require(type(body) is dict, "invalid-mcp-configuration")
        if phase == "generation":
            _require(body.get("enabled") is False, "mcp-not-explicitly-disabled")
    names = tuple(sorted(servers))
    return (
        {
            "schema_version": "0.1",
            "kind": "offline-config-candidate-check",
            "policy_version": POLICY_VERSION,
            "phase": phase,
            "required_recipe_fields_count": count,
            "mcp_servers_count": len(names),
            "origins_entries_count": len(result["origins"]),
            "supplied_recipe_values_match": True,
            "origins_metadata_retained": False,
            "configuration_values_exported": False,
            "private_names_exported": False,
            "input_provenance": "caller-supplied-unverified",
            "runtime_observed": False,
            "provider_freshness_verified": False,
            "startup_behavior_verified": False,
            "harness_isolation_verified": False,
            "full_protocol_conformance_verified": False,
            "sharing_authorized": False,
            "execution_authorized": False,
            "live_configuration_frozen": False,
            "live_benchmark_ready": False,
            "safe_to_launch": False,
            "provider_calls_by_this_tool": 0,
            "target_execution": "not-run",
            "transport_status": "not-implemented",
            "limitations": list(LIMITATIONS),
        },
        names,
    )


def check_config(result: dict, configuration: planner.TrialConfig, *, phase: str) -> dict:
    """Return detached redacted metadata, never private configuration or MCP names."""
    summary, _ = _inspect(result, configuration, phase)
    return summary


def compare_configs(
    discovery_result: dict, generation_result: dict, configuration: planner.TrialConfig
) -> dict:
    """Check a supplied pair and its exact MCP-name continuity, not actual processes."""
    discovery, before_names = _inspect(discovery_result, configuration, "discovery")
    generation, after_names = _inspect(generation_result, configuration, "generation")
    _require(before_names == after_names, "mcp-name-mismatch")
    return {
        "schema_version": "0.1",
        "kind": "offline-config-candidate-pair-check",
        "policy_version": POLICY_VERSION,
        "supplied_mcp_names_match": True,
        "discovery": discovery,
        "generation": generation,
        "runtime_observed": False,
        "provider_freshness_verified": False,
        "sharing_authorized": False,
        "execution_authorized": False,
        "live_configuration_frozen": False,
        "live_benchmark_ready": False,
        "safe_to_launch": False,
        "provider_calls_by_this_tool": 0,
        "target_execution": "not-run",
        "transport_status": "not-implemented",
        "limitations": list(LIMITATIONS),
    }
