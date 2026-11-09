"""Pure synthetic session drivers; no stored model answers or actual transport."""

from __future__ import annotations

import builtins
import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_coordinator as protocol
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts import evaluation_trial_plan as planner


def frame(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def final_text(invocation):
    spec = invocation.slot.spec
    return json.dumps(
        {
            "schema_version": "0.2",
            "kind": "evaluation-invocation-response",
            "invocation_id": invocation.invocation_id,
            "response": {
                "schema_version": "0.1",
                "kind": "evaluation-comparison-response",
                "task_id": spec.task_id,
                "request_id": spec.request_id,
                "answers": [
                    {"question_id": question.id, "answer": None} for question in spec.questions
                ],
            },
        },
        indent=2,
    )


def turn_events(invocation, boundary):
    ack = {"turn": {"id": "synthetic-turn", "items": [], "status": "inProgress", "error": None}}
    item = {
        "id": "synthetic-item",
        "type": "agentMessage",
        "text": final_text(invocation),
        "phase": "final_answer",
    }
    correlation = {"threadId": boundary.thread_id, "turnId": "synthetic-turn"}
    settings = {
        "model": boundary.configuration.model,
        "modelProvider": "openai",
        "cwd": boundary.cwd,
        "effort": boundary.configuration.effort,
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
        "collaborationMode": {
            "mode": "default",
            "settings": {
                "model": boundary.configuration.model,
                "reasoning_effort": boundary.configuration.effort,
                "developer_instructions": codec.INSTRUCTIONS,
            },
        },
    }
    pairs = [
        ("thread/settings/updated", {"threadId": boundary.thread_id, "threadSettings": settings}),
        ("turn/started", {"threadId": boundary.thread_id, "turn": copy.deepcopy(ack["turn"])}),
        (
            "item/started",
            {
                **correlation,
                "startedAtMs": 1,
                "item": {"id": item["id"], "type": "agentMessage", "text": ""},
            },
        ),
        ("item/completed", {**correlation, "completedAtMs": 2, "item": item}),
        (
            "turn/completed",
            {
                "threadId": boundary.thread_id,
                "turn": {
                    "id": "synthetic-turn",
                    "items": [copy.deepcopy(item)],
                    "status": "completed",
                    "error": None,
                },
            },
        ),
    ]
    return ack, [{"method": method, "params": params} for method, params in pairs]


def reply_for(method, invocation, boundary):
    """Public synthetic builder for the separate Batch bridge integration test."""
    if method == "initialize":
        return {
            "userAgent": "codex_cli_rs/0.153.0",
            "codexHome": "/private/synthetic",
            "platformFamily": "unix",
            "platformOs": "linux",
        }
    if method == "config/read":
        config = {}
        for path, value in recipe.descriptor(boundary.configuration)["process_config"].items():
            cursor, parts = config, path.split(".")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = copy.deepcopy(value)
        config["mcp_servers"] = {}
        return {"config": config, "origins": {}}
    if method == "remoteControl/status/read":
        return {
            "installationId": "private-installation",
            "serverName": "private-server",
            "status": "disabled",
        }
    if method == "account/read":
        return {
            "requiresOpenaiAuth": True,
            "account": {"type": "chatgpt", "email": "private@example.test", "planType": "plus"},
        }
    if method == "model/list":
        return {
            "data": [
                {
                    "id": "private-model",
                    "model": boundary.configuration.model,
                    "displayName": "private display",
                    "description": "private description",
                    "hidden": False,
                    "isDefault": False,
                    "defaultReasoningEffort": boundary.configuration.effort,
                    "supportedReasoningEfforts": [
                        {
                            "reasoningEffort": boundary.configuration.effort,
                            "description": "private effort",
                        }
                    ],
                }
            ],
            "nextCursor": None,
        }
    if method == "thread/start":
        return {
            "model": boundary.configuration.model,
            "modelProvider": "openai",
            "cwd": boundary.cwd,
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "sandbox": {"type": "readOnly", "networkAccess": False},
            "reasoningEffort": boundary.configuration.effort,
            "instructionSources": [],
            "runtimeWorkspaceRoots": [],
            "thread": {
                "id": boundary.thread_id,
                "sessionId": "private-session",
                "cliVersion": "0.153.0",
                "createdAt": 1,
                "updatedAt": 2,
                "cwd": boundary.cwd,
                "modelProvider": "openai",
                "ephemeral": True,
                "preview": "",
                "projectId": None,
                "source": "appServer",
                "status": {"type": "idle"},
                "turns": [],
            },
        }
    if method == "turn/start":
        return turn_events(invocation, boundary)[0]
    raise AssertionError("unexpected synthetic method")


@pytest.fixture
def owned():
    config = planner.TrialConfig("synthetic-model", "high", 1, 30)
    invocation = codec.prepare_candidate(codec.ROOT, config).invocations[0]
    boundary = common.Boundary(config, "/synthetic/empty", "synthetic-thread")
    return invocation, boundary


@pytest.fixture
def slot(owned):
    return protocol.SlotCoordinator(*owned)


def send_reply(slot, owned, *, result=None):
    request = json.loads(slot.next_frame())
    if "id" in request:
        payload = reply_for(request["method"], *owned) if result is None else result
        slot.feed(frame({"id": request["id"], "result": payload}))
    return request


def drive_until(slot, owned, *, phase="generation", method="turn/start"):
    for _ in range(40):
        snapshot = slot.snapshot()
        if snapshot["phase"] == phase and snapshot["next_method"] == method:
            return
        if snapshot["awaiting_phase_finish"]:
            slot.finish_phase(exit_code=0, cleanup_confirmed=True)
        else:
            send_reply(slot, owned)
    raise AssertionError("bounded synthetic driver did not reach target")


def complete_turn(slot, owned, *, before_ack=False, chunks=None):
    drive_until(slot, owned)
    request = json.loads(slot.next_frame())
    ack, events = turn_events(*owned)
    response = frame({"id": request["id"], "result": ack})
    notifications = b"".join(frame(event) for event in events)
    raw = notifications + response if before_ack else response + notifications
    stride = len(raw) if chunks is None else chunks
    for start in range(0, len(raw), stride):
        slot.feed(raw[start : start + stride])


def close_failure(slot):
    assert not slot.snapshot()["outcome_ready"]
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    assert slot.snapshot()["outcome_ready"]
    assert slot.take_outcome() == {"raw": None, "failure": "integrity"}


@pytest.mark.parametrize("before_ack,chunks", [(False, None), (True, None), (False, 1), (True, 7)])
def test_full_candidate_needs_both_lifecycles_and_preserves_exact_private_raw(
    slot, owned, before_ack, chunks
):
    complete_turn(slot, owned, before_ack=before_ack, chunks=chunks)
    assert slot.snapshot()["turn_acknowledged"] is True
    assert slot.snapshot()["closed_phases"] == 1
    with pytest.raises(protocol.CoordinatorError, match="outcome-not-ready"):
        slot.take_outcome()
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    assert slot.take_outcome() == {"raw": final_text(owned[0]), "failure": None}
    with pytest.raises(protocol.CoordinatorError, match="outcome-already-taken"):
        slot.take_outcome()


def test_exact_owned_frames_discovery_eof_gate_and_generation_request_id_namespace(slot, owned):
    expected = recipe.frames(owned[0], cwd=owned[1].cwd, thread_id=owned[1].thread_id)
    for original in expected["frame_candidates"][:3]:
        raw = slot.next_frame()
        assert raw == original["frame_text"].encode()
        message = json.loads(raw)
        if "id" in message:
            slot.feed(frame({"id": message["id"], "result": reply_for(message["method"], *owned)}))
    with pytest.raises(protocol.CoordinatorError, match="frame-not-ready"):
        slot.next_frame()
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    for original in expected["frame_candidates"]:
        raw = slot.next_frame()
        assert raw == original["frame_text"].encode()
        message = json.loads(raw)
        if "id" in message:
            slot.feed(frame({"id": message["id"], "result": reply_for(message["method"], *owned)}))


@pytest.mark.parametrize("reason", protocol.ABORT_REASONS)
def test_abort_requires_lifecycle_before_one_use_failure_outcome(slot, reason):
    slot.abort(reason)
    assert slot.snapshot()["failed"] and not slot.snapshot()["outcome_ready"]
    with pytest.raises(protocol.CoordinatorError, match="slot-failed"):
        slot.next_frame()
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    assert slot.take_outcome() == {"raw": None, "failure": reason}


@pytest.mark.parametrize("reason", [None, True, [], "retry", "private-error"])
def test_bad_abort_is_mutation_free_caller_misuse(slot, reason):
    before = slot.snapshot()
    with pytest.raises(protocol.CoordinatorError, match="invalid-abort-reason"):
        slot.abort(reason)
    assert slot.snapshot() == before


@pytest.mark.parametrize("exit_code,cleanup", [(True, True), (None, True), (0, 1), (0, None)])
def test_bad_lifecycle_arguments_are_mutation_free(slot, exit_code, cleanup):
    before = slot.snapshot()
    with pytest.raises(protocol.CoordinatorError):
        slot.finish_phase(exit_code=exit_code, cleanup_confirmed=cleanup)
    assert slot.snapshot() == before


def test_primary_abort_nonzero_exit_and_unconfirmed_cleanup_stay_separate(slot):
    slot.next_frame()
    slot.abort("timeout")
    slot.finish_phase(exit_code=-15, cleanup_confirmed=False)
    snapshot = slot.snapshot()
    assert snapshot["failure"] == "timeout" and snapshot["failure_code"] == "caller-abort"
    assert snapshot["exit_failure"] is True and snapshot["cleanup_failure"] == "cleanup-unconfirmed"
    assert slot.take_outcome() == {"raw": None, "failure": "timeout"}


@pytest.mark.parametrize(
    "exit_code,cleanup,failure", [(9, True, "failed"), (0, False, "integrity")]
)
def test_valid_turn_never_releases_raw_with_failed_lifecycle(
    slot, owned, exit_code, cleanup, failure
):
    complete_turn(slot, owned)
    slot.finish_phase(exit_code=exit_code, cleanup_confirmed=cleanup)
    assert slot.take_outcome() == {"raw": None, "failure": failure}


@pytest.mark.parametrize(
    "raw",
    [
        b'{"id":2,"result":{}}\n',
        b'{"id":true,"result":{}}\n',
        b"{invalid}\n",
        b'{"id":1,"error":{"message":"private"}}\n',
        b'{"method":"warning","params":{}}\n',
    ],
)
def test_wire_failures_latch_and_cannot_salvage_or_restart_before_cleanup(slot, raw):
    slot.next_frame()
    with pytest.raises(protocol.CoordinatorError, match="wire-rejected"):
        slot.feed(raw)
    with pytest.raises(protocol.CoordinatorError, match="slot-failed"):
        slot.feed(b"{}\n")
    close_failure(slot)


def test_receive_before_emission_and_allowlisted_premature_notifications_are_rejected(slot):
    with pytest.raises(protocol.CoordinatorError, match="receive-before-request"):
        slot.feed(b"{}\n")
    close_failure(slot)


def test_partial_future_response_cannot_be_buffered_between_owned_requests(slot, owned):
    send_reply(slot, owned)
    with pytest.raises(protocol.CoordinatorError, match="receive-outside-request"):
        slot.feed(b'{"id":2,')
    close_failure(slot)


def test_partial_future_response_in_ack_chunk_cannot_be_reused_after_arm(slot, owned):
    message = json.loads(slot.next_frame())
    raw = frame({"id": message["id"], "result": reply_for("initialize", *owned)}) + b'{"id":2,'
    with pytest.raises(protocol.CoordinatorError, match="receive-outside-request"):
        slot.feed(raw)
    close_failure(slot)


def test_fragmented_current_response_remains_valid_and_incomplete_eof_does_not(slot, owned):
    request = json.loads(slot.next_frame())
    raw = frame({"id": request["id"], "result": reply_for("initialize", *owned)})
    slot.feed(raw[:11])
    slot.feed(raw[11:])
    assert slot.snapshot()["next_method"] == "initialized"
    slot.next_frame()
    slot.next_frame()
    slot.feed(b'{"id":2,')
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    assert slot.take_outcome()["failure"] == "integrity"


def test_mcp_discovery_generation_names_must_match_and_disabled_marker_is_required(slot, owned):
    drive_until(slot, owned, phase="discovery", method="config/read")
    before = reply_for("config/read", *owned)
    before["config"]["mcp_servers"] = {"private-inherited": {"enabled": True}}
    send_reply(slot, owned, result=before)
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    drive_until(slot, owned, method="config/read")
    with pytest.raises(protocol.CoordinatorError, match="semantic-rejected"):
        send_reply(slot, owned)
    close_failure(slot)


def test_pagination_consumes_exact_prior_cursor_and_increases_rpc_ids(slot, owned):
    drive_until(slot, owned, method="model/list")
    first = send_reply(slot, owned, result={"data": [], "nextCursor": "opaque-private-cursor"})
    second = json.loads(slot.next_frame())
    assert second["id"] == first["id"] + 1
    assert second["params"] == {
        "limit": 100,
        "includeHidden": False,
        "cursor": "opaque-private-cursor",
    }
    slot.feed(frame({"id": second["id"], "result": reply_for("model/list", *owned)}))
    assert slot.snapshot()["next_method"] == "thread/start"
    assert slot.snapshot()["catalog_pages"] == 2


@pytest.mark.parametrize("fault", ["cycle", "too-many", "missing-model", "too-many-entries"])
def test_bad_catalog_never_emits_thread_or_turn(slot, owned, fault):
    drive_until(slot, owned, method="model/list")
    if fault == "cycle":
        send_reply(slot, owned, result={"data": [], "nextCursor": "same"})
        result = {"data": [], "nextCursor": "same"}
    elif fault == "too-many":
        for index in range(9):
            send_reply(slot, owned, result={"data": [], "nextCursor": f"cursor-{index}"})
        result = {"data": [], "nextCursor": "another"}
    elif fault == "too-many-entries":
        result = {"data": [{}] * 101, "nextCursor": None}
    else:
        result = {"data": [], "nextCursor": None}
    with pytest.raises(protocol.CoordinatorError, match="semantic-rejected"):
        send_reply(slot, owned, result=result)
    assert slot.snapshot()["turn_acknowledged"] is False
    close_failure(slot)


@pytest.mark.parametrize("fault", ["foreign", "failed", "phase", "bad-json", "trailing"])
def test_final_semantics_and_invocation_binding_are_required(slot, owned, fault):
    drive_until(slot, owned)
    request = json.loads(slot.next_frame())
    ack, events = turn_events(*owned)
    if fault == "foreign":
        events[-1]["params"]["threadId"] = "foreign"
    elif fault == "failed":
        events[-1]["params"]["turn"]["status"] = "failed"
    elif fault == "phase":
        events[-2]["params"]["item"]["phase"] = None
    elif fault == "bad-json":
        events[-2]["params"]["item"]["text"] = "private-invalid"
        events[-1]["params"]["turn"]["items"][0]["text"] = "private-invalid"
    else:
        events.append(copy.deepcopy(events[-1]))
    expected = "receive-outside-request" if fault == "trailing" else "semantic-rejected"
    with pytest.raises(protocol.CoordinatorError, match=expected):
        slot.feed(
            frame({"id": request["id"], "result": ack}) + b"".join(frame(event) for event in events)
        )
    close_failure(slot)


def test_trailing_bytes_after_matched_turn_fail_before_outcome(slot, owned):
    complete_turn(slot, owned)
    with pytest.raises(protocol.CoordinatorError, match="receive-outside-request"):
        slot.feed(b"{")
    close_failure(slot)


@pytest.mark.parametrize(
    "fault", ["malformed", "duplicate", "unknown", "error", "oversized", "unsupported-event"]
)
def test_ack_then_failure_is_independent_of_caller_read_partition(owned, fault):
    observed = []
    for partition in ("coalesced", "split", "fragmented"):
        slot = protocol.SlotCoordinator(*owned)
        drive_until(slot, owned)
        request = json.loads(slot.next_frame())
        ack = frame({"id": request["id"], "result": turn_events(*owned)[0]})
        tails = {
            "malformed": b"{private-invalid-json\n",
            "duplicate": ack,
            "unknown": frame({"method": "warning", "params": {"message": "private"}}),
            "error": frame({"id": request["id"], "error": {"message": "private"}}),
            "oversized": b'{"private":"' + b"x" * protocol.wire.MAX_FRAME_BYTES + b'"}\n',
            "unsupported-event": frame({"method": "thread/status/changed", "params": {}}),
        }
        tail = tails[fault]
        chunks = (ack + tail,) if partition == "coalesced" else (ack, tail)
        if partition == "fragmented":
            chunks = (ack[:9], ack[9:], tail[:5], tail[5:])
        with pytest.raises(protocol.CoordinatorError):
            for chunk in chunks:
                slot.feed(chunk)
        snapshot = slot.snapshot()
        assert snapshot["turn_acknowledged"] is True
        assert snapshot["stream_bytes"] <= protocol.wire.MAX_STREAM_BYTES
        assert snapshot["received_events"] <= protocol.wire.MAX_EVENTS
        slot.finish_phase(exit_code=0, cleanup_confirmed=True)
        outcome = slot.take_outcome()
        assert outcome == {"raw": None, "failure": "integrity"}
        observed.append(
            (snapshot["turn_acknowledged"], snapshot["failure"], snapshot["failure_code"], outcome)
        )
    assert observed[0] == observed[1] == observed[2]


def test_huge_coalesced_caller_tail_uses_bounded_segments_and_stops_at_first_failure(
    owned, monkeypatch
):
    slot = protocol.SlotCoordinator(*owned)
    drive_until(slot, owned)
    request = json.loads(slot.next_frame())
    ack = frame({"id": request["id"], "result": turn_events(*owned)[0]})
    original = protocol.wire.RpcInbox.feed
    sizes = []

    def bounded_feed(inbox, chunk):
        sizes.append(len(chunk))
        assert len(chunk) <= protocol.wire.MAX_FRAME_BYTES + 1
        return original(inbox, chunk)

    monkeypatch.setattr(protocol.wire.RpcInbox, "feed", bounded_feed)
    huge = b"x" * (protocol.wire.MAX_FRAME_BYTES * 8)
    with pytest.raises(protocol.CoordinatorError, match="wire-rejected"):
        slot.feed(ack + huge + ack)
    assert sizes == [len(ack), protocol.wire.MAX_FRAME_BYTES + 1]
    assert slot.snapshot()["turn_acknowledged"] is True
    close_failure(slot)


def test_candidate_mutation_is_latched_before_emission_and_before_final_handoff(slot, owned):
    complete_turn(slot, owned)
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    object.__setattr__(owned[1], "cwd", "/different")
    assert slot.take_outcome() == {"raw": None, "failure": "integrity"}
    assert slot.snapshot()["failure_code"] == "candidate-changed"


def test_single_owner_cannot_be_copied_to_duplicate_outcome_consumption(slot):
    for function in (copy.copy, copy.deepcopy):
        with pytest.raises(protocol.CoordinatorError, match="coordinator-copy-unsupported"):
            function(slot)


def test_shared_budget_counts_survive_discovery_restart_and_snapshot_is_redacted(slot, owned):
    drive_until(slot, owned, method="initialize")
    first = slot.snapshot()
    assert first["received_events"] == 2 and first["stream_bytes"] > 0
    send_reply(slot, owned)
    assert slot.snapshot()["received_events"] == 3
    encoded = json.dumps(slot.snapshot())
    for private in (
        owned[0].invocation_id,
        owned[1].thread_id,
        owned[1].cwd,
        "sha256",
        "private-session",
    ):
        assert private not in encoded
    for key in (
        "runtime_observed",
        "provider_freshness_verified",
        "authenticated",
        "accepted_trial",
        "ready_for_live_trial",
        "execution_authorized",
        "live_configuration_frozen",
        "timer_enforced",
        "cleanup_verified",
        "entitlement_verified",
    ):
        assert slot.snapshot()[key] is False


def test_pure_complete_driver_never_reads_io_process_account_network_or_reference_answers(
    slot, owned, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("pure slot coordinator must not access external state")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(codec.collector.secrets, "token_hex", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "load_reference", forbidden)
    monkeypatch.setattr(planner.comparison.reference, "score_reference", forbidden)
    complete_turn(slot, owned)
    slot.finish_phase(exit_code=0, cleanup_confirmed=True)
    assert slot.take_outcome()["failure"] is None
