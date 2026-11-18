"""Bounded, read-only projections of explicitly imported workflow records.

This module does not import execution helpers, follow artifact paths, authenticate
receipts, or infer authorization. Hash consistency is not source provenance.
"""

from __future__ import annotations

import json
import math
import re
from difflib import unified_diff
from hashlib import sha256
from typing import Any

MAX_RESULT_BYTES = 524_288
_STAGES = ("copy", "before", "source-diff", "source-apply", "after", "restore")
_STAGE_SUCCESS = (
    "copied-private-workspace",
    "checked-before",
    "accepted-exact-diff",
    "applied-copy-only",
    "checked-after",
    "restored-before",
)


class ResultViewError(ValueError):
    """A fixed diagnostic with no uploaded text or host path in its message."""


def _bad() -> None:
    raise ResultViewError("Invalid or unsupported workflow result")


def _object(value: Any, *, nullable: bool = False) -> dict | None:
    if value is None and nullable:
        return None
    if type(value) is not dict:
        _bad()
    return value


def _text(value: Any, *, limit: int = 512, nullable: bool = True) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str or len(value.encode("utf-8")) > limit:
        _bad()
    return value


def _bool(value: Any) -> bool | None:
    if value is not None and type(value) is not bool:
        _bad()
    return value


def _integer(value: Any, *, nullable: bool = True, minimum: int = 0) -> int | None:
    if value is None and nullable:
        return None
    if type(value) is not int or not minimum <= value <= 1_000_000:
        _bad()
    return value


def _hash(value: Any, *, nullable: bool = True) -> str | None:
    value = _text(value, nullable=nullable)
    if value is not None and re.fullmatch(r"[a-f0-9]{64}", value) is None:
        _bad()
    return value


def _strings(value: Any) -> list[str]:
    if type(value) is not list or len(value) > 32:
        _bad()
    return [_text(item, limit=4096, nullable=False) for item in value]


def _failure(value: Any) -> dict | None:
    if value is None:
        return None
    if type(value) is str:
        return {"stage": None, "code": _text(value), "turn_start": None}
    value = _object(value)
    return {key: _text(value.get(key)) for key in ("stage", "code", "turn_start")}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _bad()
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    _bad()


def _decode(raw: bytes) -> dict:
    if type(raw) is not bytes or len(raw) > MAX_RESULT_BYTES:
        raise ResultViewError("Workflow result exceeds the 512 KiB limit")
    try:
        data = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
        )
        pending, count = [(data, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 32 or count > 8192:
                _bad()
            if type(item) is dict:
                if len(item) > 128:
                    _bad()
                pending.extend((key, depth + 1) for key in item)
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                if len(item) > 512:
                    _bad()
                pending.extend((child, depth + 1) for child in item)
            elif type(item) is str:
                _text(item, limit=65_536, nullable=False)
            elif type(item) is float and not math.isfinite(item):
                _bad()
        return _object(data)
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        raise ResultViewError("Invalid or unsupported workflow result") from None


def _source(value: Any) -> dict | None:
    if value is None:
        return None
    value = _object(value)
    source = _object(value.get("source"))
    text = _text(source.get("text"), limit=16_384, nullable=False)
    digest = _hash(source.get("sha256"), nullable=False)
    if sha256(text.encode("utf-8")).hexdigest() != digest:
        _bad()
    declarations = value.get("declarations")
    if type(declarations) is not list or len(declarations) > 32:
        _bad()
    for declaration in declarations:
        _object(declaration)
    return {
        "scenario_id": _text(value.get("scenario_id"), nullable=False),
        "source": {
            "path": _text(source.get("path"), nullable=False),
            "sha256": digest,
            "text": text,
        },
        "declarations": declarations,
        "policy": _strings(value.get("policy")),
        "policy_authorship": _text(value.get("policy_authorship")),
        "policy_review": _text(value.get("policy_review")),
    }


def _diff(before: str, after: str, path: str, *, new: bool = False) -> str:
    # Preserve LF-only source identity and the producer's missing-terminal-LF marker.
    def lines(text: str) -> list[str]:
        parts = text.split("\n")
        return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in unified_diff(
            lines(before),
            lines(after),
            fromfile="/dev/null" if new else "a/" + path,
            tofile="b/" + path,
        )
    )


def _proposal(data: dict, source: dict | None) -> tuple[dict | None, dict | None]:
    generation = _object(data.get("generation"), nullable=True)
    preview = _object(data.get("proposal_preview"), nullable=True)
    if generation is None:
        if preview is not None:
            _bad()
        return None, None
    if (
        generation.get("schema_version") != "1.0"
        or generation.get("kind", "generated-repair-transport-result")
        != "generated-repair-transport-result"
    ):
        _bad()
    proposal = _object(generation.get("proposal"))
    if proposal.get("schema_version") != "1.0":
        _bad()
    status = _text(proposal.get("status"), nullable=False)
    if status not in ("proposed-change", "no-change", "unknown", "refused"):
        _bad()
    if data.get("proposal_status") != status:
        _bad()
    if preview is None or preview.get("schema_version") != "1.0":
        _bad()
    if preview.get("kind", "generated-repair-preview") != "generated-repair-preview":
        _bad()
    if preview.get("status") != status or preview.get("proposal") != proposal:
        _bad()
    changes = preview.get("changes")
    if type(changes) is not list:
        _bad()
    assessment = {
        "status": status,
        "rationale": _text(proposal.get("rationale"), limit=4096, nullable=False),
        **{
            key: _strings(proposal.get(key))
            for key in ("assumptions", "uncertainties", "limitations")
        },
    }
    if status != "proposed-change":
        if proposal.get("proposal") is not None or changes:
            _bad()
        return None, assessment
    change = _object(proposal.get("proposal"))
    after_text = _text(change.get("after_text"), limit=16_384, nullable=False)
    test_text = _text(change.get("test_text"), limit=16_384, nullable=False)
    after_path = _text(change.get("source_path"), nullable=False)
    test_path = _text(change.get("test_path"), nullable=False)
    before_hash = _hash(change.get("before_sha256"), nullable=False)
    if after_path == test_path or len(changes) != 2:
        _bad()
    expected = [
        (after_path, before_hash, sha256(after_text.encode("utf-8")).hexdigest()),
        (test_path, None, sha256(test_text.encode("utf-8")).hexdigest()),
    ]
    normalized = []
    for item, (path, before, after) in zip(changes, expected, strict=True):
        item = _object(item)
        if (item.get("path"), item.get("before_sha256"), item.get("after_sha256")) != (
            path,
            before,
            after,
        ):
            _bad()
        normalized.append(
            {
                "path": path,
                "before_sha256": before,
                "after_sha256": after,
                "diff": _text(item.get("diff"), limit=65_536, nullable=False),
            }
        )
    if normalized[1]["diff"] != _diff("", test_text, test_path, new=True):
        _bad()
    if source is not None:
        before = source["source"]
        if before["sha256"] != before_hash or before["path"] != after_path:
            _bad()
        if normalized[0]["diff"] != _diff(before["text"], after_text, after_path):
            _bad()
    return {
        **{key: value for key, value in assessment.items() if key != "status"},
        "after_source": {"path": after_path, "sha256": expected[0][2], "text": after_text},
        "test": {"path": test_path, "sha256": expected[1][2], "text": test_text},
        "changes": normalized,
    }, assessment


def _comparison(value: Any, candidate: str) -> dict | None:
    if value is None:
        return None
    value = _object(value)
    result = {
        key: _integer(value.get(key), nullable=False)
        for key in ("case_count", "matching_case_count", "request_count", "matching_request_count")
    }
    if (
        result["matching_case_count"] > result["case_count"]
        or result["matching_request_count"] > result["request_count"]
    ):
        _bad()
    result.update(
        expected_profile=_text(value.get("expected_profile"), nullable=False),
        comparison_status=_text(value.get("comparison_status"), nullable=False),
        matches_expected_profile=_bool(value.get("matches_expected_profile")),
    )
    expected = "intended-before-defect" if candidate == "before" else "repaired-policy-controls"
    if result["expected_profile"] != expected:
        _bad()
    if (
        result["comparison_status"] == "matches-expected-profile"
        and result["matches_expected_profile"] is not True
    ):
        _bad()
    if result["matches_expected_profile"] is True and (
        result["matching_case_count"] != result["case_count"]
        or result["matching_request_count"] != result["request_count"]
        or result["comparison_status"] != "matches-expected-profile"
    ):
        _bad()
    return result


def _phase(value: Any, candidate: str, proposal: dict | None) -> dict | None:
    if value is None:
        return None
    value = _object(value)
    if value.get("candidate") != candidate:
        _bad()
    result = {
        "candidate": candidate,
        "status": _text(value.get("status"), nullable=False),
        "test_exit_code": _integer(value.get("test_exit_code"), minimum=-255),
        "cleanup_confirmed": _bool(value.get("cleanup_confirmed")),
        "generated_runtime_attempted": _bool(value.get("generated_runtime_attempted")),
        "application_sha256": _hash(value.get("application_sha256")),
        "test_sha256": _hash(value.get("test_sha256")),
        "failure": _failure(value.get("failure")),
        "transport_failure": _failure(value.get("transport_failure")),
        "comparison": _comparison(value.get("comparison"), candidate),
    }
    if result["test_exit_code"] is not None and result["test_exit_code"] > 255:
        _bad()
    if proposal is not None:
        expected_app = (
            proposal["changes"][0]["before_sha256"]
            if candidate == "before"
            else proposal["after_source"]["sha256"]
        )
        for key, expected in (
            ("application_sha256", expected_app),
            ("test_sha256", proposal["test"]["sha256"]),
        ):
            if result[key] is not None and result[key] != expected:
                _bad()
    return result


def _session(data: dict, proposal: dict | None) -> dict | None:
    workflow = _object(data.get("file_workflow"), nullable=True)
    if workflow is None:
        return None
    session = _object(workflow.get("session_result"), nullable=True)
    if session is None:
        return {
            "status": _text(workflow.get("status")),
            "stopped_stage": None,
            "closed": None,
            "close_status": _text(workflow.get("close_status")),
            "runtime_input_cleanup": _text(workflow.get("runtime_input_cleanup")),
            "cleanup_unconfirmed": None,
            "clock_unconfirmed": None,
            "workspace_state": None,
            "stages": [],
            "checks": {"before": None, "after": None},
            **{
                key: None
                for key in (
                    "authorization_status",
                    "verified_fix",
                    "isolation_established",
                    "resource_enforcement_established",
                    "test_report_authenticity",
                )
            },
        }
    if session.get("schema_version") != "1.0":
        _bad()
    if session.get("kind", "generated-repair-session-result") != "generated-repair-session-result":
        _bad()
    for top, nested in (
        ("execution_status", "execution_status"),
        ("patch_application", "source_application"),
        ("restoration_status", "restoration_status"),
    ):
        if (
            data.get(top) is not None
            and session.get(nested) is not None
            and data[top] != session[nested]
        ):
            _bad()
    workspace = _object(session.get("workspace"), nullable=True) or {}
    if (
        data.get("current_copy_state") is not None
        and workspace.get("state") is not None
        and data["current_copy_state"] != workspace["state"]
    ):
        _bad()
    application = session.get("source_application")
    if (application == "applied-copy-only" and data.get("applied") is False) or (
        application == "not-run" and data.get("applied") is True
    ):
        _bad()
    stages = _object(session.get("stages"))
    if set(stages) - set(_STAGES):
        _bad()
    normalized_stages = []
    for name in _STAGES:
        if name not in stages:
            continue
        stage = _object(stages[name])
        normalized_stages.append(
            {
                "stage": name,
                **{key: _text(stage.get(key)) for key in ("status", "decision", "reason")},
                **{key: _bool(stage.get(key)) for key in ("expired", "attempted", "dispatched")},
            }
        )
    checks = _object(session.get("checks"))
    result = {
        "status": _text(workflow.get("status")),
        "stopped_stage": _text(workflow.get("stopped_stage")),
        "closed": _bool(session.get("closed")),
        "close_status": _text(workflow.get("close_status")),
        "runtime_input_cleanup": _text(workflow.get("runtime_input_cleanup")),
        "cleanup_unconfirmed": _bool(session.get("cleanup_unconfirmed")),
        "clock_unconfirmed": _bool(session.get("clock_unconfirmed")),
        "workspace_state": _text(workspace.get("state")),
        "stages": normalized_stages,
        "checks": {name: _phase(checks.get(name), name, proposal) for name in ("before", "after")},
        "authorization_status": _text(session.get("authorization_status")),
        "test_report_authenticity": _text(session.get("test_report_authenticity")),
        **{
            key: _bool(session.get(key))
            for key in ("verified_fix", "isolation_established", "resource_enforcement_established")
        },
    }
    if result["authorization_status"] not in (None, "unknown") or any(
        result[key] is True
        for key in ("verified_fix", "isolation_established", "resource_enforcement_established")
    ):
        _bad()
    if result["test_report_authenticity"] not in (None, "not-established"):
        _bad()
    if data.get("status") == "file-workflow-complete":
        if (
            data.get("exit_code") != 0
            or data.get("failure") is not None
            or workflow.get("failure") is not None
            or data.get("applied") is not True
            or data.get("original_checkout_modified") is not False
            or data.get("proposal_status") != "proposed-change"
            or data.get("execution_status") != "after-checked"
            or result["status"] != "complete"
            or result["close_status"] != "confirmed"
            or result["runtime_input_cleanup"] != "confirmed"
            or result["stopped_stage"] is not None
            or result["cleanup_unconfirmed"] is not False
            or result["clock_unconfirmed"] is not False
            or result["closed"] is not True
            or result["workspace_state"] != "restored-before"
            or data.get("restoration_status") != "restored-before"
            or application != "applied-copy-only"
        ):
            _bad()
        if len(normalized_stages) != len(_STAGES):
            _bad()
        for stage, success in zip(normalized_stages, _STAGE_SUCCESS, strict=True):
            if (
                stage["status"] != success
                or stage["decision"] != "approved"
                or stage["expired"] is not False
                or stage["attempted"] is not True
                or stage["dispatched"] is not (stage["stage"] != "source-diff")
            ):
                _bad()
        for candidate in ("before", "after"):
            phase = result["checks"][candidate]
            if (
                phase is None
                or phase["status"] != "complete"
                or phase["cleanup_confirmed"] is not True
                or phase["generated_runtime_attempted"] is not True
                or phase["failure"] is not None
                or phase["transport_failure"] is not None
                or phase["comparison"] is None
                or phase["comparison"]["matches_expected_profile"] is not True
                or phase["comparison"]["case_count"] == 0
                or phase["comparison"]["request_count"] == 0
                or phase["application_sha256"] is None
                or phase["test_sha256"] is None
                or phase["test_exit_code"] != (1 if candidate == "before" else 0)
            ):
                _bad()
    return result


def preview_workflow_result(raw: bytes) -> dict:
    """Validate display consistency, then discard private paths/account metadata."""
    data = _decode(raw)
    if data.get("kind") != "codex-generated-file-workflow":
        _bad()
    version = data.get("schema_version", "legacy-unversioned")
    if version not in ("1.0", "legacy-unversioned"):
        _bad()
    # An explicit unsupported version cannot opt into the legacy importer.
    if "schema_version" in data and version != "1.0":
        _bad()
    source = _source(data.get("source_evidence")) if version == "1.0" else None
    proposal, assessment = _proposal(data, source)
    summary = {
        **{
            key: _text(data.get(key))
            for key in (
                "status",
                "proposal_status",
                "execution_status",
                "patch_application",
                "current_copy_state",
                "restoration_status",
            )
        },
        "exit_code": _integer(data.get("exit_code")),
        "applied": _bool(data.get("applied")),
        "original_checkout_modified": _bool(data.get("original_checkout_modified")),
    }
    if summary["status"] is None:
        _bad()
    session = _session(data, proposal)
    if summary["status"] == "file-workflow-complete" and (session is None or proposal is None):
        _bad()
    warnings = [
        "Imported claims are unverified. Display validation is not execution, "
        "approval or a security verdict.",
        "Raw phase stdout/stderr and per-request captures are not included in this result.",
    ]
    if version == "legacy-unversioned":
        warnings.append(
            "Legacy unversioned record: original source and declarations are unavailable."
        )
    if source is None:
        warnings.append(
            "Original source evidence is absent; the source diff cannot be independently rebuilt."
        )
    failure = _failure(data.get("failure"))
    workflow = _object(data.get("file_workflow"), nullable=True) or {}
    if failure is None and workflow.get("failure") is not None:
        failure = _failure(workflow["failure"])
        failure["stage"] = _text(workflow.get("stopped_stage"))
    if failure is None and workflow.get("restore_status") is not None:
        failure = {
            "stage": "restore",
            "code": _text(workflow["restore_status"]),
            "turn_start": None,
        }
    return {
        "schema_version": "1.0",
        "kind": "authzest-workflow-view",
        "record_version": version,
        "provenance": "imported-unverified",
        "summary": summary,
        "source_evidence": source,
        "assessment": assessment,
        "proposal": proposal,
        "session": session,
        "failure": failure,
        "availability": {
            "before_source": source is not None,
            "declarations": source is not None,
            "raw_phase_captures": False,
        },
        "warnings": warnings,
    }
