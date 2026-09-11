"""Version-scoped, opt-in Codex stdio transport for the packaged fixture only.

The Codex installation and its managed authentication are trusted dependencies.
This is not a general agent launcher or a sandbox for an untrusted executable.
No credentials, raw stderr, account profile or conversation logs are retained.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import signal
from collections import deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from authzest.codex.contracts import MAX_JSON_BYTES, CodexAnalysisRequest, canonical, decode
from authzest.codex.fixture_draft import (
    HOST_INSTRUCTIONS,
    FixtureDraft,
    fixture_output_schema,
    fixture_prompt,
    validate_fixture_draft,
)

SUPPORTED_CODEX_VERSION = "0.153.0"
MAX_STREAM_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 4096
ALLOWED_EVENTS = {
    "remoteControl/status/changed",
    "thread/started",
    "thread/status/changed",
    "turn/started",
    "turn/completed",
    "item/started",
    "item/completed",
    "item/agentMessage/delta",
    "item/reasoning/summaryTextDelta",
    "item/reasoning/summaryPartAdded",
    "item/reasoning/textDelta",
    "thread/tokenUsage/updated",
}
BASE_INSTRUCTIONS = HOST_INSTRUCTIONS
DISABLED_FEATURES = tuple(
    [
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
    ]
)
CONFIG = {
    **{f"features.{name}": False for name in DISABLED_FEATURES},
    "features.skip_host_skill_discovery": True,
    "project_doc_max_bytes": 0,
    "web_search": "disabled",
    "notify": [],
    "developer_instructions": BASE_INSTRUCTIONS,
    "instructions": "",
    "model_provider": "openai",
    "openai_base_url": "https://api.openai.com/v1",
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


class AppServerError(RuntimeError):
    """Stable redacted error; never include an RPC error body or process output."""


def _environment() -> dict[str, str]:
    # Preserve the existing auth location, never copy tokens or repurpose home.
    # Do not forward API keys, base-URL overrides, proxies or telemetry variables.
    return {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "CODEX_HOME", "TMPDIR", "LANG", "LC_ALL", "USER", "LOGNAME"}
    }


def _arguments(executable: str, disabled_servers: tuple[str, ...]) -> list[str]:
    args = [executable]
    for key, value in CONFIG.items():
        args.extend(("-c", f"{key}={canonical(value)}"))
    for name in disabled_servers:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name):
            raise AppServerError("Unsupported inherited MCP configuration")
        args.extend(("-c", f"mcp_servers.{name}.enabled=false"))
    return [*args, "app-server", "--listen", "stdio://"]


async def _stop(process: asyncio.subprocess.Process) -> None:
    # The npm CLI wrapper launches a native child; killing only the wrapper leaks it.
    # This process group was created exclusively for this invocation.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await asyncio.wait_for(process.wait(), timeout=5)


@asynccontextmanager
async def _process(args: list[str], cwd: Path):
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=_environment(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        limit=MAX_JSON_BYTES + 1,
        start_new_session=True,
    )
    try:
        yield process
    finally:
        # Shield cleanup from a single caller cancellation, then still propagate it.
        cleanup = asyncio.create_task(_stop(process))
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
            raise


class _Session:
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self.sequence = 0
        self.total_bytes = 0
        self.events = 0
        self.pending: deque[dict[str, Any]] = deque()

    async def send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        encoded = (canonical(message) + "\n").encode()
        if len(encoded) > MAX_JSON_BYTES:
            raise AppServerError("Request size limit exceeded")
        self.process.stdin.write(encoded)
        await self.process.stdin.drain()

    async def receive(self) -> dict[str, Any]:
        assert self.process.stdout is not None
        try:
            line = await self.process.stdout.readline()
            self.total_bytes += len(line)
            self.events += 1
            if (
                not line.endswith(b"\n")
                or len(line) > MAX_JSON_BYTES
                or self.total_bytes > MAX_STREAM_BYTES
                or self.events > MAX_EVENTS
            ):
                raise AppServerError("Incomplete or oversized Codex stream")
            value = decode(line.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise AppServerError("Invalid Codex protocol message") from exc
        if "method" in value and "id" in value:
            # Refuse every server-initiated request, including permission/MCP/tool requests.
            await self.send({"id": value["id"], "error": {"code": -32601, "message": "Denied"}})
            raise AppServerError("Codex requested an unsupported capability")
        if "method" in value:
            method, params = value["method"], value.get("params")
            if method not in ALLOWED_EVENTS or type(params) is not dict:
                raise AppServerError("Unexpected Codex event")
            if method == "remoteControl/status/changed" and params.get("status") != "disabled":
                raise AppServerError("Remote Codex control must remain disabled")
            if method in {"item/started", "item/completed"}:
                _check_item(params.get("item"))
            if method in {"turn/started", "turn/completed"}:
                for item in params.get("turn", {}).get("items", []):
                    _check_item(item)
            if method == "thread/started" and params.get("thread", {}).get("turns"):
                raise AppServerError("Expected a fresh empty Codex thread")
        return value

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        request_id = self.sequence
        await self.send({"id": request_id, "method": method, "params": params})
        while True:
            value = await self.receive()
            if "id" not in value:
                if not isinstance(value.get("method"), str) or not isinstance(
                    value.get("params"), dict
                ):
                    raise AppServerError("Invalid Codex notification")
                if len(self.pending) >= 128:
                    raise AppServerError("Too many pending Codex notifications")
                self.pending.append(value)
                continue
            if type(value["id"]) is not int or value["id"] != request_id:
                raise AppServerError("Unexpected Codex response identity")
            if "error" in value or type(value.get("result")) is not dict:
                raise AppServerError("Codex request failed")
            return value["result"]

    async def initialize(self) -> dict[str, Any]:
        initialized = await self.request(
            "initialize",
            {
                "clientInfo": {"name": "authzest", "version": "0.1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        # Check server-reported version too, not only the executable's --version.
        agent = initialized.get("userAgent", "")
        if not isinstance(agent, str) or not re.search(
            rf"/{re.escape(SUPPORTED_CODEX_VERSION)}(?:\s|$)", agent
        ):
            raise AppServerError("Unsupported Codex App Server version")
        await self.send({"method": "initialized", "params": {}})
        result = await self.request("config/read", {"includeLayers": False})
        if type(result.get("config")) is not dict:
            raise AppServerError("Missing effective Codex configuration")
        return result["config"]


def _check_config(config: dict[str, Any], *, require_disabled_mcp: bool) -> tuple[str, ...]:
    for path, expected in CONFIG.items():
        value: Any = config
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if type(value) is not type(expected) or value != expected:
            raise AppServerError("Effective Codex configuration does not meet the boundary")
    if any(
        config.get(key)
        for key in (
            "model_instructions_file",
            "experimental_compact_prompt_file",
            "model_catalog_json",
            "experimental_thread_store_endpoint",
        )
    ):
        raise AppServerError("Inherited external context configuration is unsupported")
    servers = config.get("mcp_servers", {})
    if type(servers) is not dict or len(servers) > 64:
        raise AppServerError("Unsupported inherited MCP configuration")
    for name, data in servers.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name) or type(data) is not dict:
            raise AppServerError("Unsupported inherited MCP configuration")
        if require_disabled_mcp and data.get("enabled") is not False:
            raise AppServerError("An inherited MCP server is still enabled")
    return tuple(sorted(servers))


def _identifier(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise AppServerError("Invalid Codex thread or turn identity")
    return value


def _check_item(item: Any) -> None:
    if type(item) is not dict or item.get("type") not in {
        "userMessage",
        "agentMessage",
        "reasoning",
    }:
        raise AppServerError("Unexpected Codex tool or context item")
    if item.get("memoryCitation") or item.get("questions"):
        raise AppServerError("Unexpected Codex external context or interaction")


async def _finish(session: _Session, thread_id: str, turn_id: str) -> tuple[str, dict | None]:
    usage = None
    final_messages: dict[str, str] = {}
    while True:
        message = session.pending.popleft() if session.pending else await session.receive()
        method, params = message.get("method"), message.get("params")
        if method not in ALLOWED_EVENTS or type(params) is not dict:
            raise AppServerError("Unexpected Codex event")
        if method == "remoteControl/status/changed":
            if params.get("status") != "disabled":
                raise AppServerError("Remote Codex control must remain disabled")
            continue
        if method == "thread/started":
            if params.get("thread", {}).get("id") != thread_id:
                raise AppServerError("Codex thread identity mismatch")
            continue
        if params.get("threadId") != thread_id:
            raise AppServerError("Codex thread identity mismatch")
        if "turnId" in params and params["turnId"] != turn_id:
            raise AppServerError("Codex turn identity mismatch")
        if method in {"item/started", "item/completed"}:
            item = params.get("item")
            _check_item(item)
            if (
                method == "item/completed"
                and item["type"] == "agentMessage"
                and item.get("phase") in {None, "final_answer"}
            ):
                text = item.get("text")
                if type(text) is not str or len(text.encode("utf-8")) > MAX_JSON_BYTES:
                    raise AppServerError("Invalid Codex final output")
                item_id = _identifier(item.get("id"))
                if item_id in final_messages:
                    raise AppServerError("Duplicate Codex final output")
                final_messages[item_id] = text
        elif method == "thread/tokenUsage/updated":
            last = params.get("tokenUsage", {}).get("last", {})
            usage = {
                "input_tokens": last.get("inputTokens"),
                "output_tokens": last.get("outputTokens"),
            }
            if any(type(n) is not int or not 0 <= n <= 1_000_000_000 for n in usage.values()):
                raise AppServerError("Invalid Codex usage metadata")
        elif method in {"turn/started", "turn/completed"}:
            turn = params.get("turn", {})
            if turn.get("id") != turn_id:
                raise AppServerError("Codex turn identity mismatch")
            for item in turn.get("items", []):
                _check_item(item)
            if method == "turn/completed":
                if turn.get("status") != "completed" or turn.get("error") is not None:
                    raise AppServerError("Codex turn did not complete successfully")
                if len(final_messages) != 1:
                    raise AppServerError("Missing or ambiguous Codex final output")
                return next(iter(final_messages.values())), usage


class CodexAppServerAdapter:
    """Single-use, single-turn, fixture-only adapter. No application-level retries.

    The built-in provider can perform its own transport retries. The wall-clock
    limit includes metadata startup and generation but is not a token/dollar cap.
    An approval ID is a caller gate, not proof of an authenticated human identity.
    """

    name = "codex-app-server"

    def __init__(
        self,
        approved_request_id: str,
        *,
        timeout_seconds: float = 120,
        executable: str = "codex",
    ):
        if (
            os.name != "posix"
            or type(timeout_seconds) not in {int, float}
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 120
        ):
            raise AppServerError("Expected POSIX and a finite timeout in (0, 120]")
        self.approved_request_id = approved_request_id
        self.timeout_seconds = timeout_seconds
        self.executable = executable
        self.consumed = False

    async def analyze(self, request: CodexAnalysisRequest) -> str:
        """Satisfy the review-only adapter protocol without extending its JSON shape."""
        return (await self.draft(request)).review.payload_json

    async def draft(self, request: CodexAnalysisRequest) -> FixtureDraft:
        if self.consumed or self.approved_request_id != request.request_id:
            raise AppServerError("A fresh exact-request sharing decision is required")
        prompt, schema = fixture_prompt(request), fixture_output_schema(request)
        self.consumed = True
        model = request.to_dict()["config"]["model"]
        try:
            async with asyncio.timeout(self.timeout_seconds):
                with TemporaryDirectory(prefix="authzest-codex-empty-") as directory:
                    cwd = Path(directory).resolve()
                    # No thread is created by discovery. Empty TOML maps merge, so enumerate
                    # inherited MCP names without logging settings, then disable each on restart.
                    async with _process(_arguments(self.executable, ()), cwd) as process:
                        config = await _Session(process).initialize()
                        servers = _check_config(config, require_disabled_mcp=False)
                    async with _process(_arguments(self.executable, servers), cwd) as process:
                        session = _Session(process)
                        config = await session.initialize()
                        _check_config(config, require_disabled_mcp=True)
                        remote = await session.request("remoteControl/status/read", {})
                        if remote.get("status") != "disabled":
                            raise AppServerError("Remote Codex control must be disabled")
                        account = await session.request("account/read", {"refreshToken": False})
                        if (account.get("account") or {}).get("type") != "chatgpt":
                            raise AppServerError("Existing ChatGPT login is required")
                        models = await session.request(
                            "model/list", {"limit": 100, "includeHidden": False}
                        )
                        candidates = [m for m in models.get("data", []) if m.get("model") == model]
                        if len(candidates) != 1:
                            raise AppServerError(
                                "Requested model is not in the visible Codex catalog"
                            )
                        effort = candidates[0].get("defaultReasoningEffort")
                        if effort not in {"none", "minimal", "low", "medium", "high"}:
                            raise AppServerError("Unsupported model reasoning configuration")
                        started = await session.request(
                            "thread/start",
                            {
                                "model": model,
                                "modelProvider": "openai",
                                "allowProviderModelFallback": False,
                                "ephemeral": True,
                                "cwd": str(cwd),
                                "environments": [],
                                "dynamicTools": [],
                                "selectedCapabilityRoots": [],
                                "runtimeWorkspaceRoots": [],
                                "sandbox": "read-only",
                                "approvalPolicy": "on-request",
                                "baseInstructions": BASE_INSTRUCTIONS,
                                "developerInstructions": BASE_INSTRUCTIONS,
                                "experimentalRawEvents": False,
                            },
                        )
                        if (
                            started.get("model") != model
                            or started.get("modelProvider") != "openai"
                            or started.get("approvalPolicy") != "on-request"
                            or started.get("sandbox", {}).get("type") != "readOnly"
                            or started.get("sandbox", {}).get("networkAccess", False) is not False
                            or Path(started.get("cwd", "")).resolve() != cwd
                            or started.get("instructionSources")
                            or started.get("runtimeWorkspaceRoots")
                            or started.get("thread", {}).get("turns")
                        ):
                            raise AppServerError("Codex thread boundary or model mismatch")
                        thread_id = _identifier(started.get("thread", {}).get("id"))
                        turn_result = await session.request(
                            "turn/start",
                            {
                                "threadId": thread_id,
                                "model": model,
                                "effort": effort,
                                "input": [{"type": "text", "text": prompt}],
                                "outputSchema": schema,
                                "environments": [],
                                "runtimeWorkspaceRoots": [],
                                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                                "approvalPolicy": "on-request",
                                "serviceTierForTurn": "default",
                            },
                        )
                        turn_id = _identifier(turn_result.get("turn", {}).get("id"))
                        for item in turn_result.get("turn", {}).get("items", []):
                            _check_item(item)
                        raw, usage = await _finish(session, thread_id, turn_id)
                        return validate_fixture_draft(raw, request, usage=usage)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise AppServerError("Codex fixture request failed; no proposal was applied") from exc
