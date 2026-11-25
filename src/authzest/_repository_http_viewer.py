"""Read-only projection of a saved `repo-fix` result for the result viewer.

Imported claims stay unverified. The repair diff is rebuilt here from the
recorded source and model-authored replacement text rather than trusted from
the record, and private paths, account data and raw captures are dropped.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from authzest.result_viewer import (
    _bad,
    _bool,
    _diff,
    _explanation,
    _hash,
    _integer,
    _object,
    _strings,
    _text,
)

_OUTCOMES = {"match", "mismatch", "error", "not-dispatched", "invalid"}
_STAGE_NAMES = ("copy", "before", "source-diff", "source-apply", "after")


def _captured(value: Any, *, limit: int) -> dict:
    value = _object(value)
    text = _text(value.get("text"), limit=limit, nullable=False)
    digest = _hash(value.get("sha256"), nullable=False)
    if sha256(text.encode("utf-8")).hexdigest() != digest:
        _bad()
    return {"path": _text(value.get("path"), nullable=False), "sha256": digest, "text": text}


def _source(data: dict) -> tuple[dict | None, dict | None]:
    evidence = _object(data.get("source_evidence"), nullable=True)
    if evidence is None:
        return None, None
    source = _captured(evidence.get("source"), limit=16_384)
    policy = _captured(evidence.get("policy"), limit=8_192)
    return (
        {
            "scenario_id": "external-single-file-http",
            "source": source,
            "declarations": [],
            "policy": [line for line in policy["text"].splitlines() if line.strip()][:32],
            "policy_authorship": "user-provided policy file " + policy["path"],
            "policy_review": "unverified intent; expected answers come from the reviewed case file",
        },
        policy,
    )


def _proposal(data: dict, source: dict | None) -> tuple[dict | None, dict | None]:
    response = _object(data.get("proposal"), nullable=True)
    if response is None:
        return None, None
    status = _text(response.get("status"), nullable=False)
    assessment = {
        "status": status,
        "rationale": _explanation(response.get("rationale")),
        "assumptions": _strings(response.get("assumptions")),
        "uncertainties": _strings(response.get("uncertainties") or []),
        "limitations": _strings(response.get("limitations")),
    }
    change = _object(response.get("proposal"), nullable=True)
    if change is None:
        return None, assessment
    after = _text(change.get("after_text"), limit=16_384, nullable=False)
    path = _text(change.get("source_path"), nullable=False)
    poc = _object(change.get("poc"))
    headers = poc.get("headers")
    if type(headers) is not list or len(headers) > 3:
        _bad()
    poc_text = " ".join(
        [_text(poc.get("method"), nullable=False), _text(poc.get("path"), nullable=False)]
        + [
            _text(_object(item).get("name"), nullable=False)
            + ": "
            + _text(_object(item).get("value"), nullable=False)
            for item in headers
        ]
    )
    after_sha = sha256(after.encode("utf-8")).hexdigest()
    changes = []
    if source is not None:
        if (
            source["source"]["path"] != path
            or change.get("before_sha256") != source["source"]["sha256"]
        ):
            _bad()
        changes.append(
            {
                "path": path,
                "before_sha256": source["source"]["sha256"],
                "after_sha256": after_sha,
                "diff": _diff(source["source"]["text"], after, path),
            }
        )
    return (
        {
            **{key: assessment[key] for key in ("rationale", "assumptions", "uncertainties")},
            "limitations": assessment["limitations"],
            "after_source": {"path": path, "sha256": after_sha, "text": after},
            "test": {"path": "HTTP PoC request (data, not code)", "sha256": None, "text": poc_text},
            "changes": changes,
        },
        assessment,
    )


def _phase(value: Any, candidate: str, regression: str | None) -> dict | None:
    phase = _object(value, nullable=True)
    if phase is None:
        return None
    if phase.get("phase") not in (None, candidate):
        _bad()
    comparison = _object(phase.get("comparison"), nullable=True)
    outcomes, regression_status = [], None
    projected = None
    if comparison is not None:
        rows = comparison.get("outcomes")
        if type(rows) is not list or len(rows) > 8:
            _bad()
        for row in rows:
            row = _object(row)
            outcome = _text(row.get("outcome"), nullable=False)
            if outcome not in _OUTCOMES:
                _bad()
            case_id = _text(row.get("case_id"), nullable=False)
            outcomes.append(
                {"case_id": case_id, "outcome": outcome, "reason": _text(row.get("reason"))}
            )
            if case_id == regression:
                regression_status = outcome
        counts = _object(comparison.get("counts"))
        planned = _integer(comparison.get("planned_cases"), nullable=False)
        # Recount from the validated rows; a supplied count can never override them.
        matching = sum(row["outcome"] == "match" for row in outcomes)
        if planned != len(outcomes) or _integer(counts.get("match"), nullable=False) != matching:
            _bad()
        projected = {
            "expected_profile": "reviewed-" + candidate + "-answers",
            "comparison_status": _text(comparison.get("frame_status")),
            "matches_expected_profile": _bool(phase.get("criteria_met")),
            "case_count": planned,
            "matching_case_count": matching,
            "intended_match_count": None,
            "request_count": planned,
            "matching_request_count": matching,
        }
    failure = _text(phase.get("failure"))
    status = _text(phase.get("status"))
    if phase.get("criteria_met") is True and (
        status != "complete" or projected is None or projected["matching_case_count"] != planned
    ):
        _bad()
    return {
        "candidate": candidate,
        "status": status,
        "test_exit_code": None,
        "regression_status": regression_status,
        "response_status": None,
        "cleanup_confirmed": _bool(phase.get("cleanup_confirmed")),
        "generated_runtime_attempted": _bool(phase.get("runtime_attempted")),
        "application_sha256": _hash(phase.get("source_sha256")),
        "test_sha256": _hash(phase.get("schedule_sha256")),
        "failure": None
        if failure is None
        else {"stage": candidate, "code": failure, "turn_start": None},
        "transport_failure": None,
        "comparison": projected,
        "case_outcomes": outcomes,
    }


def _stages(data: dict, before: dict | None, after: dict | None) -> list[dict]:
    private = _object(data.get("private_copy"), nullable=True) or {}
    history = private.get("history") or []
    if type(history) is not list or len(history) > 16:
        _bad()
    done = {
        _text(_object(item).get("step"))
        for item in history
        if _object(item).get("status") == "completed"
    }
    status = {
        "copy": "completed" if "copy" in done else "not-run",
        "before": None if before is None else before["status"],
        "source-diff": "completed" if "accept-diff" in done else "not-run",
        "source-apply": "completed" if "apply" in done else "not-run",
        "after": None if after is None else after["status"],
    }
    return [
        {
            "stage": name,
            "status": status[name] or "not-run",
            "decision": None,
            "expired": None,
            "attempted": status[name] not in (None, "not-run"),
            "dispatched": None,
            "reason": None,
        }
        for name in _STAGE_NAMES
    ]


def preview_repository_http_fix_result(data: dict) -> dict:
    if data.get("schema_version") != "2.0":
        _bad()
    status = _text(data.get("status"), nullable=False)
    source, _policy = _source(data)
    proposal, assessment = _proposal(data, source)
    cases = _object(data.get("cases"), nullable=True) or {}
    regression = _text(cases.get("regression_case_id"))
    before = _phase(data.get("before_phase"), "before", regression)
    after = _phase(data.get("after_phase"), "after", regression)
    # Bind each check to the exact displayed source: before to the captured
    # source (when recorded) and after to the model-authored replacement.
    if (
        before is not None
        and source is not None
        and before["application_sha256"] != source["source"]["sha256"]
    ):
        _bad()
    if after is not None and (
        proposal is None or after["application_sha256"] != proposal["after_source"]["sha256"]
    ):
        _bad()
    verified = _bool(data.get("verified_fix"))
    if verified is True and (
        after is None
        or after["comparison"] is None
        or not (after["comparison"]["matches_expected_profile"])
    ):
        _bad()
    original = _object(data.get("original"), nullable=True) or {}
    original_state = _text(original.get("state"))
    modified = _bool(data.get("original_checkout_modified"))
    if status == "original-applied" and (original_state != "applied" or modified is not True):
        _bad()
    recovery = original_state == "recovery-required" or status == "original-recovery-required"
    private = _object(data.get("private_copy"), nullable=True) or {}
    warnings = [
        "Imported claims are unverified. Display validation is not execution, "
        "approval or a security verdict.",
        "Matching observations cover only the reviewed cases, not the whole application.",
        "Private paths, account data, runtime metadata and raw captures are omitted.",
    ]
    if source is None:
        warnings.append(
            "Original source evidence is absent; the source diff cannot be independently rebuilt."
        )
    failure = data.get("failure")
    return {
        "schema_version": "1.0",
        "kind": "authzest-workflow-view",
        "record_kind": "repository-http-fix-result",
        "record_version": "1.0",
        "provenance": "imported-unverified",
        "summary": {
            "status": status,
            "exit_code": _integer(data.get("exit_code")),
            "proposal_status": _text(data.get("proposal_status")),
            "execution_status": "before-and-after-checked"
            if before is not None and after is not None
            else "before-checked"
            if before is not None
            else "not-run",
            "patch_application": "applied-to-original"
            if original_state in ("applied", "restored")
            else "applied-to-copy"
            if after is not None
            else "not-run",
            "applied": modified,
            "current_copy_state": _text(private.get("state")),
            "restoration_status": original_state or "not-run",
            "original_checkout_modified": modified,
            "recovery_required": recovery,
        },
        "source_evidence": source,
        "assessment": assessment,
        "proposal": proposal,
        "session": {
            "status": status,
            "stopped_stage": None,
            "closed": None,
            "close_status": None,
            "runtime_input_cleanup": None,
            "cleanup_unconfirmed": None
            if before is None
            else not all(phase["cleanup_confirmed"] is True for phase in (before, after) if phase),
            "clock_unconfirmed": None,
            "workspace_state": _text(private.get("state")),
            "stages": _stages(data, before, after),
            "checks": {"before": before, "after": after},
            "authorization_status": "reviewed-cases-matched" if verified else "unknown",
            "verified_fix": verified,
            "isolation_established": None,
            "resource_enforcement_established": None,
            "test_report_authenticity": "not-applicable-http-data",
            "recovery_required": recovery,
        },
        "failure": None
        if failure is None
        else {
            "stage": None,
            "code": _text(_object(failure).get("code")),
            "turn_start": None,
        },
        "availability": {
            "before_source": source is not None,
            "declarations": False,
            "raw_phase_captures": False,
        },
        "warnings": warnings,
    }
