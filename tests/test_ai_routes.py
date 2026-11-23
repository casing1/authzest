"""Privileged local transport tests with inert controllers and diagnostic replies."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from authzest.api.app import create_app

ORIGIN = "http://127.0.0.1:8769"
TOKEN = "t" * 43
RUN = "a" * 32
AUTH = {"X-AuthZest-Token": TOKEN, "Origin": ORIGIN}


class Controller:
    def __init__(self):
        self.calls = []
        self.closed = 0
        self.value = {
            "run_id": RUN,
            "revision": 1,
            "state": "waiting",
            "events": [],
            "pending": None,
            "view": None,
            "view_error": None,
            "result_available": False,
            "failure": None,
            "cancel_requested": False,
        }

    def current(self):
        self.calls.append("current")
        return self.value

    def start(self, model, *, timeout_seconds):
        self.calls.append(("start", model, timeout_seconds))
        return self.value

    def snapshot(self, run_id):
        self.calls.append(("snapshot", run_id))
        return self.value

    def decide(self, *args):
        self.calls.append(("decide", *args))
        return self.value

    def cancel(self, run_id):
        self.calls.append(("cancel", run_id))
        return self.value

    def download(self, run_id):
        self.calls.append(("download", run_id))
        return b'{"synthetic":"inert result"}'

    def close(self):
        self.closed += 1
        return True


def app(controller, *, diagnostics=None):
    return create_app(
        ai_controller=controller,
        ai_origin=ORIGIN,
        ai_token=TOKEN,
        ai_diagnostics=diagnostics,
    )


def request(application, method="GET", path="/api/ai/session", *, headers=None, **kwargs):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url=ORIGIN
        ) as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


def test_default_asgi_application_has_no_active_route():
    assert request(create_app()).status_code == 404
    assert request(create_app(), "POST", "/api/ai/runs", json={"model": "x"}).status_code == 404


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({}, 401),
        ({"X-AuthZest-Token": "wrong"}, 401),
        ({**AUTH, "Host": "attacker.example"}, 403),
        ({**AUTH, "Host": "127.0.0.1:8770"}, 403),
        ({**AUTH, "Host": "localhost:8769"}, 403),
        ({**AUTH, "Origin": "https://attacker.example"}, 403),
        ({**AUTH, "Origin": "null"}, 403),
        ({**AUTH, "Origin": ORIGIN + "/"}, 403),
        ({**AUTH, "Sec-Fetch-Site": "cross-site"}, 403),
        ({**AUTH, "Sec-Fetch-Site": "same-site"}, 403),
        ([("X-AuthZest-Token", TOKEN), ("X-AuthZest-Token", TOKEN)], 401),
        ([("X-AuthZest-Token", TOKEN), ("Host", "127.0.0.1:8769"), ("Host", "evil")], 403),
        ([("X-AuthZest-Token", TOKEN), ("Origin", ORIGIN), ("Origin", ORIGIN)], 403),
    ],
)
def test_privileged_get_rejects_untrusted_headers_before_controller(headers, code):
    controller = Controller()
    response = request(app(controller), headers=headers)
    assert response.status_code == code
    assert controller.calls == []
    assert TOKEN not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_same_origin_get_may_omit_origin_but_requires_capability():
    controller = Controller()
    response = request(app(controller), headers={"X-AuthZest-Token": TOKEN})
    assert response.status_code == 200
    assert response.json() == {"run": controller.value}
    assert controller.calls == ["current"]
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in response.headers
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("headers", [{"X-AuthZest-Token": TOKEN}, {**AUTH, "Origin": "null"}])
def test_mutation_requires_exact_origin(headers):
    controller = Controller()
    response = request(
        app(controller), "POST", "/api/ai/runs", headers=headers, json={"model": "x"}
    )
    assert response.status_code == 403 and not controller.calls


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", ""])
def test_form_and_plain_text_cannot_start_a_job(content_type):
    controller = Controller()
    response = request(
        app(controller),
        "POST",
        "/api/ai/runs",
        headers={**AUTH, "content-type": content_type},
        content='{"model":"x"}',
    )
    assert response.status_code == 415 and not controller.calls


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"model": True},
        {"model": "x", "timeout_seconds": True},
        {"model": "x", "timeout_seconds": 0},
        {"model": "x", "timeout_seconds": 121},
        {"model": "x", "timeout_seconds": 10**300},
        {"model": "x", "runtime_config": "/PRIVATE-DO-NOT-READ"},
        {"model": "x", "source": "arbitrary source"},
        {"model": "x", "command": "arbitrary command"},
        {"model": "x", "path": "/PRIVATE-DO-NOT-READ"},
        {"model": "x", "proposal": {}},
        {"model": "x\nprivate"},
    ],
)
def test_start_rejects_unregistered_options_and_invalid_scalars(body):
    controller = Controller()
    response = request(app(controller), "POST", "/api/ai/runs", headers=AUTH, json=body)
    assert response.status_code == 400 and not controller.calls
    assert "PRIVATE-DO-NOT" not in response.text


@pytest.mark.parametrize("raw", [b'{"model":"x","model":"y"}', b'{"model":NaN}', b'{"x":'])
def test_duplicate_and_malformed_json_are_redacted(raw):
    controller = Controller()
    response = request(
        app(controller),
        "POST",
        "/api/ai/runs",
        headers={**AUTH, "content-type": "application/json"},
        content=raw,
    )
    assert response.status_code == 400 and not controller.calls


def test_stream_limit_ignores_forged_content_length():
    async def chunks():
        for _ in range(5):
            yield b" " * 1024

    controller = Controller()
    response = request(
        app(controller),
        "POST",
        "/api/ai/runs",
        headers={**AUTH, "content-type": "application/json", "content-length": "1"},
        content=chunks(),
    )
    assert response.status_code == 413 and not controller.calls


def test_exact_model_and_current_decision_are_forwarded_without_autoapproval():
    controller = Controller()
    application = app(controller)
    response = request(
        application, "POST", "/api/ai/runs", headers=AUTH, json={"model": "exact-model"}
    )
    assert response.status_code == 202
    assert controller.calls == [("start", "exact-model", 120)]
    response = request(
        application,
        "POST",
        f"/api/ai/runs/{RUN}/decisions",
        headers=AUTH,
        json={"prompt_id": "current-prompt", "answer": "before current-plan"},
    )
    assert response.status_code == 202
    assert controller.calls[-1] == ("decide", RUN, "current-prompt", "before current-plan")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"prompt_id": "p", "answer": True},
        {"prompt_id": "p", "answer": "", "expected": "injected"},
        {"prompt_id": "p", "answer": "a" * 257},
        {"prompt_id": "p", "answer": "\ud800"},
    ],
)
def test_decision_transport_rejects_malformed_or_injected_input(body):
    controller = Controller()
    response = request(
        app(controller),
        "POST",
        f"/api/ai/runs/{RUN}/decisions",
        headers={**AUTH, "content-type": "application/json"},
        content=json.dumps(body).encode(),
    )
    assert response.status_code == 400 and not controller.calls


def test_cancel_is_explicit_and_accepts_no_saved_plan():
    controller = Controller()
    application = app(controller)
    url = f"/api/ai/runs/{RUN}/cancel"
    assert (
        request(application, "POST", url, headers=AUTH, json={"restore": True}).status_code == 400
    )
    assert not controller.calls
    assert request(application, "POST", url, headers=AUTH, json={}).status_code == 202
    assert controller.calls == [("cancel", RUN)]


def test_download_uses_capability_and_server_derived_filename():
    controller = Controller()
    url = f"/api/ai/runs/{RUN}/result"
    application = app(controller)
    assert request(application, path=url).status_code == 401
    response = request(application, path=url, headers=AUTH)
    assert response.status_code == 200 and response.json() == {"synthetic": "inert result"}
    assert response.headers["content-disposition"] == (
        f'attachment; filename="authzest-owner-read-{RUN}.json"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert TOKEN not in response.text + response.headers["content-disposition"]


def test_diagnostics_return_only_coarse_status():
    controller = Controller()
    calls = []

    def diagnose():
        calls.append(True)
        return {
            "codex_status": "authenticated",
            "version_status": "supported",
            "model_access": "not-checked",
            "raw": "PRIVATE-DO-NOT-DISPLAY-ACCOUNT",
        }

    application = app(controller, diagnostics=diagnose)
    assert request(application, "POST", "/api/ai/diagnostics", json={}).status_code == 401
    assert not calls
    response = request(application, "POST", "/api/ai/diagnostics", headers=AUTH, json={})
    assert response.json() == {
        "codex_status": "authenticated",
        "version_status": "supported",
        "model_access": "not-checked",
    }
    assert calls == [True] and "PRIVATE-DO-NOT" not in response.text


def test_diagnostic_exception_does_not_disclose_host_details():
    def diagnose():
        raise OSError("PRIVATE-DO-NOT-DISPLAY")

    response = request(
        app(Controller(), diagnostics=diagnose),
        "POST",
        "/api/ai/diagnostics",
        headers=AUTH,
        json={},
    )
    assert response.status_code == 503 and "PRIVATE-DO-NOT" not in response.text


@pytest.mark.parametrize(
    "origin",
    [
        "http://0.0.0.0:8000",
        "http://localhost:8000",
        ORIGIN + "/",
        "https://127.0.0.1:8000",
        "http://127.0.0.1:0",
    ],
)
def test_active_transport_requires_an_exact_loopback_origin(origin):
    with pytest.raises(ValueError):
        create_app(ai_controller=Controller(), ai_origin=origin, ai_token=TOKEN)


def test_lifespan_closes_owned_controller():
    controller = Controller()
    application = app(controller)

    async def run():
        async with application.router.lifespan_context(application):
            assert controller.closed == 0

    asyncio.run(run())
    assert controller.closed == 1
