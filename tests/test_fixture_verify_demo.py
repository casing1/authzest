"""Offline walkthrough: only the exact fixed local checker may start a process."""

import asyncio
import json
import os
import signal
import socket
import sys
from contextlib import suppress
from hashlib import sha256
from pathlib import Path

import pytest
from scripts import demo_verify
from scripts.demo_proposal import FIXTURE_ROOT

from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.runner import fixture_check
from authzest.runner._fixture_workspace import supported

pytestmark = pytest.mark.skipif(not supported(), reason="POSIX owned-fixture workflow")


@pytest.fixture(autouse=True)
def fixed_worker_only(monkeypatch):
    original = asyncio.create_subprocess_exec
    children = []

    def forbidden(*args, **kwargs):
        pytest.fail("This offline demonstration must not connect to a provider or network")

    async def create(*args, **kwargs):
        assert args == (sys.executable, "-I", "-S", "-c", fixture_check.WORKER_SOURCE)
        assert kwargs["start_new_session"] is True
        assert "HOME" not in kwargs["env"] and "CODEX_HOME" not in kwargs["env"]
        child = await original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    yield children
    for child in children:
        if child.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)


@pytest.mark.parametrize(
    "action",
    [
        "approve",
        "skip",
        "skip-cancel",
        "wrong-token",
        "decline-apply",
        "decline-restore",
        "stale-verify",
        "stale-restore",
    ],
)
def test_offline_walkthrough_real_fixed_worker_and_independent_choices(
    tmp_path, fixed_worker_only, action
):
    original = FIXTURE_ROOT.joinpath("main.py").read_bytes()
    output = []
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        preview = next(item for item in map(json.loads, output) if "changes" in item)
        workspace = Path(preview["workspace"])
        if "'apply " in prompt:
            assert preview["changes"][0]["diff"]
            if action == "decline-apply":
                return ""
        elif "'verify " in prompt:
            plan = json.loads(output[-1])
            assert plan["kind"] == "fixture-configuration-verification-plan"
            assert prompt.split("'")[1] == f"verify {plan['plan_id']}"
            assert plan["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
            assert fixed_worker_only == []  # Applying the copy was not verification approval.
            if action == "skip":
                return ""
            if action == "skip-cancel":
                raise EOFError()
            if action == "wrong-token":
                return prompts[0].split("'")[1]
            if action == "stale-verify":
                workspace.joinpath("main.py").write_text("# later unapproved edit\n")
        else:
            assert "'restore " in prompt
            if action == "decline-restore":
                return ""
            if action == "stale-restore":
                workspace.joinpath("main.py").write_text("# later unapproved edit\n")
        return prompt.split("'")[1]

    result = asyncio.run(demo_verify.run_demo(read=read, emit=output.append, parent=tmp_path))
    assert result["live_provider_calls"] == 0
    assert result["draft_provenance"] == "caller-authored-mock"
    assert result["simulated_draft"] is True and result["decisions_authenticated"] is False
    assert result["original_checkout_modified"] is False
    assert result["verification_scope"] == "source-configuration"
    assert result["runtime_verification_status"] == "not-run"
    assert FIXTURE_ROOT.joinpath("main.py").read_bytes() == original == FIXTURE_SOURCE.encode()
    assert json.loads(output[0])["kind"] == "offline-owned-fixture-configuration-preview"
    assert all(isinstance(json.loads(item), dict) for item in output)
    checked = action in ("approve", "decline-restore", "stale-restore")
    assert len(fixed_worker_only) == int(checked)
    assert all(child.returncode is not None for child in fixed_worker_only)
    workspace = Path(result["workspace"])
    journal = json.loads(workspace.joinpath("record.json").read_text())
    assert journal["runtime_verification_status"] == "not-run"
    if action == "decline-apply":
        assert len(prompts) == 1
        assert result["verification"] is result["restoration"] is None
    else:
        assert [prompt.split("'")[1].split()[0] for prompt in prompts] == [
            "apply",
            "verify",
            "restore",
        ]
    if action.startswith("stale-"):
        assert result["status"] == "application-failed" and result["exit_code"] == 1
        assert workspace.joinpath("main.py").read_text() == "# later unapproved edit\n"
        assert result["restoration"]["restored"] is False
    else:
        assert result["status"] == "completed" and result["exit_code"] == 0
        expected = FIXTURE_AFTER if action == "decline-restore" else FIXTURE_SOURCE
        assert workspace.joinpath("main.py").read_text() == expected
    if checked:
        assert result["verification_status"] == "passed"
        assert result["verification"]["source_sha256"] == sha256(FIXTURE_AFTER.encode()).hexdigest()
        assert result["verification"]["check_id"] == fixture_check.CHECK_ID
        assert result["verification"]["exit_code"] == 0
        assert journal["verification_status"] == "passed"
    elif not action.startswith("stale-"):
        assert result["verification_status"] == "not-run"


def test_worker_io_failure_is_redacted_nonzero_and_still_offers_restore(
    tmp_path, monkeypatch, fixed_worker_only
):
    async def fail(*args):
        raise OSError("PRIVATE-LOCAL-STDERR")

    monkeypatch.setattr(fixture_check, "_exchange", fail)
    output = []
    result = asyncio.run(
        demo_verify.run_demo(
            read=lambda prompt: prompt.split("'")[1], emit=output.append, parent=tmp_path
        )
    )
    assert result["status"] == "verification-failed" and result["exit_code"] == 1
    assert result["verification_status"] == "failed"
    assert result["restoration"]["restored"] is True
    assert len(fixed_worker_only) == 1 and fixed_worker_only[0].returncode is not None
    assert "PRIVATE-LOCAL-STDERR" not in json.dumps(result) + "".join(output)
    assert "retained workspace record" in result["detail"]


def test_demo_cancellation_retains_applied_record_and_stops_actual_fixed_worker(
    tmp_path, monkeypatch, fixed_worker_only
):
    async def waiting_exchange(*args):
        await asyncio.Event().wait()

    monkeypatch.setattr(fixture_check, "_exchange", waiting_exchange)

    async def run():
        task = asyncio.create_task(
            demo_verify.run_demo(
                read=lambda prompt: prompt.split("'")[1], emit=lambda _: None, parent=tmp_path
            )
        )
        async with asyncio.timeout(2):
            while not fixed_worker_only:
                await asyncio.sleep(0.01)
        task.cancel()
        return await task

    result = asyncio.run(run())
    assert result["status"] == "cancelled" and result["exit_code"] == 130
    assert "verification_status" not in result
    assert result["runtime_verification_status"] == "not-run"
    assert result["restoration"] is None
    assert fixed_worker_only[0].returncode is not None
    journal = json.loads(Path(result["workspace"]).joinpath("record.json").read_text())
    assert journal["applied"] is True and journal["restored"] is False
    assert journal["verification_status"] == "failed"
    assert journal["verification"]["execution_attempted"] is True
    assert "retained workspace record" in result["detail"]


def test_demo_setup_error_has_no_false_verification_claim_or_raw_error(tmp_path, monkeypatch):
    def fail():
        raise RuntimeError("PRIVATE-LOCAL-STDERR")

    monkeypatch.setattr(demo_verify, "build_demo_proposal", fail)
    result = asyncio.run(demo_verify.run_demo(emit=lambda _: None, parent=tmp_path))
    assert result["status"] == "workflow-failed" and result["exit_code"] == 1
    assert "verification_status" not in result
    assert result["workspace"] is None and list(tmp_path.iterdir()) == []
    assert "PRIVATE-LOCAL-STDERR" not in json.dumps(result)


@pytest.mark.parametrize("argument", ["main.py", "--yes", "--command=echo", "--path=main.py"])
def test_demo_rejects_general_source_commands_and_automatic_approval(monkeypatch, argument):
    monkeypatch.setattr(sys, "argv", ["demo_verify", argument])
    monkeypatch.setattr(
        demo_verify, "run_demo", lambda: pytest.fail("Reject arguments before preparing the demo")
    )
    with pytest.raises(SystemExit) as error:
        demo_verify.main()
    assert error.value.code == 2


@pytest.mark.parametrize("exit_code", [0, 1, 130])
def test_main_prints_summary_and_preserves_workflow_exit_code(monkeypatch, capsys, exit_code):
    monkeypatch.setattr(sys, "argv", ["demo_verify"])

    async def result():
        return {"exit_code": exit_code, "runtime_verification_status": "not-run"}

    monkeypatch.setattr(demo_verify, "run_demo", result)
    assert demo_verify.main() == exit_code
    assert json.loads(capsys.readouterr().out)["exit_code"] == exit_code


@pytest.mark.parametrize("failure,expected", [(KeyboardInterrupt, 130), (RuntimeError, 1)])
def test_main_sanitizes_unhandled_interruption_and_error(monkeypatch, capsys, failure, expected):
    monkeypatch.setattr(sys, "argv", ["demo_verify"])

    async def fail():
        raise failure("PRIVATE-LOCAL-STDERR")

    monkeypatch.setattr(demo_verify, "run_demo", fail)
    assert demo_verify.main() == expected
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert "verification_status" not in summary
    assert summary["runtime_verification_status"] == "not-run"
    assert "PRIVATE-LOCAL-STDERR" not in output
