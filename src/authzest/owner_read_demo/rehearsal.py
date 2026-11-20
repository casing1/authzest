"""Run the fixed packaged sample and collect independent in-process FastAPI responses."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from .app import _app_with_rule, create_app, current_principal
from .checks import owner_read_controls

_SAMPLE = Path(__file__).resolve().with_name("positive_regression.py")
_SAMPLE_SHA256 = "92e382cadcb9584b7e953b90955a0f0fee8f4cb16b89f649b1ca26fe807b57a4"
_ITEM = "test_owner_can_read_archived_note"
_ARCHIVED_PATH = "/records/archived-note"


def _reference_rule(state: str) -> bool:
    return state in ("active", "archived")


async def _get(app: FastAPI, principal: str | None, path: str) -> httpx.Response:
    if principal is not None:
        app.dependency_overrides[current_principal] = lambda: principal
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture.invalid", trust_env=False
    ) as client:
        return await client.get(path)


def _observation(response: httpx.Response) -> dict:
    return {"status_code": response.status_code, "body": response.json()}


class _OwnerClient:
    def __init__(self, app: FastAPI):
        self.app = app
        self.requests = 0
        self.response = None

    def get(self, path: str) -> httpx.Response:
        self.requests += 1
        if path != _ARCHIVED_PATH or self.requests != 1:
            raise ValueError("The sample expects one owner read of the archived note")
        response = asyncio.run(_get(self.app, "owner", path))
        self.response = _observation(response)
        return response


class _PytestObservation:
    def __init__(self, app: FastAPI, *, captured_test=None):
        self.client = _OwnerClient(app)
        self.captured_test = captured_test
        self.collected = 0
        self.nodeid = None
        self.stages: list[tuple[str, str]] = []
        self.sample_assertion = False

    @pytest.fixture
    def owner_client(self):
        return self.client

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)
        if self.collected == 1:
            item = session.items[0]
            expected_name = self.captured_test.__name__ if self.captured_test else _ITEM
            if (
                item.path.resolve() == _SAMPLE
                and item.name == expected_name
                and (self.captured_test is None or item.obj is self.captured_test)
            ):
                self.nodeid = item.nodeid

    def pytest_runtest_makereport(self, item, call):
        if item.nodeid != self.nodeid or call.when != "call" or call.excinfo is None:
            return
        exc = call.excinfo.value
        if type(exc) is AssertionError:
            tb = exc.__traceback__
            if tb is not None:
                while tb.tb_next is not None:
                    tb = tb.tb_next
                code = tb.tb_frame.f_code
                if self.captured_test is None:
                    self.sample_assertion = (
                        code.co_name == _ITEM and Path(code.co_filename).resolve() == _SAMPLE
                    )
                else:
                    self.sample_assertion = code is self.captured_test.__code__

    def pytest_runtest_logreport(self, report):
        if report.nodeid == self.nodeid:
            self.stages.append((report.when, report.outcome))

    def result(self, exit_code: int) -> dict:
        stages = dict(self.stages)
        call = stages.get("call")
        status = "error"
        if (
            self.nodeid is not None
            and self.collected == 1
            and self.stages == [("setup", "passed"), ("call", call), ("teardown", "passed")]
            and self.client.requests == 1
            and self.client.response is not None
        ):
            if exit_code == 0 and call == "passed":
                status = "passed"
            elif exit_code == 1 and call == "failed" and self.sample_assertion:
                status = "assertion-failed"
        return {
            "status": status,
            "pytest_exit": exit_code,
            "collected": self.collected,
            "setup": stages.get("setup"),
            "call": call,
            "teardown": stages.get("teardown"),
            "requests": self.client.requests,
            "response": self.client.response,
        }


def _record_pytest(recorder: _PytestObservation, *, plugins=()) -> dict:
    with _SAMPLE.open("rb") as stream:
        if hashlib.sha256(stream.read(4097)).hexdigest() != _SAMPLE_SHA256:
            raise ValueError("The packaged rehearsal sample changed")
    # The host starts a fresh worker. Disable ambient pytest options for this sample.
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ.pop("PYTEST_PLUGINS", None)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    args = [
        "-c",
        os.devnull,
        "--rootdir",
        str(_SAMPLE.parent),
        "--noconftest",
        "--assert=plain",
        "--import-mode=importlib",
        "-p",
        "no:cacheprovider",
        "-p",
        "no:terminal",
        str(_SAMPLE),
    ]
    # The worker's stdout is reserved for its single JSON response.
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        exit_code = pytest.main(args, plugins=[recorder, *plugins])
    return recorder.result(int(exit_code))


def _phase_app(phase: str) -> FastAPI:
    if phase == "baseline":
        return create_app()
    if phase == "reference":
        return _app_with_rule(_reference_rule)
    raise ValueError("Unknown rehearsal phase")


def run_phase(phase: str) -> dict:
    """Called inside a fresh worker. Only the two checked-in phases are available."""
    if not __debug__:
        raise ValueError("The rehearsal requires active Python assertions")

    regression = _record_pytest(_PytestObservation(_phase_app(phase)))
    observations = _collect_controls(lambda: _phase_app(phase))
    return {"phase": phase, "regression": regression, "observations": observations}


def _collect_controls(make_app: Callable[[], FastAPI]) -> list[dict]:
    observations = []
    for case in owner_read_controls():
        response = asyncio.run(_get(make_app(), case["principal"], "/records/" + case["record_id"]))
        observations.append({"case_id": case["case_id"], **_observation(response)})
    return observations
