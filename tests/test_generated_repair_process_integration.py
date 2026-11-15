"""Genuine local children executing only these maintained regression constants.

No Docker, target application, generated artifact, provider or network is used.
Each Python child disables site initialization/environment influence and has a
short self-expiry fallback in addition to the transport's cleanup deadline.
"""

from __future__ import annotations

import os
import sys
from time import monotonic

import pytest

from authzest.runner import _generated_repair_process as transport

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX owned-child regression")

_RUNNING = "import os,time\nos.write(1,b'A-out\\n')\nos.write(2,b'A-err\\n')\ntime.sleep(2.0)\n"
_COMPLETING = "import os\nos.write(1,b'B-out\\n')\nos.write(2,b'B-err\\n')\n"
_CLEANUP_MARKER = "import os\nos.write(1,b'cleanup-out\\n')\nos.write(2,b'cleanup-err\\n')\n"
_FLOODING = (
    "import os,time\n"
    "end=time.monotonic()+1.5\n"
    "try:\n"
    " while time.monotonic()<end: os.write(1,b'F'*4096)\n"
    "except BrokenPipeError: time.sleep(0.3)\n"
)


def _argv(source):
    return [sys.executable, "-I", "-S", "-c", source]


def _assert_reaped_and_closed(pool, snapshots):
    assert snapshots and all(item.local_cleanup_confirmed for item in snapshots)
    for state in pool._states:
        process = state.process
        assert process is not None and process.returncode is not None
        assert process.stdout.closed and process.stderr.closed
        with pytest.raises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)


def test_real_concurrent_children_capture_both_pipes_under_one_budget():
    phase_deadline = monotonic() + 0.9
    pool = transport.ProcessPool(phase_deadline=phase_deadline)
    cleanup = ()
    try:
        a = pool.start(_argv(_RUNNING), {}, phase_deadline, "trusted-A")
        while (pool.snapshot(a).stdout, pool.snapshot(a).stderr) != (b"A-out\n", b"A-err\n"):
            pool.pump(phase_deadline)
        assert pool.snapshot(a).returncode is None
        b = pool.start(_argv(_COMPLETING), {}, phase_deadline, "trusted-B")
        result = pool.wait(b, phase_deadline)
        assert result.complete and result.returncode == 0
        assert (result.stdout, result.stderr) == (b"B-out\n", b"B-err\n")
        assert pool.snapshot(a).returncode is None and pool.snapshot(a).complete is False
        assert (pool.snapshot(a).stdout, pool.snapshot(a).stderr) == (b"A-out\n", b"A-err\n")
        assert pool.output_bytes == 24
        assert pool.first_failure is None
    finally:
        cleanup = pool.terminate_all(monotonic() + 0.6)
    _assert_reaped_and_closed(pool, cleanup)


def test_real_timeout_then_cleanup_dispatch_and_owned_group_reap():
    phase_deadline = monotonic() + 1.0
    pool = transport.ProcessPool(phase_deadline=phase_deadline, cleanup_reserve_bytes=32_768)
    cleanup_deadline, cleanup = None, ()
    try:
        a = pool.start(_argv(_RUNNING), {}, phase_deadline, "trusted-timeout-A")
        with pytest.raises(transport.ProcessError, match="original-deadline-expired"):
            pool.wait(a, phase_deadline)
        assert (pool.snapshot(a).stdout, pool.snapshot(a).stderr) == (b"A-out\n", b"A-err\n")
        cleanup_deadline = monotonic() + 0.7
        pool.begin_cleanup(cleanup_deadline)
        assert pool._states[0].process.stdout.closed and pool._states[0].process.stderr.closed
        assert pool.snapshot(a).complete is False
        marker = pool.start(_argv(_CLEANUP_MARKER), {}, cleanup_deadline, "trusted-cleanup")
        result = pool.wait(marker, cleanup_deadline)
        assert result.complete and result.returncode == 0
        assert (result.stdout, result.stderr) == (b"cleanup-out\n", b"cleanup-err\n")
        assert pool.first_failure == "original-deadline-expired"
        assert pool.output_bytes == 36
    finally:
        cleanup = pool.terminate_all(cleanup_deadline or monotonic() + 0.7)
    _assert_reaped_and_closed(pool, cleanup)
    assert pool.first_failure == "original-deadline-expired"


def test_real_flooding_capture_cannot_consume_reserved_cleanup_output():
    phase_deadline = monotonic() + 0.9
    reserve = 32_768
    normal_limit = transport.MAX_OUTPUT_BYTES - reserve
    pool = transport.ProcessPool(phase_deadline=phase_deadline, cleanup_reserve_bytes=reserve)
    cleanup_deadline, cleanup = None, ()
    try:
        noisy = pool.start(_argv(_FLOODING), {}, phase_deadline, "trusted-flood")
        with pytest.raises(transport.ProcessError, match="normal-output-limit"):
            pool.wait(noisy, phase_deadline)
        assert pool.output_bytes == normal_limit + 1
        assert pool.snapshot(noisy).complete is False
        cleanup_deadline = monotonic() + 0.7
        pool.begin_cleanup(cleanup_deadline)
        assert pool._states[0].process.stdout.closed and pool._states[0].process.stderr.closed
        marker = pool.start(_argv(_CLEANUP_MARKER), {}, cleanup_deadline, "trusted-flood-cleanup")
        result = pool.wait(marker, cleanup_deadline)
        assert result.complete and (result.stdout, result.stderr) == (
            b"cleanup-out\n",
            b"cleanup-err\n",
        )
        assert pool.output_bytes == normal_limit + 1 + 24 <= transport.MAX_OUTPUT_BYTES
        assert pool.first_failure == "normal-output-limit"
        assert pool.snapshot(noisy).complete is False
    finally:
        cleanup = pool.terminate_all(cleanup_deadline or monotonic() + 0.7)
    _assert_reaped_and_closed(pool, cleanup)
    assert pool.first_failure == "normal-output-limit"
