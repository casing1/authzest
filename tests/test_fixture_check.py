import asyncio
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
from contextlib import suppress
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import _configuration_worker as worker
from authzest.runner import fixture_check as check

BEFORE = FIXTURE_SOURCE.encode()
AFTER = FIXTURE_AFTER.encode()
pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")


def payload(source=AFTER):
    return {
        "schema_version": "1.0",
        "check_id": check.CHECK_ID,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "status": "passed" if source == AFTER else "failed",
        "reason": "debug-disabled" if source == AFTER else "debug-enabled",
    }


@pytest.fixture
def children(monkeypatch):
    """Track only this test's own subprocesses, with cleanup even on assertions."""
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
    [(BEFORE, "failed", "debug-enabled"), (AFTER, "passed", "debug-disabled")],
)
def test_real_fixed_worker_reads_only_exact_source(source, status, reason, children):
    outcome = asyncio.run(check.run_configuration_check(source))
    assert (outcome.status, outcome.reason, outcome.exit_code) == (status, reason, 0)
    assert outcome.check_id == worker.CHECK_ID
    assert outcome.source_sha256 == hashlib.sha256(source).hexdigest()
    assert outcome.worker_sha256 == hashlib.sha256(worker.WORKER_SOURCE.encode()).hexdigest()
    assert 0 <= outcome.elapsed_ms < 5000
    assert len(children) == 1
    _, args, options = children[0]
    assert args == (sys.executable, "-I", "-S", "-c", worker.WORKER_SOURCE)
    assert options["start_new_session"] is True
    assert options["stderr"] == asyncio.subprocess.DEVNULL
    assert options["limit"] == 4097
    assert_stopped(children)
    with pytest.raises(FrozenInstanceError):
        outcome.status = "passed"


@pytest.mark.parametrize(
    "source", [b"", b"x", AFTER + b"\n", b"x" * 1025, "text", None, bytearray(AFTER)]
)
def test_unknown_or_nonbytes_input_never_creates_process(monkeypatch, source):
    async def forbidden(*args, **kwargs):
        pytest.fail("Unknown input must not create a process")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    outcome = asyncio.run(check.run_configuration_check(source))
    assert (outcome.status, outcome.reason, outcome.exit_code) == (
        "not-run",
        "invalid-source",
        None,
    )


def test_no_ambient_credentials_or_python_settings_in_child(monkeypatch, tmp_path):
    for name in (
        "HOME",
        "CODEX_HOME",
        "OPENAI_API_KEY",
        "HTTPS_PROXY",
        "PYTHONPATH",
        "PYTHONSTARTUP",
    ):
        monkeypatch.setenv(name, "private-dummy-sentinel")
    environment = check._environment(tmp_path)
    assert not any(value == "private-dummy-sentinel" for value in environment.values())
    assert environment["TMPDIR"] == str(tmp_path)
    assert environment["PATH"] == "/usr/bin:/bin"
    assert set(environment) == {
        "PATH",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONUTF8",
        "NO_COLOR",
        "TERM",
    }


def test_frozen_command_is_hidden_entry_not_python_module(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/trusted/frozen/authzest")
    assert check._command() == ["/trusted/frozen/authzest", "_configuration-worker"]
    assert check.TIMEOUT_SECONDS == 5
    assert check.MAX_INPUT_BYTES == 1024
    assert check.MAX_OUTPUT_BYTES == 4096


@pytest.mark.parametrize("source", [BEFORE, AFTER])
def test_frozen_handler_uses_same_worker_source(monkeypatch, source):
    incoming = io.TextIOWrapper(io.BytesIO(source), encoding="utf-8")
    outgoing = io.StringIO()
    monkeypatch.setattr(sys, "stdin", incoming)
    monkeypatch.setattr(sys, "stdout", outgoing)
    assert worker.worker_main() == 0
    assert json.loads(outgoing.getvalue()) == payload(source)


def test_worker_rejects_unknown_bytes_without_executing_them(tmp_path):
    marker = tmp_path / "never-created"
    untrusted = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n".encode()
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", worker.WORKER_SOURCE],
        input=untrusted,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 2 and not result.stdout and not result.stderr
    assert not marker.exists()


def helper(monkeypatch, code):
    monkeypatch.setattr(check, "_command", lambda: [sys.executable, "-I", "-S", "-c", code])


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not-json",
        b"\xff",
        b"[]",
        b"null",
        b"{}",
        b"NaN",
        json.dumps({**payload(), "extra": True}).encode(),
        json.dumps({**payload(), "source_sha256": "0" * 64}).encode(),
        json.dumps({**payload(), "check_id": "arbitrary-command"}).encode(),
        json.dumps({**payload(), "status": "failed"}).encode(),
        json.dumps({**payload(), "reason": "security-fixed"}).encode(),
        json.dumps({**payload(), "schema_version": "2.0"}).encode(),
        (json.dumps(payload())[:-1] + ', "status": "passed"}').encode(),
        json.dumps(payload()).encode() + b"{}",
    ],
)
def test_malformed_or_corrupted_child_output_never_passes(monkeypatch, raw, children):
    helper(monkeypatch, f"import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write({raw!r})")
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert (outcome.status, outcome.reason) == ("failed", "invalid-worker-output")
    assert_stopped(children)


def test_forged_pass_for_before_source_is_rejected(monkeypatch, children):
    forged = {**payload(BEFORE), "status": "passed", "reason": "debug-disabled"}
    helper(monkeypatch, f"import sys; sys.stdin.buffer.read(); print({json.dumps(forged)!r})")
    outcome = asyncio.run(check.run_configuration_check(BEFORE))
    assert (outcome.status, outcome.reason) == ("failed", "invalid-worker-output")
    assert_stopped(children)


def test_nonzero_exit_cannot_claim_pass(monkeypatch, children):
    helper(
        monkeypatch,
        f"import sys; sys.stdin.buffer.read(); print({json.dumps(payload())!r}); sys.exit(7)",
    )
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert (outcome.status, outcome.reason, outcome.exit_code) == ("failed", "worker-exit-error", 7)
    assert_stopped(children)


def test_oversized_output_is_stopped_before_timeout(monkeypatch, children):
    helper(
        monkeypatch,
        "import sys,time; sys.stdin.buffer.read(); print('x' * 5000, flush=True); time.sleep(30)",
    )
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert (outcome.status, outcome.reason) == ("failed", "output-limit")
    assert_stopped(children)


def test_stderr_cannot_become_result_or_block_output(monkeypatch, children):
    helper(
        monkeypatch,
        "import sys; sys.stdin.buffer.read(); sys.stderr.write('private-dummy' * 10000); "
        f"print({json.dumps(payload())!r})",
    )
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert outcome.status == "passed"
    assert "private-dummy" not in repr(outcome)
    assert_stopped(children)


def test_timeout_kills_and_reaps_worker(monkeypatch, children):
    monkeypatch.setattr(check, "TIMEOUT_SECONDS", 0.2)
    helper(monkeypatch, "import sys,time; sys.stdin.buffer.read(); time.sleep(30)")
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert (outcome.status, outcome.reason) == ("failed", "timeout")
    assert outcome.exit_code == -signal.SIGKILL
    assert_stopped(children)


def test_cancellation_cleans_worker_and_propagates(monkeypatch, children):
    helper(monkeypatch, "import sys,time; sys.stdin.buffer.read(); time.sleep(30)")

    async def scenario():
        task = asyncio.create_task(check.run_configuration_check(AFTER))
        async with asyncio.timeout(2):
            while not children:
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert_stopped(children)


def test_spawn_error_is_redacted(monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError("private-dummy-location")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert (outcome.status, outcome.reason, outcome.exit_code) == (
        "failed",
        "worker-process-error",
        None,
    )
    assert "private-dummy" not in repr(outcome)


def test_successful_output_with_lingering_process_still_times_out(monkeypatch, children):
    monkeypatch.setattr(check, "TIMEOUT_SECONDS", 0.2)
    helper(
        monkeypatch,
        f"import sys,time; sys.stdin.buffer.read(); print({json.dumps(payload())!r}, flush=True); "
        "sys.stdout.close(); time.sleep(30)",
    )
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert (outcome.status, outcome.reason) == ("failed", "timeout")
    assert_stopped(children)


def test_worker_cwd_is_empty_and_not_the_fixture_path(monkeypatch, children):
    code = (
        "import os,sys; sys.stdin.buffer.read(); assert os.listdir('.') == []; "
        f"print({json.dumps(payload())!r})"
    )
    helper(monkeypatch, code)
    outcome = asyncio.run(check.run_configuration_check(AFTER))
    assert outcome.status == "passed"
    assert_stopped(children)


@pytest.mark.parametrize("mode", ["timeout", "cancel", "success"])
def test_owned_process_group_descendant_is_stopped(monkeypatch, children, tmp_path, mode):
    marker = tmp_path / "descendant-pid"
    code = (
        "import os,sys,time\n"
        "sys.stdin.buffer.read()\n"
        "child = os.fork()\n"
        "if child == 0:\n"
        "    os.close(1)\n"
        "    time.sleep(30)\n"
        "    os._exit(0)\n"
        f"with open({str(marker)!r}, 'w') as target: target.write(str(child))\n"
        + (f"print({json.dumps(payload())!r})\n" if mode == "success" else "time.sleep(30)\n")
    )
    helper(monkeypatch, code)
    if mode == "timeout":
        monkeypatch.setattr(check, "TIMEOUT_SECONDS", 0.2)

    async def scenario():
        task = asyncio.create_task(check.run_configuration_check(AFTER))
        if mode == "cancel":
            async with asyncio.timeout(2):
                while not marker.exists():
                    await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            return None
        return await task

    try:
        outcome = asyncio.run(scenario())
        assert_stopped(children)
        if mode != "cancel":
            assert outcome.status == ("passed" if mode == "success" else "failed")
        pid = int(marker.read_text())
        status = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        # A killed orphan may briefly remain a zombie until the OS reaps it.
        assert status.returncode in (0, 1) and not status.stderr
        assert not status.stdout.strip() or status.stdout.strip().startswith("Z")
    finally:
        if marker.exists():
            with suppress(ProcessLookupError):
                os.kill(int(marker.read_text()), signal.SIGKILL)
