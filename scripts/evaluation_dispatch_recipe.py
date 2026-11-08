"""Pure offline dispatch descriptors and request-frame candidates, never transport.

No process, account, configuration, filesystem, clock or provider is accessed here.
Caller-supplied cwd/thread labels are not observations. These selected request shapes
cannot prove effective settings, provider schema support or complete harness isolation.
The product adapter and its mutable configuration are not imported or modified.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict
from types import MappingProxyType

from scripts import evaluation_invocation as codec
from scripts import evaluation_trial_plan as planner

NS = 1_000_000_000
CONFIRM_TTL_NS = 300 * NS
CLOCK_SKEW_NS = 5 * NS
MAX_FRAME_BYTES = 256 * 1024
MAX_STREAM_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 4096
MAX_PENDING = 128
MAX_PROCESS_GROUPS = 2
CLEANUP_SECONDS_PER_GROUP = 5
MAX_MODEL_PAGES = 10
MAX_MODELS_PER_PAGE = 100
MAX_MODEL_ENTRIES = 1000
MAX_RPC_ID = 2**31 - 1
VERSION = "0.153.0"
NAME = "evaluation-stdio-0.153.0-v1"
BASELINE = "851d84cd4ab35bb35d262e2dbef23af7810dc5f3"
ENVIRONMENT_ALLOWLIST = (
    "PATH",
    "HOME",
    "CODEX_HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "USER",
    "LOGNAME",
)
DISABLED_FEATURES = (
    "apps",
    "auth_elicitation",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "code_mode",
    "code_mode_host",
    "code_mode_only",
    "code_mode_prewarm",
    "computer_use",
    "goals",
    "guardian_approval",
    "hooks",
    "image_generation",
    "in_app_browser",
    "memories",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "plugin_sharing",
    "remote_plugin",
    "request_permissions_tool",
    "shell_snapshot",
    "shell_snapshot_v2",
    "shell_tool",
    "skill_mcp_dependency_install",
    "skill_search",
    "sleep_tool",
    "tool_suggest",
    "unbounded_connection_retries",
    "unified_exec",
    "view_image",
    "workspace_dependencies",
    "tool_call_mcp_elicitation",
)
# Tuple-valued empty arrays keep this owned constant deeply immutable. JSON exports
# materialize them as detached arrays; no product constant is referenced.
CONFIG = MappingProxyType(
    {
        **{f"features.{name}": False for name in DISABLED_FEATURES},
        "features.skip_host_skill_discovery": True,
        "suppress_unstable_features_warning": True,
        "project_doc_max_bytes": 0,
        "web_search": "disabled",
        "notify": (),
        "developer_instructions": codec.INSTRUCTIONS,
        "instructions": "",
        "model_provider": "openai",
        "chatgpt_base_url": "https://chatgpt.com/backend-api",
        "approval_policy": "on-request",
        "sandbox_mode": "read-only",
        "analytics.enabled": False,
        "otel.exporter": "none",
        "otel.trace_exporter": "none",
        "otel.log_user_prompt": False,
        "include_apps_instructions": False,
        "include_collaboration_mode_instructions": False,
        "include_environment_context": False,
        "include_permissions_instructions": False,
        "memories.generate_memories": False,
        "memories.use_memories": False,
        "history.persistence": "none",
    }
)
ALLOWED_EVENTS = (
    "thread/started",
    "thread/status/changed",
    "thread/settings/updated",
    "turn/started",
    "turn/completed",
    "item/started",
    "item/completed",
    "item/agentMessage/delta",
    "item/reasoning/summaryTextDelta",
    "item/reasoning/summaryPartAdded",
    "item/reasoning/textDelta",
    "thread/tokenUsage/updated",
    "account/rateLimits/updated",
    "model/verification",
    "model/safetyBuffering/updated",
    "turn/moderationMetadata",
    "remoteControl/status/changed",
)
SCHEMA_HASHES = MappingProxyType(
    {
        "v1/InitializeParams.json": (
            "6f0094be9a65242ec779a40794cbd4fdfa32fca1e45084a16adfb50501d33ea2"
        ),
        "v2/ConfigReadParams.json": (
            "257c54a423b47c1d209ff1076765a1564d82322fd5161670fd489a2874de1bac"
        ),
        "v2/GetAccountParams.json": (
            "30b545275f60975b55bd6fbaafd70f15505801d14168ee82d3931b6e93c78aab"
        ),
        "v2/ModelListParams.json": (
            "de29a536c00a5b8f46f34dba417dabd93365305571a8ed200e33bea85db68b5a"
        ),
        "v2/ThreadStartParams.json": (
            "25f490368ec6df52a2a3b82a5469d2413307eb93439121b309f415b5648eee7a"
        ),
        "v2/ThreadStartResponse.json": (
            "a338467af5fc271ace917f9d1262405642c3df3b66116aa105343db86cc9a76d"
        ),
        "v2/TurnStartParams.json": (
            "b36fb37326b1cf69f75c8b306f1f886d53a57c4b1b985e08e298e2407ea2ad02"
        ),
        "v2/ThreadSettingsUpdatedNotification.json": (
            "f7865eabaa34c7895a1ae345e51c1ba181a63c649237d36583b80f9d759b0f53"
        ),
        "ClientRequest.json": "05c82ead1a820c765c23d3a1d262e4ae54889785276ee1acf7c494141fd94d70",
        "ClientNotification.json": (
            "706cf248d75027c84a3c63348d0ed507182e8eba40069dd17541793de029145a"
        ),
    }
)
LIMITATIONS = (
    "Offline candidates only; nothing is sent and no decision or execution is authorized.",
    "Selected parameter-shape checks are not complete protocol or provider conformance.",
    "Protocol outputSchema accepts arbitrary JSON, not a guarantee of nested-schema support.",
    "Effective config, MCP discovery startup, model availability and settings remain unverified.",
    "Empty cwd/thread labels and requested restrictions do not prove harness isolation.",
    "Surfaced retries are batch-fatal by policy; hidden retries and usage cannot be capped.",
    "First catalog page only: later cursor/IDs need rebuilding, not inferred runtime dispatch.",
    "RPC bytes, cwd and thread IDs are caller-supplied candidates, never runtime observations.",
)


class RecipeError(ValueError):
    """Invalid owned recipe/frame inputs; diagnostics do not include private values."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RecipeError(code)


def _config(configuration: planner.TrialConfig) -> None:
    _require(type(configuration) is planner.TrialConfig, "invalid-configuration")
    try:
        configuration.__post_init__()
    except planner.TrialPlanError as error:
        raise RecipeError("invalid-configuration") from error


def _canonical(value: object) -> str:
    try:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        raw.encode("utf-8")
        return raw
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise RecipeError("invalid-json-value") from error


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _flags() -> dict:
    return {
        "runtime_observed": False,
        "provider_freshness_verified": False,
        "sharing_authorized": False,
        "execution_authorized": False,
        "live_configuration_frozen": False,
        "live_benchmark_ready": False,
        "model_quality_measured": False,
        "provider_calls_by_this_tool": 0,
        "live_trials": 0,
        "target_execution": "not-run",
        "transport_status": "not-implemented",
    }


def dispatch_window_seconds(configuration: planner.TrialConfig) -> int:
    _config(configuration)
    return 60 + 14 * configuration.repetitions * (configuration.timeout_seconds + 10)


def descriptor(configuration: planner.TrialConfig) -> dict:
    """Return detached fully materialized choices, not effective or approved config."""
    _config(configuration)
    process_config = json.loads(_canonical(dict(CONFIG)))
    process_config.update(
        model=configuration.model,
        model_reasoning_effort=configuration.effort,
        approvals_reviewer="user",
    )
    return {
        "schema_version": "0.1",
        "kind": "offline-evaluation-dispatch-recipe",
        "name": NAME,
        "codex_version": VERSION,
        "product_config_source_baseline": BASELINE,
        "configuration": asdict(configuration),
        "codec_recipe_id": codec.RECIPE_ID,
        "process_config": process_config,
        "disabled_features": list(DISABLED_FEATURES),
        "environment_allowlist": list(ENVIRONMENT_ALLOWLIST),
        "instructions": {
            "base": codec.INSTRUCTIONS,
            "developer": codec.INSTRUCTIONS,
            "collaboration_developer": codec.INSTRUCTIONS,
        },
        "generated_schema_evidence": {
            "version": VERSION,
            "experimental": True,
            "generation": "codex app-server generate-json-schema --experimental --out <owned-dir>",
            "raw_document_sha256": dict(SCHEMA_HASHES),
            "scope": "selected-shape-evidence-not-runtime-or-nested-schema-support",
        },
        "inherited_config_policy": {
            "model_endpoint_override": "openai_base_url-missing-or-null-only",
            "reject_truthy_external_context_keys": [
                "model_instructions_file",
                "experimental_compact_prompt_file",
                "model_catalog_json",
                "experimental_thread_store_endpoint",
            ],
            "unknown_instruction_profile_provider_context_override": "refuse-unreviewed",
            "mcp": "enumerate-bounded-names-then-disable-each-on-generation-restart",
            "effective_and_discovery_behavior": "unverified-process-implementation-gate",
        },
        "limits": {
            "confirmation_ttl_ns": CONFIRM_TTL_NS,
            "clock_skew_ns": CLOCK_SKEW_NS,
            "slot_timeout_seconds": configuration.timeout_seconds,
            "dispatch_window_seconds": dispatch_window_seconds(configuration),
            "dispatch_window_ns": dispatch_window_seconds(configuration) * NS,
            "frame_bytes": MAX_FRAME_BYTES,
            "received_stream_bytes": MAX_STREAM_BYTES,
            "received_events": MAX_EVENTS,
            "queued_notifications": MAX_PENDING,
            "max_process_groups_per_slot": MAX_PROCESS_GROUPS,
            "cleanup_seconds_per_group": CLEANUP_SECONDS_PER_GROUP,
            "max_mcp_names": 64,
            "max_mcp_name_characters": 128,
            "model_pages": MAX_MODEL_PAGES,
            "models_per_page": MAX_MODELS_PER_PAGE,
            "model_entries": MAX_MODEL_ENTRIES,
            "rpc_id_maximum": MAX_RPC_ID,
            "cwd_label_characters": 1024,
            "thread_label_characters": 128,
            "concurrent_slots": 1,
            "planned_slots": 14 * configuration.repetitions,
            "question_opportunities": 42 * configuration.repetitions,
        },
        "wire_policy": {
            "frame_encoding": "canonical-sorted-compact-finite-json-utf8-with-final-newline",
            "experimental_api": True,
            "remote_control": "explicit-status-read-disabled-required",
            "remote_status_request_params": None,
            "model_effort": "exact-advertised-requested-values-no-default-or-fallback",
            "catalog_cursor": "unique-progressing-bounded-pages",
            "initial_reasoning_effort": "non-null-exact-report-required",
            "collaboration": "explicit-default-mode-non-null-equal-model-effort-instructions",
            "collaboration_precedence": "overrides-top-level-model-effort-developer-settings",
            "complete_matching_settings_observation": "required-no-null-or-missing-substitution",
            "allowed_events": list(ALLOWED_EVENTS),
            "remote_status_event": "disabled-only",
            "errors_warnings_tools_unknown_events": "batch-fatal",
            "surfaced_retry": "batch-fatal-no-application-retry",
            "hidden_retry_bound": None,
            "final": "unique-explicit-final-answer-item-then-successful-turn-completed",
            "snapshot_final": "identical-repeat-only-no-second-or-conflicting-final",
            "missing_usage": None,
        },
        "state_policy": {
            "ordering_policy": planner.ORDER_POLICY,
            "dispatch_window_formula": "60+14*repetitions*(timeout_seconds+10)",
            "clock_unit": "integer-nanoseconds",
            "preview_anchor": "original-monotonic-and-wall-no-reanchor",
            "confirmation": "0<=elapsed<ttl-one-whole-batch-decision",
            "dispatch": "monotonic-now<fixed-acceptance-deadline",
            "clock_integrity": "nondecreasing-monotonic-and-original-anchor-discrepancy<=skew",
            "reservation": "consumes-slot-before-process-start",
            "turn_send": "attempted-before-first-possible-write-no-intervening-await",
            "uncertain_send": "no-replenishment-or-retry",
            "sent_slot_expiry": "drain-under-original-timeout-and-cleanup-no-extension",
            "failure": "stop-on-first-nonvalid-null-answers-remain-valid",
            "cleanup": "primary-and-cleanup-failures-separate-unconfirmed-is-fatal",
            "remaining_slots": "retain-skipped-reasons-and-full-denominators",
            "ledger": "future-single-owner-in-memory-no-persistence-import-or-resume",
        },
        "limitations": list(LIMITATIONS),
        **_flags(),
    }


def recipe_id(configuration: planner.TrialConfig) -> str:
    return "dispatch-recipe-" + _digest(_canonical(descriptor(configuration)))


def _frame(method: str, params: object, rpc_id: int | None) -> dict:
    message = {"method": method}
    if rpc_id is not None:
        message.update(id=rpc_id, params=copy.deepcopy(params))
    raw = _canonical(message) + "\n"
    size = len(raw.encode("utf-8"))
    _require(size <= MAX_FRAME_BYTES, "frame-too-large")
    return {
        "method": method,
        "message": message,
        "frame_text": raw,
        "frame_sha256": _digest(raw),
        "frame_bytes": size,
    }


def frames(
    invocation: codec.Invocation, *, cwd: str, thread_id: str, first_rpc_id: int = 1
) -> dict:
    """Build one synthetic generation sequence and reusable discovery frame candidates.

    No acknowledgement, thread existence, cwd emptiness or subsequent catalog page is
    inferred. Real pagination/phase RPC IDs require a future rebuilt runtime sequence.
    """
    _require(type(invocation) is codec.Invocation, "invalid-invocation")
    try:
        invocation.__post_init__()
    except (codec.InvocationError, planner.TrialPlanError) as error:
        raise RecipeError("invalid-invocation") from error
    _require(
        type(cwd) is str
        and cwd.startswith("/")
        and len(cwd) <= 1024
        and "\\" not in cwd
        and "//" not in cwd
        and all(part not in (".", "..") for part in cwd.split("/"))
        and all(character.isprintable() for character in cwd),
        "invalid-cwd-label",
    )
    try:
        cwd.encode("utf-8")
    except UnicodeError as error:
        raise RecipeError("invalid-cwd-label") from error
    _require(
        type(thread_id) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", thread_id) is not None,
        "invalid-thread-label",
    )
    _require(type(first_rpc_id) is int and 1 <= first_rpc_id <= MAX_RPC_ID - 6, "invalid-rpc-id")
    configuration = invocation.session.configuration
    common = codec.INSTRUCTIONS
    parameters = {
        "initialize": {
            "clientInfo": {"name": "authzest-evaluation", "version": "0.1"},
            "capabilities": {"experimentalApi": True},
        },
        "initialized": None,
        "config/read": {"includeLayers": False},
        "remoteControl/status/read": None,
        "account/read": {"refreshToken": False},
        "model/list": {"limit": 100, "includeHidden": False},
        "thread/start": {
            "model": configuration.model,
            "modelProvider": "openai",
            "allowProviderModelFallback": False,
            "ephemeral": True,
            "cwd": cwd,
            "environments": [],
            "dynamicTools": [],
            "selectedCapabilityRoots": [],
            "runtimeWorkspaceRoots": [],
            "sandbox": "read-only",
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "baseInstructions": common,
            "developerInstructions": common,
            "config": {"model_reasoning_effort": configuration.effort},
            "experimentalRawEvents": False,
        },
        "turn/start": {
            "threadId": thread_id,
            "model": configuration.model,
            "effort": configuration.effort,
            "input": [{"type": "text", "text": invocation.message_text}],
            "outputSchema": invocation.output_schema,
            "environments": [],
            "runtimeWorkspaceRoots": [],
            "cwd": cwd,
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "collaborationMode": {
                "mode": "default",
                "settings": {
                    "model": configuration.model,
                    "reasoning_effort": configuration.effort,
                    "developer_instructions": common,
                },
            },
            "serviceTierForTurn": "default",
        },
    }
    output = []
    rpc_id = first_rpc_id
    for method, params in parameters.items():
        notification = method == "initialized"
        output.append(_frame(method, params, None if notification else rpc_id))
        rpc_id += not notification
    return {
        "schema_version": "0.1",
        "kind": "offline-evaluation-dispatch-frames",
        "recipe_id": recipe_id(configuration),
        "invocation_id": invocation.invocation_id,
        "original_message_sha256": invocation.original_message_sha256,
        "message_sha256": invocation.message_sha256,
        "output_schema_sha256": invocation.output_schema_sha256,
        "parameters": copy.deepcopy(parameters),
        "frame_candidates": output,
        "discovery_methods": ["initialize", "initialized", "config/read"],
        "candidate_scope": "single-generation-first-catalog-page-not-sent",
        "limitations": list(LIMITATIONS),
        **_flags(),
    }
