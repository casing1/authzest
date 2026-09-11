"""Offline defensive proposal artifacts. No provider, filesystem or execution access."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    _list,
    _object,
    _source_path,
    _text,
    _unique,
    canonical,
    decode,
    identity,
    validate_response,
)

PROPOSAL_SCHEMA_VERSION = "1.0"
CHECK_IDS = ("fixture-static-inventory", "fixture-regression-tests")
_RESERVED = {".git", ".github", ".venv", "venv", "node_modules", "build", "dist"}


def content_hash(text: str) -> str:
    """Hash exact UTF-8 content; no newline normalization."""
    return sha256(_text(text, 32_768).encode("utf-8")).hexdigest()


def source_snapshots(request: CodexAnalysisRequest) -> dict[str, str]:
    return {
        item["data"]["path"]: item["data"]["text"]
        for item in request.to_dict()["evidence"]
        if item["kind"] == "source"
    }


def _target_path(value: Any) -> str:
    path = _source_path(value)
    if (
        not path.endswith(".py")
        or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)
        or any(part.casefold() in _RESERVED or part.startswith(".") for part in path.split("/"))
    ):
        raise ContractError("Only selected existing Python source paths are supported")
    return path


def _text_items(value: Any, *, required: bool = False) -> list[str]:
    items = [_text(item) for item in _list(value, 32)]
    if required and not items:
        raise ContractError("Explicit uncertainty or expected outcome is required")
    return items


@dataclass(frozen=True, slots=True)
class ValidatedProposal:
    """A structural artifact, not a verified fix or an authorization credential.

    Consumers must call validate_proposal again with the current request/review.
    """

    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return decode(self.payload_json)

    @property
    def proposal_id(self) -> str:
        return "proposal-" + identity(self.to_dict())


def validate_proposal(
    raw: str,
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
) -> ValidatedProposal:
    request = CodexAnalysisRequest(request.payload_json)
    review = validate_response(review.payload_json, request)
    data = _object(
        decode(raw),
        {
            "schema_version",
            "request_id",
            "review_id",
            "changes",
            "rationale",
            "uncertainties",
            "side_effects",
            "verification",
        },
    )
    if (
        data["schema_version"] != PROPOSAL_SCHEMA_VERSION
        or data["request_id"] != request.request_id
        or data["review_id"] != identity(review.to_dict())
    ):
        raise ContractError("Proposal schema or input/review identity mismatch")
    _text(data["rationale"])
    _text_items(data["uncertainties"], required=True)
    _text_items(data["side_effects"])
    plan = _object(data["verification"], {"checks", "expectations"})
    checks = [_text(check, 64) for check in _list(plan["checks"], len(CHECK_IDS))]
    _unique(checks)
    if not checks or not set(checks) <= set(CHECK_IDS):
        raise ContractError("Unsupported verification check; commands are not accepted")
    _text_items(plan["expectations"], required=True)
    changes = _list(data["changes"], 8)
    if not changes:
        raise ContractError("A proposal must contain a change")
    sources = source_snapshots(request)
    _unique([path.casefold() for path in sources])
    evidence = {item["id"]: item for item in request.to_dict()["evidence"]}
    source_ids = {
        item["data"]["path"]: key for key, item in evidence.items() if item["kind"] == "source"
    }
    paths = []
    for change in changes:
        _object(change, {"path", "before_sha256", "after_text", "evidence_ids"})
        path = _target_path(change["path"])
        paths.append(path)
        if path not in sources:
            raise ContractError("Change is outside the selected existing sources")
        if change["before_sha256"] != content_hash(sources[path]):
            raise ContractError("Original source content hash mismatch")
        after = _text(change["after_text"], 32_768)
        if after == sources[path]:
            raise ContractError("No-op change")
        refs = [_text(ref, 128) for ref in _list(change["evidence_ids"])]
        _unique(refs)
        if not set(refs) <= evidence.keys() or source_ids[path] not in refs:
            raise ContractError("Change must cite its source and only existing evidence")
    _unique(paths)
    # Case-insensitive filesystems must not collapse different proposed targets.
    _unique([path.casefold() for path in paths])
    return ValidatedProposal(canonical(data))


def prepare_proposal(
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
    *,
    replacements: dict[str, str],
    rationale: str,
    uncertainties: tuple[str, ...],
    side_effects: tuple[str, ...],
    checks: tuple[str, ...],
    expectations: tuple[str, ...],
) -> ValidatedProposal:
    """Package explicit caller-authored drafts; never synthesize code or run a model."""
    sources = source_snapshots(request)
    source_ids = {
        item["data"]["path"]: item["id"]
        for item in request.to_dict()["evidence"]
        if item["kind"] == "source"
    }
    changes = []
    for path, after in sorted(replacements.items()):
        if path not in sources:
            raise ContractError("Change is outside the selected existing sources")
        changes.append(
            {
                "path": path,
                "before_sha256": content_hash(sources[path]),
                "after_text": after,
                "evidence_ids": [source_ids[path]],
            }
        )
    return validate_proposal(
        canonical(
            {
                "schema_version": PROPOSAL_SCHEMA_VERSION,
                "request_id": request.request_id,
                "review_id": identity(review.to_dict()),
                "changes": changes,
                "rationale": rationale,
                "uncertainties": list(uncertainties),
                "side_effects": list(side_effects),
                "verification": {"checks": list(checks), "expectations": list(expectations)},
            }
        ),
        request,
        review,
    )


def proposal_preview(
    proposal: ValidatedProposal,
    request: CodexAnalysisRequest,
    review: ValidatedResponse,
) -> dict[str, Any]:
    """Derive diffs from the exact bound texts; never accept a second, inconsistent diff."""
    proposal = validate_proposal(proposal.payload_json, request, review)
    data = proposal.to_dict()
    sources = source_snapshots(request)
    changes = []

    def source_lines(text: str) -> list[str]:
        # Unified diffs count LF-delimited lines, not Unicode paragraph separators.
        parts = text.split("\n")
        return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

    for change in data["changes"]:
        path = change["path"]
        lines = difflib.unified_diff(
            source_lines(sources[path]),
            source_lines(change["after_text"]),
            fromfile="a/" + path,
            tofile="b/" + path,
        )
        diff = "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in lines
        )
        changes.append(
            {
                "path": path,
                "before_sha256": change["before_sha256"],
                "after_sha256": content_hash(change["after_text"]),
                "diff": diff,
                "evidence_ids": change["evidence_ids"],
            }
        )
    return {
        "proposal_id": proposal.proposal_id,
        "request_id": request.request_id,
        "review_id": data["review_id"],
        "source_identity": request.to_dict()["source_identity"],
        "changes": changes,
        "rationale": data["rationale"],
        "uncertainties": data["uncertainties"],
        "side_effects": data["side_effects"],
        "verification": data["verification"],
        "applied": False,
        "verification_status": "not-run",
    }
