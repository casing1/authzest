import asyncio
import builtins
import hashlib
import io
import json
import os
import signal
import socket
import sys
from contextlib import suppress
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import _runtime_worker as worker
from authzest.runner import fixture_check
from authzest.runner import fixture_runtime as runtime

BEFORE = FIXTURE_SOURCE.encode()
AFTER = FIXTURE_AFTER.encode()
pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")


def evidence(source=AFTER):
    return {
        "debug": source == BEFORE,
        "health_status": 200,
        "health_body": {"status": "ok"},
        "dependency_versions": {
            "python": "3.12.7",
            "fastapi": "0.115.0",
            "starlette": "0.41.0",
            "pydantic": "2.10.0",
        },
    }


def payload(source=AFTER):
    return {
        "schema_version": "1.0",
        "check_id": runtime.CHECK_ID,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "status": "passed" if source == AFTER else "failed",
        "reason": "runtime-check-passed" if source == AFTER else "debug-enabled",
        "runtime_evidence": evidence(source),
    }


@pytest.fixture
def children(monkeypatch):
    original = asyncio.create_subprocess_exec
    created = []

    async def create(*args, **kwargs):
        process = await original(*args, **kwargs)
        created.append((process, args, kwargs))
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    yield created
    for process, _, _ in created:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)


def assert_stopped(children):
    for process, _, options in children:
        assert process.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
        assert not options["cwd"].exists()


@pytest.mark.parametrize(
    ("source", "status", "reason"),
    [(BEFORE, "failed", "debug-enabled"), (AFTER, "passed", "runtime-check-passed")],
)
def test_real_fixed_runtime_observes_debug_and_asgi_health(source, status, reason, children):
    outcome = asyncio.run(runtime.run_runtime_check(source))
    assert (outcome.status, outcome.reason, outcome.exit_code) == (status, reason, 0)
    assert runtime.validate_runtime_evidence(outcome.runtime_evidence, source)
    assert outcome.source_sha256 == hashlib.sha256(source).hexdigest()
    assert outcome.worker_sha256 == hashlib.sha256(worker.WORKER_SOURCE.encode()).hexdigest()
    assert outcome.check_id == worker.CHECK_ID
    assert 0 <= outcome.elapsed_ms < 5000
    assert len(children) == 1
    _, command, options = children[0]
    assert command == (sys.executable, "-I", "-c", worker.WORKER_SOURCE)
    assert options["start_new_session"] is True
    assert options["stderr"] == asyncio.subprocess.DEVNULL
    assert options["limit"] == 4097
    assert_stopped(children)
    with pytest.raises(FrozenInstanceError):
        outcome.status = "passed"


@pytest.mark.parametrize(
    "source", [b"", b"x", AFTER + b"\n", b"x" * 1025, None, "text", bytearray(AFTER)]
)
def test_unknown_source_never_starts_process(monkeypatch, source):
    async def forbidden(*args, **kwargs):
        pytest.fail("Unknown input must not start a worker")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    outcome = asyncio.run(runtime.run_runtime_check(source))
    assert (outcome.status, outcome.reason, outcome.exit_code, outcome.runtime_evidence) == (
        "not-run",
        "invalid-source",
        None,
        None,
    )


def worker_namespace():
    namespace = {"__name__": "trusted_runtime_test"}
    exec(compile(worker.WORKER_SOURCE, "<trusted-runtime-test>", "exec"), namespace)
    return namespace


def test_worker_constants_equal_contract_sources():
    namespace = worker_namespace()
    assert namespace["BEFORE"].encode() == BEFORE
    assert namespace["AFTER"].encode() == AFTER
    assert namespace["CHECK_ID"] == runtime.CHECK_ID


def test_unknown_input_rejected_before_dependency_import_or_compile(monkeypatch):
    namespace = worker_namespace()
    original = builtins.__import__

    def import_guard(name, *args, **kwargs):
        if name in {"fastapi", "starlette", "pydantic"}:
            pytest.fail("Unknown input must not import runtime dependencies")
        return original(name, *args, **kwargs)

    def compile_guard(*args, **kwargs):
        pytest.fail("Unknown input must not compile any fixture")

    monkeypatch.setattr(builtins, "__import__", import_guard)
    monkeypatch.setitem(namespace, "compile", compile_guard)
    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(b"raise RuntimeError('unknown')"))
    )
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdout", outgoing)
    assert namespace["_main"]() == 2
    assert outgoing.getvalue() == ""


@pytest.mark.parametrize("source", [BEFORE, AFTER])
def test_worker_executes_only_selected_bundled_constant_without_network(monkeypatch, source):
    namespace = worker_namespace()
    compiled = []
    original_compile = builtins.compile

    def compile_guard(program, *args, **kwargs):
        assert program is namespace["AFTER" if source == AFTER else "BEFORE"]
        compiled.append(program)
        return original_compile(program, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("The fixed probe must not use TCP/UDP networking")

    monkeypatch.setitem(namespace, "compile", compile_guard)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "bind", forbidden)
    monkeypatch.setattr(socket.socket, "listen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(source)))
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdout", outgoing)
    assert namespace["_main"]() == 0
    assert len(compiled) == 1
    result = json.loads(outgoing.getvalue())
    assert runtime.validate_runtime_evidence(result["runtime_evidence"], source)


def test_frozen_handler_uses_same_fixed_program(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(AFTER)))
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdout", outgoing)
    assert worker.worker_main() == 0
    assert runtime._validated_output(outgoing.getvalue().encode(), AFTER)[:2] == (
        "passed",
        "runtime-check-passed",
    )


def test_frozen_command_uses_hidden_same_executable_entry(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/trusted/authzest")
    assert runtime._command() == ["/trusted/authzest", "_runtime-worker"]
    assert runtime.TIMEOUT_SECONDS == 5
    assert runtime.MAX_CLEANUP_SECONDS == 1
    assert runtime.MAX_INPUT_BYTES == 1024
    assert runtime.MAX_OUTPUT_BYTES == 4096


def test_runtime_reuses_reduced_environment_and_clean_cwd(monkeypatch, children):
    for key in (
        "HOME",
        "CODEX_HOME",
        "OPENAI_API_KEY",
        "HTTPS_PROXY",
        "PYTHONPATH",
        "_PYI_ARCHIVE_FILE",
    ):
        monkeypatch.setenv(key, "private-dummy-sentinel")
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert outcome.status == "passed"
    environment = children[0][2]["env"]
    assert "private-dummy-sentinel" not in environment.values()
    assert environment == fixture_check._environment(children[0][2]["cwd"])
    assert_stopped(children)


def helper(monkeypatch, code):
    monkeypatch.setattr(runtime, "_command", lambda: [sys.executable, "-I", "-S", "-c", code])


def test_missing_optional_dependency_is_honest_not_run_without_install(monkeypatch, children):
    # The same trusted worker without site-packages deterministically lacks FastAPI.
    helper(monkeypatch, worker.WORKER_SOURCE)
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert (outcome.status, outcome.reason, outcome.exit_code, outcome.runtime_evidence) == (
        "not-run",
        "runtime-dependency-unavailable",
        0,
        None,
    )
    assert len(children) == 1
    assert_stopped(children)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(extra=True),
        lambda d: d.update(debug=0),
        lambda d: d.update(debug=True),
        lambda d: d.update(health_status=True),
        lambda d: d.update(health_status=200.0),
        lambda d: d.update(health_status=500),
        lambda d: d.update(health_body={"status": "ok", "extra": True}),
        lambda d: d.update(health_body={"status": "wrong"}),
        lambda d: d.update(dependency_versions={}),
        lambda d: d["dependency_versions"].update(extra="1.0"),
        lambda d: d["dependency_versions"].update(fastapi=None),
        lambda d: d["dependency_versions"].update(fastapi="1\nprivate-dummy"),
        lambda d: d["dependency_versions"].update(fastapi="1" * 81),
        lambda d: d["dependency_versions"].update(fastapi="é1"),
    ],
)
def test_evidence_is_exact_typed_bounded_and_fail_closed(mutation):
    value = evidence()
    mutation(value)
    assert not runtime.validate_runtime_evidence(value, AFTER)
    assert not runtime.validate_runtime_evidence(evidence(), b"unknown")
    assert not runtime.validate_runtime_evidence(None, AFTER)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[]",
        b"null",
        b"NaN",
        b"not-json",
        b"\xff",
        b"{}",
        json.dumps({**payload(), "extra": True}).encode(),
        json.dumps({**payload(), "check_id": "arbitrary-runtime"}).encode(),
        json.dumps({**payload(), "source_sha256": "0" * 64}).encode(),
        json.dumps({**payload(), "schema_version": "2.0"}).encode(),
        json.dumps({**payload(), "reason": "verified-security-fix"}).encode(),
        json.dumps({**payload(), "runtime_evidence": None}).encode(),
        json.dumps(payload()).encode() + b"{}",
        (json.dumps(payload())[:-1] + ', "status":"passed"}').encode(),
        json.dumps(payload()).replace('"debug": false', '"debug": true, "debug": false').encode(),
    ],
)
def test_corrupt_output_never_passes(monkeypatch, raw, children):
    helper(monkeypatch, f"import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write({raw!r})")
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert (outcome.status, outcome.reason, outcome.runtime_evidence) == (
        "failed",
        "invalid-worker-output",
        None,
    )
    assert_stopped(children)


def test_before_cannot_claim_pass(monkeypatch, children):
    forged = {**payload(BEFORE), "status": "passed", "reason": "runtime-check-passed"}
    helper(monkeypatch, f"import sys; sys.stdin.buffer.read(); print({json.dumps(forged)!r})")
    outcome = asyncio.run(runtime.run_runtime_check(BEFORE))
    assert (outcome.status, outcome.reason) == ("failed", "invalid-worker-output")
    assert_stopped(children)


def test_nonzero_exit_cannot_pass(monkeypatch, children):
    helper(
        monkeypatch,
        f"import sys; sys.stdin.buffer.read(); print({json.dumps(payload())!r}); sys.exit(7)",
    )
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert (outcome.status, outcome.reason, outcome.exit_code, outcome.runtime_evidence) == (
        "failed",
        "worker-exit-error",
        7,
        None,
    )
    assert_stopped(children)


def test_output_limit_stops_process(monkeypatch, children):
    helper(
        monkeypatch,
        "import sys,time; sys.stdin.buffer.read(); print('x'*5000,flush=True); time.sleep(30)",
    )
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert (outcome.status, outcome.reason) == ("failed", "output-limit")
    assert_stopped(children)


def test_timeout_kills_and_reaps_process(monkeypatch, children):
    monkeypatch.setattr(runtime, "TIMEOUT_SECONDS", 0.2)
    helper(monkeypatch, "import sys,time; sys.stdin.buffer.read(); time.sleep(30)")
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert (outcome.status, outcome.reason, outcome.exit_code) == (
        "failed",
        "timeout",
        -signal.SIGKILL,
    )
    assert_stopped(children)


def test_cancellation_cleans_process_and_propagates(monkeypatch, children):
    helper(monkeypatch, "import sys,time; sys.stdin.buffer.read(); time.sleep(30)")

    async def scenario():
        task = asyncio.create_task(runtime.run_runtime_check(AFTER))
        async with asyncio.timeout(2):
            while not children:
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert_stopped(children)


def test_spawn_error_does_not_expose_details(monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError("private-dummy-sentinel")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert (outcome.status, outcome.reason) == ("failed", "worker-process-error")
    assert "private-dummy-sentinel" not in repr(outcome)


def test_stderr_is_discarded_without_blocking(monkeypatch, children):
    helper(
        monkeypatch,
        "import sys; sys.stdin.buffer.read(); sys.stderr.write('private-dummy'*10000); "
        f"print({json.dumps(payload())!r})",
    )
    outcome = asyncio.run(runtime.run_runtime_check(AFTER))
    assert outcome.status == "passed"
    assert "private-dummy" not in repr(outcome)
    assert_stopped(children)


@pytest.mark.parametrize(
    "case",
    [
        "no-start",
        "duplicate-start",
        "incomplete",
        "overflow",
        "duplicate-json",
        "status",
        "extra-event",
    ],
)
def test_asgi_probe_rejects_incomplete_or_corrupt_exchange(case):
    namespace = worker_namespace()

    async def bad_app(scope, receive, send):
        start = {"type": "http.response.start", "status": 200}
        body = {"type": "http.response.body", "body": b'{"status":"ok"}'}
        if case == "no-start":
            await send(body)
            return
        await send({**start, "status": 500} if case == "status" else start)
        if case == "duplicate-start":
            await send(start)
        elif case == "incomplete":
            await send({**body, "more_body": True})
        elif case == "overflow":
            await send({**body, "body": b"x" * 1025})
        elif case == "duplicate-json":
            await send({**body, "body": b'{"status":"wrong","status":"ok"}'})
        else:
            await send(body)
            if case == "extra-event":
                await send(body)

    with pytest.raises(ValueError):
        asyncio.run(namespace["_probe"](bad_app))


def test_failed_probe_has_no_valid_result(monkeypatch):
    namespace = worker_namespace()

    async def fail(app):
        raise RuntimeError("private-dummy-probe-error")

    monkeypatch.setitem(namespace, "_probe", fail)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(AFTER)))
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdout", outgoing)
    assert namespace["_main"]() == 2
    assert outgoing.getvalue() == ""
