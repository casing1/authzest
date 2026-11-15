"""Endpoint bootstrap with synthetic frames and memory sockets only."""

from __future__ import annotations

import copy
import socket
from dataclasses import FrozenInstanceError

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _generated_repair_bootstrap as bootstrap
from authzest.runner import _generated_repair_engine_http as engine
from authzest.runner._generated_repair_preflight import engine_identity_sha256
from test_generated_repair_engine_http import PIN, MemorySocket, response
from test_generated_repair_preflight import no_external_effects  # noqa: F401

ENDPOINT = "unix:///reviewed/run/docker.sock"


@pytest.fixture(autouse=True)
def synthetic_endpoint_pin(monkeypatch):
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: copy.deepcopy(PIN))


def frames(arch="arm64"):
    values = [
        {
            "Version": "synthetic-29",
            "ApiVersion": "1.52",
            "MinAPIVersion": "1.44",
            "Os": "linux",
            "Arch": arch,
            "Ignored": "synthetic-extra-is-not-published",
        },
        {
            "ID": "synthetic-bootstrap-daemon",
            "ServerVersion": "synthetic-29",
            "OSType": "linux",
            "Architecture": "aarch64" if arch == "arm64" else "x86_64",
            "CgroupVersion": "2",
            "CgroupDriver": "systemd",
            "DefaultRuntime": "runc",
            "SecurityOptions": ["name=seccomp,profile=builtin"],
            "MemoryLimit": True,
            "SwapLimit": False,
            "PidsLimit": True,
        },
    ]
    return [
        engine.EngineResponse(operation, body, len(body) + 80, copy.deepcopy(PIN))
        for operation, body in (
            ("version", canonical(values[0]).encode()),
            ("info", canonical(values[1]).encode()),
        )
    ]


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_supplied_bootstrap_metadata_never_manufactures_a_profile_or_readiness(arch):
    observation = bootstrap.normalize_engine_bootstrap(ENDPOINT, frames(arch))
    data = observation.to_dict()
    assert data["kind"] == "generated-repair-engine-bootstrap-observation"
    assert data["status"] == "metadata-observed-unpinned"
    assert data["metadata"]["version"]["selected_api_version"] == "1.51"
    assert data["metadata"]["engine"]["architecture"] == arch
    assert data["metadata"]["engine"]["observed_identity_sha256"] == engine_identity_sha256(
        "synthetic-bootstrap-daemon"
    )
    for key in (
        "identity_pinned",
        "images_inspected",
        "profile_created",
        "runtime_invoked",
        "generated_runtime_invoked",
        "execution_authorized",
        "verified_fix",
        "ready",
    ):
        assert data[key] is False
    assert data["engine_contact_attempted"] is None
    assert data["query_attempted"] == 0
    assert "profile_id" not in data and "images" not in data["metadata"]
    assert "synthetic-extra-is-not-published" not in observation.payload_json
    assert data["provenance"] == "caller-supplied-unverified"
    with pytest.raises(FrozenInstanceError):
        observation.payload_json = "{}"


@pytest.mark.parametrize("operation,target", [("version", "/version"), ("info", "/v1.51/info")])
def test_bootstrap_transport_uses_the_shared_fixed_reader_without_full_profile(
    monkeypatch, operation, target
):
    connection = MemorySocket(response())
    constructed = []

    def create(*args, **kwargs):
        constructed.append((args, kwargs))
        return connection

    monkeypatch.setattr(engine.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(engine, "_endpoint_identity", lambda path: copy.deepcopy(PIN))
    monkeypatch.setattr(socket, "socket", create)
    budget = engine.WireBudget()
    result = engine.read_engine_bootstrap(ENDPOINT, operation, deadline=109, budget=budget)
    assert result.body == b'{"synthetic":true}'
    assert result.wire_bytes == budget.used
    assert result.operation == operation
    assert constructed == [((socket.AF_UNIX, socket.SOCK_STREAM), {})]
    assert connection.connected == [ENDPOINT[7:]] and connection.closed == 1
    assert connection.sent[0].split(b"\r\n", 1)[0] == ("GET " + target + " HTTP/1.1").encode()


def test_live_observer_uses_two_current_guards_and_one_original_budget(monkeypatch):
    supplied = frames()
    now, calls, guards = [100.0], [], []
    monkeypatch.setattr(bootstrap, "monotonic", lambda: now[0])

    def reader(endpoint, operation, *, deadline, budget, before_connect):
        assert endpoint == ENDPOINT and deadline == 109
        before_connect()
        result = supplied[len(calls)]
        budget.used += result.wire_bytes
        calls.append((operation, id(budget)))
        now[0] += 2
        return result

    monkeypatch.setattr(bootstrap, "read_engine_bootstrap", reader)
    data = bootstrap.observe_engine_bootstrap(
        ENDPOINT,
        phase_deadline=139,
        setup_deadline=109,
        before_query=lambda: guards.append(now[0]),
    ).to_dict()
    assert [item[0] for item in calls] == ["version", "info"]
    assert calls[0][1] == calls[1][1]
    assert guards == [100.0, 102.0]
    assert data["status"] == "metadata-observed-unpinned"
    assert data["engine_contact_attempted"] is True and data["query_attempted"] == 2
    assert data["response_count"] == 2
    assert data["wire_bytes_used"] == sum(frame.wire_bytes for frame in supplied)


@pytest.mark.parametrize("unsupported", ["old-api", "new-minimum", "windows", "unknown-arch"])
def test_unsupported_version_stops_before_any_info_query(monkeypatch, unsupported):
    supplied = frames()
    import json

    body = json.loads(supplied[0].body)
    if unsupported == "old-api":
        body["ApiVersion"] = "1.50"
    elif unsupported == "new-minimum":
        body["MinAPIVersion"] = "1.52"
    elif unsupported == "windows":
        body["Os"] = "windows"
    else:
        body["Arch"] = "unknown"
    body = canonical(body).encode()
    supplied[0] = engine.EngineResponse("version", body, len(body) + 80, copy.deepcopy(PIN))
    calls = []
    monkeypatch.setattr(bootstrap, "monotonic", lambda: 100.0)

    def reader(endpoint, operation, *, deadline, budget, before_connect):
        before_connect()
        calls.append(operation)
        budget.used += supplied[0].wire_bytes
        return supplied[0]

    monkeypatch.setattr(bootstrap, "read_engine_bootstrap", reader)
    data = bootstrap.observe_engine_bootstrap(
        ENDPOINT, phase_deadline=139, setup_deadline=109
    ).to_dict()
    assert calls == ["version"]
    assert data["status"] == "unsupported" and data["ready"] is False
    assert data["wire_bytes_used"] == supplied[0].wire_bytes
    assert data["failure_reason"] == (
        "api-version-unsupported"
        if unsupported in {"old-api", "new-minimum"}
        else "engine-platform-unsupported"
    )


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_first_cancellation_preserves_its_bootstrap_observation(monkeypatch, exception):
    cancellation = exception("synthetic cancellation")
    cancellation.engine_http_observation = {
        "contact_attempted": True,
        "socket_cleanup": "unconfirmed",
        "bytes_received": 4,
        "reason": "operation-failed",
    }
    monkeypatch.setattr(bootstrap, "monotonic", lambda: 100.0)

    def reader(endpoint, operation, *, deadline, budget, before_connect):
        before_connect()
        budget.used = 4
        raise cancellation

    monkeypatch.setattr(bootstrap, "read_engine_bootstrap", reader)
    with pytest.raises(exception) as caught:
        bootstrap.observe_engine_bootstrap(ENDPOINT, phase_deadline=139, setup_deadline=109)
    assert caught.value is cancellation
    data = cancellation.engine_bootstrap_observation.to_dict()
    assert data["status"] == "failed" and data["engine_contact_attempted"] is True
    assert data["transport_diagnostic"]["socket_cleanup"] == "unconfirmed"
    assert data["wire_bytes_used"] == 4 and data["ready"] is False
