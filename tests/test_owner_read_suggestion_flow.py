"""Single-share, inert proposal workflow. All provider responses are scripted."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import ContractError
from authzest.codex.owner_read_suggestion import SOURCE_PATH, TEST_PATH
from authzest.runner import owner_read_suggestion as flow

MODEL = "offline-owner-read"
SOURCE = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_owner_archived_read(owner_client):\n"
    '    response = owner_client.get("/records/archived-note")\n'
    "    assert response.status_code == 200\n"
)


class Interaction:
    def __init__(self):
        self.preview = None
        self.calls = []

    def emit(self, raw):
        assert self.preview is None
        self.preview = json.loads(raw)

    def approve(self, prompt):
        phrase = "share " + self.preview["sharing_id"]
        assert phrase in prompt
        return phrase

    def run(self, *, read=None, adapter=None, timeout=120):
        return asyncio.run(
            flow.run_suggestion(
                MODEL,
                emit=self.emit,
                read=read or self.approve,
                adapter_factory=adapter or self.forbid_adapter,
                timeout_seconds=timeout,
            )
        )

    @staticmethod
    def forbid_adapter(**kwargs):
        pytest.fail("Unexpected provider construction")

    def adapter(self, status):
        def factory(*, approved_request_id, timeout_seconds):
            assert approved_request_id == self.preview["request_id"]
            assert timeout_seconds == self.preview["limits"]["timeout_seconds"]

            async def suggest(request):
                self.calls.append(request.request_id)
                assert self.preview["request"] == request.to_dict()
                return {
                    "request_id": request.request_id,
                    "status": status,
                    "rationale": "Scripted response for the offline fixture.",
                    "source": SOURCE if status == "proposed-change" else None,
                    "test": TEST if status == "proposed-change" else None,
                }

            return SimpleNamespace(suggest_owner_read=suggest)

        return factory


@pytest.fixture
def exchange(monkeypatch):
    # Fake a supported host without changing the process-wide os.name.
    monkeypatch.setattr(flow, "os", SimpleNamespace(name="posix"))
    return Interaction()


def test_preview_binds_complete_transport_limits_and_fresh_nonce():
    one = flow.build_preview(MODEL)
    two = flow.build_preview(MODEL)
    assert one["sharing_id"] != two["sharing_id"]
    assert one["sharing_content_id"] == two["sharing_content_id"]
    assert (
        flow.build_preview(MODEL, timeout_seconds=5)["sharing_content_id"]
        != one["sharing_content_id"]
    )
    request = one["request"]
    assert request["config"]["model"] == MODEL
    assert request["source"]["path"] == SOURCE_PATH
    assert request["prompt"] and request["host_instructions"] and request["output_schema"]
    assert one["limits"]["application_retries"] == 0
    assert one["limits"]["model_fallback"] is False
    assert one["limits"]["token_hard_cap"] is None
    assert one["limits"]["codex_internal_transport_retries_hard_capped"] is False


@pytest.mark.parametrize("timeout", [False, -1, 0, 121, float("inf"), float("nan"), 10**400])
def test_invalid_timeout_rejected_before_consent(exchange, timeout):
    with pytest.raises(ContractError):
        exchange.run(timeout=timeout)
    assert exchange.preview is None


@pytest.mark.parametrize("choice", ["", "y", "cancel", "old", "eof", "interrupt"])
def test_explicit_current_challenge_required(exchange, choice):
    older = flow.build_preview(MODEL)

    def answer(_prompt):
        if choice == "old":
            return "share " + older["sharing_id"]
        if choice == "eof":
            raise EOFError
        if choice == "interrupt":
            raise KeyboardInterrupt
        return choice

    result = exchange.run(read=answer)
    cancelled = choice in {"cancel", "eof", "interrupt"}
    assert result["status"] == ("cancelled" if cancelled else "not-shared")
    assert result["sharing_decision"] == ("cancel" if cancelled else "decline")
    assert result["application_turn_attempts"] == 0
    assert result["proposal"] is None and result["diffs"] == []


@pytest.mark.parametrize("unsupported", ["windows", "frozen"])
def test_unsupported_platform_never_constructs_adapter(monkeypatch, exchange, unsupported):
    if unsupported == "windows":
        monkeypatch.setattr(flow, "os", SimpleNamespace(name="nt"))
    else:
        monkeypatch.setattr(flow, "sys", SimpleNamespace(frozen=True))
    result = exchange.run()
    assert result["status"] == "unsupported"
    assert result["application_turn_attempts"] == 0 and result["exit_code"] == 2


def test_changed_input_after_prompt_never_reaches_adapter(monkeypatch, exchange):
    def changed(_model):
        raise ContractError("data changed")

    def approve_after_change(prompt):
        monkeypatch.setattr(flow, "build_owner_read_request", changed)
        return exchange.approve(prompt)

    result = exchange.run(read=approve_after_change)
    assert result["status"] == "preview-changed" and result["application_turn_attempts"] == 0


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_proposal_is_a_validated_suggestion_only(exchange, status):
    result = exchange.run(adapter=exchange.adapter(status))
    assert result["status"] == status and result["exit_code"] == 0
    assert result["application_turn_attempts"] == 1 and exchange.calls == [result["request_id"]]
    assert result["execution_status"] == result["patch_application"] == "not-run"
    assert result["original_checkout_modified"] is False
    if status == "proposed-change":
        source_diff, test_diff = result["diffs"]
        assert source_diff["path"] == SOURCE_PATH and test_diff["path"] == TEST_PATH
        assert source_diff["before_sha256"] == exchange.preview["request"]["source"]["sha256"]
        assert test_diff["before_sha256"] is None
        assert "+    return state in" in source_diff["diff"]
        assert test_diff["diff"].startswith(f"--- /dev/null\n+++ b/{TEST_PATH}\n")
        assert result["proposal"]["source"] == SOURCE and result["proposal"]["test"] == TEST
    else:
        assert result["diffs"] == []


@pytest.mark.parametrize("mode", ["invalid-response", "setup-error", "timeout"])
def test_failures_are_bounded_and_redacted(exchange, mode):
    calls = []

    def factory(**kwargs):
        if mode == "setup-error":
            raise ValueError("/PRIVATE-EXCEPTION")

        async def suggest(_request):
            calls.append(True)
            if mode == "timeout":
                await asyncio.sleep(60)
            return {"provider-secret": "/PRIVATE-OUTPUT"}

        return SimpleNamespace(suggest_owner_read=suggest)

    result = exchange.run(adapter=factory, timeout=0.05 if mode == "timeout" else 120)
    assert result["status"] == "suggestion-failed" and result["exit_code"] == 1
    assert len(calls) == result["application_turn_attempts"] == (0 if mode == "setup-error" else 1)
    assert result["failure"] and "PRIVATE" not in json.dumps(result)
    assert result["proposal"] is None and result["diffs"] == []
    if mode == "timeout":
        assert result["failure"]["code"] == "timeout"
