import asyncio
import inspect
import json
import os
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest

from authzest.codex.fixture_draft import FIXTURE_AFTER
from authzest.runner import fixture_runtime, runtime_smoke


def passed_outcome():
    return fixture_runtime.RuntimeOutcome(
        "passed",
        "runtime-check-passed",
        fixture_runtime.CHECK_ID,
        sha256(FIXTURE_AFTER.encode()).hexdigest(),
        fixture_runtime.WORKER_SHA256,
        12.5,
        0,
        {
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
    )


def test_smoke_has_no_user_inputs_and_calls_only_the_fixed_after_worker(monkeypatch):
    called = []

    async def fixed(source):
        called.append(source)
        return passed_outcome()

    monkeypatch.setattr(runtime_smoke, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(fixture_runtime, "run_runtime_check", fixed)
    result = asyncio.run(runtime_smoke.run_runtime_smoke())
    assert inspect.signature(runtime_smoke.run_runtime_smoke).parameters == {}
    assert called == [FIXTURE_AFTER.encode()]
    assert result["status"] == result["runtime_verification_status"] == "passed"
    assert result["exit_code"] == 0
    assert result["verification_scope"] == "owned-fixture-runtime"
    assert result["runtime"]["source_sha256"] == result["source_sha256"]


def test_windows_returns_unsupported_without_calling_the_worker(monkeypatch):
    async def forbidden(source):
        pytest.fail("Unsupported platform must not start the runtime worker")

    monkeypatch.setattr(runtime_smoke, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(fixture_runtime, "run_runtime_check", forbidden)
    result = asyncio.run(runtime_smoke.run_runtime_smoke())
    assert (result["status"], result["exit_code"]) == ("unsupported", 2)
    assert result["runtime_verification_status"] == "not-run"
    assert result["runtime"] is None


def test_missing_runtime_dependency_is_not_a_passing_package_check(monkeypatch):
    async def unavailable(source):
        return replace(
            passed_outcome(),
            status="not-run",
            reason="runtime-dependency-unavailable",
            runtime_evidence=None,
        )

    monkeypatch.setattr(runtime_smoke, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(fixture_runtime, "run_runtime_check", unavailable)
    result = asyncio.run(runtime_smoke.run_runtime_smoke())
    assert (result["status"], result["reason"], result["exit_code"]) == (
        "failed",
        "runtime-dependency-unavailable",
        1,
    )
    assert result["runtime_verification_status"] == "not-run"
    assert result["runtime"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "failed"),
        ("reason", "debug-enabled"),
        ("source_sha256", "0" * 64),
        ("worker_sha256", "0" * 64),
        ("check_id", "different-check"),
        ("exit_code", False),
        ("exit_code", 1),
        ("elapsed_ms", True),
        ("elapsed_ms", -1),
        ("elapsed_ms", float("nan")),
        ("runtime_evidence", None),
    ],
)
def test_malformed_or_unconfirmed_outcomes_never_claim_pass(monkeypatch, field, value):
    async def malformed(source):
        return replace(passed_outcome(), **{field: value})

    monkeypatch.setattr(runtime_smoke, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(fixture_runtime, "run_runtime_check", malformed)
    result = asyncio.run(runtime_smoke.run_runtime_smoke())
    assert (result["status"], result["exit_code"], result["runtime"]) == ("failed", 1, None)
    assert "runtime_verification_status" not in result


def test_worker_exception_is_redacted_without_inventing_not_run(monkeypatch):
    async def broken(source):
        raise RuntimeError("untrusted secret exception detail")

    monkeypatch.setattr(runtime_smoke, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(fixture_runtime, "run_runtime_check", broken)
    result = asyncio.run(runtime_smoke.run_runtime_smoke())
    assert result["exit_code"] == 1
    assert "secret" not in json.dumps(result)
    assert "runtime_verification_status" not in result


@pytest.mark.skipif(os.name != "posix", reason="Runtime fixture feature is POSIX-only")
def test_real_source_parent_diagnostic_executes_only_the_maintained_runtime():
    result = asyncio.run(runtime_smoke.run_runtime_smoke())
    assert result["status"] == "passed"
    assert result["runtime"]["runtime_evidence"]["debug"] is False
    assert result["runtime"]["runtime_evidence"]["health_body"] == {"status": "ok"}
