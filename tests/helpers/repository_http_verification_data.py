"""Owned inert HTTP declarations and supplied frames, never live runtime evidence."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from authzest.analyzer.repository_input import CapturedFile, RepositoryInput
from authzest.codex.contracts import identity
from authzest.codex.repository_http_proposal import build_repository_http_request
from authzest.runner.repository_http_cases import build_repository_http_cases
from authzest.runner.repository_http_verification import build_repository_http_verification_plan

SOURCE = (
    "from fastapi import FastAPI, Header, HTTPException\napp = FastAPI()\n"
    '@app.get("/items/{item_id}")\n'
    "def read(item_id: str, x_user: str | None = Header(default=None)):\n"
    "    if x_user is None:\n        raise HTTPException(status_code=401)\n"
    '    return {"id": item_id}\n'
    '@app.get("/health")\ndef health():\n    return {"ok": True}\n'
    'raise RuntimeError("OWNED INERT HTTP SOURCE MUST NEVER EXECUTE")\n'
)
AFTER = SOURCE.replace(
    '    return {"id": item_id}',
    '    if x_user != "test-owner":\n        raise HTTPException(status_code=403)\n'
    '    return {"id": item_id}',
)
POLICY = "Only test-owner owns the synthetic items; /health is explicitly public.\n"


def response_value(status, value):
    return {"status": status, "body": {"kind": "json", "value": value}}


def case_data(request):
    data = request.to_dict()
    source, policy = data["selection"]["files"]
    rows = [
        ("owner", "/items/one", {"x-user": "test-owner"}, 200, {"id": "one"}),
        ("other", "/items/one", {"x-user": "test-other"}, 200, {"id": "one"}),
        ("anonymous", "/items/one", {}, 401, {"detail": "Unauthorized"}),
        ("normal", "/items/two", {"x-user": "test-owner"}, 200, {"id": "two"}),
        ("public", "/health", {}, 200, {"ok": True}),
    ]
    cases = [
        {
            "id": name,
            "request": {"method": "GET", "path": path, "headers": headers},
            "before": response_value(status, value),
            "after": response_value(status, deepcopy(value)),
        }
        for name, path, headers, status, value in rows
    ]
    cases[1]["after"] = response_value(403, {"detail": "Forbidden"})
    return {
        "schema_version": "2.0",
        "kind": "repository-http-independent-cases",
        "basis": {
            "selection_id": identity(data["selection"]),
            "interface_id": data["http_interface"]["interface_id"],
            "source_path": source["path"],
            "source_sha256": source["sha256"],
            "policy_path": policy["path"],
            "policy_sha256": policy["sha256"],
        },
        "authorship": "Assistant-authored owned inert data; not reviewed by the maintainer.",
        "assumptions": ["HOST_ONLY_EXPECTATION: supplied labels are not runtime truth."],
        "regression_case_id": "other",
        "regression_reason": "Declared non-owner denial differs from the supplied before value.",
        "coverage": {
            role: {"case_ids": [name], "not_applicable_reason": None}
            for role, name in [
                ("owner", "owner"),
                ("non-owner", "other"),
                ("anonymous", "anonymous"),
                ("normal-use", "normal"),
                ("public", "public"),
            ]
        },
        "cases": cases,
    }


def inputs(*, model="offline-model", app_attribute="app"):
    files = tuple(
        CapturedFile(name, text, sha256(text.encode()).hexdigest())
        for name, text in (("app.py", SOURCE), ("policy.md", POLICY))
    )
    request = build_repository_http_request(
        RepositoryInput(Path("/unused/owned/inert-project"), "app.py", "policy.md", (), files),
        model,
        app_attribute=app_attribute,
    )
    response = {
        "schema_version": "2.0",
        "kind": "repository-http-proposal",
        "request_id": request.request_id,
        "status": "proposed-change",
        "rationale": "Owned inert proposal data only, not an observed security result.",
        "assumptions": ["Synthetic source and identity setup require independent review."],
        "uncertainties": ["No app, HTTP request or proposed code was executed."],
        "limitations": ["No authentication assurance or verified repair."],
        "proposal": {
            "source_path": "app.py",
            "before_sha256": files[0].sha256,
            "after_text": AFTER,
            "poc": {
                "method": "GET",
                "path": "/items/one",
                "headers": [{"name": "x-user", "value": "test-other"}],
            },
        },
    }
    return request, response, build_repository_http_cases(case_data(request))


def plan_inputs():
    request, response, cases = inputs()
    plan = build_repository_http_verification_plan(request, response, cases)
    return plan, request, response, cases


def phase_frame(plan, phase):
    data = plan.to_dict()
    return {
        "schema_version": "2.0",
        "kind": "repository-http-supplied-phase",
        "plan_id": plan.plan_id,
        "phase": phase,
        "binding": {
            "source_sha256": data["source"][phase + "_sha256"],
            "interface_id": data["http_interface"]["interface_id"],
            "case_set_id": data["case_set_id"],
            "poc_sha256": data["poc_sha256"],
        },
        "observations": [
            {
                "case_id": case["id"],
                "outcome": "response",
                "response": deepcopy(case[phase]),
                "error_code": None,
            }
            for case in data["case_set"]["cases"]
        ],
        "cleanup": {"A": "confirmed", "B": "confirmed"},
    }
