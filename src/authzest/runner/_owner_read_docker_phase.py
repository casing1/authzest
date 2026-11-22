"""Fixed owner-read guests on an explicitly reviewed local Docker runtime.

The caller supplies the current file-session guard. Each phase captures fresh
private input files, observes two separately constrained guests and removes only
containers whose full identity still matches this dispatcher. The runtime image
and local daemon are operator-provisioned trust inputs.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import re
import secrets
import stat
import tempfile
from pathlib import Path
from time import monotonic

from authzest.codex.contracts import canonical, decode
from authzest.codex.owner_read_suggestion import _validate_rule, _validate_test
from authzest.runner._generated_repair_process import ProcessError, ProcessPool
from authzest.runner._owner_read_phase_result import validate_owner_read_phase
from authzest.runner._owner_read_runtime import (
    validate_created_container,
    validate_daemon,
    validate_image,
)

_SECONDS = 40
_CLEANUP_SECONDS = 10
_OUTPUT = 262_144
_RESERVE = 65_536
_FILES = ("availability.py", "test_owner_archived_read.py")
_ID = re.compile(r"[0-9a-f]{64}\Z")
_LABEL = "org.authzest.owner-read."


class OwnerReadDockerError(RuntimeError):
    """A fixed runtime operation could not establish the expected observation."""


def _check(condition, reason):
    if not condition:
        raise OwnerReadDockerError(reason)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_identity(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _guard(call):
    value = call()
    if inspect.iscoroutine(value):
        value.close()
    _check(value is None, "non-synchronous-runtime-guard")


def _capture(value):
    _check(
        type(value) is dict
        and value.keys() == {"phase", "plan_id", "source", "test", "source_sha256", "test_sha256"},
        "invalid-current-phase-input",
    )
    _check(
        value["phase"] in ("before", "after") and type(value["phase"]) is str,
        "invalid-current-phase",
    )
    _check(
        type(value["plan_id"]) is str and re.fullmatch(r"[\x21-\x7e]{1,128}", value["plan_id"]),
        "invalid-current-plan",
    )
    for name in ("source", "test"):
        data = value[name]
        _check(
            type(data) is bytes and 0 < len(data) <= 4096 and data.isascii(),
            "invalid-artifact-bytes",
        )
        _check(_sha(data) == value[name + "_sha256"], "artifact-hash-mismatch")
    _validate_rule(value["source"].decode("ascii"))
    _validate_test(value["test"].decode("ascii"))
    return dict(value)


class _InputStage:
    """Retain just-created, sealed input files and recheck their actual bytes."""

    def __init__(self, capture, guard):
        self.path = None
        self._files = {}
        self._root = None
        self._states = {name: "not-created" for name in _FILES}
        self._stage = "allocation-guard"
        try:
            _guard(guard)
            self._stage = "allocate-directory"
            self.path = Path(tempfile.mkdtemp(prefix="authzest-owner-read-guest-", dir="/tmp"))
            self._stage = "resolve-directory"
            self.path = self.path.resolve(strict=True)
            os.chmod(self.path, 0o700)
            for name, key in zip(_FILES, ("source", "test"), strict=True):
                self._stage = "create-" + name
                self._states[name] = "creation-attempted"
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                fd = os.open(self.path / name, flags, 0o600)
                self._states[name] = "created-unconfirmed"
                try:
                    pending = memoryview(capture[key])
                    while pending:
                        count = os.write(fd, pending)
                        _check(count > 0, "incomplete-input-write")
                        pending = pending[count:]
                    os.fchmod(fd, 0o444)
                    os.fsync(fd)
                    self._files[name] = (capture[key], _file_identity(os.fstat(fd)))
                finally:
                    os.close(fd)
            self._stage = "sync-directory"
            directory = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
            try:
                os.fsync(directory)
                self._root = _file_identity(os.fstat(directory))
            finally:
                os.close(directory)
            self._stage = "verify-inputs"
            self.check()
            self._states = {name: "verified" for name in _FILES}
            self._stage = "complete"
        except BaseException as exc:
            if self.path is not None:
                exc.owner_read_input_stage = self.evidence()
            raise

    def check(self):
        info = os.stat(self.path, follow_symlinks=False)
        _check(
            stat.S_ISDIR(info.st_mode)
            and stat.S_IMODE(info.st_mode) == 0o700
            and info.st_uid == os.geteuid()
            and _file_identity(info) == self._root,
            "input-directory-changed",
        )
        directory = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
        try:
            _check(_file_identity(os.fstat(directory)) == self._root, "input-directory-changed")
            with os.scandir(directory) as entries:
                names = set()
                for item in entries:
                    _check(item.name in _FILES and item.name not in names, "unexpected-input-entry")
                    names.add(item.name)
            _check(names == set(_FILES), "missing-input-entry")
            for name, (data, identity) in self._files.items():
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                try:
                    current = os.fstat(fd)
                    _check(
                        stat.S_ISREG(current.st_mode)
                        and stat.S_IMODE(current.st_mode) == 0o444
                        and current.st_uid == os.geteuid()
                        and current.st_nlink == 1
                        and _file_identity(current) == identity,
                        "input-file-changed",
                    )
                    observed = bytearray()
                    while len(observed) <= len(data):
                        part = os.read(fd, len(data) + 1 - len(observed))
                        if not part:
                            break
                        observed.extend(part)
                    _check(
                        observed == data
                        and _file_identity(os.fstat(fd)) == identity
                        and _file_identity(os.stat(name, dir_fd=directory, follow_symlinks=False))
                        == identity,
                        "input-file-changed",
                    )
                finally:
                    os.close(fd)
            _check(_file_identity(os.fstat(directory)) == self._root, "input-directory-changed")
        finally:
            os.close(directory)

    def mounts(self):
        return {str(self.path / name): "/input/" + name for name in _FILES}

    def evidence(self):
        return {
            "path": str(self.path),
            "status": "prepared" if self._stage == "complete" else "incomplete",
            "last_stage": self._stage,
            "file_states": dict(self._states),
            "files": {
                name: {"sha256": _sha(data), "identity": list(identity)}
                for name, (data, identity) in self._files.items()
            },
        }


class OwnerReadDockerDispatcher:
    """One before and one after phase for a current trusted file-session caller."""

    def __init__(self, runtime, *, clock=monotonic, pool_factory=ProcessPool):
        self.runtime = runtime
        self._clock = clock
        self._pool_factory = pool_factory
        self._used = set()
        self._history = []
        self._before_matched = False
        self._busy = False
        self._config_dir = None
        self._preflight_used = False

    def _config(self):
        if self._config_dir is None:
            root = Path(tempfile.mkdtemp(prefix="authzest-owner-read-cli-", dir="/tmp")).resolve(
                strict=True
            )
            os.chmod(root, 0o700)
            config = root / "config"
            config.mkdir(mode=0o700)
            config.chmod(0o700)
            fd = os.open(
                config / "config.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                os.fchmod(fd, 0o600)
                _check(os.write(fd, b"{}\n") == 3, "private-config-write-failed")
                os.fsync(fd)
            finally:
                os.close(fd)
            self._config_dir = config
        return self._config_dir

    def observations(self):
        return json.loads(canonical(self._history))

    def preflight(self, *, guard):
        """Inspect the reviewed local daemon/image before any provider request."""
        _check(not self._busy and not self._preflight_used, "preflight-order-or-reuse")
        self._preflight_used = True
        self._busy = True
        deadline = self._clock() + 10
        record = {
            "kind": "owner-read-runtime-preflight",
            "status": "failed",
            "runtime": self.runtime.to_dict(),
            "failure": None,
            "commands": [],
            "cleanup_confirmed": False,
        }
        self._history.append(record)
        pool = self._pool_factory(
            clock=self._clock,
            max_output_bytes=_OUTPUT,
            phase_deadline=deadline,
            cleanup_reserve_bytes=_RESERVE,
        )
        snapshots = ()
        interrupted = None
        try:
            for index, args in enumerate(
                (["info", "--format", "{{json .}}"], ["image", "inspect", self.runtime.image_id])
            ):
                self.runtime.check()
                _guard(guard)
                _check(self._clock() < deadline, "preflight-deadline-expired")
                handle = pool.start(
                    [self.runtime.docker, *args],
                    self.runtime.environment(self._config()),
                    deadline,
                    f"owner-preflight-{index}",
                    cwd=str(self._config().parent),
                )
                value = pool.wait(handle, deadline)
                _check(
                    value.complete
                    and not value.errors
                    and value.returncode == 0
                    and not value.stderr,
                    "preflight-command-failed",
                )
                if index == 0:
                    validate_daemon(decode(value.stdout.decode("utf-8")), self.runtime)
                else:
                    image = json.loads(
                        value.stdout.decode("utf-8"),
                        object_pairs_hook=_pairs,
                        parse_constant=_invalid_constant,
                    )
                    _check(
                        type(image) is list and len(image) == 1 and type(image[0]) is dict,
                        "invalid-single-image-inspect",
                    )
                    validate_image(image[0], self.runtime)
                self.runtime.check()
                _guard(guard)
                _check(self._clock() < deadline, "preflight-deadline-expired")
            record["status"] = "ready"
        except BaseException as exc:
            record["failure"] = (
                str(exc) if isinstance(exc, OwnerReadDockerError) else "runtime-preflight-failed"
            )
            if not isinstance(exc, Exception):
                interrupted = exc
        finally:
            try:
                snapshots = pool.terminate_all(self._clock() + 2)
                record["cleanup_confirmed"] = all(
                    value.local_cleanup_confirmed for value in snapshots
                )
            except BaseException as exc:
                snapshots = pool.snapshots()
                record["failure"] = record["failure"] or "preflight-cleanup-unconfirmed"
                if not isinstance(exc, Exception) and interrupted is None:
                    interrupted = exc
            if not record["cleanup_confirmed"]:
                record["status"] = "failed"
            record["commands"] = [_command_evidence(value) for value in snapshots]
            self._busy = False
        if interrupted is not None:
            raise interrupted
        return json.loads(canonical(record))

    def __call__(self, capture, *, guard):
        capture = _capture(capture)
        phase = capture["phase"]
        _check(
            not self._busy
            and phase not in self._used
            and (phase == "before" or self._before_matched),
            "phase-order-or-reuse",
        )
        self._used.add(phase)
        self._busy = True
        try:
            return self._execute(capture, guard)
        finally:
            self._busy = False

    def _execute(self, capture, guard):
        phase = capture["phase"]
        started = self._clock()
        deadline = started + _SECONDS
        nonce = secrets.token_hex(16)
        record = {
            "phase": phase,
            "plan_id": capture["plan_id"],
            "runtime": self.runtime.to_dict(),
            "source_sha256": capture["source_sha256"],
            "test_sha256": capture["test_sha256"],
            "failure": None,
            "input_stage": None,
            "commands": [],
            "guests": {},
        }
        self._history.append(record)
        pool = self._pool_factory(
            clock=self._clock,
            max_output_bytes=_OUTPUT,
            phase_deadline=deadline,
            cleanup_reserve_bytes=_RESERVE,
        )
        stage = None
        cleanup = False
        command_index = 0
        interrupted = None
        failure = None
        output = {
            role: {
                "exit_code": 125,
                "stdout": b"",
                "stderr": b"owner-read-phase-failed",
                "cleanup_confirmed": False,
            }
            for role in ("test", "controls")
        }
        plans = {}

        def tick():
            self.runtime.check()
            if not cleanup:
                _guard(guard)
                if stage is not None:
                    stage.check()
            _check(
                self._clock() < (cleanup_deadline if cleanup else deadline),
                "phase-deadline-expired",
            )

        def command(args, *, data=None, allow_failure=False):
            nonlocal command_index
            tick()
            label = f"owner-{phase}-{command_index}"
            command_index += 1
            options = {"input_bytes": data} if data is not None else {}
            handle = pool.start(
                [self.runtime.docker, *args],
                self.runtime.environment(self._config()),
                cleanup_deadline if cleanup else deadline,
                label,
                cwd=str(stage.path) if stage is not None else "/tmp",
                **options,
            )
            value = pool.wait(handle, cleanup_deadline if cleanup else deadline)
            _check(value.complete and not value.errors, "incomplete-command-capture")
            if not allow_failure:
                _check(value.returncode == 0 and not value.stderr, "docker-command-failed")
            tick()
            return value

        def object_command(args):
            raw = command(args).stdout
            value = decode(raw.decode("utf-8"))
            return value

        def single(args):
            # The image/container inspect API emits one JSON object inside an array.
            raw = command(args).stdout
            try:
                value = json.loads(
                    raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_invalid_constant
                )
            except (UnicodeError, ValueError, RecursionError):
                raise OwnerReadDockerError("invalid-inspect-json") from None
            _check(
                type(value) is list and len(value) == 1 and type(value[0]) is dict,
                "invalid-single-inspect",
            )
            return value[0]

        def owned(info, plan):
            _check(
                info.get("Id") == plan["id"]
                and info.get("Name") == "/" + plan["name"]
                and info.get("Image") == self.runtime.image_id
                and type(info.get("Config")) is dict
                and info["Config"].get("Image") == self.runtime.image_id
                and info["Config"].get("Labels") == plan["labels"],
                "owned-container-unconfirmed",
            )

        try:
            tick()
            validate_daemon(object_command(["info", "--format", "{{json .}}"]), self.runtime)
            image = single(["image", "inspect", self.runtime.image_id])
            validate_image(image, self.runtime)
            image_labels = image["Config"].get("Labels") or {}
            stage = _InputStage(capture, tick)
            record["input_stage"] = stage.evidence()
            for role in ("test", "controls"):
                current_image = single(["image", "inspect", self.runtime.image_id])
                _check(canonical(image) == canonical(current_image), "image-metadata-changed")
                name = "authzest-owner-read-" + nonce + "-" + role
                labels = {
                    **image_labels,
                    _LABEL + "session": nonce,
                    _LABEL + "role": role,
                    _LABEL + "plan": capture["plan_id"],
                }
                plan = {
                    "id": None,
                    "name": name,
                    "labels": labels,
                    "cleanup_confirmed": False,
                    "create_attempted": True,
                }
                plans[role] = plan
                record["guests"][role] = plan
                args = [
                    "container",
                    "create",
                    "--pull=never",
                    "--platform=" + self.runtime.platform,
                    "--name",
                    name,
                    "--read-only",
                    "--network=none",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges=true",
                    "--user=65532:65532",
                    "--memory=512m",
                    "--memory-swap=512m",
                    "--cpus=1",
                    "--pids-limit=64",
                    "--shm-size=8m",
                    "--cgroupns=private",
                    "--ipc=private",
                    "--init=false",
                    "--no-healthcheck",
                    "--restart=no",
                    "--log-driver=none",
                    "--interactive",
                    "--attach=stdin",
                    "--attach=stdout",
                    "--attach=stderr",
                    "--tmpfs",
                    "/tmp:rw,nosuid,nodev,noexec,size=33554432,mode=0700,uid=65532,gid=65532",
                ]
                for key, value in labels.items():
                    args += ["--label", key + "=" + value]
                for source, destination in stage.mounts().items():
                    args += [
                        "--mount",
                        f"type=bind,src={source},dst={destination},readonly,bind-propagation=rprivate",
                    ]
                created = (
                    command([*args, self.runtime.image_id, role]).stdout.strip().decode("ascii")
                )
                _check(_ID.fullmatch(created), "invalid-created-container-id")
                plan["id"] = created
                info = single(["container", "inspect", created])
                owned(info, plan)
                validate_created_container(
                    info,
                    self.runtime,
                    container_id=created,
                    name=name,
                    labels=labels,
                    role=role,
                    mounts=stage.mounts(),
                    image_info=image,
                )
                manifest = canonical(
                    {key: capture[key] for key in ("source_sha256", "test_sha256")}
                ).encode("ascii")
                observed = command(
                    ["container", "start", "--attach", "--interactive", created],
                    data=manifest,
                    allow_failure=True,
                )
                after = single(["container", "inspect", created])
                owned(after, plan)
                state = after.get("State", {})
                _check(
                    state.get("Status") == "exited"
                    and type(state.get("ExitCode")) is int
                    and state.get("ExitCode") == observed.returncode
                    and state.get("OOMKilled") is False
                    and state.get("Running") is False
                    and state.get("Paused") is False
                    and state.get("Restarting") is False
                    and state.get("Dead") is False
                    and type(state.get("Pid")) is int
                    and state["Pid"] == 0
                    and state.get("Error") == ""
                    and type(after.get("RestartCount")) is int
                    and after["RestartCount"] == 0,
                    "guest-state-unconfirmed",
                )
                output[role].update(
                    exit_code=observed.returncode, stdout=observed.stdout, stderr=observed.stderr
                )
                tick()
        except BaseException as exc:
            failure = exc
            partial = getattr(exc, "owner_read_input_stage", None)
            if type(partial) is dict:
                record["input_stage"] = json.loads(canonical(partial))
            record["failure"] = (
                exc.reason
                if isinstance(exc, ProcessError)
                else (
                    str(exc) if isinstance(exc, OwnerReadDockerError) else "phase-operation-failed"
                )
            )
            if not isinstance(exc, Exception):
                interrupted = exc
        finally:
            cleanup = True
            cleanup_deadline = self._clock() + _CLEANUP_SECONDS
            try:
                pool.begin_cleanup(cleanup_deadline)
            except BaseException as exc:
                record["failure"] = record["failure"] or "cleanup-mode-unconfirmed"
                if not isinstance(exc, Exception) and interrupted is None:
                    interrupted = exc
            for plan in plans.values():
                try:
                    listing = command(
                        [
                            "container",
                            "ls",
                            "--all",
                            "--no-trunc",
                            "--filter",
                            "name=^/" + plan["name"] + "$",
                            "--format",
                            "{{.ID}}",
                        ]
                    )
                    found = listing.stdout.strip().decode("ascii")
                    if found:
                        _check(
                            _ID.fullmatch(found) and (plan["id"] is None or found == plan["id"]),
                            "cleanup-container-identity-mismatch",
                        )
                        plan["id"] = found
                        owned(single(["container", "inspect", found]), plan)
                        command(["container", "rm", "--force", found])
                        absent = command(
                            [
                                "container",
                                "ls",
                                "--all",
                                "--no-trunc",
                                "--filter",
                                "id=" + found,
                                "--format",
                                "{{.ID}}",
                            ]
                        )
                        _check(not absent.stdout.strip(), "container-removal-unconfirmed")
                    plan["cleanup_confirmed"] = True
                except BaseException as exc:
                    record["failure"] = record["failure"] or "container-cleanup-unconfirmed"
                    if not isinstance(exc, Exception) and interrupted is None:
                        interrupted = exc
            local_clean = False
            try:
                snapshots = pool.terminate_all(cleanup_deadline)
                local_clean = all(value.local_cleanup_confirmed for value in snapshots)
            except BaseException as exc:
                snapshots = pool.snapshots()
                record["failure"] = record["failure"] or "local-cleanup-unconfirmed"
                if not isinstance(exc, Exception) and interrupted is None:
                    interrupted = exc
            for role in output:
                output[role]["cleanup_confirmed"] = local_clean and (
                    role not in plans or plans[role]["cleanup_confirmed"]
                )
            record["local_cleanup_confirmed"] = local_clean
            record["commands"] = [_command_evidence(value) for value in snapshots]
        if interrupted is not None:
            raise interrupted
        if record["failure"] is not None:
            if failure is not None:
                raise failure
            raise OwnerReadDockerError(record["failure"])
        result = validate_owner_read_phase(
            phase=phase,
            plan_id=capture["plan_id"],
            source_sha256=capture["source_sha256"],
            test_sha256=capture["test_sha256"],
            captures=output,
        )
        self._before_matched = phase == "before" and result.to_dict()["status"] == "matched"
        record["result_status"] = result.to_dict()["status"]
        return result


def _command_evidence(value):
    return {
        "label": value.label,
        "exit_code": value.returncode,
        "complete": value.complete,
        "errors": list(value.errors),
        "cleanup_confirmed": value.local_cleanup_confirmed,
        "stdout_base64": base64.b64encode(value.stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(value.stderr).decode("ascii"),
    }


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError("duplicate-inspect-key")
        result[name] = value
    return result


def _invalid_constant(_):
    raise ValueError("non-finite-inspect-value")
