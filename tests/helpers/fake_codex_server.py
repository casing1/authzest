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
    if case == "bad-final-source":
        changed = json.loads(raw)
        changed["after_text"] += "# unrelated change\n"
        raw = json.dumps(changed)
    if case == "non-string-final":
        raw = 42
    if case != "missing-final":
        notify("item/completed", **params, item=item(raw))
    if case in {"ambiguous-final", "repeated-final"}:
        identity = "final-two" if case == "ambiguous-final" else "final-one"
        notify("item/completed", **params, item=item(raw, identity))
    if case != "missing-usage":
        usage = {"inputTokens": 123, "outputTokens": 45}
        if case == "negative-usage":
            usage["inputTokens"] = -1
        if case == "boolean-usage":
            usage["outputTokens"] = True
        if case == "null-usage":
            usage["inputTokens"] = None
        notify("thread/tokenUsage/updated", **params, tokenUsage={"last": usage})
    turn = {
        "id": "turn-fixture",
        "items": [{"type": "reasoning", "id": "reasoning-one"}],
        "status": "completed",
        "error": None,
    }
    if case == "completed-turn-id":
        turn["id"] = "different-turn"
    if case == "failed-turn":
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
            result = {
                "model": SETTINGS["model"],
                "modelProvider": "openai",
                "approvalPolicy": "on-request",
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
