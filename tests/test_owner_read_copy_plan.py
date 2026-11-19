"""Offline decisions for the in-memory owner-read copy plan. No directory is created."""

import json
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import ContractError
from authzest.codex.owner_read_suggestion import build_owner_read_request
from authzest.runner import owner_read_copy as copy
from authzest.runner.owner_read_suggestion import _changes


def _inputs():
    request = build_owner_read_request("offline-copy-plan")
    proposal = {
        "request_id": request.request_id,
        "status": "proposed-change",
        "rationale": "Synthetic regression and availability update.",
        "source": (
            "def available_to_owner(state: str) -> bool:\n"
            "    return state in ('active', 'archived')\n"
        ),
        "test": (
            "def test_archive(owner_client):\n"
            "    assert owner_client.get('/records/archived-note').status_code == 200\n"
        ),
    }
    return request, proposal, _changes(request, proposal)


@pytest.fixture(autouse=True)
def _forbid_staging(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("No filesystem work is authorized for this decision")

    monkeypatch.setattr(copy, "stage_private_copy", unexpected)


def _decide(read, inputs=_inputs):
    previews = []

    def emit(raw):
        previews.append(json.loads(raw))

    def answer(prompt):
        assert len(previews) == 1
        phrase = "copy " + previews[0]["plan_id"]
        assert phrase in prompt
        return read(phrase)

    return copy.prepare_current_copy(
        sharing_id="offline-share", inputs=inputs, emit=emit, read=answer
    )


@pytest.mark.parametrize(
    ("answer", "status", "code"),
    [("", "declined", 0), ("copy offline-share", "declined", 0), ("cancel", "cancelled", 130)],
)
def test_decline_wrong_stage_phrase_and_cancel_end_without_writing(answer, status, code):
    result = _decide(lambda _: answer)
    assert (result["status"], result["exit_code"], result["path"]) == (status, code, None)


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_interrupted_input_leaves_no_copy(exception):
    def interrupt(_phrase):
        raise exception

    result = _decide(interrupt)
    assert (result["status"], result["exit_code"], result["path"]) == ("cancelled", 130, None)


def test_a_copy_phrase_from_a_previous_review_is_rejected():
    old_phrases = []

    def capture(phrase):
        old_phrases.append(phrase)
        return ""

    old = _decide(capture)
    current = _decide(lambda _: old_phrases[0])
    assert old["plan_id"] != current["plan_id"]
    assert current["status"] == "declined" and current["path"] is None


@pytest.mark.parametrize("delay", [300, 301])
def test_exact_phrase_at_or_after_the_deadline_expires(monkeypatch, delay):
    clock = iter((10.0, 10.0 + delay))
    monkeypatch.setattr(copy, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    result = _decide(lambda phrase: phrase)
    assert (result["status"], result["exit_code"], result["path"]) == ("expired", 1, None)


def test_guard_is_rechecked_at_the_write_boundary(monkeypatch):
    clock = SimpleNamespace(now=0)
    monkeypatch.setattr(copy, "time", SimpleNamespace(monotonic=lambda: clock.now))
    checks = []

    def delayed_stage(*_artifacts, guard):
        checks.append("at-boundary")
        clock.now = 301
        guard()
        pytest.fail("An expired decision reached an effect")

    monkeypatch.setattr(copy, "stage_private_copy", delayed_stage)
    result = _decide(lambda phrase: phrase)
    assert checks == ["at-boundary"] and result["status"] == "expired" and result["path"] is None


def test_an_unexpired_current_decision_forwards_only_the_three_reviewed_bytes(monkeypatch):
    clock = iter((0, 299, 299))
    monkeypatch.setattr(copy, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    staged = []

    def record(before, test, after, *, guard):
        guard()
        staged.append((before, test, after))
        return {"status": "staged-for-test", "path": "/mock", "exit_code": 0}

    monkeypatch.setattr(copy, "stage_private_copy", record)
    result = _decide(lambda phrase: phrase)
    request, proposal, _ = _inputs()
    assert result["status"] == "staged-for-test"
    assert staged == [
        (
            request.to_dict()["source"]["text"].encode("ascii"),
            proposal["test"].encode("ascii"),
            proposal["source"].encode("ascii"),
        )
    ]


@pytest.mark.parametrize("change", ["request", "proposal", "diff", "revalidation-error"])
def test_rebuild_after_review_rejects_drift(change):
    calls = 0

    def changing_inputs():
        nonlocal calls
        calls += 1
        request, proposal, diffs = _inputs()
        if calls == 2:
            if change == "request":
                request = build_owner_read_request("other-offline-model")
            elif change == "proposal":
                proposal["rationale"] = "Reworded after approval."
            elif change == "diff":
                diffs[1]["after_sha256"] = "0" * 64
            else:
                raise ContractError("PRIVATE input lookup failed")
        return request, proposal, diffs

    result = _decide(lambda phrase: phrase, inputs=changing_inputs)
    assert calls == 2
    assert (result["status"], result["exit_code"], result["path"]) == ("inputs-changed", 1, None)
    assert "PRIVATE" not in json.dumps(result)
