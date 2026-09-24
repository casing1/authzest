import builtins
import copy
import dataclasses
import json
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

from authzest.codex.contracts import (
    MAX_JSON_BYTES,
    CodexAnalysisRequest,
    ContractError,
    canonical,
    identity,
)
from authzest.codex.owner_policy_review import (
    OWNER_POLICY_MAIN_SOURCE,
    OWNER_POLICY_PROMPT_VERSION,
    OWNER_POLICY_REVIEW_SCHEMA_VERSION,
    OWNER_POLICY_SOURCE,
    OWNER_POLICY_TEXT,
    OwnerPolicyReview,
    build_owner_policy_request,
    owner_policy_output_schema,
    owner_policy_prompt,
    validate_owner_policy_draft,
    validate_owner_policy_result,
)
from authzest.runner import ScanRunner


@pytest.fixture
def context():
    return build_owner_policy_request("owner-policy-offline-model")


def response_data(request):
    """Caller-authored transport stand-in, never a live or semantically validated result."""
    evidence = request.to_dict()["evidence"]
    refs = [item["id"] for item in evidence if item["kind"] in ("source", "policy")]
    case_refs = [
        item["id"]
        for item in evidence
        if item["kind"] == "policy"
        or (item["kind"] == "source" and item["data"]["path"] == "policy.py")
    ]
    return {
        "answers": [
            {
                "question_id": "review",
                "status": "hypothesis",
                "answer": "The pure policy intends authenticated owners with reports:read.",
                "explanation": "Trusted authentication is unconfigured; no patch is proposed.",
                "evidence_ids": refs,
                "assumptions": ["The supplied principal and ownership context are trusted."],
                "unknowns": ["Endpoint enforcement has not been tested."],
                "review_questions": ["How will a trusted principal be supplied?"],
            }
        ],
        "cases": [
            {
                "id": "owner-read",
                "principal": {
                    "subject": "alice",
                    "authenticated": True,
                    "scopes": ["reports:read"],
                },
                "report": {"report_id": "report-001", "owner_id": "alice"},
                "expected": True,
                "reason": "A trusted authenticated owner has the required exact scope.",
                "evidence_ids": case_refs,
            }
        ],
    }


def test_packaged_snapshots_exactly_match_both_maintained_source_files():
    example = Path(__file__).parents[1] / "examples/fastapi_owner_policy"
    assert (example / "main.py").read_text(encoding="utf-8") == OWNER_POLICY_MAIN_SOURCE
    assert (example / "policy.py").read_text(encoding="utf-8") == OWNER_POLICY_SOURCE


def test_in_memory_route_evidence_matches_maintained_static_scan(context):
    example = Path(__file__).parents[1] / "examples/fastapi_owner_policy"
    report = ScanRunner().run(example)
    routes = [item["data"] for item in context.to_dict()["evidence"] if item["kind"] == "route"]
    assert report.python_files == 2
    assert report.analysis_status == "bounded"
    assert not report.parse_errors
    assert not report.diagnostics
    assert routes == [route.to_dict(report.root) for route in report.routes]


def test_request_is_source_minimized_deterministic_and_uses_in_memory_parser(context, tmp_path):
    request = context
    payload = request.to_dict()
    assert build_owner_policy_request("owner-policy-offline-model").request_id == request.request_id
    assert payload["config"] == {
        "provider": "codex-app-server",
        "model": "owner-policy-offline-model",
        "adapter_version": "0.1",
        "prompt_version": OWNER_POLICY_PROMPT_VERSION,
        "temperature": None,
        "seed": None,
    }
    assert payload["schema_version"] == "1.1"
    assert payload["mode"] == "evidence-plus-model"
    assert payload["source_revision"] is None
    sources = {
        item["data"]["path"]: item["data"]["text"]
        for item in payload["evidence"]
        if item["kind"] == "source"
    }
    assert sources == {"main.py": OWNER_POLICY_MAIN_SOURCE, "policy.py": OWNER_POLICY_SOURCE}
    assert payload["source_identity"] == identity(sources)
    assert [item["data"] for item in payload["evidence"] if item["kind"] == "policy"] == [
        OWNER_POLICY_TEXT
    ]
    routes = [item["data"] for item in payload["evidence"] if item["kind"] == "route"]
    assert len(routes) == 1
    assert routes[0]["file"] == "main.py"
    assert routes[0]["path"] == "/reports/{report_id}"
    assert routes[0]["line"] == 24
    assert routes[0]["methods"] == ["GET"]
    assert routes[0]["dependencies"][0]["kind"] == "Security"
    assert routes[0]["dependencies"][0]["scopes"] == ["reports:read"]
    limits = next(item["data"] for item in payload["evidence"] if item["kind"] == "limitations")
    assert limits["analysis_status"] == "bounded"
    assert limits["security_verdict"] == "unknown"
    assert str(tmp_path) not in request.payload_json
    assert "owner-policy-source" not in request.payload_json
    assert "cases.json" not in request.payload_json
    assert "frozen_evaluation_corpus" not in request.payload_json


def test_core_never_reads_writes_imports_target_starts_process_or_network(context, monkeypatch):
    data = canonical(response_data(context))
    original_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        assert name != "fastapi"
        assert not name.startswith("examples.fastapi_owner_policy")
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Owner-policy draft contracts must not access filesystem or execute a target")

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    request = build_owner_policy_request("owner-policy-offline-model")
    assert request.request_id == context.request_id
    owner_policy_prompt(request)
    owner_policy_output_schema(request)
    result = validate_owner_policy_draft(data, request, usage=None)
    assert validate_owner_policy_result(result, request) == result


@pytest.mark.parametrize("model", ["", " spaces ", "a\nmodel", "a" * 129, None, 1])
def test_invalid_explicit_model_fails_before_parsing(model, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid model identity must fail before parsing")

    monkeypatch.setattr("authzest.codex.owner_policy_review.FastAPIRouteParser", forbidden)
    with pytest.raises(ContractError):
        build_owner_policy_request(model)


def changed_request(request, mutation):
    payload = request.to_dict()
    if mutation == "provider":
        payload["config"]["provider"] = "other-provider"
    elif mutation == "temperature":
        payload["config"]["temperature"] = 0
    elif mutation == "seed":
        payload["config"]["seed"] = 1
    elif mutation == "prompt":
        payload["config"]["prompt_version"] = "extra-instructions"
    elif mutation == "revision":
        payload["source_revision"] = "a" * 40
    elif mutation == "question":
        payload["questions"][0]["text"] = "An unapproved extra task."
    elif mutation == "source":
        item = next(item for item in payload["evidence"] if item["kind"] == "source")
        item["data"]["text"] += "\n# Changed source snapshot.\n"
        item["id"] = "ev-" + identity({"kind": item["kind"], "data": item["data"]})
        payload["source_identity"] = identity(
            {
                item["data"]["path"]: item["data"]["text"]
                for item in payload["evidence"]
                if item["kind"] == "source"
            }
        )
    elif mutation == "extra-source":
        item = {"kind": "source", "data": {"path": "other.py", "text": "x = 1\n"}}
        payload["evidence"].append({"id": "ev-" + identity(item), **item})
        payload["source_identity"] = identity(
            {
                item["data"]["path"]: item["data"]["text"]
                for item in payload["evidence"]
                if item["kind"] == "source"
            }
        )
    else:
        item = next(item for item in payload["evidence"] if item["kind"] == "policy")
        item["data"] = "An unapproved policy instead."
        item["id"] = "ev-" + identity({"kind": item["kind"], "data": item["data"]})
    return CodexAnalysisRequest(canonical(payload))


@pytest.mark.parametrize("helper", ["prompt", "schema", "draft", "result"])
@pytest.mark.parametrize(
    "mutation",
    [
        "provider",
        "temperature",
        "seed",
        "prompt",
        "revision",
        "question",
        "source",
        "extra-source",
        "policy",
    ],
)
def test_every_boundary_rejects_changed_owned_request(context, helper, mutation):
    request = changed_request(context, mutation)
    raw = canonical(response_data(context))
    result = validate_owner_policy_draft(raw, context, usage=None)
    with pytest.raises(ContractError, match="exact packaged owner-policy"):
        if helper == "prompt":
            owner_policy_prompt(request)
        elif helper == "schema":
            owner_policy_output_schema(request)
        elif helper == "draft":
            validate_owner_policy_draft(raw, request, usage=None)
        else:
            validate_owner_policy_result(result, request)


def test_prompt_exactly_previews_request_and_excludes_case_labels(context):
    prompt = owner_policy_prompt(context)
    assert OWNER_POLICY_PROMPT_VERSION in prompt
    assert "Do not use tools" in prompt
    assert "not executable tests" in prompt
    assert "unreviewed suggestions" in prompt
    assert "do not invent a vulnerability or force a patch" in prompt
    assert "not-run" in prompt
    assert json.loads(prompt.split("REQUEST DATA:\n", 1)[1]) == context.to_dict()
    assert "owner-read" not in prompt


def test_schema_has_exact_keys_at_every_object_and_no_host_fields(context):
    schema = owner_policy_output_schema(context)
    assert schema["title"].endswith(OWNER_POLICY_REVIEW_SCHEMA_VERSION)
    assert set(schema["properties"]) == {"answers", "cases"}
    assert schema["properties"]["cases"]["minItems"] == 1
    assert schema["properties"]["cases"]["maxItems"] == 16
    assert schema["properties"]["answers"]["items"]["properties"]["status"]["enum"] == [
        "hypothesis",
        "unknown",
    ]
    pending = [schema]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("type") == "object":
                assert item["additionalProperties"] is False
                assert set(item["required"]) == set(item["properties"])
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    schema["properties"].clear()
    assert owner_policy_output_schema(context)["properties"]


@pytest.mark.parametrize("usage", [None, {"input_tokens": 10, "output_tokens": 20}])
def test_host_binds_identity_and_unreviewed_unexecuted_statuses(context, usage):
    raw = response_data(context)
    result = validate_owner_policy_draft(canonical(raw), context, usage=usage)
    data = result.to_dict()
    assert data["schema_version"] == OWNER_POLICY_REVIEW_SCHEMA_VERSION
    assert data["request_id"] == context.request_id
    assert data["source_identity"] == context.to_dict()["source_identity"]
    assert data["review"] == result.review.to_dict()
    assert data["review"]["usage"] == usage
    assert data["cases"] == raw["cases"]
    assert data["status"] == "draft"
    assert data["case_authorship"] == "model-authored"
    assert data["case_review_status"] == "unreviewed"
    assert data["execution_status"] == "not-run"
    assert data["authorization_status"] == "unknown"
    assert validate_owner_policy_result(result, context) == result
    data["cases"].clear()
    assert result.to_dict()["cases"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.payload_json = "{}"


def test_labels_are_not_evaluated_or_promoted_to_approved_ground_truth(context):
    raw = response_data(context)
    # Deliberately inconsistent with the intended rule: structural validation is not grading.
    raw["cases"][0]["expected"] = False
    result = validate_owner_policy_draft(canonical(raw), context, usage=None).to_dict()
    assert result["cases"][0]["expected"] is False
    assert result["case_review_status"] == "unreviewed"
    assert result["execution_status"] == "not-run"


def test_unknown_review_and_nullable_missing_context_cases_are_supported(context):
    raw = response_data(context)
    raw["answers"][0].update(status="unknown", answer=None)
    raw["cases"][0].update(principal=None, report=None, expected=False)
    data = validate_owner_policy_draft(canonical(raw), context, usage=None).to_dict()
    assert data["review"]["answers"][0]["answer"] is None
    assert data["cases"][0]["principal"] is None
    assert data["cases"][0]["report"] is None


@pytest.mark.parametrize("value", [None, "", " ", " alice "])
def test_synthetic_identifiers_preserve_denial_boundary_values_without_normalization(
    context, value
):
    raw = response_data(context)
    raw["cases"][0]["principal"]["subject"] = value
    raw["cases"][0]["report"]["owner_id"] = value
    raw["cases"][0]["report"]["report_id"] = value
    result = validate_owner_policy_draft(canonical(raw), context, usage=None).to_dict()
    assert result["cases"][0]["principal"]["subject"] == value
    assert result["cases"][0]["report"]["report_id"] == value


def test_sixteen_unique_case_drafts_are_allowed_without_running_them(context):
    raw = response_data(context)
    raw["cases"] = [{**raw["cases"][0], "id": f"case-{index}"} for index in range(16)]
    assert (
        len(validate_owner_policy_draft(canonical(raw), context, usage=None).to_dict()["cases"])
        == 16
    )


@pytest.mark.parametrize("where", ["root", "answer", "case", "principal", "report"])
@pytest.mark.parametrize("extra", ["code", "commands", "diff", "approved", "execution_status"])
def test_model_cannot_add_code_execution_or_approval_fields(context, where, extra):
    raw = response_data(context)
    target = {
        "root": raw,
        "answer": raw["answers"][0],
        "case": raw["cases"][0],
        "principal": raw["cases"][0]["principal"],
        "report": raw["cases"][0]["report"],
    }[where]
    target[extra] = "untrusted claim"
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(raw), context, usage=None)


@pytest.mark.parametrize("kind", ["main.py", "policy.py", "policy"])
def test_every_answer_must_cite_both_exact_sources_and_policy(context, kind):
    raw = response_data(context)
    evidence_id = next(
        item["id"]
        for item in context.to_dict()["evidence"]
        if (item["kind"] == "policy" and kind == "policy")
        or (item["kind"] == "source" and item["data"]["path"] == kind)
    )
    raw["answers"][0]["evidence_ids"].remove(evidence_id)
    with pytest.raises(ContractError, match="both source snapshots"):
        validate_owner_policy_draft(canonical(raw), context, usage=None)


@pytest.mark.parametrize("index", [0, 1])
def test_every_case_must_cite_policy_source_and_policy(context, index):
    raw = response_data(context)
    raw["cases"][0]["evidence_ids"].pop(index)
    with pytest.raises(ContractError, match="cite policy.py"):
        validate_owner_policy_draft(canonical(raw), context, usage=None)


@pytest.mark.parametrize(
    "mutation",
    [
        "empty-cases",
        "too-many-cases",
        "case-is-list",
        "case-missing-key",
        "id-blank",
        "id-command-like",
        "id-too-long",
        "duplicate-id",
        "expected-integer",
        "expected-string",
        "principal-list",
        "principal-missing-field",
        "authentication-integer",
        "subject-number",
        "subject-too-long",
        "subject-control",
        "scopes-string",
        "scope-number",
        "scope-blank",
        "scope-too-long",
        "too-many-scopes",
        "duplicate-scope",
        "report-list",
        "report-missing",
        "report-id-number",
        "owner-id-too-long",
        "reason-blank",
        "reason-too-long",
        "unknown-ref",
        "duplicate-ref",
        "refs-string",
        "confirmed-answer",
        "no-answer",
        "duplicate-answer",
        "answer-no-unknown",
        "model-usage",
    ],
)
def test_invalid_draft_shapes_types_bounds_and_citations_are_rejected(context, mutation):
    raw = response_data(context)
    case = raw["cases"][0]
    principal = case["principal"]
    if mutation == "empty-cases":
        raw["cases"] = []
    elif mutation == "too-many-cases":
        raw["cases"] = [{**case, "id": f"case-{index}"} for index in range(17)]
    elif mutation == "case-is-list":
        raw["cases"] = [[]]
    elif mutation == "case-missing-key":
        case.pop("reason")
    elif mutation == "id-blank":
        case["id"] = " "
    elif mutation == "id-command-like":
        case["id"] = "case;echo text"
    elif mutation == "id-too-long":
        case["id"] = "a" * 65
    elif mutation == "duplicate-id":
        raw["cases"].append(copy.deepcopy(case))
    elif mutation == "expected-integer":
        case["expected"] = 1
    elif mutation == "expected-string":
        case["expected"] = "true"
    elif mutation == "principal-list":
        case["principal"] = []
    elif mutation == "principal-missing-field":
        principal.pop("authenticated")
    elif mutation == "authentication-integer":
        principal["authenticated"] = 1
    elif mutation == "subject-number":
        principal["subject"] = 1
    elif mutation == "subject-too-long":
        principal["subject"] = "a" * 129
    elif mutation == "subject-control":
        principal["subject"] = "alice\n"
    elif mutation == "scopes-string":
        principal["scopes"] = "reports:read"
    elif mutation == "scope-number":
        principal["scopes"] = [1]
    elif mutation == "scope-blank":
        principal["scopes"] = [" "]
    elif mutation == "scope-too-long":
        principal["scopes"] = ["a" * 129]
    elif mutation == "too-many-scopes":
        principal["scopes"] = [str(index) for index in range(17)]
    elif mutation == "duplicate-scope":
        principal["scopes"] = ["reports:read", "reports:read"]
    elif mutation == "report-list":
        case["report"] = []
    elif mutation == "report-missing":
        case["report"].pop("owner_id")
    elif mutation == "report-id-number":
        case["report"]["report_id"] = 1
    elif mutation == "owner-id-too-long":
        case["report"]["owner_id"] = "a" * 129
    elif mutation == "reason-blank":
        case["reason"] = " "
    elif mutation == "reason-too-long":
        case["reason"] = "a" * 4097
    elif mutation == "unknown-ref":
        case["evidence_ids"].append("ev-" + "0" * 64)
    elif mutation == "duplicate-ref":
        case["evidence_ids"].append(case["evidence_ids"][0])
    elif mutation == "refs-string":
        case["evidence_ids"] = "policy"
    elif mutation == "confirmed-answer":
        raw["answers"][0]["status"] = "confirmed"
    elif mutation == "no-answer":
        raw["answers"] = []
    elif mutation == "duplicate-answer":
        raw["answers"].append(copy.deepcopy(raw["answers"][0]))
    elif mutation == "answer-no-unknown":
        raw["answers"][0].update(status="unknown", answer=None, unknowns=[])
    else:
        raw["usage"] = {"input_tokens": 0, "output_tokens": 0}
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(raw), context, usage=None)


@pytest.mark.parametrize(
    "raw", [None, "[]", '{"answers":[],"answers":[],"cases":[]}', "x" * 262145]
)
def test_malformed_duplicate_key_and_oversized_json_rejected(context, raw):
    with pytest.raises(ContractError):
        validate_owner_policy_draft(raw, context, usage=None)


def test_host_bound_result_metadata_also_counts_toward_json_budget(context):
    raw = response_data(context)
    raw["answers"][0]["assumptions"] = ["a" * 4096] * 32
    raw["answers"][0]["unknowns"] = ["a" * 4096] * 31
    remaining = MAX_JSON_BYTES - len(canonical(raw).encode("utf-8")) - 3
    assert 1 <= remaining <= 4096
    raw["answers"][0]["unknowns"].append("a" * remaining)
    assert len(canonical(raw).encode("utf-8")) == MAX_JSON_BYTES
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(raw), context, usage=None)


@pytest.mark.parametrize(
    "usage",
    [{}, {"input_tokens": True, "output_tokens": 0}, {"input_tokens": -1, "output_tokens": 0}],
)
def test_invalid_transport_usage_rejected(context, usage):
    with pytest.raises(ContractError):
        validate_owner_policy_draft(canonical(response_data(context)), context, usage=usage)


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "request",
        "source",
        "status",
        "authorship",
        "case-review",
        "execution",
        "authorization",
        "review-id",
        "review-model",
        "review-extra",
        "extra",
        "case-ref",
        "case-extra",
        "review-missing",
        "review-not-dict",
    ],
)
def test_forged_typed_results_are_revalidated_not_trusted(context, mutation):
    data = validate_owner_policy_draft(
        canonical(response_data(context)), context, usage=None
    ).to_dict()
    field_changes = {
        "schema": ("schema_version", "999"),
        "request": ("request_id", "request-" + "a" * 64),
        "source": ("source_identity", "a" * 64),
        "status": ("status", "approved"),
        "authorship": ("case_authorship", "maintainer-authored"),
        "case-review": ("case_review_status", "approved"),
        "execution": ("execution_status", "passed"),
        "authorization": ("authorization_status", "secure"),
    }
    if mutation in field_changes:
        field, value = field_changes[mutation]
        data[field] = value
    elif mutation == "review-id":
        data["review"]["request_id"] = "request-" + "a" * 64
    elif mutation == "review-model":
        data["review"]["identity"]["model"] = "different-model"
    elif mutation == "review-extra":
        data["review"]["approved"] = True
    elif mutation == "extra":
        data["approved"] = True
    elif mutation == "case-ref":
        data["cases"][0]["evidence_ids"] = []
    elif mutation == "case-extra":
        data["cases"][0]["executed"] = True
    elif mutation == "review-missing":
        data["review"].pop("usage")
    else:
        data["review"] = []
    forged = OwnerPolicyReview(canonical(data))
    with pytest.raises(ContractError):
        validate_owner_policy_result(forged, context)


@pytest.mark.parametrize("bad", [None, {}, object.__new__(OwnerPolicyReview)])
def test_invalid_or_uninitialized_typed_result_rejected(context, bad):
    with pytest.raises(ContractError):
        validate_owner_policy_result(bad, context)


def test_forged_request_snapshot_is_revalidated_even_without_constructor_checks(context):
    forged = object.__new__(CodexAnalysisRequest)
    object.__setattr__(forged, "payload_json", context.payload_json.replace("main.py", "other.py"))
    with pytest.raises(ContractError):
        owner_policy_prompt(forged)
