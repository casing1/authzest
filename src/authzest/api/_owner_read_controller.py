"""One owned local UI job, using the core workflow's existing plan/read boundary."""

from __future__ import annotations

import asyncio
import inspect
import json
import math
import secrets
import threading
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

from authzest.codex.contracts import AdapterConfig, ContractError, canonical, identity
from authzest.result_viewer import preview_workflow_result

MAX_PLAN_BYTES = 2 * 1024**2
MAX_RESULT_BYTES = 4 * 1024**2
MAX_EVENTS = 256
_STAGES = {"runtime", "share", "copy", "before", "diff", "apply", "after", "restore", "workflow"}
_CODES = {
    "invalid-model",
    "invalid-timeout",
    "controller-closed",
    "run-active",
    "run-not-found",
    "prompt-unavailable",
    "prompt-stale",
    "prompt-expired",
    "invalid-answer",
    "result-unavailable",
    "plan-invalid",
    "plan-too-large",
    "result-invalid",
    "result-too-large",
    "event-limit",
    "clock-unavailable",
    "workflow-failed",
    "workflow-interrupted",
    "worker-start-failed",
}


class UIWorkflowError(RuntimeError):
    """Fixed diagnostics without workflow, source, account or filesystem text."""

    def __init__(self, code: str, status_code: int):
        self.code = code if code in _CODES else "workflow-failed"
        self.status_code = (
            status_code if type(status_code) is int and 400 <= status_code <= 599 else 500
        )
        super().__init__(self.code)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON member")
        result[key] = value
    return result


def _constant(_):
    raise ValueError("Nonfinite JSON number")


def _decode(raw: str, *, maximum: int, code: str):
    try:
        if type(raw) is not str or len(raw.encode("utf-8")) > maximum:
            raise UIWorkflowError(code, 422)
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        if type(value) is not dict:
            raise ValueError
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 64 or count > 65_536:
                raise ValueError
            if type(item) is dict:
                pending.extend((key, depth + 1) for key in item)
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
            elif type(item) is str:
                item.encode("utf-8")
            elif type(item) is float and not math.isfinite(item):
                raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise UIWorkflowError(code, 422) from None


@dataclass(frozen=True)
class _Plan:
    stage: str
    raw: str
    expected: str
    emitted_at: float
    lifetime: float


@dataclass
class _Prompt:
    prompt_id: str
    text: str
    plan: _Plan
    deadline: float
    answer: str | None = None


@dataclass
class _Run:
    run_id: str
    model: str
    timeout: float
    revision: int = 0
    state: str = "running"
    events: list[dict] = field(default_factory=list)
    latest: _Plan | None = None
    pending: _Prompt | None = None
    result: bytes | None = None
    view_raw: str | None = None
    view_error: str | None = None
    failure: str | None = None
    cancel_requested: bool = False
    cancel_signal_sent: bool = False
    thread: threading.Thread | None = None
    loop: asyncio.AbstractEventLoop | None = None
    task: asyncio.Task | None = None


class OwnerReadUIController:
    """Keep one active lease until its non-daemon worker actually exits.

    Runtime configuration is fixed by the trusted launcher. Constructing this
    object performs no configuration read or provider/runtime operation. A test
    workflow injection is trusted host code and is never an API request field.
    """

    def __init__(
        self, runtime_config: Path, *, workflow=None, clock=monotonic, decision_seconds=300
    ):
        if (
            not callable(clock)
            or type(decision_seconds) not in (int, float)
            or not 0 < decision_seconds <= 300
        ):
            raise ValueError("Invalid UI controller timing")
        if workflow is not None and not callable(workflow):
            raise ValueError("Expected a callable workflow")
        self._runtime_config = Path(runtime_config)
        self._workflow = workflow
        self._clock = clock
        self._decision_seconds = float(decision_seconds)
        self._last_time = 0.0
        self._condition = threading.Condition(threading.RLock())
        self._run: _Run | None = None
        self._closed = False

    def _now(self):
        try:
            value = self._clock()
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value < self._last_time
            ):
                raise ValueError
            self._last_time = float(value)
            return self._last_time
        except Exception:
            raise UIWorkflowError("clock-unavailable", 500) from None

    def _event(self, run, stage, status, *, terminal=False):
        if len(run.events) >= MAX_EVENTS:
            if not terminal:
                raise UIWorkflowError("event-limit", 409)
        else:
            run.events.append({"sequence": len(run.events) + 1, "stage": stage, "status": status})
        run.revision += 1
        self._condition.notify_all()

    def _owned(self, run_id):
        if self._run is None or self._run.run_id != run_id:
            raise UIWorkflowError("run-not-found", 404)
        return self._run

    def _stop(self, run, *, failure=None):
        if (
            run.cancel_requested
            and run.pending is None
            and (failure is None or failure == run.failure)
        ):
            return
        if failure is not None:
            run.failure = failure
        run.cancel_requested = True
        run.state = "stopping"
        stage = run.pending.plan.stage if run.pending is not None else "workflow"
        if run.pending is not None:
            run.pending.answer = "cancel"
            run.pending = None
        run.latest = None
        self._event(
            run,
            stage,
            "expired" if failure == "prompt-expired" else "stop-requested",
            terminal=True,
        )

    def _expire(self, run):
        if run.pending is None:
            return
        try:
            expired = self._now() >= run.pending.deadline
        except UIWorkflowError:
            self._stop(run, failure="clock-unavailable")
            return
        if expired:
            self._stop(run, failure="prompt-expired")

    def _snapshot(self, run):
        self._expire(run)
        prompt = run.pending
        return {
            "run_id": run.run_id,
            "revision": run.revision,
            "state": run.state,
            "events": [dict(item) for item in run.events],
            "pending": {
                "prompt_id": prompt.prompt_id,
                "stage": prompt.plan.stage,
                "prompt": prompt.text,
                "plan": json.loads(prompt.plan.raw),
                "remaining_seconds": min(
                    prompt.plan.lifetime, max(0.0, prompt.deadline - self._last_time)
                ),
            }
            if prompt is not None
            else None,
            "view": json.loads(run.view_raw) if run.view_raw is not None else None,
            "view_error": run.view_error,
            "result_available": run.result is not None,
            "failure": run.failure,
            "cancel_requested": run.cancel_requested,
        }

    def start(self, model, timeout_seconds=120):
        try:
            AdapterConfig(model=model, temperature=None)
        except (ContractError, TypeError):
            raise UIWorkflowError("invalid-model", 422) from None
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 120
        ):
            raise UIWorkflowError("invalid-timeout", 422)
        with self._condition:
            if self._closed:
                raise UIWorkflowError("controller-closed", 503)
            if (
                self._run is not None
                and self._run.thread is not None
                and self._run.thread.is_alive()
            ):
                raise UIWorkflowError("run-active", 409)
            run = _Run(secrets.token_hex(16), model, float(timeout_seconds))
            run.thread = threading.Thread(
                target=self._worker, args=(run,), daemon=False, name="authzest-owner-read-ui"
            )
            self._run = run
            self._event(run, "workflow", "started")
            try:
                run.thread.start()
            except RuntimeError:
                run.state, run.failure = "failed", "worker-start-failed"
                self._event(run, "workflow", "failed", terminal=True)
                raise UIWorkflowError("worker-start-failed", 500) from None
            return self._snapshot(run)

    def current(self):
        with self._condition:
            return self._snapshot(self._run) if self._run is not None else None

    def snapshot(self, run_id):
        with self._condition:
            return self._snapshot(self._owned(run_id))

    def decide(self, run_id, prompt_id, answer):
        if type(answer) is not str or len(answer) > 256:
            raise UIWorkflowError("invalid-answer", 422)
        cancel = False
        with self._condition:
            if self._closed:
                raise UIWorkflowError("controller-closed", 503)
            run = self._owned(run_id)
            self._expire(run)
            prompt = run.pending
            if prompt is None or prompt.prompt_id != prompt_id:
                raise UIWorkflowError("prompt-stale", 409)
            if answer not in (prompt.plan.expected, "", "cancel"):
                raise UIWorkflowError("invalid-answer", 422)
            if answer == "cancel":
                self._stop(run)
                cancel = True
            else:
                self._event(run, prompt.plan.stage, "approved" if answer else "declined")
                prompt.answer = answer
                run.pending, run.latest = None, None
                run.state = "running"
            result = self._snapshot(run)
        if cancel:
            self._cancel_task(run)
        return result

    def cancel(self, run_id):
        with self._condition:
            run = self._owned(run_id)
            if (
                run.thread is not None
                and run.thread.is_alive()
                and run.state not in ("finished", "failed")
            ):
                self._stop(run)
            result = self._snapshot(run)
        self._cancel_task(run)
        return result

    def _cancel_task(self, run):
        with self._condition:
            loop, task = run.loop, run.task
            if run.cancel_signal_sent or loop is None or task is None:
                return
            run.cancel_signal_sent = True
        with suppress(RuntimeError):
            loop.call_soon_threadsafe(task.cancel)

    def download(self, run_id):
        with self._condition:
            run = self._owned(run_id)
            if run.result is None:
                raise UIWorkflowError("result-unavailable", 409)
            return run.result

    def close(self, timeout_seconds=60):
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 <= timeout_seconds <= 60
        ):
            raise UIWorkflowError("invalid-timeout", 422)
        with self._condition:
            self._closed = True
            run = self._run
            if run is None or run.thread is None or not run.thread.is_alive():
                return True
            if run.state not in ("finished", "failed"):
                self._stop(run)
            worker = run.thread
        self._cancel_task(run)
        if worker is threading.current_thread():
            return False
        worker.join(timeout_seconds)
        return not worker.is_alive()

    def _emit(self, run, raw):
        try:
            if type(raw) is not str or len(raw.encode("utf-8")) > MAX_PLAN_BYTES:
                raise UIWorkflowError("plan-too-large", 422)
            value = _decode(raw, maximum=MAX_PLAN_BYTES, code="plan-invalid")
            kind = value.get("kind")
            if (
                kind in ("owner-read-runtime-review", "owner-read-file-stage-plan")
                and value.get("schema_version") != "1.0"
            ):
                raise UIWorkflowError("plan-invalid", 422)
            if kind == "owner-read-runtime-review":
                stage, key, prefix = "runtime", "runtime_review_id", "owner-read-runtime-"
            elif kind == "owner-read-sharing-preview":
                stage, key, prefix = "share", "sharing_id", "share-"
            elif (
                kind == "owner-read-file-stage-plan"
                and type(value.get("stage")) is str
                and value.get("stage")
                in _STAGES
                - {
                    "runtime",
                    "share",
                    "workflow",
                }
            ):
                stage, key, prefix = value["stage"], "plan_id", "owner-read-stage-"
            else:
                raise UIWorkflowError("plan-invalid", 422)
            identifier = value.get(key)
            fields = {name: item for name, item in value.items() if name != key}
            if type(identifier) is not str or identifier != prefix + identity(fields):
                raise UIWorkflowError("plan-invalid", 422)
            lifetime = value.get("decision_expires_after_seconds", 300)
            if (
                type(lifetime) not in (int, float)
                or not math.isfinite(lifetime)
                or not 0 < lifetime <= 300
            ):
                raise UIWorkflowError("plan-invalid", 422)
            with self._condition:
                if self._run is not run or run.pending is not None:
                    raise UIWorkflowError("prompt-unavailable", 409)
                run.latest = _Plan(
                    stage,
                    raw,
                    stage + " " + identifier,
                    self._now(),
                    min(float(lifetime), self._decision_seconds),
                )
                self._event(run, stage, "plan-ready")
        except (UIWorkflowError, ContractError, UnicodeError) as exc:
            error = exc if type(exc) is UIWorkflowError else UIWorkflowError("plan-invalid", 422)
            with self._condition:
                if self._run is run:
                    self._stop(run, failure=error.code)
            raise error from None

    def _read(self, run, text):
        with self._condition:
            if run.cancel_requested:
                return "cancel"
            plan = run.latest
            if (
                self._run is not run
                or plan is None
                or run.pending is not None
                or type(text) is not str
                or len(text) > 2048
                or not text.startswith("Type '" + plan.expected + "' ")
            ):
                self._stop(run, failure="plan-invalid")
                raise UIWorkflowError("plan-invalid", 422)
            deadline = plan.emitted_at + plan.lifetime
            if deadline - plan.emitted_at > plan.lifetime:
                deadline = math.nextafter(deadline, -math.inf)
            if not math.isfinite(deadline) or deadline <= plan.emitted_at:
                self._stop(run, failure="clock-unavailable")
                raise UIWorkflowError("clock-unavailable", 500)
            prompt = _Prompt(secrets.token_hex(16), text, plan, deadline)
            run.pending, run.state = prompt, "waiting"
            self._event(run, plan.stage, "waiting")
            while prompt.answer is None:
                self._expire(run)
                if prompt.answer is not None:
                    break
                self._condition.wait(min(0.1, max(0.0, prompt.deadline - self._last_time)))
            return prompt.answer

    async def _drive(self, run):
        with self._condition:
            run.loop, run.task = asyncio.get_running_loop(), asyncio.current_task()
            if run.cancel_requested and not run.cancel_signal_sent:
                run.cancel_signal_sent = True
                run.loop.call_soon(run.task.cancel)
        try:
            workflow = self._workflow
            if workflow is None:
                from authzest.runner.owner_read_suggestion import run_suggestion

                workflow = run_suggestion
            result = workflow(
                run.model,
                timeout_seconds=run.timeout,
                file_workflow=True,
                runtime_config=self._runtime_config,
                emit=lambda raw: self._emit(run, raw),
                read=lambda text: self._read(run, text),
            )
            if not inspect.isawaitable(result):
                raise UIWorkflowError("result-invalid", 500)
            return await result
        finally:
            with self._condition:
                run.loop, run.task = None, None

    def _worker(self, run):
        failure = None
        try:
            value = asyncio.run(self._drive(run))
            if type(value) is not dict:
                raise UIWorkflowError("result-invalid", 500)
            try:
                raw = canonical(value)
            except (ContractError, UnicodeError):
                raise UIWorkflowError("result-invalid", 500) from None
            if len(raw.encode("utf-8")) > MAX_RESULT_BYTES:
                raise UIWorkflowError("result-too-large", 500)
            _decode(raw, maximum=MAX_RESULT_BYTES, code="result-invalid")
            try:
                view_raw = canonical(preview_workflow_result(raw.encode("utf-8")))
                view_error = None
            except Exception:
                view_raw, view_error = None, "result-view-unavailable"
            with self._condition:
                run.result, run.view_raw, run.view_error = raw.encode("utf-8"), view_raw, view_error
                run.state = "finished"
                self._event(run, "workflow", "returned", terminal=True)
        except BaseException as exc:
            failure = (
                exc.code
                if type(exc) is UIWorkflowError
                else "workflow-interrupted"
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError))
                else "workflow-failed"
            )
        finally:
            if failure is not None:
                with self._condition:
                    run.failure, run.state = failure, "failed"
                    if run.pending is not None:
                        run.pending.answer = "cancel"
                    run.pending, run.latest = None, None
                    self._event(run, "workflow", "failed", terminal=True)
