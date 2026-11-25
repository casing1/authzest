"""Private HTTP-only A -> B direct phase for one live private source copy.

A trusted coordinator calls this after a current private copy (before) or
private apply (after) decision. It stages the exact live private source for A,
creates/starts owned A and B guests through the pinned Docker client, gives B
only the request schedule over bounded stdin plus EOF, removes every owned
guest and compares B's capture with host-held independent case expectations.

Calling it is an effect. Results are retained history: they never reopen a
session, approve a later file write or certify the application. Guest output,
including A's startup hint and B's capture, remains untrusted data.
"""

from __future__ import annotations

import base64
import inspect
import json
import math
import re
import uuid
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from authzest.codex.contracts import canonical
from authzest.runner._generated_repair_phase import (
    _IMAGE_ENVIRONMENT,
    MAX_PHASE_RESULT_BYTES,
    PhaseError,
    SessionEvidenceBudget,
    _Journal,
    _json,
    _single,
)
from authzest.runner._generated_repair_process import MAX_INPUT_BYTES, ProcessPool
from authzest.runner._repository_http_client_pin import RepositoryHttpClientPin
from authzest.runner._repository_http_container_inspect import validate_stopped_container
from authzest.runner._repository_http_preflight import observe_runtime_metadata
from authzest.runner._repository_http_runtime_input import LoadedRepositoryHttpRuntimeProfile
from authzest.runner._repository_http_runtime_profile import (
    RepositoryHttpCreatePlan,
    build_container_create_plan,
    validate_runtime_profile,
)
from authzest.runner._repository_http_staging import (
    RepositoryHttpInputStage,
    RepositoryHttpStageInitializationError,
    supported,
)
from authzest.runner._repository_http_transport import (
    MAX_CAPTURE_BYTES,
    HTTPProfileError,
    decode_response_fact,
    validate_http_observer_schedule,
)
from authzest.runner.repository_http_file_session import RepositoryHttpFileSession
from authzest.runner.repository_http_verification import (
    RepositoryHttpVerificationPlan,
    compare_repository_http_phase,
    prepare_repository_http_observer_schedule,
)

PHASE_SECONDS = 40.0
SETUP_SECONDS = 10.0
CLEANUP_SECONDS = 10.0
MAX_OUTPUT_BYTES = 262_144
_READY = b"AUTHZEST_REPOSITORY_HTTP_A_STARTED\n"
_LABEL = "org.authzest.repository-http."
_ID = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_STATES = {"before": "copied-before", "after": "applied-after"}
_INLINE_OUTPUT_BYTES = 16_384
_MANIFEST_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}
_RECORD_FIELDS = {
    "case_id",
    "dispatch_status",
    "fact",
    "error_code",
    "close_status",
    "close_failure",
}
_CAPTURE_FIELDS = {
    "schema_version",
    "kind",
    "schedule_id",
    "plan_id",
    "phase",
    "planned_count",
    "status",
    "records",
    "failure",
    "wire_bytes",
    "recv_calls",
    "cancellation",
    "provenance",
    "execution_status",
    "authorization_status",
    "verified_fix",
}


class RepositoryHttpPhaseError(PhaseError):
    """A direct HTTP phase step failed; the retained result describes known effects."""


@dataclass(frozen=True, slots=True)
class RepositoryHttpPhaseResult:
    """Detached history only; no importer, readiness or write capability."""

    payload_json: str

    def to_dict(self) -> dict:
        return json.loads(self.payload_json)


def _error_class(code):
    """Project a guest capture failure onto the closed supplied-frame error set."""
    if code == "deadline-expired":
        return "timeout"
    if code == "body-invalid":
        return code
    if code.startswith("http-") or code in {"wire-budget", "receive-call-budget"}:
        return "http-framing"
    return "transport-error"


def _bounded_output(name, data):
    """Inline small outputs; larger ones (B's capture) keep only size and digest.

    The decoded relay capture is summarized separately and its digest journaled,
    so the retained result stays within its precharged fixed allowance.
    """
    if len(data) <= _INLINE_OUTPUT_BYTES:
        return {name + "_base64": base64.b64encode(data).decode("ascii")}
    return {name + "_sha256": sha256(data).hexdigest(), name + "_bytes": len(data)}


def _manifest_pin(image):
    """Select the image-inspect platform manifest digest, never the config ID.

    The containerd image store reports a single-platform manifest descriptor
    without ``platform``; the same inspect's linux/arm64 fields (already checked
    by the metadata projection) identify its platform. Indexes/lists never
    qualify. The stopped container must later report this exact digest with an
    explicit platform, from a separate daemon query.
    """
    descriptor = image["manifest_descriptor"]
    if image["platform_manifest_reported"] is True:
        return descriptor["digest"]
    if (
        type(descriptor) is dict
        and descriptor.get("platform") is None
        and descriptor.get("mediaType") in _MANIFEST_TYPES
        and image.get("os") == "linux"
        and image.get("architecture") == "arm64"
        and image.get("variant") in (None, "", "v8")
    ):
        return descriptor["digest"]
    raise RepositoryHttpPhaseError("platform-manifest-pin-unreported")


def _owned(value, plan, container_id=None):
    config = value.get("Config")
    labels = config.get("Labels") if type(config) is dict else None
    image = plan["profile"]["images"][plan["role"]]["image_id"]
    if (
        type(value.get("Id")) is not str
        or not _ID.fullmatch(value["Id"])
        or container_id is not None
        and value["Id"] != container_id
        or value.get("Name") != "/" + plan["owned_name"]
        or type(labels) is not dict
        or labels.get(_LABEL + "session") != plan["session_nonce"]
        or labels.get(_LABEL + "role") != plan["role"]
        or labels.get(_LABEL + "nonce") != plan["role_nonce"]
        or value.get("Image") != image
        or config.get("Image") != image
    ):
        raise RepositoryHttpPhaseError("owned-container-identity-unconfirmed")
    return value["Id"]


def decode_relay_capture(raw: bytes, schedule: dict, *, exit_code: int) -> dict:
    """Strictly decode B's bounded capture for exactly this schedule and exit."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_CAPTURE_BYTES:
        raise RepositoryHttpPhaseError("relay-capture-size")
    try:
        data = _json(raw)
    except PhaseError as exc:
        raise RepositoryHttpPhaseError("relay-capture-json") from exc
    requests = schedule["requests"]
    schedule_id = (
        "repository-http-observer-schedule-"
        + sha256(canonical(schedule).encode("utf-8")).hexdigest()
    )
    if (
        type(data) is not dict
        or set(data) != _CAPTURE_FIELDS
        or data["schema_version"] != "2.0"
        or data["kind"] != "repository-http-raw-capture"
        or data["schedule_id"] != schedule_id
        or data["plan_id"] != schedule["plan_id"]
        or data["phase"] != schedule["phase"]
        or data["planned_count"] != len(requests)
        or data["status"] != {0: "complete", 1: "partial"}.get(exit_code)
        or type(data["records"]) is not list
        or len(data["records"]) != len(requests)
        or data["verified_fix"] is not False
    ):
        raise RepositoryHttpPhaseError("relay-capture-identity")
    for request, record in zip(requests, data["records"], strict=True):
        if (
            type(record) is not dict
            or set(record) != _RECORD_FIELDS
            or record["case_id"] != request["case_id"]
            or record["dispatch_status"] not in {"response", "error", "not-dispatched"}
            or record["error_code"] is not None
            and (type(record["error_code"]) is not str or not 1 <= len(record["error_code"]) <= 64)
        ):
            raise RepositoryHttpPhaseError("relay-capture-record")
    return data


def build_phase_frame(capture: dict, plan: dict, phase: str, cleanup: dict) -> dict:
    """Project decoded responses into the closed comparison frame.

    Expected answers never enter this projection; the host compares afterward.
    The first failure aborts the remaining cases, mirroring the guest loop.
    """
    observations, aborted = [], False
    for record in capture["records"]:
        if aborted:
            if record["dispatch_status"] != "not-dispatched" or record["fact"] is not None:
                raise RepositoryHttpPhaseError("relay-capture-after-abort")
            observations.append(
                {
                    "case_id": record["case_id"],
                    "outcome": "not-dispatched",
                    "response": None,
                    "error_code": "phase-aborted",
                }
            )
            continue
        if (
            record["dispatch_status"] == "response"
            and record["error_code"] is None
            and record["close_status"] == "closed"
        ):
            try:
                value = decode_response_fact(record["fact"])
            except HTTPProfileError as exc:
                observations.append(
                    {
                        "case_id": record["case_id"],
                        "outcome": "error",
                        "response": None,
                        "error_code": _error_class(exc.code),
                    }
                )
                aborted = True
                continue
            observations.append(
                {
                    "case_id": record["case_id"],
                    "outcome": "response",
                    "response": value,
                    "error_code": None,
                }
            )
        elif record["dispatch_status"] in {"error", "not-dispatched"} and record["error_code"]:
            observations.append(
                {
                    "case_id": record["case_id"],
                    "outcome": "error",
                    "response": None,
                    "error_code": _error_class(record["error_code"]),
                }
            )
            aborted = True
        else:
            raise RepositoryHttpPhaseError("relay-capture-record")
    return {
        "schema_version": "2.0",
        "kind": "repository-http-supplied-phase",
        "plan_id": plan["plan_id"],
        "phase": phase,
        "binding": {
            "source_sha256": plan["source"][phase + "_sha256"],
            "interface_id": plan["http_interface"]["interface_id"],
            "case_set_id": plan["case_set_id"],
            "poc_sha256": plan["poc_sha256"],
        },
        "observations": observations,
        "cleanup": cleanup,
    }


class _Phase:
    def __init__(self, inputs, profile_input, phase, nonce, guard, budget):
        self.clock = monotonic
        self.last = 0.0
        self.started = self.now()
        self.deadline = self.started + PHASE_SECONDS
        self.setup_used = 0.0
        self.cleanup_deadline = None
        self.session, self.request, self.response, self.cases, self.plan = inputs
        self.profile_input = profile_input
        self.profile = validate_runtime_profile(profile_input.profile.payload_json)
        self.phase, self.nonce, self.guard, self.budget = phase, nonce, guard, budget
        self.pool = ProcessPool(
            clock=self.now,
            max_output_bytes=MAX_OUTPUT_BYTES,
            cleanup_reserve_bytes=32_768,
            max_input_bytes=MAX_INPUT_BYTES,
        )
        self.pin = self.journal = self.metadata = self.checkpoint = None
        self.schedule = self.schedule_bytes = None
        self.stages, self.owned, self.commands = [], [], []
        self.manifest_pins = {}
        self.capture = self.capture_failure = self.relay_exit = None
        self.frame = self.comparison = None
        self.stage_failure = None
        self.failure = None
        self.cleanup_errors = []
        self.runtime_attempted = False
        self.interruption = None

    def now(self):
        value = self.clock()
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not self.last <= value <= 2**48
        ):
            raise RepositoryHttpPhaseError("phase-clock-unconfirmed")
        self.last = float(value)
        return self.last

    def tick(self):
        deadline = self.cleanup_deadline if self.cleanup_deadline is not None else self.deadline
        if self.now() >= deadline:
            raise RepositoryHttpPhaseError("original-phase-or-cleanup-deadline-expired")

    def current(self, stage=None):
        self.tick()
        if self.cleanup_deadline is None:
            answer = self.guard()
            if inspect.iscoroutine(answer):
                answer.close()
            if answer is not None:
                raise RepositoryHttpPhaseError("dispatch-guard-must-synchronously-return-none")
            self.session._recheck_runtime_checkpoint(self.checkpoint)
            self.profile_input.assert_current()
            if self.profile_input.profile.payload_json != self.profile.payload_json:
                raise RepositoryHttpPhaseError("runtime-profile-changed-during-phase")
            if stage is not None:
                stage.assert_current()
        if self.pin is not None:
            self.pin.check()
        self.tick()

    def setup(self, operation):
        before = self.now()
        limit = min(self.deadline, before + SETUP_SECONDS - self.setup_used)
        if limit <= before:
            raise RepositoryHttpPhaseError("cumulative-setup-readiness-limit")
        failure = None
        try:
            return operation(limit)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            self.setup_used += self.now() - before
            if self.setup_used > SETUP_SECONDS and failure is None:
                raise RepositoryHttpPhaseError("cumulative-setup-readiness-limit")

    def command(self, args, *, deadline, stage=None, label, create=False, record=True, data=None):
        self.current(stage)
        if self.now() >= deadline:
            raise RepositoryHttpPhaseError("command-dispatch-deadline-expired")
        engine = self.profile.to_dict()["engine"]
        argv = (
            list(args)
            if create
            else [
                engine["executable"],
                "--config=" + engine["config_dir"],
                "--host=" + engine["endpoint"],
                "container",
                *args,
            ]
        )
        if record:
            self.journal.event("command-intent", label=label)
        self.tick()
        if self.now() >= deadline:
            raise RepositoryHttpPhaseError("command-dispatch-deadline-expired")
        handle = self.pool.start(
            argv,
            {"DOCKER_API_VERSION": engine["api_version"]},
            deadline=(self.cleanup_deadline or self.deadline),
            label=label + "-" + str(len(self.commands)),
            input_bytes=data,
        )
        self.commands.append(handle)
        return handle

    def checked(self, handle, deadline, allowed=(0,)):
        snapshot = self.pool.wait(handle, deadline)
        if not snapshot.complete or snapshot.returncode not in allowed:
            raise RepositoryHttpPhaseError("docker-command-failed")
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
            raise RepositoryHttpPhaseError("invalid-owned-container-list") from exc
        if not _ID.fullmatch(value) or not by_name and value != item["id"]:
            raise RepositoryHttpPhaseError("ambiguous-owned-container-list")
        return value

    def create(self, plan, stage):
        data = plan.to_dict()
        item = {"plan": data, "id": None, "create_attempted": False, "absent": False}
        self.owned.append(item)

        def action(limit):
            self.current(stage)
            self.journal.event("owned-name-registered", plan_id=plan.plan_id, plan=data)
            if self.listing(item, limit=limit, by_name=True) is not None:
                raise RepositoryHttpPhaseError("owned-name-already-exists")
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
                raise RepositoryHttpPhaseError("create-id-unconfirmed") from exc
            if not _ID.fullmatch(value):
                raise RepositoryHttpPhaseError("create-id-unconfirmed")
            item["id"] = value
            self.journal.event(
                "owned-id-observed", owned_name=data["owned_name"], container_id=value
            )
            raw = self.inspect(value, limit=limit, label="stopped-inspect-" + data["role"])
            self.current(stage)
            role = data["role"]
            observation = validate_stopped_container(
                plan,
                raw.decode("utf-8"),
                container_id=value,
                image_environment=self.metadata["metadata"]["images"][role]["config"][
                    "environment"
                ],
                image_manifest_digest=self.manifest_pins[role],
            )
            self.journal.event("stopped-config-observed", observation=observation.to_dict())
            return item

        return self.setup(action)

    def start(self, item, stage, data=None):
        role = item["plan"]["role"]

        def action(limit):
            self.current(stage)
            # The pinned CLI owns attach-before-start ordering and, for B, the
            # exact schedule write followed by EOF. It is one combined attempt.
            self.journal.event("attach-and-start-attempt", container_id=item["id"])
            self.runtime_attempted = True
            handle = self.command(
                [
                    "start",
                    "--attach",
                    *(("--interactive",) if data is not None else ()),
                    item["id"],
                ],
                deadline=limit,
                stage=stage,
                label="attach-start-" + role,
                data=data,
            )
            # Poll only Engine metadata; never retry the start or any request.
            for _ in range(8):
                value = _single(
                    self.inspect(item["id"], limit=limit, label="start-inspect-" + role)
                )
                _owned(value, item["plan"], item["id"])
                state = value.get("State")
                if type(state) is not dict:
                    raise RepositoryHttpPhaseError("container-start-state-unconfirmed")
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
                    raise RepositoryHttpPhaseError("container-start-state-unconfirmed")
                self.current(stage)
                self.pool.pump(limit)
            raise RepositoryHttpPhaseError("container-start-state-unconfirmed")

        return self.setup(action)

    def finished(self, item, snapshot):
        role = item["plan"]["role"]
        value = _single(self.inspect(item["id"], limit=self.deadline, label="exit-inspect-" + role))
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
            raise RepositoryHttpPhaseError("container-exit-state-unconfirmed")
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
        role = item["plan"]["role"]
        raw = self.inspect(
            item["id"], limit=limit, label="cleanup-inspect-" + role, cleanup=cleanup
        )
        _owned(_single(raw), item["plan"], item["id"])
        handle = self.command(
            ["rm", "--force", item["id"]],
            deadline=limit,
            label="remove-" + role,
            record=not cleanup,
        )
        self.checked(handle, limit)
        if self.listing(item, limit=limit, cleanup=cleanup) is not None:
            raise RepositoryHttpPhaseError("container-removal-unconfirmed")
        item["absent"] = True

    def execute(self):
        self.checkpoint = self.session._capture_runtime_checkpoint(self.phase)
        schedule = prepare_repository_http_observer_schedule(
            self.plan, self.request, self.response, self.cases, phase=self.phase
        )
        self.schedule = validate_http_observer_schedule(schedule)
        self.schedule_bytes = canonical(self.schedule).encode("utf-8")
        self.current()
        self.journal = _Journal(self.budget, prefix="authzest-repository-http-phase-")
        self.journal.initialize()
        self.journal.event(
            "phase-created",
            phase=self.phase,
            session_nonce=self.nonce,
            plan_id=self.plan.plan_id,
            profile_id=self.profile.profile_id,
            file_session_id=self.checkpoint.session_id,
            file_session_revision=self.checkpoint.revision,
            source_sha256=sha256(self.checkpoint.source_bytes).hexdigest(),
            schedule_sha256=sha256(self.schedule_bytes).hexdigest(),
        )
        self.setup(self._preflight)
        try:
            stage = RepositoryHttpInputStage(
                self.session, self.request, self.response, self.cases, self.plan, self.phase
            )
        except BaseException as exc:
            failure = getattr(exc, "repository_http_stage_initialization", exc)
            if isinstance(failure, RepositoryHttpStageInitializationError):
                self.stage_failure = {
                    "stage": failure.stage,
                    "created_path": None
                    if failure.created_path is None
                    else str(failure.created_path),
                    "allocation_attempted": failure.allocation_attempted,
                    "creation_confirmed": failure.creation_confirmed,
                    "ownership_uncertain": failure.ownership_uncertain,
                    "descriptor_cleanup_confirmed": failure.descriptor_cleanup_confirmed,
                }
                if failure.descriptor_cleanup_confirmed is not True or failure.ownership_uncertain:
                    self.cleanup_errors.append("stage-initialization-cleanup-unconfirmed")
            raise
        self.stages.append(stage)
        staged = stage.prepare_create(self.profile, self.nonce, uuid.uuid4().hex).to_dict()
        item_a = self.create(
            RepositoryHttpCreatePlan(canonical(staged["container_create_plan"])), stage
        )
        handle_a = self.start(item_a, stage)

        def wait_hint(limit):
            while True:
                self.current(stage)
                value = self.pool.snapshot(handle_a)
                if value.returncode is not None:
                    raise RepositoryHttpPhaseError("application-exited-before-relay")
                if _READY in value.stdout.splitlines(keepends=True):
                    return
                self.pool.pump(limit)

        self.setup(wait_hint)
        self.current(stage)
        plan_b = build_container_create_plan(
            self.profile,
            "B",
            session_nonce=self.nonce,
            role_nonce=uuid.uuid4().hex,
            application_container_id=item_a["id"],
            remaining_ms=max(1, min(40_000, int((self.deadline - self.now()) * 1000))),
            schedule=self.schedule,
        )
        stdin = plan_b.to_dict()["stdin"]
        if (
            stdin["sha256"] != sha256(self.schedule_bytes).hexdigest()
            or stdin["utf8_bytes"] != len(self.schedule_bytes)
            or len(self.schedule_bytes) > MAX_INPUT_BYTES
        ):
            raise RepositoryHttpPhaseError("relay-schedule-binding-mismatch")
        item_b = self.create(plan_b, stage)
        handle_b = self.start(item_b, stage, self.schedule_bytes)
        try:
            result_b = self.checked(handle_b, self.deadline, (0, 1))
        finally:
            self.relay_exit = self.pool.snapshot(handle_b).returncode
        self.current(stage)
        if self.pool.snapshot(handle_a).returncode is not None:
            raise RepositoryHttpPhaseError("application-exited-during-relay")
        self.finished(item_b, result_b)
        try:
            self.capture = decode_relay_capture(
                result_b.stdout, self.schedule, exit_code=result_b.returncode
            )
        except RepositoryHttpPhaseError as exc:
            self.capture_failure = str(exc)
            raise
        self.journal.event(
            "relay-capture-observed",
            status=self.capture["status"],
            failure=self.capture["failure"],
            stdout_sha256=sha256(result_b.stdout).hexdigest(),
        )
        self.current(stage)

    def _preflight(self, limit):
        self.pin = RepositoryHttpClientPin(self.profile, self.tick)
        self.metadata = observe_runtime_metadata(
            self.profile,
            phase_deadline=self.deadline,
            setup_deadline=limit,
            before_query=self.current,
        ).to_dict()
        wire = self.metadata.get("wire_bytes_used")
        self.budget.charge(wire if type(wire) is int and 0 <= wire <= 266_240 else 0)
        self.journal.event("metadata-observed", observation=self.metadata)
        if self.metadata["status"] != "metadata-match":
            raise RepositoryHttpPhaseError("runtime-metadata-mismatch")
        for role in "AB":
            image = self.metadata["metadata"]["images"][role]
            config = image["config"]
            if (
                config.get("environment") != list(_IMAGE_ENVIRONMENT)
                or config.get("volumes") not in (None, {})
                or config.get("user") != "65532:65532"
            ):
                raise RepositoryHttpPhaseError("reviewed-image-config-mismatch")
            self.manifest_pins[role] = _manifest_pin(image)
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
            raise RepositoryHttpPhaseError("required-daemon-capabilities-unreported")

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
            if self.cleanup_deadline is None:
                self.cleanup_deadline = min(
                    self.last + CLEANUP_SECONDS, self.deadline + CLEANUP_SECONDS
                )
        # Each exact owned guest gets an attempt; no name/global prune fallback.
        for item in reversed(self.owned) if can_dispatch else ():
            try:
                self.remove(item, limit=self.cleanup_deadline, cleanup=True)
            except BaseException as exc:
                item["cleanup_failed"] = True
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

    def compare(self):
        """Compare only after every owned guest's cleanup state is known."""
        if self.capture is None:
            return
        states = {}
        for role in "AB":
            items = [item for item in self.owned if item["plan"]["role"] == role]
            # Each role reflects only its own exact removal observation.
            states[role] = (
                "confirmed"
                if len(items) == 1 and items[0]["absent"]
                else "failed"
                if any(item.get("cleanup_failed") for item in items)
                else "unknown"
            )
        plan = self.plan.to_dict()
        try:
            self.frame = build_phase_frame(self.capture, plan, self.phase, states)
        except RepositoryHttpPhaseError as exc:
            self.capture_failure = str(exc)
            self.failure = self.failure or str(exc)
            return
        self.comparison = compare_repository_http_phase(
            canonical(self.frame),
            self.plan,
            self.request,
            self.response,
            self.cases,
            phase=self.phase,
        )
        if self.comparison["frame_status"] != "valid-supplied":
            self.failure = self.failure or "relay-frame-invalid"

    def result(self):
        captures = [
            {
                "label": value.label,
                "returncode": value.returncode,
                "complete": value.complete,
                **_bounded_output("stdout", value.stdout),
                **_bounded_output("stderr", value.stderr),
                "errors": list(value.errors),
                "local_cleanup_confirmed": value.local_cleanup_confirmed,
            }
            for value in self.pool.snapshots()
        ]
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
        complete = self.failure is None and cleaned and self.comparison is not None
        checkpoint = self.checkpoint
        return {
            "schema_version": "2.0",
            "kind": "repository-http-phase-result",
            "phase": self.phase,
            "plan_id": self.plan.plan_id,
            "profile_id": self.profile.profile_id,
            "session_nonce": self.nonce,
            "file_session_id": None if checkpoint is None else checkpoint.session_id,
            "file_session_revision": None if checkpoint is None else checkpoint.revision,
            "source_path": None if checkpoint is None else checkpoint.source_path,
            "source_sha256": None
            if checkpoint is None
            else sha256(checkpoint.source_bytes).hexdigest(),
            "schedule_sha256": None
            if self.schedule_bytes is None
            else sha256(self.schedule_bytes).hexdigest(),
            "status": "complete" if complete else "failed",
            "failure": self.failure,
            # A capture-level failure (e.g. B's final deadline check) is never
            # success, even when every individual record holds a response.
            "criteria_met": bool(
                complete
                and self.capture["status"] == "complete"
                and self.capture["failure"] is None
                and self.comparison["supplied_criteria_met"]
            ),
            "cleanup_confirmed": cleaned,
            "cleanup_errors": self.cleanup_errors,
            "runtime_attempted": self.runtime_attempted,
            "relay_exit_code": self.relay_exit,
            "relay_capture": None
            if self.capture is None
            else {
                key: self.capture[key]
                for key in ("status", "failure", "wire_bytes", "recv_calls", "schedule_id")
            },
            "relay_capture_failure": self.capture_failure,
            "frame": self.frame,
            "frame_source": "direct-host-phase-relay-capture",
            "comparison": self.comparison,
            "runtime_metadata": self.metadata,
            "engine_transport_cleanup_confirmed": engine_cleanup,
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
            "staged_inputs": [
                None if stage.path is None else str(stage.path) for stage in self.stages
            ],
            "stage_initialization_failure": self.stage_failure,
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
            "authorization_status": "unknown",
            "verified_fix": False,
            "source_applied": False,
            "resource_enforcement_established": False,
            "isolation_established": False,
            "universal_wall_time_bound": False,
            "provenance": "historical-private-controller-result-not-importable-authority",
        }


def execute_repository_http_phase(
    session,
    request,
    response,
    cases,
    plan,
    profile_input,
    *,
    phase,
    session_nonce,
    dispatch_guard,
    evidence_budget,
) -> RepositoryHttpPhaseResult:
    """Run one bounded HTTP-only A -> B phase against the live private source.

    The caller is trusted to have obtained the current user's decision for this
    phase. ``session`` must be quiescent in ``copied-before`` (before) or
    ``applied-after`` (after). No caller-selected command, path or network
    target is accepted, and nothing here writes the private or original source.
    """
    if (
        not supported()
        or type(session) is not RepositoryHttpFileSession
        or type(phase) is not str
        or phase not in _STATES
        or session.state != _STATES[phase]
        or type(plan) is not RepositoryHttpVerificationPlan
        or type(profile_input) is not LoadedRepositoryHttpRuntimeProfile
        or type(session_nonce) is not str
        or not _NONCE.fullmatch(session_nonce)
        or not callable(dispatch_guard)
        or inspect.iscoroutinefunction(dispatch_guard)
        or type(evidence_budget) is not SessionEvidenceBudget
    ):
        raise RepositoryHttpPhaseError("invalid-private-http-phase-context")
    try:
        validate_runtime_profile(profile_input.profile.payload_json)
    except Exception:
        raise RepositoryHttpPhaseError("invalid-private-http-phase-context") from None
    # Precharge one bounded record slot before any effect.
    evidence_budget.charge(MAX_PHASE_RESULT_BYTES)
    current = _Phase(
        (session, request, response, cases, plan),
        profile_input,
        phase,
        session_nonce,
        dispatch_guard,
        evidence_budget,
    )
    interrupted = None
    try:
        current.execute()
    except BaseException as exc:
        current.failure = str(exc) if isinstance(exc, PhaseError) else type(exc).__name__
        if not isinstance(exc, Exception):
            interrupted = exc
    finally:
        try:
            current.cleanup()
        except BaseException as exc:
            current.cleanup_errors.append(type(exc).__name__)
            if not isinstance(exc, Exception):
                interrupted = interrupted or exc
    try:
        current.compare()
    except BaseException as exc:
        current.failure = current.failure or (
            str(exc) if isinstance(exc, PhaseError) else type(exc).__name__
        )
        if not isinstance(exc, Exception):
            interrupted = interrupted or exc
    interrupted = interrupted or current.interruption
    payload = current.result()
    try:
        if current.journal is not None:
            current.journal.result(payload)
    except BaseException as exc:
        payload["status"] = "failed"
        payload["criteria_met"] = False
        payload["failure"] = payload["failure"] or "evidence-persistence-failed"
        payload["evidence_persistence_failure"] = type(exc).__name__
        if not isinstance(exc, Exception):
            interrupted = interrupted or exc
    finally:
        if current.journal is not None:
            try:
                current.journal.close()
            except BaseException as exc:
                payload["status"] = "failed"
                payload["criteria_met"] = False
                payload["failure"] = payload["failure"] or "journal-close-unconfirmed"
                payload["journal_close_failure"] = type(exc).__name__
                if not isinstance(exc, Exception):
                    interrupted = interrupted or exc
    result = RepositoryHttpPhaseResult(canonical(payload))
    if interrupted is not None:
        interrupted.repository_http_phase_result = result
        raise interrupted
    return result
