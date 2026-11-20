"""The packaged rehearsal exercises a fixed positive sample inside a fresh interpreter."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.owner_read_demo import rehearsal
from authzest.owner_read_demo.checks import compare_owner_read_observations

# Test-only bootstrap for both a checkout and a wheel installed outside it.
_PACKAGE_PARENT = str(Path(rehearsal.__file__).resolve().parents[2])
_RUN = (
    "import json, sys; sys.path.insert(0, sys.argv[1]); "
    "from authzest.owner_read_demo.rehearsal import run_phase; "
    "print(json.dumps(run_phase(sys.argv[2])))"
)


@pytest.mark.parametrize(
    ("phase", "outcome", "status", "body", "matches"),
    [
        ("baseline", "assertion-failed", 403, {"detail": "Read denied"}, 6),
        ("reference", "passed", 200, {"id": "archived-note", "title": "Archived note"}, 7),
    ],
)
def test_real_packaged_sample_and_independent_controls(
    phase, outcome, status, body, matches, tmp_path
):
    # Neither working-directory conftest nor external pytest flags can select additional code.
    (tmp_path / "conftest.py").write_text("raise RuntimeError('unrelated conftest')")
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", _RUN, _PACKAGE_PARENT, phase],
        cwd=tmp_path,
        env={
            **({"SYSTEMROOT": os.environ["SYSTEMROOT"]} if "SYSTEMROOT" in os.environ else {}),
            "PYTEST_ADDOPTS": "--missing-option",
            "PYTEST_PLUGINS": "missing_plugin",
        },
        capture_output=True,
        timeout=20,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["phase"] == phase
    assert payload["regression"] == {
        "status": outcome,
        "pytest_exit": int(phase == "baseline"),
        "collected": 1,
        "setup": "passed",
        "call": "failed" if phase == "baseline" else "passed",
        "teardown": "passed",
        "requests": 1,
        "response": {"status_code": status, "body": body},
    }
    comparison = compare_owner_read_observations(payload["observations"])
    assert comparison["intended_matches"] == matches
    assert comparison["matches_before_profile"] == (phase == "baseline")
    assert comparison["matches_intended_policy"] == (phase == "reference")


def test_rehearsal_refuses_unknown_phase_and_different_sample(monkeypatch, tmp_path):
    monkeypatch.setattr(pytest, "main", lambda *_a, **_kw: pytest.fail("unexpected collection"))
    with pytest.raises(ValueError, match="Unknown rehearsal phase"):
        rehearsal.run_phase("other")
    wrong = tmp_path / "changed.py"
    wrong.write_text("raise RuntimeError('changed')")
    monkeypatch.setattr(rehearsal, "_SAMPLE", wrong)
    with pytest.raises(ValueError, match="sample changed"):
        rehearsal.run_phase("reference")


def test_owner_client_only_accepts_one_positive_request():
    client = rehearsal._OwnerClient(rehearsal.create_app())
    response = client.get("/records/archived-note")
    assert response.status_code == 403
    with pytest.raises(ValueError):
        client.get("/records/archived-note")
    another = rehearsal._OwnerClient(rehearsal.create_app())
    with pytest.raises(ValueError):
        another.get("/records/active-note")
    assert another.response is None


@pytest.mark.parametrize(
    ("exit_code", "collected", "assertion", "stages", "requests"),
    [
        (1, 0, True, [], 0),
        (1, 2, True, ["passed", "failed", "passed"], 1),
        (1, 1, False, ["passed", "failed", "passed"], 1),
        (1, 1, True, ["failed", "failed", "passed"], 1),
        (1, 1, True, ["passed", "failed", "failed"], 1),
        (1, 1, True, ["passed", "failed", "passed"], 0),
        (2, 1, True, ["passed", "failed", "passed"], 1),
        (0, 1, False, ["passed", "skipped", "passed"], 1),
        (0, 1, False, ["passed", "passed", "passed"], 2),
    ],
)
def test_incomplete_or_inconsistent_pytest_facts_never_match(
    exit_code, collected, assertion, stages, requests
):
    record = rehearsal._PytestObservation(rehearsal.create_app())
    record.nodeid = "fixed"
    record.collected = collected
    record.sample_assertion = assertion
    record.stages = list(zip(("setup", "call", "teardown"), stages, strict=False))
    record.client.requests = requests
    record.client.response = {"status_code": 403, "body": {"detail": "Read denied"}}
    assert record.result(exit_code)["status"] == "error"


def test_assertion_in_fixture_is_not_the_packaged_test_assertion():
    record = rehearsal._PytestObservation(rehearsal.create_app())
    record.nodeid = "fixed"
    try:
        raise AssertionError("fixture error")
    except AssertionError as exc:
        call = SimpleNamespace(when="call", excinfo=SimpleNamespace(value=exc))
        record.pytest_runtest_makereport(SimpleNamespace(nodeid="fixed"), call)
    assert record.sample_assertion is False
