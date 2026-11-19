"""Exercise the owner-read CLI with scripted responses. Staged files are never imported."""

import builtins
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from authzest.cli import app
from authzest.cli_output import WorkflowOutput
from authzest.codex import app_server
from authzest.codex.owner_read_suggestion import build_owner_read_request
from authzest.runner import _owner_read_copy_files, owner_read_copy

MODEL = "offline-owner-read"
SOURCE = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_owner_reads_archive(owner_client):\n"
    '    assert owner_client.get("/records/archived-note").status_code == 200\n'
)
ARGUMENTS = ["owner-read-suggest", "--model", MODEL, "--json"]


def test_portable_combined_preview(monkeypatch):
    monkeypatch.setattr(owner_read_copy, "copy_supported", lambda: False)
    monkeypatch.setattr(builtins, "input", lambda: pytest.fail("Unexpected prompt"))
    monkeypatch.setattr(
        app_server, "CodexAppServerAdapter", lambda **_: pytest.fail("Unexpected adapter")
    )
    result = CliRunner().invoke(app, [*ARGUMENTS, "--preview-only", "--prepare-copy"])

    assert result.exit_code == 0, result.exception
    assert result.stderr == ""
    preview = json.loads(result.stdout)
    assert preview["kind"] == "owner-read-copy-offline-preview"
    assert preview["status"] == "preview-only"
    assert preview["sharing_preview"]["request"] == build_owner_read_request(MODEL).to_dict()
    controls = preview["local_copy"]["controls"]
    assert len(controls) == 7
    assert [
        (c["case_id"], c["before"]["status_code"], c["intended"]["status_code"]) for c in controls
    ] == [
        ("owner-active", 200, 200),
        ("owner-archived", 403, 200),
        ("other-active", 403, 403),
        ("other-archived", 403, 403),
        ("anonymous-active", 401, 401),
        ("owner-missing", 404, 404),
        ("owner-pending", 403, 403),
    ]


@pytest.fixture
def dialogue(monkeypatch, tmp_path):
    """Read the current IDs from each printed envelope, leaving CLI I/O in place."""
    monkeypatch.setattr(_owner_read_copy_files, "_TEMP_PARENT", tmp_path)
    previews = []
    emit = WorkflowOutput.emit

    def record(self, text):
        previews.append(json.loads(text))
        emit(self, text)

    monkeypatch.setattr(WorkflowOutput, "emit", record)

    def invoke(status, choices, *, prepare=True):
        choices = list(choices)
        adapter_calls = []

        def respond():
            assert choices, "Unexpected extra prompt"
            choice = choices.pop(0)
            if choice == "share":
                return "share " + previews[-1]["sharing_id"]
            if choice == "copy":
                return "copy " + previews[-1]["plan_id"]
            return choice

        def factory(*, approved_request_id, timeout_seconds):
            assert approved_request_id == previews[0]["request_id"]

            async def suggest(request):
                assert request.request_id == approved_request_id and timeout_seconds == 120
                adapter_calls.append(request.request_id)
                return {
                    "request_id": request.request_id,
                    "status": status,
                    "rationale": "Scripted offline response.",
                    "source": SOURCE if status == "proposed-change" else None,
                    "test": TEST if status == "proposed-change" else None,
                }

            return SimpleNamespace(suggest_owner_read=suggest)

        monkeypatch.setattr(builtins, "input", respond)
        monkeypatch.setattr(app_server, "CodexAppServerAdapter", factory)
        args = [*ARGUMENTS, "--prepare-copy"] if prepare else ARGUMENTS
        result = CliRunner().invoke(app, args)
        assert not choices, "Expected a prompt that never occurred"
        return result, previews, adapter_calls

    return invoke


def test_unsupported_host_never_prompts_or_allocates(dialogue, monkeypatch, tmp_path):
    monkeypatch.setattr(owner_read_copy, "copy_supported", lambda: False)
    result, _, calls = dialogue("proposed-change", [])
    assert result.exit_code == 2, result.exception
    outcome = json.loads(result.stdout)
    assert outcome["status"] == "unsupported"
    assert outcome["copy"] == {"status": "not-started", "path": None}
    assert outcome["application_turn_attempts"] == 0 and calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="Active copy workflow requires POSIX")
@pytest.mark.parametrize(
    ("status", "choices", "expected_result", "expected_copy", "call_count", "plan_count"),
    [
        ("proposed-change", [""], "not-shared", "not-started", 0, 0),
        ("no-change", ["share"], "no-change", "not-started", 1, 0),
        ("unknown", ["share"], "unknown", "not-started", 1, 0),
        ("refused", ["share"], "refused", "not-started", 1, 0),
        ("proposed-change", ["share", ""], "proposed-change", "declined", 1, 1),
        ("proposed-change", ["share", "copy stale-id"], "proposed-change", "declined", 1, 1),
    ],
)
def test_no_copy_without_proposal_and_current_decisions(
    dialogue, tmp_path, status, choices, expected_result, expected_copy, call_count, plan_count
):
    result, previews, calls = dialogue(status, choices)
    assert result.exit_code == 0, result.exception
    outcome = json.loads(result.stdout)
    assert outcome["status"] == expected_result
    assert outcome["copy"]["status"] == expected_copy and outcome["copy"]["path"] is None
    assert outcome["application_turn_attempts"] == len(calls) == call_count
    assert [p["kind"] for p in previews].count("owner-read-copy-plan") == plan_count
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="Active copy workflow requires POSIX")
def test_approved_copy_stages_exact_bytes_and_separates_interaction(dialogue, tmp_path):
    result, previews, calls = dialogue("proposed-change", ["share", "copy"])
    assert result.exit_code == 0, result.exception
    outcome = json.loads(result.stdout)
    assert outcome["kind"] == "owner-read-suggestion" and outcome["status"] == "proposed-change"
    assert outcome["execution_status"] == outcome["patch_application"] == "not-run"
    assert outcome["original_checkout_modified"] is False
    assert outcome["copy"]["status"] == "prepared"
    assert calls == [outcome["request_id"]]
    assert [item["kind"] for item in previews] == [
        "owner-read-sharing-preview",
        "owner-read-copy-plan",
    ]
    assert "share " + previews[0]["sharing_id"] in result.stderr
    assert "copy " + previews[1]["plan_id"] in result.stderr
    path = Path(outcome["copy"]["path"])
    assert list(tmp_path.iterdir()) == [path]
    assert {p.name for p in path.iterdir()} == {
        "availability.py",
        "test_owner_archived_read.py",
        "proposed-availability.txt",
    }
    assert (path / "availability.py").read_bytes() == previews[0]["request"]["source"][
        "text"
    ].encode()
    assert (path / "proposed-availability.txt").read_bytes() == SOURCE.encode()
    assert (path / "test_owner_archived_read.py").read_bytes() == TEST.encode()


@pytest.mark.skipif(os.name != "posix", reason="Live suggestion path requires POSIX")
def test_suggestion_without_copy_option_preserves_the_original_result(dialogue, tmp_path):
    result, previews, _ = dialogue("proposed-change", ["share"], prepare=False)
    assert result.exit_code == 0, result.exception
    outcome = json.loads(result.stdout)
    assert outcome["status"] == "proposed-change" and "copy" not in outcome
    assert [p["kind"] for p in previews] == ["owner-read-sharing-preview"]
    assert list(tmp_path.iterdir()) == []
