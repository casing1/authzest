"""Fixed child transport for captured-file repair checks, not an OS sandbox.

The trusted coordinator owns consent and exact input validation. This module has
no caller-selectable command, executable, source callback, path or environment. Cancellation
is re-raised unchanged, with its final ``worker_transport`` diagnostic attached.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import CoroutineType

from authzest.codex.contracts import canonical
from authzest.runner._owner_policy_file_worker import (
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    WORKER_SOURCE,
)

TIMEOUT_SECONDS = 5.0
MAX_CLEANUP_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class WorkerTransport:
    output: bytes
    exit_code: int | None
    reason: str | None
    child_cleanup_status: str
    workspace_cleanup_status: str
    launch_status: str


class _OutputLimitError(ValueError):
    pass


class _LaunchGuardError(RuntimeError):
    """A trusted prelaunch guard failed before any subprocess launch was attempted."""


class _LaunchGuardCancelled(_LaunchGuardError):
    def __init__(self, original: asyncio.CancelledError):
        super().__init__("Prelaunch guard cancelled")
        self.original = original


async def _launch(directory: Path, before_launch: Callable[[], None] | None):
    # Run inside the scheduled launch task: task-queue delay may have expired the
    # decision after directory setup. There is no intervening await before launch.
    if before_launch is not None:
        try:
            outcome = before_launch()
            if outcome is not None:
                if type(outcome) is CoroutineType:
                    outcome.close()  # Reject async guards without running their bodies.
                raise _LaunchGuardError("Prelaunch guard did not confirm")
        except asyncio.CancelledError as exc:
            raise _LaunchGuardCancelled(exc) from None
        except Exception:
            raise _LaunchGuardError("Prelaunch guard failed") from None
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-S",
        "-c",
        WORKER_SOURCE,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=directory,
        env=_environment(directory),
        start_new_session=True,
        limit=MAX_OUTPUT_BYTES + 1,
    )


async def _exchange(process, raw: bytes) -> bytes:
    if type(raw) is not bytes or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Invalid input size")
    if process.stdin is None or process.stdout is None:
        raise ValueError("Missing worker pipes")
    process.stdin.write(raw)
    await process.stdin.drain()
    process.stdin.close()
    output = bytearray()
    while True:
        chunk = await process.stdout.read(min(1024, MAX_OUTPUT_BYTES + 1 - len(output)))
        if not chunk:
            return bytes(output)
        output.extend(chunk)
        if len(output) > MAX_OUTPUT_BYTES:
            raise _OutputLimitError


def _environment(directory: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(directory),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }


def _consume_task_outcome(task) -> None:
    # A cancelled in-flight launch/reaper may finish later. Retrieve its exception
    # without awaiting beyond the cleanup deadline or claiming it had no child.
    with suppress(asyncio.CancelledError):
        task.exception()


async def _wait_before(task, deadline: float) -> bool:
    remaining = max(0.0, deadline - asyncio.get_running_loop().time())
    if not task.done() and remaining:
        await asyncio.wait({task}, timeout=remaining)
    if task.done():
        return True
    task.cancel()
    task.add_done_callback(_consume_task_outcome)
    return False


async def _finish_child(launch, process) -> tuple[str, str, int | None]:
    """Share one additional deadline between an in-flight launch and kill/reap.

    Cancellation during startup cannot establish that no child exists. A shielded
    launch can yield its handle within the cleanup budget; otherwise the result stays
    ambiguous/unconfirmed even after cancelling the pending launch task.
    """
    deadline = asyncio.get_running_loop().time() + MAX_CLEANUP_SECONDS
    if process is None:
        if launch is None:
            return "not-needed", "not-attempted", None
        if not await _wait_before(launch, deadline):
            return "unconfirmed", "ambiguous", None
        try:
            process = launch.result()
        except _LaunchGuardError:
            return "not-needed", "not-attempted", None
        except asyncio.CancelledError:
            return "unconfirmed", "ambiguous", None
        except (OSError, ValueError, TypeError):
            return "not-needed", "no-child", None
        except Exception:
            return "unconfirmed", "ambiguous", None
    killed = True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        killed = False
    reaper = asyncio.create_task(process.wait())
    if not await _wait_before(reaper, deadline):
        return "unconfirmed", "started", process.returncode
    try:
        exit_code = reaper.result()
    except (Exception, asyncio.CancelledError):
        return "unconfirmed", "started", process.returncode
    return "confirmed" if killed else "unconfirmed", "started", exit_code


async def _protected_cleanup(launch, process):
    # Repeated caller cancellation neither abandons the bounded cleanup task nor
    # replaces the first cancellation. Filesystem cleanup happens afterward.
    cleanup = asyncio.create_task(_finish_child(launch, process))
    cancellation = None
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError as exc:
            if cancellation is None:
                cancellation = exc
        except Exception:
            break
    try:
        status = cleanup.result()
    except (Exception, asyncio.CancelledError):
        status = ("unconfirmed", "started" if process is not None else "ambiguous", None)
    return status, cancellation


async def run_worker(
    worker_input: dict, *, before_launch: Callable[[], None] | None = None
) -> WorkerTransport:
    """Run the fixed recipe once; the coordinator must first consume its decision.

    Startup, I/O and completion share five seconds; child cleanup gets one additional
    second. Host directory creation/removal is synchronous and has no hard wall cap.
    Only a successful exchange with both cleanup steps confirmed returns output.
    An optional trusted synchronous guard must return None or raise; it rechecks
    coordinator decisions after directory setup and task scheduling, not authority
    supplied by this low-level helper. It cannot select a command or source.
    """
    if os.name != "posix" or getattr(sys, "frozen", False):
        return WorkerTransport(
            b"", None, "unsupported-platform", "not-needed", "not-needed", "not-attempted"
        )
    try:
        if type(worker_input) is not dict:
            raise TypeError("Invalid worker input")
        if before_launch is not None and not callable(before_launch):
            raise TypeError("Invalid prelaunch guard")
        wire = canonical(worker_input).encode("utf-8")
        if len(wire) > MAX_INPUT_BYTES:
            raise ValueError("Invalid input size")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return WorkerTransport(
            b"", None, "worker-input-error", "not-needed", "not-needed", "not-attempted"
        )

    output = b""
    exit_code = None
    reason = None
    process = None
    launch = None
    temporary = None
    cancellation = None
    child_cleanup = "not-needed"
    workspace_cleanup = "unconfirmed"
    launch_status = "not-attempted"
    try:
        temporary = TemporaryDirectory(prefix="authzest-owner-file-check-")
        directory = Path(temporary.name).resolve()
        async with asyncio.timeout(TIMEOUT_SECONDS):
            launch = asyncio.create_task(_launch(directory, before_launch))
            launch_status = "ambiguous"
            process = await asyncio.shield(launch)
            launch_status = "started"
            output = await _exchange(process, wire)
            exit_code = await process.wait()
            if exit_code != 0:
                reason = "worker-exit-error"
    except _LaunchGuardCancelled as exc:
        cancellation = exc.original
    except asyncio.CancelledError as exc:
        cancellation = exc
    except TimeoutError:
        # Synchronous host directory operations are outside the child deadline.
        reason = "worker-process-error" if launch is None else "timeout"
    except _OutputLimitError:
        reason = "output-limit"
    except (OSError, ValueError, TypeError, RuntimeError):
        reason = "worker-process-error"
    finally:
        status, cleanup_cancellation = await _protected_cleanup(launch, process)
        child_cleanup, launch_status, cleaned_exit = status
        if cleaned_exit is not None:
            exit_code = cleaned_exit
        if cancellation is None:
            cancellation = cleanup_cancellation
        if temporary is not None:
            try:
                temporary.cleanup()
                workspace_cleanup = "confirmed"
            except Exception:
                workspace_cleanup = "unconfirmed"
    if cancellation is not None:
        reason = "cancelled"
    elif reason is None and (child_cleanup != "confirmed" or workspace_cleanup != "confirmed"):
        reason = "cleanup-unconfirmed"
    result = WorkerTransport(
        output if reason is None else b"",
        exit_code,
        reason,
        child_cleanup,
        workspace_cleanup,
        launch_status,
    )
    if cancellation is not None:
        cancellation.worker_transport = result
        raise cancellation
    return result
