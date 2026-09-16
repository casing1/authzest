"""Export an owned, caller-authored preview bundle; no live provider or target execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from authzest.codex.contracts import validate_response
from authzest.codex.expectations import prepare_expectation_manifest
from authzest.codex.mock import scripted_response
from authzest.codex.preview import prepare_preview_bundle
from authzest.codex.proposals import prepare_proposal
from scripts.evaluate_offline import prepare_case


def build_demo_bundle():
    """Only the existing public development fixture is read, never imported as code."""
    case = {
        "id": "public",
        "policies": ["The /health route is intentionally public."],
        "questions": [
            {"id": "policy", "text": "Review public intent; runtime behavior is unknown."}
        ],
    }
    _, request = prepare_case(case, "evidence-plus-model")
    review = validate_response(scripted_response(request, {"policy": None}), request)
    evidence = {item["kind"]: item for item in request.to_dict()["evidence"]}
    source = evidence["source"]["data"]
    proposal = prepare_proposal(
        request,
        review,
        replacements={
            source["path"]: source["text"]
            + "# Caller-authored preview example; no behavior change.\n"
        },
        rationale="Caller-authored comment-only demonstration, not a generated security fix.",
        uncertainties=("Runtime authorization and policy enforcement have not been checked.",),
        side_effects=("Adds a source comment; the proposal is not applied.",),
        checks=("fixture-static-inventory",),
        expectations=(
            "Review the caller's public policy intent separately from runtime behavior.",
        ),
    )
    manifest = prepare_expectation_manifest(
        request,
        review,
        proposal,
        expectations=[
            {
                "id": "public-intent",
                "source_evidence_id": evidence["source"]["id"],
                "route_evidence_id": evidence["route"]["id"],
                "policy_evidence_ids": [evidence["policy"]["id"]],
                "observation": "policy-intent",
                "expected": {"intent": "public"},
                "limitations": ["Caller-authored policy interpretation; enforcement is unknown."],
            }
        ],
    )
    return prepare_preview_bundle(request, review, proposal, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Create a new bundle file; refuse an existing path."
    )
    args = parser.parse_args()
    payload = json.dumps(
        build_demo_bundle().to_dict(), ensure_ascii=True, separators=(",", ":"), allow_nan=False
    )
    if args.output is None:
        print(payload)
        return
    try:
        with args.output.open("x", encoding="utf-8", newline="") as stream:
            stream.write(payload)
    except OSError:
        parser.error("Cannot create the output bundle; choose a new writable file path.")


if __name__ == "__main__":
    main()
