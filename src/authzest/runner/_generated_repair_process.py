"""Private POSIX pipe transport, not command validation or Docker cleanup.

The trusted caller supplies reviewed argv/environment and original deadlines.
This module adds no shell, environment, retries or execution authorization. It
retains one shared bounded output history while servicing concurrent children.
Synchronous spawn/signal/close calls have no universal preemption guarantee.
"""

from __future__ import annotations

import math
import os
import re
import selectors
import signal
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic

MAX_OUTPUT_BYTES = 262_144
_POLL_INTERVAL = 0.05


@dataclass(frozen=True, slots=True)
class ProcessHandle:
    token: int
    label: str


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    label: str
    pid: int | None
    returncode: int | None
    stdout: bytes
    stderr: bytes
    complete: bool
    errors: tuple[str, ...]
    local_cleanup_confirmed: bool


class ProcessError(RuntimeError):
    def __init__(self, reason: str, snapshots: tuple[ProcessSnapshot, ...]):
        super().__init__("Private process transport failed: " + reason)
        self.reason, self.snapshots = reason, snapshots


@dataclass(slots=True)
class _State:
    handle: ProcessHandle
    deadline: float
    created_in_cleanup: bool = False
    process: object = None
    streams: dict = field(default_factory=dict)
    closed: set = field(default_factory=set)
    eof: set = field(default_factory=set)
    stdout: bytearray = field(default_factory=bytearray)
    stderr: bytearray = field(default_factory=bytearray)
    errors: list[str] = field(default_factory=list)
    cleanup_confirmed: bool = False
    group_absent: bool = False
    close_uncertain: bool = False
    input_stream: object = None
    input_closed: bool = False


class ProcessPool:
    """One phase's local children and output allowance; never a session token."""

    def __init__(
        self,
        clock: Callable[[], float] = monotonic,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        *,
        phase_deadline: float | None = None,
        cleanup_reserve_bytes: int = 0,
    ):
        if (
            not callable(clock)
            or type(max_output_bytes) is not int
            or not 0 < max_output_bytes <= MAX_OUTPUT_BYTES
            or type(cleanup_reserve_bytes) is not int
            or not 0 <= cleanup_reserve_bytes < max_output_bytes
        ):
            raise ValueError("Invalid process pool configuration")
        if phase_deadline is not None and (
            type(phase_deadline) not in {int, float} or not math.isfinite(phase_deadline)
        ):
            raise ValueError("Invalid original process phase deadline")
        if os.name != "posix" or getattr(sys, "frozen", False):
            raise ProcessError("unsupported-platform", ())
        self._clock, self._maximum = clock, max_output_bytes
        self._normal_limit = max_output_bytes - cleanup_reserve_bytes
        self._normal_output_exhausted = False
        self._last, self._phase_deadline, self._first = None, phase_deadline, None
        self._cleanup_deadline, self._cleanup_mode = None, False
        self._used, self._states, self._busy, self._closed = 0, [], False, False
        self._selector = selectors.DefaultSelector()
        self._selector_cleanup_uncertain = False

    @property
    def first_failure(self) -> str | None:
        return self._first

    @property
    def output_bytes(self) -> int:
        return self._used

    def _record(self, reason: str, state: _State | None = None) -> None:
        if self._first is None:
            self._first = reason
        if state is not None and reason not in state.errors and len(state.errors) < 16:
            state.errors.append(reason)

    def _raise(self, reason: str, state: _State | None = None) -> None:
        self._record(reason, state)
        raise ProcessError(self._first, self.snapshots())

    def _now(self) -> float:
        value = self._clock()
        if (
            type(value) not in {int, float}
            or not math.isfinite(value)
            or (self._last is not None and value < self._last)
        ):
            self._raise("invalid-or-reversing-clock")
        self._last = float(value)
        return self._last

    def _deadline(self, deadline: float) -> float:
        if type(deadline) not in {int, float} or not math.isfinite(deadline):
            self._raise("invalid-deadline")
        value = float(deadline)
        limit = self._cleanup_deadline if self._cleanup_mode else self._phase_deadline
        if limit is not None:
            value = min(value, limit)
        if value <= self._now():
            self._raise("original-deadline-expired")
        return value

    def _enter(self) -> None:
        if self._busy:
            self._raise("reentrant-operation")
        if self._closed:
            self._raise("pool-closed")
        if self._first is not None and not self._cleanup_mode:
            self._raise(self._first)
        if self._used > self._maximum:
            self._raise("combined-output-limit")
        self._busy = True

    def _cancel(self, error: BaseException) -> None:
        self._record("cancelled")
        try:
            error.process_observation = self.snapshots()
            error.process_first_failure = self._first
        except Exception:
            pass

    def _state(self, handle: ProcessHandle) -> _State:
        if (
            type(handle) is not ProcessHandle
            or type(handle.token) is not int
            or not 0 <= handle.token < len(self._states)
            or self._states[handle.token].handle is not handle
        ):
            self._raise("foreign-process-handle")
        return self._states[handle.token]

    def snapshot(self, handle: ProcessHandle) -> ProcessSnapshot:
        state = self._state(handle)
        process = state.process
        return ProcessSnapshot(
            state.handle.label,
            getattr(process, "pid", None),
            getattr(process, "returncode", None),
            bytes(state.stdout),
            bytes(state.stderr),
            process is not None
            and process.returncode is not None
            and state.eof == {"stdout", "stderr"},
            tuple(state.errors),
            state.cleanup_confirmed,
        )

    def snapshots(self) -> tuple[ProcessSnapshot, ...]:
        return tuple(self.snapshot(state.handle) for state in self._states)

    def begin_cleanup(self, deadline: float) -> None:
        """One bounded cleanup-only window; caller still owns command policy."""
        if self._busy:
            self._raise("reentrant-operation")
        if self._closed or self._cleanup_mode:
            self._raise("cleanup-already-started-or-pool-closed")
        self._busy = True
        try:
            if type(deadline) not in {int, float} or not math.isfinite(deadline):
                self._raise("invalid-cleanup-deadline")
            remaining = deadline - self._now()
            if not 0 < remaining <= 10.000001:
                self._raise("invalid-cleanup-window")
            self._cleanup_deadline, self._cleanup_mode = float(deadline), True
            if self._normal_limit < self._maximum:
                # Stop old capture at terminal cleanup, including timeout or
                # successful B completion. Otherwise a newly noisy attached A
                # could consume the reserve before fixed cleanup commands.
                # Closing is not EOF evidence and does not complete that handle.
                for state in self._states:
                    for name in ("stdout", "stderr"):
                        self._close_stream(state, name)
        except ProcessError:
            raise
        except Exception:
            self._raise("cleanup-mode-failed")
        except BaseException as error:
            self._cancel(error)
            raise
        finally:
            self._busy = False

    def start(
        self,
        argv,
        env,
        deadline: float,
        label: str,
        *,
        cwd: str | None = None,
        input_bytes: bytes | None = None,
    ) -> ProcessHandle:
        """Spawn exactly supplied data; command policy belongs to the caller."""
        self._enter()
        state = None
        failure = None
        try:
            deadline = self._deadline(deadline)
            if (
                type(argv) not in {list, tuple}
                or not 1 <= len(argv) <= 256
                or any(
                    type(arg) is not str or "\0" in arg or len(arg.encode()) > 8192 for arg in argv
                )
                or not argv[0].startswith("/")
                or sum(len(arg.encode()) for arg in argv) > 65_536
                or type(env) is not dict
                or len(env) > 64
                or any(
                    type(key) is not str
                    or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None
                    or type(value) is not str
                    or "\0" in value
                    or len(value.encode()) > 8192
                    for key, value in env.items()
                )
                or sum(len(key) + len(value.encode()) for key, value in env.items()) > 65_536
                or (cwd is not None and (type(cwd) is not str or not os.path.isabs(cwd)))
                or (
                    input_bytes is not None
                    and (type(input_bytes) is not bytes or len(input_bytes) > 512)
                )
                or type(label) is not str
                or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", label) is None
                or len(self._states) >= 64
                or any(item.handle.label == label for item in self._states)
            ):
                self._raise("invalid-process-input")
            handle = ProcessHandle(len(self._states), label)
            if self._phase_deadline is None and not self._cleanup_mode:
                self._phase_deadline = deadline
            state = _State(handle, deadline, created_in_cleanup=self._cleanup_mode)
            self._states.append(state)
            state.process = subprocess.Popen(
                list(argv),
                env=dict(env),
                stdin=subprocess.DEVNULL if input_bytes is None else subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                bufsize=0,
                **({"cwd": cwd} if cwd is not None else {}),
            )
            process = state.process
            if input_bytes is not None:
                state.input_stream = process.stdin
            if type(process.pid) is not int or process.pid <= 0:
                self._raise("invalid-child-handle", state)
            for name in ("stdout", "stderr"):
                stream = getattr(process, name)
                state.streams[name] = stream
                os.set_blocking(stream.fileno(), False)
                self._selector.register(stream, selectors.EVENT_READ, (state, name))
            if input_bytes is not None:
                self._write_input(state, input_bytes, deadline)
            self._deadline(deadline)
            return handle
        except ProcessError as error:
            failure = error
            raise
        except Exception as error:
            failure = error
            self._raise("process-start-failed", state)
        except BaseException as error:
            failure = error
            self._cancel(error)
            raise
        finally:
            try:
                if state is not None:
                    self._close_input(state)
            except BaseException:
                if failure is None:
                    raise
            finally:
                self._busy = False

    def _close_input(self, state: _State) -> None:
        if state.input_stream is None or state.input_closed:
            return
        try:
            state.input_stream.close()
            state.input_closed = True
        except BaseException:
            state.close_uncertain = True
            self._record("input-pipe-cleanup-unconfirmed", state)
            raise

    def _write_input(self, state: _State, data: bytes, deadline: float) -> None:
        # At most POSIX's minimum PIPE_BUF enters a fresh empty pipe. Nonblocking
        # writes still refuse unavailable capacity instead of waiting for a reader.
        failure = None
        try:
            descriptor = state.input_stream.fileno()
            os.set_blocking(descriptor, False)
            remaining = memoryview(data)
            while remaining:
                self._deadline(deadline)
                try:
                    written = os.write(descriptor, remaining)
                except InterruptedError:
                    continue
                if type(written) is not int or not 0 < written <= len(remaining):
                    self._raise("process-input-incomplete", state)
                remaining = remaining[written:]
            self._deadline(deadline)
        except BaseException as exc:
            failure = exc
            if isinstance(exc, Exception) and not isinstance(exc, ProcessError):
                self._record("process-input-failed", state)
            raise
        finally:
            try:
                self._close_input(state)
            except BaseException:
                if failure is None:
                    raise

    def _close_stream(self, state: _State, name: str) -> None:
        if name in state.closed:
            return
        stream = state.streams.get(name) or getattr(state.process, name, None)
        state.closed.add(name)
        if stream is None:
            state.close_uncertain = True
            self._record("pipe-cleanup-unconfirmed", state)
            return
        cancellation = None
        try:
            self._selector.unregister(stream)
        except KeyError:
            pass
        except Exception:
            state.close_uncertain = True
            self._record("selector-unregister-failed", state)
        except BaseException as error:
            state.close_uncertain = True
            self._record("cancelled", state)
            cancellation = error
        try:
            stream.close()
        except Exception:
            state.close_uncertain = True
            self._record("pipe-cleanup-unconfirmed", state)
        except BaseException as error:
            state.close_uncertain = True
            self._record("cancelled", state)
            if cancellation is None:
                cancellation = error
        if cancellation is not None:
            raise cancellation

    def _step(self, deadline: float) -> None:
        active = [
            state.deadline
            for state in self._states
            if not self.snapshot(state.handle).complete
            and (not self._cleanup_mode or state.created_in_cleanup)
        ]
        limit = min([deadline, *active])
        remaining = limit - self._now()
        if remaining <= 0:
            self._raise("original-deadline-expired")
        for state in self._states:
            if state.process is not None:
                state.process.poll()
        events = self._selector.select(min(_POLL_INTERVAL, remaining))
        output_limit = self._maximum if self._cleanup_mode else self._normal_limit
        for key, _ in events:
            state, name = key.data
            try:
                raw = os.read(key.fd, min(65_536, output_limit + 1 - self._used))
            except BlockingIOError:
                continue
            if not raw:
                state.eof.add(name)
                self._close_stream(state, name)
                continue
            self._used += len(raw)
            target = getattr(state, name)
            available = max(
                0, self._maximum - sum(len(item.stdout) + len(item.stderr) for item in self._states)
            )
            target.extend(raw[:available])
            if self._used > output_limit:
                if not self._cleanup_mode and self._normal_limit < self._maximum:
                    self._normal_output_exhausted = True
                    self._raise("normal-output-limit", state)
                self._raise("combined-output-limit", state)
        for state in self._states:
            if state.process is not None:
                state.process.poll()
        self._deadline(limit)
        if self._first is not None and not self._cleanup_mode:
            self._raise(self._first)

    def pump(self, deadline: float) -> tuple[ProcessSnapshot, ...]:
        """One bounded selector step across every active child's two pipes."""
        self._enter()
        try:
            self._step(self._deadline(deadline))
            return self.snapshots()
        except ProcessError:
            raise
        except Exception:
            self._raise("process-io-failed")
        except BaseException as error:
            self._cancel(error)
            raise
        finally:
            self._busy = False

    def wait(self, handle: ProcessHandle, deadline: float) -> ProcessSnapshot:
        """Await one child while concurrently draining all children; never wait()."""
        self._enter()
        try:
            self._state(handle)
            deadline = self._deadline(deadline)
            while not self.snapshot(handle).complete:
                self._step(deadline)
            return self.snapshot(handle)
        except ProcessError:
            raise
        except Exception:
            self._raise("process-io-failed")
        except BaseException as error:
            self._cancel(error)
            raise
        finally:
            self._busy = False

    def terminate_all(self, deadline: float) -> tuple[ProcessSnapshot, ...]:
        """Kill/reap local groups under one deadline; does not clean containers."""
        if self._busy:
            self._raise("reentrant-operation")
        if self._closed:
            return self.snapshots()
        if type(deadline) not in {int, float} or not math.isfinite(deadline):
            self._raise("invalid-cleanup-deadline")
        if self._cleanup_deadline is not None:
            deadline = min(deadline, self._cleanup_deadline)
        self._busy = True
        cancellation = None
        operation_error = None

        def failed(error, reason, state=None):
            nonlocal cancellation
            self._record(reason if isinstance(error, Exception) else "cancelled", state)
            if not isinstance(error, Exception) and cancellation is None:
                cancellation = error

        try:
            for state in self._states:
                if state.process is None:
                    self._record("launch-cleanup-unconfirmed", state)
                    continue
                # Only an unreaped owned leader pins this numeric process-group
                # ID against reuse. Do not poll/reap before this signal decision.
                # A historical reaped leader permits absence observation only.
                if state.process.returncode is not None or state.group_absent:
                    continue
                try:
                    os.killpg(state.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    state.group_absent = True
                except BaseException as error:
                    failed(error, "group-signal-failed", state)
            for state in self._states:
                try:
                    self._close_input(state)
                except BaseException as error:
                    failed(error, "input-pipe-cleanup-unconfirmed", state)
                for name in ("stdout", "stderr"):
                    try:
                        self._close_stream(state, name)
                    except BaseException as error:
                        failed(error, "pipe-cleanup-unconfirmed", state)
            while True:
                unresolved = False
                for state in self._states:
                    if state.process is None:
                        continue
                    try:
                        state.process.poll()
                    except BaseException as error:
                        failed(error, "process-reap-unconfirmed", state)
                    if not state.group_absent:
                        try:
                            os.killpg(state.process.pid, 0)
                        except ProcessLookupError:
                            state.group_absent = True
                        except BaseException as error:
                            failed(error, "group-observation-failed", state)
                    state.cleanup_confirmed = (
                        state.process.returncode is not None
                        and state.group_absent
                        and state.closed == {"stdout", "stderr"}
                        and (state.input_stream is None or state.input_closed)
                        and not state.close_uncertain
                    )
                    unresolved |= state.process.returncode is None or not state.group_absent
                if not unresolved or cancellation is not None or self._now() >= deadline:
                    break
                self._selector.select(min(_POLL_INTERVAL, max(0, deadline - self._now())))
            for state in self._states:
                if not state.cleanup_confirmed:
                    self._record("local-cleanup-unconfirmed", state)
        except ProcessError as error:
            operation_error = error
            raise
        except Exception:
            self._record("local-cleanup-unconfirmed")
        except BaseException as error:
            failed(error, "local-cleanup-unconfirmed")
        finally:
            self._closed, self._busy = True, False
            try:
                self._selector.close()
            except BaseException as error:
                self._selector_cleanup_uncertain = True
                failed(error, "selector-cleanup-unconfirmed")
            if self._selector_cleanup_uncertain:
                for state in self._states:
                    state.cleanup_confirmed = False
            if operation_error is not None:
                operation_error.snapshots = self.snapshots()
        if cancellation is not None:
            self._cancel(cancellation)
            raise cancellation
        return self.snapshots()
