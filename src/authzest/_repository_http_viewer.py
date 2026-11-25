"""Read-only projection of a saved `repo-fix` result for the result viewer.

Imported claims stay unverified. The repair diff is rebuilt here from the
recorded source and model-authored replacement text rather than trusted from
the record, and private paths, account data and raw captures are dropped.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from authzest.codex.contracts import identity
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


def _source(data: dict) -> tuple[dict | None, dict | None, str | None]:
    evidence = _object(data.get("source_evidence"), nullable=True)
    if evidence is None:
        return None, None, None
    source = _captured(evidence.get("source"), limit=16_384)
    policy = _captured(evidence.get("policy"), limit=8_192)
    interface = _text(_object(evidence.get("http_interface")).get("interface_id"), nullable=False)
    return (
        {
            "scenario_id": "external-single-file-http",
            "source": source,
            "declarations": [],
            # The full policy (at most 8 KiB) is shown: the checks are bound to
            # all of it, so no later rule may be hidden from the operator.
            "policy": [line for line in policy["text"].splitlines() if line.strip()],
            "policy_authorship": "user-provided policy file " + policy["path"],
            "policy_review": "unverified intent; expected answers come from the reviewed case file",
        },
        policy,
        interface,
    )


def _basis(
    data: dict, source: dict | None, policy: dict | None, interface: str | None
) -> dict | None:
    """The reviewed case file's basis, bound to the captured inputs when recorded."""
    basis = _object(data.get("case_basis"), nullable=True)
    if basis is None:
        return None
    values = {
        key: _text(basis.get(key), nullable=False)
        for key in ("selection_id", "interface_id", "source_path", "policy_path")
    }
    for key in ("source_sha256", "policy_sha256"):
        values[key] = _hash(basis.get(key), nullable=False)
    if source is not None and policy is not None:
        captured = {
            "interface_id": interface,
            "source_path": source["source"]["path"],
            "source_sha256": source["source"]["sha256"],
            "policy_path": policy["path"],
            "policy_sha256": policy["sha256"],
        }
        if any(values[key] != value for key, value in captured.items()):
            _bad()
    return values


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


def _frame_supports(phase: dict, comparison: dict, case_ids: list[str]) -> bool:
    """The retained runtime frame must back every matching comparison row.

    It belongs to the same phase, plan and binding, confirms A and B cleanup,
    and holds one policy-range HTTP response per reviewed case, in order.
    """
    frame = phase.get("frame")
    if type(frame) is not dict:
        return False
    observations = frame.get("observations")
    if (
        frame.get("phase") != phase.get("phase")
        or frame.get("plan_id") != comparison.get("plan_id")
        or frame.get("binding") != comparison.get("binding")
        or frame.get("cleanup") != {"A": "confirmed", "B": "confirmed"}
        or type(observations) is not list
        or len(observations) != len(case_ids)
    ):
        return False
    for observed, row in zip(observations, comparison["outcomes"], strict=False):
        if type(observed) is not dict or type(row) is not dict:
            return False
        response = observed.get("response")
        status = response.get("status") if type(response) is dict else None
        if (
            observed.get("case_id") != row.get("case_id")
            or observed.get("outcome") != "response"
            or type(status) is not int
            or not (200 <= status < 300 or 400 <= status < 500)
        ):
            return False
    return True


def _producer_success(phase: dict) -> bool:
    """The runner's own success conditions beyond the comparison itself.

    A complete phase has no failure, a complete failure-free relay capture,
    no cleanup errors, confirmed engine transport cleanup and exactly one
    created container per role (A and B), each observed absent afterwards.
    """
    capture = _object(phase.get("relay_capture"), nullable=True)
    owned = phase.get("owned")
    if type(owned) is not list or len(owned) != 2:
        return False
    return (
        phase.get("failure") is None
        and capture is not None
        and capture.get("status") == "complete"
        and capture.get("failure") is None
        and phase.get("relay_capture_failure") is None
        and phase.get("cleanup_errors") == []
        and phase.get("engine_transport_cleanup_confirmed") is True
        and phase.get("stage_initialization_failure") is None
        and phase.get("evidence_persistence_failure") is None
        and phase.get("journal_close_failure") is None
        # Compare without ordering unvalidated values (a missing or non-string
        # role must be refused, not raise).
        and [_object(item).get("role") for item in owned] in (["A", "B"], ["B", "A"])
        and all(
            _object(item).get("create_attempted") is True
            and _object(item).get("absence_observed") is True
            for item in owned
        )
    )


def _phase(
    value: Any,
    candidate: str,
    regression: str | None,
    case_ids: list[str] | None,
    binding: dict[str, str | None],
) -> dict | None:
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
        # Every reviewed case appears exactly once; invented or repeated IDs
        # cannot stand in for the recorded case set.
        ids = [row["case_id"] for row in outcomes]
        if case_ids is None or len(set(ids)) != len(ids) or set(ids) != set(case_ids):
            _bad()
        # The comparison must belong to this phase, case set, interface, PoC
        # and displayed source; a check from other inputs cannot be reused.
        recorded = _object(comparison.get("binding"))
        if (
            comparison.get("phase") != candidate
            or comparison.get("designated_regression_case_id") != regression
            or any(
                expected is not None and recorded.get(key) != expected
                for key, expected in binding.items()
            )
        ):
            _bad()
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
    digest = _hash(phase.get("source_sha256"))
    cleaned = _bool(phase.get("cleanup_confirmed"))
    attempted = _bool(phase.get("runtime_attempted"))
    # A phase may fail before capturing its source hash. Success is recomputed:
    # a started runtime, a valid frame, confirmed cleanup, every reviewed case
    # matching, the hash and, before the repair, the regression answer
    # differing from the desired one.
    if phase.get("criteria_met") is True and (
        status != "complete"
        or projected is None
        or comparison.get("frame_status") != "valid-supplied"
        or comparison.get("cleanup_supplied_confirmed") is not True
        or comparison.get("supplied_criteria_met") is not True
        or projected["matching_case_count"] != planned
        or cleaned is not True
        or attempted is not True
        or not _producer_success(phase)
        or not _frame_supports(phase, comparison, case_ids or [])
        or digest is None
        or (
            candidate == "before"
            and comparison.get("supplied_before_differs_from_desired_after") is not True
        )
    ):
        _bad()
    return {
        "candidate": candidate,
        "status": status,
        "test_exit_code": None,
        "regression_status": regression_status,
        "response_status": None,
        "cleanup_confirmed": cleaned,
        "generated_runtime_attempted": attempted,
        "application_sha256": digest,
        "test_sha256": _hash(phase.get("schedule_sha256")),
        "failure": None
        if failure is None
        else {"stage": candidate, "code": failure, "turn_start": None},
        "transport_failure": None,
        "comparison": projected,
        "case_outcomes": outcomes,
    }


def _step_statuses(private: dict) -> dict[str, str]:
    """Latest recorded outcome of each private file step, failed ones included."""
    history = private.get("history") or []
    if type(history) is not list or len(history) > 16:
        _bad()
    steps: dict[str, str] = {}
    for item in history:
        item = _object(item)
        status = _text(item.get("status"), nullable=False)
        if status not in ("completed", "failed"):
            _bad()
        steps[_text(item.get("step"), nullable=False)] = status
    return steps


def _case_ids(cases: dict, regression: str | None) -> list[str] | None:
    ids = cases.get("case_ids")
    if ids is None:
        return None
    if type(ids) is not list or not 4 <= len(ids) <= 8:
        _bad()
    ids = [_text(item, nullable=False) for item in ids]
    if len(set(ids)) != len(ids) or regression not in ids:
        _bad()
    return ids


def _stages(steps: dict[str, str], before: dict | None, after: dict | None) -> list[dict]:
    # Only the before and after checks start containers; file steps never do.
    runtime = {
        name: None if phase is None else phase["generated_runtime_attempted"]
        for name, phase in (("before", before), ("after", after))
    }
    # A failed file step may already have written files; it stays visible as
    # failed with an unconfirmed effect rather than reading as never run.
    status = {
        "copy": steps.get("copy", "not-run"),
        "before": None if before is None else before["status"],
        "source-diff": steps.get("accept-diff", "not-run"),
        "source-apply": steps.get("apply", "not-run"),
        "after": None if after is None else after["status"],
    }
    return [
        {
            "stage": name,
            "status": status[name] or "not-run",
            "decision": None,
            "expired": None,
            "attempted": runtime.get(name, False),
            "dispatched": None,
            "reason": "effect-unconfirmed"
            if status[name] == "failed" and name not in runtime
            else None,
        }
        for name in _STAGE_NAMES
    ]


def preview_repository_http_fix_result(data: dict) -> dict:
    if data.get("schema_version") != "2.0":
        _bad()
    status = _text(data.get("status"), nullable=False)
    source, policy, interface = _source(data)
    basis = _basis(data, source, policy, interface)
    proposal, assessment = _proposal(data, source)
    cases = _object(data.get("cases"), nullable=True) or {}
    regression = _text(cases.get("regression_case_id"))
    case_ids = _case_ids(cases, regression)
    # Reviewed cases are only accepted against a recorded basis.
    if case_ids is not None and basis is None:
        _bad()
    change = _object(_object(data.get("proposal"), nullable=True) or {}).get("proposal")
    shared = {
        "case_set_id": _text(cases.get("case_set_id")),
        "interface_id": None if basis is None else basis["interface_id"],
        "poc_sha256": None if change is None else identity(_object(change).get("poc")),
    }
    before_source = (
        source["source"]["sha256"]
        if source is not None
        else None
        if basis is None
        else basis["source_sha256"]
    )
    before = _phase(
        data.get("before_phase"),
        "before",
        regression,
        case_ids,
        {**shared, "source_sha256": before_source},
    )
    after = _phase(
        data.get("after_phase"),
        "after",
        regression,
        case_ids,
        {
            **shared,
            "source_sha256": None if proposal is None else proposal["after_source"]["sha256"],
        },
    )
    # Bind each recorded hash to the exact displayed source: before to the
    # captured source (when recorded) and after to the model-authored repair.
    # A phase that failed before its checkpoint has no hash to bind.
    before_sha = None if before is None else before["application_sha256"]
    if before_sha is not None and source is not None and before_sha != source["source"]["sha256"]:
        _bad()
    if after is not None and (
        proposal is None
        or after["application_sha256"] not in (None, proposal["after_source"]["sha256"])
    ):
        _bad()
    verified = _bool(data.get("verified_fix"))
    # A verified repair needs the defect reproduced before and every reviewed
    # case matched after, each with a bound hash and confirmed cleanup.
    if verified is True and not all(
        phase is not None
        and phase["comparison"] is not None
        and phase["comparison"]["matches_expected_profile"] is True
        for phase in (before, after)
    ):
        _bad()
    original = _object(data.get("original"), nullable=True) or {}
    original_state = _text(original.get("state"))
    modified = _bool(data.get("original_checkout_modified"))
    if status == "original-applied" and (original_state != "applied" or modified is not True):
        _bad()
    private = _object(data.get("private_copy"), nullable=True) or {}
    steps = _step_statuses(private)
    recovery = (
        original_state == "recovery-required"
        or status == "original-recovery-required"
        or private.get("state") == "recovery-required"
    )
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
            if steps.get("apply") == "completed"
            else "copy-apply-unconfirmed"
            if steps.get("apply") == "failed"
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
            "stages": _stages(steps, before, after),
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
