"""Inert selected-source copy specifications; no files, sessions or approvals exist.

Hashes identify supplied bytes, not their provider, safety or permission to use them.
Only a later live implementation can bind a private root and obtain fresh decisions.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.codex.repository_proposal import (
    TEST_PATH,
    RepositoryProposalRequest,
    prepare_repository_preview,
    validate_repository_request,
    validate_repository_response,
)

SCHEMA_VERSION = "1.0"
LAYOUT_VERSION = "1.0"
MAX_MATERIAL_BYTES = 131_072
MAX_JOURNAL_BYTES = 65_536


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _file(role: str, path: str, text: str, origin: str | None) -> dict:
    return {
        "role": role,
        "workspace_path": path,
        "origin_relative_path": origin,
        "utf8_bytes": len(text.encode("utf-8")),
        "sha256": _hash(text),
    }


def _check_paths(files: list[dict]) -> None:
    # Preserve exact spelling, but reject aliases on case/normalization-insensitive hosts.
    def key(path: str) -> tuple[str, ...]:
        decomposed = unicodedata.normalize("NFD", path)
        return tuple(unicodedata.normalize("NFD", decomposed.casefold()).split("/"))

    paths = [key(file["workspace_path"]) for file in files]
    paths.append(("record.json",))
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            if left[: len(right)] == right or right[: len(left)] == left:
                raise ContractError("Private workspace paths overlap", code="validation-identity")


@dataclass(frozen=True, slots=True)
class RepositoryCopyPlan:
    """Detached metadata, never a live workspace handle or an execution decision."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return self.to_dict()["plan_id"]


def prepare_repository_copy_plan(
    request: RepositoryProposalRequest, response: dict
) -> RepositoryCopyPlan | None:
    """Describe a fresh private layout from current validated data; perform no effects."""
    checked_request = validate_repository_request(request)
    context = checked_request.to_dict()
    checked_response = validate_repository_response(canonical(response), checked_request)
    if checked_response["status"] != "proposed-change":
        return None
    preview = prepare_repository_preview(checked_response, checked_request)
    selection, proposal = context["selection"], checked_response["proposal"]
    source, policy, *contexts = selection["files"]
    source_path = "project/" + source["path"]
    files = [
        _file("selected-source", source_path, source["text"], source["path"]),
        *[
            _file("selected-context", "project/" + file["path"], file["text"], file["path"])
            for file in contexts
        ],
        _file("generated-test", "project/" + TEST_PATH, proposal["test_text"], None),
        _file("policy-snapshot", "evidence/policy.txt", policy["text"], policy["path"]),
        _file("source-before", "evidence/source.before", source["text"], source["path"]),
        _file("source-after", "evidence/source.after", proposal["after_text"], source["path"]),
        _file("test-snapshot", "evidence/test.txt", proposal["test_text"], None),
    ]
    _check_paths(files)
    total = sum(file["utf8_bytes"] for file in files)
    if total > MAX_MATERIAL_BYTES:
        raise ContractError("Private material byte limit exceeded", code="validation-budget")
    payload = {
        "kind": "repository-copy-plan",
        "schema_version": SCHEMA_VERSION,
        "layout_version": LAYOUT_VERSION,
        "request_id": checked_request.request_id,
        "request_identity": identity(context),
        "response_identity": identity(checked_response),
        "files": files,
        "material_utf8_bytes": total,
        "material_max_utf8_bytes": MAX_MATERIAL_BYTES,
        "source_transition": {
            "workspace_path": source_path,
            "before_sha256": source["sha256"],
            "after_sha256": _hash(proposal["after_text"]),
            "restore_sha256": source["sha256"],
        },
        "diff_identities": [
            {
                "path": change["path"],
                "before_sha256": change["before_sha256"],
                "after_sha256": change["after_sha256"],
                "diff_sha256": _hash(change["diff"]),
            }
            for change in preview["changes"]
        ],
        "generated_test": {
            "workspace_path": "project/" + TEST_PATH,
            "basis": "private-new-artifact",
            "original_path_status": "uninspected",
            "original_absence_established": False,
        },
        "journal": {
            "workspace_path": "record.json",
            "role": "host-journal",
            "max_utf8_bytes": MAX_JOURNAL_BYTES,
            "binding": "separate-host-metadata-no-plan-hash-cycle",
            "authority": "none",
        },
        "requirements": {
            "fresh_root": "required-before-copy-not-bound",
            "selected_original_freshness": "required-before-copy-not-checked",
            "live_session": "required-current-process-no-open-or-reopen-from-plan",
            "decisions": "required-per-step-single-use-max-300-seconds-not-issued",
            "materialization": "requires-current-validated-request-response-and-live-binding",
            "evidence": "byte-identities-only-not-provider-origin-safety-or-permission",
        },
        "effects": {
            "workspace": "not-created",
            "original_files": "not-read-or-written",
            "copy": "not-run",
            "execution": "not-run",
            "patch_application": "not-run",
            "restoration": "not-run",
            "approvals": "not-issued",
            "authorization": "unknown",
        },
    }
    payload["plan_id"] = "repository-copy-plan-" + identity(payload)
    return RepositoryCopyPlan(canonical(payload))


def validate_repository_copy_plan(
    plan: RepositoryCopyPlan, request: RepositoryProposalRequest, response: dict
) -> RepositoryCopyPlan:
    """Rebuild against current inputs; canonical metadata is no runtime authority."""
    if type(plan) is not RepositoryCopyPlan:
        raise ContractError("Expected repository copy plan", code="validation-shape")
    expected = prepare_repository_copy_plan(request, response)
    if expected is None or canonical(plan.to_dict()) != expected.payload_json:
        raise ContractError("Repository copy plan mismatch", code="validation-identity")
    return expected
