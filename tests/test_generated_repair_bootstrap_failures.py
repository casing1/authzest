"""Synthetic bootstrap refusals only; no Engine, application or image runs."""

from __future__ import annotations

import ast
import asyncio
import builtins
import os
import subprocess
from copy import deepcopy
from dataclasses import replace

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.runner import _generated_repair_bootstrap as bootstrap
from authzest.runner import _generated_repair_engine_http as engine
from test_generated_repair_bootstrap import ENDPOINT, frames
from test_generated_repair_engine_http import PIN


@pytest.fixture(autouse=True)
def no_real_effects(monkeypatch, request):
    assert len(request.node.nodeid) < 512
    original_compile = builtins.compile

    def forbidden(*args, **kwargs):
        pytest.fail("Bootstrap failures use maintained synthetic frames only")

    def ast_only(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "compile", ast_only)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(engine.socket, "socket", forbidden)
    monkeypatch.setattr(engine.socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: deepcopy(PIN))


@pytest.mark.parametrize(
    "endpoint",
    [
        None,
        True,
        "",
        "tcp://localhost:2375",
        "unix:///a/../b",
        "unix:///a//b",
        "unix:///a,b",
        "unix:///a\nb",
    ],
)
def test_bootstrap_never_uses_an_arbitrary_endpoint(endpoint):
    with pytest.raises(ValueError):
        bootstrap.normalize_engine_bootstrap(endpoint, frames())


@pytest.mark.parametrize("operation", [None, True, "image-T", "build", "info?x=y", "/version"])
def test_endpoint_only_transport_never_accepts_image_or_other_operations(monkeypatch, operation):
    monkeypatch.setattr(engine.time, "monotonic", lambda: 100.0)
    with pytest.raises(engine.EngineHTTPError) as caught:
        engine.read_engine_bootstrap(ENDPOINT, operation, deadline=109, budget=engine.WireBudget())
    assert caught.value.diagnostic["contact_attempted"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "wrong-order",
        "different-pin",
        "wire-bool",
        "deep-json",
        "duplicate-json",
        "wrong-engine-version",
    ],
)
def test_bootstrap_rejects_forged_or_inconsistent_two_frame_batches(fault):
    values = frames()
    if fault == "missing":
        values.pop()
    elif fault == "extra":
        values.append(values[-1])
    elif fault == "wrong-order":
        values.reverse()
    elif fault == "different-pin":
        pin = deepcopy(PIN)
        pin["socket_identity"][1] += 1
        values[1] = replace(values[1], endpoint_identity=pin)
    elif fault == "wire-bool":
        values[0] = replace(values[0], wire_bytes=True)
    elif fault == "deep-json":
        raw = b'{"x":' + b"[" * 17 + b"0" + b"]" * 17 + b"}"
        values[0] = replace(values[0], body=raw, wire_bytes=len(raw) + 80)
    elif fault == "duplicate-json":
        raw = b'{"Version":"a","Version":"b"}'
        values[0] = replace(values[0], body=raw, wire_bytes=len(raw) + 80)
    else:
        import json

        body = json.loads(values[1].body)
        body["ServerVersion"] = "different"
        raw = canonical(body).encode()
        values[1] = replace(values[1], body=raw, wire_bytes=len(raw) + 80)
    with pytest.raises(ContractError):
        bootstrap.normalize_engine_bootstrap(ENDPOINT, values)


@pytest.mark.parametrize(
    "phase,setup",
    [(True, 109), (141, 109), (139, 111), (139, 99), (float("inf"), 109), (139, float("nan"))],
)
def test_invalid_deadlines_do_not_dispatch(monkeypatch, phase, setup):
    monkeypatch.setattr(bootstrap, "monotonic", lambda: 100.0)
    result = bootstrap.observe_engine_bootstrap(
        ENDPOINT, phase_deadline=phase, setup_deadline=setup
    ).to_dict()
    assert result["status"] == "failed" and result["query_attempted"] == 0
    assert result["engine_contact_attempted"] is False and result["ready"] is False


def test_failed_info_preserves_prior_version_and_unknown_cleanup(monkeypatch):
    values, calls = frames(), []
    monkeypatch.setattr(bootstrap, "monotonic", lambda: 100.0)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: deepcopy(PIN))

    def reader(endpoint, operation, *, deadline, budget, before_connect):
        before_connect()
        calls.append(operation)
        if operation == "version":
            budget.used += values[0].wire_bytes
            return values[0]
        budget.used += 17
        raise engine.EngineHTTPError(
            {
                "contact_attempted": True,
                "socket_cleanup": "unconfirmed",
                "bytes_received": 17,
                "reason": "operation-failed",
                "cleanup_failure": True,
            }
        )

    monkeypatch.setattr(bootstrap, "read_engine_bootstrap", reader)
    result = bootstrap.observe_engine_bootstrap(
        ENDPOINT, phase_deadline=139, setup_deadline=109
    ).to_dict()
    assert calls == ["version", "info"] and result["response_count"] == 1
    assert result["metadata"]["version"]["selected_api_version"] == "1.51"
    assert result["transport_diagnostic"]["socket_cleanup"] == "unconfirmed"
    assert result["wire_bytes_used"] == values[0].wire_bytes + 17
    assert result["status"] == "failed" and result["ready"] is False


def test_socket_replacement_between_queries_is_refused_before_info_contact(monkeypatch):
    values, calls = frames(), []
    pin = deepcopy(PIN)
    monkeypatch.setattr(bootstrap, "monotonic", lambda: 100.0)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: deepcopy(pin))

    def reader(endpoint, operation, *, deadline, budget, before_connect):
        before_connect()
        calls.append(operation)
        result = values[len(calls) - 1]
        budget.used += result.wire_bytes
        if operation == "version":
            pin["socket_identity"][1] += 1
        return result

    monkeypatch.setattr(bootstrap, "read_engine_bootstrap", reader)
    result = bootstrap.observe_engine_bootstrap(
        ENDPOINT, phase_deadline=139, setup_deadline=109
    ).to_dict()
    assert calls == ["version"] and result["response_count"] == 1
    assert result["status"] == "failed" and result["profile_created"] is False
    assert result["identity_pinned"] is False and result["execution_authorized"] is False


def test_unknown_snapshot_cannot_be_used_as_a_full_runtime_profile():
    observation = bootstrap.normalize_engine_bootstrap(ENDPOINT, frames())
    from authzest.runner._generated_repair_runtime_profile import validate_runtime_profile

    with pytest.raises(ContractError):
        validate_runtime_profile(observation.payload_json)
