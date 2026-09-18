"""Offline orchestration of artifact validation and pure source declaration comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from authzest.analyzer.declarations import DeclarationTarget, compare_declarations
from authzest.codex.contracts import identity
from authzest.codex.preview import ValidatedPreviewBundle, validate_preview_bundle
from authzest.runner.proposal_preview import PreviewInputError, load_preview_bundle

COMPARISON_SCHEMA_VERSION = "1.0"


def _unavailable(observation: str, reason: str) -> dict[str, Any]:
    policy = observation == "policy-intent"
    return {
        "status": "not-evaluated" if policy else "unknown",
        "reason": "policy-intent-not-checkable" if policy else reason,
        "before_observed": None,
        "observed": None,
        "after_registration_id": None,
    }


def check_proposal(bundle: ValidatedPreviewBundle) -> dict[str, Any]:
    """Compare supplied snapshots only; no filesystem, execution or provider access.

    The wrapper is revalidated, not trusted. A completed result means processing
    completed, never approval, current-source freshness or authorization enforcement.
    """
    bundle = validate_preview_bundle(bundle.payload_json)
    payload = bundle.to_dict()
    request = payload["request"]
    manifest = payload["manifest"]
    evidence = {item["id"]: item for item in request["evidence"]}
    sources = [item["data"] for item in evidence.values() if item["kind"] == "source"]
    limits = [item["data"] for item in evidence.values() if item["kind"] == "limitations"]
    changes = payload["proposal"]["changes"]
    expectations = manifest["expectations"]
    unavailable = None
    if len(sources) != 1 or len(changes) != 1:
        unavailable = "unsupported-source-scope"
    elif len(limits) != 1:
        unavailable = "baseline-analysis-unavailable"
    elif (
        limits[0]["analysis_status"] != "bounded"
        or limits[0]["diagnostic_codes"]
        or limits[0]["parse_error_count"] != 0
    ):
        unavailable = "baseline-analysis-partial"
    if unavailable is not None:
        comparisons = [_unavailable(item["observation"], unavailable) for item in expectations]
    else:
        comparisons = compare_declarations(
            path=sources[0]["path"],
            before_text=sources[0]["text"],
            after_text=changes[0]["after_text"],
            targets=[
                DeclarationTarget(
                    baseline=evidence[item["route_evidence_id"]]["data"],
                    observation=item["observation"],
                    expected=item["expected"],
                )
                for item in expectations
            ],
        )
    results = [
        {**item, **comparison} for item, comparison in zip(expectations, comparisons, strict=True)
    ]
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "kind": "source-declaration-comparison",
        "status": "completed",
        "scope": "source-declarations",
        "bundle_id": bundle.bundle_id,
        "request_id": manifest["request_id"],
        "proposal_id": manifest["proposal_id"],
        "manifest_id": "expectation-" + identity(manifest),
        "applied": False,
        "verification_status": "not-run",
        "runtime_verification_status": "not-run",
        "authorization_verdict": "unknown",
        "live_provider_calls": 0,
        "results": results,
        "summary": {
            status: sum(item["status"] == status for item in results)
            for status in ("matched", "mismatched", "unknown", "not-evaluated")
        },
        "limitations": [
            "Compares supplied source declarations only, not current filesystem or Git state.",
            "Dependency counts and declared scopes do not establish authorization enforcement.",
            "Policy intent is caller interpretation and is never evaluated by this checker.",
            "Unsupported, ambiguous or partial source forms remain unknown.",
            "No provider call, source execution, patch application or runtime verification occurs.",
            "Completed processing and exit code zero do not mean expectations or security passed.",
            "This result grants no sharing, application, verification or restoration approval.",
        ],
    }


def load_check(path: Path) -> dict[str, Any]:
    """Read only the selected bounded bundle file; embedded paths are labels."""
    try:
        bundle = load_preview_bundle(path)
    except PreviewInputError:
        raise PreviewInputError(
            "Cannot check: expected a stable regular UTF-8 bundle of at most 262144 bytes "
            "with valid, matching artifacts on a supported POSIX system"
        ) from None
    return check_proposal(bundle)
