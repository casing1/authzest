"""Source-only HTTP copy declarations, never file/session or execution authority."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from authzest.codex.contracts import ContractError, canonical, decode, identity
from authzest.codex.repository_copy_plan import _check_paths, _file
from authzest.codex.repository_http_proposal import (
    RepositoryHttpRequest,
    prepare_repository_http_preview,
    validate_repository_http_request,
    validate_repository_http_response,
)
from authzest.runner.repository_http_cases import RepositoryHttpCaseSet
from authzest.runner.repository_http_verification import build_repository_http_verification_plan

SCHEMA_VERSION = "2.0"
LAYOUT_VERSION = "2.0"
MAX_MATERIAL_BYTES = 131_072
MAX_JOURNAL_BYTES = 65_536


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RepositoryHttpCopyPlan:
    """Detached exact layout data; it cannot open or resume a private workspace."""

    payload_json: str

    def to_dict(self) -> dict:
        return decode(self.payload_json)

    @property
    def plan_id(self) -> str:
        return self.to_dict()["plan_id"]


def prepare_repository_http_copy_plan(
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet | None,
) -> RepositoryHttpCopyPlan | None:
    """Describe one new source-only copy using full validated HTTP/case bindings."""
    checked = validate_repository_http_request(request)
    context = checked.to_dict()
    response = validate_repository_http_response(canonical(response), checked)
    verification = build_repository_http_verification_plan(checked, response, cases)
    if verification is None:
        return None
    verified = verification.to_dict()
    preview = prepare_repository_http_preview(response, checked)
    source, policy = context["selection"]["files"]
    proposal = response["proposal"]
    source_path = "project/" + source["path"]
    files = [
        _file("selected-source", source_path, source["text"], source["path"]),
        _file("policy-snapshot", "evidence/policy.txt", policy["text"], policy["path"]),
        _file("source-before", "evidence/source.before", source["text"], source["path"]),
        _file("source-after", "evidence/source.after", proposal["after_text"], source["path"]),
    ]
    _check_paths(files)
    total = sum(item["utf8_bytes"] for item in files)
    if total > MAX_MATERIAL_BYTES:
        raise ContractError("HTTP private material byte limit exceeded", code="validation-budget")
    payload = {
        "kind": "repository-http-copy-plan",
        "schema_version": SCHEMA_VERSION,
        "layout_version": LAYOUT_VERSION,
        "request_id": checked.request_id,
        "request_identity": identity(context),
        "response_identity": identity(response),
        "verification_plan_id": verification.plan_id,
        "case_set_id": verified["case_set_id"],
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
            "materialization": "requires-current-request-response-cases-and-live-binding",
            "runtime": "separate-direct-current-phase-not-established",
            "evidence": "byte-identities-only-not-provider-origin-safety-or-permission",
        },
        "effects": {
            "workspace": "not-created",
            "original_files": "not-read-or-written-by-plan",
            "copy": "not-run",
            "execution": "not-run",
            "patch_application": "not-run",
            "restoration": "not-run",
            "approvals": "not-issued",
            "authorization": "unknown",
            "writes_authorized": False,
            "verified_fix": False,
        },
    }
    payload["plan_id"] = "repository-http-copy-plan-" + identity(payload)
    raw = canonical(payload)
    decode(raw)
    return RepositoryHttpCopyPlan(raw)


def validate_repository_http_copy_plan(
    plan: RepositoryHttpCopyPlan,
    request: RepositoryHttpRequest,
    response: dict,
    cases: RepositoryHttpCaseSet | None,
) -> RepositoryHttpCopyPlan:
    """Reconstruct the entire current HTTP layout; saved data is not authority."""
    if type(plan) is not RepositoryHttpCopyPlan:
        raise ContractError("Expected HTTP copy plan", code="validation-shape")
    expected = prepare_repository_http_copy_plan(request, response, cases)
    if expected is None or canonical(plan.to_dict()) != expected.payload_json:
        raise ContractError("HTTP copy plan mismatch", code="validation-identity")
    return expected
