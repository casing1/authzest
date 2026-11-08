"""Synthetic selected transcripts prove matching only, never a live model trial."""

from __future__ import annotations

import builtins
import copy
import json
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts import evaluation_trial_plan as planner
from scripts import evaluation_turn_semantics as turns


@pytest.fixture
def invocation():
    configuration = planner.TrialConfig("synthetic-model", "medium", 1, 30)
    # Preparation reads only the repository-owned public tasks, never reference answers.
    return codec.prepare_candidate(codec.ROOT, configuration).invocations[0]


@pytest.fixture
def boundary(invocation):
    return common.Boundary(invocation.session.configuration, "/synthetic/cwd", "synthetic-thread")


def response(invocation) -> dict:
    spec = invocation.slot.spec
    return {
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
    }


def settings(boundary) -> dict:
    return {
        "threadId": boundary.thread_id,
        "threadSettings": {
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "cwd": boundary.cwd,
            "model": boundary.configuration.model,
            "modelProvider": "openai",
            "effort": boundary.configuration.effort,
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "collaborationMode": {
                "mode": "default",
                "settings": {
                    "model": boundary.configuration.model,
                    "reasoning_effort": boundary.configuration.effort,
                    "developer_instructions": codec.INSTRUCTIONS,
                },
            },
        },
    }


def event(method: str, params: dict) -> dict:
    return {"method": method, "params": params}


def transcript(invocation, boundary, *, deltas: bool = False):
    start = {"turn": {"id": "synthetic-turn", "items": [], "status": "inProgress", "error": None}}
    item = {
        "id": "synthetic-item",
        "type": "agentMessage",
        "text": json.dumps(response(invocation), ensure_ascii=False),
        "phase": "final_answer",
    }
    correlation = {"threadId": boundary.thread_id, "turnId": start["turn"]["id"]}
    events = [
        event("thread/settings/updated", settings(boundary)),
        event(
            "turn/started", {"threadId": boundary.thread_id, "turn": copy.deepcopy(start["turn"])}
        ),
        event(
            "item/started",
            {
                **correlation,
                "item": {"id": item["id"], "type": "agentMessage", "text": ""},
                "startedAtMs": 1000,
            },
        ),
    ]
    if deltas:
        midpoint = len(item["text"]) // 2
        for text in (item["text"][:midpoint], item["text"][midpoint:]):
            events.append(
                event(
                    "item/agentMessage/delta",
                    {**correlation, "itemId": item["id"], "delta": text},
                )
            )
    events.extend(
        [
            event("item/completed", {**correlation, "item": item, "completedAtMs": 1001}),
            event(
                "turn/completed",
                {
                    "threadId": boundary.thread_id,
                    "turn": {
                        "id": start["turn"]["id"],
                        "items": [copy.deepcopy(item)],
                        "status": "completed",
                        "error": None,
                    },
                },
            ),
        ]
    )
    return start, events


def set_path(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def replace_text(events, text):
    events[-2]["params"]["item"]["text"] = text
    events[-1]["params"]["turn"]["items"][0]["text"] = text


@pytest.mark.parametrize("deltas", [False, True])
def test_matches_complete_unknown_answers_without_claiming_live_acceptance(
    invocation, boundary, deltas
):
    start, events = transcript(invocation, boundary, deltas=deltas)
    original = copy.deepcopy((start, events))
    summary = turns.check_turn(invocation, boundary, start, events)
    assert summary["supplied_fields_match"] is True
    assert summary["events_count"] == (7 if deltas else 5)
    assert summary["deltas_count"] == (2 if deltas else 0)
    assert summary["answer_fields_count"] == len(invocation.slot.spec.questions)
    assert summary["unknown_answer_fields_count"] == summary["answer_fields_count"]
    for key, value in common.limitations().items():
        assert summary[key] == value
    assert (start, events) == original
    rendered = json.dumps(summary)
    for private in (
        boundary.cwd,
        boundary.thread_id,
        boundary.configuration.model,
        invocation.invocation_id,
        invocation.slot.spec.request_id,
        "synthetic-turn",
        "synthetic-item",
        events[-2]["params"]["item"]["text"],
    ):
        assert private not in rendered


def test_normalizes_only_selected_optional_nulls_and_full_view(invocation, boundary):
    start, events = transcript(invocation, boundary)
    events[1]["params"]["turn"].update(
        itemsView="full", startedAt=None, completedAt=None, durationMs=None
    )
    events[-2]["params"]["item"].update(delivery=None, memoryCitation=None, questions=None)
    events[-1]["params"]["turn"].update(itemsView="full")
    assert turns.check_turn(invocation, boundary, start, events)["items_count"] == 1


def test_candidate_timestamps_only_match_without_timing_proof(invocation, boundary):
    start, events = transcript(invocation, boundary)
    start["turn"]["startedAt"] = events[1]["params"]["turn"]["startedAt"] = 1
    events[-1]["params"]["turn"].update(startedAt=1, completedAt=2, durationMs=1000)
    summary = turns.check_turn(invocation, boundary, start, events)
    assert summary["timing_verified"] is False


def test_check_has_no_file_process_network_or_entropy_access(invocation, boundary, monkeypatch):
    start, events = transcript(invocation, boundary)

    def forbidden(*args, **kwargs):
        pytest.fail("pure turn validation must not access external effects")

    with monkeypatch.context() as scoped:
        scoped.setattr(builtins, "open", forbidden)
        scoped.setattr(Path, "read_text", forbidden)
        scoped.setattr(Path, "read_bytes", forbidden)
        scoped.setattr(subprocess, "Popen", forbidden)
        scoped.setattr(subprocess, "run", forbidden)
        scoped.setattr(socket, "socket", forbidden)
        scoped.setattr(socket, "create_connection", forbidden)
        scoped.setattr(codec.collector.secrets, "token_hex", forbidden)
        result = turns.check_turn(invocation, boundary, start, events)
    assert result["actual_model_calls"] == 0


@pytest.mark.parametrize(
    ("path", "replacement", "code"),
    [
        ((0, "params", "threadId"), "foreign", "thread-id-mismatch"),
        ((1, "params", "threadId"), "foreign", "thread-mismatch"),
        ((1, "params", "turn", "id"), "foreign", "turn-start-mismatch"),
        ((2, "params", "threadId"), "foreign", "thread-mismatch"),
        ((2, "params", "turnId"), "foreign", "turn-mismatch"),
        ((3, "params", "threadId"), "foreign", "thread-mismatch"),
        ((3, "params", "turnId"), "foreign", "turn-mismatch"),
        ((3, "params", "item", "id"), "foreign", "item-mismatch"),
        ((4, "params", "threadId"), "foreign", "thread-mismatch"),
        ((4, "params", "turn", "id"), "foreign", "turn-mismatch"),
        ((4, "params", "turn", "items", 0, "text"), "foreign", "completed-snapshot-mismatch"),
        ((4, "params", "turn", "items", 0, "id"), "foreign", "completed-snapshot-mismatch"),
        ((4, "params", "turn", "items"), [], "unsupported-turn-items"),
        ((4, "params", "turn", "status"), "failed", "turn-status-mismatch"),
        ((4, "params", "turn", "status"), "interrupted", "turn-status-mismatch"),
        ((4, "params", "turn", "error"), {"message": "private"}, "turn-error"),
        ((3, "params", "item", "phase"), None, "explicit-final-answer-required"),
        ((3, "params", "item", "phase"), "commentary", "explicit-final-answer-required"),
        ((3, "params", "item", "delivery"), "async", "unsupported-item-context"),
        ((3, "params", "item", "memoryCitation"), {}, "unsupported-item-context"),
        ((3, "params", "item", "questions"), [], "unsupported-item-context"),
        ((3, "params", "item", "type"), "reasoning", "unsupported-item-type"),
        ((3, "params", "item", "type"), "commandExecution", "unsupported-item-type"),
        ((2, "params", "item", "text"), "nonempty", "unsupported-item-start"),
        ((2, "params", "item", "phase"), "commentary", "unsupported-item-start"),
        ((4, "params", "turn", "itemsView"), "summary", "unsupported-items-view"),
        ((4, "params", "turn", "startedAt"), 2, "turn-start-time-mismatch"),
        ((0, "params", "threadSettings", "model"), "wrong", "boundary-mismatch"),
        ((0, "params", "threadSettings", "effort"), None, "boundary-mismatch"),
        (
            (0, "params", "threadSettings", "sandboxPolicy", "networkAccess"),
            True,
            "sandbox-mismatch",
        ),
    ],
)
def test_refuses_mismatched_or_unsupported_selected_fields(
    invocation, boundary, path, replacement, code
):
    start, events = transcript(invocation, boundary)
    set_path(events, path, replacement)
    original = copy.deepcopy((start, events))
    with pytest.raises(common.SemanticError, match=f"^{code}$"):
        turns.check_turn(invocation, boundary, start, events)
    assert (start, events) == original


@pytest.mark.parametrize("index", range(5))
def test_duplicate_events_never_silently_overwrite_prior_observation(invocation, boundary, index):
    start, events = transcript(invocation, boundary)
    events.insert(index + 1, copy.deepcopy(events[index]))
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize("index", range(5))
def test_missing_required_event_is_refused(invocation, boundary, index):
    start, events = transcript(invocation, boundary)
    del events[index]
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize("left,right", [(0, 1), (0, 3), (1, 2), (2, 3), (3, 4)])
def test_late_settings_and_other_reordered_events_are_refused(invocation, boundary, left, right):
    start, events = transcript(invocation, boundary)
    events[left], events[right] = events[right], events[left]
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize(
    "method",
    [
        "thread/status/changed",
        "thread/tokenUsage/updated",
        "item/reasoning/textDelta",
        "item/commandExecution/outputDelta",
        "item/commandExecution/requestApproval",
        "warning",
        "error",
        "turn/retry",
        "future/notification",
    ],
)
def test_unreviewed_events_are_unsupported_not_full_protocol_acceptance(
    invocation, boundary, method
):
    start, events = transcript(invocation, boundary)
    events.insert(3, event(method, {}))
    with pytest.raises(common.SemanticError, match="^unsupported-event$"):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize("timestamp", [None, True, 1.5, -1, 2**63, "1000"])
@pytest.mark.parametrize("index,field", [(2, "startedAtMs"), (3, "completedAtMs")])
def test_item_timestamp_requires_selected_nonnegative_int64(
    invocation, boundary, timestamp, index, field
):
    start, events = transcript(invocation, boundary)
    events[index]["params"][field] = timestamp
    with pytest.raises(common.SemanticError, match="^invalid-timestamp$"):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize("index,field", [(2, "startedAtMs"), (3, "completedAtMs")])
def test_required_item_timestamp_may_not_be_omitted(invocation, boundary, index, field):
    start, events = transcript(invocation, boundary)
    del events[index]["params"][field]
    with pytest.raises(common.SemanticError, match="^missing-selected-fields$"):
        turns.check_turn(invocation, boundary, start, events)


def test_reverse_item_timestamp_is_refused(invocation, boundary):
    start, events = transcript(invocation, boundary)
    events[3]["params"]["completedAtMs"] = 999
    with pytest.raises(common.SemanticError, match="^timestamp-order-mismatch$"):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize(
    "field,value",
    [
        ("threadId", "foreign"),
        ("turnId", "foreign"),
        ("itemId", "foreign"),
        ("delta", "wrong"),
        ("delta", 7),
    ],
)
def test_delta_correlation_and_exact_concatenation(invocation, boundary, field, value):
    start, events = transcript(invocation, boundary, deltas=True)
    events[3]["params"][field] = value
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize("mode", ["lost", "duplicated", "before-item", "after-item"])
def test_delta_loss_duplication_and_late_delivery_are_not_accepted(invocation, boundary, mode):
    start, events = transcript(invocation, boundary, deltas=True)
    if mode == "lost":
        del events[3]
    elif mode == "duplicated":
        events.insert(4, copy.deepcopy(events[3]))
    elif mode == "before-item":
        events[2], events[3] = events[3], events[2]
    else:
        events[4], events[5] = events[5], events[4]
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, events)


def test_zero_length_delta_does_not_infer_a_final_answer(invocation, boundary):
    start, events = transcript(invocation, boundary, deltas=True)
    events[3]["params"]["delta"] = events[4]["params"]["delta"] = ""
    with pytest.raises(common.SemanticError, match="^delta-text-mismatch$"):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize(
    "mode",
    [
        "stale-invocation",
        "foreign-task",
        "foreign-request",
        "missing-answer",
        "extra-answer",
        "invalid-answer",
        "malformed",
        "fenced",
        "duplicate-key",
    ],
)
def test_final_text_must_pass_unchanged_invocation_codec(invocation, boundary, mode):
    start, events = transcript(invocation, boundary)
    value = response(invocation)
    if mode == "stale-invocation":
        value["invocation_id"] = "eval-invocation-v2-" + "0" * 64
    elif mode == "foreign-task":
        value["response"]["task_id"] = "foreign"
    elif mode == "foreign-request":
        value["response"]["request_id"] = "foreign"
    elif mode == "missing-answer":
        value["response"]["answers"].pop()
    elif mode == "extra-answer":
        value["response"]["answers"].append({"question_id": "foreign", "answer": None})
    elif mode == "invalid-answer":
        value["response"]["answers"][0]["answer"] = {"not": "an answer"}
    text = json.dumps(value)
    if mode == "malformed":
        text = "{private invalid output"
    elif mode == "fenced":
        text = "```json\n" + text + "\n```"
    elif mode == "duplicate-key":
        text = '{"schema_version":"0.2",' + text[1:]
    replace_text(events, text)
    with pytest.raises(common.SemanticError, match="^invocation-response-mismatch$"):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize(
    "mode",
    ["wrong-config", "wrong-invocation-type", "uninitialized-invocation", "wrong-boundary-type"],
)
def test_expected_binding_is_revalidated(invocation, boundary, mode):
    start, events = transcript(invocation, boundary)
    if mode == "wrong-config":
        boundary = replace(
            boundary, configuration=replace(boundary.configuration, timeout_seconds=31)
        )
    elif mode == "wrong-invocation-type":
        invocation = object()
    elif mode == "uninitialized-invocation":
        invocation = object.__new__(codec.Invocation)
    else:
        boundary = object()
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, events)


@pytest.mark.parametrize("value", [None, {}, (), "events", [], [None], [{"method": []}]])
def test_non_event_candidates_are_closed(invocation, boundary, value):
    start, _ = transcript(invocation, boundary)
    with pytest.raises(common.SemanticError):
        turns.check_turn(invocation, boundary, start, value)


def test_custom_inputs_do_not_execute_conversion_hooks(invocation, boundary):
    class Hostile(dict):
        def items(self):
            pytest.fail("custom conversion hook was called")

    _, events = transcript(invocation, boundary)
    with pytest.raises(common.SemanticError, match="^invalid-input-type$"):
        turns.check_turn(invocation, boundary, Hostile(), events)


def test_event_budget_is_bounded_before_processing(invocation, boundary):
    start, events = transcript(invocation, boundary)
    with pytest.raises(common.SemanticError, match="^invalid-events$"):
        turns.check_turn(invocation, boundary, start, [{}] * (turns.MAX_EVENTS + 1))
    events[0]["params"]["extra"] = "x" * (common.MAX_TOTAL_BYTES + 1)
    with pytest.raises(common.SemanticError, match="^input-too-large$"):
        turns.check_turn(invocation, boundary, start, events)


def test_delta_and_completed_text_have_independent_size_limits(invocation, boundary):
    start, events = transcript(invocation, boundary, deltas=True)
    events[3]["params"]["delta"] = "x" * (codec.MAX_RAW_BYTES // 2 + 1)
    events[4]["params"]["delta"] = "x" * (codec.MAX_RAW_BYTES // 2 + 1)
    with pytest.raises(common.SemanticError, match="^deltas-too-large$"):
        turns.check_turn(invocation, boundary, start, events)
    start, events = transcript(invocation, boundary)
    replace_text(events, "x" * (codec.MAX_RAW_BYTES + 1))
    with pytest.raises(common.SemanticError, match="^text-too-large$"):
        turns.check_turn(invocation, boundary, start, events)


def test_rewrapping_old_answer_content_cannot_prove_freshness(invocation, boundary):
    start, events = transcript(invocation, boundary)
    reused = response(invocation)["response"]
    envelope = response(invocation)
    envelope["response"] = copy.deepcopy(reused)
    replace_text(events, json.dumps(envelope))
    result = turns.check_turn(invocation, boundary, start, events)
    assert result["supplied_fields_match"] is True
    assert result["provider_freshness_verified"] is False
    assert result["accepted_trial"] is False
