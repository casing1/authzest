import json
from pathlib import Path

import pytest
from scripts import demo_apply
from scripts.demo_proposal import FIXTURE_ROOT, build_demo_proposal

from authzest.runner._fixture_workspace import supported


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("", "decline"),
        ("approve", "decline"),
        ("apply wrong", "decline"),
        ("apply proposal-123", "approve"),
        ("cancel", "cancel"),
        (" apply proposal-123", "decline"),
    ],
)
def test_exact_terminal_confirmation(answer, expected):
    assert demo_apply._choice(lambda _: answer, "apply", "proposal-123") == expected


@pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
def test_terminal_interruption_cancels(interrupt):
    def read(_):
        raise interrupt()

    assert demo_apply._choice(read, "apply", "id") == "cancel"


@pytest.mark.parametrize(
    "action", ["decline", "cancel", "apply", "restore", "edit-before-apply", "edit-before-restore"]
)
def test_owned_demo_real_copy_only(tmp_path, action):
    if not supported():
        pytest.skip("POSIX copy demo")
    original = (FIXTURE_ROOT / "main.py").read_bytes()
    output = []
    decisions = []

    def read(prompt):
        workspace = next(tmp_path.glob("authzest-fixture-*"))
        decisions.append(prompt)
        # Full scope and exact diff must have been emitted before asking for a decision.
        preview = json.loads(output[1])
        assert preview["changes"][0]["diff"]
        assert preview["workspace"] == str(workspace)
        if action == "cancel":
            raise EOFError()
        if action == "decline":
            return ""
        if action == "edit-before-apply" and len(decisions) == 1:
            (workspace / "main.py").write_text("# user change\n")
        if action == "edit-before-restore" and len(decisions) == 2:
            (workspace / "main.py").write_text("# user change\n")
        if len(decisions) == 2 and action == "apply":
            return ""
        return prompt.split("'")[1]

    result = demo_apply.run_demo(read=read, emit=output.append, parent=tmp_path)
    copy = Path(result["workspace"]) / "main.py"
    assert (FIXTURE_ROOT / "main.py").read_bytes() == original
    assert result["live_provider_calls"] == 0
    assert result["verification_status"] == "not-run"
    assert result["original_checkout_modified"] is False
    if action in ("decline", "cancel", "restore"):
        assert copy.read_bytes() == original
    elif action.startswith("edit-"):
        assert copy.read_text() == "# user change\n"
    else:
        assert b"debug=False" in copy.read_bytes()
    if action == "restore":
        assert result["restoration"]["restored"]
    elif action == "edit-before-restore":
        assert result["restoration"]["status"] == "not-restored"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("declined", 0),
        ("cancelled", 0),
        ("applied", 0),
        ("stale-source", 1),
        ("applied-state-unconfirmed", 1),
    ],
)
def test_demo_exit_status(monkeypatch, status, expected):
    monkeypatch.setattr("sys.argv", ["demo_apply"])
    monkeypatch.setattr(
        demo_apply, "run_demo", lambda: {"application": {"status": status}, "restoration": None}
    )
    assert demo_apply.main() == expected


def test_demo_failure_is_json_and_nonzero(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["demo_apply"])

    def fail():
        raise OSError("safe diagnostic")

    monkeypatch.setattr(demo_apply, "run_demo", fail)
    assert demo_apply.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_demo_draft_remains_caller_authored():
    request, review, proposal = build_demo_proposal()
    assert proposal.to_dict()["request_id"] == request.request_id
    assert "Caller-authored" in proposal.to_dict()["rationale"]
    assert review.to_dict()["identity"]["provider"] == "mock"
