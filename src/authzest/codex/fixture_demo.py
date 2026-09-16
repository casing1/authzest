"""Package an offline, caller-authored proposal using only maintained fixture constants."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ValidatedResponse,
    prepare_request,
    validate_response,
)
from authzest.codex.fixture_draft import FIXTURE_AFTER, FIXTURE_SOURCE
from authzest.codex.mock import scripted_response
from authzest.codex.proposals import ValidatedProposal, prepare_proposal
from authzest.runner import ScanRunner


def build_demo_proposal() -> tuple[CodexAnalysisRequest, ValidatedResponse, ValidatedProposal]:
    """Parse packaged source as data and bind mock identities, never provider identities.

    No repository checkout, installed test fixture, provider, target import or generated
    command is needed. The short-lived directory contains only the maintained constant;
    its path is excluded from the prepared evidence and deterministic request identity.
    """
    with TemporaryDirectory(prefix="authzest-demo-source-") as directory:
        root = Path(directory)
        (root / "main.py").write_text(FIXTURE_SOURCE, encoding="utf-8", newline="")
        report = ScanRunner().run(root)
        request = prepare_request(
            report,
            registration_ids=tuple(
                route.to_dict(report.root)["registration_id"] for route in report.routes
            ),
            sources={"main.py": FIXTURE_SOURCE},
            policies=("Deployment configuration should explicitly disable framework debug mode.",),
            questions=(
                ("review", "Review the declared debug configuration in this owned fixture."),
            ),
        )
    review = validate_response(
        scripted_response(
            request,
            {"review": "Consider explicitly disabling debug mode; runtime behavior is unverified."},
        ),
        request,
    )
    proposal = prepare_proposal(
        request,
        review,
        replacements={"main.py": FIXTURE_AFTER},
        rationale="Caller-authored mock draft: explicitly disable framework debug mode.",
        uncertainties=("This is not a runtime authorization check or a verified fix.",),
        side_effects=("Framework debug diagnostics would no longer be enabled by this setting.",),
        checks=("fixture-static-inventory", "fixture-regression-tests"),
        expectations=("Preserve route inventory and review the changed debug setting.",),
    )
    return request, review, proposal
