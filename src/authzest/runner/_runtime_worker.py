"""Fixed benign runtime probe; only identical bundled fixture constants may execute."""

from hashlib import sha256

CHECK_ID = "owned-fixture-runtime-debug-health-v1"
MAX_INPUT_BYTES = 1024

# -I source workers use trusted installed dependencies and their interpreter startup.
# Frozen workers use the same fixed program and bundled dependencies. Neither mode
# is an OS/network sandbox, and asyncio can use internal socketpair/thread IPC.
WORKER_SOURCE = r'''
import asyncio
import hashlib
import json
import re
import sys

CHECK_ID = "owned-fixture-runtime-debug-health-v1"
BEFORE = (
    '"""Owned source-only configuration fixture; never imported by the demo."""\n'
    "\n"
    "from fastapi import FastAPI\n"
    "\n"
    "app = FastAPI(debug=True)\n"
    "\n"
    "\n"
    '@app.get("/health")\n'
    "def health():\n"
    '    return {"status": "ok"}\n'
)
AFTER = BEFORE.replace("debug=True", "debug=False", 1)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate health response field")
        result[key] = value
    return result


async def _probe(app):
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/health", "raw_path": b"/health", "query_string": b"",
        "root_path": "", "headers": [], "client": None, "server": None,
    }
    request_sent = False
    started = False
    finished = False
    status = None
    body = bytearray()
    events = 0

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        # No synthetic early disconnect, network listener, or HTTP client.
        await asyncio.Event().wait()

    async def send(message):
        nonlocal started, finished, status, events
        events += 1
        if events > 8 or type(message) is not dict or finished:
            raise ValueError("Unexpected ASGI event")
        kind = message.get("type")
        if kind == "http.response.start":
            if started or type(message.get("status")) is not int:
                raise ValueError("Unexpected ASGI start")
            started = True
            status = message["status"]
        elif kind == "http.response.body":
            chunk = message.get("body", b"")
            more = message.get("more_body", False)
            if not started or type(chunk) is not bytes or type(more) is not bool:
                raise ValueError("Unexpected ASGI body")
            if len(body) + len(chunk) > 1024:
                raise ValueError("ASGI body limit")
            body.extend(chunk)
            finished = not more
        else:
            raise ValueError("Unexpected ASGI message")

    await app(scope, receive, send)
    if not started or not finished or status != 200:
        raise ValueError("Incomplete or failed health response")
    parsed = json.loads(body.decode("utf-8"), object_pairs_hook=_object)
    if type(parsed) is not dict or parsed != {"status": "ok"}:
        raise ValueError("Unexpected health response")
    return status, parsed


def _emit(digest, status, reason, evidence):
    payload = {
        "schema_version": "1.0", "check_id": CHECK_ID,
        "source_sha256": digest, "status": status, "reason": reason,
        "runtime_evidence": evidence,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


def _main():
    try:
        source = sys.stdin.buffer.read(1025)
        # Choose trusted, bundled text only after exact byte equality. Never
        # compile the incoming object or import a caller-selected source path.
        if source == BEFORE.encode("utf-8"):
            program = BEFORE
            expected_debug = True
        elif source == AFTER.encode("utf-8"):
            program = AFTER
            expected_debug = False
        else:
            return 2
        digest = hashlib.sha256(source).hexdigest()
        try:
            import fastapi
            import starlette
            import pydantic
        except ModuleNotFoundError:
            return _emit(digest, "not-run", "runtime-dependency-unavailable", None)
        namespace = {"__name__": "authzest_owned_runtime_fixture"}
        exec(compile(program, "<authzest-owned-runtime-fixture>", "exec"), namespace)
        app = namespace.get("app")
        if not isinstance(app, fastapi.FastAPI) or type(app.debug) is not bool:
            return 2
        if app.debug is not expected_debug:
            return 2
        health_status, health_body = asyncio.run(_probe(app))
        versions = {
            "python": ".".join(map(str, sys.version_info[:3])),
            "fastapi": fastapi.__version__, "starlette": starlette.__version__,
            "pydantic": pydantic.__version__,
        }
        if any(
            type(value) is not str or re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]{0,79}", value) is None
            for value in versions.values()
        ):
            return 2
        evidence = {
            "debug": app.debug, "health_status": health_status,
            "health_body": health_body, "dependency_versions": versions,
        }
        return _emit(
            digest, "failed" if app.debug else "passed",
            "debug-enabled" if app.debug else "runtime-check-passed", evidence,
        )
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
'''.lstrip()

WORKER_SHA256 = sha256(WORKER_SOURCE.encode("utf-8")).hexdigest()


def worker_main() -> int:
    """Run the same fixed probe; incoming bytes select only identical bundled text."""
    namespace = {"__name__": "authzest_fixed_runtime_worker"}
    exec(compile(WORKER_SOURCE, "<authzest-fixed-runtime-worker>", "exec"), namespace)
    return namespace["_main"]()
