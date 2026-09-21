"""Build one owned, caller-authored review bundle entirely from source constants.

The source is parsed as data. No temporary directory, target import, provider or
execution is used, and the example explicitly omits authentication implementation.
"""

from __future__ import annotations

from pathlib import Path

from authzest.codex.contracts import ContractError, prepare_request, validate_response
from authzest.codex.expectations import prepare_expectation_manifest
from authzest.codex.mock import scripted_response
from authzest.codex.preview import ValidatedPreviewBundle, prepare_preview_bundle
from authzest.codex.proposals import prepare_proposal
from authzest.models import ScanReport
from authzest.parser.fastapi import FastAPIRouteParser

REVIEW_DEMO_CASE_ID = "scope-declaration-review"
REVIEW_DEMO_PATH = "main.py"
REVIEW_DEMO_SOURCE = (
    '"""Owned source-only review example; never import or execute this module."""\n'
    "\n"
    "from fastapi import FastAPI, Security\n"
    "\n"
    "app = FastAPI()\n"
    "\n"
    "\n"
    "def require_reports_access():\n"
    '    raise RuntimeError("Source-only example; not authentication implementation")\n'
    "\n"
    "\n"
    '@app.get("/reports", dependencies=[Security(require_reports_access, scopes=[])])\n'
    "def reports():\n"
    '    return {"example": "source-only"}\n'
)
REVIEW_DEMO_AFTER = REVIEW_DEMO_SOURCE.replace("scopes=[]", 'scopes=["reports:read"]', 1)


def build_review_demo_bundle() -> ValidatedPreviewBundle:
    """Return a deterministic mock bundle; every Path here is a logical source label."""
    root = Path("review-demo-source")
    parsed = FastAPIRouteParser().parse_source(REVIEW_DEMO_SOURCE, root / REVIEW_DEMO_PATH)
    if parsed.error or parsed.diagnostics or len(parsed.routes) != 1:
        raise ContractError("Maintained review example is outside its expected source subset")
    report = ScanReport(root=root, python_files=1, routes=parsed.routes)
    request = prepare_request(
        report,
        registration_ids=(parsed.routes[0].to_dict(root)["registration_id"],),
        sources={REVIEW_DEMO_PATH: REVIEW_DEMO_SOURCE},
        policies=(
            "Reports are intended to require reports:read. A declared scope is not enforcement; "
            "authentication and authorization are not implemented by this source-only example.",
        ),
        questions=(
            ("review", "Review declared scopes; runtime and policy enforcement are unknown."),
        ),
    )
    review = validate_response(
        scripted_response(
            request,
            {
                "review": "The scope list is empty. Adding an explicit reports:read declaration "
                "would not implement authentication or prove authorization enforcement."
            },
        ),
        request,
    )
    proposal = prepare_proposal(
        request,
        review,
        replacements={REVIEW_DEMO_PATH: REVIEW_DEMO_AFTER},
        rationale="Caller-authored mock proposal: make the intended scope declaration explicit.",
        uncertainties=(
            "This source-only example has no authentication or authorization implementation.",
            "Matching declarations cannot establish a verified security fix or runtime behavior.",
        ),
        side_effects=(
            "Changes only the declared scope list; the dependency remains unimplemented.",
        ),
        checks=("fixture-static-inventory", "fixture-regression-tests"),
        expectations=(
            "Retain one dependency declaration and declare reports:read explicitly.",
            "Keep policy enforcement and runtime outcomes unknown.",
        ),
    )
    evidence = {item["kind"]: item for item in request.to_dict()["evidence"]}
    shared = {
        "source_evidence_id": evidence["source"]["id"],
        "route_evidence_id": evidence["route"]["id"],
        "policy_evidence_ids": [evidence["policy"]["id"]],
    }
    manifest = prepare_expectation_manifest(
        request,
        review,
        proposal,
        expectations=[
            {
                **shared,
                "id": "dependency-count",
                "observation": "dependency-declarations",
                "expected": {"count": 1},
                "limitations": ["A dependency declaration does not establish access control."],
            },
            {
                **shared,
                "id": "declared-scopes",
                "observation": "scope-declarations",
                "expected": {"scopes": ["reports:read"]},
                "limitations": [
                    "Scope declarations do not establish scope validation or enforcement."
                ],
            },
            {
                **shared,
                "id": "restricted-intent",
                "observation": "policy-intent",
                "expected": {"intent": "restricted"},
                "limitations": [
                    "Caller-authored intent; the source does not implement this policy."
                ],
            },
        ],
    )
    return prepare_preview_bundle(request, review, proposal, manifest)
