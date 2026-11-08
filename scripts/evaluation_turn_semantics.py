"""Match a narrow caller-supplied turn candidate, not an observed live transcript.

The selected sequence is settings, turn-start, one agent item (optional deltas),
item-complete, turn-complete. Other protocol-valid items/events remain unsupported.
Candidate order, timestamps and correlated IDs do not prove wire order, timing,
freshness, provider behavior or authorization. This module performs no I/O.
"""

from __future__ import annotations

from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts.evaluation_session_semantics import check_settings

SemanticError = common.SemanticError
Boundary = common.Boundary
require = common.require
MAX_EVENTS = 4096
METHODS = frozenset(
    (
        "thread/settings/updated",
        "turn/started",
        "item/started",
        "item/agentMessage/delta",
        "item/completed",
        "turn/completed",
    )
)


def _object(value: object, required: set[str], optional: set[str] | None = None) -> dict:
    require(type(value) is dict, "invalid-object")
    require(required <= value.keys(), "missing-selected-fields")
    require(value.keys() <= required | (optional or set()), "unsupported-fields")
    return value


def _timestamp(value: object) -> None:
    require(type(value) is int and 0 <= value < 2**63, "invalid-timestamp")


def _text(value: object) -> None:
    require(type(value) is str, "invalid-text")
    require(len(value.encode("utf-8")) <= codec.MAX_RAW_BYTES, "text-too-large")


def _item(value: object, *, complete: bool) -> dict:
    item = _object(
        value,
        {"id", "type", "text"},
        {"phase", "delivery", "memoryCitation", "questions"},
    )
    require(item["type"] == "agentMessage", "unsupported-item-type")
    identity = common.identifier(item["id"])
    _text(item["text"])
    require(
        all(item.get(field) is None for field in ("delivery", "memoryCitation", "questions")),
        "unsupported-item-context",
    )
    phase = item.get("phase")
    if complete:
        require(phase == "final_answer", "explicit-final-answer-required")
    else:
        require(phase in (None, "final_answer") and item["text"] == "", "unsupported-item-start")
    return {"id": identity, "type": "agentMessage", "text": item["text"], "phase": phase}


def _turn(value: object, *, complete: bool) -> dict:
    turn = _object(
        value,
        {"id", "items", "status", "error"},
        {"itemsView", "startedAt", "completedAt", "durationMs"},
    )
    identity = common.identifier(turn["id"])
    require(turn["status"] == ("completed" if complete else "inProgress"), "turn-status-mismatch")
    require(turn["error"] is None, "turn-error")
    require(turn.get("itemsView", "full") == "full", "unsupported-items-view")
    for field in ("startedAt", "completedAt", "durationMs"):
        if turn.get(field) is not None:
            _timestamp(turn[field])
    if not complete:
        require(
            turn.get("completedAt") is None and turn.get("durationMs") is None,
            "unsupported-turn-start",
        )
    if turn.get("startedAt") is not None and turn.get("completedAt") is not None:
        require(turn["completedAt"] >= turn["startedAt"], "timestamp-order-mismatch")
    items = turn["items"]
    require(type(items) is list and len(items) == int(complete), "unsupported-turn-items")
    return {
        "id": identity,
        "items": [_item(item, complete=True) for item in items],
        "status": turn["status"],
        "error": None,
        "itemsView": "full",
        "startedAt": turn.get("startedAt"),
        "completedAt": turn.get("completedAt"),
        "durationMs": turn.get("durationMs"),
    }


def _correlate(
    params: dict, boundary: Boundary, turn_id: str, *, item_id: str | None = None
) -> None:
    require(params["threadId"] == boundary.thread_id, "thread-mismatch")
    require(params["turnId"] == turn_id, "turn-mismatch")
    if item_id is not None:
        require(params["itemId"] == item_id, "item-mismatch")


def check_turn(
    invocation: codec.Invocation,
    boundary: Boundary,
    start_result: object,
    events: object,
) -> dict:
    """Return only redacted match counts; never return the decoded model answer.

    Inputs are detached exact JSON values. A match is deliberately narrower than
    the pinned schema/dispatch recipe and cannot substitute for transport capture.
    """
    require(type(boundary) is Boundary, "invalid-boundary")
    boundary.validate()
    require(type(invocation) is codec.Invocation, "invalid-invocation")
    try:
        invocation.__post_init__()
        configuration = invocation.session.configuration
    except (codec.InvocationError, TypeError, AttributeError):
        raise SemanticError("invalid-invocation") from None
    require(configuration == boundary.configuration, "configuration-mismatch")
    start = _object(common.checked(start_result), {"turn"})
    acknowledged = _turn(start["turn"], complete=False)
    candidates = common.checked(events, max_bytes=common.MAX_TOTAL_BYTES)
    require(type(candidates) is list and 1 <= len(candidates) <= MAX_EVENTS, "invalid-events")
    turn_id = acknowledged["id"]
    settings_seen = started = completed = False
    item_start = item_end = None
    item_start_time = None
    deltas: list[str] = []
    delta_bytes = 0
    for index, candidate in enumerate(candidates):
        event = _object(common.checked(candidate), {"method", "params"})
        method = event["method"]
        require(type(method) is str and method in METHODS, "unsupported-event")
        require(not completed, "events-after-completion")
        if method == "thread/settings/updated":
            require(index == 0 and not settings_seen, "settings-order-mismatch")
            check_settings(event["params"], boundary)
            settings_seen = True
            continue
        require(settings_seen, "settings-required-first")
        if method == "turn/started":
            require(not started and index == 1, "turn-start-order-mismatch")
            params = _object(event["params"], {"threadId", "turn"})
            require(params["threadId"] == boundary.thread_id, "thread-mismatch")
            require(_turn(params["turn"], complete=False) == acknowledged, "turn-start-mismatch")
            started = True
        elif method == "item/started":
            require(started and item_start is None, "item-start-order-mismatch")
            params = _object(event["params"], {"threadId", "turnId", "item", "startedAtMs"})
            _correlate(params, boundary, turn_id)
            _timestamp(params["startedAtMs"])
            item_start_time = params["startedAtMs"]
            item_start = _item(params["item"], complete=False)
        elif method == "item/agentMessage/delta":
            require(item_start is not None and item_end is None, "delta-order-mismatch")
            params = _object(event["params"], {"threadId", "turnId", "itemId", "delta"})
            _correlate(params, boundary, turn_id, item_id=item_start["id"])
            _text(params["delta"])
            delta_bytes += len(params["delta"].encode("utf-8"))
            require(delta_bytes <= codec.MAX_RAW_BYTES, "deltas-too-large")
            deltas.append(params["delta"])
        elif method == "item/completed":
            require(item_start is not None and item_end is None, "item-complete-order-mismatch")
            params = _object(event["params"], {"threadId", "turnId", "item", "completedAtMs"})
            _correlate(params, boundary, turn_id)
            _timestamp(params["completedAtMs"])
            require(params["completedAtMs"] >= item_start_time, "timestamp-order-mismatch")
            item_end = _item(params["item"], complete=True)
            require(item_end["id"] == item_start["id"], "item-mismatch")
            if deltas:
                require("".join(deltas) == item_end["text"], "delta-text-mismatch")
        elif method == "turn/completed":
            require(started and item_end is not None, "turn-complete-order-mismatch")
            params = _object(event["params"], {"threadId", "turn"})
            require(params["threadId"] == boundary.thread_id, "thread-mismatch")
            final = _turn(params["turn"], complete=True)
            require(final["id"] == turn_id, "turn-mismatch")
            require(final["items"] == [item_end], "completed-snapshot-mismatch")
            require(final["startedAt"] == acknowledged["startedAt"], "turn-start-time-mismatch")
            completed = True
    require(completed, "incomplete-turn")
    decoded = codec.decode_response(invocation, item_end["text"])
    require(decoded["status"] == "valid", "invocation-response-mismatch")
    records = decoded["records"]
    return {
        "kind": "offline-selected-turn-semantics",
        "check": "turn",
        "supplied_fields_match": True,
        "semantic_scope": "selected-caller-supplied-fields-not-full-schema",
        "events_count": len(candidates),
        "settings_count": 1,
        "turns_count": 1,
        "items_count": 1,
        "deltas_count": len(deltas),
        "answer_fields_count": len(records),
        "unknown_answer_fields_count": sum(record["answer"] is None for record in records),
        **common.limitations(),
    }
