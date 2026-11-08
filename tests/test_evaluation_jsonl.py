"""Pure byte and envelope examples, not notification semantics or live trials."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from pathlib import Path

import pytest
from scripts import evaluation_jsonl as wire


def line(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def reply(identity=1, result=None):
    return {"id": identity, "result": {} if result is None else result}


def notice(method="thread/started", params=None):
    return {"method": method, "params": {} if params is None else params}


def armed(identity=1, budget=None):
    inbox = wire.RpcInbox(budget)
    inbox.arm(identity)
    return inbox


def assert_error(code, function, *args):
    with pytest.raises(wire.JsonlError) as error:
        function(*args)
    assert error.value.code == str(error.value) == code
    return error.value


def assert_no_execution(snapshot):
    for key in (
        "runtime_observed",
        "provider_freshness_verified",
        "notification_semantics_verified",
        "full_protocol_conformance_verified",
        "accepted_trial",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "live_benchmark_ready",
    ):
        assert snapshot[key] is False
    assert snapshot["provider_calls_by_this_tool"] == 0
    assert snapshot["target_execution"] == "not-run"
    assert snapshot["transport_status"] == "not-implemented"


def test_empty_feed_and_clean_eof_are_not_provider_or_trial_evidence():
    decoder = wire.JsonlDecoder()
    assert decoder.feed(b"") == ()
    assert decoder.feed(b"{}\n") == ({},)
    assert decoder.finish() is None
    assert decoder.budget.snapshot()["stream_bytes"] == 3
    assert decoder.budget.snapshot()["events"] == 1
    assert_no_execution(decoder.budget.snapshot())


def test_utf8_every_single_byte_split_and_multiple_coalesced_objects():
    values = [{"private": "한국어🍋"}, {"escaped": '\\"{}[]'}, {}]
    raw = b"".join(line(value) for value in values)
    decoder = wire.JsonlDecoder()
    decoded = []
    for byte in raw:
        decoded.extend(decoder.feed(bytes([byte])))
    assert decoded == values
    decoder.finish()
    assert wire.JsonlDecoder().feed(raw) == tuple(values)


@pytest.mark.parametrize("raw", [b"{}\r\n", b" \t{} \r\n", b'{"v":1}\r\n'])
def test_crlf_is_supported_as_json_whitespace_and_counts_both_bytes(raw):
    decoder = wire.JsonlDecoder()
    assert decoder.feed(raw) == (json.loads(raw),)
    assert decoder.budget.snapshot()["stream_bytes"] == len(raw)


def test_escaped_pair_is_valid_unicode_but_string_brackets_do_not_affect_depth():
    decoder = wire.JsonlDecoder()
    assert decoder.feed(b'{"s":"\\ud83c\\udf4b","nested":"[[[{{{\\""}\n') == (
        {"s": "🍋", "nested": '[[[{{{"'},
    )


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"\n", "blank-frame"),
        (b" \r\t\n", "blank-frame"),
        (b"{\n", "invalid-json"),
        (b"{bad}\n", "invalid-json"),
        (b"{}{}\n", "invalid-json"),
        (b'{"a":1,}\n', "invalid-json"),
        (b"[1]\n", "nonobject-json"),
        (b"null\n", "nonobject-json"),
        (b"true\n", "nonobject-json"),
        (b'"private"\n', "nonobject-json"),
        (b"\xef\xbb\xbf{}\n", "utf8-bom"),
        (b'{"private":"\xff"}\n', "invalid-utf8"),
        (b'{"private":"\\ud800"}\n', "invalid-utf8"),
        (b'{"\\udfff":"private"}\n', "invalid-utf8"),
        (b'{"a":1,"a":2}\n', "duplicate-json-key"),
        (b'{"a":{"x":1,"x":2}}\n', "duplicate-json-key"),
    ],
)
def test_invalid_frames_fail_closed_and_poison_the_shared_budget(raw, code):
    budget = wire.Budget()
    decoder, other = wire.JsonlDecoder(budget), wire.JsonlDecoder(budget)
    assert_error(code, decoder.feed, raw)
    assert budget.snapshot()["terminal"] is True
    assert budget.snapshot()["failure_code"] == code
    assert_error("terminal-budget", decoder.feed, b"{}\n")
    assert_error("terminal-budget", other.feed, b"{}\n")
    assert_error("terminal-budget", other.finish)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999999", "-1e999999"])
def test_nonfinite_and_float_overflow_are_rejected(number):
    assert_error("nonfinite-json", wire.JsonlDecoder().feed, f'{{"n":{number}}}\n'.encode())


def test_integer_policy_exact_boundary_and_oversized_digit_token():
    maximum = (1 << wire.MAX_INTEGER_BITS) - 1
    assert wire.JsonlDecoder().feed(line({"n": maximum})) == ({"n": maximum},)
    assert_error("integer-too-large", wire.JsonlDecoder().feed, line({"n": maximum + 1}))
    assert_error("integer-too-large", wire.JsonlDecoder().feed, b'{"n":' + b"1" * 1301 + b"}\n")


def test_depth_is_checked_before_json_parsing_and_has_exact_container_boundary(monkeypatch):
    def nested(depth):
        return b'{"v":' + b"[" * (depth - 1) + b"0" + b"]" * (depth - 1) + b"}\n"

    assert wire.JsonlDecoder().feed(nested(wire.MAX_DEPTH))
    assert_error("json-too-deep", wire.JsonlDecoder().feed, nested(wire.MAX_DEPTH + 1))

    def forbidden(*args, **kwargs):
        pytest.fail("deep raw frames must be rejected before json.loads")

    monkeypatch.setattr(wire.json, "loads", forbidden)
    assert_error("json-too-deep", wire.JsonlDecoder().feed, nested(wire.MAX_DEPTH + 1))


def test_decoded_node_limit_includes_keys_values_and_containers(monkeypatch):
    raw = b'{"v":[null,true,"x",{}]}\n'  # root + key + list + four children = 7.
    monkeypatch.setattr(wire, "MAX_NODES", 7)
    assert wire.JsonlDecoder().feed(raw)
    monkeypatch.setattr(wire, "MAX_NODES", 6)
    assert_error("too-many-json-nodes", wire.JsonlDecoder().feed, raw)


def test_full_frame_limit_includes_lf_and_allows_large_coalesced_chunks():
    # A {} object plus JSON whitespace gives exactly MAX-1 payload bytes plus LF.
    exact = b"{}" + b" " * (wire.MAX_FRAME_BYTES - 3) + b"\n"
    decoder = wire.JsonlDecoder()
    assert decoder.feed(exact + exact) == ({}, {})
    assert len(exact + exact) > wire.MAX_FRAME_BYTES
    assert_error("frame-too-large", wire.JsonlDecoder().feed, exact[:-1] + b" \n")


def test_partial_frame_limit_does_not_forget_preceding_chunk_bytes():
    decoder = wire.JsonlDecoder()
    assert decoder.feed(b"{}" + b" " * (wire.MAX_FRAME_BYTES - 2)) == ()
    assert_error("frame-too-large", decoder.feed, b"\n")


@pytest.mark.parametrize("raw", [b"{}", b"{", b" \r", b'{"s":"\xe9'])
def test_eof_requires_full_lf_frame_even_for_valid_json_or_partial_utf8(raw):
    decoder = wire.JsonlDecoder()
    assert decoder.feed(raw) == ()
    assert_error("truncated-frame", decoder.finish)
    assert_error("terminal-budget", decoder.feed, b"\n")


def test_same_chunk_earlier_valid_frame_cannot_be_salvaged_after_later_parse_failure():
    decoder = wire.JsonlDecoder()
    assert_error("invalid-json", decoder.feed, b"{}\n{bad}\n")
    assert decoder.budget.snapshot()["events"] == 2
    assert_error("terminal-budget", decoder.finish)


def test_shared_stream_budget_exact_boundary_across_two_decoder_instances(monkeypatch):
    monkeypatch.setattr(wire, "MAX_STREAM_BYTES", 6)
    budget = wire.Budget()
    first, second = wire.JsonlDecoder(budget), wire.JsonlDecoder(budget)
    first.feed(b"{}\n")
    first.finish()
    second.feed(b"{}\n")
    assert budget.snapshot()["stream_bytes"] == 6
    assert_error("stream-too-large", second.feed, b"x")
    assert_error("terminal-budget", first.feed, b"{}\n")


def test_shared_event_budget_exact_boundary_across_decoder_instances(monkeypatch):
    monkeypatch.setattr(wire, "MAX_EVENTS", 2)
    budget = wire.Budget()
    wire.JsonlDecoder(budget).feed(b"{}\n")
    other = wire.JsonlDecoder(budget)
    other.feed(b"{}\n")
    assert budget.snapshot()["events"] == 2
    assert_error("too-many-events", other.feed, b"{}\n")


def test_caller_chunk_type_and_closed_decoder_misuse_do_not_poison_budget():
    decoder = wire.JsonlDecoder()
    for value in (None, "private", bytearray(b"{}\n"), memoryview(b"{}\n")):
        assert_error("invalid-bytes", decoder.feed, value)
        assert decoder.budget.snapshot()["terminal"] is False
        assert decoder.budget.snapshot()["stream_bytes"] == 0
    decoder.finish()
    assert_error("decoder-finished", decoder.finish)
    assert_error("decoder-finished", decoder.feed, b"{}\n")
    assert decoder.budget.snapshot()["terminal"] is False


def test_serial_response_result_consumption_and_strictly_increasing_arm():
    inbox = armed(2)
    assert inbox.take_result() is None
    inbox.feed(line(reply(2, {"private": "retained only in memory"})))
    assert inbox.snapshot()["pending_requests"] == 0
    assert inbox.snapshot()["result_ready"] is True
    assert_error("result-not-consumed", inbox.arm, 3)
    assert inbox.take_result() == {"private": "retained only in memory"}
    assert inbox.take_result() is None
    assert_error("nonincreasing-request-id", inbox.arm, 2)
    inbox.arm(3)
    inbox.feed(line(reply(3)))
    inbox.finish()
    assert inbox.take_result() == {}
    assert inbox.snapshot()["retired_responses"] == 2
    assert_no_execution(inbox.snapshot())


@pytest.mark.parametrize("identity", [None, True, False, "1", 1.0, 0, -1, 2**31])
def test_arm_ids_are_exact_positive_bounded_ints_and_misuse_does_not_mutate(identity):
    inbox = wire.RpcInbox()
    before = inbox.snapshot()
    assert_error("invalid-request-id", inbox.arm, identity)
    assert inbox.snapshot() == before


def test_arm_pending_id_rejection_does_not_overwrite_original_pending_request():
    inbox = armed()
    assert_error("request-already-pending", inbox.arm, 2)
    inbox.feed(line(reply()))
    assert inbox.take_result() == {}


def test_distinct_process_inboxes_keep_rpc_id_namespaces_separate_but_share_budget():
    budget = wire.Budget()
    for _ in range(2):
        inbox = armed(1, budget)
        inbox.feed(line(reply()))
        inbox.finish()
        assert inbox.take_result() == {}
    assert budget.snapshot()["events"] == 2


@pytest.mark.parametrize("consume", [False, True])
def test_duplicate_response_before_or_after_take_is_terminal(consume):
    inbox = armed()
    inbox.feed(line(reply()))
    if consume:
        assert inbox.take_result() == {}
    assert_error("duplicate-response", inbox.feed, line(reply()))
    for operation in (inbox.take_result, inbox.drain_notifications, inbox.finish):
        assert_error("terminal-budget", operation)
    assert_error("terminal-budget", inbox.arm, 2)


@pytest.mark.parametrize("identity", [2, 17])
def test_foreign_or_unarmed_response_is_terminal(identity):
    for inbox in (armed(), wire.RpcInbox()):
        assert_error("response-id-mismatch", inbox.feed, line(reply(identity)))


def test_old_retired_id_is_rejected_after_new_request_is_armed():
    inbox = armed()
    inbox.feed(line(reply()))
    inbox.take_result()
    inbox.arm(2)
    assert_error("duplicate-response", inbox.feed, line(reply()))


@pytest.mark.parametrize(
    "frame,code",
    [
        ({"id": True, "result": {}}, "invalid-response-id"),
        ({"id": "1", "result": {}}, "invalid-response-id"),
        ({"id": 1, "result": None}, "invalid-result"),
        ({"id": 1, "result": []}, "invalid-result"),
        ({"id": 1, "result": {}, "error": {}}, "invalid-envelope"),
        ({"id": 1, "result": {}, "jsonrpc": "2.0"}, "invalid-envelope"),
        ({"id": 1}, "invalid-envelope"),
        ({"result": {}}, "invalid-envelope"),
        ({}, "invalid-envelope"),
        ({"id": 1, "method": "approval", "params": {}}, "server-request-rejected"),
        ({"id": 1, "error": {"message": "private-server-text"}}, "rpc-error"),
    ],
)
def test_wrong_rpc_envelopes_ids_results_errors_and_server_requests_fail_closed(frame, code):
    inbox = armed()
    error = assert_error(code, inbox.feed, line(frame))
    assert "private" not in repr(error)
    assert inbox.snapshot()["terminal"] is True


@pytest.mark.parametrize(
    "frame",
    [
        notice("warning", {"message": "private-warning"}),
        notice("error", {"willRetry": True}),
        notice("unknown"),
        {"method": "thread/started"},
        {"method": "thread/started", "params": None},
        {"method": "thread/started", "params": []},
        {"method": "thread/started", "params": {}, "extra": True},
        {"method": {}, "params": {}},
    ],
)
def test_warnings_retries_unknown_names_and_wrong_notification_envelopes_are_terminal(frame):
    assert_error("notification-rejected", armed().feed, line(frame))


def test_all_allowlisted_names_are_envelopes_only_without_semantic_validation():
    inbox = armed()
    values = [
        notice(method, {"deliberately-not-real-semantic-data": True})
        for method in sorted(wire.ALLOWED_NOTIFICATION_METHODS)
    ]
    inbox.feed(b"".join(line(value) for value in values) + line(reply()))
    assert inbox.take_result() == {}
    assert inbox.drain_notifications() == tuple(values)
    assert inbox.drain_notifications() == ()
    assert inbox.snapshot()["queued_notifications"] == 0
    assert_no_execution(inbox.snapshot())


def test_claimed_failed_foreign_or_enabled_payloads_are_not_semantically_verified_trials():
    frames = (
        notice("turn/completed", {"threadId": "foreign", "status": "failed"}),
        notice("thread/settings/updated", {"model": "different", "reasoningEffort": None}),
        notice("remoteControl/status/changed", {"status": "enabled"}),
    )
    inbox = armed()
    inbox.feed(b"".join(line(value) for value in frames) + line(reply()))
    assert inbox.drain_notifications() == frames
    assert inbox.take_result() == {}
    assert_no_execution(inbox.snapshot())
    assert inbox.snapshot()["notification_semantics_verified"] is False


def test_budget_reference_cannot_be_rebound_through_normal_public_api_after_failure():
    budget = wire.Budget()
    decoder, inbox = wire.JsonlDecoder(budget), wire.RpcInbox(budget)
    assert_error("invalid-json", decoder.feed, b"{bad}\n")
    for receiver in (decoder, inbox):
        with pytest.raises(AttributeError):
            receiver.budget = wire.Budget()
        assert receiver.budget is budget
        assert_error("terminal-budget", receiver.feed, b"{}\n")


def test_before_ack_notification_limit_exactly_128_then_129_fails_and_poison_is_shared():
    budget = wire.Budget()
    inbox, other = armed(1, budget), wire.RpcInbox(budget)
    raw = line(notice())
    inbox.feed(raw * 128)
    assert inbox.snapshot()["local_queued_notifications"] == 128
    assert_error("too-many-notifications", other.feed, raw)
    assert_error("terminal-budget", inbox.drain_notifications)
    assert_error("terminal-budget", inbox.feed, line(reply()))


def test_drain_notifications_releases_shared_queue_but_never_resets_event_byte_budgets():
    budget = wire.Budget()
    first, second = wire.RpcInbox(budget), wire.RpcInbox(budget)
    raw = line(notice())
    first.feed(raw * 64)
    second.feed(raw * 64)
    assert len(first.drain_notifications()) == 64
    assert budget.snapshot()["queued_notifications"] == 64
    second.feed(raw * 64)
    assert budget.snapshot()["queued_notifications"] == 128
    assert budget.snapshot()["events"] == 192
    assert budget.snapshot()["stream_bytes"] == len(raw) * 192


def test_pending_eof_and_partial_eof_fail_without_salvaging_prior_result():
    assert_error("missing-response", armed().finish)
    inbox = armed()
    inbox.feed(line(reply()) + b"{")
    assert_error("truncated-frame", inbox.finish)
    assert_error("terminal-budget", inbox.take_result)


def test_successful_response_then_bad_notification_same_chunk_cannot_be_taken():
    inbox = armed()
    assert_error("notification-rejected", inbox.feed, line(reply()) + line(notice("warning")))
    assert_error("terminal-budget", inbox.take_result)
    assert inbox.snapshot()["failure_code"] == "notification-rejected"


def test_snapshot_is_redacted_detached_counts_only_and_does_not_expose_pending_identity():
    inbox = armed(973)
    inbox.feed(line(notice(params={"private-path": "/private/user-path"})))
    snapshot = inbox.snapshot()
    encoded = json.dumps(snapshot)
    assert "private" not in encoded and "973" not in encoded
    assert "sha256" not in encoded and "digest" not in encoded
    snapshot["stream_bytes"] = -1
    assert inbox.snapshot()["stream_bytes"] > 0
    assert_no_execution(snapshot)


def test_invalid_budget_objects_and_bytes_subclasses_are_not_coerced():
    for constructor in (wire.JsonlDecoder, wire.RpcInbox):
        assert_error("invalid-budget", constructor, {})

    class OtherBytes(bytes):
        pass

    decoder = wire.JsonlDecoder()
    assert_error("invalid-bytes", decoder.feed, OtherBytes(b"{}\n"))
    assert decoder.budget.snapshot()["stream_bytes"] == 0


def test_framing_and_rpc_operations_have_no_io_process_network_account_or_clock_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure JSONL must not read or launch external state")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    inbox = armed()
    inbox.feed(line(notice()) + line(reply()))
    inbox.finish()
    assert inbox.take_result() == {}
    assert inbox.drain_notifications() == (notice(),)
    assert_no_execution(inbox.snapshot())
