"""Offline/mock transport tests: no policy, worker, subprocess, provider or network runs.

All observations and review choices below are test-owned scripted data. They are not
maintainer approval, a live model answer, or an execution/security-pass receipt.
"""

import asyncio
import builtins
import copy
import json
import socket
import subprocess
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex import owner_case_plan as preview
from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    canonical,
    decode,
    identity,
)
from authzest.codex.mock import scripted_response
from authzest.codex.owner_policy_review import (
    OwnerPolicyReview,
    build_owner_policy_request,
    validate_owner_policy_draft,
)
from authzest.runner import owner_policy_check as check

REFERENCE = Path(__file__).parent / "fixtures/owner_case_review/proposed_review.json"


@pytest.fixture
def context(monkeypatch):
    # Read the preserved public envelope before forbidding all target-related I/O.
    original = json.loads(REFERENCE.read_text(encoding="utf-8"))
    request = build_owner_policy_request(original["origin"]["identity"]["model"])
    answers = decode(scripted_response(request, {"review": None}))["answers"]
    for answer in answers:
        answer["evidence_ids"] = [item["id"] for item in request.to_dict()["evidence"]]
    draft = validate_owner_policy_draft(
        canonical({"answers": answers, "cases": original["cases"]}), request, usage=None
    )

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Offline/mock checks must not execute a target or perform filesystem/network I/O"
        )

    original_import = builtins.__import__

    def imports(name, *args, **kwargs):
        if name.split(".")[0] in {"examples", "fastapi", "uvicorn"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(check, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    case_set = preview.prepare_owner_case_set(
        draft, request, origin={key: original["origin"][key] for key in ("code_head", "date")}
    )
    return original, request, draft, case_set


def _context(context, state="approved", *, changed_first=False, reviewer="offline-test"):
    original, request, draft, case_set = context
    choices = {
        case["id"]: {
            "decision": state,
            "expected": case["expected"] if state == "approved" else None,
            "reason": None if state == "pending" else "Test-owned choice; not user approval",
        }
        for case in original["cases"]
    }
    if changed_first:
        first = original["cases"][0]
        choices[first["id"]].update(decision="changed", expected=not first["expected"])
    labels = preview.review_owner_cases(
        case_set, draft, request, decisions=choices, reviewer=reviewer
    )
    offline_plan = preview.prepare_owner_policy_plan(labels, case_set, draft, request)
    return offline_plan, labels, case_set, draft, request


def _output(plan, observed):
    value = copy.deepcopy(plan.to_dict()["worker_input"])
    value["cases"] = [
        {"id": row["id"], "case_sha256": row["case_sha256"], "observed": observed[row["id"]]}
        for row in value["cases"]
    ]
    return value


def _scripted_observations(context):
    # Explicit fixture data, never an evaluation of the registered pure policy.
    return {case["id"]: case["expected"] for case in context[0]["cases"]}


def _mock_worker(
    monkeypatch, context, *, mutate=None, reason=None, exit_code=0, cleanup="confirmed"
):
    calls = []

    async def scripted(plan):
        calls.append(plan)
        output = _output(plan, _scripted_observations(context))
        if mutate is not None:
            output = mutate(output)
        raw = output if isinstance(output, bytes) else canonical(output).encode("utf-8")
        return check.WorkerTransport(
            output=raw, exit_code=exit_code, reason=reason, cleanup_status=cleanup
        )

    monkeypatch.setattr(check, "_run_worker", scripted)
    return calls


def _approved_session(args, *, clock=lambda: 100.0):
    session = check.OwnerPolicyCheckSession(*args, clock=clock)
    session.decide("approved", plan_id=session.plan.check_plan_id)
    return session


def _assert_unknown(data):
    assert data["status"] == "not-run"
    assert data["authorization_status"] == "unknown"
    assert data["provider_calls"] == 0 and data["patch_application"] == "not-run"
    assert all(row["observed"] is None and row["result"] == "unknown" for row in data["cases"])


def test_preparation_is_immutable_offline_and_keeps_preview_contract_unchanged(context):
    args = _context(context)
    offline_plan = args[0]
    before = offline_plan.payload_json
    plan = check.prepare_owner_policy_check(*args)
    wire = plan.to_dict()["worker_input"]
    assert wire["plan_id"] == plan.check_plan_id
    assert wire["input_sha256"] == identity(wire["cases"])
    assert wire["policy_source_sha256"] == context[0]["source_sha256"]["policy.py"]
    assert set(wire) == {
        "schema_version",
        "check_id",
        "plan_id",
        "policy_source_sha256",
        "worker_sha256",
        "input_sha256",
        "cases",
    }
    for original, row in zip(context[0]["cases"], wire["cases"], strict=True):
        assert row["id"] == original["id"]
        assert row["case_sha256"] == identity(original)
        assert row["principal"] == original["principal"] and row["report"] == original["report"]
        assert "reason" not in row and "evidence_ids" not in row and "expected" not in row
    with pytest.raises(FrozenInstanceError):
        plan.payload_json = "{}"
    mutated = plan.to_dict()
    mutated["worker_input"]["cases"][0]["principal"]["subject"] = "mutated-copy"
    assert mutated != plan.to_dict()
    assert offline_plan.payload_json == before
    preview_data = offline_plan.to_dict()
    assert preview_data["schema_version"] == "1.0"
    assert preview_data["execution_available"] is False
    assert preview_data["execution_status"] == "not-run"
    assert preview.validate_owner_policy_plan(before, *args[1:]) == offline_plan


def test_model_and_reviewer_reason_text_is_bound_but_not_worker_input(context):
    original, request, draft, _ = context
    text = "$(never-run)\n__import__('os').system('never-run')\u202e"
    raw = draft.to_dict()
    for case in raw["cases"]:
        case["reason"] = text
    changed_draft = OwnerPolicyReview(canonical(raw))
    case_set = preview.prepare_owner_case_set(changed_draft, request)
    choices = {
        case["id"]: {"decision": "approved", "expected": case["expected"], "reason": text}
        for case in original["cases"]
    }
    labels = preview.review_owner_cases(
        case_set, changed_draft, request, decisions=choices, reviewer="test-only"
    )
    offline_plan = preview.prepare_owner_policy_plan(labels, case_set, changed_draft, request)
    plan = check.prepare_owner_policy_check(offline_plan, labels, case_set, changed_draft, request)
    data = offline_plan.to_dict()
    assert data["cases"][0]["reason"] == text
    assert data["label_review"]["decisions"][0]["reason"] == text
    assert "never-run" not in canonical(plan.to_dict()["worker_input"])


@pytest.mark.parametrize("change", ["label", "reviewer", "reason", "case"])
def test_every_valid_review_or_case_change_creates_a_new_bound_check_plan(context, change):
    args = _context(context)
    before = check.prepare_owner_policy_check(*args)
    if change == "label":
        altered = _context(context, changed_first=True)
    elif change == "reviewer":
        altered = _context(context, reviewer="another-test-only-caller")
    elif change == "reason":
        choices = {
            case["id"]: {
                "decision": "approved",
                "expected": case["expected"],
                "reason": "New note",
            }
            for case in context[0]["cases"]
        }
        labels = preview.review_owner_cases(
            args[2], args[3], args[4], decisions=choices, reviewer="offline-test"
        )
        altered = (preview.prepare_owner_policy_plan(labels, *args[2:]), labels, *args[2:])
    else:
        raw = args[3].to_dict()
        raw["cases"][0]["reason"] += " New model-authored text."
        draft = OwnerPolicyReview(canonical(raw))
        case_set = preview.prepare_owner_case_set(draft, args[4])
        altered = _context((context[0], args[4], draft, case_set))
    after = check.prepare_owner_policy_check(*altered)
    assert before.check_plan_id != after.check_plan_id


def test_scripted_success_is_compared_by_host_and_never_claims_authorization(context, monkeypatch):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = _approved_session(args)
    data = asyncio.run(session.run(*args)).to_dict()
    assert len(calls) == 1 and data["status"] == "passed"
    assert all(
        row["result"] == "passed" and row["observed"] is row["expected"] for row in data["cases"]
    )
    assert sum(row["observed"] is True for row in data["cases"]) == 2
    assert data["authorization_status"] == "unknown"
    assert data["provider_calls"] == 0 and data["patch_application"] == "not-run"


def test_scripted_mismatch_uses_changed_reviewed_label_not_original_model_label(
    context, monkeypatch
):
    args = _context(context, changed_first=True)
    _mock_worker(monkeypatch, context)
    data = asyncio.run(_approved_session(args).run(*args)).to_dict()
    assert data["status"] == "failed"
    first = data["cases"][0]
    assert first["expected"] is not context[0]["cases"][0]["expected"]
    assert first["observed"] is context[0]["cases"][0]["expected"]
    assert first["result"] == "failed"
    assert all(row["result"] == "passed" for row in data["cases"][1:])
    assert data["authorization_status"] == "unknown"


@pytest.mark.parametrize("state", ["pending", "declined"])
def test_unreviewed_labels_cannot_execute_even_with_fresh_approved_choice(
    context, monkeypatch, state
):
    args = _context(context, state)
    calls = _mock_worker(monkeypatch, context)
    session = _approved_session(args)
    data = asyncio.run(session.run(*args)).to_dict()
    _assert_unknown(data)
    assert data["reason"] == "labels-not-reviewed" and calls == []


@pytest.mark.parametrize("choice", [None, "pending", "declined", "cancelled"])
def test_pending_declined_cancelled_or_absent_decision_never_calls_transport(
    context, monkeypatch, choice
):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = check.OwnerPolicyCheckSession(*args, clock=lambda: 100.0)
    if choice is not None:
        session.decide(choice, plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


def test_approved_decision_expires_and_failed_attempt_cannot_be_reused(context, monkeypatch):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    now = [100.0]
    session = _approved_session(args, clock=lambda: now[0])
    now[0] += 301.0
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    now[0] = 101.0
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize("choice", ["approved", "declined", "cancelled"])
def test_terminal_choice_cannot_be_replaced_and_invalidates_the_entire_session(
    context, monkeypatch, choice
):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = check.OwnerPolicyCheckSession(*args, clock=lambda: 100.0)
    session.decide(choice, plan_id=session.plan.check_plan_id)
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    # Rejection cannot clear the choice and silently permit a second renewal.
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize("choice", ["pending", "approved"])
@pytest.mark.parametrize("now", [400.0, 401.0])
def test_expired_choice_cannot_be_renewed_and_requires_a_new_session(
    context, monkeypatch, choice, now
):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    ticks = [100.0]
    session = check.OwnerPolicyCheckSession(*args, clock=lambda: ticks[0])
    session.decide(choice, plan_id=session.plan.check_plan_id, lifetime_seconds=300)
    ticks[0] = now
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    # Moving a supplied clock back into the old window cannot revive the session.
    ticks[0] = 101.0
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


def test_still_valid_pending_choice_can_be_replaced_by_one_approved_choice(context, monkeypatch):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    ticks = [100.0]
    session = check.OwnerPolicyCheckSession(*args, clock=lambda: ticks[0])
    session.decide("pending", plan_id=session.plan.check_plan_id)
    ticks[0] = 101.0
    decision = session.decide("approved", plan_id=session.plan.check_plan_id)
    assert decision.to_dict()["choice"] == "approved"
    assert asyncio.run(session.run(*args)).to_dict()["status"] == "passed"
    assert len(calls) == 1


def test_successful_decision_is_single_use(context, monkeypatch):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = _approved_session(args)
    original_result = asyncio.run(session.run(*args))
    assert original_result.to_dict()["status"] == "passed"
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert session.last_result is original_result
    assert len(calls) == 1


@pytest.mark.parametrize("platform", ["windows", "frozen"])
def test_unsupported_platform_fails_closed_before_mock_transport(context, monkeypatch, platform):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = _approved_session(args)
    if platform == "windows":
        # Replace the host binding, never os.name globally (which breaks pathlib).
        monkeypatch.setattr(check, "os", SimpleNamespace(name="nt"))
    else:
        monkeypatch.setattr(check, "sys", SimpleNamespace(frozen=True))
    data = asyncio.run(session.run(*args)).to_dict()
    _assert_unknown(data)
    assert data["reason"] == "unsupported-platform" and calls == []


@pytest.mark.parametrize("change", ["worker-source", "worker-hash", "recipe"])
def test_changed_worker_or_recipe_invalidates_bound_choice_before_transport(
    context, monkeypatch, change
):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = _approved_session(args)
    if change == "worker-source":
        monkeypatch.setattr(check, "WORKER_SOURCE", check.WORKER_SOURCE + "\n# Changed recipe\n")
    elif change == "worker-hash":
        monkeypatch.setattr(check, "WORKER_SHA256", "0" * 64)
    else:
        original_recipe = check._recipe

        def changed_recipe():
            recipe = original_recipe()
            recipe["mapping_version"] += "-changed"
            return recipe

        monkeypatch.setattr(check, "_recipe", changed_recipe)
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize("change", ["labels", "case", "request", "preview"])
def test_stale_or_forged_context_consumes_attempt_before_transport(context, monkeypatch, change):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = _approved_session(args)
    if change == "labels":
        altered = _context(context, changed_first=True)
    elif change == "case":
        raw = args[3].to_dict()
        raw["cases"][0]["principal"]["subject"] += " "
        altered = (*args[:3], OwnerPolicyReview(canonical(raw)), args[4])
    elif change == "request":
        raw = args[4].to_dict()
        evidence = next(item for item in raw["evidence"] if item["kind"] == "source")
        evidence["data"]["text"] += "\n# changed\n"
        evidence["id"] = "ev-" + identity({"kind": evidence["kind"], "data": evidence["data"]})
        raw["source_identity"] = identity(
            {
                item["data"]["path"]: item["data"]["text"]
                for item in raw["evidence"]
                if item["kind"] == "source"
            }
        )
        altered = (*args[:4], CodexAnalysisRequest(canonical(raw)))
    else:
        raw = args[0].to_dict()
        raw["harness_recipe_sha256"] = "0" * 64
        altered = (preview.OwnerPolicyPlan(canonical(raw)), *args[1:])
    _assert_unknown(asyncio.run(session.run(*altered)).to_dict())
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize("choice", ["approve", "APPROVED", "", None, True, [], {}])
def test_invalid_decision_choice_is_rejected_without_coercion(context, choice):
    session = check.OwnerPolicyCheckSession(*_context(context), clock=lambda: 100.0)
    with pytest.raises(ContractError):
        session.decide(choice, plan_id=session.plan.check_plan_id)


def test_invalid_first_choice_cannot_be_retried_in_the_same_session(context, monkeypatch):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    session = check.OwnerPolicyCheckSession(*args, clock=lambda: 100.0)
    with pytest.raises(ContractError):
        session.decide("not-a-choice", plan_id=session.plan.check_plan_id)
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    data = asyncio.run(session.run(*args)).to_dict()
    _assert_unknown(data)
    assert data["reason"] == "execution-decision-invalidated" and calls == []


@pytest.mark.parametrize("plan_id", ["wrong-plan", "", None, True, []])
def test_decision_requires_exact_bound_plan_id(context, plan_id):
    session = check.OwnerPolicyCheckSession(*_context(context), clock=lambda: 100.0)
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=plan_id)


@pytest.mark.parametrize(
    "lifetime", [0, -1, 300.1, 10**1000, True, float("nan"), float("inf"), "300", None]
)
def test_invalid_decision_lifetime_is_rejected(context, lifetime):
    session = check.OwnerPolicyCheckSession(*_context(context), clock=lambda: 100.0)
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id, lifetime_seconds=lifetime)


@pytest.mark.parametrize(
    "now", [-1, 1e12 + 1, 10**1000, True, float("nan"), float("inf"), "100", None]
)
def test_invalid_clock_values_are_rejected_without_coercion(context, now):
    with pytest.raises(ContractError):
        session = check.OwnerPolicyCheckSession(*_context(context), clock=lambda: now)
        session.decide("approved", plan_id=session.plan.check_plan_id)


@pytest.mark.parametrize(("now", "lifetime"), [(1e12, 1), (1e12 - 100, 300), (1e12, 1e-10)])
def test_expiry_must_be_representable_increasing_and_within_clock_budget(context, now, lifetime):
    session = check.OwnerPolicyCheckSession(*_context(context), clock=lambda: now)
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id, lifetime_seconds=lifetime)


@pytest.mark.parametrize("change", ["choice", "plan", "lifetime", "clock"])
def test_invalid_replacement_cannot_leave_an_earlier_approval_active(context, monkeypatch, change):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    ticks = [100.0]
    session = _approved_session(args, clock=lambda: ticks[0])
    choice = "approved"
    plan_id = session.plan.check_plan_id
    lifetime = 300
    if change == "choice":
        choice = "not-a-choice"
    elif change == "plan":
        plan_id = "wrong-plan"
    elif change == "lifetime":
        lifetime = 0
    else:
        ticks[0] = 99.0
    with pytest.raises(ContractError):
        session.decide(choice, plan_id=plan_id, lifetime_seconds=lifetime)
    ticks[0] = 101.0
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize("change", ["choice", "plan", "lifetime", "clock", "nonfinite-clock"])
def test_invalid_pending_replacement_irreversibly_locks_the_session(context, monkeypatch, change):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    ticks = [100.0]
    session = check.OwnerPolicyCheckSession(*args, clock=lambda: ticks[0])
    session.decide("pending", plan_id=session.plan.check_plan_id)
    choice, plan_id, lifetime = "approved", session.plan.check_plan_id, 300
    if change == "choice":
        choice = "not-a-choice"
    elif change == "plan":
        plan_id = "wrong-plan"
    elif change == "lifetime":
        lifetime = 0
    elif change == "clock":
        ticks[0] = 99.0
    else:
        ticks[0] = float("nan")
    with pytest.raises(ContractError):
        session.decide(choice, plan_id=plan_id, lifetime_seconds=lifetime)
    ticks[0] = 101.0
    with pytest.raises(ContractError):
        session.decide("approved", plan_id=session.plan.check_plan_id)
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize("now", [99.0, True, float("nan"), float("inf")])
def test_backward_or_invalid_clock_at_run_fails_closed(context, monkeypatch, now):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context)
    ticks = [100.0]
    session = _approved_session(args, clock=lambda: ticks[0])
    ticks[0] = now
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert calls == []


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "check-id",
        "plan-id",
        "policy-sha",
        "worker-sha",
        "input-sha",
        "extra",
        "case-sha",
        "case-id",
        "order",
        "missing",
        "duplicate",
        "case-extra",
        "integer",
        "null",
        "text",
        "not-object",
        "bad-json",
        "duplicate-json-keys",
        "invalid-utf8",
        "nonfinite-json",
        "trailing-event",
        "oversize",
    ],
)
def test_corrupt_or_unbound_worker_output_never_becomes_false_denial(context, monkeypatch, change):
    def mutate(value):
        header_fields = {
            "schema": "schema_version",
            "check-id": "check_id",
            "plan-id": "plan_id",
            "policy-sha": "policy_source_sha256",
            "worker-sha": "worker_sha256",
            "input-sha": "input_sha256",
        }
        if change in header_fields:
            value[header_fields[change]] = "forged"
        elif change == "extra":
            value["command"] = "never-run"
        elif change == "case-sha":
            value["cases"][0]["case_sha256"] = "0" * 64
        elif change == "case-id":
            value["cases"][0]["id"] += "x"
        elif change == "order":
            value["cases"].reverse()
        elif change == "missing":
            value["cases"].pop()
        elif change == "duplicate":
            value["cases"][1] = copy.deepcopy(value["cases"][0])
        elif change == "case-extra":
            value["cases"][0]["reason"] = "not a worker result"
        elif change in {"integer", "null", "text"}:
            value["cases"][0]["observed"] = {"integer": 1, "null": None, "text": "false"}[change]
        elif change == "not-object":
            return b"[]"
        elif change == "bad-json":
            return b"{broken"
        elif change == "duplicate-json-keys":
            return b'{"schema_version":"1.0","schema_version":"1.0"}'
        elif change == "invalid-utf8":
            return b"\xff"
        elif change == "nonfinite-json":
            return b'{"cases":NaN}'
        elif change == "trailing-event":
            return canonical(value).encode("utf-8") + b"\n{}\n"
        else:
            return b" " * (16 * 1024 + 1)
        return value

    args = _context(context)
    calls = _mock_worker(monkeypatch, context, mutate=mutate)
    session = _approved_session(args)
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("reason", "exit_code", "cleanup"),
    [
        ("timeout", None, "confirmed"),
        ("output-limit", None, "confirmed"),
        ("launch-failed", None, "not-needed"),
        (None, 1, "confirmed"),
        (None, 0, "unconfirmed"),
        ("cleanup-unconfirmed", None, "unconfirmed"),
    ],
)
def test_transport_failures_are_unknown_even_when_payload_has_scripted_booleans(
    context, monkeypatch, reason, exit_code, cleanup
):
    args = _context(context)
    calls = _mock_worker(monkeypatch, context, reason=reason, exit_code=exit_code, cleanup=cleanup)
    _assert_unknown(asyncio.run(_approved_session(args).run(*args)).to_dict())
    assert len(calls) == 1


def test_no_child_launch_failure_preserves_process_error_and_not_needed_cleanup(
    context, monkeypatch
):
    args = _context(context)

    async def launch_failure(plan):
        return check.WorkerTransport(
            output=b"", exit_code=None, reason="worker-process-error", cleanup_status="not-needed"
        )

    monkeypatch.setattr(check, "_run_worker", launch_failure)
    data = asyncio.run(_approved_session(args).run(*args)).to_dict()
    _assert_unknown(data)
    assert data["reason"] == "worker-process-error"
    assert data["exit_code"] is None and data["cleanup_status"] == "not-needed"
    assert data["execution_status"] == "not-run"


@pytest.mark.parametrize("reason", [None, "worker-process-error", "timeout"])
def test_unconfirmed_cleanup_keeps_priority_over_other_transport_reason(
    context, monkeypatch, reason
):
    args = _context(context)

    async def uncertain(plan):
        return check.WorkerTransport(
            output=b"", exit_code=None, reason=reason, cleanup_status="unconfirmed"
        )

    monkeypatch.setattr(check, "_run_worker", uncertain)
    data = asyncio.run(_approved_session(args).run(*args)).to_dict()
    _assert_unknown(data)
    assert data["reason"] == "cleanup-unconfirmed" and data["cleanup_status"] == "unconfirmed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("output", "not-bytes"),
        ("output", bytearray(b"{}")),
        ("exit_code", False),
        ("exit_code", True),
        ("exit_code", "0"),
        ("cleanup_status", None),
        ("cleanup_status", []),
        ("cleanup_status", {}),
        ("reason", []),
    ],
)
def test_malformed_transport_fields_fail_closed_without_coercion(
    context, monkeypatch, field, value
):
    args = _context(context)

    async def malformed(plan):
        fields = {
            "output": canonical(_output(plan, _scripted_observations(context))).encode(),
            "exit_code": 0,
            "reason": None,
            "cleanup_status": "confirmed",
        }
        fields[field] = value
        return check.WorkerTransport(**fields)

    monkeypatch.setattr(check, "_run_worker", malformed)
    _assert_unknown(asyncio.run(_approved_session(args).run(*args)).to_dict())


def test_unknown_transport_object_fails_closed(context, monkeypatch):
    args = _context(context)

    async def malformed(plan):
        return {"output": b"{}", "exit_code": 0, "cleanup_status": "confirmed"}

    monkeypatch.setattr(check, "_run_worker", malformed)
    _assert_unknown(asyncio.run(_approved_session(args).run(*args)).to_dict())


def test_cancellation_retains_unknown_result_and_consumes_decision(context, monkeypatch):
    args = _context(context)
    calls = []

    async def cancelled(plan):
        calls.append(plan)
        raise asyncio.CancelledError

    monkeypatch.setattr(check, "_run_worker", cancelled)
    session = _approved_session(args)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(session.run(*args))
    _assert_unknown(session.last_result.to_dict())
    assert session.last_result.to_dict()["reason"] == "cancelled"
    _assert_unknown(asyncio.run(session.run(*args)).to_dict())
    assert len(calls) == 1


def test_concurrent_attempt_cannot_reuse_choice_while_first_transport_is_waiting(
    context, monkeypatch
):
    args = _context(context)
    calls = []

    async def scenario():
        entered, finish = asyncio.Event(), asyncio.Event()

        async def waiting(plan):
            calls.append(plan)
            entered.set()
            await finish.wait()
            return check.WorkerTransport(
                output=canonical(_output(plan, _scripted_observations(context))).encode(),
                exit_code=0,
                reason=None,
                cleanup_status="confirmed",
            )

        monkeypatch.setattr(check, "_run_worker", waiting)
        session = _approved_session(args)
        first = asyncio.create_task(session.run(*args))
        await entered.wait()
        second = await session.run(*args)
        _assert_unknown(second.to_dict())
        finish.set()
        assert (await first).to_dict()["status"] == "passed"

    asyncio.run(scenario())
    assert len(calls) == 1
