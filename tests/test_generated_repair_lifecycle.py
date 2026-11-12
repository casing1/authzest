"""Maintained synthetic data exercises; no generated input or runtime execution."""

from __future__ import annotations

import builtins
import os
import socket
import subprocess

import pytest

from authzest.codex.contracts import ContractError
from authzest.runner._generated_repair_lifecycle import GeneratedRepairLifecycleModel


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def reply_for(intent, *, t_exit=0):
    data = intent.to_dict()
    action = data["action"]
    role = data["role"]
    fields = {
        "record": {"ok": True},
        "create": {"status": "created", "container_id": {"T": "1", "A": "2", "B": "3"}[role] * 64},
        "inspect": {
            "status": "found",
            "container_id": data["container_id"],
            "config": data["expected_config"],
        },
        "attach": {"status": "ok"},
        "start": {"status": "ok"},
        "readiness": {"ready": True, "output_bytes": 0},
        "capture": {
            "complete": True,
            "exit_code": t_exit if role == "T" else 0,
            "signal": None,
            "oom": False,
            "output_bytes": 10,
        },
        "terminate": {"stopped": True, "output_bytes": 0},
        "remove": {"removed": True},
    }
    return {"intent_id": data["intent_id"], **fields[action]}


@pytest.fixture
def inert_runtime(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Synthetic lifecycle must not execute anything")

    for target, field in (
        (builtins, "exec"),
        (builtins, "eval"),
        (subprocess, "Popen"),
        (subprocess, "run"),
        (os, "system"),
        (socket, "socket"),
        (socket, "create_connection"),
    ):
        monkeypatch.setattr(target, field, blocked)
    yield


@pytest.mark.parametrize("t_exit", [0, 1])
def test_synthetic_happy_trace_remains_no_execution(inert_runtime, t_exit):
    clock = Clock()
    model = GeneratedRepairLifecycleModel(clock=clock)
    trace = []
    for _ in range(40):
        intent = model.next_intent()
        if intent is None:
            break
        data = intent.to_dict()
        trace.append((data["role"], data["action"]))
        assert data["preview_bound"] is False
        assert data["expected_config"]["synthetic_only"] is True
        model.reply(reply_for(intent, t_exit=t_exit))
        clock.now += 0.01
    else:
        pytest.fail("Unbounded model trace")
    result = model.result().to_dict()
    assert result["status"] == "simulation-complete"
    assert result["cleanup_status"] == "confirmed"
    assert result["execution_status"] == "not-run"
    assert result["runtime_invoked"] is False
    assert result["execution_authorized"] is False
    assert result["baseline"] == "not-established"
    assert result["authorization_status"] == "unknown"
    assert result["verified_fix"] is False
    assert result["source_application"] == "not-run"
    assert result["restoration_status"] == "not-run"
    assert trace.index(("T", "remove")) < trace.index(("A", "record"))
    assert trace.index(("A", "readiness")) < trace.index(("B", "record"))
    for role in ("T", "A", "B"):
        assert trace.index((role, "inspect")) < trace.index((role, "attach"))
        assert trace.index((role, "attach")) < trace.index((role, "start"))
    assert result["roles"]["B"]["container_id"] == "3" * 64
    assert result["roles"]["T"]["last_capture"] == {
        "complete": True,
        "exit_code": t_exit,
        "signal": None,
        "oom": False,
        "output_bytes": 10,
        "trusted": False,
    }
    for role in ("T", "A", "B"):
        assert result["roles"][role]["attached"] is True
        assert result["roles"][role]["start_attempted"] is True
        assert result["roles"][role]["simulated_started"] is True


def test_relay_binds_exact_inspected_application_only(inert_runtime):
    model = GeneratedRepairLifecycleModel(clock=Clock())
    while (intent := model.next_intent()) is not None:
        data = intent.to_dict()
        config = data["expected_config"]
        if data["role"] == "B":
            assert config["network"] == "container:" + "2" * 64
            assert config["mounts"] == []
        else:
            assert config["network"] == "none"
        assert config["environment"] == config["ports"] == config["devices"] == []
        assert config["read_only_root"] is config["no_new_privileges"] is True
        assert config["logging"] == "none"
        assert config["pull"] == "never"
        model.reply(reply_for(intent))


def test_distinct_instances_cannot_exchange_current_replies(inert_runtime):
    first = GeneratedRepairLifecycleModel(clock=Clock())
    second = GeneratedRepairLifecycleModel(clock=Clock())
    a, b = first.next_intent(), second.next_intent()
    assert a.to_dict()["name"] != b.to_dict()["name"]
    assert a.to_dict()["nonce"] != b.to_dict()["nonce"]
    with pytest.raises(ContractError):
        second.reply(reply_for(a))
    second.reply(reply_for(b))


def test_mutating_export_cannot_change_model_config(inert_runtime):
    model = GeneratedRepairLifecycleModel(clock=Clock())
    intent = model.next_intent()
    data = intent.to_dict()
    data["expected_config"]["privileged"] = True
    assert intent.to_dict()["expected_config"]["privileged"] is False
    result = model.result().to_dict()
    result["roles"]["T"]["removed"] = True
    assert model.result().to_dict()["roles"]["T"]["removed"] is False


def test_no_constructor_importer_or_execute_surface(inert_runtime):
    model = GeneratedRepairLifecycleModel(clock=Clock())
    for method in ("run", "execute", "resume", "apply", "restore", "accept_baseline"):
        assert not hasattr(model, method)
    with pytest.raises(TypeError):
        GeneratedRepairLifecycleModel(preview={})
