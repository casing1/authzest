"""Current owned files through fake Engine metadata; no target or guest runs."""

import os
import stat
import subprocess
from contextlib import suppress
from hashlib import sha256

import pytest
from tests.helpers.repository_http_container_data import example
from tests.helpers.repository_http_engine_data import (
    PIN,
    MemorySocket,
    metadata_context,
)
from tests.helpers.repository_http_engine_data import (
    response as http_response,
)
from tests.helpers.repository_http_file_data import make_http_file_session, perform

from authzest.codex.contracts import canonical
from authzest.runner import _generated_repair_engine_http as wire
from authzest.runner import _repository_http_client_pin as client
from authzest.runner import _repository_http_engine_http as engine
from authzest.runner import _repository_http_preflight as metadata
from authzest.runner._repository_http_container_inspect import validate_stopped_container
from authzest.runner._repository_http_runtime_input import prepare_repository_http_runtime_input
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpCreatePlan,
    build_container_create_plan,
)
from authzest.runner._repository_http_staging import RepositoryHttpInputStage
from authzest.runner.repository_http_verification import (
    build_repository_http_verification_plan,
    prepare_repository_http_observer_schedule,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX current HTTP runtime inputs")


def _supplied_stopped(plan, container_id, environment):
    data = plan.to_dict()
    _, value = example(data["role"])
    image = data["profile"]["images"][data["role"]]["image_id"]
    command = data["argv"][data["argv"].index(image) + 1 :]
    value.update(Id=container_id, Name="/" + data["owned_name"], Args=command)
    value["Config"].update(Cmd=command, Env=environment)
    value["HostConfig"]["NetworkMode"] = (
        "none" if data["role"] == "A" else "container:" + data["application_container_id"]
    )
    value["HostConfig"]["Mounts"] = [
        {
            "Type": "bind",
            "Source": entry["source"],
            "Target": entry["target"],
            "ReadOnly": True,
            "BindOptions": {"Propagation": "rprivate"},
        }
        for entry in data["declared_files"]
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
        for entry in data["declared_files"]
    ]
    return canonical(value)


@pytest.fixture
def connection(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Runtime preparation must not execute a target/client or real socket")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "execve", forbidden)
    checked, frames = metadata_context()
    private = tmp_path.resolve() / "runtime"
    private.mkdir(mode=0o700)
    binary = private / "docker"
    binary.write_bytes(b"owned inert client, never run\n")
    binary.chmod(0o500)
    config = private / "config"
    config.mkdir(mode=0o700)
    (config / "config.json").write_bytes(b"{}\n")
    (config / "config.json").chmod(0o600)
    data = checked.to_dict()
    data["engine"].update(
        executable=str(binary),
        executable_sha256=sha256(binary.read_bytes()).hexdigest(),
        config_dir=str(config),
    )
    profile_path = private / "profile.json"
    profile_path.write_text(canonical(data), encoding="utf-8")
    profile_path.chmod(0o600)
    loaded = prepare_repository_http_runtime_input(profile_path)
    monkeypatch.setattr(client, "_endpoint_identity", lambda _path: PIN.copy())
    monkeypatch.setattr(engine, "_endpoint_identity", lambda _path: PIN.copy())
    monkeypatch.setattr(wire.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(metadata, "monotonic", lambda: 10.0)
    sockets = [MemorySocket(http_response(frame.body)) for frame in frames]
    opened = []

    def acquire(*_args):
        value = sockets[len(opened)]
        opened.append(value)
        return value

    monkeypatch.setattr(engine.socket, "socket", acquire)
    monkeypatch.setattr(engine.socket, "create_connection", forbidden)
    sessions, stages = [], []

    def prepare(phase):
        values = make_http_file_session(tmp_path, prefix=phase)
        session, origin, _, request, response, cases, _ = values
        sessions.append(session)
        perform(session, "copy")
        if phase == "after":
            perform(session, "accept-diff")
            perform(session, "apply")
        plan = build_repository_http_verification_plan(request, response, cases)
        stage = RepositoryHttpInputStage(session, request, response, cases, plan, phase)
        stages.append(stage)
        pin = client.RepositoryHttpClientPin(loaded.profile, lambda: None)

        def guard():
            loaded.assert_current()
            pin.check()
            stage.assert_current()

        return session, origin, request, response, cases, plan, stage, guard

    yield prepare, loaded, profile_path, opened
    for stage in stages:
        with suppress(Exception):
            stage.close()
    for session in sessions:
        with suppress(Exception):
            session.close()
    with suppress(Exception):
        loaded.close()
    # Production close retains sealed evidence. Only test-owned directories are
    # made removable here, after assertions and after releasing descriptors.
    for path in tmp_path.rglob("*"):
        with suppress(OSError):
            if stat.S_ISDIR(path.lstat().st_mode):
                path.chmod(0o700)


@pytest.mark.parametrize("phase", ["before", "after"])
def test_current_private_source_to_metadata_and_stopped_AB_plans(connection, phase):
    prepare, loaded, _, opened = connection
    session, origin, request, response, cases, plan, stage, guard = prepare(phase)
    original = (origin.snapshot.root / "app.py").read_bytes()
    observed = metadata.observe_runtime_metadata(
        loaded.profile, phase_deadline=50.0, setup_deadline=20.0, before_query=guard
    ).to_dict()
    assert observed["status"] == "metadata-match" and observed["query_attempted"] == 4
    assert len(opened) == 4 and all(sock.closed == 1 for sock in opened)
    staged = stage.prepare_create(loaded.profile, "8" * 32, "9" * 32).to_dict()
    a = RepositoryHttpCreatePlan(canonical(staged["container_create_plan"]))
    schedule = prepare_repository_http_observer_schedule(
        plan, request, response, cases, phase=phase
    )
    b = build_container_create_plan(
        loaded.profile,
        "B",
        session_nonce="8" * 32,
        role_nonce="9" * 32,
        application_container_id="a" * 64,
        remaining_ms=1200,
        schedule=schedule,
    )
    for value, cid in ((a, "a" * 64), (b, "b" * 64)):
        role = value.to_dict()["role"]
        environment = observed["metadata"]["images"][role]["config"]["environment"]
        stopped = validate_stopped_container(
            value,
            _supplied_stopped(value, cid, environment),
            container_id=cid,
            image_environment=environment,
        ).to_dict()
        assert stopped["profile_id"] == observed["profile_id"]
        assert stopped["ready"] is stopped["execution_authorized"] is False
        assert stopped["authorization_status"] == "unknown"
    source = (stage.input_path / "project/app.py").read_bytes()
    assert sha256(source).hexdigest() == plan.to_dict()["source"][phase + "_sha256"]
    assert (origin.snapshot.root / "app.py").read_bytes() == original
    if phase == "after":
        stage.close()
        perform(session, "restore")
        assert session.result()["verified_fix"] is False


@pytest.mark.parametrize("drift", ["profile", "stage"])
def test_current_guard_refuses_file_drift_before_any_fake_connection(connection, drift):
    prepare, loaded, profile_path, opened = connection
    *_, stage, guard = prepare("before")
    profile = loaded.profile
    if drift == "profile":
        profile_path.write_bytes(profile_path.read_bytes() + b" ")
    else:
        (stage.input_path / "project/app.py").chmod(0o644)
    result = metadata.observe_runtime_metadata(
        profile, phase_deadline=50.0, setup_deadline=20.0, before_query=guard
    ).to_dict()
    assert result["status"] == "failed"
    assert result["engine_contact_attempted"] is False
    assert result["response_count"] == 0 and opened == []
    assert result["verified_fix"] is result["ready"] is False
