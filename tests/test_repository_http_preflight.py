"""HTTP-only supplied or mocked Engine metadata only; no socket, Docker, CLI or guest."""

from __future__ import annotations

import asyncio
import builtins
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _repository_http_preflight as preflight
from authzest.runner._generated_repair_engine_http import EngineHTTPError
from helpers.repository_http_engine_data import PIN, frame, metadata_context


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
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)


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
    assert data["status"] == "metadata-match" and data["response_count"] == 4
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
    assert seen == [item.operation for item in frames] and hooks == ["guard"] * 4
    assert all(budget is budgets[0] for budget in budgets)
    assert result["wire_bytes_used"] == sum(item.wire_bytes for item in frames)
    assert result["engine_contact_attempted"] is True and result["query_attempted"] == 4
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


def test_new_observation_is_distinct_and_saved_metadata_is_not_a_profile():
    from authzest.codex.contracts import ContractError
    from authzest.runner._generated_repair_runtime_profile import RuntimeProfile

    checked, frames = metadata_context()
    result = preflight.normalize_runtime_metadata(checked, frames)
    data = result.to_dict()
    assert data["schema_version"] == "2.0"
    assert data["kind"] == "repository-http-runtime-metadata-observation"
    assert result.observation_id.startswith("repository-http-runtime-metadata-observation-")
    assert set(data["metadata"]["images"]) == {"A", "B"}
    for supplied in (data, result, RuntimeProfile(checked.payload_json)):
        with pytest.raises(ContractError):
            preflight.normalize_runtime_metadata(supplied, frames)


def test_profile_changes_after_reader_guard_cannot_be_reported_as_match(monkeypatch):
    checked, frames = metadata_context()
    monkeypatch.setattr(preflight, "monotonic", lambda: 100.0)
    value = checked.to_dict()
    value["engine"]["api_version"] = "1.48"
    seen = []

    def reader(profile, operation, *, deadline, budget, before_connect):
        before_connect()
        seen.append(operation)
        budget.used += frames[0].wire_bytes
        object.__setattr__(checked, "payload_json", canonical(value))
        return frames[0]

    monkeypatch.setattr(preflight, "read_engine", reader)
    data = preflight.observe_runtime_metadata(
        checked, phase_deadline=140, setup_deadline=110
    ).to_dict()
    assert seen == ["version"]
    assert data["status"] == "failed" and data["response_count"] == 0
    assert data["ready"] is data["verified_fix"] is False


def test_async_current_hook_is_not_awaited_or_dispatched(monkeypatch):
    checked, _ = metadata_context()
    monkeypatch.setattr(preflight, "monotonic", lambda: 100.0)
    queries, calls = [], []

    async def hook():
        calls.append(True)

    def reader(*args, **kwargs):
        queries.append(True)
        raise AssertionError("invalid hook must refuse before dispatch")

    monkeypatch.setattr(preflight, "read_engine", reader)
    data = preflight.observe_runtime_metadata(
        checked, phase_deadline=140, setup_deadline=110, before_query=hook
    ).to_dict()
    assert calls == queries == []
    assert data["status"] == "failed" and data["engine_contact_attempted"] is False


def test_image_config_ids_and_platform_manifest_digests_remain_distinct():
    from tests.helpers.repository_http_container_data import MANIFEST_DIGESTS

    checked, frames = metadata_context()
    result = preflight.normalize_runtime_metadata(checked, frames).to_dict()
    for role in ("A", "B"):
        image = result["metadata"]["images"][role]
        assert image["image_id"] == checked.to_dict()["images"][role]["image_id"]
        assert image["manifest_descriptor"]["digest"] == MANIFEST_DIGESTS[role]
        assert image["manifest_descriptor"]["digest"] != image["image_id"]
        assert image["platform_manifest_reported"] is True
    assert result["ready"] is result["verified_fix"] is result["execution_authorized"] is False
    assert (
        "independently-reviewed-platform-manifest-pin-and-config-id-correspondence"
        in result["pending"]
    )


@pytest.mark.parametrize("kind", ["absent", "null", "no-platform", "null-platform"])
def test_absent_descriptor_or_platform_never_falls_back_to_config_id(kind):
    from authzest.codex.contracts import decode

    checked, frames = metadata_context()
    body = decode(frames[2].body.decode())
    if kind == "absent":
        del body["Descriptor"]
    elif kind == "null":
        body["Descriptor"] = None
    elif kind == "no-platform":
        del body["Descriptor"]["platform"]
    else:
        body["Descriptor"]["platform"] = None
    frames[2] = frame("image-A", body)
    result = preflight.normalize_runtime_metadata(checked, frames).to_dict()
    image = result["metadata"]["images"]["A"]
    assert result["status"] == "metadata-match"
    assert image["platform_manifest_reported"] is False
    if kind in {"absent", "null"}:
        assert image["manifest_descriptor"] is None
    else:
        assert image["manifest_descriptor"]["platform"] is None
        assert image["manifest_descriptor"]["digest"] != image["image_id"]
    assert result["ready"] is result["verified_fix"] is False


@pytest.mark.parametrize(
    "media_type",
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    ],
    ids=["oci-index", "docker-list"],
)
def test_index_or_manifest_list_is_recorded_without_becoming_a_platform_manifest(media_type):
    from authzest.codex.contracts import decode

    checked, frames = metadata_context()
    body = decode(frames[2].body.decode())
    body["Descriptor"]["mediaType"] = media_type
    # Even explicit matching platform metadata cannot turn an index into a
    # single-platform manifest or an independently accepted pin.
    frames[2] = frame("image-A", body)
    result = preflight.normalize_runtime_metadata(checked, frames).to_dict()
    image = result["metadata"]["images"]["A"]
    assert image["manifest_descriptor"]["mediaType"] == media_type
    assert image["platform_manifest_reported"] is False
    assert image["manifest_descriptor"]["digest"] != image["image_id"]
    assert result["ready"] is result["execution_authorized"] is False


@pytest.mark.parametrize(
    "platform",
    [
        {"os": "linux", "architecture": "amd64"},
        {"os": "windows", "architecture": "arm64"},
        {"os": "linux", "architecture": "arm64", "variant": "v7"},
    ],
    ids=["other-architecture", "other-os", "other-variant"],
)
def test_other_platform_descriptor_is_reported_without_a_matching_platform_claim(platform):
    from authzest.codex.contracts import decode

    checked, frames = metadata_context()
    body = decode(frames[2].body.decode())
    body["Descriptor"]["platform"] = platform
    frames[2] = frame("image-A", body)
    image = preflight.normalize_runtime_metadata(checked, frames).to_dict()["metadata"]["images"][
        "A"
    ]
    assert image["manifest_descriptor"]["platform"] == platform
    assert image["platform_manifest_reported"] is False


def test_descriptor_projection_is_detached_and_keeps_only_bounded_selected_fields():
    from authzest.codex.contracts import decode

    checked, frames = metadata_context()
    body = decode(frames[2].body.decode())
    body["Descriptor"]["annotations"] = {"ignored": "not-selected"}
    body["Descriptor"]["platform"].update(
        {"os.version": "", "os.features": ["synthetic"], "features": []}
    )
    frames[2] = frame("image-A", body)
    result = preflight.normalize_runtime_metadata(checked, frames)
    value = result.to_dict()["metadata"]["images"]["A"]
    descriptor = value["manifest_descriptor"]
    assert set(descriptor) == {"digest", "mediaType", "size", "platform"}
    assert descriptor["platform"]["os.features"] == ["synthetic"]
    assert value["platform_manifest_reported"] is True
    assert "not-selected" not in result.payload_json
    descriptor["digest"] = "changed detached dictionary"
    assert (
        result.to_dict()["metadata"]["images"]["A"]["manifest_descriptor"]["digest"]
        != descriptor["digest"]
    )
