"""Private fixed Docker phase; the public generation/session remain inactive.

The trusted coordinator must review provisioned images and fresh capabilities,
bind the current workspace/profile/decision, and supply a synchronous guard.
Calling this private function is an effect, unlike importing a historical JSON
result. It never applies a source file or establishes imported apply authority.
"""

from __future__ import annotations

import base64
import inspect
import json
import math
import os
import re
import stat
import tempfile
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import monotonic

from authzest.codex.contracts import canonical
from authzest.runner._generated_repair_container_inspect import validate_stopped_container
from authzest.runner._generated_repair_engine_http import _endpoint_identity
from authzest.runner._generated_repair_preflight import observe_runtime_metadata
from authzest.runner._generated_repair_process import ProcessPool
from authzest.runner._generated_repair_relay import compare_generated_repair_relay_capture
from authzest.runner._generated_repair_runtime_profile import (
    ContainerCreatePlan,
    RuntimeProfile,
    build_container_create_plan,
    validate_runtime_profile,
)
from authzest.runner._generated_repair_staging import GeneratedRepairInputStage
from authzest.runner._generated_repair_workspace import GeneratedRepairWorkspace, supported
from authzest.runner.generated_repair_controls import build_generated_repair_controls

PHASE_SECONDS = 40.0
SETUP_SECONDS = 10.0
CLEANUP_SECONDS = 10.0
MAX_OUTPUT_BYTES = 262_144
MAX_SESSION_EVIDENCE_BYTES = 2_097_152
MAX_PHASE_RESULT_BYTES = 524_288
_READY = b"AUTHZEST_A_STARTED\n"
_IMAGE_ENVIRONMENT = (
    "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG=C.UTF-8",
    "GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305",
    "PYTHON_VERSION=3.12.16",
    "PYTHON_SHA256=b5796915dc45ff745cfb4e990a7e7c93d6f546328a102ce31448d69ebc37575c",
)
_ID = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32}\Z")


class PhaseError(RuntimeError):
    """A fixed phase failed; its retained record describes uncertain effects."""


@dataclass(frozen=True, slots=True)
class GeneratedRepairPhaseResult:
    """Detached history only; no importer, readiness or write capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return json.loads(self.payload_json)


class SessionEvidenceBudget:
    """One trusted coordinator's cumulative retained bytes, never a reset token.

    Reuse the same instance for before and after. The public session has not yet
    integrated this private helper. Counts include JSON/base64 expansion and the
    metadata reader's wire charge, rather than only decoded guest payload bytes.
    """

    def __init__(self):
        self._used = 0

    @property
    def used(self):
        return self._used

    def charge(self, size):
        if type(size) is not int or size < 0 or self._used + size > MAX_SESSION_EVIDENCE_BYTES:
            raise PhaseError("retained-session-evidence-limit")
        self._used += size


def _json(raw: bytes):
    if type(raw) is not bytes or len(raw) > MAX_OUTPUT_BYTES:
        raise PhaseError("invalid-command-json")

    def pairs(items):
        value = {}
        for key, child in items:
            if key in value:
                raise PhaseError("duplicate-command-json-field")
            value[key] = child
        return value

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(PhaseError("nonfinite-command-json")),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PhaseError("invalid-command-json") from exc


def _single(raw: bytes):
    value = _json(raw)
    if type(value) is not list or len(value) != 1 or type(value[0]) is not dict:
        raise PhaseError("invalid-single-container-inspect")
    return value[0]


def _owned(value, plan, container_id=None):
    config = value.get("Config")
    if (
        type(value.get("Id")) is not str
        or not _ID.fullmatch(value["Id"])
        or container_id is not None
        and value["Id"] != container_id
        or value.get("Name") != "/" + plan["owned_name"]
        or type(config) is not dict
        or type(config.get("Labels")) is not dict
        or config["Labels"].get("org.authzest.generated.session") != plan["session_nonce"]
        or config["Labels"].get("org.authzest.generated.role") != plan["role"]
        or config["Labels"].get("org.authzest.generated.nonce") != plan["role_nonce"]
        or value.get("Image") != plan["profile"]["images"][plan["role"]]["image_id"]
        or config.get("Image") != plan["profile"]["images"][plan["role"]]["image_id"]
    ):
        raise PhaseError("owned-container-identity-unconfirmed")
    return value["Id"]


def _file_identity(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _file_digest(path, *, maximum, tick, private=False):
    before = os.lstat(path)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid not in {0, os.geteuid()}
        or before.st_mode & 0o022
        or before.st_nlink != 1
        or not 0 < before.st_size <= maximum
        or private
        and (before.st_uid != os.geteuid() or before.st_mode & 0o077)
    ):
        raise PhaseError("unsupported-client-or-config-file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        if _file_identity(before) != _file_identity(opened):
            raise PhaseError("client-or-config-identity-changed")
        digest, total = sha256(), 0
        while True:
            tick()
            chunk = os.read(fd, min(262_144, maximum - total + 1))
            total += len(chunk)
            if total > maximum:
                raise PhaseError("client-or-config-size-limit")
            digest.update(chunk)
            if not chunk:
                break
        if (
            _file_identity(os.fstat(fd)) != _file_identity(opened)
            or _file_identity(os.lstat(path)) != _file_identity(opened)
            or total != opened.st_size
        ):
            raise PhaseError("client-or-config-identity-changed")
        return digest.hexdigest(), _file_identity(opened)
    finally:
        os.close(fd)


class _ClientPin:
    def __init__(self, profile, tick):
        self.engine = profile.to_dict()["engine"]
        self.tick = tick
        self.identity = None
        self.check(initial=True)

    def check(self, *, initial=False):
        self.tick()
        engine = self.engine
        for path in (engine["config_dir"], engine["executable"]):
            for parent in reversed(Path(path).parents):
                info = os.lstat(parent)
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_uid not in {0, os.geteuid()}
                    or info.st_mode & 0o022
                    and not info.st_mode & stat.S_ISVTX
                ):
                    raise PhaseError("unsupported-client-or-config-parent")
        folder = os.lstat(engine["config_dir"])
        if (
            not stat.S_ISDIR(folder.st_mode)
            or folder.st_uid != os.geteuid()
            or folder.st_mode & 0o077
            or os.listdir(engine["config_dir"]) != ["config.json"]
        ):
            raise PhaseError("private-empty-config-required")
        if not os.access(engine["executable"], os.X_OK):
            raise PhaseError("client-not-executable")
        client_digest, client_identity = _file_digest(
            engine["executable"], maximum=134_217_728, tick=self.tick
        )
        config_digest, config_identity = _file_digest(
            str(Path(engine["config_dir"]) / "config.json"),
            maximum=3,
            tick=self.tick,
            private=True,
        )
        if (
            client_digest != engine["executable_sha256"]
            or config_digest != engine["config_json_sha256"]
        ):
            raise PhaseError("client-or-empty-config-digest-mismatch")
        value = {
            "client": client_identity,
            "config": config_identity,
            "directory": _file_identity(folder),
            "endpoint": _endpoint_identity(engine["endpoint"][7:]),
        }
        if not initial and value != self.identity:
            raise PhaseError("client-config-or-endpoint-changed")
        self.identity = value
        self.tick()


class _Journal:
    def __init__(self, budget):
        self.budget = budget
        self.path = None
        self.fd = -1
        self.initialization_stage = "not-created"
        self.count = 0
        self.failed = False

    def initialize(self):
        self.initialization_stage = "create-directory"
        self.path = Path(tempfile.mkdtemp(prefix="authzest-generated-phase-"))
        self.initialization_stage = "open-journal"
        self.fd = os.open(
            self.path / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        self.initialization_stage = "sync-directory"
        self._sync_directory()
        self.initialization_stage = "complete"

    def _sync_directory(self):
        fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def event(self, event, **values):
        if self.initialization_stage != "complete" or self.failed or self.count >= 128:
            raise PhaseError("phase-journal-unavailable")
        raw = (canonical({"sequence": self.count, "event": event, **values}) + "\n").encode()
        self.budget.charge(len(raw))
        self.failed = True
        if os.write(self.fd, raw) != len(raw):
            raise PhaseError("phase-journal-short-write")
        os.fsync(self.fd)
        self.count += 1
        self.failed = False

    def result(self, payload):
        if self.initialization_stage != "complete":
            raise PhaseError("phase-journal-initialization-unconfirmed")
        raw = canonical(payload).encode()
        # The controller reserves this entire fixed allowance before effects.
        # Even a persistence/budget failure cannot export uncharged captures.
        if len(raw) > MAX_PHASE_RESULT_BYTES:
            raise PhaseError("phase-result-size-limit")
        fd = os.open(
            self.path / "result.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        try:
            if os.write(fd, raw) != len(raw):
                raise PhaseError("phase-result-short-write")
            os.fsync(fd)
        finally:
            os.close(fd)
        self._sync_directory()

    def close(self):
        fd, self.fd = self.fd, -1
        if fd >= 0:
            os.close(fd)


class _Phase:
    def __init__(self, workspace, candidate, profile, nonce, plan_id, guard, budget):
        self.clock = monotonic
        self.last = 0.0
        self.started = self.now()
        self.deadline = self.started + PHASE_SECONDS
        self.setup_used = 0.0
        self.cleanup_deadline = None
        self.workspace, self.candidate = workspace, candidate
        self.profile = validate_runtime_profile(profile.payload_json)
        self.nonce, self.plan_id, self.guard, self.budget = nonce, plan_id, guard, budget
        self.pool = ProcessPool(
            clock=self.now, max_output_bytes=MAX_OUTPUT_BYTES, cleanup_reserve_bytes=32_768
        )
        self.pin = None
        self.journal = None
        self.stages, self.owned, self.commands = [], [], []
        self.metadata = self.comparison = None
        self.test_exit = None
        self.failure = None
        self.cleanup_errors = []
        self.runtime_attempted = False
        self.checkpoint = None
        self.interruption = None

    def now(self):
        value = self.clock()
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not self.last <= value <= 2**48
        ):
            raise PhaseError("phase-clock-unconfirmed")
        self.last = float(value)
        return self.last

    def tick(self):
        deadline = self.cleanup_deadline if self.cleanup_deadline is not None else self.deadline
        if self.now() >= deadline:
            raise PhaseError("original-phase-or-cleanup-deadline-expired")

    def current(self, stage=None):
        self.tick()
        if self.cleanup_deadline is None:
            answer = self.guard()
            if inspect.iscoroutine(answer):
                answer.close()
            if answer is not None:
                raise PhaseError("dispatch-guard-must-synchronously-return-none")
            if (
                self.workspace.read_source(),
                self.workspace.read_test(),
                self.workspace.read_record(),
            ) != self.checkpoint:
                raise PhaseError("workspace-changed-during-phase")
            if stage is not None:
                stage.assert_current()
        if self.pin is not None:
            self.pin.check()
        self.tick()

    def setup(self, operation):
        before = self.now()
        limit = min(self.deadline, before + SETUP_SECONDS - self.setup_used)
        if limit <= before:
            raise PhaseError("cumulative-setup-readiness-limit")
        failure = None
        try:
            return operation(limit)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            self.setup_used += self.now() - before
            if self.setup_used > SETUP_SECONDS and failure is None:
                raise PhaseError("cumulative-setup-readiness-limit")

    def command(self, args, *, deadline=None, stage=None, label, create=False, record=True):
        self.current(stage)
        if deadline is not None and self.now() >= deadline:
            raise PhaseError("command-dispatch-deadline-expired")
        engine = self.profile.to_dict()["engine"]
        argv = [
            engine["executable"],
            "--config=" + engine["config_dir"],
            "--host=" + engine["endpoint"],
            "container",
            *args,
        ]
        if create:
            argv = args
        if record:
            self.journal.event("command-intent", label=label)
        self.tick()
        if deadline is not None and self.now() >= deadline:
            raise PhaseError("command-dispatch-deadline-expired")
        handle = self.pool.start(
            argv,
            {"DOCKER_API_VERSION": engine["api_version"]},
            deadline=(self.cleanup_deadline or self.deadline),
            label=label + "-" + str(len(self.commands)),
        )
        self.commands.append(handle)
        return handle

    def checked(self, handle, deadline, allowed=(0,)):
        snapshot = self.pool.wait(handle, deadline)
        if not snapshot.complete or snapshot.returncode not in allowed:
            raise PhaseError("docker-command-failed")
        return snapshot

    def inspect(self, target, *, limit, label, cleanup=False):
        handle = self.command(["inspect", target], deadline=limit, label=label, record=not cleanup)
        return self.checked(handle, limit).stdout

    def listing(self, item, *, limit, by_name=False, cleanup=False):
        selector = ("name=^/" + item["plan"]["owned_name"] + "$") if by_name else "id=" + item["id"]
        handle = self.command(
            ["ls", "--all", "--no-trunc", "--filter=" + selector, "--format={{.ID}}"],
            deadline=limit,
            label="reconcile-" + item["plan"]["role"],
            record=not cleanup,
        )
        raw = self.checked(handle, limit).stdout
        if raw == b"":
            return None
        try:
            value = raw.decode("ascii").removesuffix("\n")
        except UnicodeError as exc:
            raise PhaseError("invalid-owned-container-list") from exc
        if not _ID.fullmatch(value) or not by_name and value != item["id"]:
            raise PhaseError("ambiguous-owned-container-list")
        return value

    def create(self, plan, stage=None):
        data = plan.to_dict()
        item = {"plan": data, "id": None, "create_attempted": False, "absent": False}
        self.owned.append(item)

        def action(limit):
            self.current(stage)
            self.journal.event("owned-name-registered", plan=data)
            if self.listing(item, limit=limit, by_name=True) is not None:
                raise PhaseError("owned-name-already-exists")
            self.current(stage)
            self.journal.event("stopped-create-attempt", owned_name=data["owned_name"])
            item["create_attempted"] = True
            handle = self.command(
                data["argv"],
                deadline=limit,
                stage=stage,
                label="create-" + data["role"],
                create=True,
            )
            raw = self.checked(handle, limit).stdout
            try:
                value = raw.decode("ascii").removesuffix("\n")
            except UnicodeError as exc:
                raise PhaseError("create-id-unconfirmed") from exc
            if not _ID.fullmatch(value):
                raise PhaseError("create-id-unconfirmed")
            item["id"] = value
            self.journal.event(
                "owned-id-observed", owned_name=data["owned_name"], container_id=value
            )
            raw = self.inspect(value, limit=limit, label="stopped-inspect-" + data["role"])
            self.current(stage)
            environment = self.metadata["metadata"]["images"][data["role"]]["config"]["environment"]
            observation = validate_stopped_container(
                plan,
                raw.decode("utf-8"),
                container_id=value,
                image_environment=environment,
            )
            self.journal.event("stopped-config-observed", observation=observation.to_dict())
            return item

        return self.setup(action)

    def start(self, item, stage=None):
        def action(limit):
            self.current(stage)
            # The trusted pinned CLI owns attach-before-start ordering. This is
            # one combined attempt, never fabricated separate attach evidence.
            self.journal.event("attach-and-start-attempt", container_id=item["id"])
            self.runtime_attempted = True
            handle = self.command(
                ["start", "--attach", item["id"]],
                deadline=limit,
                stage=stage,
                label="attach-start-" + item["plan"]["role"],
            )
            # Client spawn is not a start acknowledgement. Poll only Engine
            # metadata, never retry the application start or any HTTP request.
            for _ in range(8):
                raw = self.inspect(
                    item["id"], limit=limit, label="start-inspect-" + item["plan"]["role"]
                )
                value = _single(raw)
                _owned(value, item["plan"], item["id"])
                state = value.get("State")
                if type(state) is not dict:
                    raise PhaseError("container-start-state-unconfirmed")
                if (
                    state.get("Status") in {"running", "exited"}
                    and type(state.get("StartedAt")) is str
                    and re.fullmatch(r"[0-9]{4}-[0-9T:.+Z-]{15,40}", state["StartedAt"])
                    and state["StartedAt"] != "0001-01-01T00:00:00Z"
                    and all(state.get(key) is False for key in ("Dead", "OOMKilled", "Restarting"))
                    and state.get("Error") == ""
                ):
                    self.journal.event("container-start-observed", container_id=item["id"])
                    return handle
                if state.get("Status") != "created":
                    raise PhaseError("container-start-state-unconfirmed")
                self.current(stage)
                self.pool.pump(limit)
            raise PhaseError("container-start-state-unconfirmed")

        return self.setup(action)

    def finished(self, item, snapshot):
        raw = self.inspect(
            item["id"], limit=self.deadline, label="finished-inspect-" + item["plan"]["role"]
        )
        value = _single(raw)
        _owned(value, item["plan"], item["id"])
        state = value.get("State")
        if (
            type(state) is not dict
            or state.get("Status") != "exited"
            or state.get("Running") is not False
            or state.get("Dead") is not False
            or state.get("OOMKilled") is not False
            or type(state.get("ExitCode")) is not int
            or state["ExitCode"] != snapshot.returncode
            or state.get("Error") != ""
        ):
            raise PhaseError("container-exit-state-unconfirmed")
        self.journal.event(
            "container-exit-observed", container_id=item["id"], exit_code=state["ExitCode"]
        )

    def remove(self, item, *, limit, cleanup=False):
        if not item["create_attempted"] or item["absent"]:
            return
        if item["id"] is None:
            item["id"] = self.listing(item, limit=limit, by_name=True, cleanup=cleanup)
            if item["id"] is None:
                item["absent"] = True
                return
        elif self.listing(item, limit=limit, cleanup=cleanup) is None:
            item["absent"] = True
            return
        raw = self.inspect(
            item["id"],
            limit=limit,
            label="cleanup-inspect-" + item["plan"]["role"],
            cleanup=cleanup,
        )
        _owned(_single(raw), item["plan"], item["id"])
        handle = self.command(
            ["rm", "--force", item["id"]],
            deadline=limit,
            label="remove-" + item["plan"]["role"],
            record=not cleanup,
        )
        self.checked(handle, limit)
        if self.listing(item, limit=limit, cleanup=cleanup) is not None:
            raise PhaseError("container-removal-unconfirmed")
        item["absent"] = True

    def execute(self):
        self.checkpoint = (
            self.workspace.read_source(),
            self.workspace.read_test(),
            self.workspace.read_record(),
        )
        self.current()
        self.journal = _Journal(self.budget)
        self.journal.initialize()
        self.journal.event(
            "phase-created",
            candidate=self.candidate,
            session_nonce=self.nonce,
            phase_plan_id=self.plan_id,
            profile_id=self.profile.profile_id,
            application_sha256=sha256(self.checkpoint[0].data).hexdigest(),
            test_sha256=sha256(self.checkpoint[1].data).hexdigest(),
        )
        self.setup(lambda limit: self._preflight(limit))
        stage_t = GeneratedRepairInputStage(self.workspace, self.candidate, "T")
        self.stages.append(stage_t)
        item_t = self.create(
            ContainerCreatePlan(
                canonical(
                    stage_t.prepare_create(self.profile, self.nonce, uuid.uuid4().hex).to_dict()[
                        "container_create_plan"
                    ]
                )
            ),
            stage_t,
        )
        handle_t = self.start(item_t, stage_t)
        try:
            result_t = self.checked(handle_t, self.deadline, (0, 1))
        finally:
            # Preserve entry/infrastructure refusal (including the maintained
            # guard's 78) without treating any guest exit as trusted proof.
            self.test_exit = self.pool.snapshot(handle_t).returncode
        self.current(stage_t)
        self.finished(item_t, result_t)
        self.remove(item_t, limit=self.deadline)

        stage_a = GeneratedRepairInputStage(self.workspace, self.candidate, "A")
        self.stages.append(stage_a)
        item_a = self.create(
            ContainerCreatePlan(
                canonical(
                    stage_a.prepare_create(self.profile, self.nonce, uuid.uuid4().hex).to_dict()[
                        "container_create_plan"
                    ]
                )
            ),
            stage_a,
        )
        handle_a = self.start(item_a, stage_a)

        def wait_hint(limit):
            while True:
                self.current(stage_a)
                value = self.pool.snapshot(handle_a)
                if value.returncode is not None:
                    raise PhaseError("application-exited-before-relay")
                if _READY in value.stdout.splitlines(keepends=True):
                    return
                self.pool.pump(limit)

        self.setup(wait_hint)
        self.current(stage_a)
        plan_b = build_container_create_plan(
            self.profile,
            "B",
            session_nonce=self.nonce,
            role_nonce=uuid.uuid4().hex,
            application_container_id=item_a["id"],
            remaining_ms=max(1, min(40_000, int((self.deadline - self.now()) * 1000))),
        )
        item_b = self.create(plan_b)
        handle_b = self.start(item_b)
        result_b = self.checked(handle_b, self.deadline)
        self.current(stage_a)
        if self.pool.snapshot(handle_a).returncode is not None:
            raise PhaseError("application-exited-during-relay")
        self.finished(item_b, result_b)
        self.comparison = compare_generated_repair_relay_capture(
            result_b.stdout.decode("utf-8"),
            build_generated_repair_controls(),
            candidate=self.candidate,
        ).to_dict()
        if not self.comparison["matches_expected_profile"]:
            raise PhaseError("independent-http-profile-mismatch")
        self.journal.event("host-comparison", comparison=self.comparison)
        self.current(stage_a)

    def _preflight(self, limit):
        self.pin = _ClientPin(self.profile, self.tick)
        self.metadata = observe_runtime_metadata(
            self.profile,
            phase_deadline=self.deadline,
            setup_deadline=limit,
            before_query=self.current,
        ).to_dict()
        observed_wire = max(
            (
                value
                for value in (self.metadata.get("wire_bytes"), self.metadata.get("wire_bytes_used"))
                if type(value) is int and 0 <= value <= 266_240
            ),
            default=0,
        )
        self.budget.charge(observed_wire)
        self.journal.event("metadata-observed", observation=self.metadata)
        if self.metadata["status"] != "metadata-match":
            raise PhaseError("runtime-metadata-mismatch")
        for role in "TAB":
            config = self.metadata["metadata"]["images"][role]["config"]
            if (
                config.get("environment") != list(_IMAGE_ENVIRONMENT)
                or config.get("volumes") not in (None, {})
                or config.get("user") != "65532:65532"
            ):
                raise PhaseError("reviewed-image-config-mismatch")
        engine = self.metadata["metadata"]["engine"]
        if (
            engine["default_runtime"] != "runc"
            or engine["cgroup_version"] != "2"
            or not any(
                value.startswith("name=seccomp,profile=builtin")
                for value in engine["security_options"] or []
            )
            or any(
                engine["reported_capabilities"].get(key) is not True
                for key in ("MemoryLimit", "SwapLimit", "CpuCfsPeriod", "CpuCfsQuota", "PidsLimit")
            )
        ):
            raise PhaseError("required-daemon-capabilities-unreported")

    def cleanup(self):
        can_dispatch = False
        try:
            self.cleanup_deadline = self.now() + CLEANUP_SECONDS
            self.pool.begin_cleanup(self.cleanup_deadline)
            can_dispatch = True
        except BaseException as exc:
            self.cleanup_errors.append(type(exc).__name__)
            if not isinstance(exc, Exception):
                self.interruption = self.interruption or exc
            # No new daemon call follows an invalid clock/window. Local owned
            # children still get a final signal/close attempt under a last-known
            # conservative bound; this cannot establish confirmed cleanup.
            if self.cleanup_deadline is None:
                self.cleanup_deadline = min(
                    self.last + CLEANUP_SECONDS, self.deadline + CLEANUP_SECONDS
                )
        # The first cleanup error must not prevent attempting another exact
        # owned object under the same deadline. No names/global prune fallback.
        for item in reversed(self.owned) if can_dispatch else ():
            try:
                self.remove(item, limit=self.cleanup_deadline, cleanup=True)
            except BaseException as exc:
                self.cleanup_errors.append(type(exc).__name__)
                if not isinstance(exc, Exception):
                    self.failure = self.failure or "cancelled-during-cleanup"
                    self.interruption = self.interruption or exc
        try:
            snapshots = self.pool.terminate_all(self.cleanup_deadline)
            if any(not value.local_cleanup_confirmed for value in snapshots):
                self.cleanup_errors.append("local-process-cleanup-unconfirmed")
        except BaseException as exc:
            self.cleanup_errors.append(type(exc).__name__)
            if not isinstance(exc, Exception):
                self.interruption = self.interruption or exc
        for stage in self.stages:
            try:
                stage.close()
            except BaseException as exc:
                self.cleanup_errors.append(type(exc).__name__)
                if not isinstance(exc, Exception):
                    self.interruption = self.interruption or exc

    def result(self):
        captures = []
        for value in self.pool.snapshots():
            captures.append(
                {
                    "label": value.label,
                    "returncode": value.returncode,
                    "complete": value.complete,
                    "stdout_base64": base64.b64encode(value.stdout).decode("ascii"),
                    "stderr_base64": base64.b64encode(value.stderr).decode("ascii"),
                    "errors": list(value.errors),
                    "local_cleanup_confirmed": value.local_cleanup_confirmed,
                }
            )
        cleaned = not self.cleanup_errors and all(
            not item["create_attempted"] or item["absent"] for item in self.owned
        )
        engine_cleanup = True
        if self.metadata is not None:
            diagnostic = self.metadata.get("transport_diagnostic")
            if type(diagnostic) is dict and (
                diagnostic.get("cleanup_failure") is True
                or diagnostic.get("socket_cleanup") not in ("not-needed", "confirmed")
            ):
                engine_cleanup = False
        cleaned = cleaned and engine_cleanup
        return {
            "schema_version": "1.0",
            "kind": "generated-repair-phase-result",
            "candidate": self.candidate,
            "profile_id": self.profile.profile_id,
            "phase_plan_id": self.plan_id,
            "session_nonce": self.nonce,
            "status": "complete" if self.failure is None and cleaned else "failed",
            "failure": self.failure,
            "cleanup_confirmed": cleaned,
            "cleanup_errors": self.cleanup_errors,
            "generated_runtime_attempted": self.runtime_attempted,
            "test_exit_code": self.test_exit,
            "runtime_metadata": self.metadata,
            "engine_transport_cleanup_confirmed": engine_cleanup,
            "comparison": self.comparison,
            "owned": [
                {
                    "role": item["plan"]["role"],
                    "name": item["plan"]["owned_name"],
                    "id": item["id"],
                    "create_attempted": item["create_attempted"],
                    "absence_observed": item["absent"],
                }
                for item in self.owned
            ],
            "application_sha256": None
            if self.checkpoint is None
            else sha256(self.checkpoint[0].data).hexdigest(),
            "test_sha256": None
            if self.checkpoint is None
            else sha256(self.checkpoint[1].data).hexdigest(),
            "cli_output_bytes": self.pool.output_bytes,
            "setup_seconds": self.setup_used,
            "transport_failure": self.pool.first_failure,
            "evidence_directory": None
            if self.journal is None or self.journal.path is None
            else str(self.journal.path),
            "evidence_initialization_stage": None
            if self.journal is None
            else self.journal.initialization_stage,
            "captures": captures,
            "execution_authorized": False,
            "authorization_status": "unknown",
            "verified_fix": False,
            "source_applied": False,
            "resource_enforcement_established": False,
            "isolation_established": False,
            "universal_wall_time_bound": False,
            "provenance": "historical-private-controller-result-not-importable-authority",
        }


def execute_generated_repair_phase(
    workspace, candidate, profile, *, session_nonce, phase_plan_id, dispatch_guard, evidence_budget
) -> GeneratedRepairPhaseResult:
    """Effectful internal entry; not connected to public CLI or disabled session.

    A trusted future coordinator must review actual image contents/capabilities
    and each fresh decision before calling. The guard is coordination, not an
    authentication boundary. No caller-selected command, source or network path
    is accepted. Test reports and the startup hint never authorize file writes.
    """
    if (
        not supported()
        or type(workspace) is not GeneratedRepairWorkspace
        or candidate not in ("before", "after")
        or workspace.state != ("ready-before" if candidate == "before" else "applied-after")
        or type(profile) is not RuntimeProfile
        or type(session_nonce) is not str
        or not _NONCE.fullmatch(session_nonce)
        or type(phase_plan_id) is not str
        or not re.fullmatch(r"generated-repair-session-plan-[0-9a-f]{64}", phase_plan_id)
        or not callable(dispatch_guard)
        or inspect.iscoroutinefunction(dispatch_guard)
        or type(evidence_budget) is not SessionEvidenceBudget
    ):
        raise PhaseError("invalid-private-phase-context")
    # Precharge a bounded record slot so failure handling never exports a large
    # uncharged capture when later journal charges exhaust the shared budget.
    evidence_budget.charge(MAX_PHASE_RESULT_BYTES)
    phase = _Phase(
        workspace, candidate, profile, session_nonce, phase_plan_id, dispatch_guard, evidence_budget
    )
    interrupted = None
    try:
        phase.execute()
    except BaseException as exc:
        phase.failure = str(exc) if type(exc) is PhaseError else type(exc).__name__
        if not isinstance(exc, Exception):
            interrupted = exc
    finally:
        try:
            phase.cleanup()
        except BaseException as exc:
            phase.cleanup_errors.append(type(exc).__name__)
            if not isinstance(exc, Exception):
                interrupted = interrupted or exc
    interrupted = interrupted or phase.interruption
    payload = phase.result()
    try:
        if phase.journal is not None:
            phase.journal.result(payload)
    except BaseException as exc:
        payload["status"] = "failed"
        payload["failure"] = payload["failure"] or "evidence-persistence-failed"
        payload["evidence_persistence_failure"] = type(exc).__name__
        if not isinstance(exc, Exception):
            interrupted = interrupted or exc
    finally:
        if phase.journal is not None:
            try:
                phase.journal.close()
            except BaseException as exc:
                payload["status"] = "failed"
                payload["failure"] = payload["failure"] or "journal-close-unconfirmed"
                payload["journal_close_failure"] = type(exc).__name__
                if not isinstance(exc, Exception):
                    interrupted = interrupted or exc
    result = GeneratedRepairPhaseResult(canonical(payload))
    if interrupted is not None:
        interrupted.generated_repair_phase_result = result
        raise interrupted
    return result
