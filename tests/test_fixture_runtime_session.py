"""Exact-plan runtime decisions on a fresh owned copy; no provider calls."""

import asyncio
import json
from dataclasses import replace
from hashlib import sha256

import pytest
from scripts.demo_proposal import build_demo_proposal

from authzest.codex.contracts import ContractError
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import fixture_runtime
from authzest.runner._fixture_workspace import WorkspaceError, supported
from authzest.runner.fixture_apply import FixtureApplySession


@pytest.fixture
def owned(tmp_path):
    if not supported():
        pytest.skip("POSIX fixture only")
    request, review, proposal = build_demo_proposal()
    clock = [10.0]
    session = FixtureApplySession(
        proposal, request, review, parent=tmp_path, clock=lambda: clock[0], runtime_check=True
    )
    session.decide("approve")
    assert session.apply().status == "applied"
    yield session, clock
    session.close()


def approve(session, choice="approve"):
    plan = session.verification_preview()
    session.decide_verification(choice, plan["plan_id"])
    return plan


def journal(session):
    return json.loads((session.workspace / "record.json").read_text())


@pytest.fixture
def outcome():
    return fixture_runtime.RuntimeOutcome(
        status="passed",
        reason="runtime-check-passed",
        check_id=fixture_runtime.CHECK_ID,
        source_sha256=sha256(FIXTURE_AFTER.encode()).hexdigest(),
        worker_sha256=fixture_runtime.WORKER_SHA256,
        elapsed_ms=1.0,
        exit_code=0,
        runtime_evidence={
            "debug": False,
            "health_status": 200,
            "health_body": {"status": "ok"},
            "dependency_versions": {
                "python": "3.12.0",
                "fastapi": "0.115.0",
                "starlette": "0.40.0",
                "pydantic": "2.10.0",
            },
        },
    )


@pytest.fixture
def checker(monkeypatch, outcome):
    calls = []

    async def check(source):
        calls.append(source)
        return outcome

    monkeypatch.setattr(fixture_runtime, "run_runtime_check", check)
    return calls


def test_plan_selection_is_not_permission_and_runtime_is_explicit(owned, checker):
    session, _ = owned
    plan = session.verification_preview()
    assert plan["kind"] == "fixture-runtime-verification-plan"
    assert plan["verification_scope"] == "owned-fixture-runtime"
    assert plan["runtime_verification_status"] == "not-run"
    assert plan["expected_checks"] == {
        "debug": False,
        "method": "GET",
        "path": "/health",
        "health_status": 200,
        "health_body": {"status": "ok"},
    }
    assert "site startup hooks" in plan["limitations"]
    assert plan["worker_sha256"] == sha256(plan["worker_source"].encode()).hexdigest()
    assert asyncio.run(session.verify())["reason"] == "pending"
    assert checker == []


def test_runtime_pass_and_restore_keep_historical_scope_and_evidence(owned, checker, outcome):
    session, _ = owned
    plan = approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] == result["runtime_verification_status"] == "passed"
    assert result["runtime_evidence"] == outcome.runtime_evidence
    assert result["plan_id"] == plan["plan_id"]
    assert checker == [FIXTURE_AFTER.encode()]
    assert journal(session)["verification_decision"]["purpose"] == (
        "owned-fixture-runtime-verification"
    )
    restored = session.restore("approve")
    assert restored.restored and restored.runtime_verification_status == "passed"
    data = journal(session)
    assert data["schema_version"] == "1.2"
    assert data["runtime_verification_status"] == "passed"
    assert data["verification"]["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
    assert (session.workspace / "main.py").read_bytes() == FIXTURE_SOURCE.encode()


@pytest.mark.parametrize("choice", ["decline", "cancel"])
def test_replaced_approval_refuses_runtime(owned, checker, choice):
    session, _ = owned
    approve(session)
    approve(session, choice)
    result = asyncio.run(session.verify())
    assert result["runtime_verification_status"] == "not-run"
    assert checker == []
    assert session.restore("approve").restored


@pytest.mark.parametrize("mutation", ["source", "inode", "mode", "plan", "expiry"])
def test_changed_runtime_preconditions_do_not_execute(owned, checker, monkeypatch, mutation):
    session, clock = owned
    approve(session)
    target = session.workspace / "main.py"
    if mutation == "source":
        target.write_text("# subsequent edit\n")
    elif mutation == "inode":
        other = session.workspace / "new-main"
        other.write_bytes(FIXTURE_AFTER.encode())
        other.chmod(0o600)
        other.replace(target)
    elif mutation == "mode":
        target.chmod(0o644)
    elif mutation == "plan":
        monkeypatch.setattr(fixture_runtime, "TIMEOUT_SECONDS", 4.0)
    else:
        clock[0] = 310.0
    result = asyncio.run(session.verify())
    assert result["status"] == result["runtime_verification_status"] == "not-run"
    assert checker == []


def test_static_plan_cannot_authorize_runtime(owned, checker):
    session, _ = owned
    session._runtime_check = False
    plan = approve(session)
    session._runtime_check = True
    assert session.verification_preview()["plan_id"] != plan["plan_id"]
    assert asyncio.run(session.verify())["reason"] == "precondition-failed"
    assert checker == []


def test_runtime_decision_is_consumed_once(owned, checker):
    session, _ = owned
    plan = approve(session)
    assert asyncio.run(session.verify())["status"] == "passed"
    assert asyncio.run(session.verify())["reason"] == "decision-consumed"
    with pytest.raises(WorkspaceError):
        session.decide_verification("approve", plan["plan_id"])
    assert len(checker) == 1
    assert journal(session)["runtime_verification_status"] == "passed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "unknown"),
        ("reason", "debug-disabled"),
        ("check_id", "wrong"),
        ("source_sha256", "0" * 64),
        ("worker_sha256", "0" * 64),
        ("elapsed_ms", float("nan")),
        ("exit_code", True),
        ("exit_code", 1),
        ("runtime_evidence", None),
        ("runtime_evidence", {"debug": False}),
    ],
)
def test_invalid_runtime_outcome_cannot_report_pass(owned, monkeypatch, outcome, field, value):
    session, _ = owned

    async def invalid(source):
        return replace(outcome, **{field: value})

    monkeypatch.setattr(fixture_runtime, "run_runtime_check", invalid)
    approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] == result["runtime_verification_status"] == "failed"
    assert result["runtime_evidence"] is None
    assert session.restore("approve").restored


@pytest.mark.parametrize(
    "event",
    [
        "verification-decision-recorded",
        "verification-intent",
        "verification-runtime-check-passed",
    ],
)
def test_journal_failure_never_records_runtime_pass(owned, checker, monkeypatch, event):
    session, _ = owned
    record = session._record

    def fail(value):
        if value == event:
            raise OSError("journal unavailable")
        record(value)

    monkeypatch.setattr(session, "_record", fail)
    if event == "verification-decision-recorded":
        with pytest.raises(OSError):
            approve(session)
    else:
        approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] != "passed"
    assert result["runtime_verification_status"] != "passed"
    assert session.restore("approve").restored


def test_runtime_cancellation_consumes_decision_and_preserves_restore(owned, monkeypatch):
    session, _ = owned

    async def cancel(source):
        assert session.restore("approve").status == "restoration-unavailable"
        raise asyncio.CancelledError

    monkeypatch.setattr(fixture_runtime, "run_runtime_check", cancel)
    approve(session)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(session.verify())
    data = journal(session)
    assert data["runtime_verification_status"] == "failed"
    assert data["verification"]["reason"] == "cancelled"
    assert data["verification_decision_consumed"] is True
    assert session.restore("approve").restored


def test_later_edit_during_runtime_does_not_get_restored_over(owned, monkeypatch, outcome):
    session, _ = owned

    async def changed(source):
        (session.workspace / "main.py").write_text("# later edit\n")
        return outcome

    monkeypatch.setattr(fixture_runtime, "run_runtime_check", changed)
    approve(session)
    result = asyncio.run(session.verify())
    assert result["runtime_verification_status"] == "failed"
    assert result["reason"] == "source-changed-during-check"
    assert not session.restore("approve").restored
    assert (session.workspace / "main.py").read_text() == "# later edit\n"


@pytest.mark.parametrize("value", [None, 1, "yes", [], {}])
def test_selector_is_validated_before_creating_files(tmp_path, value):
    request, review, proposal = build_demo_proposal()
    with pytest.raises(ContractError, match="boolean"):
        FixtureApplySession(proposal, request, review, parent=tmp_path, runtime_check=value)
    assert list(tmp_path.iterdir()) == []
