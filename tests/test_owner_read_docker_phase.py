"""Fixed dispatcher regressions with supplied fake Docker/process observations only."""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from authzest.codex.owner_read_suggestion import build_owner_read_request
from authzest.owner_read_demo.checks import owner_read_controls
from authzest.runner import _owner_read_docker_phase as module

IMAGE = "sha256:" + "c" * 64
SOURCE = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_archived(owner_client):\n"
    '    assert owner_client.get("/records/archived-note").status_code == 200\n'
)


def capture(phase="before"):
    source = (
        build_owner_read_request("offline-runtime").to_dict()["source"]["text"]
        if phase == "before"
        else SOURCE
    )
    return {
        "phase": phase,
        "plan_id": "owner-plan-" + phase,
        "source": source.encode(),
        "test": TEST.encode(),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "test_sha256": hashlib.sha256(TEST.encode()).hexdigest(),
    }


class FakeRuntime:
    docker = "/reviewed/docker"
    image_id = IMAGE
    platform = "linux/arm64"

    def __init__(self):
        self.failed = False

    def check(self):
        if self.failed:
            raise ValueError("Runtime changed")

    def environment(self, config_dir):
        assert (Path(config_dir) / "config.json").read_bytes() == b"{}\n"
        assert (Path(config_dir).stat().st_mode & 0o777) == 0o700
        return {"DOCKER_CONFIG": str(config_dir), "DOCKER_HOST": "unix:///reviewed.sock"}

    def to_dict(self):
        return {"image_id": IMAGE, "platform": self.platform}


class FakePool:
    def __init__(self, *, clock, max_output_bytes, phase_deadline, cleanup_reserve_bytes):
        self.clock = clock
        self.limit = max_output_bytes
        self.reserve = cleanup_reserve_bytes
        self.deadline = phase_deadline
        self.cleaning = False
        self.calls = []
        self.values = []
        self.containers = {}
        self.created = 0
        self.behavior = {}
        self.current_capture = None
        self.ended = False

    def start(self, argv, env, deadline, label, *, cwd, **options):
        assert argv[0] == "/reviewed/docker" and cwd.startswith("/")
        assert set(env) == {"DOCKER_CONFIG", "DOCKER_HOST"}
        assert deadline <= (self.cleanup_deadline if self.cleaning else self.deadline)
        call = {"argv": argv[1:], "env": env, "label": label, "options": options}
        self.calls.append(call)
        return len(self.calls) - 1

    def wait(self, handle, deadline):
        call = self.calls[handle]
        args = call["argv"]
        if self.behavior.get("fail") and self.behavior["fail"](self, args):
            raise OSError("Fake command failure")
        stdout, stderr, code = b"", b"", 0
        if args[0] == "info":
            stdout = json.dumps(
                {
                    "ID": "daemon",
                    "OSType": "linux",
                    "CgroupVersion": "2",
                    "Architecture": "aarch64",
                    "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns"],
                    "MemoryLimit": True,
                    "SwapLimit": True,
                    "PidsLimit": True,
                    "CpuCfsPeriod": True,
                    "CpuCfsQuota": True,
                }
            ).encode()
        elif args[:2] == ["image", "inspect"]:
            stdout = json.dumps([{"Id": IMAGE, "Config": {"Labels": {"reviewed": "yes"}}}]).encode()
        elif args[:2] == ["container", "create"]:
            self.created += 1
            identifier = str(self.created) * 64
            name = args[args.index("--name") + 1]
            labels = dict(
                args[i + 1].split("=", 1) for i, item in enumerate(args) if item == "--label"
            )
            self.containers[identifier] = {
                "Id": identifier,
                "Name": "/" + name,
                "Image": IMAGE,
                "Config": {"Image": IMAGE, "Labels": labels, "StdinOnce": True},
                "State": {"Status": "created"},
            }
            stdout = (identifier + "\n").encode()
            if self.behavior.get("bad_create_output"):
                raise OSError("Created but output unavailable")
        elif args[:2] == ["container", "inspect"]:
            info = copy.deepcopy(self.containers[args[-1]])
            if self.behavior.get("wrong_owner") and self.cleaning:
                info["Config"]["Labels"] = {"other": "container"}
            stdout = json.dumps([info]).encode()
        elif args[:2] == ["container", "start"]:
            manifest = json.loads(call["options"]["input_bytes"])
            assert set(manifest) == {"source_sha256", "test_sha256"}
            info = self.containers[args[-1]]
            role = info["Config"]["Labels"][module._LABEL + "role"]
            before = self.current_capture["phase"] == "before"
            rows = owner_read_controls()
            record = {
                "kind": "owner-read-guest-observation",
                "schema_version": "1.0",
                "role": role,
                **manifest,
            }
            if role == "test":
                record["regression"] = {
                    "status": "assertion-failed" if before else "passed",
                    "pytest_exit": int(before),
                    "collected": 1,
                    "setup": "passed",
                    "call": "failed" if before else "passed",
                    "teardown": "passed",
                    "requests": 1,
                    "response": rows[1]["before" if before else "intended"],
                }
            else:
                record["observations"] = [
                    {"case_id": row["case_id"], **row["before" if before else "intended"]}
                    for row in rows
                ]
            stdout = json.dumps(record).encode()
            if self.behavior.get("malformed_guest"):
                stdout = b"{"
            info["RestartCount"] = 0
            info["State"] = {
                "Status": "exited",
                "ExitCode": code,
                "OOMKilled": False,
                "Running": False,
                "Paused": False,
                "Restarting": False,
                "Error": "",
                "Dead": False,
                "Pid": 0,
            }
        elif args[:2] == ["container", "ls"]:
            filt = args[args.index("--filter") + 1]
            if filt.startswith("name="):
                found = [
                    key
                    for key, info in self.containers.items()
                    if filt == "name=^" + info["Name"] + "$"
                ]
            else:
                found = [key for key in self.containers if filt == "id=" + key]
            stdout = "\n".join(found).encode()
        elif args[:2] == ["container", "rm"]:
            del self.containers[args[-1]]
        else:
            raise AssertionError(args)
        value = SimpleNamespace(
            label=call["label"],
            returncode=code,
            stdout=stdout,
            stderr=stderr,
            complete=True,
            errors=(),
            local_cleanup_confirmed=True,
        )
        self.values.append(value)
        if self.behavior.get("after_wait"):
            self.behavior["after_wait"](self, args)
        return value

    def begin_cleanup(self, deadline):
        self.cleaning = True
        self.cleanup_deadline = deadline

    def terminate_all(self, deadline):
        self.ended = True
        if self.behavior.get("bad_local_cleanup"):
            for value in self.values:
                value.local_cleanup_confirmed = False
        return self.values

    def snapshots(self):
        return self.values


@pytest.fixture
def setup(monkeypatch, tmp_path):
    pools = []
    checks = []
    original_mkdtemp = module.tempfile.mkdtemp
    monkeypatch.setattr(
        module.tempfile,
        "mkdtemp",
        lambda **kwargs: original_mkdtemp(prefix=kwargs["prefix"], dir=tmp_path),
    )
    monkeypatch.setattr(
        module, "validate_daemon", lambda info, runtime: checks.append(("daemon", info))
    )
    monkeypatch.setattr(
        module, "validate_image", lambda info, runtime: checks.append(("image", info))
    )
    monkeypatch.setattr(
        module,
        "validate_created_container",
        lambda info, runtime, **kwargs: checks.append(("container", kwargs)),
    )

    def factory(**kwargs):
        pool = FakePool(**kwargs)
        pools.append(pool)
        pool.behavior = behavior
        pool.current_capture = current[0]
        return pool

    behavior = {}
    current = [capture()]
    runtime = FakeRuntime()
    dispatcher = module.OwnerReadDockerDispatcher(runtime, clock=lambda: 10.0, pool_factory=factory)
    return dispatcher, pools, checks, behavior, current, runtime


def test_complete_before_after_are_separate_guests_with_exact_readonly_inputs(setup):
    dispatcher, pools, checks, _, current, _ = setup
    before = dispatcher(current[0], guard=lambda: None).to_dict()
    assert before["status"] == "matched" and before["cleanup_confirmed"] is True
    current[0] = capture("after")
    after = dispatcher(current[0], guard=lambda: None).to_dict()
    assert after["status"] == "matched" and after["comparison"]["intended_matches"] == 7
    assert len(pools) == 2
    for pool in pools:
        assert pool.ended and not pool.containers
        assert pool.created == 2 and pool.limit == 262144 and pool.reserve == 65536
        creates = [
            call["argv"] for call in pool.calls if call["argv"][:2] == ["container", "create"]
        ]
        assert len(creates) == 2
        for args in creates:
            assert "--network=none" in args and "--pull=never" in args and "--read-only" in args
            assert "--cap-drop=ALL" in args and "--user=65532:65532" in args
            mounts = [args[i + 1] for i, value in enumerate(args) if value == "--mount"]
            assert len(mounts) == 2 and all(
                value.endswith(",readonly,bind-propagation=rprivate") for value in mounts
            )
        assert all(
            call["options"].get("input_bytes") is None or len(call["options"]["input_bytes"]) <= 512
            for call in pool.calls
        )
    assert [row[0] for row in checks].count("container") == 4
    history = dispatcher.observations()
    assert len(history) == 2 and all(row["local_cleanup_confirmed"] for row in history)
    for row in history:
        root = Path(row["input_stage"]["path"])
        assert root.stat().st_mode & 0o777 == 0o700
        assert all((root / name).stat().st_mode & 0o777 == 0o444 for name in module._FILES)
        assert row["commands"] and all(c["cleanup_confirmed"] for c in row["commands"])
    history[0]["failure"] = "edited"
    assert dispatcher.observations()[0]["failure"] is None


def test_readonly_preflight_does_not_create_containers(setup):
    dispatcher, pools, checks, _, _, _ = setup
    value = dispatcher.preflight(guard=lambda: None)
    assert value["status"] == "ready" and value["cleanup_confirmed"] is True
    assert [call["argv"][0] for call in pools[0].calls] == ["info", "image"]
    assert pools[0].created == 0 and pools[0].ended
    assert [name for name, _ in checks] == ["daemon", "image"]
    with pytest.raises(module.OwnerReadDockerError, match="preflight-order"):
        dispatcher.preflight(guard=lambda: None)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "a" * 64),
        ("source", b"import os\n"),
        ("test", b"import sys\n"),
        ("phase", "later"),
    ],
)
def test_invalid_artifacts_are_refused_before_processes_or_allocation(setup, field, value):
    dispatcher, pools, _, _, current, _ = setup
    current[0][field] = value
    with pytest.raises((module.OwnerReadDockerError, ValueError)):
        dispatcher(current[0], guard=lambda: None)
    assert pools == [] and dispatcher.observations() == []


def test_phase_reuse_and_after_without_before_are_refused(setup):
    dispatcher, _, _, _, current, _ = setup
    with pytest.raises(module.OwnerReadDockerError, match="phase-order"):
        dispatcher(capture("after"), guard=lambda: None)
    dispatcher(current[0], guard=lambda: None)
    with pytest.raises(module.OwnerReadDockerError, match="phase-order"):
        dispatcher(current[0], guard=lambda: None)


def test_uncertain_create_is_found_by_exact_owned_name_and_removed(setup):
    dispatcher, pools, _, behavior, current, _ = setup
    behavior["bad_create_output"] = True
    with pytest.raises(OSError):
        dispatcher(current[0], guard=lambda: None)
    assert pools[0].created == 1 and not pools[0].containers and pools[0].ended
    assert dispatcher.observations()[0]["guests"]["test"]["cleanup_confirmed"] is True


def test_foreign_container_identity_is_preserved_during_cleanup(setup):
    dispatcher, pools, _, behavior, current, _ = setup
    behavior.update(bad_create_output=True, wrong_owner=True)
    with pytest.raises(OSError):
        dispatcher(current[0], guard=lambda: None)
    assert pools[0].containers
    assert not any(call["argv"][:2] == ["container", "rm"] for call in pools[0].calls)
    assert dispatcher.observations()[0]["guests"]["test"]["cleanup_confirmed"] is False


def test_bad_created_constraints_refuse_guest_start_but_remove_owned_container(setup, monkeypatch):
    dispatcher, pools, _, _, current, _ = setup

    def refuse(*args, **kwargs):
        raise ValueError("Unexpected mounts")

    monkeypatch.setattr(module, "validate_created_container", refuse)
    with pytest.raises(ValueError):
        dispatcher(current[0], guard=lambda: None)
    assert not any(call["argv"][:2] == ["container", "start"] for call in pools[0].calls)
    assert not pools[0].containers


def test_malformed_guest_output_fails_after_confirmed_cleanup(setup):
    dispatcher, pools, _, behavior, current, _ = setup
    behavior["malformed_guest"] = True
    result = dispatcher(current[0], guard=lambda: None).to_dict()
    assert result["status"] == "failed" and result["failure"] == "invalid-guest-json"
    assert result["cleanup_confirmed"] is True and not pools[0].containers


def test_local_process_cleanup_uncertainty_cannot_report_a_matched_phase(setup):
    dispatcher, _, _, behavior, current, _ = setup
    behavior["bad_local_cleanup"] = True
    result = dispatcher(current[0], guard=lambda: None).to_dict()
    assert result["status"] == "failed" and result["cleanup_confirmed"] is False


def test_runtime_change_is_refused_and_retained_without_foreign_cleanup(setup):
    dispatcher, pools, _, _, current, runtime = setup
    runtime.failed = True
    with pytest.raises(ValueError):
        dispatcher(current[0], guard=lambda: None)
    assert pools[0].calls == [] and pools[0].ended


def test_preflight_failure_preserves_observation_and_starts_no_guest(setup):
    dispatcher, pools, _, behavior, _, _ = setup
    behavior["fail"] = lambda pool, args: args[0] == "image"
    value = dispatcher.preflight(guard=lambda: None)
    assert value["status"] == "failed" and value["failure"] == "runtime-preflight-failed"
    assert pools[0].created == 0 and pools[0].ended


def test_failure_after_both_valid_guest_outputs_cannot_become_a_matched_phase(setup):
    dispatcher, pools, _, behavior, current, _ = setup
    now = [10.0]
    dispatcher._clock = lambda: now[0]

    def expire_after_controls(pool, args):
        if args[:2] == ["container", "start"] and len(pool.containers) == 2:
            now[0] = 51.0

    behavior["after_wait"] = expire_after_controls
    with pytest.raises(module.OwnerReadDockerError, match="phase-deadline-expired"):
        dispatcher(current[0], guard=lambda: None)
    assert not pools[0].containers and pools[0].ended
    record = dispatcher.observations()[0]
    assert record["failure"] == "phase-deadline-expired"
    assert all(plan["cleanup_confirmed"] for plan in record["guests"].values())
    assert "result_status" not in record


def test_cleanup_attempts_both_owned_roles_when_first_removal_fails(setup):
    dispatcher, pools, _, behavior, current, _ = setup
    behavior["fail"] = lambda pool, args: args[:2] == ["container", "rm"] and args[-1] == "1" * 64
    with pytest.raises(module.OwnerReadDockerError, match="container-cleanup-unconfirmed"):
        dispatcher(current[0], guard=lambda: None)
    assert set(pools[0].containers) == {"1" * 64}
    guests = dispatcher.observations()[0]["guests"]
    assert guests["test"]["cleanup_confirmed"] is False
    assert guests["controls"]["cleanup_confirmed"] is True
    assert pools[0].ended


def test_interruption_after_start_cleans_owned_container_and_preserves_cancel(setup):
    dispatcher, pools, _, behavior, current, _ = setup

    def interrupt(pool, args):
        if args[:2] == ["container", "start"]:
            raise KeyboardInterrupt

    behavior["after_wait"] = interrupt
    with pytest.raises(KeyboardInterrupt):
        dispatcher(current[0], guard=lambda: None)
    assert not pools[0].containers and pools[0].ended
    assert dispatcher.observations()[0]["guests"]["test"]["cleanup_confirmed"] is True


def test_staged_user_edit_is_detected_and_preserved_during_owned_cleanup(setup):
    dispatcher, pools, _, behavior, current, _ = setup
    edited = []

    def edit_stage(pool, args):
        if args[:2] == ["container", "start"] and not edited:
            path = Path(dispatcher.observations()[0]["input_stage"]["path"]) / "availability.py"
            path.chmod(0o600)
            path.write_bytes(b"user edit\n")
            edited.append(path)

    behavior["after_wait"] = edit_stage
    with pytest.raises(module.OwnerReadDockerError, match="input-file-changed"):
        dispatcher(current[0], guard=lambda: None)
    assert not pools[0].containers and pools[0].ended
    assert edited[0].read_bytes() == b"user edit\n"


@pytest.mark.parametrize("field", ["source", "test"])
def test_closed_grammar_is_checked_even_when_supplied_hash_matches_bytes(setup, field):
    dispatcher, pools, _, _, current, _ = setup
    current[0][field] = b"import os\n"
    current[0][field + "_sha256"] = hashlib.sha256(current[0][field]).hexdigest()
    with pytest.raises(ValueError):
        dispatcher(current[0], guard=lambda: None)
    assert pools == []


def test_preflight_interruption_still_reaps_local_processes(setup):
    dispatcher, pools, _, behavior, _, _ = setup

    def interrupt(pool, args):
        raise KeyboardInterrupt

    behavior["after_wait"] = interrupt
    with pytest.raises(KeyboardInterrupt):
        dispatcher.preflight(guard=lambda: None)
    assert pools[0].ended and not pools[0].containers
    assert dispatcher.observations()[0]["status"] == "failed"


def test_cancel_during_first_removal_still_attempts_second_cleanup_and_propagates(setup):
    dispatcher, pools, _, behavior, current, _ = setup

    def interrupt_remove(pool, args):
        if args[:2] == ["container", "rm"] and args[-1] == "1" * 64:
            raise KeyboardInterrupt
        return False

    behavior["fail"] = interrupt_remove
    with pytest.raises(KeyboardInterrupt):
        dispatcher(current[0], guard=lambda: None)
    assert set(pools[0].containers) == {"1" * 64}
    assert dispatcher.observations()[0]["guests"]["controls"]["cleanup_confirmed"] is True
    assert pools[0].ended


def test_private_roots_are_resolved_before_runtime_pins_and_mount_declarations(
    setup, monkeypatch, tmp_path
):
    dispatcher, pools, _, _, current, _ = setup
    real = tmp_path / "real-temp"
    real.mkdir()
    alias = tmp_path / "temp-alias"
    alias.symlink_to(real, target_is_directory=True)
    allocated = []

    def allocate(**kwargs):
        name = kwargs["prefix"] + str(len(allocated))
        (real / name).mkdir(mode=0o700)
        allocated.append(name)
        return str(alias / name)

    monkeypatch.setattr(module.tempfile, "mkdtemp", allocate)
    assert dispatcher(current[0], guard=lambda: None).to_dict()["status"] == "matched"
    assert str(alias) not in dispatcher.observations()[0]["input_stage"]["path"]
    assert dispatcher._config_dir == dispatcher._config_dir.resolve(strict=True)
    for call in pools[0].calls:
        assert str(alias) not in call["env"]["DOCKER_CONFIG"]
        assert all(str(alias) not in arg for arg in call["argv"] if arg.startswith("type=bind"))


@pytest.mark.parametrize("interruption", [OSError, KeyboardInterrupt])
def test_partial_input_stage_retains_path_and_unconfirmed_file_without_starting_guest(
    setup, monkeypatch, interruption
):
    dispatcher, pools, _, _, current, _ = setup
    write = module.os.write
    baseline = current[0]["source"]

    def partial_write(descriptor, data):
        if bytes(data) == baseline:
            write(descriptor, baseline[:1])
            raise interruption("Synthetic partial input write")
        return write(descriptor, data)

    monkeypatch.setattr(module.os, "write", partial_write)
    with pytest.raises(interruption):
        dispatcher(current[0], guard=lambda: None)
    record = dispatcher.observations()[0]
    staged = record["input_stage"]
    assert staged["status"] == "incomplete"
    assert staged["last_stage"] == "create-availability.py"
    assert staged["file_states"] == {
        "availability.py": "created-unconfirmed",
        "test_owner_archived_read.py": "not-created",
    }
    assert staged["files"] == {}
    assert (Path(staged["path"]) / "availability.py").read_bytes() == baseline[:1]
    assert not any(call["argv"][:2] == ["container", "create"] for call in pools[0].calls)
    assert pools[0].ended and not pools[0].containers
