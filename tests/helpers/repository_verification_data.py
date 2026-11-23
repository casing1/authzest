"""Owned inert declarations and deliberately supplied frames, never live evidence."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from authzest.analyzer.repository_input import CapturedFile, RepositoryInput
from authzest.codex.contracts import identity
from authzest.codex.repository_proposal import TEST_PATH, build_repository_request
from authzest.codex.repository_test_interface import build_repository_test_request
from authzest.runner.repository_cases import build_repository_cases
from authzest.runner.repository_verification import build_repository_verification_plan

SOURCE = (
    "from fastapi import FastAPI, Header, HTTPException\napp = FastAPI()\n"
    '@app.get("/items/{item_id}")\n'
    "def read(item_id: str, x_user: str | None = Header(default=None)):\n"
    "    if x_user is None:\n        raise HTTPException(status_code=401)\n"
    '    return {"id": item_id}\n'
    '@app.get("/health")\ndef health():\n    return {"ok": True}\n'
    'raise RuntimeError("OWNED INERT SOURCE MUST NEVER EXECUTE")\n'
)
AFTER = SOURCE.replace(
    '    return {"id": item_id}',
    '    if x_user != "test-owner":\n        raise HTTPException(status_code=403)\n'
    '    return {"id": item_id}',
)
TEST = 'raise RuntimeError("OWNED INERT TEST MUST NEVER EXECUTE")\n'
POLICY = "Only test-owner owns these synthetic items; /health is explicitly public.\n"


def response_value(status, value):
    return {"status": status, "body": {"kind": "json", "value": value}}


def case_data(request):
    data = request.to_dict()
    source, policy = data["selection"]["files"][:2]
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
        "schema_version": "1.0",
        "kind": "repository-independent-cases",
        "basis": {
            "selection_id": identity(data["selection"]),
            "interface_id": data["test_interface"]["interface_id"],
            "source_path": source["path"],
            "source_sha256": source["sha256"],
            "policy_path": policy["path"],
            "policy_sha256": policy["sha256"],
        },
        "authorship": "Assistant-authored owned synthetic test data; no maintainer review.",
        "assumptions": ["HOST_ONLY_EXPECTATION: supplied labels are not runtime truth."],
        "regression_case_id": "other",
        "regression_reason": "Declared non-owner denial differs from the supplied before result.",
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
    captured = tuple(
        CapturedFile(name, text, sha256(text.encode()).hexdigest())
        for name, text in (("app.py", SOURCE), ("policy.md", POLICY))
    )
    base = build_repository_request(
        RepositoryInput(Path("/unused/inert/origin"), "app.py", "policy.md", (), captured), model
    )
    request = build_repository_test_request(
        base, entry_source="app.py", app_attribute=app_attribute
    )
    response = {
        "schema_version": "1.1",
        "request_id": request.request_id,
        "status": "proposed-change",
        "rationale": "An owned inert proposal for pure contract tests only.",
        "assumptions": ["Synthetic source and policy; no runtime check."],
        "uncertainties": ["Nothing was executed or authenticated."],
        "limitations": ["No correctness or authorization assurance."],
        "proposal": {
            "source_path": "app.py",
            "before_sha256": captured[0].sha256,
            "after_text": AFTER,
            "test_path": TEST_PATH,
            "test_text": TEST,
        },
    }
    return request, response, build_repository_cases(case_data(request))


def plan_inputs():
    request, response, cases = inputs()
    plan = build_repository_verification_plan(request, response, cases)
    return plan, request, response, cases


def phase_frame(plan, phase):
    data = plan.to_dict()
    return {
        "schema_version": "1.0",
        "kind": "repository-supplied-phase",
        "plan_id": plan.plan_id,
        "phase": phase,
        "binding": {
            "source_sha256": data["source"][phase + "_sha256"],
            "test_sha256": data["test"]["sha256"],
            "interface_id": data["test_interface"]["interface_id"],
        },
        "observations": [
            {
                "case_id": c["id"],
                "outcome": "response",
                "response": deepcopy(c[phase]),
                "error_code": None,
            }
            for c in data["case_set"]["cases"]
        ],
        "pytest": {
            "collected": 1,
            "passed": 0 if phase == "before" else 1,
            "failed": 1 if phase == "before" else 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "exit_code": 1 if phase == "before" else 0,
            "failure_kind": "assertion" if phase == "before" else "none",
        },
        "cleanup": {"T": "confirmed", "A": "confirmed", "B": "confirmed"},
    }
