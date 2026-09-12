"""Offline JSONL test child; copied into a private executable by transport tests."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SETTINGS = {}


def record(event, **values):
    with Path(SETTINGS["log"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": event, **values}) + "\n")


def send(value):
    sys.stdout.write(json.dumps(value) + "\n")
    sys.stdout.flush()


def notify(method, **params):
    send({"method": method, "params": params})


def item(text, identity="final-one", **changes):
    value = {"type": "agentMessage", "id": identity, "phase": "final_answer", "text": text}
    value.update(changes)
    return value


def capability_request():
    send({"id": "server-tool", "method": "item/permissions/requestApproval", "params": {}})
    incoming = sys.stdin.readline()
    if incoming:
        record("denial", message=json.loads(incoming))
    time.sleep(3600)


def metadata_notification(case, stage):
    if not case.startswith("metadata:"):
        return
    _, method, selected_stage, mutation = case.split(":")
    if stage != selected_stage:
        return
    identities = {"threadId": "thread-fixture", "turnId": "turn-fixture"}
    payloads = {
        "account/rateLimits/updated": {"rateLimits": {"planType": "plus", "primary": None}},
        "model/verification": {**identities, "verifications": ["trustedAccessForCyber"]},
        "model/safetyBuffering/updated": {
            **identities,
            "model": SETTINGS["model"],
            "fasterModel": None,
            "reasons": [],
            "showBufferingUi": False,
            "useCases": [],
        },
        "turn/moderationMetadata": {
            **identities,
            "metadata": {"input_tokens": 999999, "output_tokens": 999999, "approved": True},
        },
    }
    payload = payloads[method]
    if mutation == "wrong-thread":
        payload["threadId"] = "another-thread"
    if mutation == "wrong-turn":
        payload["turnId"] = "another-turn"
    if mutation == "missing-thread":
        del payload["threadId"]
    if mutation == "missing-turn":
        del payload["turnId"]
    notify(method, **payload)


def warning_notification(case, stage):
    if case.startswith("unrecognized-warning:"):
        _, method, selected_stage = case.split(":")
        if selected_stage == stage:
            notify(method, message="FAKE_SECRET_WARNING", threadId="thread-fixture")


def generic_warning(case, stage):
    if not case.startswith("warning:"):
        return
    _, selected_stage, mutation = case.split(":")
    if selected_stage != stage:
        return
    params = {
        "message": (
            'FAKE_SECRET_WARNING: {"usage": {"input_tokens": 999999}, '
            '"model": "not-the-negotiated-model", "approved": true}'
        ),
        "threadId": "thread-fixture",
    }
    if mutation == "unscoped":
        del params["threadId"]
    if mutation == "null-thread":
        params["threadId"] = None
    if mutation == "wrong-thread":
        params["threadId"] = "another-thread"
    if mutation == "non-string-thread":
        params["threadId"] = 42
    if mutation == "missing-message":
        del params["message"]
    if mutation == "empty-message":
        params["message"] = ""
    if mutation == "non-string-message":
        params["message"] = 42
    if mutation == "null-message":
        params["message"] = None
    if mutation == "maximum-message":
        params["message"] = "a" * 4096
    if mutation == "overlong-message":
        params["message"] = "a" * 4097
    if mutation == "extra-properties":
        params["usage"] = {"input_tokens": 999999}
    if mutation == "non-object":
        send({"method": "warning", "params": []})
        return
    notify("warning", **params)


def disconnected_stream_error(case, stage):
    if case != f"stream-disconnected:{stage}":
        return
    # Schema-valid representative of the observed event type and retry flag, not a raw capture.
    event = {
        "method": "error",
        "params": {
            "threadId": "thread-fixture",
            "turnId": "turn-fixture",
            "willRetry": True,
            "error": {
                "message": "Stream disconnected before completion",
                "codexErrorInfo": {"responseStreamDisconnected": {"httpStatusCode": None}},
                "additionalDetails": "FAKE_SECRET_ERROR_DETAIL",
            },
        },
    }
    record("injected-error", message=event)
    send(event)


def retry_notice(scenario):
    params = {
        "threadId": "thread-fixture",
        "turnId": "turn-fixture",
        "willRetry": True,
        "error": {
            "message": "Stream disconnected before completion",
            "codexErrorInfo": {"responseStreamDisconnected": {"httpStatusCode": None}},
            "additionalDetails": None,
            "misalignment": None,
        },
    }
    error = params["error"]
    info = error["codexErrorInfo"]
    if scenario == "connection-failed":
        error["codexErrorInfo"] = {"responseStreamConnectionFailed": {"httpStatusCode": 503}}
    if scenario == "missing-http-status":
        info["responseStreamDisconnected"] = {}
    if scenario == "fatal-flag":
        params["willRetry"] = False
    if scenario == "string-flag":
        params["willRetry"] = "true"
    if scenario == "integer-flag":
        params["willRetry"] = 1
    if scenario == "wrong-thread":
        params["threadId"] = "different-thread"
    if scenario == "wrong-turn":
        params["turnId"] = "different-turn"
    if scenario == "other-error":
        error["codexErrorInfo"] = "serverOverloaded"
    if scenario == "extra-error-field":
        error["approved"] = True
    if scenario == "extra-info-variant":
        info["responseStreamConnectionFailed"] = {}
    if scenario == "misalignment":
        error["misalignment"] = {"message": "not transport retry metadata"}
    if scenario in {
        "boolean-http",
        "negative-http",
        "overlong-http",
        "unauthorized-http",
        "rate-limit-http",
    }:
        info["responseStreamDisconnected"]["httpStatusCode"] = {
            "boolean-http": True,
            "negative-http": -1,
            "overlong-http": 65536,
            "unauthorized-http": 401,
            "rate-limit-http": 429,
        }[scenario]
    if scenario == "non-string-message":
        error["message"] = 12
    if scenario == "long-message":
        error["message"] = "m" * 4097
    if scenario == "long-details":
        error["additionalDetails"] = "d" * 4097
    if scenario == "extra-params":
        params["approved"] = True
    record("retry-notice", params=params)
    notify("error", **params)


def retry_flow(case):
    if not case.startswith("retry:"):
        return
    scenario = case.split(":", 1)[1]
    params = {"threadId": "thread-fixture", "turnId": "turn-fixture"}
    if scenario in {"partial-reset", "no-refreshed-usage", "no-fresh-final", "old-final-replay"}:
        notify("item/completed", **params, item=item(SETTINGS["raw"]))
        notify(
            "thread/tokenUsage/updated",
            **params,
            tokenUsage={"last": {"inputTokens": 9999, "outputTokens": 8888}},
        )
    for _ in range({"three-notices": 3, "four-notices": 4}.get(scenario, 1)):
        retry_notice(scenario)
    if scenario == "eof":
        raise SystemExit(0)
    if scenario == "timeout":
        time.sleep(3600)
    if scenario == "tool-request":
        capability_request()


def settings_notification(case, stage):
    if not case.startswith("settings:"):
        return
    _, selected_stage, mutation = case.split(":")
    if selected_stage != stage:
        return
    settings = {
        "model": SETTINGS["model"],
        "modelProvider": "openai",
        "cwd": os.getcwd(),
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
        "effort": None if mutation == "null-effort" else "low",
        "collaborationMode": {"mode": "default", "settings": {"model": SETTINGS["model"]}},
    }
    params = {"threadId": "thread-fixture", "threadSettings": settings}
    replacements = {
        "wrong-model": ("model", "different-model"),
        "wrong-provider": ("modelProvider", "other-provider"),
        "wrong-cwd": ("cwd", str(Path(os.getcwd()).parent)),
        "wrong-policy": ("approvalPolicy", "never"),
        "wrong-reviewer": ("approvalsReviewer", "guardian_subagent"),
        "wrong-sandbox": ("sandboxPolicy", {"type": "dangerFullAccess"}),
        "enabled-network": ("sandboxPolicy", {"type": "readOnly", "networkAccess": True}),
        "wrong-effort": ("effort", "high"),
    }
    if mutation in replacements:
        key, value = replacements[mutation]
        settings[key] = value
    if mutation == "wrong-thread":
        params["threadId"] = "different-thread"
    if mutation == "missing-settings":
        del params["threadSettings"]
    if mutation == "null-settings":
        params["threadSettings"] = None
    if mutation == "missing-sandbox":
        del settings["sandboxPolicy"]
    if mutation == "missing-model":
        del settings["model"]
    if mutation == "same-collaboration":
        settings["collaborationMode"]["settings"].update(
            reasoning_effort="low",
            developer_instructions=SETTINGS["config"]["developer_instructions"],
        )
    if mutation == "wrong-collaboration-mode":
        settings["collaborationMode"]["mode"] = "plan"
    if mutation == "wrong-collaboration-model":
        settings["collaborationMode"]["settings"]["model"] = "different-model"
    if mutation == "wrong-collaboration-effort":
        settings["collaborationMode"]["settings"]["reasoning_effort"] = "high"
    if mutation == "extra-collaboration-instructions":
        settings["collaborationMode"]["settings"]["developer_instructions"] = (
            "FAKE_SECRET_UNREVIEWED_INSTRUCTIONS"
        )
    if mutation == "missing-collaboration-mode":
        del settings["collaborationMode"]
    if mutation == "missing-collaboration-settings":
        del settings["collaborationMode"]["settings"]
    notify("thread/settings/updated", **params)


def finish(case):
    params = {"threadId": "thread-fixture", "turnId": "turn-fixture"}
    if case in {"hang", "descendant", "infinite-output"}:
        if case == "descendant":
            child = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(3600)"])
            record("descendant", pid=child.pid)
        if case == "infinite-output":
            while True:
                notify("item/reasoning/textDelta", **params, delta="still working")
                time.sleep(0.01)
        time.sleep(3600)
    if case == "tool-request":
        capability_request()
    if case == "unexpected-event":
        notify("item/fileChange/outputDelta", **params, delta="not allowed")
    if case == "unexpected-response":
        send({"id": 999, "result": {}})
    if case == "wrong-thread":
        params["threadId"] = "different-thread"
    if case == "wrong-turn":
        params["turnId"] = "different-turn"
    notify("turn/started", **params, turn={"id": "turn-fixture", "items": []})
    if case == "retry:missing-start-turn-id":
        notify(
            "item/started",
            threadId="thread-fixture",
            item={"type": "reasoning", "id": "unscoped-item"},
        )
    retry_flow(case)
    settings_notification(case, "during-turn")
    generic_warning(case, "during-turn")
    disconnected_stream_error(case, "during-turn")
    metadata_notification(case, "during-turn")
    warning_notification(case, "during-turn")
    if case == "metadata-only":
        metadata_notification("metadata:model/verification:during-turn:valid", "during-turn")
        metadata_notification("metadata:turn/moderationMetadata:during-turn:valid", "during-turn")
    if case == "warning-only":
        generic_warning("warning:during-turn:scoped", "during-turn")
    if case == "tool-item":
        notify("item/started", **params, item={"type": "commandExecution", "id": "command"})
    if case == "memory-item":
        notify("item/started", **params, item=item("draft", memoryCitation={"source": "other"}))
    if case == "interaction-item":
        notify("item/started", **params, item=item("draft", questions=["answer this"]))
    if case in {"stream-bytes", "stream-events"}:
        for _ in range(500):
            notify("item/reasoning/textDelta", **params, delta="x" * 8192)
    notify("item/started", **params, item={"type": "reasoning", "id": "reasoning-one"})
    notify("item/reasoning/summaryPartAdded", **params, itemId="reasoning-one", summaryIndex=0)
    notify("item/reasoning/summaryTextDelta", **params, itemId="reasoning-one", delta="review")
    notify("item/reasoning/textDelta", **params, itemId="reasoning-one", delta="bounded")
    notify("item/completed", **params, item={"type": "reasoning", "id": "reasoning-one"})
    notify("item/agentMessage/delta", **params, itemId="final-one", delta="{")
    raw = SETTINGS["raw"]
    if case == "bad-final-json":
        raw = "not JSON"
    if case in {"bad-final-source", "retry:bad-final-source"}:
        changed = json.loads(raw)
        changed["after_text"] += "# unrelated change\n"
        raw = json.dumps(changed)
    if case == "non-string-final":
        raw = 42
    if case not in {"missing-final", "metadata-only", "warning-only", "retry:no-fresh-final"}:
        final_id = (
            "final-after-retry"
            if case in {"retry:partial-reset", "retry:no-refreshed-usage"}
            else "final-one"
        )
        final_params = (
            {"threadId": "thread-fixture"} if case == "retry:missing-final-turn-id" else params
        )
        notify("item/completed", **final_params, item=item(raw, final_id))
    if case in {"ambiguous-final", "repeated-final"}:
        identity = "final-two" if case == "ambiguous-final" else "final-one"
        notify("item/completed", **params, item=item(raw, identity))
    if case not in {"missing-usage", "retry:no-refreshed-usage"}:
        usage = {"inputTokens": 123, "outputTokens": 45}
        if case == "negative-usage":
            usage["inputTokens"] = -1
        if case == "boolean-usage":
            usage["outputTokens"] = True
        if case == "null-usage":
            usage["inputTokens"] = None
        usage_params = (
            {"threadId": "thread-fixture"} if case == "retry:missing-usage-turn-id" else params
        )
        notify("thread/tokenUsage/updated", **usage_params, tokenUsage={"last": usage})
    turn = {
        "id": "turn-fixture",
        "items": [{"type": "reasoning", "id": "reasoning-one"}],
        "status": "completed",
        "error": None,
    }
    if case == "completed-turn-id":
        turn["id"] = "different-turn"
    if case in {"failed-turn", "retry:failed-turn"}:
        turn["status"] = "failed"
        turn["error"] = {"message": "FAKE_SECRET_RESPONSE"}
    if case == "interrupted-turn":
        turn["status"] = "interrupted"
    if case == "final-tool-item":
        turn["items"] = [{"type": "fileChange", "id": "write"}]
    notify("turn/completed", **params, turn=turn)


def main():
    case = SETTINGS["case"]
    previous = []
    if Path(SETTINGS["log"]).exists():
        previous = [json.loads(line) for line in Path(SETTINGS["log"]).read_text().splitlines()]
    generation = 1 + sum(event["event"] == "start" for event in previous)
    record(
        "start",
        pid=os.getpid(),
        generation=generation,
        cwd=os.getcwd(),
        arguments=sys.argv[1:],
        environment_keys=sorted(os.environ),
    )
    for line in sys.stdin:
        message = json.loads(line)
        record("request", message=message, generation=generation)
        if "id" not in message:
            continue
        method = message.get("method")
        result = {}
        if method == "initialize":
            if case == "warning-per-session":
                notify("warning", message="Unscoped informational startup warning")
            if case == "warning-burst":
                for _ in range(130):
                    notify("warning", message="Informational quota-independent warning")
            if case == "quota-burst":
                for _ in range(130):
                    notify("account/rateLimits/updated", rateLimits={})
            if case == "missing-notification-method":
                send({"notice": "not a notification"})
            if case == "malformed":
                sys.stdout.write("not JSON\n")
                sys.stdout.flush()
                continue
            if case == "duplicate-json-key":
                sys.stdout.write('{"id": 1, "id": 1, "result": {}}\n')
                sys.stdout.flush()
                continue
            if case == "invalid-unicode":
                sys.stdout.buffer.write(b"\xff\n")
                sys.stdout.buffer.flush()
                continue
            if case == "partial-eof":
                sys.stdout.write('{"id":')
                sys.stdout.flush()
                return
            if case == "oversized":
                sys.stdout.write("x" * 300000 + "\n")
                sys.stdout.flush()
                continue
            if case == "pending-overflow":
                for _ in range(130):
                    notify("thread/status/changed", threadId="thread-fixture", status={})
            if case == "early-event":
                notify("item/fileChange/outputDelta", threadId="thread-fixture", delta="no")
            if case == "early-tool-request":
                capability_request()
            version = "0.1.0" if case == "wrong-version" else "0.153.0"
            result = {"userAgent": "authzest/" + version}
        elif method == "config/read":
            config = json.loads(json.dumps(SETTINGS["config"]))
            config["mcp_servers"] = {"inherited-server": {"enabled": True}}
            for argument in sys.argv:
                prefix = "mcp_servers."
                suffix = ".enabled=false"
                if argument.startswith(prefix) and argument.endswith(suffix):
                    name = argument[len(prefix) : -len(suffix)]
                    config["mcp_servers"][name] = {"enabled": False}
            if case == "bad-config":
                config["web_search"] = "live"
            if case == "unstable-warning-enabled":
                config["suppress_unstable_features_warning"] = False
            if case == "unstable-warning-string":
                config["suppress_unstable_features_warning"] = "true"
            if case == "unstable-warning-missing":
                del config["suppress_unstable_features_warning"]
            if case == "external-context":
                config["model_instructions_file"] = "/not-to-be-read/private.md"
            if case == "invalid-mcp-name":
                config["mcp_servers"] = {"not.safe": {"enabled": True}}
            if case == "too-many-mcp-servers":
                config["mcp_servers"] = {f"server-{index}": {} for index in range(65)}
            if case == "mcp-still-enabled":
                config["mcp_servers"]["inherited-server"]["enabled"] = True
            if case == "new-mcp-second-pass" and generation == 2:
                config["mcp_servers"]["new-server"] = {"enabled": True}
            result = {"config": config}
            if case == "missing-config":
                result = {"config": None}
        elif method == "account/read":
            account = {"type": "chatgpt", "email": "FAKE_SECRET_PROFILE@example.invalid"}
            if case == "api-key-auth":
                account["type"] = "apiKey"
            if case == "missing-auth":
                account = None
            if case == "malformed-auth":
                account = ["not an account object"]
            result = {"account": account}
        elif method == "remoteControl/status/read":
            result = {
                "status": "enabled"
                if case in {"remote-enabled", "remote-result-enabled"}
                else "disabled"
            }
            notify(
                "remoteControl/status/changed",
                status="disabled" if case == "remote-result-enabled" else result["status"],
            )
        elif method == "model/list":
            model = {"model": SETTINGS["model"], "defaultReasoningEffort": "low"}
            if case == "unsupported-effort":
                model["defaultReasoningEffort"] = "ultra"
            result = {"data": [model], "nextCursor": None}
            if case == "missing-model":
                result["data"] = []
            if case == "duplicate-model":
                result["data"] *= 2
        elif method == "thread/start":
            if case == "retry:before-turn-dispatch":
                retry_notice("normal")
            warning_notification(case, "before-response")
            generic_warning(case, "before-thread-response")
            settings_notification(case, "before-thread-response")
            result = {
                "model": SETTINGS["model"],
                "modelProvider": "openai",
                "approvalPolicy": "on-request",
                "approvalsReviewer": "user",
                "sandbox": {"type": "readOnly"},
                "cwd": os.getcwd(),
                "instructionSources": [],
                "runtimeWorkspaceRoots": [],
                "thread": {"id": "thread-fixture"},
            }
            modifications = {
                "thread-model": {"model": "different-model"},
                "thread-provider": {"modelProvider": "elsewhere"},
                "thread-approval": {"approvalPolicy": "never"},
                "thread-sandbox": {"sandbox": {"type": "dangerFullAccess"}},
                "thread-network": {"sandbox": {"type": "readOnly", "networkAccess": True}},
                "thread-cwd": {"cwd": str(Path(os.getcwd()).parent)},
                "thread-instructions": {"instructionSources": ["unreviewed.md"]},
                "thread-roots": {"runtimeWorkspaceRoots": ["/unreviewed"]},
                "thread-id": {"thread": {"id": "bad/id"}},
                "thread-history": {
                    "thread": {"id": "thread-fixture", "turns": [{"id": "old-turn"}]}
                },
            }
            result.update(modifications.get(case, {}))
            notification = {"id": "thread-fixture"}
            if case == "thread-notification-history":
                notification["turns"] = [{"id": "old-turn"}]
            if case == "thread-notification-id":
                notification["id"] = "different-thread"
            notify("thread/started", thread=notification)
        elif method == "turn/start":
            if case == "retry:queued-terminal-before-error":
                scoped = {"threadId": "thread-fixture", "turnId": "turn-fixture"}
                notify("item/completed", **scoped, item=item(SETTINGS["raw"]))
                notify(
                    "turn/completed",
                    **scoped,
                    turn={"id": "turn-fixture", "items": [], "status": "completed", "error": None},
                )
                retry_notice("normal")
            if case == "retry:wrong-turn-before-response":
                retry_notice("wrong-turn")
            metadata_notification(case, "before-response")
            generic_warning(case, "before-turn-response")
            disconnected_stream_error(case, "before-turn-response")
            settings_notification(case, "before-turn-response")
            result = {"turn": {"id": "turn-fixture", "items": []}}
            if case == "turn-result-tool":
                result["turn"]["items"] = [{"type": "commandExecution", "id": "command"}]
        else:
            record("unexpected-method", method=method)
            return
        response = {"id": message["id"], "result": result}
        if case == "wrong-rpc-id":
            response["id"] += 1
        if case == "boolean-rpc-id":
            response["id"] = True
        if case == "rpc-error":
            response = {"id": message["id"], "error": {"message": "FAKE_SECRET_RESPONSE"}}
        send(response)
        if method == "turn/start":
            finish(case)


if __name__ == "__main__":
    main()
