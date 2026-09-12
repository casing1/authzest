import builtins
import hashlib
import json
import math
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import smoke_fixture_runtime as gate


def summary(*, posix=True):
    return {
        "kind": "owned-fixture-runtime-smoke",
        "schema_version": "1.0",
        "verification_scope": "owned-fixture-runtime",
        "source_sha256": gate.AFTER_SHA256,
        "status": "passed" if posix else "unsupported",
        "reason": "runtime-check-passed" if posix else "unsupported-platform",
        "exit_code": 0 if posix else 2,
        "runtime_verification_status": "passed" if posix else "not-run",
        "runtime": {
            "status": "passed",
            "reason": "runtime-check-passed",
            "check_id": gate.CHECK_ID,
            "source_sha256": gate.AFTER_SHA256,
            "worker_sha256": gate.expected_worker_hash(),
            "exit_code": 0,
            "elapsed_ms": 12.5,
            "runtime_evidence": {
                "debug": False,
                "health_status": 200,
                "health_body": {"status": "ok"},
                "dependency_versions": {
                    "python": "3.12.7",
                    "fastapi": "0.141.1",
                    "starlette": "1.6.0",
                    "pydantic": "2.13.5",
                },
            },
        }
        if posix
        else None,
    }


def fake_binary(tmp_path):
    binary = tmp_path / "authzest-test-os"
    binary.write_bytes(b"unit-test placeholder, never executed")
    return binary


@pytest.mark.parametrize("posix", [True, False])
def test_selected_and_relocated_native_parents_use_the_fixed_command_only(
    tmp_path, monkeypatch, posix
):
    binary = fake_binary(tmp_path)
    calls = []

    def run(arguments, **options):
        calls.append((arguments, options))
        return subprocess.CompletedProcess(
            arguments, 0 if posix else 2, json.dumps(summary(posix=posix)), ""
        )

    monkeypatch.setattr(gate, "os", SimpleNamespace(name="posix" if posix else "nt"))
    monkeypatch.setattr(subprocess, "run", run)
    results = gate.smoke_runtime(binary)
    assert len(results) == len(calls) == 2
    assert calls[0][0][0] == str(binary.resolve())
    assert calls[1][0][0] != str(binary.resolve())
    for arguments, options in calls:
        assert arguments[1:] == ["_runtime-smoke"]
        assert options["timeout"] == 45
        assert options["stdin"] == subprocess.DEVNULL
        assert options.get("shell", False) is False
        assert options["cwd"] != gate.CHECKOUT
        assert "_PYI_ARCHIVE_FILE" not in options["env"]
    if not posix:
        assert all(value["runtime"] is None for value in results)


def test_verified_artifact_executes_only_copy_preserving_original_bytes_and_permissions(
    tmp_path, monkeypatch
):
    binary = fake_binary(tmp_path)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    binary.with_name(binary.name + ".sha256").write_bytes(f"{digest}  {binary.name}\n".encode())
    binary.chmod(stat.S_IRUSR | stat.S_IWUSR)
    mode = binary.stat().st_mode
    calls = []

    def run(arguments, **options):
        calls.append(arguments)
        copied = Path(arguments[0])
        assert copied != binary
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == digest
        assert copied.stat().st_mode & stat.S_IXUSR
        return subprocess.CompletedProcess(arguments, 0, json.dumps(summary()), "")

    monkeypatch.setattr(gate, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(subprocess, "run", run)
    selected, verified = gate.select_artifact(tmp_path)
    assert len(gate.smoke_runtime(selected, artifact_digest=verified)) == 1
    assert len(calls) == 1
    assert binary.stat().st_mode == mode
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == digest


def test_artifact_changed_after_checksum_is_rejected_without_execution(tmp_path, monkeypatch):
    binary = fake_binary(tmp_path)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    binary.write_bytes(b"changed artifact")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: pytest.fail("No changed binary execution")
    )
    with pytest.raises(gate.SmokeError, match="Copied artifact"):
        gate.smoke_runtime(binary, artifact_digest=digest)


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf, -math.inf])
def test_invalid_outer_deadline_never_runs_a_binary(tmp_path, monkeypatch, timeout):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: pytest.fail("No invalid-deadline execution")
    )
    with pytest.raises(gate.SmokeError, match="finite and positive"):
        gate.smoke_runtime(fake_binary(tmp_path), timeout)


@pytest.mark.parametrize(
    "change",
    [
        "missing-field",
        "extra-field",
        "wrong-kind",
        "wrong-scope",
        "top-exit-bool",
        "missing-dependency",
        "wrong-source",
        "wrong-worker",
        "wrong-check",
        "child-exit-bool",
        "debug-enabled",
        "debug-zero",
        "health-status",
        "health-body",
        "missing-version",
        "bad-version",
        "elapsed-bool",
        "elapsed-negative",
        "elapsed-nan",
        "elapsed-inf",
    ],
)
def test_malformed_or_missing_runtime_evidence_is_not_a_release_pass(change):
    value = summary()
    runtime = value["runtime"]
    evidence = runtime["runtime_evidence"]
    if change == "missing-field":
        del value["runtime_verification_status"]
    elif change == "extra-field":
        value["extra"] = "unreviewed"
    elif change == "wrong-kind":
        value["kind"] = "another-command"
    elif change == "wrong-scope":
        value["verification_scope"] = "source-configuration"
    elif change == "top-exit-bool":
        value["exit_code"] = False
    elif change == "missing-dependency":
        runtime.update(
            status="not-run", reason="runtime-dependency-unavailable", runtime_evidence=None
        )
    elif change == "wrong-source":
        runtime["source_sha256"] = "0" * 64
    elif change == "wrong-worker":
        runtime["worker_sha256"] = "0" * 64
    elif change == "wrong-check":
        runtime["check_id"] = "another-check"
    elif change == "child-exit-bool":
        runtime["exit_code"] = False
    elif change in ("debug-enabled", "debug-zero"):
        evidence["debug"] = True if change == "debug-enabled" else 0
    elif change == "health-status":
        evidence["health_status"] = "200"
    elif change == "health-body":
        evidence["health_body"] = {"status": "not-ok"}
    elif change == "missing-version":
        del evidence["dependency_versions"]["fastapi"]
    elif change == "bad-version":
        evidence["dependency_versions"]["fastapi"] = "version\ntext"
    else:
        runtime["elapsed_ms"] = {
            "elapsed-bool": True,
            "elapsed-negative": -1,
            "elapsed-nan": math.nan,
            "elapsed-inf": math.inf,
        }[change]
    with pytest.raises(gate.SmokeError):
        gate.validate_summary(json.dumps(value), gate.expected_worker_hash(), posix=True)


@pytest.mark.parametrize("text", ["not JSON", "[]", '{"kind":1,"kind":2}', "{}\n{}", "x" * 16385])
def test_invalid_duplicate_multiple_or_oversized_json_is_rejected(text):
    with pytest.raises(gate.SmokeError):
        gate.validate_summary(text, gate.expected_worker_hash(), posix=True)


def test_windows_rejects_a_claimed_worker_execution():
    value = summary(posix=False)
    value["runtime"] = summary()["runtime"]
    with pytest.raises(gate.SmokeError, match="must not report"):
        gate.validate_summary(json.dumps(value), gate.expected_worker_hash(), posix=False)


def test_worker_identity_extraction_never_imports_core_or_runtime_dependencies(monkeypatch):
    original = builtins.__import__

    def reject(name, *args, **kwargs):
        assert name.split(".")[0] not in {"authzest", "fastapi", "starlette", "pydantic"}
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject)
    assert len(gate.expected_worker_hash()) == 64


def test_standalone_controller_help_runs_in_isolated_stdlib_only_python():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(gate.CHECKOUT / "scripts" / "smoke_fixture_runtime.py"),
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0 and result.stderr == ""
    assert "--artifact-dir" in result.stdout


def test_fixture_dependency_extra_and_fresh_artifact_publication_gate():
    project = tomllib.loads((gate.CHECKOUT / "pyproject.toml").read_text())
    assert project["project"]["optional-dependencies"]["fixture"] == ["fastapi>=0.115,<1.0"]
    assert not any(
        "httpx" in item for item in project["project"]["optional-dependencies"]["fixture"]
    )
    workflow = (gate.CHECKOUT / ".github" / "workflows" / "release.yml").read_text()
    fresh = workflow.split("  verify-artifacts:", 1)[1].split("  publish:", 1)[0]
    assert "python -I scripts/smoke_fixture_runtime.py --artifact-dir artifact" in fresh
    assert "pip install" not in fresh
    assert "needs: [validate, build, verify-artifacts]" in workflow
    assert "python scripts/smoke_release.py --binary dist/authzest" in workflow
    assert "python scripts/smoke_fixture_runtime.py --binary dist/authzest" in workflow
