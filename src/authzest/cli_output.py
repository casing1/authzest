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
            "codex-fixture-sharing-preview",
        ):
            typer.echo(format_sharing_preview(value))
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
        else:
            typer.echo(format_record(value), err=error)
