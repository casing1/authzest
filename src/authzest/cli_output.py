"""CLI-only presentation; never interpret displayed data as permission or code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import typer


def quoted(value: Any) -> str:
    """Keep controls, bidi characters and source/model text inert in terminals."""
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def json_output(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False)


_UNKNOWN = {
    "usage",
    "returned_identity",
    "latency_ms",
    "provider_warning_count",
    "provider_retry_notification_count",
    "observed",
    "observation",
}
_SECTIONS = {
    "source_scope": "Source scope",
    "evidence": "Evidence",
    "review": "Review / rationale",
    "draft": "Untrusted draft",
    "recommendation": "Untrusted recommendation / transport metadata",
    "recommendation_preview": "Locally composed recommendation preview (not applied)",
    "cases": "Cases / observations (see explicit status)",
    "case_drafts": "Case drafts (unreviewed; not executed)",
    "application": "Application result",
    "verification": "Verification result",
    "restoration": "Restoration result",
    "failure": "Redacted failure diagnostic",
    "limits": "Limits",
    "changes": "Changes",
    "expectations": "Expectations (not execution)",
    "limitations": "Limitations",
    "results": "Results (not a security verdict)",
    "decisions": "Decisions",
}


def _lines(value: Any, *, depth: int = 0, key: str | None = None) -> list[str]:
    prefix = "  " * depth
    if key == "diff" and isinstance(value, str):
        return [prefix + "Exact diff (each line is quoted):"] + [
            prefix + quoted(line) for line in value.split("\n")
        ]
    if isinstance(value, dict) and value:
        lines = []
        for name, item in value.items():
            if isinstance(item, (dict, list)) and item or name == "diff":
                lines.append(prefix + quoted(name) + ":")
                lines.extend(_lines(item, depth=depth + 1, key=name))
            else:
                suffix = " (unknown; not reported)" if item is None and name in _UNKNOWN else ""
                lines.append(prefix + quoted(name) + ": " + quoted(item) + suffix)
        return lines
    if isinstance(value, list) and value:
        lines = []
        for index, item in enumerate(value, 1):
            lines.append(prefix + f"Item {index}:")
            lines.extend(_lines(item, depth=depth + 1))
        return lines
    suffix = " (unknown; not reported)" if value is None and key in _UNKNOWN else ""
    return [prefix + quoted(value) + suffix]


def section(title: str, value: Any, *, key: str | None = None) -> str:
    """Titles are caller-owned constants; every data value/key remains quoted."""
    return title + "\n" + "\n".join(_lines(value, key=key))


def format_record(value: dict, *, title: str = "Workflow result") -> str:
    parts = [title, "Processing status is not an authorization/security pass."]
    summary = {key: item for key, item in value.items() if key not in _SECTIONS}
    parts.append(section("Status / identity / decisions", summary))
    for key, item in value.items():
        if key in _SECTIONS:
            parts.append(section(_SECTIONS[key], item, key=key))
    return "\n\n".join(parts)


def format_sharing_preview(value: dict) -> str:
    scope = {
        key: value[key]
        for key in (
            "source_scope",
            "request_id",
            "sharing_id",
            "sharing_content_id",
            "invocation_nonce",
            "runtime_check_requested",
            "verification_scope",
        )
        if key in value
    }
    return "\n\n".join(
        [
            "Source-sharing preview - not shared; no approval implied",
            section("Source scope / confirmation identity", scope),
            "Complete sharing envelope (authoritative JSON; review every field before consent)\n"
            + json_output(value),
        ]
    )


def format_file_workflow_preview(value: dict) -> str:
    """Readable orientation never replaces the complete authoritative consent data."""
    copying = value.get("kind") == "owner-policy-file-copy-preview"
    title = "Owned-copy creation preview" if copying else "Owned-file stage preview"
    identity = {
        key: value[key]
        for key in ("stage", "copy_confirmation", "decision", "limits", "notice")
        if key in value
    }
    return "\n\n".join(
        [
            title + " - not approved; no effect implied",
            section("Scope / separate decision", identity),
            "Complete authoritative JSON (review every field before consent)\n"
            + json_output(value),
        ]
    )


def _file_checkpoint_parts(checkpoint: Any) -> list[str]:
    if not isinstance(checkpoint, dict):
        return [
            "File checkpoint unavailable. Execution, file state and observations are unknown; "
            "no rollback or deletion is implied."
        ]
    summary = {
        key: checkpoint.get(key)
        for key in (
            "phase",
            "generation",
            "workspace",
            "closed",
            "diff_status",
            "application_status",
            "restoration_status",
            "comparison_status",
            "file_binding_status",
            "evidence_status",
            "authorization_status",
            "provider_calls",
            "failure",
            "attempts_consumed",
            "restart_supported",
            "provenance",
        )
    }
    parts = [section("File state / distinct stage and evidence statuses", summary)]
    checks = checkpoint.get("checks")
    checks = checks if isinstance(checks, dict) else {}
    for candidate, title in (("before", "Before check"), ("after", "Applied-after check")):
        check = checks.get(candidate)
        if isinstance(check, dict):
            parts.append(
                section(
                    title + " - execution is separate from expectation comparison",
                    {
                        key: check.get(key)
                        for key in ("execution_status", "comparison_status", "reason", "transport")
                    },
                )
            )
        else:
            parts.append(title + ": no accepted check checkpoint; observations are unknown.")
    rows = checkpoint.get("comparison")
    if isinstance(rows, list) and rows:
        lines = [
            "Case comparison (recorded captured-file observations)",
            "Case | Expected | Before | Applied after | Change",
        ]
        for row in rows:
            if not isinstance(row, dict):
                continue
            observations = [
                quoted(row.get(key))
                if type(row.get(key)) is bool
                else "unknown (no accepted observation)"
                for key in ("before", "after")
            ]
            lines.append(
                " | ".join(
                    [
                        quoted(row.get("case_id")),
                        quoted(row.get("expected")),
                        *observations,
                        quoted(row.get("change")),
                    ]
                )
            )
        lines.append(
            "Unknown is not denial. Fixed-case comparisons are not authorization verdicts."
        )
        parts.append("\n".join(lines))
    else:
        parts.append("Case observations unavailable; no passing comparison can be inferred.")
    if checkpoint.get("phase") == "restored-before":
        parts.append(
            "Restored-before: any retained after pass is HISTORICAL. It does not mean the "
            "currently restored before file passes; restoration does not run another check."
        )
    parts.append(
        "Checkpoints and choices are unauthenticated, not independent execution or approval "
        "proof. Retained files are not a resumable session. Session provider_calls excludes "
        "the separate recommendation transport."
    )
    return parts


def format_file_workflow_result(value: dict) -> str:
    file_workflow = value.get("file_workflow")
    file_workflow = file_workflow if isinstance(file_workflow, dict) else {}
    summary = {
        key: value.get(key)
        for key in (
            "status",
            "exit_code",
            "candidate",
            "sharing_decision",
            "application_turn_attempts",
            "returned_identity",
            "model_identity_basis",
            "usage",
            "latency_ms",
            "provider_warning_count",
            "provider_retry_notification_count",
            "execution_status",
            "patch_application",
            "restoration_status",
            "comparison_status",
            "authorization_status",
            "failure",
            "limits",
        )
    }
    parts = [
        "Owned policy file workflow result",
        "Processing status is not an authorization/security pass.",
        section("Recommendation transport / workflow status", summary),
    ]
    recommendation = value.get("recommendation")
    if isinstance(recommendation, dict):
        parts.append(
            section(
                "Untrusted recommendation - not execution or permission",
                recommendation.get("recommendation", recommendation),
            )
        )
    parts.append(
        section(
            "Copy decision / retained-file diagnostic",
            {key: item for key, item in file_workflow.items() if key != "session_result"},
        )
    )
    if (
        file_workflow.get("session_result") is None
        and file_workflow.get("checkpoint_status") == "not-created"
    ):
        parts.append(
            "File workflow not started: no file session or copy was created. "
            "File checks, application and restoration were not run."
        )
    else:
        parts.extend(_file_checkpoint_parts(file_workflow.get("session_result")))
    return "\n\n".join(parts)


@dataclass
class WorkflowOutput:
    """Separate interactive I/O from the single machine-readable final result."""

    as_json: bool = False

    def emit(self, text: str) -> None:
        value = json.loads(text)
        if self.as_json:
            typer.echo(json_output(value), err=True)
        elif isinstance(value, dict) and value.get("kind") in (
            "codex-owner-review-sharing-preview",
            "codex-owner-repair-sharing-preview",
            "codex-fixture-sharing-preview",
        ):
            typer.echo(format_sharing_preview(value))
        elif isinstance(value, dict) and value.get("kind") in (
            "owner-policy-file-copy-preview",
            "owner-policy-file-stage-preview",
        ):
            typer.echo(format_file_workflow_preview(value))
        elif isinstance(value, dict) and value.get("kind") == "owner-policy-file-stage-result":
            typer.echo(
                "\n\n".join(
                    [
                        section("Owned-file stage observation", {"stage": value.get("stage")}),
                        *_file_checkpoint_parts(value.get("session_result")),
                    ]
                )
            )
        else:
            typer.echo(format_record(value, title="Workflow preview / observation"))

    def read(self, prompt: str) -> str:
        # input() without a prompt does not write to stdout. Do not echo supplied
        # answers or change their content: the runner owns exact-choice validation.
        typer.echo(quoted(prompt)[1:-1], nl=False, err=True)
        return input()

    def finish(self, value: dict, *, error: bool = False, preview: bool = False) -> None:
        if self.as_json or error:
            # Small redacted errors retain stderr in human mode; explicit JSON
            # mode includes application failures in its single stdout result.
            typer.echo(json_output(value), err=error and not self.as_json)
        elif preview:
            typer.echo(format_sharing_preview(value))
        elif value.get("kind") == "codex-owner-file-workflow":
            typer.echo(format_file_workflow_result(value))
        else:
            typer.echo(format_record(value), err=error)
