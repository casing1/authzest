import asyncio
import json
import math
from dataclasses import replace
from hashlib import sha256

import pytest
from scripts.demo_proposal import FIXTURE_ROOT, build_demo_proposal

from authzest.codex.contracts import ContractError
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import fixture_check
from authzest.runner._fixture_workspace import WorkspaceError, supported
from authzest.runner.fixture_apply import FixtureApplySession


@pytest.fixture
def owned(tmp_path):
    if not supported():
        pytest.skip("POSIX owned fixture only")
    request, review, proposal = build_demo_proposal()
    clock = [10.0]
    session = FixtureApplySession(
        proposal, request, review, parent=tmp_path, clock=lambda: clock[0]
    )
    session.decide("approve")
    assert session.apply().status == "applied"
    yield session, clock
    session.close()


@pytest.fixture
def checker(monkeypatch):
    calls = []

    async def check(source):
        calls.append(source)
        return fixture_check.VerificationOutcome(
            status="passed",
            reason="debug-disabled",
            check_id=fixture_check.CHECK_ID,
            source_sha256=sha256(source).hexdigest(),
            worker_sha256=fixture_check.WORKER_SHA256,
            elapsed_ms=1.0,
            exit_code=0,
        )

    monkeypatch.setattr(fixture_check, "run_configuration_check", check)
    return calls


def journal(session):
    return json.loads((session.workspace / "record.json").read_text())


def approve(session, **kwargs):
    plan = session.verification_preview()
    session.decide_verification("approve", plan["plan_id"], **kwargs)
    return plan


def test_preview_is_nonexecuting_complete_and_decision_is_separate(owned, checker):
    session, _ = owned
    plan = session.verification_preview()
    assert plan["source_text"] == FIXTURE_AFTER
    assert plan["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
    assert plan["worker_sha256"] == sha256(plan["worker_source"].encode()).hexdigest()
    assert plan["max_worker_attempts"] == 1
    assert plan["timeout_seconds"] == 5
    assert plan["max_output_bytes"] == 4096
    assert plan["verification_scope"] == "source-configuration"
    assert asyncio.run(session.verify())["reason"] == "pending"
    assert checker == []


def test_pass_records_checked_hash_then_restore_preserves_historical_result(owned, checker):
    session, _ = owned
    original = (FIXTURE_ROOT / "main.py").read_bytes()
    plan = approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] == "passed"
    assert result["runtime_verification_status"] == "not-run"
    assert result["plan_id"] == plan["plan_id"]
    assert checker == [FIXTURE_AFTER.encode()]
    data = journal(session)
    assert data["verification_plan"] == plan
    assert data["verification_decision"]["purpose"] == "source-configuration-verification"
    assert data["verification_decision_consumed"] is True
    assert session.restore("approve").verification_status == "passed"
    data = journal(session)
    assert data["phase"] == "restored"
    assert data["verification"]["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
    assert (session.workspace / "main.py").read_bytes() == FIXTURE_SOURCE.encode()
    assert (FIXTURE_ROOT / "main.py").read_bytes() == original


@pytest.mark.parametrize("choice,reason", [("decline", "declined"), ("cancel", "cancelled")])
def test_refusal_replaces_approval_and_does_not_start_worker(owned, checker, choice, reason):
    session, _ = owned
    plan = approve(session)
    session.decide_verification(choice, plan["plan_id"])
    result = asyncio.run(session.verify())
    assert result["status"] == "not-run" and result["reason"] == reason
    assert checker == []
    assert session.restore("approve").restored


def test_consumed_decision_cannot_run_or_be_replaced(owned, checker):
    session, _ = owned
    plan = approve(session)
    assert asyncio.run(session.verify())["status"] == "passed"
    assert asyncio.run(session.verify())["reason"] == "decision-consumed"
    with pytest.raises(WorkspaceError):
        session.decide_verification("approve", plan["plan_id"])
    assert checker == [FIXTURE_AFTER.encode()]
    assert journal(session)["verification_status"] == "passed"


@pytest.mark.parametrize("when", [9, 310, 311, math.inf, math.nan])
def test_expired_or_invalid_clock_cannot_launch(owned, checker, when):
    session, clock = owned
    approve(session)
    clock[0] = when
    result = asyncio.run(session.verify())
    assert result["status"] == "not-run"
    assert result["reason"] in {"expired", "precondition-failed"}
    assert checker == []


@pytest.mark.parametrize("duration", [0, -1, 301, True, None, math.nan, math.inf])
def test_invalid_decision_lifetime(owned, checker, duration):
    session, _ = owned
    with pytest.raises(ContractError):
        approve(session, valid_for_seconds=duration)
    assert asyncio.run(session.verify())["reason"] == "pending"
    assert checker == []


@pytest.mark.parametrize("choice", ["yes", "", None, True, []])
def test_invalid_verification_choice(owned, checker, choice):
    session, _ = owned
    plan = session.verification_preview()
    with pytest.raises(ContractError):
        session.decide_verification(choice, plan["plan_id"])
    assert checker == []


def test_wrong_plan_cannot_grant_approval(owned, checker):
    session, _ = owned
    with pytest.raises(ContractError):
        session.decide_verification("approve", "verification-" + "0" * 64)
    assert asyncio.run(session.verify())["reason"] == "pending"


@pytest.mark.parametrize("mutation", ["content", "inode", "mode", "missing", "symlink"])
def test_stale_current_file_never_starts_worker_or_overwrites_edits(owned, checker, mutation):
    session, _ = owned
    approve(session)
    target = session.workspace / "main.py"
    if mutation == "content":
        target.write_bytes(b"# later user edit\n")
    elif mutation == "inode":
        replacement = session.workspace / "new-main"
        replacement.write_bytes(FIXTURE_AFTER.encode())
        replacement.chmod(0o600)
        replacement.replace(target)
    elif mutation == "mode":
        target.chmod(0o644)
    else:
        target.unlink()
        if mutation == "symlink":
            target.symlink_to(FIXTURE_ROOT / "main.py")
    result = asyncio.run(session.verify())
    assert result["status"] == "not-run" and result["reason"] == "precondition-failed"
    assert checker == []
    assert not session.restore("approve").restored


@pytest.mark.parametrize("phase", ["before", "intent"])
def test_plan_change_invalidates_approval(owned, checker, monkeypatch, phase):
    session, _ = owned
    approve(session)
    record = session._record

    def change(event):
        record(event)
        if event == "verification-intent":
            monkeypatch.setattr(fixture_check, "TIMEOUT_SECONDS", 4.0)

    if phase == "before":
        monkeypatch.setattr(fixture_check, "TIMEOUT_SECONDS", 4.0)
    else:
        monkeypatch.setattr(session, "_record", change)
    assert asyncio.run(session.verify())["reason"] == "precondition-failed"
    assert checker == []


@pytest.mark.parametrize("phase", ["decision", "intent", "result"])
def test_journal_failure_does_not_report_pass(owned, checker, monkeypatch, phase):
    session, _ = owned
    record = session._record
    event_to_fail = {
        "decision": "verification-decision-recorded",
        "intent": "verification-intent",
        "result": "verification-debug-disabled",
    }[phase]

    def fail(event):
        if event == event_to_fail:
            raise OSError("injected journal failure")
        record(event)

    monkeypatch.setattr(session, "_record", fail)
    if phase == "decision":
        with pytest.raises(OSError):
            approve(session)
    else:
        approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] != "passed"
    assert len(checker) == (1 if phase == "result" else 0)
    assert session.restore("approve").restored


def test_change_during_worker_is_not_a_pass_and_is_not_restored_over(owned, monkeypatch):
    session, _ = owned
    real = fixture_check.run_configuration_check

    async def changed(source):
        result = await real(source)
        (session.workspace / "main.py").write_bytes(b"# later edit\n")
        return result

    monkeypatch.setattr(fixture_check, "run_configuration_check", changed)
    approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] == "failed" and result["reason"] == "source-changed-during-check"
    assert not session.restore("approve").restored
    assert (session.workspace / "main.py").read_bytes() == b"# later edit\n"


def test_restore_and_second_verification_are_blocked_while_checking(owned, checker, monkeypatch):
    session, _ = owned
    stub = fixture_check.run_configuration_check

    async def checking(source):
        assert session.restore("approve").status == "restoration-unavailable"
        assert (await session.verify())["reason"] == "decision-consumed"
        with pytest.raises(WorkspaceError):
            session.verification_preview()
        return await stub(source)

    monkeypatch.setattr(fixture_check, "run_configuration_check", checking)
    approve(session)
    assert asyncio.run(session.verify())["status"] == "passed"


def test_cancellation_is_recorded_and_consumed(owned, monkeypatch):
    session, _ = owned

    async def cancel(source):
        raise asyncio.CancelledError()

    monkeypatch.setattr(fixture_check, "run_configuration_check", cancel)
    approve(session)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(session.verify())
    assert journal(session)["verification"]["reason"] == "cancelled"
    assert journal(session)["verification_status"] == "failed"
    assert asyncio.run(session.verify())["reason"] == "decision-consumed"
    assert session.restore("approve").restored


def test_worker_exception_is_sanitized_and_restoration_remains_available(owned, monkeypatch):
    session, _ = owned

    async def fail(source):
        raise RuntimeError("sensitive exception should not be serialized")

    monkeypatch.setattr(fixture_check, "run_configuration_check", fail)
    approve(session)
    result = asyncio.run(session.verify())
    assert result["reason"] == "check-failed" and result["status"] == "failed"
    assert "sensitive" not in json.dumps(journal(session))
    assert session.restore("approve").restored


def test_wrong_worker_identity_is_not_a_pass(owned, checker, monkeypatch):
    session, _ = owned
    check = fixture_check.run_configuration_check

    async def wrong(source):
        return replace(await check(source), source_sha256="0" * 64)

    monkeypatch.setattr(fixture_check, "run_configuration_check", wrong)
    approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] == "failed" and result["reason"] == "invalid-check-result"


def test_verification_after_restoration_is_unavailable(owned, checker):
    session, _ = owned
    approve(session)
    assert session.restore("approve").restored
    assert asyncio.run(session.verify())["reason"] == "verification-unavailable"
    assert checker == []


@pytest.mark.parametrize("persistent", [False, True])
def test_post_commit_journal_error_attempts_failure_correction(
    owned, checker, monkeypatch, persistent
):
    session, _ = owned
    approve(session)
    write = session._workspace.write_record
    failures = []

    def committed(data):
        write(data)
        payload = json.loads(data)
        verification = payload.get("verification")
        if verification and (verification["status"] == "passed" or persistent):
            failures.append(True)
            raise OSError("injected failure after record replacement")

    monkeypatch.setattr(session._workspace, "write_record", committed)
    result = asyncio.run(session.verify())
    assert failures
    assert result["status"] == "failed" and result["reason"] == "journal-unavailable"
    assert result["journal_status"] == "unconfirmed"
    assert journal(session)["verification_status"] == "failed"
    assert journal(session)["verification"]["journal_status"] == "unconfirmed"


@pytest.mark.parametrize(
    "fields",
    [
        {"exit_code": 1},
        {"exit_code": False},
        {"reason": "unexpected"},
        {"elapsed_ms": -1},
        {"elapsed_ms": float("inf")},
        {"elapsed_ms": True},
    ],
)
def test_inconsistent_pass_result_is_rejected(owned, checker, monkeypatch, fields):
    session, _ = owned
    check = fixture_check.run_configuration_check

    async def invalid(source):
        return replace(await check(source), **fields)

    monkeypatch.setattr(fixture_check, "run_configuration_check", invalid)
    approve(session)
    result = asyncio.run(session.verify())
    assert result["status"] == "failed"
    assert result["reason"] in {"invalid-check-result", "check-failed"}
