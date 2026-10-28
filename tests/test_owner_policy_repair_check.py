"""Offline contracts and SCRIPTED transport results, never real policy observations.

No test here starts the new worker, evaluates either registered policy, contacts a
provider or grants user execution approval. Boolean outputs are test-owned data.
"""

import ast
import asyncio
import builtins
import copy
import socket
import subprocess
import sys
import tempfile
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.owner_policy_repair_pair import (
    OwnerPolicyRepairPair,
    build_owner_policy_repair_pair,
)
from authzest.runner import owner_policy_repair_check as check

# Scripted mock data only: these are NOT observations of either policy candidate.
SCRIPTED_MATCHES = (True, False, False, False, False, False, False, False)
SCRIPTED_MISMATCHES = (True, True, False, False, False, False, False, True)


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline tests must not execute a policy, process, provider or filesystem I/O")

    async def forbidden_worker(*args, **kwargs):
        forbidden()

    original_import = builtins.__import__
    original_compile = builtins.compile

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn", "openai"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    def guarded_compile(source, filename, mode, flags=0, *args, **kwargs):
        # Pytest's failure renderer parses its own traceback source through ast;
        # permit only that non-executing diagnostic path, never target compilation.
        if (
            flags & ast.PyCF_ONLY_AST
            and sys._getframe(1).f_globals.get("__name__") == "ast"
            and sys._getframe(2).f_globals.get("__name__") in {"_pytest._code.source", "traceback"}
        ):
            return original_compile(source, filename, mode, flags, *args, **kwargs)
        forbidden()

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(builtins, "compile", guarded_compile)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(check, "_run_worker", forbidden_worker)


def _scripted_output(worker_input, observations=SCRIPTED_MATCHES):
    output = copy.deepcopy(worker_input)
    output["cases"] = [
        {"case_id": row["case_id"], "input_sha256": row["input_sha256"], "observed": value}
        for row, value in zip(output["cases"], observations, strict=True)
    ]
    return output


def _mock_worker(monkeypatch, *, observations=SCRIPTED_MATCHES, mutate=None, **diagnostics):
    calls = []

    async def scripted(plan):
        calls.append(plan)
        output = _scripted_output(plan, observations)
        if mutate is not None:
            output = mutate(output)
        raw = output if isinstance(output, bytes) else canonical(output).encode("utf-8")
        return check.WorkerTransport(
            **{
                "output": raw,
                "exit_code": 0,
                "reason": None,
                "child_cleanup_status": "confirmed",
                "workspace_cleanup_status": "confirmed",
                "launch_status": "started",
                **diagnostics,
            }
        )

    monkeypatch.setattr(check, "_run_worker", scripted)
    return calls


def _approved_session(candidate="before", *, clock=lambda: 100.0):
    session = check.OwnerPolicyRepairCheckSession(candidate, clock=clock)
    session.decide("approved", plan_id=session.plan.check_plan_id)
    return session


def _assert_unknown(data):
    assert data["status"] == "not-run"
    assert data["comparison_status"] == "not-evaluated"
    assert data["authorization_status"] == "unknown"
    assert data["provider_calls"] == 0
    assert data["patch_application"] == data["restoration_status"] == "not-run"
    assert len(data["cases"]) == 8
    assert all(row["observed"] is None and row["result"] == "unknown" for row in data["cases"])


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_plan_is_immutable_complete_offline_data_not_execution_authority(candidate):
    plan = check.prepare_owner_policy_repair_check(candidate)
    data = plan.to_dict()
    pair = build_owner_policy_repair_pair()
    content = pair.to_dict()["content"]
    assert set(data) == {
        "schema_version",
        "kind",
        "check_plan_id",
        "candidate",
        "bindings",
        "worker_input",
        "planning_status",
        "requires_separate_execution_approval",
        "execution_status",
        "authorization_status",
        "provider_calls",
        "patch_application",
        "restoration_status",
    }
    assert data["candidate"] == candidate
    assert data["bindings"]["pair"] == pair.to_dict()
    assert data["bindings"]["pair_id"] == pair.pair_id
    assert data["bindings"]["source"] == content[candidate]
    assert data["bindings"]["cases"] == content["cases"]
    assert (
        data["bindings"]["worker_sha256"]
        == sha256(data["bindings"]["worker_source"].encode()).hexdigest()
    )
    assert data["bindings"]["recipe_sha256"] == identity(data["bindings"]["recipe"])
    assert data["requires_separate_execution_approval"] is True
    assert data["execution_status"] == data["patch_application"] == "not-run"
    assert data["restoration_status"] == "not-run"
    assert data["authorization_status"] == "unknown" and data["provider_calls"] == 0
    assert check.validate_owner_policy_repair_check_plan(plan.payload_json) == plan
    with pytest.raises(FrozenInstanceError):
        plan.payload_json = "{}"
    data["worker_input"]["cases"][0]["principal"]["subject"] = "changed-copy"
    assert data != plan.to_dict()


def test_candidates_bind_different_sources_and_plans_but_same_eight_exact_inputs():
    before = check.prepare_owner_policy_repair_check("before")
    after = check.prepare_owner_policy_repair_check("after")
    assert before.check_plan_id != after.check_plan_id
    before_wire, after_wire = [plan.to_dict()["worker_input"] for plan in (before, after)]
    assert before_wire["policy_source_sha256"] != after_wire["policy_source_sha256"]
    assert before_wire["cases"] == after_wire["cases"]
    for plan, wire in ((before, before_wire), (after, after_wire)):
        assert wire["plan_id"] == plan.check_plan_id
        assert wire["input_sha256"] == identity(wire["cases"])
        assert set(wire) == {
            "schema_version",
            "check_id",
            "plan_id",
            "candidate",
            "policy_source_sha256",
            "worker_sha256",
            "input_sha256",
            "cases",
        }
        for row in wire["cases"]:
            assert set(row) == {"case_id", "input_sha256", "principal", "report"}
            assert row["input_sha256"] == identity(
                {key: row[key] for key in ("case_id", "principal", "report")}
            )
        assert wire["cases"][-1]["principal"]["subject"] == " alice"


@pytest.mark.parametrize("candidate", [None, True, "", "both", "BEFORE", "policy.py", [], {}])
def test_no_implicit_candidate_path_or_combined_run(candidate):
    with pytest.raises(ContractError):
        check.prepare_owner_policy_repair_check(candidate)
    with pytest.raises(ContractError):
        check.OwnerPolicyRepairCheckSession(candidate)


@pytest.mark.parametrize(
    "change", ["extra", "missing", "candidate", "source", "label", "worker", "recipe", "wire"]
)
def test_imported_plan_requires_exact_current_rebuild_not_self_consistent_caller_data(change):
    data = check.prepare_owner_policy_repair_check("before").to_dict()
    if change == "extra":
        data["approved"] = True
    elif change == "missing":
        del data["authorization_status"]
    elif change == "candidate":
        data["candidate"] = "after"
    elif change == "source":
        data["bindings"]["source"]["text"] += "\n# Caller-controlled text\n"
        data["bindings"]["source"]["sha256"] = sha256(
            data["bindings"]["source"]["text"].encode()
        ).hexdigest()
    elif change == "label":
        data["bindings"]["cases"][1]["expected"] = "allow"
    elif change == "worker":
        data["bindings"]["worker_source"] += "\n# Changed worker\n"
        data["bindings"]["worker_sha256"] = sha256(
            data["bindings"]["worker_source"].encode()
        ).hexdigest()
    elif change == "recipe":
        data["bindings"]["recipe"]["version"] = "caller-version"
        data["bindings"]["recipe_sha256"] = identity(data["bindings"]["recipe"])
    else:
        data["worker_input"]["cases"][0]["principal"]["subject"] = "other"
    # Rehashing caller-owned bindings cannot turn altered data into the current
    # registration or into an executable/approved plan.
    prefix = data["check_plan_id"].rsplit("-", 1)[0] + "-"
    data["check_plan_id"] = prefix + identity(data["bindings"])
    data["worker_input"]["plan_id"] = data["check_plan_id"]
    with pytest.raises(ContractError):
        check.validate_owner_policy_repair_check_plan(canonical(data))


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_scripted_matches_have_complete_bound_results_and_do_not_claim_authorization(
    monkeypatch, candidate
):
    calls = _mock_worker(monkeypatch)
    session = _approved_session(candidate)
    result = asyncio.run(session.run())
    data = result.to_dict()
    assert len(calls) == 1 and calls[0] == session.plan.to_dict()["worker_input"]
    assert data["kind"] == "owner-policy-repair-check-result"
    assert data["check_plan"] == session.plan.to_dict()
    assert data["check_plan_id"] == session.plan.check_plan_id
    assert data["candidate"] == candidate
    assert data["status"] == data["comparison_status"] == "passed"
    assert data["execution_status"] == "completed"
    assert data["cleanup_status"] == "confirmed"
    assert data["child_cleanup_status"] == data["workspace_cleanup_status"] == "confirmed"
    assert data["authorization_status"] == "unknown" and data["provider_calls"] == 0
    assert data["patch_application"] == data["restoration_status"] == "not-run"
    assert all(row["result"] == "passed" for row in data["cases"])
    assert [row["observed"] for row in data["cases"]] == list(SCRIPTED_MATCHES)
    assert [row["expected"] for row in data["cases"]] == ["allow"] + ["deny"] * 7
    assert session.last_result is result
    assert check.validate_owner_policy_repair_check_result(result.payload_json) == result


def test_scripted_mismatches_are_failed_comparison_not_worker_failure(monkeypatch):
    _mock_worker(monkeypatch, observations=SCRIPTED_MISMATCHES)
    data = asyncio.run(_approved_session().run()).to_dict()
    assert data["status"] == data["comparison_status"] == "failed"
    assert data["execution_status"] == "completed" and data["exit_code"] == 0
    assert [row["case_id"] for row in data["cases"] if row["result"] == "failed"] == [
        "non-owner",
        "exact-owner-no-normalization",
    ]
    assert data["authorization_status"] == "unknown"


@pytest.mark.parametrize("choice", [None, "pending", "declined", "cancelled"])
def test_nonapproval_never_launches_and_consumes_attempt(monkeypatch, choice):
    calls = _mock_worker(monkeypatch)
    session = check.OwnerPolicyRepairCheckSession("before", clock=lambda: 100.0)
    if choice is not None:
        session.decide(choice, plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    _assert_unknown(asyncio.run(session.run()).to_dict())
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    assert calls == []


@pytest.mark.parametrize("choice", ["approved", "declined", "cancelled"])
def test_terminal_decision_replacement_irreversibly_invalidates_session(monkeypatch, choice):
    calls = _mock_worker(monkeypatch)
    session = check.OwnerPolicyRepairCheckSession("before", clock=lambda: 100.0)
    session.decide(choice, plan_id=session.plan.check_plan_id)
    for _ in range(2):
        with pytest.raises(ContractError):
            session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


def test_only_current_pending_decision_can_be_replaced_once(monkeypatch):
    calls = _mock_worker(monkeypatch)
    ticks = [100.0]
    session = check.OwnerPolicyRepairCheckSession("after", clock=lambda: ticks[0])
    session.decide("pending", plan_id=session.plan.check_plan_id)
    ticks[0] += 1
    session.decide("approved", plan_id=session.plan.check_plan_id)
    assert asyncio.run(session.run()).to_dict()["status"] == "passed"
    assert len(calls) == 1


@pytest.mark.parametrize("choice", ["pending", "approved"])
def test_expired_decision_cannot_be_renewed_or_revived_by_clock_rollback(monkeypatch, choice):
    calls = _mock_worker(monkeypatch)
    ticks = [100.0]
    session = check.OwnerPolicyRepairCheckSession("before", clock=lambda: ticks[0])
    session.decide(choice, plan_id=session.plan.check_plan_id, lifetime_seconds=300)
    ticks[0] = 400.0
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    ticks[0] = 101.0
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("choice", "approve"),
        ("choice", True),
        ("choice", []),
        ("plan_id", "other-plan"),
        ("plan_id", True),
        ("lifetime_seconds", 0),
        ("lifetime_seconds", -1),
        ("lifetime_seconds", 300.1),
        ("lifetime_seconds", True),
        ("lifetime_seconds", "300"),
        ("lifetime_seconds", float("inf")),
        ("lifetime_seconds", float("nan")),
        ("lifetime_seconds", 10**1000),
    ],
)
def test_invalid_first_decision_is_terminal_without_type_coercion(monkeypatch, field, value):
    calls = _mock_worker(monkeypatch)
    session = check.OwnerPolicyRepairCheckSession("before", clock=lambda: 100.0)
    args = {"choice": "approved", "plan_id": session.plan.check_plan_id, "lifetime_seconds": 300}
    args[field] = value
    with pytest.raises(ContractError):
        session.decide(**args)
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


@pytest.mark.parametrize("value", [-1, True, "100", None, float("inf"), float("nan"), 10**1000])
def test_invalid_initial_clock_is_rejected(value):
    with pytest.raises(ContractError):
        check.OwnerPolicyRepairCheckSession("before", clock=lambda: value)


@pytest.mark.parametrize("now", [99.0, True, float("nan"), float("inf")])
def test_invalid_decision_time_permanently_invalidates_session(monkeypatch, now):
    calls = _mock_worker(monkeypatch)
    ticks = [100.0]
    session = check.OwnerPolicyRepairCheckSession("before", clock=lambda: ticks[0])
    ticks[0] = now
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    ticks[0] = 101.0
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


@pytest.mark.parametrize("now", [99.0, 400.0, True, float("nan"), float("inf")])
def test_invalid_expired_or_rollback_run_clock_consumes_without_launch(monkeypatch, now):
    calls = _mock_worker(monkeypatch)
    ticks = [100.0]
    session = _approved_session(clock=lambda: ticks[0])
    ticks[0] = now
    _assert_unknown(asyncio.run(session.run()).to_dict())
    ticks[0] = 101.0
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


def test_before_decision_cannot_authorize_after_session():
    before = check.OwnerPolicyRepairCheckSession("before", clock=lambda: 100.0)
    after = check.OwnerPolicyRepairCheckSession("after", clock=lambda: 100.0)
    with pytest.raises(ContractError):
        after.decide("approved", plan_id=before.plan.check_plan_id)
    _assert_unknown(asyncio.run(after.run()).to_dict())


@pytest.mark.parametrize("platform", ["windows", "frozen"])
def test_unsupported_source_platform_never_launches(monkeypatch, platform):
    calls = _mock_worker(monkeypatch)
    session = _approved_session()
    if platform == "windows":
        monkeypatch.setattr(check, "os", SimpleNamespace(name="nt"))
    else:
        monkeypatch.setattr(check, "sys", SimpleNamespace(frozen=True))
    data = asyncio.run(session.run()).to_dict()
    _assert_unknown(data)
    assert data["reason"] == "unsupported-platform" and calls == []


@pytest.mark.parametrize("change", ["worker-source", "worker-hash", "recipe"])
def test_current_worker_or_recipe_drift_invalidates_prepared_plan(monkeypatch, change):
    calls = _mock_worker(monkeypatch)
    session = _approved_session()
    if change == "worker-source":
        monkeypatch.setattr(check, "WORKER_SOURCE", check.WORKER_SOURCE + "\n# changed\n")
    elif change == "worker-hash":
        monkeypatch.setattr(check, "WORKER_SHA256", "0" * 64)
    else:
        original = check._recipe

        def changed_recipe():
            recipe = original()
            recipe["version"] = "changed"
            return recipe

        monkeypatch.setattr(check, "_recipe", changed_recipe)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


@pytest.mark.parametrize("change", ["source", "label", "review"])
def test_current_registration_drift_is_revalidated_before_transport(monkeypatch, change):
    calls = _mock_worker(monkeypatch)
    session = _approved_session()
    payload = build_owner_policy_repair_pair().to_dict()
    if change == "source":
        payload["content"]["before"]["text"] += "\n# changed policy\n"
        payload["content"]["before"]["sha256"] = sha256(
            payload["content"]["before"]["text"].encode()
        ).hexdigest()
    elif change == "label":
        payload["content"]["cases"][1]["expected"] = "allow"
    else:
        payload["review_binding"]["unexpected"] = "changed review"
    changed = OwnerPolicyRepairPair(canonical(payload))
    monkeypatch.setattr(check, "build_owner_policy_repair_pair", lambda: changed)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert calls == []


def test_concurrent_and_repeated_calls_share_only_one_attempt(monkeypatch):
    calls = []

    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()

        async def scripted(plan):
            calls.append(plan)
            entered.set()
            await release.wait()
            return check.WorkerTransport(
                output=canonical(_scripted_output(plan)).encode(),
                exit_code=0,
                reason=None,
                child_cleanup_status="confirmed",
                workspace_cleanup_status="confirmed",
                launch_status="started",
            )

        monkeypatch.setattr(check, "_run_worker", scripted)
        session = _approved_session()
        first = asyncio.create_task(session.run())
        await entered.wait()
        _assert_unknown((await session.run()).to_dict())
        release.set()
        result = await first
        assert result.to_dict()["status"] == "passed"
        _assert_unknown((await session.run()).to_dict())
        assert session.last_result is result

    asyncio.run(scenario())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        "schema_version",
        "check_id",
        "plan_id",
        "candidate",
        "policy_source_sha256",
        "worker_sha256",
        "input_sha256",
        "extra",
        "case-id",
        "case-hash",
        "case-extra",
        "order",
        "missing",
        "duplicate",
        "integer",
        "null",
        "text",
        "bad-json",
        "duplicate-json-keys",
        "invalid-utf8",
        "nonfinite",
        "trailing",
        "oversize",
    ],
)
def test_unbound_or_malformed_output_never_fabricates_denials(monkeypatch, change):
    def mutate(output):
        if change in output and change != "cases":
            output[change] = "forged"
        elif change == "extra":
            output["stderr"] = "untrusted worker text"
        elif change == "case-id":
            output["cases"][0]["case_id"] += "-changed"
        elif change == "case-hash":
            output["cases"][0]["input_sha256"] = "0" * 64
        elif change == "case-extra":
            output["cases"][0]["reason"] = "untrusted worker text"
        elif change == "order":
            output["cases"].reverse()
        elif change == "missing":
            output["cases"].pop()
        elif change == "duplicate":
            output["cases"][1] = copy.deepcopy(output["cases"][0])
        elif change in {"integer", "null", "text"}:
            output["cases"][0]["observed"] = {"integer": 1, "null": None, "text": "false"}[change]
        else:
            return {
                "bad-json": b"{broken",
                "duplicate-json-keys": b'{"x":1,"x":1}',
                "invalid-utf8": b"\xff",
                "nonfinite": b'{"cases":NaN}',
                "trailing": canonical(output).encode() + b"\n{}",
                "oversize": b" " * (16 * 1024 + 1),
            }[change]
        return output

    calls = _mock_worker(monkeypatch, mutate=mutate)
    data = asyncio.run(_approved_session().run()).to_dict()
    _assert_unknown(data)
    assert data["execution_status"] == "attempted"
    assert data["reason"] == "invalid-worker-output"
    assert len(calls) == 1
    assert "untrusted worker text" not in canonical(data)


@pytest.mark.parametrize(
    "diagnostics",
    [
        {"reason": "timeout"},
        {"reason": "output-limit"},
        {"exit_code": 2},
        {"child_cleanup_status": "unconfirmed"},
        {"workspace_cleanup_status": "unconfirmed"},
        {"reason": "sensitive exception text"},
    ],
)
def test_unsuccessful_transport_discards_even_complete_scripted_stdout(monkeypatch, diagnostics):
    calls = _mock_worker(monkeypatch, **diagnostics)
    data = asyncio.run(_approved_session().run()).to_dict()
    _assert_unknown(data)
    assert data["execution_status"] == "attempted" and len(calls) == 1
    assert "sensitive exception text" not in canonical(data)
    if "unconfirmed" in diagnostics.values():
        assert data["cleanup_status"] == "unconfirmed"


@pytest.mark.parametrize(
    ("launch", "child", "workspace", "cleanup", "execution"),
    [
        ("no-child", "not-needed", "confirmed", "confirmed", "not-run"),
        ("no-child", "not-needed", "unconfirmed", "unconfirmed", "not-run"),
        ("not-attempted", "not-needed", "not-needed", "not-needed", "not-run"),
        ("not-attempted", "not-needed", "unconfirmed", "unconfirmed", "not-run"),
        ("ambiguous", "unconfirmed", "confirmed", "unconfirmed", "attempted"),
    ],
)
def test_launch_and_workspace_cleanup_are_recorded_separately(
    monkeypatch, launch, child, workspace, cleanup, execution
):
    _mock_worker(
        monkeypatch,
        output=b"",
        exit_code=None,
        reason="worker-process-error",
        launch_status=launch,
        child_cleanup_status=child,
        workspace_cleanup_status=workspace,
    )
    result = asyncio.run(_approved_session().run())
    data = result.to_dict()
    _assert_unknown(data)
    assert data["launch_status"] == launch
    assert data["child_cleanup_status"] == child
    assert data["workspace_cleanup_status"] == workspace
    assert data["cleanup_status"] == cleanup
    assert data["execution_status"] == execution
    assert check.validate_owner_policy_repair_check_result(result.payload_json) == result


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "candidate",
        "plan-id",
        "case-id",
        "label",
        "integer",
        "partial",
        "result",
        "comparison",
        "authorization",
        "provider",
        "patch",
        "cleanup",
        "provenance",
    ],
)
def test_imported_result_is_closed_revalidated_data_never_authenticated_execution(
    monkeypatch, change
):
    _mock_worker(monkeypatch)
    data = asyncio.run(_approved_session().run()).to_dict()
    if change == "extra":
        data["approved"] = True
    elif change == "candidate":
        data["candidate"] = "after"
    elif change == "plan-id":
        data["check_plan_id"] += "x"
    elif change == "case-id":
        data["cases"][0]["case_id"] += "x"
    elif change == "label":
        data["cases"][0]["expected"] = "deny"
    elif change == "integer":
        data["cases"][0]["observed"] = 1
    elif change == "partial":
        data["cases"][0]["observed"] = None
    elif change == "result":
        data["cases"][0]["result"] = "failed"
    elif change == "comparison":
        data["comparison_status"] = "failed"
    elif change == "authorization":
        data["authorization_status"] = "protected"
    elif change == "provider":
        data["provider_calls"] = False
    elif change == "patch":
        data["patch_application"] = "applied"
    elif change == "cleanup":
        data["workspace_cleanup_status"] = "unconfirmed"
    else:
        data["provenance"]["authenticated"] = True
    with pytest.raises(ContractError):
        check.validate_owner_policy_repair_check_result(canonical(data))


def _scripted_unobserved_record(reason, launch, child, workspace, exit_code):
    """Build caller-owned diagnostics, never observations or an execution receipt."""
    session = check.OwnerPolicyRepairCheckSession("before", clock=lambda: 100.0)
    data = asyncio.run(session.run()).to_dict()  # No decision: transport is forbidden.
    cleanup = {child, workspace}
    data.update(
        reason=reason,
        launch_status=launch,
        child_cleanup_status=child,
        workspace_cleanup_status=workspace,
        cleanup_status="unconfirmed"
        if "unconfirmed" in cleanup
        else ("not-needed" if cleanup == {"not-needed"} else "confirmed"),
        exit_code=exit_code,
        execution_status="attempted" if launch in {"started", "ambiguous"} else "not-run",
    )
    return data


@pytest.mark.parametrize(
    ("reason", "launch", "child", "workspace", "exit_code"),
    [
        ("unsupported-platform", "started", "confirmed", "confirmed", 0),
        ("execution-decision-pending", "no-child", "not-needed", "confirmed", None),
        ("stale-plan", "not-attempted", "not-needed", "confirmed", None),
        ("invalid-decision-time", "ambiguous", "unconfirmed", "confirmed", None),
        ("worker-input-error", "started", "confirmed", "confirmed", 0),
        ("worker-input-error", "not-attempted", "not-needed", "confirmed", None),
        ("cleanup-unconfirmed", "started", "confirmed", "confirmed", 0),
        ("cleanup-unconfirmed", "not-attempted", "not-needed", "not-needed", None),
        ("invalid-worker-output", "started", "confirmed", "confirmed", 2),
        ("invalid-worker-output", "no-child", "not-needed", "confirmed", None),
        ("worker-exit-error", "started", "confirmed", "confirmed", 0),
        ("worker-exit-error", "not-attempted", "not-needed", "not-needed", None),
        ("output-limit", "not-attempted", "not-needed", "not-needed", None),
        ("output-limit", "no-child", "not-needed", "confirmed", None),
        ("timeout", "not-attempted", "not-needed", "confirmed", None),
        ("worker-process-error", "started", "confirmed", "confirmed", None),
        ("cancelled", "started", "confirmed", "confirmed", None),
        ("cancelled", "ambiguous", "unconfirmed", "not-needed", None),
        ("cancelled", "no-child", "not-needed", "not-needed", None),
    ],
)
def test_imported_result_rejects_impossible_reason_and_resource_combinations(
    reason, launch, child, workspace, exit_code
):
    data = _scripted_unobserved_record(reason, launch, child, workspace, exit_code)
    with pytest.raises(ContractError):
        check.validate_owner_policy_repair_check_result(canonical(data))


@pytest.mark.parametrize(
    ("reason", "launch", "child", "workspace", "exit_code"),
    [
        ("worker-input-error", "not-attempted", "not-needed", "not-needed", None),
        # Launch may fail while cleanup waits after a timeout; no child is then known.
        ("timeout", "no-child", "not-needed", "confirmed", None),
        # A catch-all transport exception cannot establish resource cleanup.
        ("worker-process-error", "ambiguous", "unconfirmed", "unconfirmed", None),
        ("cancelled", "started", "confirmed", "confirmed", 0),
        ("cancelled", "not-attempted", "not-needed", "unconfirmed", None),
        # Overflow is independent of whether the child has already exited zero.
        ("output-limit", "started", "confirmed", "confirmed", 0),
        ("worker-exit-error", "started", "confirmed", "confirmed", -9),
    ],
)
def test_import_validation_preserves_possible_failure_diagnostics_without_attestation(
    reason, launch, child, workspace, exit_code
):
    data = _scripted_unobserved_record(reason, launch, child, workspace, exit_code)
    validated = check.validate_owner_policy_repair_check_result(canonical(data)).to_dict()
    assert validated == data
    assert validated["provenance"]["authenticated"] is False
    _assert_unknown(validated)


@pytest.mark.parametrize("reason", ["worker-input-error", "worker-exit-error"])
def test_contradictory_transport_diagnostics_are_discarded_without_observations(
    monkeypatch, reason
):
    # A child cannot report pre-launch input refusal or an exit error with exit 0.
    calls = _mock_worker(monkeypatch, reason=reason, exit_code=0)
    result = asyncio.run(_approved_session().run())
    data = result.to_dict()
    _assert_unknown(data)
    assert len(calls) == 1
    assert data["reason"] == "invalid-worker-transport"
    assert data["launch_status"] == "ambiguous"
    assert data["cleanup_status"] == "unconfirmed"
    assert data["exit_code"] is None
    assert check.validate_owner_policy_repair_check_result(result.payload_json) == result


def test_transport_exception_never_leaks_raw_text_or_retries(monkeypatch):
    calls = []

    async def scripted(plan):
        calls.append(plan)
        raise OSError("PRIVATE-EXCEPTION-DETAIL")

    monkeypatch.setattr(check, "_run_worker", scripted)
    session = _approved_session()
    data = asyncio.run(session.run()).to_dict()
    _assert_unknown(data)
    assert "PRIVATE-EXCEPTION-DETAIL" not in canonical(data)
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert len(calls) == 1


def test_cancellation_is_preserved_with_unknown_last_result_and_no_reuse(monkeypatch):
    calls = []

    async def scripted(plan):
        calls.append(plan)
        raise asyncio.CancelledError("original scripted cancellation")

    monkeypatch.setattr(check, "_run_worker", scripted)
    session = _approved_session()
    with pytest.raises(asyncio.CancelledError, match="original scripted cancellation"):
        asyncio.run(session.run())
    _assert_unknown(session.last_result.to_dict())
    _assert_unknown(asyncio.run(session.run()).to_dict())
    assert len(calls) == 1
