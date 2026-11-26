"""The bundled external examples stay consistent with their reviewed case files."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from authzest.analyzer.repository_origin import capture_repository_origin
from authzest.codex.repository_http_proposal import build_repository_http_request
from authzest.runner._repository_http_staging import supported
from authzest.runner.repository_http_cases import build_repository_http_cases
from authzest.runner.repository_http_fix import case_basis

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
APPS = ("external_notes_app", "external_orders_app")


def _cases(name: str) -> dict:
    return json.loads((EXAMPLES / name / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not supported(), reason="POSIX external repair flow scope")
@pytest.mark.parametrize("name", APPS)
def test_case_basis_matches_the_shipped_app_and_policy(name):
    origin = capture_repository_origin(EXAMPLES / name, "app.py", "policy.txt")
    try:
        request = build_repository_http_request(origin.snapshot, "offline-example-check")
    finally:
        origin.close()
    cases = build_repository_http_cases(_cases(name))
    assert cases.to_dict()["basis"] == case_basis(request)


@pytest.mark.parametrize("name", APPS)
def test_before_answers_describe_the_shipped_app(name):
    testclient = pytest.importorskip("fastapi.testclient")
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / name / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = testclient.TestClient(module.app)
    for case in _cases(name)["cases"]:
        request, before = case["request"], case["before"]
        response = client.get(request["path"], headers=request["headers"])
        assert response.status_code == before["status"], case["id"]
        assert response.json() == before["body"]["value"], case["id"]
