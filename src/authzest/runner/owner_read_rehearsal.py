"""Run the two maintained owner-read reference phases in separate installed interpreters."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from importlib.util import find_spec
from time import monotonic

from authzest.codex.contracts import ContractError, canonical, decode
from authzest.owner_read_demo.checks import compare_owner_read_observations, owner_read_controls
from authzest.runner._generated_repair_process import ProcessError, ProcessPool

_PHASES = ("baseline", "reference")
_TIMEOUT = 20
_CLEANUP = 2
_OUTPUT_BYTES = 32_768
_MISSING_DEPS = 31


def _child(arguments: list[str]) -> int:
    if len(arguments) != 1 or arguments[0] not in _PHASES:
        return 2
    if any(find_spec(name) is None for name in ("fastapi", "httpx", "pytest")):
        return _MISSING_DEPS
    from authzest.owner_read_demo.rehearsal import run_phase

    print(json.dumps(run_phase(arguments[0]), ensure_ascii=True, allow_nan=False))
    return 0


def _empty_phase() -> dict:
    return {
        "status": "not-run",
        "observation": None,
        "comparison": None,
        "failure": None,
        "process": {
            "exit_code": None,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "cleanup_confirmed": None,
        },
    }


def _check_observation(phase: str, raw: bytes, result: dict) -> None:
    try:
        value = decode(raw.decode("utf-8"))
    except (ContractError, UnicodeError):
        result["failure"] = "invalid-child-json"
        return
    if set(value) != {"phase", "observations", "regression"} or value["phase"] != phase:
        result["failure"] = "invalid-phase-record"
        return
    comparison = compare_owner_read_observations(value["observations"])
    if comparison["status"] != "compared":
        result["failure"] = "invalid-observations"
        return
    result["comparison"] = comparison
    baseline = phase == "baseline"
    archived = next(case for case in owner_read_controls() if case["case_id"] == "owner-archived")
    expected_regression = {
        "status": "assertion-failed" if baseline else "passed",
        "pytest_exit": 1 if baseline else 0,
        "collected": 1,
        "setup": "passed",
        "call": "failed" if baseline else "passed",
        "teardown": "passed",
        "requests": 1,
        "response": archived["before" if baseline else "intended"],
    }
    regression = value["regression"]
    if type(regression) is not dict or regression.keys() != expected_regression.keys():
        result["failure"] = "invalid-regression-record"
        return
    lifecycle = (regression["status"], regression["pytest_exit"], regression["call"])
    if (
        any(type(regression[key]) is not int for key in ("collected", "requests", "pytest_exit"))
        or regression["collected"] != 1
        or regression["requests"] != 1
        or regression["setup"] != "passed"
        or regression["teardown"] != "passed"
        or lifecycle not in (("assertion-failed", 1, "failed"), ("passed", 0, "passed"))
    ):
        result["failure"] = "pytest-lifecycle-error"
        return
    profile = "matches_before_profile" if baseline else "matches_intended_policy"
    # JSON types matter; Python considers True == 1 and False == 0.
    if canonical(regression) != canonical(expected_regression) or not comparison[profile]:
        result.update(status="mismatch", failure="unexpected-observations")
        return
    result.update(status="matched", observation=value)


def _run_child(phase: str, directory: str, result: dict) -> None:
    deadline = monotonic() + _TIMEOUT
    pool = ProcessPool(max_output_bytes=_OUTPUT_BYTES, phase_deadline=deadline)
    failure = None
    try:
        handle = pool.start(
            [sys.executable, "-I", "-B", "-m", "authzest.runner.owner_read_rehearsal", phase],
            {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
            deadline,
            "owner-read-" + phase,
            cwd=directory,
        )
        pool.wait(handle, deadline)
    except ProcessError as exc:
        failure = exc.reason
    except KeyboardInterrupt:
        failure = "cancelled"
    finally:
        try:
            snapshots = pool.terminate_all(monotonic() + _CLEANUP)
        except (ProcessError, OSError, KeyboardInterrupt):
            snapshots = pool.snapshots()
            failure = "cleanup-unconfirmed"

    if not snapshots:
        result["failure"] = failure or "no-process-observation"
        return
    snapshot = snapshots[0]
    result["process"] = {
        "exit_code": snapshot.returncode,
        "stdout_bytes": len(snapshot.stdout),
        "stderr_bytes": len(snapshot.stderr),
        "cleanup_confirmed": snapshot.local_cleanup_confirmed and failure != "cleanup-unconfirmed",
    }
    if not snapshot.local_cleanup_confirmed:
        result["failure"] = "cleanup-unconfirmed"
    elif failure or pool.first_failure:
        result["failure"] = failure or pool.first_failure
    elif not snapshot.complete or snapshot.errors:
        result["failure"] = "incomplete-capture"
    elif snapshot.returncode == _MISSING_DEPS:
        result["failure"] = "missing-dependencies"
    elif snapshot.returncode != 0:
        result["failure"] = "child-failed"
    else:
        _check_observation(phase, snapshot.stdout, result)


def _run_one(phase: str) -> dict:
    result = _empty_phase()
    result["status"] = "failed"
    try:
        with tempfile.TemporaryDirectory(prefix="authzest-owner-read-rehearse-", dir="/tmp") as cwd:
            _run_child(phase, cwd, result)
    except (ProcessError, OSError):
        result.update(status="failed", failure="local-phase-error")
    except KeyboardInterrupt:
        result.update(status="failed", failure="cancelled")
    return result


def run_rehearsal() -> dict:
    """Observe only installed maintainer code. Each phase must match its complete profile."""
    result = {
        "schema_version": "1.0",
        "kind": "owner-read-rehearsal",
        "provenance": "maintainer-reference",
        "status": "unsupported",
        "exit_code": 2,
        "baseline": _empty_phase(),
        "reference": _empty_phase(),
        "model_invoked": False,
        "patch_application": "not-run",
        "restoration_status": "not-run",
    }
    if os.name != "posix" or getattr(sys, "frozen", False):
        return result
    for phase in _PHASES:
        observation = _run_one(phase)
        result[phase] = observation
        if observation["status"] != "matched":
            reason = observation["failure"]
            if reason == "missing-dependencies":
                result.update(status="missing-dependencies", exit_code=2)
            elif reason == "cancelled":
                result.update(status="cancelled", exit_code=130)
            else:
                result.update(status="failed", exit_code=1)
            return result
    result.update(status="completed", exit_code=0)
    return result


if __name__ == "__main__":
    raise SystemExit(_child(sys.argv[1:]))
