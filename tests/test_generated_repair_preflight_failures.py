"""Supplied metadata and fake reader failures; no actual Engine or generated code."""

from __future__ import annotations

import asyncio
import os
import socket
import stat
import subprocess
from copy import deepcopy
from dataclasses import replace

import pytest

from authzest.codex.contracts import ContractError, canonical
from authzest.runner import _generated_repair_preflight as preflight
from authzest.runner._generated_repair_engine_http import (
    MAX_WIRE_BYTES,
    EngineHTTPError,
    EngineResponse,
)
from authzest.runner._generated_repair_runtime_profile import validate_runtime_profile
from test_generated_repair_runtime_profile import profile

OPERATIONS = ("version", "info", "image-T", "image-A", "image-B")
PIN = {
    "socket_identity": [1, 2, stat.S_IFSOCK | 0o600, 0, 0, 1, 0, 10, 10],
    "parent_chain_sha256": "a" * 64,
}


def sample():
    data = profile().to_dict()
    data["engine"]["server_identity_sha256"] = preflight.engine_identity_sha256(
        "owned-synthetic-engine"
    )
    checked = validate_runtime_profile(canonical(data))
    arch = data["platform"].split("/")[1]
    bodies = [
        {
            "Version": "28.5.1",
            "ApiVersion": "1.99",
            "MinAPIVersion": "1.41",
            "Os": "linux",
            "Arch": arch,
        },
        {
            "ID": "owned-synthetic-engine",
            "ServerVersion": "28.5.1",
            "OSType": "linux",
            "Architecture": arch,
            "CgroupVersion": "2",
            "CgroupDriver": "systemd",
            "DefaultRuntime": "runc",
            "SecurityOptions": ["name=seccomp,profile=builtin"],
            "MemoryLimit": True,
        },
    ]
    for role in "TAB":
        bodies.append(
            {
                "Id": data["images"][role]["image_id"],
                "Os": "linux",
                "Architecture": arch,
                "Config": {
                    "User": "65532:65532",
                    "Env": [],
                    "Entrypoint": [],
                    "Cmd": [],
                    "Volumes": {},
                    "Healthcheck": {"Test": ["NONE"]},
                },
            }
        )
    frames = []
    for operation, body in zip(OPERATIONS, bodies, strict=True):
        raw = canonical(body).encode()
        frames.append(EngineResponse(operation, raw, len(raw) + 80, deepcopy(PIN)))
    return checked, bodies, frames


@pytest.fixture(autouse=True)
def no_real_effects(monkeypatch, request):
    assert len(request.node.nodeid) < 512

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata tests may only use supplied frames or a fixed in-memory reader")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(preflight, "monotonic", lambda: 100.0)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"true",
        b"[]",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b"\xff",
        b"x" * 65537,
        b'{"x":' + b"[" * 17 + b"0" + b"]" * 17 + b"}",
    ],
    ids=[
        "empty",
        "primitive",
        "array",
        "duplicate-key",
        "nonfinite",
        "non-utf8",
        "body-over-limit",
        "too-deep",
    ],
)
def test_bad_json_refuses_before_any_runtime_authority(raw):
    checked, _, frames = sample()
    frames[0] = replace(frames[0], body=raw, wire_bytes=len(raw) + 80)
    with pytest.raises(ContractError):
        preflight.normalize_runtime_metadata(checked, frames)


@pytest.mark.parametrize(
    "fault",
    [
        "short",
        "extra",
        "order",
        "duplicate",
        "foreign",
        "wire-bool",
        "wire-short",
        "wire-total",
        "different-pin",
        "pin-bool",
        "pin-extra",
    ],
)
def test_response_batch_requires_exact_native_order_budget_and_one_endpoint(fault):
    checked, _, frames = sample()
    if fault == "short":
        frames.pop()
    elif fault == "extra":
        frames.append(frames[-1])
    elif fault == "order":
        frames[0], frames[1] = frames[1], frames[0]
    elif fault == "duplicate":
        frames[1] = frames[0]
    elif fault == "foreign":
        frames[0] = {"operation": "version", "body": frames[0].body}
    elif fault == "wire-bool":
        frames[0] = replace(frames[0], wire_bytes=True)
    elif fault == "wire-short":
        frames[0] = replace(frames[0], wire_bytes=1)
    elif fault == "wire-total":
        frames = [replace(frame, wire_bytes=MAX_WIRE_BYTES) for frame in frames]
    else:
        pin = deepcopy(PIN)
        if fault == "different-pin":
            pin["socket_identity"][1] += 1
        elif fault == "pin-bool":
            pin["socket_identity"][0] = True
        else:
            pin["ready"] = True
        frames[3] = replace(frames[3], endpoint_identity=pin)
    with pytest.raises(ContractError):
        preflight.normalize_runtime_metadata(checked, frames)


@pytest.mark.parametrize(
    "index,key,value",
    [
        (0, "ApiVersion", "1.40"),
        (0, "MinAPIVersion", "1.99"),
        (0, "Os", "windows"),
        (0, "Arch", "other"),
        (0, "Version", "bad\nversion"),
        (1, "ID", "different-engine"),
        (1, "ServerVersion", "other-version"),
        (1, "OSType", "windows"),
        (1, "Architecture", "other"),
        (1, "MemoryLimit", 1),
        (1, "CgroupVersion", None),
        (1, "SecurityOptions", [True]),
        (2, "Id", "sha256:" + "0" * 64),
        (2, "Os", "windows"),
        (2, "Architecture", "other"),
        (2, "Config", None),
    ],
)
def test_declared_identity_platform_api_and_metadata_shapes_must_match(index, key, value):
    checked, bodies, frames = sample()
    bodies[index][key] = value
    raw = canonical(bodies[index]).encode()
    frames[index] = replace(frames[index], body=raw, wire_bytes=len(raw) + 80)
    with pytest.raises(ContractError):
        preflight.normalize_runtime_metadata(checked, frames)


@pytest.mark.parametrize(
    "key,value",
    [
        ("Env", [True]),
        ("Env", ["bad\nvalue"]),
        ("Cmd", "shell"),
        ("User", False),
        ("Volumes", []),
        ("Healthcheck", {"Test": [False, {"deep": {"x": {"y": {"z": 1}}}}]}),
    ],
)
def test_selected_image_config_is_bounded_inert_metadata(key, value):
    checked, bodies, frames = sample()
    bodies[2]["Config"][key] = value
    raw = canonical(bodies[2]).encode()
    frames[2] = replace(frames[2], body=raw, wire_bytes=len(raw) + 80)
    with pytest.raises(ContractError):
        preflight.normalize_runtime_metadata(checked, frames)


def fake_reader(monkeypatch, frames, *, hook=None):
    observed = []

    def read(checked, operation, *, deadline, budget, before_connect):
        observed.append((operation, deadline, id(budget)))
        before_connect()
        frame = frames[len(observed) - 1]
        budget.used += frame.wire_bytes
        if hook is not None:
            hook(operation, budget)
        return frame

    monkeypatch.setattr(preflight, "read_engine", read)
    return observed


@pytest.mark.parametrize("bad_index", [0, 1, 2, 4])
def test_bad_metadata_stops_before_the_next_query(monkeypatch, bad_index):
    checked, _, frames = sample()
    frames[bad_index] = replace(frames[bad_index], body=b"{}")
    observed = fake_reader(monkeypatch, frames)
    result = preflight.observe_runtime_metadata(
        checked, phase_deadline=130.0, setup_deadline=105.0
    ).to_dict()
    assert result["status"] == "failed"
    assert len(observed) == bad_index + 1
    assert result["response_count"] == bad_index
    assert result["execution_authorized"] is False and result["verified_fix"] is False


@pytest.mark.parametrize(
    "phase,setup",
    [(True, 105), (141, 105), (130, 111), (130, 99), (float("nan"), 105), (130, float("inf"))],
)
def test_invalid_original_deadlines_do_not_dispatch(monkeypatch, phase, setup):
    checked, _, frames = sample()
    observed = fake_reader(monkeypatch, frames)
    result = preflight.observe_runtime_metadata(
        checked, phase_deadline=phase, setup_deadline=setup
    ).to_dict()
    assert result["status"] == "failed" and observed == []
    assert result["engine_contact_attempted"] is False


def test_setup_deadline_is_not_restarted_after_a_successful_query(monkeypatch):
    checked, _, frames = sample()
    now = [100.0]
    monkeypatch.setattr(preflight, "monotonic", lambda: now[0])
    observed = fake_reader(monkeypatch, frames, hook=lambda *args: now.__setitem__(0, 105.0))
    result = preflight.observe_runtime_metadata(
        checked, phase_deadline=130.0, setup_deadline=105.0
    ).to_dict()
    assert result["status"] == "failed" and len(observed) == 1
    assert result["failure_reason"] == "deadline-expired"


def test_guard_runs_once_per_query_and_never_grants_execution(monkeypatch):
    checked, _, frames = sample()
    observed = fake_reader(monkeypatch, frames)
    guards = []
    result = preflight.observe_runtime_metadata(
        checked,
        phase_deadline=130.0,
        setup_deadline=105.0,
        before_query=lambda: guards.append(len(observed)),
    ).to_dict()
    assert result["status"] == "metadata-match" and guards == [1, 2, 3, 4, 5]
    assert {row[1] for row in observed} == {105.0} and len({row[2] for row in observed}) == 1
    assert result["runtime_invoked"] is False and result["verified_fix"] is False


def test_missing_preconnect_guard_confirmation_invalidates_fake_response(monkeypatch):
    checked, _, frames = sample()

    def unsafe(*args, **kwargs):
        return frames[0]

    monkeypatch.setattr(preflight, "read_engine", unsafe)
    result = preflight.observe_runtime_metadata(
        checked, phase_deadline=130.0, setup_deadline=105.0
    ).to_dict()
    assert result["status"] == "failed" and result["response_count"] == 0


def test_transport_failure_keeps_contact_and_close_uncertainty(monkeypatch):
    checked, _, _ = sample()

    def failed(*args, budget, before_connect, **kwargs):
        before_connect()
        budget.used += 37
        raise EngineHTTPError(
            {
                "operation": "version",
                "contact_attempted": True,
                "connection_status": "connected",
                "request_status": "sent",
                "socket_acquisition": "handle-returned",
                "socket_cleanup": "unconfirmed",
                "bytes_received": 37,
                "reason": "operation-failed",
                "cleanup_failure": True,
            }
        )

    monkeypatch.setattr(preflight, "read_engine", failed)
    result = preflight.observe_runtime_metadata(
        checked, phase_deadline=130.0, setup_deadline=105.0
    ).to_dict()
    assert result["status"] == "failed" and result["engine_contact_attempted"] is True
    assert result["response_count"] == 0
    assert result["wire_bytes_used"] == 37
    assert result["transport_diagnostic"]["socket_cleanup"] == "unconfirmed"


def test_transport_cancellation_preserves_original_and_known_partial_disposition(monkeypatch):
    checked, _, _ = sample()
    original = KeyboardInterrupt("owned fake transport cancellation")

    def cancelled(*args, budget, before_connect, **kwargs):
        before_connect()
        budget.used += 29
        original.engine_http_observation = {
            "operation": "version",
            "contact_attempted": True,
            "connection_status": "connected",
            "request_status": "sent",
            "socket_acquisition": "handle-returned",
            "socket_cleanup": "unconfirmed",
            "bytes_received": 29,
            "reason": "operation-failed",
            "cleanup_failure": True,
        }
        raise original

    monkeypatch.setattr(preflight, "read_engine", cancelled)
    with pytest.raises(KeyboardInterrupt) as caught:
        preflight.observe_runtime_metadata(checked, phase_deadline=130.0, setup_deadline=105.0)
    assert caught.value is original
    result = original.runtime_metadata_observation.to_dict()
    assert result["engine_contact_attempted"] is True and result["wire_bytes_used"] == 29
    assert result["transport_diagnostic"]["socket_cleanup"] == "unconfirmed"
    assert result["ready"] is False and result["verified_fix"] is False
