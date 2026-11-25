"""Suite-wide stall guard: one stuck test fails the run with stacks, not a CI cancel."""

from __future__ import annotations

import faulthandler
import os
import sys

import pytest

# Far above any test's normal runtime (single digits of seconds even on slow CI
# runners), so only a real stall trips it. faulthandler then writes every thread's
# stack, naming the stuck test and frame, and exits non-zero. Without it a stall
# burns the rest of a job's time budget and the job shows only "cancelled".
STALLED_TEST_SECONDS = 120.0
_stderr_fd: int | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _stderr_fd
    # Capture is suspended here; keep a copy of the real stderr, because during a
    # test file descriptor 2 is redirected and would be lost when the process exits.
    for stream in (sys.stderr, sys.__stderr__):
        try:
            _stderr_fd = os.dup(stream.fileno())
            return
        except (AttributeError, ValueError, OSError):
            continue  # No real descriptor (e.g. a wrapped stream): leave the guard off.


def pytest_unconfigure(config: pytest.Config) -> None:
    global _stderr_fd
    if _stderr_fd is not None:
        os.close(_stderr_fd)
        _stderr_fd = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    if _stderr_fd is None:
        yield
        return
    faulthandler.dump_traceback_later(STALLED_TEST_SECONDS, exit=True, file=_stderr_fd)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
