"""HTTP 2.0 wire observations use owned memory streams, never target sockets."""

from __future__ import annotations

import pytest
from tests.helpers.repository_http_verification_data import phase_frame, plan_inputs

from authzest.codex.contracts import canonical
from authzest.runner import _repository_http as old
from authzest.runner import _repository_http_transport as codec
from authzest.runner.repository_http_verification import (
    compare_repository_http_phase,
    prepare_repository_http_observer_schedule,
)
from test_repository_http import Stream, _wire
from test_repository_http import no_external_effects as no_external_effects


def schedule(count=4):
    return {
        "schema_version": "2.0",
        "kind": "repository-http-observer-schedule",
        "plan_id": "repository-http-verification-plan-" + "a" * 64,
        "phase": "before",
        "requests": [
            {
                "case_id": f"case-{i}",
                "method": "GET",
                "path": f"/objects/{i}",
                "headers": {"x-user-id": "test-owner"},
            }
            for i in range(count)
        ],
    }


def capture(streams, *, data=None, clock=lambda: 0, deadline=40):
    iterator = iter(streams)
    return codec.capture_repository_http_poc(
        data or schedule(),
        stream_factory=lambda *_: next(iterator),
        phase_deadline=deadline,
        clock=clock,
    ).to_dict()


def test_new_wire_schedule_is_distinct_detached_and_request_only():
    data = schedule(8)
    checked = codec.validate_http_observer_schedule(data)
    checked["requests"][0]["headers"]["x-user-id"] = "test-other"
    assert data["requests"][0]["headers"]["x-user-id"] == "test-owner"
    assert codec.validate_http_observer_schedule(canonical(data)) == data
    wire = codec.encode_http_observer_request(data, "case-0")
    assert wire == (
        b"GET /objects/0 HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n"
        b"Accept-Encoding: identity\r\nx-user-id: test-owner\r\n\r\n"
    )
    assert b"plan" not in wire and b"case-0" not in wire
    with pytest.raises(codec.HTTPProfileError):
        old.validate_observer_schedule(data)
    legacy = {**data, "schema_version": "1.0", "kind": "repository-observer-schedule"}
    legacy["plan_id"] = "repository-verification-plan-" + "a" * 64
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_http_observer_schedule(legacy)


@pytest.mark.parametrize("count", [0, 3, 9, 100])
def test_count_is_four_to_eight(count):
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_http_observer_schedule(schedule(count))


@pytest.mark.parametrize(
    "kind",
    [
        "legacy-plan",
        "phase",
        "oracle",
        "source",
        "duplicate-id",
        "post",
        "absolute-url",
        "traversal",
        "query",
        "newline",
        "credentials",
        "non-synthetic",
        "oversized-header",
        "header-array",
        "bool-version",
    ],
)
def test_unreviewed_wire_inputs_are_closed_before_factory(kind):
    data = schedule()
    row = data["requests"][0]
    if kind == "legacy-plan":
        data["plan_id"] = "repository-verification-plan-" + "a" * 64
    elif kind == "phase":
        data["phase"] = "repair"
    elif kind == "oracle":
        row["expected"] = {"status": 403}
    elif kind == "source":
        data["source"] = "PRIVATE_SOURCE_DATA"
    elif kind == "duplicate-id":
        data["requests"][1]["case_id"] = row["case_id"]
    elif kind == "post":
        row["method"] = "POST"
    elif kind == "absolute-url":
        row["path"] = "https://example.invalid/private"
    elif kind == "traversal":
        row["path"] = "/../private"
    elif kind == "query":
        row["path"] = "/objects?token=PRIVATE_DATA"
    elif kind == "newline":
        row["path"] = "/objects\r\nPRIVATE_DATA"
    elif kind == "credentials":
        row["headers"] = {"authorization": "PRIVATE_DATA"}
    elif kind == "non-synthetic":
        row["headers"] = {"x-user-id": "PRIVATE_DATA"}
    elif kind == "oversized-header":
        row["headers"] = {"x-user-id": "test-" + "a" * 60}
    elif kind == "header-array":
        row["headers"] = [{"name": "x-user-id", "value": "test-owner"}]
    else:
        data["schema_version"] = True

    def forbidden(*_):
        pytest.fail("Invalid schedule reached a stream factory")

    with pytest.raises(codec.HTTPProfileError) as caught:
        codec.capture_repository_http_poc(
            data, stream_factory=forbidden, clock=lambda: 0, phase_deadline=40
        )
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("raw", ['{"phase":1,"phase":2}', '{"phase":NaN}', " " * 16385])
def test_strict_json_and_schedule_byte_limit(raw):
    with pytest.raises(codec.HTTPProfileError):
        codec.validate_http_observer_schedule(raw)


@pytest.mark.parametrize("chunk", [1, 2, 7, 4096])
def test_complete_capture_uses_same_parser_and_one_owned_stream_per_case(chunk):
    streams = [Stream(_wire(canonical({"id": i}).encode()), chunk=chunk) for i in range(4)]
    result = capture(streams)
    assert result["schema_version"] == "2.0"
    assert result["kind"] == "repository-http-raw-capture"
    assert result["schedule_id"].startswith("repository-http-observer-schedule-")
    assert result["planned_count"] == 4 and result["status"] == "complete"
    assert result["failure"] is None and result["cancellation"] is None
    assert result["execution_status"] == "not-established" and not result["verified_fix"]
    assert result["authorization_status"] == "unknown"
    assert "cleanup" not in result and "pytest" not in result
    for i, (stream, row) in enumerate(zip(streams, result["records"], strict=True)):
        assert stream.closed == 1 and len(stream.sent) == 1
        assert stream.sent[0] == codec.encode_http_observer_request(schedule(), f"case-{i}")
        assert row["dispatch_status"] == "response" and row["close_status"] == "closed"
        assert codec.decode_response_fact(row["fact"]) == {
            "status": 200,
            "body": {"kind": "json", "value": {"id": i}},
        }


@pytest.mark.parametrize("fault", ["send", "receive", "close"])
def test_first_error_preserves_all_remaining_cases_without_dispatch(fault):
    streams = [Stream(_wire(), fault=fault), *[Stream(_wire()) for _ in range(3)]]
    result = capture(streams)
    assert result["status"] == "partial" and result["failure"]
    assert result["planned_count"] == len(result["records"]) == 4
    assert result["records"][0]["dispatch_status"] == "error"
    assert all(row["dispatch_status"] == "not-dispatched" for row in result["records"][1:])
    assert streams[0].closed == 1
    assert all(not stream.sent and stream.closed == 0 for stream in streams[1:])
    assert "private details" not in canonical(result)


def test_reused_stream_is_not_sent_or_closed_twice():
    stream = Stream(_wire())
    result = codec.capture_repository_http_poc(
        schedule(), stream_factory=lambda *_: stream, clock=lambda: 0, phase_deadline=40
    ).to_dict()
    assert result["status"] == "partial" and stream.closed == 1 and len(stream.sent) == 1
    assert result["records"][0]["dispatch_status"] == "response"
    assert result["records"][1]["dispatch_status"] == "error"
    assert result["records"][1]["close_status"] == "not-acquired"


def test_factory_time_consumes_original_deadline_and_acquired_stream_is_closed():
    ticks = [0]
    stream = Stream(_wire())

    def factory(*_):
        ticks[0] = 40
        return stream

    result = codec.capture_repository_http_poc(
        schedule(), stream_factory=factory, clock=lambda: ticks[0], phase_deadline=40
    ).to_dict()
    assert result["status"] == "partial" and result["failure"] == "deadline-expired"
    assert stream.closed == 1 and not stream.sent
    assert all(row["dispatch_status"] == "not-dispatched" for row in result["records"][1:])


def test_close_time_does_not_reset_deadline_or_hide_the_failure():
    ticks = [0]

    class Closing(Stream):
        def close(self):
            super().close()
            ticks[0] = 40

    stream = Closing(_wire())
    result = capture([stream], clock=lambda: ticks[0])
    assert result["status"] == "partial" and result["failure"] == "deadline-expired"
    assert stream.closed == 1 and result["records"][0]["dispatch_status"] == "error"


@pytest.mark.parametrize("body", [b'{"same":1,"same":2}', b"NaN", b'"\xff"'])
def test_invalid_http_body_stops_before_remaining_requests(body):
    streams = [Stream(_wire(body)), *[Stream(_wire()) for _ in range(3)]]
    result = capture(streams)
    assert result["status"] == "partial" and result["failure"] == "body-invalid"
    assert streams[0].closed == 1 and not streams[1].sent


@pytest.mark.parametrize("phase", ["before", "after"])
def test_bound_plan_schedule_memory_capture_and_supplied_comparison_never_become_live(phase):
    plan, request, response, cases = plan_inputs()
    data = prepare_repository_http_observer_schedule(plan, request, response, cases, phase=phase)
    assert "HOST_ONLY_EXPECTATION" not in canonical(data)
    assert "source_sha256" not in canonical(data) and "after_text" not in canonical(data)
    streams = [
        Stream(_wire(canonical(case[phase]["body"]["value"]).encode(), case[phase]["status"]))
        for case in plan.to_dict()["case_set"]["cases"]
    ]
    observed = capture(streams, data=data)
    assert observed["status"] == "complete" and len(observed["records"]) == 5
    frame = phase_frame(plan, phase)
    for row, raw in zip(frame["observations"], observed["records"], strict=True):
        row["response"] = codec.decode_response_fact(raw["fact"])
    checked = compare_repository_http_phase(
        canonical(frame), plan, request, response, cases, phase=phase
    )
    assert checked["execution_status"] == "not-run"
    assert checked["evidence_basis"] == "supplied-unverified"
    assert checked["authorization_status"] == "unknown"
    assert (
        checked["verified_fix"] is checked["live_evidence"] is checked["writes_authorized"] is False
    )
