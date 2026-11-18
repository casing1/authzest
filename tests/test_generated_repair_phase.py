"""One owned inert copy and maintained fake collaborators; never start a guest."""

from __future__ import annotations

import ast
import asyncio
import base64
import builtins
import json
import os
import socket
import subprocess
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.contracts import canonical
from authzest.runner import _generated_repair_phase as phase
from authzest.runner._generated_repair_process import ProcessError, ProcessHandle, ProcessSnapshot
from authzest.runner._generated_repair_runtime_profile import build_container_create_plan
from authzest.runner._generated_repair_workspace import GeneratedRepairWorkspace, supported
from authzest.runner.generated_repair_controls import build_generated_repair_controls
from test_generated_repair_runtime_profile import profile
from test_generated_repair_session import _preview

pytestmark = pytest.mark.skipif(not supported(), reason="POSIX owned temporary-copy scope")
NONCE = "a" * 32
PLAN_ID = "generated-repair-session-plan-" + "b" * 64


def _capture(candidate):
    facts, wire_bytes = [], 0
    for case in build_generated_repair_controls().to_dict()["cases"]:
        for request in case["requests"]:
            expected = request["expected_" + candidate]
            body = canonical(expected["body_json"]).encode()
            headers = [["Content-Type", "application/json"], ["Content-Length", str(len(body))]]
            wire_bytes += len(f"HTTP/1.1 {expected['status_code']} \r\n".encode()) + 2 + len(body)
            wire_bytes += sum(len(key) + len(value) + 4 for key, value in headers)
            facts.append(
                {
                    "request_id": request["request_id"],
                    "status_code": expected["status_code"],
                    "headers": headers,
                    "body_base64": base64.b64encode(body).decode(),
                }
            )
    return canonical(
        {
            "schema_version": "1.0",
            "kind": "generated-repair-relay-capture",
            "status": "complete",
            "request_count": 21,
            "facts": facts,
            "failure": None,
            "failed_request_index": None,
            "wire_bytes": wire_bytes,
            "call_count": 42,
            "close_status": "closed",
            "close_failure": None,
            "cancellation": None,
            "provenance": "caller-supplied-unverified",
            "execution_status": "not-established",
            "authorization_status": "unknown",
            "verified_fix": False,
        }
    ).encode()


class World:
    def __init__(self, copy):
        self.copy = copy
        self.time = 100.0
        self.candidate = "before"
        self.events, self.calls, self.containers, self.stages, self.pools = [], [], {}, [], []
        self.plans = {}
        self.hook = lambda *_: None
        self.command_hook = lambda *_: None
        self.wait_hook = lambda *_: None
        self.waits = []
        self.pump_hook = None
        self.guard_hook = lambda: None
        self.stage_close_hook = lambda *_: None
        self.terminate_hook = lambda *_: None
        self.inspect_hook = lambda *_: None
        self.t_exit = None
        self.a_hint = b"AUTHZEST_A_STARTED\n"
        self.relay_candidate = None
        self.local_cleanup = True

    def guard(self):
        self.events.append("guard")
        return self.guard_hook()

    def invoke(self, *, budget=None):
        return phase.execute_generated_repair_phase(
            self.copy,
            self.candidate,
            profile(),
            session_nonce=NONCE,
            phase_plan_id=PLAN_ID,
            dispatch_guard=self.guard,
            evidence_budget=phase.SessionEvidenceBudget() if budget is None else budget,
        )


class FakePool:
    def __init__(self, world, *, clock, max_output_bytes, cleanup_reserve_bytes=0):
        self.world, self.clock, self.maximum = world, clock, max_output_bytes
        self.records, self.output_bytes = [], 0
        self.first_failure = None
        world.pools.append(self)

    def start(self, argv, env, *, deadline, label):
        argv = list(argv)
        self.world.calls.append((argv, dict(env), deadline, label))
        self.world.command_hook(argv, label)
        args = argv[4:]
        action = args[0]
        role, stdout, stderr, code = None, b"", b"", 0
        if action == "create":
            role = next(
                arg.rsplit("=", 1)[1]
                for arg in argv
                if arg.startswith("--label=org.authzest.generated.role=")
            )
            plan = self.world.plans[role]
            container_id = str(len(self.world.containers) + 1) * 64
            self.world.containers[container_id] = {"plan": plan, "status": "created", "exit": 0}
            stdout = (container_id + "\n").encode()
        elif action == "ls":
            selector = next(arg[9:] for arg in args if arg.startswith("--filter="))
            matches = [
                key
                for key, item in self.world.containers.items()
                if (
                    selector == "id=" + key
                    or selector == "name=^/" + item["plan"]["owned_name"] + "$"
                )
            ]
            stdout = ("\n".join(matches) + ("\n" if matches else "")).encode()
        elif action == "inspect":
            item = self.world.containers[args[1]]
            plan = item["plan"]
            role = plan["role"]
            value = {
                "Id": args[1],
                "Name": "/" + plan["owned_name"],
                "Image": plan["profile"]["images"][role]["image_id"],
                "Config": {
                    "Image": plan["profile"]["images"][role]["image_id"],
                    "Labels": {
                        "org.authzest.generated.session": plan["session_nonce"],
                        "org.authzest.generated.role": role,
                        "org.authzest.generated.nonce": plan["role_nonce"],
                    },
                },
                "State": {
                    "Status": item["status"],
                    "Running": item["status"] == "running",
                    "Dead": False,
                    "OOMKilled": False,
                    "Restarting": False,
                    "StartedAt": "0001-01-01T00:00:00Z"
                    if item["status"] == "created"
                    else "2026-11-15T01:00:00Z",
                    "ExitCode": item["exit"],
                    "Error": "",
                },
            }
            self.world.inspect_hook(value, label)
            stdout = canonical([value]).encode()
        elif action == "start":
            assert args[1] == "--attach" and len(args) == 3
            item = self.world.containers[args[2]]
            role = item["plan"]["role"]
            if role == "A":
                item["status"] = "running"
                stdout, code = self.world.a_hint, None
            else:
                item["status"] = "exited"
                code = (1 if self.world.candidate == "before" else 0) if role == "T" else 0
                if role == "T" and self.world.t_exit is not None:
                    code = self.world.t_exit
                item["exit"] = code
                stdout = (
                    b"generated test output is auxiliary\n"
                    if role == "T"
                    else _capture(self.world.relay_candidate or self.world.candidate)
                )
        elif action == "rm":
            assert args[1] == "--force" and len(args) == 3
            item = self.world.containers.pop(args[2])
            role = item["plan"]["role"]
            if role == "A":
                for index, value in enumerate(self.records):
                    if value.label.startswith("attach-start-A"):
                        self.records[index] = replace(value, returncode=137, complete=True)
        else:
            pytest.fail("Unexpected fake Docker subcommand: " + action)
        handle = ProcessHandle(len(self.records), label)
        snapshot = ProcessSnapshot(
            label, 10 + handle.token, code, stdout, stderr, code is not None, (), False
        )
        self.records.append(snapshot)
        self.output_bytes += len(stdout) + len(stderr)
        self.world.hook(self, handle, role)
        return handle

    def wait(self, handle, deadline):
        self.world.events.append("wait:" + handle.label)
        self.world.waits.append((handle.label, deadline))
        self.world.wait_hook(self, handle, deadline)
        if self.output_bytes > self.maximum:
            self.first_failure = "combined-output-limit"
            raise ProcessError(self.first_failure, tuple(self.records))
        return self.snapshot(handle)

    def snapshot(self, handle):
        return self.records[handle.token]

    def snapshots(self):
        return tuple(self.records)

    def pump(self, deadline):
        if self.world.pump_hook is not None:
            self.world.pump_hook(self, deadline)
            return tuple(self.records)
        self.world.time = deadline
        self.first_failure = "original-deadline-expired"
        raise ProcessError(self.first_failure, tuple(self.records))

    def begin_cleanup(self, deadline):
        self.world.events.append("begin-cleanup")

    def terminate_all(self, deadline):
        self.world.terminate_hook(self)
        self.records = [
            replace(value, local_cleanup_confirmed=self.world.local_cleanup)
            for value in self.records
        ]
        self.world.events.append("terminate-local")
        return tuple(self.records)


@pytest.fixture
def world(monkeypatch, tmp_path):
    assert ast.unparse(ast.Constant(value=None)) == "None"
    copy = GeneratedRepairWorkspace(_preview(), _parent=tmp_path)
    value = World(copy)
    original_compile, original_import = builtins.compile, builtins.__import__
    original_mkdtemp = phase.tempfile.mkdtemp

    def forbidden(*_, **__):
        pytest.fail("Phase tests must use memory-only process/network collaborators")

    def guarded_compile(source, filename, mode, flags=0, *args, **kwargs):
        if not flags & ast.PyCF_ONLY_AST:
            forbidden()
        return original_compile(source, filename, mode, flags, *args, **kwargs)

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app",
            "docker",
            "fastapi",
            "uvicorn",
            "openai",
            "httpx",
            "requests",
        }:
            forbidden()
        return original_import(name, *args, **kwargs)

    class Pin:
        def __init__(self, profile, tick):
            self.tick = tick
            self.check()

        def check(self, **_):
            self.tick()
            value.events.append("client-pin")

    class Stage:
        def __init__(self, workspace, candidate, role):
            assert workspace is copy and candidate == value.candidate
            self.role, self.closed = role, False
            value.stages.append(self)

        def assert_current(self):
            value.events.append("stage-current:" + self.role)

        def prepare_create(self, runtime, nonce, role_nonce):
            kwargs = {
                "session_nonce": nonce,
                "role_nonce": role_nonce,
                "staging_root": "/maintained/inert-inputs/" + self.role,
                "application_sha256": sha256(copy.read_source().data).hexdigest(),
            }
            if self.role == "T":
                kwargs["test_sha256"] = sha256(copy.read_test().data).hexdigest()
            plan = build_container_create_plan(runtime, self.role, **kwargs)
            value.plans[self.role] = plan.to_dict()
            return SimpleNamespace(to_dict=lambda: {"container_create_plan": plan.to_dict()})

        def close(self):
            self.closed = True
            value.events.append("stage-close:" + self.role)
            value.stage_close_hook(self)

    def create_plan(*args, **kwargs):
        plan = build_container_create_plan(*args, **kwargs)
        value.plans["B"] = plan.to_dict()
        return plan

    def metadata(runtime, *, phase_deadline, setup_deadline, before_query):
        assert runtime == profile() and setup_deadline <= phase_deadline
        before_query()
        value.events.append("metadata")
        return SimpleNamespace(
            to_dict=lambda: {
                "status": "metadata-match",
                "wire_bytes": 100,
                "metadata": {
                    "engine": {
                        "default_runtime": "runc",
                        "cgroup_version": "2",
                        "security_options": ["name=seccomp,profile=builtin"],
                        "reported_capabilities": {
                            key: True
                            for key in (
                                "MemoryLimit",
                                "SwapLimit",
                                "CpuCfsPeriod",
                                "CpuCfsQuota",
                                "PidsLimit",
                            )
                        },
                    },
                    "images": {
                        role: {
                            "config": {
                                "environment": list(phase._IMAGE_ENVIRONMENT),
                                "volumes": None,
                                "user": "65532:65532",
                            }
                        }
                        for role in "TAB"
                    },
                },
            }
        )

    def inspect_stopped(plan, raw, *, container_id, image_environment):
        data = plan.to_dict()
        item = json.loads(raw)[0]
        assert item["Id"] == container_id and item["State"]["Status"] == "created"
        assert image_environment == list(phase._IMAGE_ENVIRONMENT)
        phase._owned(item, data, container_id)
        value.events.append("stopped-inspected:" + data["role"])
        return SimpleNamespace(
            to_dict=lambda: {"kind": "fake-stopped-comparison", "role": data["role"]}
        )

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "compile", guarded_compile)
    for name in ("exec", "eval"):
        monkeypatch.setattr(builtins, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(phase, "monotonic", lambda: value.time)
    monkeypatch.setattr(phase, "_ClientPin", Pin)
    monkeypatch.setattr(phase, "_endpoint_identity", forbidden)
    monkeypatch.setattr(phase, "ProcessPool", lambda **kwargs: FakePool(value, **kwargs))
    monkeypatch.setattr(phase, "GeneratedRepairInputStage", Stage)
    monkeypatch.setattr(phase, "build_container_create_plan", create_plan)
    monkeypatch.setattr(phase, "observe_runtime_metadata", metadata)
    monkeypatch.setattr(phase, "validate_stopped_container", inspect_stopped)
    monkeypatch.setattr(
        phase.tempfile, "mkdtemp", lambda **kwargs: original_mkdtemp(dir=tmp_path, **kwargs)
    )
    try:
        yield value
    finally:
        copy.close()


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_full_fixed_phase_observes_current_bytes_comparison_and_exact_cleanup(world, candidate):
    world.candidate = candidate
    if candidate == "after":
        world.copy.apply_source(world.copy.read_source(), guard=lambda: None)
    before = world.copy.read_source()
    result = world.invoke().to_dict()
    assert result["status"] == "complete", result
    assert result["cleanup_confirmed"] is True and result["cleanup_errors"] == []
    assert result["test_exit_code"] == (1 if candidate == "before" else 0)
    assert result["comparison"]["matches_expected_profile"] is True
    assert result["comparison"]["matching_request_count"] == 21
    assert result["application_sha256"] == sha256(before.data).hexdigest()
    assert world.copy.read_source() == before
    assert (
        result["source_applied"]
        is result["verified_fix"]
        is result["execution_authorized"]
        is False
    )
    assert world.containers == {} and all(stage.closed for stage in world.stages)
    starts = [argv for argv, _, _, _ in world.calls if argv[4] == "start"]
    assert [row[4:6] for row in starts] == [["start", "--attach"]] * 3
    assert [item["role"] for item in result["owned"]] == ["T", "A", "B"]
    assert all(item["absence_observed"] for item in result["owned"])
    assert all(env == {"DOCKER_API_VERSION": "1.45"} for _, env, _, _ in world.calls)
    plan_b = world.plans["B"]
    assert plan_b["application_container_id"] == result["owned"][1]["id"]
    assert "--network=container:" + plan_b["application_container_id"] in plan_b["argv"]
    assert plan_b["declared_files"] == []
    assert not any(
        arg.startswith(("--publish=", "-p=", "--add-host=", "--mount=")) for arg in plan_b["argv"]
    )
    assert all("--network=none" in world.plans[role]["argv"] for role in "TA")


def test_shared_evidence_budget_accounts_both_phases_and_does_not_refresh(world):
    budget = phase.SessionEvidenceBudget()
    first = world.invoke(budget=budget).to_dict()
    used = budget.used
    assert first["status"] == "complete" and used > first["cli_output_bytes"]
    world.candidate = "after"
    world.copy.apply_source(world.copy.read_source(), guard=lambda: None)
    second = world.invoke(budget=budget).to_dict()
    assert second["status"] == "complete" and used < budget.used <= phase.MAX_SESSION_EVIDENCE_BYTES


@pytest.mark.parametrize("bad_exit", [2, 5, 78, 137])
def test_test_infrastructure_failure_never_starts_application(world, bad_exit):
    world.t_exit = bad_exit
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["failure"] == "docker-command-failed"
    assert result["test_exit_code"] == bad_exit
    assert result["comparison"] is None and result["cleanup_confirmed"] is True
    assert set(world.plans) == {"T"} and world.containers == {}


def test_unknown_create_reply_reconciles_exact_name_before_removing_owned_id(world):
    def alter(pool, handle, role):
        if handle.label.startswith("create-T"):
            pool.records[handle.token] = replace(pool.records[handle.token], stdout=b"not-an-id\n")

    world.hook = alter
    result = world.invoke().to_dict()
    assert result["failure"] == "create-id-unconfirmed" and result["cleanup_confirmed"] is True
    assert world.containers == {} and len(result["owned"]) == 1
    assert result["owned"][0]["id"] is not None
    assert not any(argv[4] == "start" for argv, _, _, _ in world.calls)


def test_independent_wrong_profile_cannot_be_overridden_by_passing_generated_test(world):
    world.t_exit, world.relay_candidate = 0, "after"
    result = world.invoke().to_dict()
    assert result["failure"] == "independent-http-profile-mismatch"
    assert result["comparison"]["matches_expected_profile"] is False
    assert result["cleanup_confirmed"] is True and world.containers == {}


def test_startup_hint_without_a_live_application_never_reaches_relay(world):
    def exited(pool, handle, role):
        if role == "A" and handle.label.startswith("attach-start"):
            pool.records[handle.token] = replace(
                pool.records[handle.token], returncode=0, complete=True
            )

    world.hook = exited
    result = world.invoke().to_dict()
    assert result["failure"] == "application-exited-before-relay"
    assert "B" not in world.plans and result["cleanup_confirmed"] is True


def test_missing_startup_hint_fails_within_original_setup_allowance(world):
    world.a_hint = b"untrusted output, no complete hint line"
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["comparison"] is None
    assert "B" not in world.plans and result["setup_seconds"] <= 10
    assert result["cleanup_confirmed"] is True


def test_source_edit_in_guard_refuses_next_effect_but_still_cleans_owned_container(world):
    changed = False

    def guard():
        nonlocal changed
        if world.containers and not changed:
            changed = True
            (world.copy.path / "app.py").write_bytes(b"# user edit; never execute\n")

    world.guard_hook = guard
    result = world.invoke().to_dict()
    assert result["failure"] in {"WorkspaceError", "workspace-changed-during-phase"}
    assert result["cleanup_confirmed"] is True and world.containers == {}
    assert not any(argv[4] == "start" for argv, _, _, _ in world.calls)


def test_unknown_cleanup_identity_is_not_removed_and_first_failure_is_preserved(world):
    def altered(value, label):
        if label.startswith("cleanup-inspect"):
            value["Config"]["Labels"]["org.authzest.generated.nonce"] = "0" * 32

    world.inspect_hook, world.t_exit = altered, 2
    result = world.invoke().to_dict()
    assert result["failure"] == "docker-command-failed"
    assert result["cleanup_confirmed"] is False and result["cleanup_errors"]
    assert world.containers and not any(argv[4] == "rm" for argv, _, _, _ in world.calls)


def test_local_cleanup_uncertainty_prevents_complete_even_with_matching_http(world):
    world.local_cleanup = False
    result = world.invoke().to_dict()
    assert result["comparison"]["matches_expected_profile"] is True
    assert result["status"] == "failed" and result["cleanup_confirmed"] is False
    assert "local-process-cleanup-unconfirmed" in result["cleanup_errors"]


def test_output_limit_stops_before_new_role_and_retains_first_cause(world):
    def flood(pool, handle, role):
        if role == "T" and handle.label.startswith("attach-start"):
            pool.records[handle.token] = replace(
                pool.records[handle.token], stdout=b"x" * phase.MAX_OUTPUT_BYTES
            )
            pool.output_bytes = phase.MAX_OUTPUT_BYTES + 1

    world.hook = flood
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["comparison"] is None
    assert set(world.plans) == {"T"}
    assert result["cli_output_bytes"] > phase.MAX_OUTPUT_BYTES
    assert result["failure"] is not None


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt, SystemExit])
def test_dispatch_cancellation_propagates_with_result_and_exact_cleanup(world, cancellation):
    def cancel(argv, label):
        if label.startswith("attach-start-T"):
            raise cancellation("cancel-current-phase")

    world.command_hook = cancel
    with pytest.raises(cancellation) as caught:
        world.invoke()
    result = caught.value.generated_repair_phase_result.to_dict()
    assert result["status"] == "failed" and result["failure"] == cancellation.__name__
    assert result["cleanup_confirmed"] is True and world.containers == {}


@pytest.mark.parametrize("origin", ["remove", "local", "stage"])
def test_cleanup_cancellation_propagates_after_remaining_cleanup_attempts(world, origin):
    def cancel(*_):
        raise KeyboardInterrupt("cleanup-cancelled")

    if origin == "remove":

        def command(argv, label):
            if label.startswith("remove-B"):
                cancel()

        world.command_hook = command
    elif origin == "local":
        world.terminate_hook = cancel
    else:
        world.stage_close_hook = cancel
    with pytest.raises(KeyboardInterrupt) as caught:
        world.invoke()
    result = caught.value.generated_repair_phase_result.to_dict()
    assert result["status"] == "failed" and result["cleanup_confirmed"] is False
    assert all(stage.closed for stage in world.stages)
    assert "A" not in [item["plan"]["role"] for item in world.containers.values()]


def test_retained_evidence_exhaustion_never_dispatches_a_create(world):
    budget = phase.SessionEvidenceBudget()
    budget.charge(phase.MAX_SESSION_EVIDENCE_BYTES)
    with pytest.raises(phase.PhaseError, match="retained-session-evidence-limit"):
        world.invoke(budget=budget)
    assert world.calls == [] and world.pools == []
    assert budget.used == phase.MAX_SESSION_EVIDENCE_BYTES


def test_create_exception_after_possible_allocation_still_reconciles_owned_name(world):
    def uncertain(pool, handle, role):
        if handle.label.startswith("create-T"):
            raise OSError("reply-lost-after-create")

    world.hook = uncertain
    result = world.invoke().to_dict()
    assert result["failure"] == "OSError" and result["cleanup_confirmed"] is True
    assert result["owned"][0]["create_attempted"] is True and world.containers == {}
    assert not any(argv[4] == "start" for argv, _, _, _ in world.calls)


def test_existing_owned_name_is_never_adopted_or_removed(world):
    def collision(pool, handle, role):
        if handle.label.startswith("reconcile-T"):
            pool.records[handle.token] = replace(
                pool.records[handle.token], stdout=b"f" * 64 + b"\n"
            )

    world.hook = collision
    result = world.invoke().to_dict()
    assert result["failure"] == "owned-name-already-exists"
    assert result["owned"][0]["create_attempted"] is False
    assert not any(argv[4] in {"create", "start", "rm"} for argv, _, _, _ in world.calls)


@pytest.mark.parametrize("field", ["OOMKilled", "ExitCode"])
def test_daemon_exit_disagrees_with_test_process_and_blocks_next_role(world, field):
    def disagreement(value, label):
        if label.startswith("finished-inspect-T"):
            value["State"][field] = True if field == "OOMKilled" else 0

    world.inspect_hook = disagreement
    result = world.invoke().to_dict()
    assert result["failure"] == "container-exit-state-unconfirmed"
    assert set(world.plans) == {"T"} and result["cleanup_confirmed"] is True


@pytest.mark.parametrize("raw", [b"not-json", b"\xff", b"{}", b'{"status":"complete"}'])
def test_malformed_relay_cannot_create_comparison_or_verified_fix(world, raw):
    def malformed(pool, handle, role):
        if role == "B" and handle.label.startswith("attach-start"):
            pool.records[handle.token] = replace(pool.records[handle.token], stdout=raw)

    world.hook = malformed
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["comparison"] is None
    assert result["verified_fix"] is False and result["cleanup_confirmed"] is True


@pytest.mark.parametrize("answer", [True, "approved", 1])
def test_non_none_dispatch_guard_never_allocates_journal_or_process(world, answer):
    world.guard_hook = lambda: answer
    result = world.invoke().to_dict()
    assert result["failure"] == "dispatch-guard-must-synchronously-return-none"
    assert world.calls == [] and result["evidence_directory"] is None


def test_first_dispatch_cancellation_survives_different_cleanup_cancellation(world):
    first = KeyboardInterrupt("first-cancellation")

    def cancel(argv, label):
        if label.startswith("attach-start-T"):
            raise first

    def cleanup_cancel(_):
        raise SystemExit("later-cancellation")

    world.command_hook, world.terminate_hook = cancel, cleanup_cancel
    with pytest.raises(KeyboardInterrupt) as caught:
        world.invoke()
    assert caught.value is first
    result = first.generated_repair_phase_result.to_dict()
    assert result["failure"] == "KeyboardInterrupt" and result["cleanup_errors"]
    assert result["cleanup_confirmed"] is False and world.containers == {}


def test_slow_test_capture_keeps_original_phase_deadline_and_setup_allowance(world):
    def complete_later(pool, handle, deadline):
        if handle.label.startswith("attach-start-T"):
            assert deadline == 140.0
            world.time = 115.0

    world.wait_hook = complete_later
    result = world.invoke().to_dict()
    assert result["status"] == "complete" and result["setup_seconds"] == 0
    starts = [
        (label, deadline)
        for _, _, deadline, label in world.calls
        if label.startswith("attach-start")
    ]
    assert len(starts) == 3 and all(deadline == 140.0 for _, deadline in starts)
    assert 1 <= world.plans["B"]["remaining_ms"] <= 25_000


def test_delayed_start_is_observed_without_reissuing_start(world):
    calls = 0

    def delayed(value, label):
        nonlocal calls
        if label.startswith("start-inspect-T"):
            calls += 1
            if calls <= 2:
                value["State"].update(
                    Status="created", Running=False, StartedAt="0001-01-01T00:00:00Z"
                )

    world.inspect_hook = delayed
    world.pump_hook = lambda *_: setattr(world, "time", world.time + 0.01)
    result = world.invoke().to_dict()
    assert result["status"] == "complete" and calls == 3
    assert len([label for _, _, _, label in world.calls if label.startswith("attach-start-T")]) == 1
    assert 0 < result["setup_seconds"] < 10


def test_never_started_container_exhausts_fixed_inspection_count_without_start_retry(world):
    calls = 0

    def delayed(value, label):
        nonlocal calls
        if label.startswith("start-inspect-T"):
            calls += 1
            value["State"].update(Status="created", Running=False, StartedAt="0001-01-01T00:00:00Z")

    world.inspect_hook = delayed
    world.pump_hook = lambda *_: setattr(world, "time", world.time + 0.01)
    result = world.invoke().to_dict()
    assert result["failure"] == "container-start-state-unconfirmed" and calls == 8
    assert len([label for _, _, _, label in world.calls if label.startswith("attach-start-T")]) == 1
    assert set(world.plans) == {"T"} and result["cleanup_confirmed"] is True


def test_partial_journal_initialization_retains_directory_and_closes_owned_fd(world, monkeypatch):
    created = {}

    def fail_sync(journal):
        created.update(path=journal.path, fd=journal.fd)
        raise OSError("journal-directory-sync-failed")

    monkeypatch.setattr(phase._Journal, "_sync_directory", fail_sync)
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["failure"] == "OSError"
    assert result["evidence_directory"] == str(created["path"])
    assert created["path"].is_dir() and world.calls == []
    with pytest.raises(OSError):
        os.fstat(created["fd"])


@pytest.mark.parametrize(
    "diagnostic", [{"cleanup_failure": True}, {"socket_cleanup": "unconfirmed"}]
)
def test_failed_metadata_retains_diagnostic_wire_charge_and_socket_cleanup_uncertainty(
    world, monkeypatch, diagnostic
):
    observation = {
        "status": "failed",
        "failure_reason": "query-failed",
        "wire_bytes": 100,
        "wire_bytes_used": 321,
        "engine_contact_attempted": True,
        "transport_diagnostic": diagnostic,
        "metadata": {},
    }

    def fail_metadata(_, *, before_query, **__):
        before_query()
        return SimpleNamespace(to_dict=lambda: observation)

    monkeypatch.setattr(phase, "observe_runtime_metadata", fail_metadata)
    budget = phase.SessionEvidenceBudget()
    result = world.invoke(budget=budget).to_dict()
    assert result["failure"] == "runtime-metadata-mismatch" and result["status"] == "failed"
    assert result["runtime_metadata"] == observation
    assert result["engine_transport_cleanup_confirmed"] is False
    assert result["cleanup_confirmed"] is False and world.calls == []
    assert result["generated_runtime_attempted"] is False
    directory = Path(result["evidence_directory"])
    journal = (directory / "events.jsonl").read_bytes()
    rows = [json.loads(line) for line in journal.splitlines()]
    assert [row["observation"] for row in rows if row["event"] == "metadata-observed"] == [
        observation
    ]
    assert budget.used == phase.MAX_PHASE_RESULT_BYTES + len(journal) + 321
    assert json.loads((directory / "result.json").read_bytes())["runtime_metadata"] == observation


def test_insufficient_result_reservation_refuses_before_any_phase_allocation(world):
    budget = phase.SessionEvidenceBudget()
    budget.charge(phase.MAX_SESSION_EVIDENCE_BYTES - 100)
    with pytest.raises(phase.PhaseError, match="retained-session-evidence-limit"):
        world.invoke(budget=budget)
    assert budget.used == phase.MAX_SESSION_EVIDENCE_BYTES - 100
    assert world.calls == world.pools == world.stages == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", ["LD_PRELOAD=/input/foreign.so"]),
        ("volumes", {"/unexpected": {}}),
        ("user", "0"),
    ],
)
def test_unreviewed_image_environment_or_auto_volume_refuses_before_create(
    world, monkeypatch, field, value
):
    observe = phase.observe_runtime_metadata

    def changed(*args, **kwargs):
        data = observe(*args, **kwargs).to_dict()
        data["metadata"]["images"]["T"]["config"][field] = value
        return SimpleNamespace(to_dict=lambda: data)

    monkeypatch.setattr(phase, "observe_runtime_metadata", changed)
    result = world.invoke().to_dict()
    assert result["failure"] == "reviewed-image-config-mismatch"
    assert not world.calls and not world.stages
    assert result["generated_runtime_attempted"] is False
