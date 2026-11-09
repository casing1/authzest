"""Fixed owned fake pipes exercise the pure coordinator, never live acceptance.

Only this test harness launches two sequential, descendant-free Python fixtures.
Its watchdog/cleanup are test controls, not a product launcher, sandbox, complete
process-tree proof, slot timing proof or permission to use an account/model.
"""

from __future__ import annotations

import copy
import json
import os
import selectors
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from scripts import evaluation_coordinator as coordinator
from scripts import evaluation_dispatch_recipe as recipe
from scripts import evaluation_invocation as codec
from scripts import evaluation_semantics as common
from scripts import evaluation_trial_plan as planner

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owned POSIX pipe lifecycle fixture")

FIXTURE = Path(__file__).parent / "fixtures/evaluation_protocol/fake_coordinator_server.py"
PYTHON = str(Path(sys.executable).absolute())
ENVIRONMENT = {"LANG": "C", "LC_ALL": "C"}
MODES = frozenset(
    {
        "success",
        "fragmented",
        "nonzero",
        "malformed",
        "truncated",
        "eof",
        "stall",
        "ignore-term",
        "broken-pipe",
    }
)


def _frame(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


@pytest.fixture
def owned_candidate():
    # Public task input only: no stored model response/reference-answer corpus.
    configuration = planner.TrialConfig("synthetic-model", "high", 1, 30)
    invocation = codec.prepare_candidate(codec.ROOT, configuration).invocations[0]
    boundary = common.Boundary(configuration, "/synthetic/empty", "synthetic-thread")
    return invocation, boundary


@pytest.fixture(autouse=True)
def owned_process_only(monkeypatch, tmp_path):
    original = subprocess.Popen
    started = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network or non-owned process forbidden")

    def guarded(args, **kwargs):
        assert type(args) is list and len(args) == 5
        assert args[:4] == [PYTHON, "-I", "-S", str(FIXTURE.resolve())]
        assert args[4] in MODES
        assert kwargs == {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "cwd": tmp_path,
            "env": ENVIRONMENT,
            "bufsize": 0,
            "start_new_session": True,
        }
        assert not list(tmp_path.iterdir())
        process = original(args, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", guarded)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    yield started
    for process in started:
        assert process.returncode is not None
        assert process.stdin.closed and process.stdout.closed
        with pytest.raises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)
    assert not list(tmp_path.iterdir())


class _OwnedPeer:
    """Private test-only fixed executable/script/modes, with owned-child cleanup."""

    def __init__(self, mode: str, cwd: Path):
        assert mode in MODES
        self.deadline = time.monotonic() + 5
        self.signals: list[int] = []
        self.process = subprocess.Popen(
            [PYTHON, "-I", "-S", str(FIXTURE.resolve()), mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            env=ENVIRONMENT.copy(),
            bufsize=0,
            start_new_session=True,
        )
        try:
            assert self.process.stdin is not None and self.process.stdout is not None
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("owned-fixture-watchdog")
        return value

    def _wait(self, pipe, event: int, timeout: float | None = None) -> None:
        remaining = self._remaining()
        if timeout is not None:
            remaining = min(remaining, timeout)
        with selectors.DefaultSelector() as selector:
            selector.register(pipe, event)
            if not selector.select(remaining):
                raise TimeoutError("owned-fixture-io-timeout")

    def write(self, raw: bytes) -> None:
        view = memoryview(raw)
        while view:
            self._wait(self.process.stdin, selectors.EVENT_WRITE)
            try:
                written = os.write(self.process.stdin.fileno(), view)
            except BlockingIOError:
                continue
            assert written > 0
            view = view[written:]

    def read(self, *, size: int = 65536, timeout: float | None = None) -> bytes:
        self._wait(self.process.stdout, selectors.EVENT_READ, timeout)
        return os.read(self.process.stdout.fileno(), size)

    def _signal(self, signum: int) -> None:
        if self.process.poll() is not None:
            return
        try:
            assert os.getpgid(self.process.pid) == self.process.pid
            os.killpg(self.process.pid, signum)
            self.signals.append(signum)
        except ProcessLookupError:
            pass

    def close(self) -> None:
        try:
            if self.process.poll() is None:
                self._signal(signal.SIGTERM)
                try:
                    self.process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    self._signal(signal.SIGKILL)
                    self.process.wait(timeout=1)
            else:
                self.process.wait(timeout=1)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    stream.close()


def _config(boundary) -> dict:
    nested = {}
    for path, value in recipe.descriptor(boundary.configuration)["process_config"].items():
        parts = path.split(".")
        parent = nested
        for part in parts[:-1]:
            parent = parent.setdefault(part, {})
        parent[parts[-1]] = copy.deepcopy(value)
    nested["mcp_servers"] = {}
    return {"config": nested, "origins": {}}


def _thread(boundary) -> dict:
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
            "cliVersion": "0.153.0",
            "createdAt": 1,
            "updatedAt": 2,
            "cwd": boundary.cwd,
            "ephemeral": True,
            "id": boundary.thread_id,
            "modelProvider": "openai",
            "preview": "",
            "projectId": None,
            "sessionId": "synthetic-session",
            "source": "appServer",
            "status": {"type": "idle"},
            "turns": [],
        },
    }


def _response(invocation) -> str:
    spec = invocation.slot.spec
    # Preserve intentionally noncanonical whitespace through the private outcome.
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
                "answers": [{"question_id": item.id, "answer": None} for item in spec.questions],
            },
        },
        indent=2,
    )


def _turn(boundary, text: str) -> tuple[dict, list[dict]]:
    ack = {"turn": {"id": "synthetic-turn", "items": [], "status": "inProgress", "error": None}}
    item = {"type": "agentMessage", "id": "synthetic-item", "text": text, "phase": "final_answer"}
    common_fields = {"threadId": boundary.thread_id, "turnId": "synthetic-turn"}
    settings = {
        "model": boundary.configuration.model,
        "modelProvider": "openai",
        "cwd": boundary.cwd,
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
        "effort": boundary.configuration.effort,
        "collaborationMode": {
            "mode": "default",
            "settings": {
                "model": boundary.configuration.model,
                "reasoning_effort": boundary.configuration.effort,
                "developer_instructions": codec.INSTRUCTIONS,
            },
        },
    }
    values = [
        ("thread/settings/updated", {"threadId": boundary.thread_id, "threadSettings": settings}),
        ("turn/started", {"threadId": boundary.thread_id, "turn": copy.deepcopy(ack["turn"])}),
        (
            "item/started",
            {
                **common_fields,
                "item": {"id": item["id"], "type": "agentMessage", "text": ""},
                "startedAtMs": 1000,
            },
        ),
        ("item/agentMessage/delta", {**common_fields, "itemId": item["id"], "delta": text}),
        ("item/completed", {**common_fields, "item": item, "completedAtMs": 1001}),
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
    return ack, [{"method": method, "params": params} for method, params in values]


def _steps(invocation, boundary, phase: str, *, fault: str | None = None):
    frames = recipe.frames(invocation, cwd=boundary.cwd, thread_id=boundary.thread_id)
    requests = [copy.deepcopy(item["message"]) for item in frames["frame_candidates"]]
    if phase == "discovery":
        requests = requests[:3]
    text = _response(invocation)
    if fault == "stale":
        stale = json.loads(text)
        stale["invocation_id"] = "eval-invocation-v2-" + "0" * 64
        text = json.dumps(stale)
    ack, events = _turn(boundary, text)
    if fault == "foreign":
        events[2]["params"]["turnId"] = "foreign-turn"
    elif fault == "failed":
        events[-1]["params"]["turn"]["status"] = "failed"
    elif fault == "settings":
        events[0]["params"]["threadSettings"]["model"] = "wrong-model"
    elif fault == "warning":
        events.insert(0, {"method": "warning", "params": {"message": "synthetic"}})
    results = {
        "initialize": {
            "userAgent": "codex_cli_rs/0.153.0 (synthetic 한글)",
            "codexHome": "/synthetic/codex-home",
            "platformFamily": "unix",
            "platformOs": "linux",
        },
        "config/read": _config(boundary),
        "remoteControl/status/read": {
            "installationId": "synthetic-installation",
            "serverName": "synthetic-server",
            "status": "disabled",
        },
        "account/read": {
            "requiresOpenaiAuth": True,
            "account": {"type": "chatgpt", "email": "synthetic@example.test", "planType": "plus"},
        },
        "model/list": {
            "data": [
                {
                    "id": boundary.configuration.model,
                    "model": boundary.configuration.model,
                    "displayName": "Synthetic model",
                    "description": "Synthetic only",
                    "hidden": False,
                    "isDefault": False,
                    "defaultReasoningEffort": boundary.configuration.effort,
                    "supportedReasoningEfforts": [
                        {
                            "reasoningEffort": boundary.configuration.effort,
                            "description": "Synthetic",
                        }
                    ],
                }
            ],
            "nextCursor": None,
        },
        "thread/start": _thread(boundary),
        "turn/start": ack,
    }
    steps = []
    for request in requests:
        method = request["method"]
        replies = (
            [] if method == "initialized" else [{"id": request["id"], "result": results[method]}]
        )
        if method == "turn/start":
            replies.extend(events)
            if fault == "duplicate":
                replies.append(copy.deepcopy(replies[0]))
            elif fault == "foreign-rpc":
                replies[0]["id"] += 1
        steps.append({"request": request, "replies": replies})
    return steps


def _drive(slot, steps, tmp_path, *, mode="success", cleanup=True, cancel=False):
    sent = []
    with _OwnedPeer(mode, tmp_path) as peer:
        peer.write(_frame({"steps": steps}))
        try:
            while True:
                snapshot = slot.snapshot()
                if snapshot["failure_code"] is not None:
                    break
                if cancel and snapshot["turn_acknowledged"]:
                    slot.abort("interrupted")
                    break
                if snapshot["next_method"] is not None:
                    request = slot.next_frame()
                    sent.append(json.loads(request)["method"])
                    peer.write(request)
                    if len(sent) == len(steps):
                        peer.process.stdin.close()
                    continue
                timeout = (
                    0.15
                    if snapshot["turn_acknowledged"] and mode in ("stall", "ignore-term")
                    else None
                )
                chunk = peer.read(size=7 if mode == "fragmented" else 65536, timeout=timeout)
                if not chunk:
                    peer.process.wait(timeout=peer._remaining())
                    break
                slot.feed(chunk)
        except TimeoutError:
            assert slot.snapshot()["turn_acknowledged"], "timeout must follow deterministic ack"
            slot.abort("timeout")
        except BrokenPipeError:
            assert sent == ["initialize", "initialized"]
            slot.abort("failed")
        except coordinator.CoordinatorError:
            assert slot.snapshot()["failure_code"] is not None
    # Terminal process status and cleanup assertion are explicit, not inferred by
    # coordinator from synthetic bytes or from this caller-controlled boolean.
    try:
        slot.finish_phase(exit_code=peer.process.returncode, cleanup_confirmed=cleanup)
    except coordinator.CoordinatorError:
        assert slot.snapshot()["failure_code"] is not None
    return sent, peer


def _discovered(invocation, boundary, tmp_path):
    slot = coordinator.SlotCoordinator(invocation, boundary)
    sent, _ = _drive(slot, _steps(invocation, boundary, "discovery"), tmp_path)
    assert sent == ["initialize", "initialized", "config/read"]
    assert slot.snapshot()["phase"] == "generation"
    assert slot.snapshot()["outcome_ready"] is False
    return slot


@pytest.mark.parametrize("mode", ["success", "fragmented"])
def test_two_owned_phases_preserve_exact_private_final_text_and_no_live_claims(
    owned_candidate, tmp_path, mode, capfd, owned_process_only
):
    invocation, boundary = owned_candidate
    slot = coordinator.SlotCoordinator(invocation, boundary)
    for phase in ("discovery", "generation"):
        steps = _steps(invocation, boundary, phase)
        sent, peer = _drive(slot, steps, tmp_path, mode=mode)
        assert sent == [step["request"]["method"] for step in steps]
        assert peer.process.returncode == 0
        assert peer.process.stderr is None
    assert len(owned_process_only) == 2
    outcome = slot.take_outcome()
    assert outcome == {"raw": _response(invocation), "failure": None}
    assert codec.decode_response(invocation, outcome["raw"])["status"] == "valid"
    snapshot = slot.snapshot()
    assert snapshot["terminal"] is True
    assert snapshot["accepted_trial"] is False
    assert snapshot["runtime_observed"] is False
    assert snapshot["actual_model_calls"] == 0
    rendered = json.dumps(snapshot)
    for private in (
        boundary.cwd,
        boundary.thread_id,
        invocation.invocation_id,
        "synthetic@example.test",
        _response(invocation),
    ):
        assert private not in rendered
    with pytest.raises(ValueError):
        slot.take_outcome()
    assert "OWNED_COORDINATOR_STDERR" not in "".join(capfd.readouterr())


@pytest.mark.parametrize(
    "fault", ["stale", "foreign", "failed", "settings", "warning", "duplicate", "foreign-rpc"]
)
def test_owned_generation_wire_and_semantic_mismatches_never_export_raw(
    owned_candidate, tmp_path, fault
):
    invocation, boundary = owned_candidate
    slot = _discovered(invocation, boundary, tmp_path)
    _drive(slot, _steps(invocation, boundary, "generation", fault=fault), tmp_path)
    assert slot.take_outcome() == {"raw": None, "failure": "integrity"}
    assert slot.snapshot()["failure_code"] is not None


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("malformed", "integrity"),
        ("truncated", "integrity"),
        ("eof", "integrity"),
        ("nonzero", "failed"),
    ],
)
def test_owned_generation_transport_end_is_not_semantic_success(
    owned_candidate, tmp_path, mode, expected
):
    invocation, boundary = owned_candidate
    slot = _discovered(invocation, boundary, tmp_path)
    _drive(slot, _steps(invocation, boundary, "generation"), tmp_path, mode=mode)
    assert slot.take_outcome() == {"raw": None, "failure": expected}


@pytest.mark.parametrize(
    "mode,cancel,expected",
    [
        ("stall", False, "timeout"),
        ("stall", True, "interrupted"),
        ("ignore-term", False, "timeout"),
    ],
)
def test_owned_timeout_and_cancel_follow_turn_ack_and_reap_fixed_child(
    owned_candidate, tmp_path, mode, cancel, expected
):
    invocation, boundary = owned_candidate
    slot = _discovered(invocation, boundary, tmp_path)
    _, peer = _drive(
        slot, _steps(invocation, boundary, "generation"), tmp_path, mode=mode, cancel=cancel
    )
    assert slot.snapshot()["turn_acknowledged"] is True
    assert slot.take_outcome() == {"raw": None, "failure": expected}
    assert signal.SIGTERM in peer.signals
    if mode == "ignore-term":
        assert signal.SIGKILL in peer.signals
        assert peer.process.returncode == -signal.SIGKILL


def test_owned_discovery_broken_pipe_is_synchronized_after_initialize(
    owned_candidate, tmp_path, owned_process_only
):
    invocation, boundary = owned_candidate
    slot = coordinator.SlotCoordinator(invocation, boundary)
    sent, _ = _drive(slot, _steps(invocation, boundary, "discovery"), tmp_path, mode="broken-pipe")
    assert sent == ["initialize", "initialized"]
    assert len(owned_process_only) == 1
    assert slot.take_outcome() == {"raw": None, "failure": "failed"}


@pytest.mark.parametrize("phase", ["discovery", "generation"])
def test_unconfirmed_cleanup_never_promotes_observed_fake_success(owned_candidate, tmp_path, phase):
    invocation, boundary = owned_candidate
    slot = coordinator.SlotCoordinator(invocation, boundary)
    if phase == "generation":
        slot = _discovered(invocation, boundary, tmp_path)
    _drive(slot, _steps(invocation, boundary, phase), tmp_path, cleanup=False)
    assert slot.take_outcome() == {"raw": None, "failure": "integrity"}


@pytest.mark.parametrize("failure_on,error", [(1, OSError), (2, KeyboardInterrupt)])
def test_owned_setup_failure_reaps_child_before_context_entry(
    tmp_path, monkeypatch, owned_process_only, failure_on, error
):
    original = os.set_blocking
    calls = 0

    def fail_setup(fd, blocking):
        nonlocal calls
        calls += 1
        if calls == failure_on:
            raise error("synthetic-setup-failure")
        return original(fd, blocking)

    monkeypatch.setattr(os, "set_blocking", fail_setup)
    with pytest.raises(error, match="synthetic-setup-failure"):
        _OwnedPeer("success", tmp_path)
    assert len(owned_process_only) == 1
    assert owned_process_only[0].returncode is not None
