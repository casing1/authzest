"""Read-only display projection for the fixed archived-owner result contract.

All inputs are imported claims. The projection checks their internal consistency
and exposes a small display surface without following paths or importing any
application, test, dispatcher or model adapter.
"""

from __future__ import annotations

from hashlib import sha256

from authzest.codex.contracts import canonical
from authzest.owner_read_demo.checks import compare_owner_read_observations, owner_read_controls
from authzest.result_viewer import (
    _bad,
    _bool,
    _diff,
    _explanation,
    _failure,
    _hash,
    _integer,
    _object,
    _source,
    _text,
)

_SOURCE_PATH = "src/authzest/owner_read_demo/availability.py"
_TEST_PATH = "tests/test_owner_archived_read.py"
_STAGES = ("copy", "before", "diff", "apply", "after", "restore")
_SUCCESS = dict(
    zip(_STAGES, ("prepared", "matched", "accepted", "applied", "matched", "restored"), strict=True)
)
_LABELS = {"diff": "source-diff", "apply": "source-apply"}


def _digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _code(value):
    value = _text(value, limit=4096, nullable=False)
    if not value or not value.isascii() or any(ord(char) < 32 and char != "\n" for char in value):
        _bad()
    return value


def _owner_source(data):
    value = _source(data.get("source_evidence"))
    if value is not None and (value["source"]["path"] != _SOURCE_PATH or value["declarations"]):
        _bad()
    if value is not None:
        _code(value["source"]["text"])
    return value


def _proposal(data, source):
    value = _object(data.get("proposal"), nullable=True)
    changes = data.get("diffs", [])
    if type(changes) is not list:
        _bad()
    if value is None:
        if changes:
            _bad()
        return None, None
    status = _text(value.get("status"), nullable=False)
    if status not in ("proposed-change", "no-change", "unknown", "refused"):
        _bad()
    if (
        data.get("status") in ("proposed-change", "no-change", "unknown", "refused")
        and data["status"] != status
    ):
        _bad()
    request_id = _hash(data.get("request_id"), nullable=False)
    if value.get("request_id") != request_id:
        _bad()
    assessment = {
        "status": status,
        "rationale": _explanation(value.get("rationale")),
        "assumptions": [],
        "uncertainties": [],
        "limitations": [],
    }
    if status != "proposed-change":
        if value.get("source") is not None or value.get("test") is not None or changes:
            _bad()
        return None, assessment
    after, test = _code(value.get("source")), _code(value.get("test"))
    if len(changes) != 2:
        _bad()
    normalized = []
    for index, (path, text) in enumerate(((_SOURCE_PATH, after), (_TEST_PATH, test))):
        change = _object(changes[index])
        before_hash = _hash(change.get("before_sha256"), nullable=index == 1)
        if (
            change.get("path") != path
            or change.get("after_sha256") != _digest(text)
            or index == 1
            and before_hash is not None
        ):
            _bad()
        normalized.append(
            {
                "path": path,
                "before_sha256": before_hash,
                "after_sha256": _digest(text),
                "diff": _text(change.get("diff"), limit=65_536, nullable=False),
            }
        )
    if normalized[1]["diff"] != _diff("", test, _TEST_PATH, new=True):
        _bad()
    if source is not None:
        before = source["source"]
        if before["sha256"] != normalized[0]["before_sha256"] or normalized[0]["diff"] != _diff(
            before["text"], after, _SOURCE_PATH
        ):
            _bad()
    return {
        **{key: child for key, child in assessment.items() if key != "status"},
        "after_source": {"path": _SOURCE_PATH, "sha256": _digest(after), "text": after},
        "test": {"path": _TEST_PATH, "sha256": _digest(test), "text": test},
        "changes": normalized,
    }, assessment


def _regression(value):
    if value is None:
        return None
    value = _object(value)
    if value.keys() != {
        "status",
        "pytest_exit",
        "collected",
        "setup",
        "call",
        "teardown",
        "requests",
        "response",
    }:
        _bad()
    if any(_integer(value.get(key), nullable=False) != 1 for key in ("collected", "requests")):
        _bad()
    if value.get("setup") != "passed" or value.get("teardown") != "passed":
        _bad()
    code = _integer(value.get("pytest_exit"), nullable=False)
    if (value.get("status"), code, value.get("call")) not in (
        ("assertion-failed", 1, "failed"),
        ("passed", 0, "passed"),
    ):
        _bad()
    response = _object(value.get("response"))
    if (
        response.keys() != {"status_code", "body"}
        or not 100 <= _integer(response.get("status_code"), nullable=False) <= 599
    ):
        _bad()
    body = _object(response.get("body"))
    if len(body) > 8:
        _bad()
    for key, child in body.items():
        _text(key, limit=64, nullable=False)
        _text(child, limit=256, nullable=False)
    return value


def _phase(value, candidate, proposal):
    if value is None:
        return None
    value = _object(value)
    if (
        proposal is None
        or value.get("kind") != "owner-read-phase-result"
        or value.get("schema_version") != "1.0"
        or value.get("phase") != candidate
    ):
        _bad()
    expected_source = (
        proposal["changes"][0]["before_sha256"]
        if candidate == "before"
        else proposal["after_source"]["sha256"]
    )
    if (
        value.get("source_sha256") != expected_source
        or value.get("test_sha256") != proposal["test"]["sha256"]
    ):
        _bad()
    status = _text(value.get("status"), nullable=False)
    if status not in ("matched", "mismatch", "failed"):
        _bad()
    cleanup = _bool(value.get("cleanup_confirmed"))
    regression = _regression(value.get("regression"))
    comparison = None
    observations = value.get("observations")
    compared = value.get("comparison")
    if observations is not None:
        checked = compare_owner_read_observations(observations)
        if checked["status"] != "compared" or canonical(checked) != canonical(compared):
            _bad()
        before = candidate == "before"
        profile_matches = checked["matches_before_profile" if before else "matches_intended_policy"]
        matching = sum(
            row["before_match" if before else "intended_match"] for row in checked["checks"]
        )
        comparison = {
            "expected_profile": "intended-before-defect" if before else "repaired-policy-controls",
            "comparison_status": "matches-expected-profile"
            if profile_matches
            else "does-not-match-expected-profile",
            "matches_expected_profile": profile_matches,
            "case_count": 7,
            "matching_case_count": matching,
            "request_count": 7,
            "matching_request_count": matching,
            "intended_match_count": checked["intended_matches"],
        }
    elif compared is not None:
        _bad()
    expected_response = owner_read_controls()[1]["before" if candidate == "before" else "intended"]
    expected_regression = "assertion-failed" if candidate == "before" else "passed"
    matched = (
        regression is not None
        and regression["status"] == expected_regression
        and canonical(regression["response"]) == canonical(expected_response)
        and comparison is not None
        and comparison["matches_expected_profile"] is True
    )
    failure = _failure(value.get("failure"))
    if status == "matched" and (not matched or cleanup is not True or failure is not None):
        _bad()
    if status == "mismatch" and (matched or cleanup is not True):
        _bad()
    return {
        "candidate": candidate,
        "status": status,
        "test_exit_code": regression["pytest_exit"] if regression else None,
        "cleanup_confirmed": cleanup,
        "generated_runtime_attempted": True,
        "application_sha256": expected_source,
        "test_sha256": proposal["test"]["sha256"],
        "failure": failure,
        "transport_failure": None,
        "comparison": comparison,
        "regression_status": regression["status"] if regression else None,
        "response_status": regression["response"]["status_code"] if regression else None,
    }


def _session(data, proposal):
    value = _object(data.get("file_workflow"), nullable=True)
    if value is None:
        return None
    if value.get("kind") not in (None, "owner-read-file-session") or value.get(
        "schema_version"
    ) not in (None, "1.0"):
        _bad()
    status = _text(value.get("status"), nullable=False)
    stages = _object(value.get("stages"), nullable=True) or {}
    if set(stages) - set(_STAGES):
        _bad()
    normalized = []
    stopped = None
    for name in _STAGES:
        if name not in stages:
            continue
        stage = _object(stages[name])
        recorded = _text(stage.get("status"), nullable=False)
        dispatched = _bool(stage.get("guest_dispatch_started"))
        if name not in ("before", "after") and dispatched is True:
            _bad()
        success = recorded == _SUCCESS[name]
        normalized.append(
            {
                "stage": _LABELS.get(name, name),
                "status": recorded,
                "decision": "approved"
                if success or recorded in ("approved", "dispatched")
                else "declined"
                if recorded == "declined"
                else "cancelled"
                if recorded == "cancelled"
                else None,
                "expired": True if recorded == "expired" else False if success else None,
                "attempted": dispatched
                if name in ("before", "after")
                else True
                if success
                else None,
                "dispatched": dispatched
                if name in ("before", "after")
                else False
                if name == "diff" and success
                else True
                if success
                else None,
                "reason": _text(stage.get("reason")),
            }
        )
        if stopped is None and recorded not in (_SUCCESS[name], "not-run"):
            stopped = _LABELS.get(name, name)
    checks = {
        candidate: _phase(value.get(candidate), candidate, proposal)
        for candidate in ("before", "after")
    }
    for candidate, phase in checks.items():
        if (
            candidate in stages
            and stages[candidate].get("status") == "matched"
            and (phase is None or phase["status"] != "matched")
        ):
            _bad()
        if phase is not None and (
            candidate not in stages or stages[candidate].get("guest_dispatch_started") is not True
        ):
            _bad()
    recovery = _bool(value.get("recovery_required"))
    descriptor_cleanup = _bool(value.get("descriptor_cleanup_confirmed"))
    guest_cleanup = _bool(value.get("guest_cleanup_confirmed"))
    runtime_cleanup = _bool(data.get("runtime_descriptor_cleanup_confirmed"))
    application = _text(value.get("patch_application"))
    restoration = _text(value.get("restoration_status"))
    for field, recorded in (
        ("patch_application", application),
        ("restoration_status", restoration),
    ):
        if data.get(field) is not None and recorded is not None and data[field] != recorded:
            _bad()
    if application == "applied-to-copy" and proposal is None:
        _bad()
    if status == "completed" and (
        set(stages) != set(_STAGES)
        or proposal is None
        or value.get("exit_code") != 0
        or type(value.get("exit_code")) is not int
        or any(stages[name].get("status") != _SUCCESS[name] for name in _STAGES)
        or any(
            stages[name].get("guest_dispatch_started") is not True for name in ("before", "after")
        )
        or any(
            phase is None or phase["status"] != "matched" or phase["cleanup_confirmed"] is not True
            for phase in checks.values()
        )
        or application != "applied-to-copy"
        or restoration != "restored"
        or value.get("workspace_state") != "restored-before"
        or recovery is not False
        or descriptor_cleanup is not True
        or guest_cleanup is not True
        or value.get("original_checkout_modified") is not False
        or data.get("original_checkout_modified") is not False
        or data.get("execution_status") != "completed"
    ):
        _bad()
    if (
        status == "completed"
        and data.get("status") == "proposed-change"
        and (
            type(data.get("exit_code")) is not int
            or data["exit_code"] != 0
            or data.get("failure") is not None
            or data.get("runtime_descriptor_cleanup_confirmed") is not True
        )
    ):
        _bad()
    return {
        "status": status,
        "stopped_stage": stopped,
        "closed": descriptor_cleanup,
        "close_status": "confirmed"
        if descriptor_cleanup is True
        else "unconfirmed"
        if descriptor_cleanup is False
        else None,
        "runtime_input_cleanup": "confirmed"
        if data.get("runtime_descriptor_cleanup_confirmed") is True
        else "unconfirmed"
        if data.get("runtime_descriptor_cleanup_confirmed") is False
        else None,
        "cleanup_unconfirmed": True
        if descriptor_cleanup is False or guest_cleanup is False or runtime_cleanup is False
        else False
        if descriptor_cleanup is True and guest_cleanup is True and runtime_cleanup is True
        else None,
        "clock_unconfirmed": None,
        "workspace_state": _text(value.get("workspace_state")),
        "stages": normalized,
        "checks": checks,
        "authorization_status": "unknown",
        "verified_fix": False,
        "isolation_established": None,
        "resource_enforcement_established": None,
        "test_report_authenticity": "not-established",
        "recovery_required": recovery,
    }


def preview_owner_read_result(data):
    if data.get("schema_version") != "1.0":
        _bad()
    source = _owner_source(data)
    proposal, assessment = _proposal(data, source)
    session = _session(data, proposal)
    status = _text(data.get("status"), nullable=False)
    if status in ("proposed-change", "no-change", "unknown", "refused") and assessment is None:
        _bad()
    runtime_cleanup = _bool(data.get("runtime_descriptor_cleanup_confirmed"))
    recovery = session["recovery_required"] if session is not None else None
    if runtime_cleanup is False:
        recovery = True
    application = _text(data.get("patch_application"))
    if application == "applied-to-copy" and proposal is None:
        _bad()
    if data.get("execution_status") == "completed" and (
        session is None
        or any(
            phase is None or phase["status"] != "matched" for phase in session["checks"].values()
        )
    ):
        _bad()
    warnings = [
        "Imported claims are unverified. Display validation is not execution, "
        "approval or a security verdict.",
        "Raw runtime metadata, phase captures and account information are omitted from this view.",
    ]
    if source is None:
        warnings.append(
            "Original source evidence is absent; the source diff cannot be independently rebuilt."
        )
    return {
        "schema_version": "1.0",
        "kind": "authzest-workflow-view",
        "record_kind": "owner-read-suggestion",
        "record_version": "1.0",
        "provenance": "imported-unverified",
        "summary": {
            "status": session["status"]
            if status == "proposed-change" and session is not None
            else status,
            "exit_code": _integer(data.get("exit_code")),
            "proposal_status": assessment["status"] if assessment else None,
            "execution_status": _text(data.get("execution_status")),
            "patch_application": application,
            "applied": True
            if application == "applied-to-copy"
            else False
            if application == "not-run"
            else None,
            "current_copy_state": session["workspace_state"] if session else None,
            "restoration_status": _text(data.get("restoration_status")),
            "original_checkout_modified": _bool(data.get("original_checkout_modified")),
            "recovery_required": recovery,
        },
        "source_evidence": source,
        "assessment": assessment,
        "proposal": proposal,
        "session": session,
        "failure": _failure(data.get("failure")),
        "availability": {
            "before_source": source is not None,
            "declarations": source is not None,
            "raw_phase_captures": False,
        },
        "warnings": warnings,
    }
