"""Publicly describable reference phases, with no provider or generated artifact."""

import json
import os
import stat
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.owner_read_demo.checks import owner_read_controls
from authzest.runner import owner_read_rehearsal as runner
from authzest.runner._generated_repair_process import ProcessError, ProcessSnapshot


def phase_payload(phase):
    before = phase == "baseline"
    controls = owner_read_controls()
    observations = [
        {"case_id": c["case_id"], **c["before" if before else "intended"]} for c in controls
    ]
    archived = controls[1]["before" if before else "intended"]
    return {
        "phase": phase,
        "regression": {
            "status": "assertion-failed" if before else "passed",
            "pytest_exit": int(before),
            "collected": 1,
            "setup": "passed",
            "call": "failed" if before else "passed",
            "teardown": "passed",
            "requests": 1,
            "response": archived,
        },
        "observations": observations,
    }


@pytest.mark.skipif(os.name != "posix", reason="POSIX installed interpreter required")
def test_real_two_phase_rehearsal_ignores_ambient_pytest_settings(monkeypatch):
    monkeypatch.setenv("PYTEST_ADDOPTS", "--unexpected-option")
    monkeypatch.setenv("PYTEST_PLUGINS", "uninstalled_ambient_plugin")
    result = runner.run_rehearsal()
    assert result["status"] == "completed" and result["exit_code"] == 0
    assert result["provenance"] == "maintainer-reference" and result["model_invoked"] is False
    assert result["patch_application"] == result["restoration_status"] == "not-run"
    for phase, count in (("baseline", 6), ("reference", 7)):
        observed = result[phase]
        assert observed["observation"] == phase_payload(phase)
        assert observed["comparison"]["intended_matches"] == count
        assert observed["process"]["cleanup_confirmed"] is True
        assert observed["process"]["exit_code"] == 0
        assert 0 < observed["process"]["stdout_bytes"] <= 32768
        assert observed["status"] == "matched" and observed["failure"] is None


@pytest.fixture
def fake_pool(monkeypatch):
    if os.name != "posix":
        pytest.skip("POSIX private directory and process transport")
    calls = []
    options = {}
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(runner, "sys", SimpleNamespace(executable=sys.executable))
    snapshot = ProcessSnapshot("owner-read-baseline", 1234, 0, b"", b"", True, (), True)

    class Pool:
        first_failure = None

        def __init__(self, *, max_output_bytes, phase_deadline):
            assert max_output_bytes == 32768 and 0 < phase_deadline - runner.monotonic() <= 20

        def start(self, argv, env, deadline, label, *, cwd):
            phase = argv[-1]
            assert argv == [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "authzest.runner.owner_read_rehearsal",
                phase,
            ]
            assert env == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
            path = Path(cwd)
            assert not list(path.iterdir()) and stat.S_IMODE(path.stat().st_mode) == 0o700
            calls.append((phase, path))
            self.phase = phase
            return label

        def wait(self, handle, deadline):
            if error := options.get("wait_error"):
                raise error

        def terminate_all(self, deadline):
            assert 0 < deadline - runner.monotonic() <= 2
            if options.get("terminate_error"):
                raise ProcessError("cleanup-failed", ())
            return self.snapshots()

        def snapshots(self):
            record = phase_payload(self.phase)
            if modify := options.get("modify"):
                modify(record)
            raw = options.get("raw", json.dumps(record).encode())
            normal = replace(snapshot, stdout=raw, label="owner-read-" + self.phase)
            return (replace(normal, **options.get("snapshot", {})),)

    monkeypatch.setattr(runner, "ProcessPool", Pool)
    return calls, options


def test_fixed_child_invocations_have_distinct_cleaned_directories(fake_pool):
    calls, _ = fake_pool
    assert runner.run_rehearsal()["status"] == "completed"
    assert [phase for phase, _ in calls] == ["baseline", "reference"]
    assert calls[0][1] != calls[1][1] and all(not path.exists() for _, path in calls)


@pytest.mark.parametrize(
    "options,reason",
    [
        ({"raw": b"{not-json"}, "invalid-child-json"),
        ({"raw": b'{"phase":1,"phase":2}'}, "invalid-child-json"),
        ({"modify": lambda r: r.update(phase="reference")}, "invalid-phase-record"),
        ({"modify": lambda r: r["observations"].pop()}, "invalid-observations"),
        (
            {"modify": lambda r: r["observations"][0]["body"].update(title="wrong")},
            "unexpected-observations",
        ),
        ({"modify": lambda r: r["regression"].update(pytest_exit=True)}, "pytest-lifecycle-error"),
        ({"modify": lambda r: r["regression"].update(collected=2)}, "pytest-lifecycle-error"),
        ({"modify": lambda r: r["regression"].update(setup="failed")}, "pytest-lifecycle-error"),
        (
            {"modify": lambda r: r["regression"].update(teardown="failed")},
            "pytest-lifecycle-error",
        ),
        ({"modify": lambda r: r["regression"].update(requests=0)}, "pytest-lifecycle-error"),
        (
            {"modify": lambda r: r["regression"].update(response={"status_code": 403})},
            "unexpected-observations",
        ),
        ({"snapshot": {"returncode": 4, "stderr": b"private diagnostic"}}, "child-failed"),
        ({"snapshot": {"complete": False}}, "incomplete-capture"),
        ({"snapshot": {"local_cleanup_confirmed": False}}, "cleanup-unconfirmed"),
        ({"terminate_error": True}, "cleanup-unconfirmed"),
        (
            {"wait_error": ProcessError("original-deadline-expired", ())},
            "original-deadline-expired",
        ),
        ({"wait_error": ProcessError("combined-output-limit", ())}, "combined-output-limit"),
    ],
)
def test_invalid_baseline_stops_reference_and_redacts_supplied_data(fake_pool, options, reason):
    calls, state = fake_pool
    state.update(options)
    result = runner.run_rehearsal()
    assert result["status"] == "failed" and result["exit_code"] == 1
    assert result["baseline"]["failure"] == reason
    assert result["baseline"]["observation"] is None
    assert result["reference"]["status"] == "not-run" and len(calls) == 1
    assert not calls[0][1].exists() and "private diagnostic" not in json.dumps(result)


def test_interrupt_and_missing_dependencies_have_distinct_outcomes(fake_pool):
    _, options = fake_pool
    options["snapshot"] = {"returncode": runner._MISSING_DEPS}
    assert runner.run_rehearsal()["status"] == "missing-dependencies"
    options.clear()
    options["wait_error"] = KeyboardInterrupt()
    result = runner.run_rehearsal()
    assert result["status"] == "cancelled" and result["exit_code"] == 130
    assert result["baseline"]["process"]["cleanup_confirmed"] is True
    assert result["reference"]["status"] == "not-run"


@pytest.mark.parametrize("name,frozen", [("nt", False), ("posix", True)])
def test_unsupported_never_starts_a_phase(monkeypatch, name, frozen):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name=name))
    monkeypatch.setattr(runner, "sys", SimpleNamespace(frozen=frozen))
    monkeypatch.setattr(runner, "_run_one", lambda _: pytest.fail("Unexpected launch"))
    result = runner.run_rehearsal()
    assert result["status"] == "unsupported" and result["exit_code"] == 2
    assert result["baseline"]["status"] == result["reference"]["status"] == "not-run"


def test_fixed_child_refuses_unknown_phase_and_detects_missing_extras(monkeypatch):
    monkeypatch.setattr(runner, "find_spec", lambda _: None)
    assert runner._child(["reference", "elsewhere"]) == runner._child(["elsewhere"]) == 2
    assert runner._child(["baseline"]) == runner._MISSING_DEPS
