import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from scripts.demo_proposal import FIXTURE_ROOT, run_demo

from authzest.codex.contracts import ContractError, canonical
from authzest.runner.approval import ProposalDecision, assess_decision, record_decision
from test_proposal_contract import AFTER, SOURCE, draft, make_context


@pytest.fixture
def prepared(tmp_path):
    request, review = make_context(tmp_path)
    return request, review, draft(request, review)


@pytest.mark.parametrize(
    "choice,reason,eligible",
    [("approve", "approved", True), ("decline", "declined", False), ("cancel", "cancelled", False)],
)
def test_explicit_decisions_are_not_application_or_execution(prepared, choice, reason, eligible):
    request, review, proposal = prepared
    current = {"main.py": SOURCE, "unselected.py": "leave user edits alone"}
    before = current.copy()
    decision = record_decision(proposal, request, review, choice, now=100)
    result = assess_decision(proposal, request, review, decision, current_sources=current, now=101)
    assert result.reason == reason and result.eligible is eligible
    assert result.applied is False and result.verification_status == "not-run"
    assert decision.to_dict()["purpose"] == "patch-application"
    assert current == before
    with pytest.raises(FrozenInstanceError):
        decision.payload_json = "{}"


def test_missing_decision_never_infers_approval(prepared):
    request, review, proposal = prepared
    result = assess_decision(
        proposal, request, review, None, current_sources={"main.py": SOURCE}, now=100
    )
    assert result.reason == "pending" and not result.eligible


@pytest.mark.parametrize(
    "now,reason",
    [
        (99, "clock-before-decision"),
        (100, "approved"),
        (399.999, "approved"),
        (400, "expired"),
        (401, "expired"),
    ],
)
def test_decision_lifetime_boundaries(prepared, now, reason):
    request, review, proposal = prepared
    decision = record_decision(proposal, request, review, "approve", now=100)
    result = assess_decision(
        proposal, request, review, decision, current_sources={"main.py": SOURCE}, now=now
    )
    assert result.reason == reason


@pytest.mark.parametrize(
    "current",
    [{}, {"main.py": SOURCE + "# user edit\n"}, {"main.py": None}, {"main.py": SOURCE.encode()}],
)
def test_changed_or_missing_source_needs_fresh_decision(prepared, current):
    request, review, proposal = prepared
    decision = record_decision(proposal, request, review, "approve", now=100)
    assert (
        assess_decision(
            proposal, request, review, decision, current_sources=current, now=101
        ).reason
        == "stale-source"
    )


def test_unchanged_target_does_not_hide_other_selected_edits(tmp_path):
    request, review = make_context(tmp_path, {"main.py": SOURCE, "helper.py": "VALUE = 1\n"})
    proposal = draft(request, review)
    decision = record_decision(proposal, request, review, "approve", now=100)
    current = {"main.py": SOURCE, "helper.py": "VALUE = 2\n"}
    assert (
        assess_decision(
            proposal, request, review, decision, current_sources=current, now=101
        ).reason
        == "stale-source"
    )


@pytest.mark.parametrize(
    "revision,expected",
    [(None, "stale-source"), ("b" * 40, "stale-source"), ("a" * 40, "approved")],
)
def test_caller_supplied_revision_is_rechecked(tmp_path, revision, expected):
    request, review = make_context(tmp_path, revision="a" * 40)
    proposal = draft(request, review)
    decision = record_decision(proposal, request, review, "approve", now=100)
    assert (
        assess_decision(
            proposal,
            request,
            review,
            decision,
            current_sources={"main.py": SOURCE},
            now=101,
            current_revision=revision,
        ).reason
        == expected
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"replacements": {"main.py": AFTER + "# changed draft\n"}},
        {"checks": ("fixture-regression-tests",)},
        {"expectations": ("Changed expected result.",)},
        {"side_effects": ("New side effect.",)},
        {"uncertainties": ("Different uncertainty.",)},
    ],
)
def test_changed_proposal_or_plan_invalidates_old_decision(prepared, overrides):
    request, review, proposal = prepared
    decision = record_decision(proposal, request, review, "approve", now=100)
    changed = draft(request, review, **overrides)
    result = assess_decision(
        changed, request, review, decision, current_sources={"main.py": SOURCE}, now=101
    )
    assert result.reason == "stale-proposal" and not result.eligible


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "2.0"),
        ("proposal_id", "unbound"),
        ("proposal_id", True),
        ("choice", "yes"),
        ("choice", True),
        ("purpose", "verification-execution"),
        ("purpose", "source-sharing"),
        ("created_at", True),
        ("created_at", -1),
        ("expires_at", 100),
        ("expires_at", 3701),
        ("extra", "command"),
    ],
)
def test_invalid_decision_schema_rejected(prepared, field, value):
    request, review, proposal = prepared
    data = record_decision(proposal, request, review, "approve", now=100).to_dict()
    data[field] = value
    with pytest.raises(ContractError):
        ProposalDecision(canonical(data))


@pytest.mark.parametrize("duration", [0, -1, True, 3601, float("nan"), float("inf")])
def test_invalid_decision_expiry(prepared, duration):
    request, review, proposal = prepared
    with pytest.raises(ContractError):
        record_decision(proposal, request, review, "approve", now=100, valid_for_seconds=duration)


@pytest.mark.parametrize("now", [-1, True, float("nan"), float("inf")])
def test_invalid_current_clock(prepared, now):
    request, review, proposal = prepared
    with pytest.raises(ContractError):
        assess_decision(
            proposal, request, review, None, current_sources={"main.py": SOURCE}, now=now
        )


def test_pure_checker_does_not_claim_replay_prevention(prepared):
    request, review, proposal = prepared
    decision = record_decision(proposal, request, review, "approve", now=100)
    first = assess_decision(
        proposal, request, review, decision, current_sources={"main.py": SOURCE}, now=101
    )
    second = assess_decision(
        proposal, request, review, decision, current_sources={"main.py": SOURCE}, now=101
    )
    assert first == second and not first.applied


def test_decision_checks_do_not_read_or_write_files(prepared, monkeypatch):
    request, review, proposal = prepared

    def forbidden(*a, **kw):
        pytest.fail("No filesystem access in decision contract")

    for method in ("read_text", "read_bytes", "write_text", "write_bytes", "open"):
        monkeypatch.setattr(Path, method, forbidden)
    decision = record_decision(proposal, request, review, "approve", now=100)
    assert assess_decision(
        proposal, request, review, decision, current_sources={"main.py": SOURCE}, now=101
    ).eligible


@pytest.mark.parametrize(
    "choice,scenario,expected",
    [
        ("approve", "current", "approved"),
        ("decline", "current", "declined"),
        ("cancel", "current", "cancelled"),
        ("approve", "expired", "expired"),
        ("approve", "stale-source", "stale-source"),
    ],
)
def test_owned_demo_is_offline_and_does_not_modify_source(monkeypatch, choice, scenario, expected):
    before = (FIXTURE_ROOT / "main.py").read_bytes()

    def forbidden(*a, **kw):
        pytest.fail("No network, process, or source write in demo")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    result = run_demo(choice, scenario)
    assert result["assessment"]["reason"] == expected
    assert result["assessment"]["applied"] is False
    assert result["assessment"]["verification_status"] == "not-run"
    assert result["simulated_decision"] is True and result["live_provider_calls"] == 0
    assert (FIXTURE_ROOT / "main.py").read_bytes() == before
    assert result["kind"] == "offline-proposal-demo"
    assert json.loads(json.dumps(result))["decision"]["choice"] == choice


def test_demo_defaults_to_decline():
    assert run_demo()["assessment"]["reason"] == "declined"


@pytest.mark.parametrize("args", [("unknown", "current"), ("approve", "unknown")])
def test_demo_invalid_choices(args):
    with pytest.raises(ValueError):
        run_demo(*args)
