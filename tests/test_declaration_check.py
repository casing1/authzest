"""Supplied source declarations only: no generated tests or authorization verdicts."""

import asyncio
import builtins
import json
import os
import socket
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path, PureWindowsPath

import pytest

from authzest.analyzer import declarations
from authzest.analyzer.declarations import DeclarationTarget, compare_declarations
from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    canonical,
    identity,
    prepare_request,
    validate_response,
)
from authzest.codex.expectations import prepare_expectation_manifest
from authzest.codex.mock import MockCodexAdapter, scripted_response
from authzest.codex.preview import (
    ValidatedPreviewBundle,
    prepare_preview_bundle,
    validate_preview_bundle,
)
from authzest.codex.proposals import prepare_proposal
from authzest.models import ScanReport
from authzest.parser.fastapi import FastAPIRouteParser
from authzest.runner import ScanRunner
from authzest.runner.proposal_check import check_proposal

ROOT = Path("/supplied-snapshot")
BASE = (
    "from fastapi import Depends, FastAPI, Security\n"
    "app = FastAPI()\n\n"
    "def current_user():\n    return None\n\n"
    '@app.get("/reports")\n'
    'def reports():\n    return {"ok": True}\n'
)
WITH_DEPENDENCY = BASE.replace("def reports():", "def reports(user=Depends(current_user)):")
WITH_SCOPES = BASE.replace(
    "def reports():", 'def reports(user=Security(current_user, scopes=["reports:read"])):'
)


def route_for(source=BASE, *, path="main.py", index=0):
    parsed = FastAPIRouteParser().parse_source(source, ROOT / path)
    assert parsed.error is None and parsed.routes
    return parsed.routes[index].to_dict(ROOT)


def bundle_for(
    before=BASE,
    after=WITH_DEPENDENCY,
    *,
    observation="dependency-declarations",
    expected=None,
    path="main.py",
    mutate_request=None,
    extra_sources=None,
    extra_changes=None,
):
    """Caller-authored examples; do not consume evaluation labels or a live provider."""
    parsed = FastAPIRouteParser().parse_source(before, ROOT / path)
    assert parsed.routes
    report = ScanReport(
        root=ROOT,
        python_files=1,
        routes=parsed.routes,
        diagnostics=parsed.diagnostics,
        parse_errors=(parsed.error,) if parsed.error else (),
    )
    source_map = {path: before, **(extra_sources or {})}
    request = prepare_request(
        report,
        registration_ids=(parsed.routes[0].to_dict(ROOT)["registration_id"],),
        sources=source_map,
        policies=("Review explicitly declared dependencies; enforcement remains unknown.",),
        questions=(("review", "Review these supplied source declarations only."),),
    )
    if mutate_request:
        data = request.to_dict()
        mutate_request(data)
        for item in data["evidence"]:
            item["id"] = "ev-" + identity({"kind": item["kind"], "data": item["data"]})
        request = CodexAnalysisRequest(canonical(data))
    review = validate_response(scripted_response(request, {"review": None}), request)
    proposal = prepare_proposal(
        request,
        review,
        replacements={path: after, **(extra_changes or {})},
        rationale="Caller-authored source declaration comparison example.",
        uncertainties=("No source execution or enforcement has been checked.",),
        side_effects=(),
        checks=("fixture-static-inventory",),
        expectations=("Compare declarations, never infer access-control enforcement.",),
    )
    evidence = {item["kind"]: item for item in request.to_dict()["evidence"]}
    source = next(
        item
        for item in request.to_dict()["evidence"]
        if item["kind"] == "source" and item["data"]["path"] == path
    )
    manifest = prepare_expectation_manifest(
        request,
        review,
        proposal,
        expectations=[
            {
                "id": "declaration-target",
                "source_evidence_id": source["id"],
                "route_evidence_id": evidence["route"]["id"],
                "policy_evidence_ids": [evidence["policy"]["id"]],
                "observation": observation,
                "expected": {"count": 1} if expected is None else expected,
                "limitations": [
                    "Declarations do not establish callable execution or authorization."
                ],
            }
        ],
    )
    return prepare_preview_bundle(request, review, proposal, manifest)


def compare(
    before=BASE,
    after=WITH_DEPENDENCY,
    *,
    observation="dependency-declarations",
    expected=None,
    baseline=None,
):
    target = DeclarationTarget(
        route_for(before) if baseline is None else baseline,
        observation,
        {"count": 1} if expected is None else expected,
    )
    return compare_declarations(
        path="main.py", before_text=before, after_text=after, targets=[target]
    )[0]


@pytest.mark.parametrize("path", ["main.py", "pkg/api.py", "pkg/nested/api.py"])
@pytest.mark.parametrize("windows_paths", [False, True])
def test_nested_wire_labels_and_ids_survive_host_path_semantics(monkeypatch, path, windows_paths):
    after = "# Shift all declaration locations.\n\n" + WITH_SCOPES
    bundle = bundle_for(
        before=WITH_DEPENDENCY,
        after=after,
        path=path,
        observation="scope-declarations",
        expected={"scopes": ["reports:read"]},
    )
    baseline = next(
        item["data"] for item in bundle.to_dict()["request"]["evidence"] if item["kind"] == "route"
    )
    after_bundle = bundle_for(before=after, after=after + "# another draft\n", path=path)
    after_evidence = next(
        item["data"]
        for item in after_bundle.to_dict()["request"]["evidence"]
        if item["kind"] == "route"
    )
    # prepare_request establishes POSIX wire labels, including on a Windows host.
    for evidence in (baseline, after_evidence):
        assert evidence["file"] == path
        assert evidence["registration"]["declaration"]["file"] == path
        assert evidence["registration"]["owner"]["location"]["file"] == path
        assert evidence["registration"]["application"]["location"]["file"] == path
        for field in ("dependencies", "effective_dependencies"):
            assert evidence[field]
            assert all(item["location"]["file"] == path for item in evidence[field])
    assert baseline["registration_id"] != after_evidence["registration_id"]
    original_baseline = deepcopy(baseline)
    native_report = check_proposal(bundle)
    if windows_paths:
        # Only choose the host path flavour. Real parsing, evidence serialization and
        # comparison still run; no comparator or result is replaced by a test double.
        monkeypatch.setattr(declarations, "Path", PureWindowsPath)
    compared = compare_declarations(
        path=path,
        before_text=WITH_DEPENDENCY,
        after_text=after,
        targets=[DeclarationTarget(baseline, "scope-declarations", {"scopes": ["reports:read"]})],
    )[0]
    assert compared["status"] == "matched", compared
    assert compared["before_observed"] == {"scopes": []}
    assert compared["observed"] == {"scopes": ["reports:read"]}
    assert compared["after_registration_id"] == after_evidence["registration_id"]
    report = check_proposal(bundle)
    assert report == native_report
    assert report["results"][0]["status"] == "matched"
    assert report["results"][0]["path"] == path
    assert report["results"][0]["baseline_registration_id"] == baseline["registration_id"]
    assert report["results"][0]["after_registration_id"] == after_evidence["registration_id"]
    assert baseline == original_baseline


@pytest.mark.parametrize("windows_paths", [False, True])
def test_path_normalization_does_not_match_another_canonical_source(monkeypatch, windows_paths):
    foreign = bundle_for(before=WITH_DEPENDENCY, after=WITH_SCOPES, path="other/api.py")
    baseline = next(
        item["data"] for item in foreign.to_dict()["request"]["evidence"] if item["kind"] == "route"
    )
    if windows_paths:
        monkeypatch.setattr(declarations, "Path", PureWindowsPath)
    result = compare_declarations(
        path="pkg/api.py",
        before_text=WITH_DEPENDENCY,
        after_text=WITH_SCOPES,
        targets=[DeclarationTarget(baseline, "dependency-declarations", {"count": 1})],
    )[0]
    assert result["status"] == "unknown" and result["reason"] == "baseline-evidence-mismatch"
    assert (
        result["before_observed"] is result["observed"] is result["after_registration_id"] is None
    )


def assert_unknown(result):
    assert set(result) == {
        "status",
        "reason",
        "before_observed",
        "observed",
        "after_registration_id",
    }
    assert result["status"] == "unknown" and result["reason"]
    assert (
        result["before_observed"] is result["observed"] is result["after_registration_id"] is None
    )


@pytest.mark.parametrize("expected,status", [(0, "mismatched"), (1, "matched"), (2, "mismatched")])
def test_dependency_declarations_compare_exact_count_not_enforcement(expected, status):
    result = compare(expected={"count": expected})
    assert result["status"] == status
    assert result["before_observed"] == {"count": 0}
    assert result["observed"] == {"count": 1}
    assert result["after_registration_id"] == route_for(WITH_DEPENDENCY)["registration_id"]
    assert result["reason"]


def test_application_decorator_and_parameter_annotations_count_separately():
    after = (
        BASE.replace("from fastapi", "from typing import Annotated\nfrom fastapi")
        .replace("app = FastAPI()", "app = FastAPI(dependencies=[Depends(current_user)])")
        .replace(
            '@app.get("/reports")', '@app.get("/reports", dependencies=[Depends(current_user)])'
        )
        .replace("def reports():", "def reports(user: Annotated[str, Depends(current_user)]):")
    )
    result = compare(after=after, expected={"count": 3})
    assert result["status"] == "matched" and result["observed"] == {"count": 3}


@pytest.mark.parametrize(
    "scopes,status",
    [
        (["reports:read", "reports:write"], "matched"),
        (["reports:write", "reports:read"], "matched"),
        (["reports:read"], "mismatched"),
        ([], "mismatched"),
    ],
)
def test_scope_comparison_is_sorted_unique_union_of_literal_security_declarations(scopes, status):
    after = WITH_SCOPES.replace(
        '@app.get("/reports")',
        '@app.get("/reports", dependencies=[Security(current_user, '
        'scopes=["reports:write", "reports:read", "reports:write"]), Depends(current_user)])',
    )
    result = compare(
        before=WITH_SCOPES,
        after=after,
        observation="scope-declarations",
        expected={"scopes": scopes},
    )
    assert result["status"] == status
    assert result["before_observed"] == {"scopes": ["reports:read"]}
    assert result["observed"] == {"scopes": ["reports:read", "reports:write"]}


@pytest.mark.parametrize(
    "after",
    [WITH_DEPENDENCY, BASE.replace("def reports():", "def reports(user=Security(current_user)):")],
)
def test_no_security_scope_declarations_are_an_empty_set_not_a_public_verdict(after):
    result = compare(after=after, observation="scope-declarations", expected={"scopes": []})
    assert result["status"] == "matched" and result["observed"] == {"scopes": []}


def test_line_shifts_match_stable_route_but_report_new_registration_identity():
    after = "# A comment shifts all source locations.\n\n" + WITH_DEPENDENCY
    before_id = route_for()["registration_id"]
    after_id = route_for(after)["registration_id"]
    assert before_id != after_id
    result = compare(after=after)
    assert result["status"] == "matched" and result["after_registration_id"] == after_id


@pytest.mark.parametrize(
    "mutation", ["dependencies", "effective_dependencies", "function", "line", "registration"]
)
def test_baseline_evidence_must_match_full_reparsed_route(mutation):
    baseline = route_for(WITH_DEPENDENCY)
    if mutation in ("dependencies", "effective_dependencies"):
        baseline[mutation] = []
    elif mutation == "function":
        baseline[mutation] = "different_handler"
    elif mutation == "line":
        baseline[mutation] += 1
    else:
        baseline[mutation]["declaration"]["column"] += 1
    assert_unknown(
        compare(before=WITH_DEPENDENCY, after=WITH_DEPENDENCY + "# change\n", baseline=baseline)
    )


@pytest.mark.parametrize(
    "after",
    [
        WITH_DEPENDENCY.replace("def reports(", "def renamed("),
        WITH_DEPENDENCY.replace('"/reports"', '"/renamed"'),
        WITH_DEPENDENCY.replace("@app.get", "@app.post"),
        WITH_DEPENDENCY.replace("app =", "other =").replace("@app.get", "@other.get"),
        BASE.split("@app.get")[0],
        WITH_DEPENDENCY.replace(
            '@app.get("/reports")', '@app.get("/reports")\n@app.get("/reports")'
        ),
        WITH_DEPENDENCY.replace('"/reports"', "route_path"),
        WITH_DEPENDENCY + "\napp.include_router(extra)\n",
        WITH_DEPENDENCY + "\napp.dependency_overrides[current_user] = another\n",
        WITH_DEPENDENCY + "\nsecond = FastAPI()\n",
        WITH_DEPENDENCY.replace(
            "app = FastAPI()",
            '@app.get("/earlier")\ndef earlier():\n    return None\n\napp = FastAPI()',
        ),
        WITH_DEPENDENCY.replace("Depends(current_user)", "Depends(factory())"),
        WITH_SCOPES.replace('["reports:read"]', "wanted_scopes"),
        WITH_DEPENDENCY.replace("Depends, FastAPI", "Depends as Alias, FastAPI").replace(
            "Depends(current_user)", "Alias(current_user)"
        ),
        WITH_DEPENDENCY.replace("@app.get", "@unrelated\n@app.get"),
        WITH_DEPENDENCY + "\ndef broken(:\n",
    ],
)
def test_unsupported_changed_or_ambiguous_routes_remain_unknown(after):
    assert_unknown(compare(after=after))


def test_repeated_baseline_registration_is_not_disambiguated_by_source_line():
    before = BASE.replace('@app.get("/reports")', '@app.get("/reports")\n@app.get("/reports")')
    assert_unknown(compare(before=before, after=before + "# new comment\n"))


@pytest.mark.parametrize(
    "after",
    [
        "from dependencies import AuthDep\n"
        + BASE.replace("def reports():", "def reports(user: AuthDep):"),
        BASE.replace("def reports():", "def reports(user: AuthDep):"),
        BASE.replace("def reports():", 'def reports(user: "AuthDep"):'),
    ],
)
def test_unknown_annotation_aliases_are_not_reported_as_zero_dependencies(after):
    assert_unknown(compare(after=after, expected={"count": 0}))


@pytest.mark.parametrize("source", [BASE, BASE.encode("utf-8")])
def test_memory_parser_accepts_text_and_bytes_without_opening_label(monkeypatch, source):
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("Path is a label only"))
    parsed = FastAPIRouteParser().parse_source(source, Path("never-created/main.py"))
    assert parsed.error is None and not parsed.diagnostics
    assert parsed.routes[0].file == Path("never-created/main.py")


def test_policy_intent_is_never_inferred_even_with_unsupported_source():
    result = compare(
        after="not valid Python (", observation="policy-intent", expected={"intent": "public"}
    )
    assert result["status"] == "not-evaluated" and result["reason"]
    assert (
        result["before_observed"] is result["observed"] is result["after_registration_id"] is None
    )


def test_target_order_and_frozen_wrapper_do_not_mutate_caller_data():
    baseline = route_for()
    original = deepcopy(baseline)
    targets = [
        DeclarationTarget(baseline, "policy-intent", {"intent": "public"}),
        DeclarationTarget(baseline, "dependency-declarations", {"count": 1}),
        DeclarationTarget(baseline, "scope-declarations", {"scopes": ["absent"]}),
    ]
    results = compare_declarations(
        path="main.py", before_text=BASE, after_text=WITH_DEPENDENCY, targets=targets
    )
    assert [item["status"] for item in results] == ["not-evaluated", "matched", "mismatched"]
    results[1]["observed"]["count"] = 999
    assert compare_declarations(
        path="main.py", before_text=BASE, after_text=WITH_DEPENDENCY, targets=targets
    )[1]["observed"] == {"count": 1}
    assert baseline == original
    with pytest.raises(FrozenInstanceError):
        targets[0].observation = "dependency-declarations"


def test_bundle_report_is_identity_bound_detached_and_never_an_approval():
    bundle = bundle_for()
    report = check_proposal(bundle)
    assert report["schema_version"] == "1.0"
    assert report["kind"] == "source-declaration-comparison" and report["status"] == "completed"
    assert report["scope"] == "source-declarations"
    assert report["bundle_id"] == bundle.bundle_id
    assert report["request_id"] == bundle.to_dict()["proposal"]["request_id"]
    assert report["proposal_id"] == bundle.to_dict()["manifest"]["proposal_id"]
    assert report["manifest_id"].startswith("expectation-")
    assert report["applied"] is False and report["live_provider_calls"] == 0
    assert report["verification_status"] == report["runtime_verification_status"] == "not-run"
    assert report["authorization_verdict"] == "unknown" and report["limitations"]
    assert report["summary"] == {"matched": 1, "mismatched": 0, "unknown": 0, "not-evaluated": 0}
    report["results"][0]["observed"]["count"] = 999
    assert check_proposal(bundle)["results"][0]["observed"] == {"count": 1}
    assert check_proposal(
        validate_preview_bundle(json.dumps(bundle.to_dict(), indent=2))
    ) == check_proposal(bundle)
    with pytest.raises(ContractError):
        check_proposal(ValidatedPreviewBundle("{}"))


def test_structurally_valid_rebound_baseline_dependency_forgery_is_unknown():
    def forge(data):
        route = next(item["data"] for item in data["evidence"] if item["kind"] == "route")
        route["dependencies"] = []
        route["effective_dependencies"] = []

    bundle = bundle_for(
        before=WITH_DEPENDENCY, after=WITH_DEPENDENCY + "# supplied change\n", mutate_request=forge
    )
    assert validate_preview_bundle(bundle.payload_json) == bundle
    report = check_proposal(bundle)
    assert report["results"][0]["status"] == "unknown"
    assert report["summary"]["unknown"] == 1


@pytest.mark.parametrize(
    "gate",
    [
        "missing",
        "duplicate",
        "partial",
        "diagnostics",
        "parse-errors",
        "extra-source",
        "extra-change",
    ],
)
@pytest.mark.parametrize("policy", [False, True])
def test_bundle_scope_and_limitation_gates_do_not_promote_partial_evidence(gate, policy):
    def alter(data):
        evidence = data["evidence"]
        item = next(item for item in evidence if item["kind"] == "limitations")
        if gate == "missing":
            evidence.remove(item)
        elif gate == "duplicate":
            duplicate = deepcopy(item)
            duplicate["data"]["analysis_status"] = "partial"
            evidence.append(duplicate)
        elif gate == "partial":
            item["data"]["analysis_status"] = "partial"
        elif gate == "diagnostics":
            item["data"]["diagnostic_codes"] = ["unsupported-route-arguments"]
        elif gate == "parse-errors":
            item["data"]["parse_error_count"] = 1

    extra = gate in {"extra-source", "extra-change"}
    bundle = bundle_for(
        observation="policy-intent" if policy else "dependency-declarations",
        expected={"intent": "restricted"} if policy else {"count": 1},
        mutate_request=alter,
        extra_sources={"other.py": "x = 1\n"} if extra else None,
        extra_changes={"other.py": "x = 2\n"} if gate == "extra-change" else None,
    )
    report = check_proposal(bundle)
    assert report["results"][0]["status"] == ("not-evaluated" if policy else "unknown")
    assert report["results"][0]["observed"] is None


def test_parser_and_comparison_use_supplied_text_without_any_io_or_execution(monkeypatch):
    bundle = bundle_for(path="private/missing.py")
    baseline = route_for()

    def forbidden(*args, **kwargs):
        pytest.fail("In-memory declaration analysis attempted I/O, execution or a provider call")

    for obj, name in [
        (builtins, "open"),
        (builtins, "exec"),
        (os, "open"),
        (Path, "open"),
        (Path, "read_text"),
        (Path, "read_bytes"),
        (socket.socket, "connect"),
        (subprocess, "Popen"),
        (asyncio, "create_subprocess_exec"),
        (MockCodexAdapter, "analyze"),
        (ScanRunner, "run"),
        (FastAPIRouteParser, "parse_file"),
        (FastAPIRouteParser, "parse_repository"),
    ]:
        monkeypatch.setattr(obj, name, forbidden)
    parsed = FastAPIRouteParser().parse_source(BASE, ROOT / "main.py")
    assert len(parsed.routes) == 1
    assert compare(baseline=baseline)["status"] == "matched"
    assert check_proposal(bundle)["results"][0]["status"] == "matched"
