"""Preview a caller-authored defensive draft and simulated decision without applying it."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from authzest.codex.contracts import prepare_request, validate_response
from authzest.codex.mock import scripted_response
from authzest.codex.proposals import prepare_proposal, proposal_preview
from authzest.runner import ScanRunner
from authzest.runner.approval import assess_decision, record_decision

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "tests/fixtures/proposal_demo"


def build_demo_proposal():
    """Read the maintained source-only fixture and package its fixed, caller-authored draft."""
    source = (FIXTURE_ROOT / "main.py").read_text(encoding="utf-8")
    report = ScanRunner().run(FIXTURE_ROOT)
    request = prepare_request(
        report,
        registration_ids=tuple(
            route.to_dict(report.root)["registration_id"] for route in report.routes
        ),
        sources={"main.py": source},
        policies=("Deployment configuration should explicitly disable framework debug mode.",),
        questions=(("review", "Review the declared debug configuration in this owned fixture."),),
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
        replacements={"main.py": source.replace("debug=True", "debug=False", 1)},
        rationale="Caller-authored mock draft: explicitly disable framework debug mode.",
        uncertainties=("This is not a runtime authorization check or a verified fix.",),
        side_effects=("Framework debug diagnostics would no longer be enabled by this setting.",),
        checks=("fixture-static-inventory", "fixture-regression-tests"),
        expectations=("Preserve route inventory and review the changed debug setting.",),
    )
    return request, review, proposal


def run_demo(decision: str = "decline", scenario: str = "current") -> dict:
    if decision not in ("approve", "decline", "cancel"):
        raise ValueError("Unsupported demonstration decision")
    if scenario not in ("current", "stale-source", "expired"):
        raise ValueError("Unsupported demonstration scenario")
    request, review, proposal = build_demo_proposal()
    source = next(
        item["data"]["text"] for item in request.to_dict()["evidence"] if item["kind"] == "source"
    )
    # Relative demonstration times and a simulated choice, not a real user's consent receipt.
    recorded = record_decision(proposal, request, review, decision, now=0, valid_for_seconds=300)
    current = {"main.py": source + "# later local edit\n" if scenario == "stale-source" else source}
    assessment = assess_decision(
        proposal,
        request,
        review,
        recorded,
        current_sources=current,
        now=300 if scenario == "expired" else 1,
    )
    return {
        "kind": "offline-proposal-demo",
        "live_provider_calls": 0,
        "simulated_decision": True,
        "scenario": scenario,
        "proposal": proposal_preview(proposal, request, review),
        "decision": recorded.to_dict(),
        "assessment": asdict(assessment),
        "limitations": [
            "No AI-generated patch, file application or verification execution.",
            "The decision is simulated, not signed or one-use authorization.",
            "Filesystem/symlink checks and atomic application remain future work.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", choices=("approve", "decline", "cancel"), default="decline")
    parser.add_argument(
        "--scenario", choices=("current", "stale-source", "expired"), default="current"
    )
    args = parser.parse_args()
    # Escape control/non-ASCII characters instead of rendering untrusted terminal instructions.
    print(json.dumps(run_demo(args.decision, args.scenario), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
