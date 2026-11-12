"""Private, fake-only lifecycle model; there is deliberately no execution adapter.

Intents and replies are synthetic data, not commands, consent, runtime observations,
or resumable records. This model cannot establish a baseline or unlock a source write.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from time import monotonic
from types import CoroutineType
from uuid import uuid4

from authzest.codex.contracts import ContractError, canonical, decode, identity

_ROLES = ("T", "A", "B")
_ID = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "record": {"ok"},
    "create": {"status", "container_id"},
    "inspect": {"status", "container_id", "config"},
    "reconcile": {"status", "container_id", "config"},
    "attach": {"status"},
    "start": {"status"},
    "readiness": {"ready", "output_bytes"},
    "capture": {"complete", "exit_code", "signal", "oom", "output_bytes"},
    "terminate": {"stopped", "output_bytes"},
    "remove": {"removed"},
}


@dataclass(frozen=True, slots=True)
class LifecycleIntent:
    """An immutable simulated intent, never an executable command."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    """Historical simulated state; it is not a fresh runtime attestation."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)


def _error() -> ContractError:
    return ContractError("Invalid synthetic lifecycle transition", code="validation-shape")


def _json(raw: object) -> str:
    """Bound arbitrary caller data before encoding, including cycles/subclasses."""
    pending = [(raw, 0)]
    visited = 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if visited > 512 or depth > 8:
            raise _error()
        if type(item) is dict:
            if len(item) > 64 or any(type(key) is not str for key in item):
                raise _error()
            pending.extend((child, depth + 1) for child in item.values())
            pending.extend((key, depth + 1) for key in item)
        elif type(item) is list:
            if len(item) > 64:
                raise _error()
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            if len(item) > 4096:
                raise _error()
        elif (
            item is not None
            and type(item) not in (bool, int, float)
            or type(item) in (int, float)
            and (abs(item) > 2**53 or not math.isfinite(item))
        ):
            raise _error()
    encoded = canonical(raw)
    try:
        size = len(encoded.encode("utf-8"))
    except UnicodeError as exc:
        raise _error() from exc
    if size > 16_384:
        raise _error()
    return encoded


class GeneratedRepairLifecycleModel:
    """One bounded synthetic phase, with no preview, file, transport, or import API.

    The trusted clock callback is not a sandbox. A pending intent must receive one
    closed reply; asking for another intent cannot repeat its simulated dispatch.
    Normal T cleanup is inside the original phase. Final/failure cleanup has one
    additional ten-second deadline shared by every remaining role, never reset.
    """

    def __init__(self, *, clock=monotonic) -> None:
        if not callable(clock):
            raise _error()
        self._clock = clock
        self._busy = False
        self._last_time = None
        self._phase_started = self._phase_deadline = self._cleanup_deadline = None
        self._readiness_started = None
        self._readiness_seconds = 0.0
        self._output_bytes = 0
        self._failure = None
        self._finished = False
        self._cleanup_mode = self._terminal_cleanup = False
        self._clock_bad = False
        self._pending = None
        self._count = 0
        self._role, self._step = "T", "record"
        self._session = uuid4().hex
        self._engine = "synthetic-engine-" + uuid4().hex
        self._roles = {}
        for role in _ROLES:
            nonce = uuid4().hex
            self._roles[role] = {
                "name": f"authzest-sim-{self._session}-{role.lower()}-{nonce[:8]}",
                "nonce": nonce,
                "container_id": None,
                "recorded": False,
                "possibly_created": False,
                "ownership_verified": False,
                "attached": False,
                "start_attempted": False,
                "simulated_started": False,
                "last_capture": None,
                "stopped": False,
                "removed": False,
                "cleanup_unconfirmed": False,
                "reconcile_attempted": False,
                "terminate_attempted": False,
                "remove_attempted": False,
            }
        self._busy = True
        try:
            self._tick()
        finally:
            self._busy = False

    def _enter(self) -> None:
        if self._busy:
            raise _error()
        self._busy = True

    def _tick(self) -> float:
        value = self._clock()
        if type(value) is CoroutineType:
            value.close()
            raise _error()
        if (
            type(value) not in (int, float)
            or value < 0
            or value > 2**48
            or not math.isfinite(value)
            or (self._last_time is not None and value < self._last_time)
        ):
            raise _error()
        self._last_time = float(value)
        return float(value)

    def _config(self, role: str) -> dict:
        ledger = self._roles[role]
        small = role == "B"
        return {
            "synthetic_only": True,
            "engine_identity": self._engine,
            "image_id": "sha256:" + identity({"synthetic-image-role": role}),
            "entrypoint_sha256": identity({"synthetic-entrypoint": role}),
            "session_nonce": self._session,
            "role_nonce": ledger["nonce"],
            "owned_name": ledger["name"],
            "role": role,
            "create_stopped": True,
            "running": False,
            "network": "container:" + self._roles["A"]["container_id"]
            if small and self._roles["A"]["container_id"] is not None
            else "none",
            "mounts": []
            if small
            else ["synthetic-app-read-only"]
            + (["synthetic-test-read-only"] if role == "T" else []),
            "environment": [],
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
            "seccomp": "default",
            "pid_namespace": "private",
            "ipc_namespace": "private",
            "cpu": 0.5 if small else 1,
            "memory_mib": 128 if small else 512,
            "swap_mib": 128 if small else 512,
            "pids": 32 if small else 64,
            "tmpfs_mib": 8 if small else 32,
            "shared_memory_mib": 8,
            "ports": [],
            "devices": [],
            "privileged": False,
            "healthcheck": "disabled",
            "anonymous_volumes": [],
            "logging": "none",
            "pull": "never",
        }

    def _begin_cleanup(self, now: float, *, terminal: bool) -> None:
        self._cleanup_mode = True
        self._terminal_cleanup = self._terminal_cleanup or terminal
        if terminal and self._cleanup_deadline is None:
            self._cleanup_deadline = now + 10.0

    def _fail(self, reason: str, now: float) -> None:
        if self._failure is None:
            self._failure = reason
        self._close_readiness(now)
        self._pending = None
        self._begin_cleanup(now, terminal=True)

    def _close_readiness(self, now: float) -> None:
        if self._readiness_started is not None:
            self._readiness_seconds += now - self._readiness_started
            self._readiness_started = None

    def _check_time(self, now: float) -> bool:
        if self._finished:
            return False
        if self._terminal_cleanup and now >= self._cleanup_deadline:
            self._close_readiness(now)
            for ledger in self._roles.values():
                if ledger["possibly_created"] and not ledger["removed"]:
                    ledger["cleanup_unconfirmed"] = True
            self._pending = None
            self._finished = True
            if self._failure is None:
                self._failure = "cleanup-timeout"
            return False
        if not self._terminal_cleanup and self._phase_deadline is not None:
            if now >= self._phase_deadline:
                self._close_readiness(now)
                self._fail("phase-timeout", now)
                return False
            if (
                self._readiness_started is not None
                and self._readiness_seconds + now - self._readiness_started >= 10
            ):
                self._close_readiness(now)
                self._fail("readiness-timeout", now)
                return False
        return True

    def _clock_failure(self) -> None:
        self._clock_bad = self._finished = True
        if self._failure is None:
            self._failure = "clock-invalid"
        self._pending = None
        for ledger in self._roles.values():
            if ledger["possibly_created"] and not ledger["removed"]:
                ledger["cleanup_unconfirmed"] = True

    def _cleanup_step(self) -> tuple[str, str] | None:
        roles = reversed(_ROLES) if self._terminal_cleanup else ("T",)
        for role in roles:
            ledger = self._roles[role]
            if not ledger["possibly_created"] or ledger["removed"]:
                continue
            if ledger["cleanup_unconfirmed"]:
                continue
            if not ledger["ownership_verified"] or ledger["container_id"] is None:
                if not ledger["reconcile_attempted"]:
                    return role, "reconcile"
            elif not ledger["stopped"]:
                if not ledger["terminate_attempted"]:
                    return role, "terminate"
            elif not ledger["remove_attempted"]:
                return role, "remove"
            ledger["cleanup_unconfirmed"] = True
        if not self._terminal_cleanup and self._failure is None:
            self._cleanup_mode = False
            self._role, self._step = "A", "record"
            return self._role, self._step
        self._finished = True
        return None

    def next_intent(self) -> LifecycleIntent | None:
        """Return one synthetic intent; never call a transport or repeat a dispatch."""
        self._enter()
        try:
            if self._finished:
                return None
            if self._pending is not None:
                raise _error()
            try:
                now = self._tick()
            except (Exception, KeyboardInterrupt):
                self._clock_failure()
                return None
            if self._phase_started is None and not self._terminal_cleanup:
                self._phase_started, self._phase_deadline = now, now + 40.0
            self._check_time(now)
            if self._finished:
                return None
            selected = self._cleanup_step() if self._cleanup_mode else (self._role, self._step)
            if selected is None:
                return None
            role, action = selected
            self._count += 1
            if self._count > 40:
                self._clock_failure()
                return None
            ledger = self._roles[role]
            if action == "create":
                ledger["possibly_created"] = True
            elif action == "start":
                ledger["start_attempted"] = True
            elif action in ("reconcile", "terminate", "remove"):
                ledger[action + "_attempted"] = True
            elif action == "record":
                self._readiness_started = now
            config = self._config(role)
            data = {
                "schema_version": "1.0",
                "kind": "generated-repair-synthetic-lifecycle-intent",
                "intent_id": identity({"session": self._session, "sequence": self._count}),
                "action": action,
                "role": role,
                "name": ledger["name"],
                "nonce": ledger["nonce"],
                "container_id": ledger["container_id"],
                "expected_config": config,
                "synthetic_recipe_id": identity(config),
                "preview_bound": False,
            }
            self._pending = LifecycleIntent(_json(data))
            return self._pending
        finally:
            self._busy = False

    def _event(self, event: object, pending: dict) -> dict:
        event = decode(_json(event))
        if type(event) is not dict or set(event) != _FIELDS[pending["action"]] | {"intent_id"}:
            raise _error()
        if event["intent_id"] != pending["intent_id"]:
            raise _error()
        for field in ("ok", "ready", "complete", "oom", "stopped", "removed"):
            if field in event and type(event[field]) is not bool:
                raise _error()
        if "output_bytes" in event and (
            type(event["output_bytes"]) is not int or not 0 <= event["output_bytes"] <= 2**31 - 1
        ):
            raise _error()
        for field, maximum in (("exit_code", 255), ("signal", 127)):
            if (
                field in event
                and event[field] is not None
                and (type(event[field]) is not int or not 0 <= event[field] <= maximum)
            ):
                raise _error()
        if (
            "container_id" in event
            and event["container_id"] is not None
            and (type(event["container_id"]) is not str or not _ID.fullmatch(event["container_id"]))
        ):
            raise _error()
        action = pending["action"]
        if "status" in event:
            choices = (
                {"created", "ambiguous", "failed"}
                if action == "create"
                else {"found", "absent", "failed"}
                if action in ("inspect", "reconcile")
                else {"ok", "ambiguous", "failed"}
            )
            if type(event["status"]) is not str or event["status"] not in choices:
                raise _error()
        if action == "create" and (
            (event["status"] == "created") != (event["container_id"] is not None)
        ):
            raise _error()
        if action in ("inspect", "reconcile"):
            found = event["status"] == "found"
            if found != (event["container_id"] is not None and type(event["config"]) is dict):
                raise _error()
            if not found and (event["container_id"] is not None or event["config"] is not None):
                raise _error()
        return event

    def reply(self, event: dict) -> LifecycleResult:
        """Consume exactly one closed synthetic reply; never import runtime facts."""
        self._enter()
        try:
            if self._pending is None or self._finished:
                raise _error()
            pending = self._pending.to_dict()
            event = self._event(event, pending)
            try:
                now = self._tick()
            except (Exception, KeyboardInterrupt):
                self._clock_failure()
                return self._result()
            if not self._check_time(now):
                return self._result()
            self._pending = None
            role, action = pending["role"], pending["action"]
            self._output_bytes += event.get("output_bytes", 0)
            if self._output_bytes > 262_144:
                self._fail("output-overflow", now)
            self._apply_reply(role, action, event, pending, now)
            return self._result()
        finally:
            self._busy = False

    def _apply_reply(self, role, action, event, pending, now):
        ledger = self._roles[role]
        if action == "record":
            ledger["recorded"] = event["ok"]
            if not event["ok"]:
                self._fail("persistence-failed", now)
            else:
                self._step = "create"
        elif action == "create":
            ledger["container_id"] = event["container_id"]
            if event["status"] != "created":
                # Even a negative CLI reply does not prove no guest was created.
                self._fail("create-" + event["status"], now)
            else:
                self._step = "inspect"
        elif action in ("inspect", "reconcile"):
            owned = (
                event["status"] == "found"
                and _json(event["config"]) == canonical(pending["expected_config"])
                and (
                    ledger["container_id"] is None
                    or event["container_id"] == ledger["container_id"]
                )
                and all(
                    other == role or item["container_id"] != event["container_id"]
                    for other, item in self._roles.items()
                )
            )
            if owned:
                ledger["container_id"] = event["container_id"]
                ledger["ownership_verified"] = True
                if action == "inspect":
                    self._step = "attach"
            elif (
                action == "reconcile"
                and event["status"] == "absent"
                and ledger["container_id"] is None
            ):
                ledger["removed"] = True
            else:
                ledger["cleanup_unconfirmed"] = True
                self._fail("identity-unconfirmed", now)
        elif action in ("attach", "start"):
            if event["status"] != "ok":
                self._fail(action + "-" + event["status"], now)
            else:
                ledger["attached" if action == "attach" else "simulated_started"] = True
                self._step = (
                    "start" if action == "attach" else ("readiness" if role == "A" else "capture")
                )
                if action == "start" and role != "A":
                    self._close_readiness(now)
        elif action == "readiness":
            self._close_readiness(now)
            if not event["ready"]:
                self._fail("readiness-failed", now)
            else:
                self._role, self._step = "B", "record"
        elif action == "capture":
            ledger["last_capture"] = {
                key: event[key]
                for key in ("complete", "exit_code", "signal", "oom", "output_bytes")
            }
            ledger["last_capture"]["trusted"] = False
            reason = (
                "oom"
                if event["oom"]
                else "signal"
                if event["signal"] not in (None, 0)
                else "capture-incomplete"
                if not event["complete"] or event["exit_code"] is None
                else "process-exit"
                if event["exit_code"] not in ((0, 1) if role == "T" else (0,))
                else None
            )
            if reason is not None:
                self._fail(reason, now)
            else:
                self._begin_cleanup(now, terminal=role == "B")
        elif action == "terminate":
            ledger["stopped"] = event["stopped"]
            if not event["stopped"]:
                ledger["cleanup_unconfirmed"] = True
                self._fail("termination-unconfirmed", now)
        elif action == "remove":
            ledger["removed"] = event["removed"]
            if not event["removed"]:
                ledger["cleanup_unconfirmed"] = True
                self._fail("removal-unconfirmed", now)

    def cancel(self) -> LifecycleResult:
        """Latch cancellation and model owned cleanup, without issuing effects."""
        self._enter()
        try:
            if self._finished:
                return self._result()
            try:
                now = self._tick()
            except (Exception, KeyboardInterrupt):
                self._clock_failure()
                return self._result()
            self._check_time(now)
            if not self._finished:
                self._close_readiness(now)
                self._fail("cancelled", now)
            return self._result()
        finally:
            self._busy = False

    def _result(self) -> LifecycleResult:
        outstanding = [
            item
            for item in self._roles.values()
            if item["possibly_created"] and not item["removed"]
        ]
        cleanup = (
            "unconfirmed"
            if any(item["cleanup_unconfirmed"] for item in outstanding)
            else "pending"
            if outstanding
            else "confirmed"
            if any(item["possibly_created"] for item in self._roles.values())
            else "not-required"
        )
        return LifecycleResult(
            canonical(
                {
                    "schema_version": "1.0",
                    "kind": "generated-repair-synthetic-lifecycle-result",
                    "status": "simulation-failed"
                    if self._failure is not None
                    else "simulation-complete"
                    if self._finished
                    else "simulation-in-progress",
                    "failure_reason": self._failure,
                    "cleanup_status": cleanup,
                    "phase_started_at": self._phase_started,
                    "phase_deadline": self._phase_deadline,
                    "cleanup_deadline": self._cleanup_deadline,
                    "readiness_seconds": self._readiness_seconds,
                    "output_bytes": self._output_bytes,
                    "intent_count": self._count,
                    "roles": self._roles,
                    "preview_bound": False,
                    "image_ids": None,
                    "engine_identity": None,
                    "runtime_invoked": False,
                    "execution_status": "not-run",
                    "baseline": "not-established",
                    "authorization_status": "unknown",
                    "execution_authorized": False,
                    "verified_fix": False,
                    "source_application": "not-run",
                    "restoration_status": "not-run",
                    "generated_reports": "untrusted-auxiliary-not-proof",
                }
            )
        )

    def result(self) -> LifecycleResult:
        """Return bounded historical data without polling time or any runtime."""
        self._enter()
        try:
            return self._result()
        finally:
            self._busy = False
