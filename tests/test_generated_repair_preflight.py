"""Pure or mocked Engine metadata only; no socket, Docker, CLI or guest."""

from __future__ import annotations

import asyncio
import builtins
import copy
import os
import socket
import stat
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _generated_repair_preflight as preflight
from authzest.runner._generated_repair_engine_http import EngineHTTPError, EngineResponse
from authzest.runner._generated_repair_runtime_profile import validate_runtime_profile
from test_generated_repair_runtime_profile import profile_data

PIN = {
    "socket_identity": [1, 2, stat.S_IFSOCK | 0o660, 0, 0, 1, 0, 7, 8],
    "parent_chain_sha256": "a" * 64,
}


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch, request):
    assert len(request.node.nodeid) < 512
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata checks require supplied frames or a mocked fixed reader")

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

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for name in ("open", "eval", "exec", "compile"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "lstat", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


def frame(operation, payload):
    body = canonical(payload).encode("utf-8")
    return EngineResponse(operation, body, len(body) + 80, copy.deepcopy(PIN))


def metadata_context():
    data = profile_data()
    data["engine"]["server_identity_sha256"] = preflight.engine_identity_sha256("synthetic-engine")
    checked = validate_runtime_profile(canonical(data))
    frames = [
        frame(
            "version",
            {
                "Version": "29.0.0",
                "ApiVersion": "1.51",
                "MinAPIVersion": "1.41",
                "Os": "linux",
                "Arch": "arm64",
                "Ignored": "never-copy-this-synthetic-extra-field",
            },
        ),
        frame(
            "info",
            {
                "ID": "synthetic-engine",
                "ServerVersion": "29.0.0",
                "OSType": "linux",
                "Architecture": "aarch64",
                "CgroupVersion": "2",
                "CgroupDriver": "systemd",
                "DefaultRuntime": "runc",
                "SecurityOptions": ["name=seccomp,profile=builtin"],
                "MemoryLimit": True,
                "SwapLimit": False,
                "PidsLimit": True,
                "Ignored": "never-copy-this-synthetic-extra-field",
            },
        ),
    ]
    for role in ("T", "A", "B"):
        frames.append(
            frame(
                "image-" + role,
                {
                    "Id": data["images"][role]["image_id"],
                    "Os": "linux",
                    "Architecture": "arm64",
                    "Variant": "v8",
                    "Config": {
                        "Env": ["PYTHONDONTWRITEBYTECODE=1"],
                        "Entrypoint": ["/usr/local/bin/python"],
                        "Cmd": None,
                        "User": "65532:65532",
                        "Volumes": None,
                        "Healthcheck": {"Test": ["NONE"]},
                    },
                    "Ignored": "never-copy-this-synthetic-extra-field",
                },
            )
        )
    return checked, frames


def test_identity_digest_has_the_fixed_domain_separated_preimage():
    expected = canonical(
        {
            "schema_version": "1.0",
            "kind": "generated-repair-engine-identity",
            "engine_id": "synthetic-engine",
        }
    ).encode()
    assert preflight.engine_identity_sha256("synthetic-engine") == sha256(expected).hexdigest()


def test_supplied_metadata_match_is_not_contact_readiness_or_execution():
    checked, frames = metadata_context()
    result = preflight.normalize_runtime_metadata(checked, frames)
    data = result.to_dict()
    assert data["status"] == "metadata-match" and data["response_count"] == 5
    assert data["query_attempted"] == 0 and data["engine_contact_attempted"] is None
    assert data["wire_bytes"] == sum(item.wire_bytes for item in frames)
    assert data["wire_bytes_used"] is None
    assert data["metadata"]["engine"]["architecture"] == "arm64"
    assert data["metadata"]["engine"]["reported_capabilities"]["SwapLimit"] is False
    assert data["metadata"]["engine"]["resource_enforcement_established"] is False
    assert data["endpoint_identity"] == PIN
    assert data["responses"][0]["body_sha256"] == sha256(frames[0].body).hexdigest()
    assert "never-copy-this-synthetic-extra-field" not in result.payload_json
    assert data["runtime_invoked"] is data["ready"] is data["verified_fix"] is False
    assert data["execution_authorized"] is False and data["authorization_status"] == "unknown"
    assert data["provenance"] == "caller-supplied-unverified" and data["pending"]
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"


def test_mocked_reader_reuses_original_deadline_budget_and_fresh_guard(monkeypatch):
    checked, frames = metadata_context()
    seen, hooks, budgets = [], [], []
    monkeypatch.setattr(preflight, "monotonic", lambda: 1000.0)

    def reader(profile, operation, *, deadline, budget, before_connect):
        assert profile == checked and deadline == 1007
        before_connect()
        response = frames[len(seen)]
        assert operation == response.operation
        seen.append(operation)
        budgets.append(budget)
        budget.used += response.wire_bytes
        return response

    monkeypatch.setattr(preflight, "read_engine", reader)
    result = preflight.observe_runtime_metadata(
        checked,
        phase_deadline=1030,
        setup_deadline=1007,
        before_query=lambda: hooks.append("guard"),
    ).to_dict()
    assert result["status"] == "metadata-match"
    assert seen == [item.operation for item in frames] and hooks == ["guard"] * 5
    assert all(budget is budgets[0] for budget in budgets)
    assert result["wire_bytes_used"] == sum(item.wire_bytes for item in frames)
    assert result["engine_contact_attempted"] is True and result["query_attempted"] == 5
    assert result["ready"] is result["runtime_invoked"] is result["execution_authorized"] is False


def test_invalid_metadata_stops_before_remaining_queries(monkeypatch):
    checked, frames = metadata_context()
    frames[1] = frame("info", {"ID": "wrong"})
    seen = []
    monkeypatch.setattr(preflight, "monotonic", lambda: 1000)

    def reader(profile, operation, *, deadline, budget, before_connect):
        before_connect()
        result = frames[len(seen)]
        seen.append(operation)
        budget.used += result.wire_bytes
        return result

    monkeypatch.setattr(preflight, "read_engine", reader)
    result = preflight.observe_runtime_metadata(
        checked, phase_deadline=1040, setup_deadline=1010
    ).to_dict()
    assert seen == ["version", "info"]
    assert result["status"] == "failed" and result["failure_reason"] == "metadata-invalid"
    assert result["query_attempted"] == 2 and result["response_count"] == 1
    assert result["wire_bytes_used"] == frames[0].wire_bytes + frames[1].wire_bytes


def test_transport_failure_keeps_partial_progress_and_independent_cleanup(monkeypatch):
    checked, frames = metadata_context()
    seen = []
    monkeypatch.setattr(preflight, "monotonic", lambda: 1000)

    def reader(profile, operation, *, deadline, budget, before_connect):
        before_connect()
        seen.append(operation)
        if operation == "info":
            budget.used += 23
            raise EngineHTTPError(
                {
                    "operation": operation,
                    "contact_attempted": True,
                    "connection_status": "connected",
                    "request_status": "sent",
                    "socket_acquisition": "handle-returned",
                    "socket_cleanup": "unconfirmed",
                    "bytes_received": 23,
                    "reason": "truncated-response",
                    "cleanup_failure": True,
                    "ignored": "never-copy-private-error-data",
                }
            )
        budget.used += frames[0].wire_bytes
        return frames[0]

    monkeypatch.setattr(preflight, "read_engine", reader)
    result = preflight.observe_runtime_metadata(checked, phase_deadline=1040, setup_deadline=1010)
    data = result.to_dict()
    assert data["status"] == "failed" and data["response_count"] == 1
    assert data["query_attempted"] == 2 and data["engine_contact_attempted"] is True
    assert data["wire_bytes_used"] == frames[0].wire_bytes + 23
    assert data["transport_diagnostic"]["reason"] == "truncated-response"
    assert data["transport_diagnostic"]["socket_cleanup"] == "unconfirmed"
    assert data["transport_diagnostic"]["cleanup_failure"] is True
    assert "never-copy-private-error-data" not in result.payload_json


def test_cancellation_preserves_original_and_attaches_bounded_observation(monkeypatch):
    checked, _ = metadata_context()
    cancelled = asyncio.CancelledError("synthetic cancellation")
    cancelled.engine_http_observation = {
        "operation": "version",
        "contact_attempted": True,
        "connection_status": "connected",
        "request_status": "sent",
        "socket_acquisition": "handle-returned",
        "socket_cleanup": "confirmed",
        "bytes_received": 1,
        "reason": "operation-failed",
        "cleanup_failure": False,
    }
    monkeypatch.setattr(preflight, "monotonic", lambda: 1000)

    def reader(profile, operation, *, deadline, budget, before_connect):
        before_connect()
        budget.used += 1
        raise cancelled

    monkeypatch.setattr(preflight, "read_engine", reader)
    with pytest.raises(asyncio.CancelledError) as caught:
        preflight.observe_runtime_metadata(checked, phase_deadline=1040, setup_deadline=1010)
    assert caught.value is cancelled
    result = caught.value.runtime_metadata_observation.to_dict()
    assert result["query_attempted"] == 1 and result["engine_contact_attempted"] is True
    assert result["transport_diagnostic"]["socket_cleanup"] == "confirmed"
    assert result["ready"] is False
