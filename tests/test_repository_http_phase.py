"""Direct HTTP A -> B phase with owned inert files and a fake Docker client.

No container, socket, target import or provider call occurs. The fake client
emulates the reviewed app's GET behavior and feeds it through the maintained B
capture codec, so the host comparison sees genuine capture framing.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import stat
import subprocess
from contextlib import suppress
from copy import deepcopy
from hashlib import sha256

import pytest
from tests.helpers.repository_http_container_data import example
from tests.helpers.repository_http_engine_data import frame, profile_data
from tests.helpers.repository_http_file_data import make_http_file_session, perform
from tests.helpers.repository_http_verification_data import AFTER, SOURCE

from authzest.codex.contracts import canonical
from authzest.runner import _repository_http_phase as module
from authzest.runner._generated_repair_phase import (
    _IMAGE_ENVIRONMENT,
    MAX_PHASE_RESULT_BYTES,
    SessionEvidenceBudget,
)
from authzest.runner._generated_repair_process import ProcessHandle, ProcessSnapshot
from authzest.runner._repository_http_preflight import normalize_runtime_metadata
from authzest.runner._repository_http_runtime_input import (
    prepare_repository_http_runtime_input,
)
from authzest.runner._repository_http_runtime_profile import validate_runtime_profile
from authzest.runner._repository_http_staging import supported
from authzest.runner._repository_http_transport import capture_repository_http_poc
from authzest.runner.repository_http_verification import build_repository_http_verification_plan

pytestmark = pytest.mark.skipif(not supported(), reason="POSIX source-only HTTP phase scope")
NONCE = "c" * 32
DIGESTS = {"A": "sha256:" + "5" * 64, "B": "sha256:" + "6" * 64}
BEFORE_BYTES, AFTER_BYTES = SOURCE.encode(), AFTER.encode()


@pytest.fixture(autouse=True)
def no_actual_process_or_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("HTTP phase tests must not start a process or open a socket")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def app_response(phase, path, headers):
    """The owned inert reviewed source behavior: before leaks, after denies."""
    user = headers.get("x-user")
    if path == "/health":
        return 200, {"ok": True}
    if user is None:
        return 401, {"detail": "Unauthorized"}
    if phase == "after" and user != "test-owner":
        return 403, {"detail": "Forbidden"}
    return 200, {"id": path.rsplit("/", 1)[1]}


class MemoryStream:
    def __init__(self, world):
        self.world, self.reply, self.closed = world, b"", False

    def settimeout(self, _value):
        return None

    def sendall(self, data):
        lines = data.decode("ascii").split("\r\n")
        path = lines[0].split(" ")[1]
        headers = {}
        for line in lines[1:]:
            if ": " in line:
                name, value = line.split(": ", 1)
                headers[name.lower()] = value
        status, value = self.world.respond(path, headers)
        body = canonical(value).encode()
        self.reply = (
            f"HTTP/1.1 {status} OK\r\ncontent-type: application/json\r\n"
            f"content-length: {len(body)}\r\n\r\n"
        ).encode() + body

    def recv(self, count):
        chunk, self.reply = self.reply[:count], self.reply[count:]
        return chunk

    def close(self):
        self.closed = True


def stopped_inspect(plan, container_id):
    role = plan["role"]
    _, value = example(role)
    image = plan["profile"]["images"][role]["image_id"]
    command = ["-I", "-B", plan["argv"][plan["argv"].index(image) + 3]]
    if role == "B":
        command.append(str(plan["remaining_ms"]))
    value.update(Id=container_id, Name="/" + plan["owned_name"], Image=image, Args=command)
    config = value["Config"]
    config.update(Image=image, Cmd=command, Env=list(_IMAGE_ENVIRONMENT))
    config["Labels"] = {
        "org.authzest.repository-http.session": plan["session_nonce"],
        "org.authzest.repository-http.role": role,
        "org.authzest.repository-http.nonce": plan["role_nonce"],
    }
    host = value["HostConfig"]
    host["NetworkMode"] = "container:" + plan["application_container_id"] if role == "B" else "none"
    host["Mounts"] = [
        {
            "Type": "bind",
            "Source": entry["source"],
            "Target": entry["target"],
            "ReadOnly": True,
            "BindOptions": {"Propagation": "rprivate"},
        }
        for entry in plan["declared_files"]
    ]
    value["Mounts"] = [
        {
            "Type": "bind",
            "Source": entry["source"],
            "Destination": entry["target"],
            "RW": False,
            "Propagation": "rprivate",
            "Mode": "",
        }
        for entry in plan["declared_files"]
    ]
    value["ImageManifestDescriptor"]["digest"] = DIGESTS[role]
    return value


class World:
    def __init__(self, phase):
        self.phase = phase
        self.app_phase = phase
        self.time = 1000.0
        self.containers, self.calls, self.inputs = {}, [], []
        self.guard_hook = lambda: None
        self.command_hook = lambda *_: None
        self.a_hint = b"AUTHZEST_REPOSITORY_HTTP_A_STARTED\n"
        self.capture_hook = None
        self.relay_override = None
        self.rm_fails = False

    def respond(self, path, headers):
        return app_response(self.app_phase, path, headers)

    def clock(self):
        self.time += 0.001
        return self.time

    def relay(self, schedule_bytes):
        if self.relay_override is not None:
            return self.relay_override
        schedule = json.loads(schedule_bytes)
        streams = iter(lambda: MemoryStream(self), None)
        capture = capture_repository_http_poc(
            schedule,
            stream_factory=lambda *_: next(streams),
            phase_deadline=self.time + 30,
            clock=self.clock,
        ).to_dict()
        if self.capture_hook is not None:
            capture = self.capture_hook(capture)
        code = 0 if capture["status"] == "complete" else 1
        return canonical(capture).encode(), code


class FakePool:
    def __init__(self, world, *, clock, max_output_bytes, cleanup_reserve_bytes, max_input_bytes):
        assert max_input_bytes == 16_384 and max_output_bytes == 262_144
        self.world, self.clock = world, clock
        self.records, self.output_bytes, self.first_failure = [], 0, None

    def _snapshot(self, label, code, stdout=b"", stderr=b""):
        return ProcessSnapshot(label, 1, code, stdout, stderr, code is not None, (), True)

    def start(self, argv, env, *, deadline, label, input_bytes=None):
        world = self.world
        world.calls.append((list(argv), label, input_bytes))
        world.command_hook(argv, label)
        assert env == {"DOCKER_API_VERSION": "1.47"} and deadline > 0
        args = argv[4:]
        action, stdout, code = args[0], b"", 0
        if action == "create":
            role = next(a.rsplit("=", 1)[1] for a in argv if ".repository-http.role=" in a)
            plan = world.plans[role]
            assert argv == plan["argv"]
            container_id = str(len(world.containers) + 1) * 64
            world.containers[container_id] = {"plan": plan, "status": "created", "exit": 0}
            stdout = (container_id + "\n").encode()
        elif action == "ls":
            selector = next(a[9:] for a in args if a.startswith("--filter="))
            matches = [
                key
                for key, item in world.containers.items()
                if selector in ("id=" + key, "name=^/" + item["plan"]["owned_name"] + "$")
            ]
            stdout = "".join(key + "\n" for key in matches).encode()
        elif action == "inspect":
            item = world.containers[args[1]]
            value = stopped_inspect(item["plan"], args[1])
            if item["status"] != "created":
                value["State"].update(
                    Status=item["status"],
                    Running=item["status"] == "running",
                    StartedAt="2026-11-25T01:00:00Z",
                    ExitCode=item["exit"],
                )
            stdout = canonical([value]).encode()
        elif action == "start":
            assert args[1] == "--attach"
            item = world.containers[args[-1]]
            role = item["plan"]["role"]
            if role == "A":
                assert len(args) == 3 and input_bytes is None
                item["status"] = "running"
                stdout, code = world.a_hint, None
                if world.a_hint is None:
                    stdout, code = b"", 1
                    item.update(status="exited", exit=1)
            else:
                assert args[2] == "--interactive" and len(args) == 4
                world.inputs.append(input_bytes)
                stdout, code = world.relay(input_bytes)
                item.update(status="exited", exit=code)
        elif action == "rm":
            assert args[1] == "--force"
            if world.rm_fails:
                code = 1
            else:
                world.containers.pop(args[2])
                for index, value in enumerate(self.records):
                    if value.returncode is None:
                        self.records[index] = self._snapshot(value.label, 137, value.stdout)
        else:
            raise AssertionError(argv)
        self.output_bytes += len(stdout)
        self.records.append(self._snapshot(label, code, stdout))
        return ProcessHandle(len(self.records) - 1, label)

    def snapshot(self, handle):
        return self.records[handle.token]

    def snapshots(self):
        return tuple(self.records)

    def wait(self, handle, deadline):
        return self.records[handle.token]

    def pump(self, deadline):
        return tuple(self.records)

    def begin_cleanup(self, deadline):
        return None

    def terminate_all(self, deadline):
        self.records = [
            value if value.returncode is not None else self._snapshot(value.label, -9, value.stdout)
            for value in self.records
        ]
        return tuple(self.records)


class FakePin:
    def __init__(self, profile, tick):
        self.tick = tick
        tick()

    def check(self):
        self.tick()


def metadata_frames(profile, *, descriptor_platform=False, media=None, swap=True):
    data = profile.to_dict()
    info = {
        "ID": "synthetic-http-engine",
        "ServerVersion": "29.0.0",
        "OSType": "linux",
        "Architecture": "aarch64",
        "CgroupVersion": "2",
        "CgroupDriver": "cgroupfs",
        "DefaultRuntime": "runc",
        "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns"],
        "MemoryLimit": True,
        "SwapLimit": swap,
        "CpuCfsPeriod": True,
        "CpuCfsQuota": True,
        "PidsLimit": True,
    }
    frames = [
        frame(
            "version",
            {
                "Version": "29.0.0",
                "ApiVersion": "1.51",
                "MinAPIVersion": "1.41",
                "Os": "linux",
                "Arch": "arm64",
            },
        ),
        frame("info", info),
    ]
    for role in "AB":
        descriptor = {
            "digest": DIGESTS[role],
            "mediaType": media or "application/vnd.oci.image.manifest.v1+json",
            "size": 1754,
        }
        if descriptor_platform:
            descriptor["platform"] = {"os": "linux", "architecture": "arm64", "variant": "v8"}
        frames.append(
            frame(
                "image-" + role,
                {
                    "Id": data["images"][role]["image_id"],
                    "Descriptor": descriptor,
                    "Os": "linux",
                    "Architecture": "arm64",
                    "Variant": "v8",
                    "Config": {
                        "Env": list(_IMAGE_ENVIRONMENT),
                        "Entrypoint": ["/usr/local/bin/python"],
                        "Cmd": None,
                        "User": "65532:65532",
                        "Volumes": None,
                    },
                },
            )
        )
    return frames


@pytest.fixture
def setup(tmp_path, monkeypatch):
    resources = []

    def create(phase="before", **metadata_options):
        values = make_http_file_session(tmp_path, prefix=phase + str(len(resources)))
        session, _, _, request, response, cases, _ = values
        perform(session, "copy")
        if phase == "after":
            perform(session, "accept-diff")
            perform(session, "apply")
        plan = build_repository_http_verification_plan(request, response, cases)
        folder = tmp_path / ("profile-" + str(len(resources)))
        folder.mkdir(mode=0o700)
        path = folder / "runtime.json"
        path.write_text(canonical(profile_data()) + "\n", encoding="utf-8")
        path.chmod(0o600)
        loaded = prepare_repository_http_runtime_input(path)
        resources.append((session, loaded))
        world = World(phase)
        world.plans = {}
        world.metadata = metadata_options
        profile = validate_runtime_profile(canonical(profile_data()))

        def observe(checked, *, phase_deadline, setup_deadline, before_query):
            assert checked.payload_json == profile.payload_json
            before_query()
            frames = metadata_frames(checked, **world.metadata)
            return normalize_runtime_metadata(checked, frames)

        original_create = module._Phase.create

        def record_plan(self, plan_object, stage):
            data = plan_object.to_dict()
            world.plans[data["role"]] = data
            return original_create(self, plan_object, stage)

        monkeypatch.setattr(module, "observe_runtime_metadata", observe)
        monkeypatch.setattr(module, "RepositoryHttpClientPin", FakePin)
        monkeypatch.setattr(module, "ProcessPool", lambda **kw: FakePool(world, **kw))
        monkeypatch.setattr(module._Phase, "create", record_plan)
        world.session, world.loaded = session, loaded

        def invoke(*, budget=None, guard=None):
            def default_guard():
                world.guard_hook()

            return module.execute_repository_http_phase(
                session,
                request,
                response,
                cases,
                plan,
                loaded,
                phase=phase,
                session_nonce=NONCE,
                dispatch_guard=guard or default_guard,
                evidence_budget=budget or SessionEvidenceBudget(),
            )

        world.invoke = invoke
        world.args = (session, request, response, cases, plan, loaded)
        return world

    yield create
    for session, loaded in resources:
        with suppress(Exception):
            loaded.close()
        with suppress(Exception):
            session.close()
    for path in tmp_path.rglob("*"):
        with suppress(OSError):
            if stat.S_ISDIR(path.lstat().st_mode):
                path.chmod(0o700)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _actions(world):
    return [(argv[4] if len(argv) > 4 else argv[0], label) for argv, label, _ in world.calls]


@pytest.mark.parametrize("phase", ["before", "after"])
def test_complete_phase_compares_every_case_and_removes_both_guests(setup, phase):
    world = setup(phase)
    result = world.invoke().to_dict()
    assert result["status"] == "complete" and result["failure"] is None
    assert result["criteria_met"] is True
    assert result["cleanup_confirmed"] is True and world.containers == {}
    comparison = result["comparison"]
    assert comparison["counts"]["match"] == comparison["planned_cases"] == 5
    assert comparison["frame_status"] == "valid-supplied"
    if phase == "before":
        assert comparison["supplied_before_differs_from_desired_after"] is True
    assert result["frame"]["cleanup"] == {"A": "confirmed", "B": "confirmed"}
    assert [item["role"] for item in result["owned"]] == ["A", "B"]
    assert all(item["absence_observed"] for item in result["owned"])
    assert result["verified_fix"] is False and result["source_applied"] is False
    expected_source = AFTER_BYTES if phase == "after" else BEFORE_BYTES
    assert result["source_sha256"] == sha256(expected_source).hexdigest()
    # B received exactly the request-only schedule bytes bound into its plan.
    schedule = json.loads(world.inputs[0])
    assert schedule["phase"] == phase and len(schedule["requests"]) == 5
    assert b"Forbidden" not in world.inputs[0] and b'"status"' not in world.inputs[0]
    for request in schedule["requests"]:
        assert set(request) == {"case_id", "method", "path", "headers"}
    stdin = world.plans["B"]["stdin"]
    assert stdin["sha256"] == sha256(world.inputs[0]).hexdigest()
    assert result["schedule_sha256"] == stdin["sha256"]
    # A had no network and only the sealed manifest/source mounts; B joined A only.
    assert "--network=none" in world.plans["A"]["argv"]
    assert world.plans["B"]["argv"].count("--network=container:" + "1" * 64) == 1
    assert len(world.plans["A"]["declared_files"]) == 2
    assert world.plans["B"]["declared_files"] == []
    evidence = result["evidence_directory"]
    events = [
        json.loads(line)["event"]
        for line in _read(os.path.join(evidence, "events.jsonl")).splitlines()
    ]
    assert events[0] == "phase-created" and "relay-capture-observed" in events
    assert json.loads(_read(os.path.join(evidence, "result.json"))) == result
    assert stat.S_IMODE(os.stat(evidence).st_mode) == 0o700


def test_before_without_reproduction_is_complete_but_not_met(setup):
    world = setup("before")
    world.app_phase = "after"  # The supplied before source already denies the PoC.
    result = world.invoke().to_dict()
    assert result["status"] == "complete" and result["criteria_met"] is False
    outcome = {row["case_id"]: row["outcome"] for row in result["comparison"]["outcomes"]}
    assert outcome["other"] == "mismatch"
    assert result["comparison"]["supplied_before_differs_from_desired_after"] is False


def test_after_regression_mismatch_is_not_met(setup):
    world = setup("after")
    world.app_phase = "before"
    result = world.invoke().to_dict()
    assert result["status"] == "complete" and result["criteria_met"] is False
    assert result["comparison"]["counts"]["mismatch"] == 1


def test_partial_capture_keeps_error_and_undispatched_suffix(setup):
    world = setup("after")

    def timeout_third(capture):
        records = capture["records"]
        records[2].update(dispatch_status="error", fact=None, error_code="deadline-expired")
        for record in records[3:]:
            record.update(
                dispatch_status="not-dispatched",
                fact=None,
                error_code=None,
                close_status="not-acquired",
            )
        capture.update(status="partial", failure="deadline-expired")
        return capture

    world.capture_hook = timeout_third
    result = world.invoke().to_dict()
    assert result["relay_exit_code"] == 1 and result["status"] == "complete"
    assert result["criteria_met"] is False
    outcomes = [row["outcome"] for row in result["comparison"]["outcomes"]]
    assert outcomes == ["match", "match", "error", "not-dispatched", "not-dispatched"]
    assert result["frame"]["observations"][2]["error_code"] == "timeout"


@pytest.mark.parametrize(
    "relay",
    [
        (b"not json", 0),
        (b'{"schema_version":"2.0"}', 0),
        (b"", 0),
    ],
)
def test_invalid_capture_is_a_failed_phase_without_comparison(setup, relay):
    world = setup("before")
    world.relay_override = relay
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["criteria_met"] is False
    assert result["comparison"] is None and result["frame"] is None
    assert result["relay_capture_failure"].startswith("relay-capture-")
    assert result["cleanup_confirmed"] is True and world.containers == {}


def test_capture_status_must_match_relay_exit(setup):
    world = setup("before")

    def partial_status(capture):
        capture["status"] = "partial"
        return capture

    world.capture_hook = partial_status
    original = world.relay

    def mismatched(schedule_bytes):
        raw, _ = original(schedule_bytes)
        return raw, 0

    world.relay = mismatched
    result = world.invoke().to_dict()
    assert result["failure"] == "relay-capture-identity" and result["comparison"] is None


def test_application_exit_before_ready_hint_never_starts_relay(setup):
    world = setup("before")
    world.a_hint = None
    result = world.invoke().to_dict()
    assert result["failure"] == "application-exited-before-relay"
    assert "B" not in world.plans and world.inputs == []
    assert result["cleanup_confirmed"] is True and world.containers == {}


def test_metadata_requirements_refuse_before_any_container(setup):
    world = setup("before", swap=False)
    result = world.invoke().to_dict()
    assert result["failure"] == "required-daemon-capabilities-unreported"
    assert [action for action, _ in _actions(world)] == []
    assert result["owned"] == [] and result["cleanup_confirmed"] is True


def test_index_descriptor_never_supplies_manifest_pin(setup):
    world = setup("before", media="application/vnd.oci.image.index.v1+json")
    result = world.invoke().to_dict()
    assert result["failure"] == "platform-manifest-pin-unreported"
    assert world.calls == []


def test_explicit_platform_descriptor_is_accepted(setup):
    world = setup("before", descriptor_platform=True)
    assert world.invoke().to_dict()["criteria_met"] is True


def test_private_source_edit_during_phase_stops_and_cleans_up(setup):
    world = setup("before")
    root = world.session.result()["private_root"]
    edited = []

    def edit(argv, label):
        if label.startswith("attach-start-A") and not edited:
            path = os.path.join(root, "project", "app.py")
            os.chmod(path, 0o600)
            with open(path, "ab") as handle:
                handle.write(b"# edited\n")
            edited.append(label)

    world.command_hook = edit
    result = world.invoke().to_dict()
    assert edited and result["status"] == "failed" and result["criteria_met"] is False
    assert result["comparison"] is None
    assert world.containers == {}
    assert world.session.state == "recovery-required"


def test_guard_failure_stops_before_create(setup):
    world = setup("before")

    def refuse():
        raise RuntimeError("decision-expired")

    world.guard_hook = refuse
    result = world.invoke().to_dict()
    assert result["failure"] == "RuntimeError" and world.calls == []


def test_non_none_guard_is_refused(setup):
    world = setup("before")
    result = world.invoke(guard=lambda: True).to_dict()
    assert result["failure"] == "dispatch-guard-must-synchronously-return-none"


def test_removal_failure_is_retained_and_never_met(setup):
    world = setup("after")
    world.rm_fails = True
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and result["criteria_met"] is False
    assert result["cleanup_confirmed"] is False and result["cleanup_errors"]
    assert result["frame"]["cleanup"] == {"A": "failed", "B": "failed"}
    assert all(item["absence_observed"] is False for item in result["owned"])
    assert result["comparison"]["supplied_criteria_met"] is False


def test_existing_owned_name_is_never_adopted(setup):
    world = setup("before")
    original = world.command_hook

    def preexisting(argv, label):
        original(argv, label)
        if label.startswith("reconcile-A") and not world.containers:
            plan = world.plans["A"]
            world.containers["f" * 64] = {"plan": plan, "status": "created", "exit": 0}

    world.command_hook = preexisting
    result = world.invoke().to_dict()
    assert result["failure"] == "owned-name-already-exists"
    assert not any(label.startswith("create-") for _, label, _ in world.calls)


@pytest.mark.parametrize(
    "change",
    [
        lambda a: a.update(phase="after"),
        lambda a: a.update(session_nonce="C" * 32),
        lambda a: a.update(dispatch_guard=None),
        lambda a: a.update(evidence_budget=object()),
        lambda a: a.update(profile_input=object()),
        lambda a: a.update(plan=object()),
    ],
)
def test_invalid_context_is_refused_before_any_effect(setup, change):
    world = setup("before")
    session, request, response, cases, plan, loaded = world.args
    arguments = {
        "phase": "before",
        "session_nonce": NONCE,
        "dispatch_guard": lambda: None,
        "evidence_budget": SessionEvidenceBudget(),
        "profile_input": loaded,
        "plan": plan,
    }
    change(arguments)
    with pytest.raises(module.RepositoryHttpPhaseError, match="invalid-private-http-phase-context"):
        module.execute_repository_http_phase(
            session,
            request,
            response,
            cases,
            arguments.pop("plan"),
            arguments.pop("profile_input"),
            **arguments,
        )
    assert world.calls == []


async def _async_guard():
    return None


def test_async_guard_and_wrong_state_are_refused(setup):
    world = setup("before")
    session, request, response, cases, plan, loaded = world.args
    common = dict(session_nonce=NONCE, evidence_budget=SessionEvidenceBudget())
    with pytest.raises(module.RepositoryHttpPhaseError):
        module.execute_repository_http_phase(
            session,
            request,
            response,
            cases,
            plan,
            loaded,
            phase="before",
            dispatch_guard=_async_guard,
            **common,
        )
    perform(session, "accept-diff")
    with pytest.raises(module.RepositoryHttpPhaseError):
        module.execute_repository_http_phase(
            session,
            request,
            response,
            cases,
            plan,
            loaded,
            phase="before",
            dispatch_guard=lambda: None,
            **common,
        )
    assert world.calls == []


def test_evidence_budget_is_precharged_and_shared(setup):
    world = setup("before")
    budget = SessionEvidenceBudget()
    world.invoke(budget=budget)
    assert budget.used > MAX_PHASE_RESULT_BYTES


def test_relay_result_captures_are_bounded_history(setup):
    world = setup("before")
    result = world.invoke().to_dict()
    relay = [item for item in result["captures"] if item["label"].startswith("attach-start-B")]
    assert len(relay) == 1
    raw = base64.b64decode(relay[0]["stdout_base64"]) if "stdout_base64" in relay[0] else None
    digest = relay[0].get("stdout_sha256") or sha256(raw).hexdigest()
    events = _read(os.path.join(result["evidence_directory"], "events.jsonl"))
    assert digest in events
    assert result["provenance"] == "historical-private-controller-result-not-importable-authority"


def _capture(phase="before"):
    schedule = {
        "schema_version": "2.0",
        "kind": "repository-http-observer-schedule",
        "plan_id": "repository-http-verification-plan-" + "b" * 64,
        "phase": phase,
        "requests": [
            {"case_id": name, "method": "GET", "path": "/items/one", "headers": {}}
            for name in ("one", "two", "three", "four")
        ],
    }
    world = World(phase)
    streams = iter(lambda: MemoryStream(world), None)
    capture = capture_repository_http_poc(
        schedule, stream_factory=lambda *_: next(streams), phase_deadline=1030, clock=world.clock
    ).to_dict()
    return schedule, capture


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(plan_id="repository-http-verification-plan-" + "e" * 64),
        lambda c: c.update(phase="after"),
        lambda c: c.update(schedule_id="repository-http-observer-schedule-" + "0" * 64),
        lambda c: c.update(planned_count=3),
        lambda c: c["records"].pop(),
        lambda c: c["records"][0].update(case_id="two"),
        lambda c: c["records"][0].update(extra=True),
        lambda c: c.update(extra=True),
        lambda c: c.update(verified_fix=True),
        lambda c: c["records"][1].update(dispatch_status="maybe"),
    ],
)
def test_capture_decoder_binds_exact_schedule(change):
    schedule, capture = _capture()
    module.decode_relay_capture(canonical(capture).encode(), schedule, exit_code=0)
    change(capture)
    with pytest.raises(module.RepositoryHttpPhaseError):
        module.decode_relay_capture(canonical(capture).encode(), schedule, exit_code=0)


def test_capture_decoder_rejects_duplicates_and_oversize():
    schedule, capture = _capture()
    raw = canonical(capture)
    duplicate = raw[:-1] + ',"status":"complete"}'
    with pytest.raises(module.RepositoryHttpPhaseError):
        module.decode_relay_capture(duplicate.encode(), schedule, exit_code=0)
    with pytest.raises(module.RepositoryHttpPhaseError):
        module.decode_relay_capture(b" " * 131_073, schedule, exit_code=0)
    with pytest.raises(module.RepositoryHttpPhaseError):
        module.decode_relay_capture(raw.encode(), schedule, exit_code=2)


def test_frame_projection_refuses_dispatch_after_abort():
    schedule, capture = _capture()
    capture["records"][0].update(dispatch_status="error", fact=None, error_code="receive-failed")
    plan = {
        "plan_id": schedule["plan_id"],
        "source": {"before_sha256": "1" * 64},
        "http_interface": {"interface_id": "i"},
        "case_set_id": "c",
        "poc_sha256": "p",
    }
    with pytest.raises(module.RepositoryHttpPhaseError, match="relay-capture-after-abort"):
        module.build_phase_frame(capture, plan, "before", {"A": "confirmed", "B": "confirmed"})
    for record in capture["records"][1:]:
        record.update(dispatch_status="not-dispatched", fact=None, close_status="not-acquired")
    frame_value = module.build_phase_frame(
        capture, plan, "before", {"A": "confirmed", "B": "confirmed"}
    )
    assert [row["outcome"] for row in frame_value["observations"]] == [
        "error",
        "not-dispatched",
        "not-dispatched",
        "not-dispatched",
    ]
    assert frame_value["observations"][0]["error_code"] == "transport-error"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("deadline-expired", "timeout"),
        ("body-invalid", "body-invalid"),
        ("http-truncated", "http-framing"),
        ("wire-budget", "http-framing"),
        ("receive-call-budget", "http-framing"),
        ("factory-failed", "transport-error"),
        ("clock-invalid", "transport-error"),
    ],
)
def test_error_projection_is_closed(code, expected):
    assert module._error_class(code) == expected


def test_manifest_pin_selection_never_uses_config_or_index():
    base = {
        "os": "linux",
        "architecture": "arm64",
        "variant": "v8",
        "platform_manifest_reported": False,
        "manifest_descriptor": {
            "digest": DIGESTS["A"],
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "size": 10,
            "platform": None,
        },
    }
    assert module._manifest_pin(deepcopy(base)) == DIGESTS["A"]
    for change in (
        lambda v: v.update(manifest_descriptor=None),
        lambda v: v["manifest_descriptor"].update(
            mediaType="application/vnd.oci.image.index.v1+json"
        ),
        lambda v: v.update(architecture="amd64"),
        lambda v: v["manifest_descriptor"].update(
            platform={"os": "linux", "architecture": "amd64"}
        ),
    ):
        value = deepcopy(base)
        change(value)
        with pytest.raises(module.RepositoryHttpPhaseError):
            module._manifest_pin(value)


def test_large_outputs_keep_digest_only(setup):
    assert module._bounded_output("stdout", b"x" * 10) == {
        "stdout_base64": base64.b64encode(b"x" * 10).decode()
    }
    large = module._bounded_output("stdout", b"y" * 16_385)
    assert large == {"stdout_sha256": sha256(b"y" * 16_385).hexdigest(), "stdout_bytes": 16_385}


def test_closed_profile_is_refused_before_precharge(setup):
    world = setup("before")
    world.loaded.close()
    budget = SessionEvidenceBudget()
    with pytest.raises(module.RepositoryHttpPhaseError, match="invalid-private-http-phase-context"):
        world.invoke(budget=budget)
    assert budget.used == 0 and world.calls == []


def test_capture_level_failure_is_never_criteria_met(setup):
    world = setup("after")

    def late_deadline(capture):
        capture.update(status="partial", failure="deadline-expired")
        return capture

    world.capture_hook = late_deadline
    result = world.invoke().to_dict()
    assert result["relay_exit_code"] == 1
    assert result["comparison"]["counts"]["match"] == 5
    assert result["relay_capture"]["failure"] == "deadline-expired"
    assert result["criteria_met"] is False


def test_stage_initialization_failure_is_retained(setup, monkeypatch):
    world = setup("before")
    from authzest.runner import _repository_http_staging as staging

    original = staging.RepositoryHttpInputStage._create_file

    def failing(self, name, content):
        if name.endswith("app.py"):
            raise OSError("synthetic staging write failure")
        return original(self, name, content)

    monkeypatch.setattr(staging.RepositoryHttpInputStage, "_create_file", failing)
    monkeypatch.setattr(
        staging.RepositoryHttpInputStage, "_close_descriptors", lambda self: OSError("close")
    )
    result = world.invoke().to_dict()
    failure = result["stage_initialization_failure"]
    assert result["status"] == "failed" and result["owned"] == []
    assert failure["created_path"] and failure["descriptor_cleanup_confirmed"] is False
    assert "stage-initialization-cleanup-unconfirmed" in result["cleanup_errors"]
    assert result["cleanup_confirmed"] is False


@pytest.mark.parametrize(
    "attribute", ["descriptor_cleanup_confirmed", "http_client_descriptor_cleanup_confirmed"]
)
def test_client_pin_cleanup_failure_is_retained(setup, monkeypatch, attribute):
    world = setup("before")

    def failing(profile, tick):
        error = RuntimeError("pin")
        setattr(error, attribute, False)
        raise error

    monkeypatch.setattr(module, "RepositoryHttpClientPin", failing)
    result = world.invoke().to_dict()
    assert result["status"] == "failed" and world.calls == []
    assert "client-pin-descriptor-cleanup-unconfirmed" in result["cleanup_errors"]
    assert result["cleanup_confirmed"] is False
