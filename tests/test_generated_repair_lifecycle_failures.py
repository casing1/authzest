"""Adversarial lifecycle modeling only; no engine or candidate code is run."""

from __future__ import annotations

import ast
import asyncio
import builtins
import gc
import math
import os
import socket
import subprocess
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError
from authzest.runner import _generated_repair_lifecycle as lifecycle

IDS = {"T": "1" * 64, "A": "2" * 64, "B": "3" * 64}


class Clock:
    def __init__(self, value=1000.0):
        self.value = value
        self.callback = None

    def __call__(self):
        callback, self.callback = self.callback, None
        if callback is not None:
            callback()
        return self.value


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch, request):
    assert len(request.node.nodeid) < 512
    assert ast.unparse(ast.Constant(value=None)) == "None"

    def forbidden(*args, **kwargs):
        pytest.fail("Lifecycle tests must remain in-memory and must not execute code")

    original_import = builtins.__import__
    original_compile = builtins.compile

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app",
            "docker",
            "fastapi",
            "httpx",
            "openai",
            "requests",
            "uvicorn",
        } or name.startswith("authzest.codex.app_server"):
            forbidden()
        return original_import(name, *args, **kwargs)

    def ast_only_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", ast_only_compile)
    for name in ("open", "eval", "exec"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def _model():
    clock = Clock()
    return lifecycle.GeneratedRepairLifecycleModel(clock=clock), clock


def _intent(model):
    value = model.next_intent()
    assert value is not None
    return value.to_dict()


def _event(intent, **overrides):
    action, role = intent["action"], intent["role"]
    if action == "record":
        values = {"ok": True}
    elif action == "create":
        values = {"status": "created", "container_id": IDS[role]}
    elif action in {"inspect", "reconcile"}:
        values = {
            "status": "found",
            "container_id": IDS[role],
            "config": intent["expected_config"],
        }
    elif action in {"attach", "start"}:
        values = {"status": "ok"}
    elif action == "readiness":
        values = {"ready": True, "output_bytes": 0}
    elif action == "capture":
        values = {
            "complete": True,
            "exit_code": 1 if role == "T" else 0,
            "signal": None,
            "oom": False,
            "output_bytes": 0,
        }
    elif action == "terminate":
        values = {"stopped": True, "output_bytes": 0}
    elif action == "remove":
        values = {"removed": True}
    else:
        pytest.fail(f"Unexpected model intent: {action}")
    return {"intent_id": intent["intent_id"], **values, **overrides}


def _reach(model, action, role=None):
    for _ in range(80):
        intent = _intent(model)
        if intent["action"] == action and (role is None or intent["role"] == role):
            return intent
        model.reply(_event(intent))
    pytest.fail("Closed lifecycle did not reach the expected fixed action")


def _drain(model):
    intents = []
    for _ in range(80):
        value = model.next_intent()
        if value is None:
            return intents
        intent = value.to_dict()
        intents.append(intent)
        model.reply(_event(intent))
    pytest.fail("Closed lifecycle did not terminate within its fixed role schedule")


def _inert(model):
    data = model.result().to_dict()
    assert data["runtime_invoked"] is False
    assert data["execution_status"] == "not-run"
    assert data["baseline"] == "not-established"
    assert data["authorization_status"] == "unknown"
    assert data["verified_fix"] is False
    return data


def test_complete_model_is_not_execution_or_application_authority():
    model, _ = _model()
    intents = _drain(model)
    assert {item["role"] for item in intents} == {"T", "A", "B"}
    _inert(model)
    for forbidden in ("execute", "run", "apply", "restore", "import_result"):
        assert not hasattr(model, forbidden)


def test_each_role_is_recorded_inspected_and_attached_before_start():
    model, _ = _model()
    intents = _drain(model)
    for role in IDS:
        actions = [item["action"] for item in intents if item["role"] == role]
        assert actions.index("record") < actions.index("create")
        assert actions.index("create") < actions.index("inspect")
        assert actions.index("inspect") < actions.index("attach")
        assert actions.index("attach") < actions.index("start")
    t_remove = next(
        i for i, item in enumerate(intents) if item["role"] == "T" and item["action"] == "remove"
    )
    a_create = next(
        i for i, item in enumerate(intents) if item["role"] == "A" and item["action"] == "create"
    )
    assert t_remove < a_create


def test_pending_intent_cannot_be_dispatched_twice():
    model, _ = _model()
    pending = _intent(model)
    with pytest.raises(ContractError):
        model.next_intent()
    model.reply(_event(pending))
    assert _intent(model)["action"] == "create"


@pytest.mark.parametrize("mutation", ["missing-id", "wrong-id", "extra-field", "wrong-shape"])
def test_malformed_reply_preserves_pending_intent(mutation):
    model, _ = _model()
    intent = _intent(model)
    event = _event(intent)
    if mutation == "missing-id":
        del event["intent_id"]
    elif mutation == "wrong-id":
        event["intent_id"] = "unrelated-current-intent"
    elif mutation == "extra-field":
        event["action"] = "start"
    else:
        event["ok"] = 1
    with pytest.raises(ContractError):
        model.reply(event)
    model.reply(_event(intent))
    assert _intent(model)["action"] == "create"


def test_consumed_reply_cannot_be_replayed_against_new_pending_intent():
    model, _ = _model()
    first = _intent(model)
    event = _event(first)
    model.reply(event)
    second = _intent(model)
    with pytest.raises(ContractError):
        model.reply(event)
    model.reply(_event(second))
    assert _intent(model)["action"] == "inspect"


def test_record_refusal_never_emits_create_or_cleanup_for_uncreated_role():
    model, _ = _model()
    intent = _intent(model)
    model.reply(_event(intent, ok=False))
    assert _drain(model) == []
    _inert(model)


def test_ambiguous_create_reconciles_only_previously_recorded_unique_name():
    model, _ = _model()
    intent = _reach(model, "create", "T")
    model.reply(_event(intent, status="ambiguous", container_id=None))
    reconcile = _intent(model)
    assert reconcile["action"] == "reconcile"
    for key in ("role", "name", "nonce", "expected_config"):
        assert reconcile[key] == intent[key]
    model.reply(_event(reconcile))
    cleanup = _drain(model)
    assert all(item["action"] in {"terminate", "remove"} for item in cleanup)
    assert all(item["container_id"] == IDS["T"] for item in cleanup)


@pytest.mark.parametrize("field", ["nonce", "image_id", "role", "name"])
def test_foreign_ambiguous_create_never_becomes_destructive_cleanup_target(field):
    model, _ = _model()
    intent = _reach(model, "create", "T")
    model.reply(_event(intent, status="ambiguous", container_id=None))
    reconcile = _intent(model)
    event = _event(reconcile)
    event["config"] = dict(event["config"])
    event["config"][field] = "foreign-owned-value"
    model.reply(event)
    assert _drain(model) == []
    _inert(model)


def test_absent_ambiguous_create_does_not_issue_terminate_or_remove():
    model, _ = _model()
    intent = _reach(model, "create", "T")
    model.reply(_event(intent, status="ambiguous", container_id=None))
    reconcile = _intent(model)
    model.reply(_event(reconcile, status="absent", container_id=None, config=None))
    assert _drain(model) == []


def test_owned_name_absence_cannot_prove_previously_returned_container_id_removed():
    model, _ = _model()
    pending = _reach(model, "inspect", "T")
    assert pending["container_id"] == IDS["T"]
    model.cancel()
    reconcile = _intent(model)
    assert reconcile["action"] == "reconcile"
    assert reconcile["container_id"] == IDS["T"]
    model.reply(_event(reconcile, status="absent", container_id=None, config=None))
    assert _drain(model) == []
    data = model.result().to_dict()
    assert data["cleanup_status"] == "unconfirmed"
    assert data["roles"]["T"]["removed"] is False
    assert data["roles"]["T"]["container_id"] == IDS["T"]


def test_inspection_cannot_replace_created_id_with_a_different_owned_looking_id():
    model, _ = _model()
    intent = _reach(model, "inspect", "T")
    model.reply(_event(intent, container_id="f" * 64))
    assert _drain(model) == []
    assert model.result().to_dict()["cleanup_status"] == "unconfirmed"


def test_relay_wrong_application_network_identity_never_receives_start_or_cleanup():
    model, _ = _model()
    intent = _reach(model, "inspect", "B")
    event = _event(intent)
    event["config"] = dict(event["config"])
    event["config"]["network"] = "container:" + "f" * 64
    model.reply(event)
    remaining = _drain(model)
    assert not any(item["role"] == "B" for item in remaining)
    assert model.result().to_dict()["cleanup_status"] == "unconfirmed"
    _inert(model)


@pytest.mark.parametrize("field,value", [("read_only_root", 1), ("cpu", True)])
def test_inspected_config_requires_exact_wire_types_not_python_scalar_equality(field, value):
    model, _ = _model()
    intent = _reach(model, "inspect", "T")
    event = _event(intent)
    event["config"] = dict(event["config"])
    event["config"][field] = value
    model.reply(event)
    assert _drain(model) == []
    assert model.result().to_dict()["cleanup_status"] == "unconfirmed"
    assert model.result().to_dict()["failure_reason"] == "identity-unconfirmed"


def test_ambiguous_start_never_claims_guest_stopped_and_always_requests_cleanup():
    model, _ = _model()
    intent = _reach(model, "start", "T")
    model.reply(_event(intent, status="ambiguous"))
    cleanup = _drain(model)
    assert [item["action"] for item in cleanup] == ["terminate", "remove"]
    assert all(item["container_id"] == IDS["T"] for item in cleanup)


def test_expected_t_assertion_failure_remains_auxiliary_and_allows_independent_roles():
    model, _ = _model()
    intent = _reach(model, "capture", "T")
    model.reply(_event(intent, exit_code=1))
    remaining = _drain(model)
    assert any(item["action"] == "create" and item["role"] == "A" for item in remaining)
    assert any(item["action"] == "create" and item["role"] == "B" for item in remaining)
    _inert(model)


def test_exact_phase_deadline_expires_instead_of_resetting_for_application_role():
    model, clock = _model()
    first = _intent(model)
    model.reply(_event(first))
    origin = model.result().to_dict()["phase_started_at"]
    intent = _reach(model, "capture", "T")
    clock.value = origin + 35
    model.reply(_event(intent))
    readiness = _reach(model, "readiness", "A")
    clock.value = origin + 40
    model.reply(_event(readiness))
    data = model.result().to_dict()
    assert data["phase_started_at"] == origin
    assert data["phase_deadline"] == origin + 40
    assert data["failure_reason"] == "phase-timeout"
    assert all(item["action"] in {"terminate", "remove"} for item in _drain(model))
    _inert(model)


def test_exact_readiness_budget_is_not_extra_phase_time():
    model, clock = _model()
    intent = _reach(model, "readiness", "A")
    clock.value += 10
    model.reply(_event(intent))
    data = model.result().to_dict()
    assert data["failure_reason"] == "readiness-timeout"
    assert data["readiness_seconds"] == 10
    assert data["phase_deadline"] == data["phase_started_at"] + 40
    assert not any(item["action"] == "create" for item in _drain(model))


def test_phase_deadline_is_not_refreshed_by_new_role_or_intent():
    model, clock = _model()
    first = _intent(model)
    model.reply(_event(first))
    deadline = model.result().to_dict()["phase_deadline"]
    for _ in range(12):
        clock.value += 1
        intent = _intent(model)
        model.reply(_event(intent))
        assert model.result().to_dict()["phase_deadline"] == deadline


def test_startup_and_readiness_share_one_cumulative_budget_across_all_roles():
    model, clock = _model()
    seen_roles = set()
    for _ in range(35):
        intent = _intent(model)
        seen_roles.add(intent["role"])
        if intent["action"] == "record":
            clock.value += 2
        elif intent["action"] in {"start", "readiness"}:
            clock.value += 1
        model.reply(_event(intent))
        if model.result().to_dict()["failure_reason"] is not None:
            break
    else:
        pytest.fail("Per-role startup must not reset cumulative readiness")
    assert seen_roles == {"T", "A", "B"}
    data = model.result().to_dict()
    assert data["failure_reason"] == "readiness-timeout"
    assert data["readiness_seconds"] == 10
    assert data["phase_deadline"] == data["phase_started_at"] + 40
    _drain(model)


def test_cleanup_deadline_is_shared_across_both_surviving_roles():
    model, clock = _model()
    intent = _reach(model, "capture", "B")
    model.reply(_event(intent))
    first = _intent(model)
    assert first["action"] == "terminate" and first["role"] == "B"
    deadline = model.result().to_dict()["cleanup_deadline"]
    assert deadline == clock.value + 10
    clock.value += 4
    model.reply(_event(first))
    second = _intent(model)
    assert second["action"] == "remove" and second["role"] == "B"
    clock.value += 4
    model.reply(_event(second))
    third = _intent(model)
    assert third["action"] == "terminate" and third["role"] == "A"
    assert model.result().to_dict()["cleanup_deadline"] == deadline
    clock.value = deadline
    model.reply(_event(third))
    assert model.next_intent() is None
    data = model.result().to_dict()
    assert data["cleanup_deadline"] == deadline
    assert data["cleanup_status"] == "unconfirmed"
    assert data["failure_reason"] == "cleanup-timeout"


def test_later_cleanup_timeout_preserves_initial_capture_failure():
    model, clock = _model()
    intent = _reach(model, "capture", "T")
    model.reply(_event(intent, complete=False))
    first_reason = model.result().to_dict()["failure_reason"]
    assert first_reason is not None
    terminate = _intent(model)
    assert terminate["action"] == "terminate"
    clock.value = model.result().to_dict()["cleanup_deadline"]
    model.reply(_event(terminate))
    assert model.next_intent() is None
    assert model.result().to_dict()["failure_reason"] == first_reason
    assert model.result().to_dict()["cleanup_status"] == "unconfirmed"


def test_exact_output_limit_is_shared_across_test_and_relay_captures():
    model, _ = _model()
    test_capture = _reach(model, "capture", "T")
    model.reply(_event(test_capture, output_bytes=262_144))
    relay_capture = _reach(model, "capture", "B")
    assert model.result().to_dict()["output_bytes"] == 262_144
    model.reply(_event(relay_capture, output_bytes=1))
    data = model.result().to_dict()
    assert data["failure_reason"] == "output-overflow"
    assert data["output_bytes"] == 262_145
    _drain(model)
    _inert(model)


def test_cleanup_output_cannot_receive_an_independent_extra_output_allowance():
    model, _ = _model()
    capture = _reach(model, "capture", "T")
    model.reply(_event(capture, output_bytes=262_144))
    terminate = _intent(model)
    assert terminate["action"] == "terminate"
    model.reply(_event(terminate, output_bytes=1))
    assert model.result().to_dict()["failure_reason"] == "output-overflow"
    assert not any(item["action"] == "create" for item in _drain(model))


@pytest.mark.parametrize(
    "count", [-1, True, 1.5, 2**80], ids=["negative", "boolean", "float", "huge"]
)
def test_invalid_output_count_is_not_consumed_or_coerced(count):
    model, _ = _model()
    intent = _reach(model, "capture", "T")
    with pytest.raises(ContractError):
        model.reply(_event(intent, output_bytes=count))
    model.reply(_event(intent))
    assert model.result().to_dict()["output_bytes"] == 0


def test_extremely_large_integer_reply_is_bounded_before_float_conversion():
    model, _ = _model()
    intent = _reach(model, "capture", "T")
    with pytest.raises(ContractError):
        model.reply(_event(intent, output_bytes=1 << 4096))
    model.reply(_event(intent))
    assert model.result().to_dict()["output_bytes"] == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"complete": False},
        {"signal": 9, "exit_code": None},
        {"oom": True, "exit_code": 137},
        {"exit_code": 2},
    ],
    ids=["incomplete", "signal", "oom", "collection-exit"],
)
def test_capture_failures_remain_distinct_and_never_reach_application(overrides):
    model, _ = _model()
    intent = _reach(model, "capture", "T")
    model.reply(_event(intent, **overrides))
    data = model.result().to_dict()
    assert data["failure_reason"] is not None
    assert not any(item["action"] == "create" for item in _drain(model))
    _inert(model)


def test_cancelled_outstanding_create_requires_reconciliation_not_zero_effects():
    model, _ = _model()
    pending = _reach(model, "create", "T")
    model.cancel()
    reconcile = _intent(model)
    assert reconcile["action"] == "reconcile"
    assert reconcile["name"] == pending["name"]
    model.reply(_event(reconcile))
    assert [item["action"] for item in _drain(model)] == ["terminate", "remove"]
    assert model.result().to_dict()["failure_reason"] == "cancelled"


def test_cancelled_outstanding_start_requires_exact_id_cleanup():
    model, _ = _model()
    pending = _reach(model, "start", "T")
    model.cancel()
    remaining = _drain(model)
    assert [item["action"] for item in remaining] == ["terminate", "remove"]
    assert all(item["container_id"] == pending["container_id"] for item in remaining)


def test_cleanup_remove_failure_is_not_confirmed_or_automatically_retried():
    model, _ = _model()
    remove = _reach(model, "remove", "T")
    model.reply(_event(remove, removed=False))
    assert model.next_intent() is None
    data = model.result().to_dict()
    assert data["cleanup_status"] == "unconfirmed"
    assert data["roles"]["T"]["removed"] is False
    _inert(model)


def test_result_is_historical_and_does_not_consult_clock():
    model, clock = _model()
    _drain(model)

    def forbidden_clock():
        pytest.fail("Historical model result must not inspect current time")

    clock.callback = forbidden_clock
    assert model.result().to_dict() == model.result().to_dict()


def test_returned_intent_and_result_cannot_mutate_live_state():
    model, _ = _model()
    intent = _intent(model)
    original = _event(intent)
    intent["expected_config"]["foreign"] = "caller mutation"
    data = model.result().to_dict()
    data["roles"]["T"]["name"] = "foreign-name"
    model.reply(original)
    create = _intent(model)
    assert "foreign" not in create["expected_config"]
    assert create["name"] != "foreign-name"


def test_validated_reply_is_detached_before_clock_callback_can_mutate_caller_dict():
    model, clock = _model()
    intent = _reach(model, "capture", "T")
    event = _event(intent, output_bytes=3)

    def mutate_caller_input():
        event["output_bytes"] = -100
        event["complete"] = "not-a-boolean"

    clock.callback = mutate_caller_input
    model.reply(event)
    assert model.result().to_dict()["output_bytes"] == 3
    assert model.result().to_dict()["failure_reason"] is None
    assert _intent(model)["action"] == "terminate"


@pytest.mark.parametrize(
    "value", [True, math.nan, math.inf, -1.0], ids=["boolean", "nan", "infinity", "negative"]
)
def test_invalid_initial_clock_cannot_produce_effect_intent(value):
    clock = Clock(value)
    with pytest.raises(ContractError):
        model = lifecycle.GeneratedRepairLifecycleModel(clock=clock)
        model.next_intent()


@pytest.mark.parametrize(
    "returning_coroutine", [False, True], ids=["async-clock", "coroutine-result"]
)
def test_async_clock_is_refused_without_unawaited_coroutine_leak(recwarn, returning_coroutine):
    async def async_clock():
        return 1000.0

    def sync_clock():
        return async_clock()

    with pytest.raises(ContractError):
        lifecycle.GeneratedRepairLifecycleModel(
            clock=sync_clock if returning_coroutine else async_clock
        )
    gc.collect()
    assert not any(issubclass(item.category, RuntimeWarning) for item in recwarn)


def test_clock_backwards_after_create_cannot_revive_or_emit_new_effect_intent():
    model, clock = _model()
    intent = _reach(model, "create", "T")
    clock.value -= 1
    model.reply(_event(intent))
    data = model.result().to_dict()
    assert data["failure_reason"] == "clock-invalid"
    assert data["cleanup_status"] == "unconfirmed"
    assert model.next_intent() is None
    clock.value += 2
    assert model.next_intent() is None
    _inert(model)


def test_reentrant_clock_callback_cannot_cancel_outer_dispatch():
    model, clock = _model()
    nested_errors = []

    def nested():
        try:
            model.cancel()
        except ContractError as exc:
            nested_errors.append(exc)

    clock.callback = nested
    first = _intent(model)
    assert len(nested_errors) == 1
    model.reply(_event(first))
    assert _intent(model)["action"] == "create"
    assert model.result().to_dict()["failure_reason"] is None
