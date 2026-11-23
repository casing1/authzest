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
    "generation": "Untrusted generated proposal / transport metadata",
    "proposal_preview": "Locally composed generated-source diff (not applied or executed)",
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


def _terminal_line(text: str) -> str:
    """Readable ASCII quotes, escaped backslashes/controls/Unicode; no terminal codes.

    This is a display, not copyable source or a JSON string literal. The complete
    JSON retains exact source bytes as text; every displayed payload line is marked.
    """
    return "".join(
        char if " " <= char <= "~" and char != "\\" else quoted(char)[1:-1] for char in text
    )


def _display_value(value: Any) -> str:
    if value is None:
        return "unknown (not reported)"
    return _terminal_line(value) if isinstance(value, str) else quoted(value)


def _payload_block(title: str, value: Any, *, show_ending: bool = False) -> str:
    if not isinstance(value, str):
        return title + "\n  | " + _display_value(value)
    # Only LF separates payload lines. CR, U+2028 and all other controls stay
    # visibly escaped; a trailing empty line preserves a terminal LF.
    lines = ["  | " + _terminal_line(line) for line in value.split("\n")]
    if show_ending and not value.endswith("\n"):
        lines.append("  [No terminal LF in this text]")
    return title + "\n" + "\n".join(lines)


def _explanation_block(title: str, value: Any) -> str:
    if not isinstance(value, list):
        return _payload_block(title, value)
    if not value:
        return title + "\n  None reported."
    return (
        title
        + "\n"
        + "\n".join(
            "  | " + _display_value(item)
            if not isinstance(item, str)
            else "\n".join("  | " + _terminal_line(line) for line in item.split("\n"))
            for item in value
        )
    )


def format_generated_repair_result(value: dict, *, details: bool = False) -> str:
    """Summarize generated proposals without duplicating transport/source data.

    Missing observations remain unknown. This presentation never validates a
    proposal or supplies permission; JSON is the complete machine-readable record.
    """
    generation = value.get("generation")
    generation = generation if isinstance(generation, dict) else {}
    proposal = generation.get("proposal")
    proposal = proposal if isinstance(proposal, dict) else {}
    preview = value.get("proposal_preview")
    preview = preview if isinstance(preview, dict) else {}
    change = proposal.get("proposal")
    change = change if isinstance(change, dict) else {}
    parts = [
        "Generated repair result",
        "Untrusted proposal, not a verified repair or an authorization/security pass.",
        "Summary\n"
        + "\n".join(
            "  " + label + ": " + _display_value(value.get(key))
            for label, key in (
                ("Workflow", "status"),
                ("Proposal", "proposal_status"),
                ("Sharing decision", "sharing_decision"),
                ("Applied", "applied"),
                ("Execution", "execution_status"),
                ("Patch application", "patch_application"),
                ("Restoration", "restoration_status"),
                ("Authorization", "authorization_status"),
                (
                    "Adapter attempts (local calls, not accepted/billed provider turns)",
                    "application_turn_attempts",
                ),
            )
        ),
        "Validation limits\n"
        + "\n".join(
            "  " + label + ": " + _display_value(preview.get(key))
            for label, key in (
                ("Trust", "trust"),
                ("Python validation", "python_validation"),
                ("Code safety", "code_safety"),
                ("Policy correctness", "policy_correctness"),
                ("Policy review", "policy_review"),
            )
        ),
    ]
    changes = preview.get("changes")
    files = [
        "Changed files (proposed only)",
        "Planned proposals only; no filesystem observation or change implied.",
    ]
    if isinstance(changes, list):
        if not changes:
            files.append("  No planned changes reported.")
        for index, item in enumerate(changes, 1):
            item = item if isinstance(item, dict) else {}
            files.append(f"  | {index}. " + _display_value(item.get("path")))
    else:
        files.append("  Planned changes: unknown (not reported)")
    parts.append("\n".join(files))
    if proposal:
        parts.extend(
            [
                _payload_block("Model rationale (untrusted)", proposal.get("rationale")),
                _explanation_block("Assumptions (untrusted)", proposal.get("assumptions")),
                _explanation_block("Uncertainties (untrusted)", proposal.get("uncertainties")),
                _explanation_block("Limitations (untrusted)", proposal.get("limitations")),
            ]
        )
    failure = value.get("failure")
    if failure is not None:
        parts.append(section("Redacted failure diagnostic", failure))
    if change:
        parts.extend(
            [
                "Text display: each untrusted line starts with '  | '. Controls, Unicode and "
                "backslashes are escaped; text is not executable/copyable source. "
                "LF separates lines, including a final empty line for terminal LF. "
                "Use --json for exact artifact text, not as execution approval.",
                _payload_block(
                    "Generated source (untrusted; not executed)",
                    change.get("after_text"),
                    show_ending=True,
                ),
                _payload_block(
                    "Generated test (untrusted; not executed)",
                    change.get("test_text"),
                    show_ending=True,
                ),
            ]
        )
    if isinstance(changes, list) and changes:
        parts.append("Exact proposed diff (untrusted; not applied)")
        for item in changes:
            item = item if isinstance(item, dict) else {}
            parts.append(
                _payload_block(
                    "Diff for " + quoted(item.get("path")), item.get("diff"), show_ending=True
                )
            )
    parts.append(
        "--details includes complete result metadata; --json returns the full result only. "
        "Display options never authorize another request, execution or file application."
    )
    if details:
        parts.append("Complete result (authoritative JSON)\n" + json_output(value))
    return "\n\n".join(parts)


def _generated_file_checkpoint(value: Any) -> str:
    """Show distinct current file state and finite historical observations."""
    checkpoint = value if isinstance(value, dict) else {}
    workspace = checkpoint.get("workspace")
    workspace = workspace if isinstance(workspace, dict) else {}
    lines = ["Generated file checkpoint"]
    for label, item in (
        ("Retained private copy", workspace.get("path")),
        ("Current file state", workspace.get("state")),
        ("Baseline", checkpoint.get("baseline")),
        ("Source application", checkpoint.get("source_application")),
        ("Restoration", checkpoint.get("restoration_status")),
        ("Cleanup unconfirmed", checkpoint.get("cleanup_unconfirmed")),
        ("Authorization", checkpoint.get("authorization_status")),
    ):
        lines.append("  " + label + ": " + _display_value(item))
    checks = checkpoint.get("checks")
    checks = checks if isinstance(checks, dict) else {}
    for candidate, label in (("before", "Before"), ("after", "Applied after")):
        check = checks.get(candidate)
        if not isinstance(check, dict):
            lines.append("  " + label + ": not observed")
            continue
        comparison = check.get("comparison")
        comparison = comparison if isinstance(comparison, dict) else check
        lines.extend(
            [
                "  "
                + label
                + " execution: "
                + _display_value(check.get("status", check.get("execution_status"))),
                "    Independent cases: "
                + _display_value(comparison.get("matching_case_count"))
                + "/"
                + _display_value(comparison.get("case_count")),
                "    Independent requests: "
                + _display_value(comparison.get("matching_request_count"))
                + "/"
                + _display_value(comparison.get("request_count")),
                "    Native test exit (untrusted auxiliary): "
                + _display_value(check.get("test_exit_code")),
                "    Exact guest/local cleanup: " + _display_value(check.get("cleanup_confirmed")),
            ]
        )
    if checkpoint.get("restoration_status") == "restored-before":
        lines.append(
            "  Restored-before: after observations are historical; "
            "the restored file was not rechecked."
        )
    lines.append(
        "Finite HTTP comparisons and native test exits do not prove general authorization "
        "or assertion/report authenticity. Raw captures remain in private evidence."
    )
    return "\n".join(lines)


def format_generated_file_workflow_result(value: dict, *, details: bool = False) -> str:
    workflow = value.get("file_workflow")
    workflow = workflow if isinstance(workflow, dict) else {}
    parts = [
        "Generated repair file workflow",
        "Only separately approved stages affect the private copy; authorization remains unknown.",
        "Summary\n"
        + "\n".join(
            "  " + label + ": " + _display_value(item)
            for label, item in (
                ("Workflow", value.get("status")),
                ("Proposal", value.get("proposal_status")),
                ("File flow", workflow.get("status")),
                ("Stopped stage", workflow.get("stopped_stage")),
                (
                    "Runtime input cleanup",
                    workflow.get("runtime_input_cleanup", "not-reported"),
                ),
                ("Session close", workflow.get("close_status", "not-reported")),
                ("File-flow failure", workflow.get("failure")),
                ("Execution", value.get("execution_status")),
                ("Source application", value.get("patch_application")),
                ("Applied (historical)", value.get("applied")),
                ("Current private copy", value.get("current_copy_state", "not-reported")),
                ("Restoration", value.get("restoration_status")),
                ("Original checkout modified", value.get("original_checkout_modified")),
            )
        ),
        _generated_file_checkpoint(workflow.get("session_result")),
        "Copies and evidence are retained. No automatic rollback, retry or session resume. "
        "Use --json for the complete result; --details also includes it in human output.",
    ]
    if details:
        parts.append("Complete result (authoritative JSON)\n" + json_output(value))
    return "\n\n".join(parts)


def format_generated_file_stage_preview(value: dict) -> str:
    return "\n\n".join(
        [
            "Generated private-copy stage - not approved; no effect implied",
            section(
                "Separate current decision",
                {
                    "stage": value.get("stage"),
                    "confirmation_phrase": value.get("confirmation_phrase"),
                    "notice": value.get("notice"),
                },
            ),
            "Complete current plan (review all fields before deciding)\n" + json_output(value),
        ]
    )


def format_generated_runtime_review(value: dict) -> str:
    return "\n\n".join(
        [
            "Local runtime review - separate from source sharing and stage approval",
            "This local profile is not sent to the provider and is not kernel/image attestation.",
            "Complete local review data\n" + json_output(value),
        ]
    )


def format_generated_file_offline_preview(value: dict) -> str:
    runtime = value.get("runtime_review_preview")
    sharing = value.get("sharing_preview")
    return "\n\n".join(
        [
            "Generated file workflow preview - offline, no prompt or effect",
            section(
                "Preview status",
                {
                    "status": value.get("status", "offline-no-effects"),
                    "file_workflow": value.get("file_workflow"),
                },
            ),
            format_generated_runtime_review(runtime if isinstance(runtime, dict) else {}),
            format_sharing_preview(sharing if isinstance(sharing, dict) else {}),
        ]
    )


def format_repository_suggestion(value: dict) -> str:
    """Keep external proposals readable while escaping every untrusted text line."""
    evidence = value.get("source_evidence") or {}
    selection = evidence.get("selection") or {}
    proposal = value.get("proposal") or {}
    preview = value.get("proposal_preview") or {}
    parts = [
        "External repository proposal",
        "Untrusted source/test suggestions; not executed, applied or verified.",
        section(
            "Summary",
            {
                "status": value.get("status"),
                "model": value.get("model"),
                "source": selection.get("source"),
                "policy": selection.get("policy"),
                "context_files": selection.get("contexts"),
                "sharing_decision": value.get("sharing_decision"),
                "local_adapter_calls": value.get("application_turn_attempts"),
                "proposal_status": proposal.get("status"),
                "execution": value.get("execution_status"),
                "application": value.get("patch_application"),
            },
        ),
    ]
    if value.get("detail"):
        parts.append(_payload_block("Detail", value["detail"]))
    if proposal:
        parts.append(_payload_block("Model rationale (unverified)", proposal.get("rationale")))
        for key in ("assumptions", "uncertainties", "limitations"):
            parts.append(_explanation_block(key.capitalize(), proposal.get(key)))
    for change in preview.get("changes", []):
        parts.append(
            section(
                "Proposed artifact identity",
                {
                    key: change.get(key)
                    for key in ("path", "before_sha256", "after_sha256", "basis")
                },
            )
        )
        parts.append(_payload_block("Exact proposed diff (not applied)", change.get("diff")))
    if value.get("failure"):
        parts.append(section("Redacted failure", value["failure"]))
    parts.append(
        "Proposed test paths are artifact labels; existing test files were not inspected. "
        "Use --json for complete selected-source evidence and proposal data. "
        "The current GUI does not import this external-proposal result kind."
    )
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


def format_owner_read_rehearsal(value: dict) -> str:
    lines = [
        "Owner's archived note | Maintainer rehearsal",
        "Result: " + _display_value(value["status"]),
    ]
    for phase, title in (
        ("baseline", "Installed baseline"),
        ("reference", "Maintained correction"),
    ):
        record = value[phase]
        lines.append("")
        lines.append(title + "  [" + _display_value(record["status"]) + "]")
        observation = record.get("observation")
        if observation:
            regression = observation["regression"]
            lines.append("  Positive pytest: " + _display_value(regression["status"]))
            if response := regression.get("response"):
                lines.append(
                    "  Owner's archived read: HTTP " + _display_value(response["status_code"])
                )
        comparison = record.get("comparison")
        if comparison:
            lines.append(
                "  Responses matching intended policy: "
                + _display_value(comparison["intended_matches"])
                + " / "
                + _display_value(comparison["checks_total"])
            )
        if record.get("failure"):
            lines.append("  Observation failed: " + _display_value(record["failure"]))
    if value["status"] == "missing-dependencies":
        lines.append("\nIn the source checkout, install the rehearsal dependencies with:")
        lines.append('  python -m pip install -e ".[owner-read]"')
    if value["status"] == "unsupported":
        lines.append("\nRun from a POSIX Python installation of AuthZest.")
    return "\n".join(lines)


def format_owner_read_suggestion(value: dict) -> str:
    lines = [
        "Owner's archived record",
        "Suggestion: " + _display_value(value.get("status")),
        "Test execution: " + _display_value(value.get("execution_status")),
        "File application: " + _display_value(value.get("patch_application")),
    ]
    workflow = value.get("file_workflow")
    if workflow:
        lines.extend(
            [
                "File workflow: " + _display_value(workflow.get("status")),
                "Restoration: " + _display_value(workflow.get("restoration_status")),
                "Recovery required: " + _display_value(workflow.get("recovery_required")),
            ]
        )
        for stage in ("before", "after"):
            phase = workflow.get(stage)
            if phase:
                regression = phase.get("regression") or {}
                comparison = phase.get("comparison") or {}
                lines.append(
                    stage.title()
                    + ": "
                    + _display_value(phase.get("status"))
                    + " / pytest "
                    + _display_value(regression.get("status"))
                    + " / independent checks "
                    + _display_value(comparison.get("intended_matches"))
                    + "/7"
                )
        retained = workflow.get("copy") or {}
        if retained.get("path"):
            lines.append("Retained directory: " + _display_value(retained["path"]))
    copy = value.get("copy")
    if copy:
        lines.append("Private copy: " + _display_value(copy["status"]))
        if copy.get("path"):
            label = "Retained directory" if copy["status"] == "prepared" else "Last known location"
            lines.append(label + ": " + _display_value(copy["path"]))
        if copy.get("status") == "incomplete":
            lines.append(section("Last recorded file states", copy.get("files")))
    proposal = value.get("proposal")
    if proposal:
        lines.append(_payload_block("Model rationale", proposal["rationale"]))
    for change in value.get("diffs", []):
        lines.append(
            _payload_block("Proposed diff for " + _display_value(change["path"]), change["diff"])
        )
    if value.get("failure"):
        lines.append(section("Failure", value["failure"]))
    if value.get("detail"):
        lines.append(_payload_block("Detail", value["detail"]))
    return "\n".join(lines)


@dataclass
class WorkflowOutput:
    """Separate interactive I/O from the single machine-readable final result."""

    as_json: bool = False
    details: bool = False

    def emit(self, text: str) -> None:
        value = json.loads(text)
        if self.as_json:
            typer.echo(json_output(value), err=True)
        elif isinstance(value, dict) and value.get("kind") in (
            "codex-owner-review-sharing-preview",
            "codex-owner-repair-sharing-preview",
            "codex-generated-repair-sharing-preview",
            "codex-fixture-sharing-preview",
            "owner-read-sharing-preview",
            "repository-sharing-preview",
        ):
            typer.echo(format_sharing_preview(value))
        elif isinstance(value, dict) and value.get("kind") in (
            "owner-policy-file-copy-preview",
            "owner-policy-file-stage-preview",
        ):
            typer.echo(format_file_workflow_preview(value))
        elif isinstance(value, dict) and value.get("kind") == "owner-read-copy-plan":
            typer.echo("Private copy review\n" + json_output(value))
        elif isinstance(value, dict) and value.get("kind") == "owner-policy-file-stage-result":
            typer.echo(
                "\n\n".join(
                    [
                        section("Owned-file stage observation", {"stage": value.get("stage")}),
                        *_file_checkpoint_parts(value.get("session_result")),
                    ]
                )
            )
        elif isinstance(value, dict) and value.get("kind") == "generated-repair-file-stage-preview":
            typer.echo(format_generated_file_stage_preview(value))
        elif (
            isinstance(value, dict)
            and value.get("kind") == "generated-repair-runtime-review-preview"
        ):
            typer.echo(format_generated_runtime_review(value))
        elif isinstance(value, dict) and value.get("kind") == "generated-repair-file-stage-result":
            typer.echo(_generated_file_checkpoint(value.get("session_result")))
        else:
            typer.echo(format_record(value, title="Workflow preview / observation"))

    def read(self, prompt: str) -> str:
        # input() without a prompt does not write to stdout. Do not echo supplied
        # answers or change their content: the runner owns exact-choice validation.
        typer.echo(quoted(prompt)[1:-1], nl=False, err=True)
        return input()

    def finish(self, value: dict, *, error: bool = False, preview: bool = False) -> None:
        if not self.as_json and value.get("kind") == "repository-suggestion":
            typer.echo(format_repository_suggestion(value), err=error)
        elif not self.as_json and value.get("kind") == "owner-read-suggestion":
            typer.echo(format_owner_read_suggestion(value), err=error)
        elif self.as_json or error:
            # Small redacted errors retain stderr in human mode; explicit JSON
            # mode includes application failures in its single stdout result.
            typer.echo(json_output(value), err=error and not self.as_json)
        elif preview and value.get("kind") == "owner-read-file-offline-preview":
            typer.echo(format_sharing_preview(value["sharing_preview"]))
            typer.echo(section("Reviewed local runtime", value["runtime_review"]))
            typer.echo(section("Separate file decisions", value["stages"]))
        elif preview and value.get("kind") == "owner-read-copy-offline-preview":
            typer.echo(format_sharing_preview(value["sharing_preview"]))
            typer.echo(section("Private files and expected observations", value["local_copy"]))
        elif preview:
            typer.echo(
                format_generated_file_offline_preview(value)
                if value.get("kind") == "codex-generated-file-workflow-preview"
                else format_sharing_preview(value)
            )
        elif value.get("kind") == "codex-owner-file-workflow":
            typer.echo(format_file_workflow_result(value))
        elif value.get("kind") == "codex-generated-repair-workflow":
            typer.echo(format_generated_repair_result(value, details=self.details))
        elif value.get("kind") == "codex-generated-file-workflow":
            typer.echo(format_generated_file_workflow_result(value, details=self.details))
        else:
            typer.echo(format_record(value), err=error)
