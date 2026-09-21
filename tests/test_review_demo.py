"""Integrated read-only review: supplied artifacts and prose drafts, never executed tests."""

import asyncio
import builtins
import json
import os
import socket
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path, PureWindowsPath

import pytest
from click import unstyle
from typer.testing import CliRunner

from authzest import cli
from authzest.analyzer import declarations
from authzest.codex import review_demo as builder
from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.mock import MockCodexAdapter
from authzest.codex.preview import ValidatedPreviewBundle, preview_bundle, validate_preview_bundle
from authzest.codex.proposals import content_hash
from authzest.parser.fastapi import FastAPIRouteParser
from authzest.runner import ScanRunner
from authzest.runner import review_demo as workflow
from authzest.runner.proposal_check import check_proposal
from test_declaration_check import BASE, WITH_DEPENDENCY, bundle_for

runner = CliRunner()


@pytest.fixture(autouse=True)
def no_provider_or_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Review composition must not execute a process, provider or network request")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(MockCodexAdapter, "analyze", forbidden)


def assert_read_only(view):
    assert view["status"] == "completed"
    assert view["applied"] is False and view["live_provider_calls"] == 0
    assert view["verification_status"] == view["runtime_verification_status"] == "not-run"
    assert view["authorization_verdict"] == "unknown"
    draft = view["regression_test_draft"]
    assert draft["status"] == "draft" and draft["executable"] is False
    assert draft["verification_status"] == draft["runtime_verification_status"] == "not-run"
    assert draft["authorization_verdict"] == "unknown"
    assert all(case["status"] == "draft" and case["observed"] is None for case in draft["cases"])


def test_fixed_demo_is_deterministic_mock_and_explicitly_not_authentication():
    bundle = builder.build_review_demo_bundle()
    assert builder.build_review_demo_bundle() == bundle
    payload = bundle.to_dict()
    sources = [item["data"] for item in payload["request"]["evidence"] if item["kind"] == "source"]
    assert sources == [{"path": builder.REVIEW_DEMO_PATH, "text": builder.REVIEW_DEMO_SOURCE}]
    assert payload["proposal"]["changes"][0]["after_text"] == builder.REVIEW_DEMO_AFTER
    assert (
        builder.REVIEW_DEMO_SOURCE.replace("scopes=[]", 'scopes=["reports:read"]', 1)
        == builder.REVIEW_DEMO_AFTER
    )
    assert (
        'raise RuntimeError("Source-only example; not authentication implementation")'
        in builder.REVIEW_DEMO_SOURCE
    )
    assert payload["request"]["config"]["provider"] == "mock"
    assert payload["review"]["identity"]["provider"] == "mock"
    assert payload["review"]["usage"] is None
    with pytest.raises(FrozenInstanceError):
        bundle.payload_json = "{}"
    view = workflow.run_review_demo()
    assert view["schema_version"] == "1.0" and view["kind"] == "offline-integrated-review"
    assert view["demo"] == {
        "case_id": "scope-declaration-review",
        "artifact_provenance": "caller-authored-mock",
        "simulated_draft": True,
    }
    assert view["comparison"]["summary"] == {
        "matched": 2,
        "mismatched": 0,
        "unknown": 0,
        "not-evaluated": 1,
    }
    assert_read_only(view)


def test_composition_preserves_existing_views_and_binds_every_prose_case():
    bundle = builder.build_review_demo_bundle()
    payload = bundle.to_dict()
    view = workflow.compose_review(bundle)
    assert "demo" not in view
    assert view["preview"] == preview_bundle(bundle)
    assert view["comparison"] == check_proposal(bundle)
    draft = view["regression_test_draft"]
    manifest = payload["manifest"]
    assert draft["schema_version"] == draft["template_version"] == "1.0"
    assert draft["format"] == "structured-prose"
    assert draft["bindings"] == {
        "bundle_id": bundle.bundle_id,
        "request_id": manifest["request_id"],
        "review_id": manifest["review_id"],
        "proposal_id": manifest["proposal_id"],
        "manifest_id": "expectation-" + identity(manifest),
        "source_identity": payload["request"]["source_identity"],
    }
    source = next(item for item in payload["request"]["evidence"] if item["kind"] == "source")
    change = payload["proposal"]["changes"][0]
    assert draft["sources"] == [
        {
            "path": change["path"],
            "source_evidence_id": source["id"],
            "before_sha256": content_hash(source["data"]["text"]),
            "after_sha256": content_hash(change["after_text"]),
        }
    ]
    assert len(draft["cases"]) == len(manifest["expectations"])
    for case, expected in zip(draft["cases"], manifest["expectations"], strict=True):
        for key, value in expected.items():
            if key == "limitations":
                assert case[key][: len(value)] == value and len(case[key]) > len(value)
            else:
                assert case[key] == value
        assert case["title"] and all(isinstance(step, str) and step for step in case["steps"])
        assert case["status"] == "draft" and case["observed"] is None
    content = {key: value for key, value in draft.items() if key != "draft_id"}
    assert draft["draft_id"] == "regression-draft-" + identity(content)

    def no_executor_fields(value):
        if isinstance(value, dict):
            assert not {
                "command",
                "commands",
                "code",
                "script",
                "executor",
                "approval",
                "approved",
            }.intersection(value)
            for item in value.values():
                no_executor_fields(item)
        elif isinstance(value, list):
            for item in value:
                no_executor_fields(item)

    no_executor_fields(draft)
    assert_read_only(view)


@pytest.mark.parametrize("outcome", ["matched", "mismatched", "unknown", "not-evaluated"])
def test_generic_composition_preserves_outcomes_without_promoting_prose_to_results(outcome):
    bundle = bundle_for(
        after=WITH_DEPENDENCY + "\nother = FastAPI()\n"
        if outcome == "unknown"
        else WITH_DEPENDENCY,
        observation="policy-intent" if outcome == "not-evaluated" else "dependency-declarations",
        expected={"intent": "restricted"}
        if outcome == "not-evaluated"
        else {"count": 2 if outcome == "mismatched" else 1},
    )
    view = workflow.compose_review(bundle)
    assert view["comparison"] == check_proposal(bundle)
    assert view["comparison"]["results"][0]["status"] == outcome
    assert_read_only(view)


@pytest.mark.parametrize("provider", ["mock", "declared-external-provider"])
def test_generic_composition_does_not_invent_mock_origin_or_erase_historical_usage(provider):
    def declared_identity(data):
        data["config"]["provider"] = provider
        data["config"]["model"] = "caller-declared-model"

    payload = bundle_for(mutate_request=declared_identity).to_dict()
    # These are caller-authored test metadata, not observed provider usage.
    payload["review"]["usage"] = {"input_tokens": 123, "output_tokens": 45}
    payload["proposal"]["review_id"] = identity(payload["review"])
    payload["manifest"]["review_id"] = identity(payload["review"])
    payload["manifest"]["proposal_id"] = "proposal-" + identity(payload["proposal"])
    bundle = validate_preview_bundle(canonical(payload))
    view = workflow.compose_review(bundle)
    assert view["test_draft_provenance"] == "maintainer-authored-template"
    assert view["source_artifact_provenance"] == "supplied-artifacts"
    assert view["regression_test_draft"]["provenance"] == "maintainer-authored-template"
    assert not {"demo", "draft_provenance", "simulated_draft"}.intersection(view)
    assert view["preview"]["review"] == payload["review"]
    assert view["preview"]["review"]["identity"]["provider"] == provider
    assert view["preview"]["review"]["usage"] == {"input_tokens": 123, "output_tokens": 45}
    assert view["live_provider_calls"] == 0  # This composition only, not artifact history.


@pytest.mark.parametrize("change", ["review", "proposal", "manifest", "source"])
def test_material_rebindings_change_draft_identity(change):
    original = bundle_for()
    payload = original.to_dict()
    if change == "source":
        changed = bundle_for(
            before=BASE + "# baseline note\n", after=WITH_DEPENDENCY + "# after note\n"
        )
    else:
        if change == "review":
            payload["review"]["answers"][0]["explanation"] = (
                "A different caller-authored explanation."
            )
            payload["proposal"]["review_id"] = identity(payload["review"])
            payload["manifest"]["review_id"] = identity(payload["review"])
        elif change == "proposal":
            payload["proposal"]["rationale"] = "A different caller-authored proposal rationale."
        else:
            payload["manifest"]["expectations"][0]["expected"] = {"count": 2}
        payload["manifest"]["proposal_id"] = "proposal-" + identity(payload["proposal"])
        changed = validate_preview_bundle(canonical(payload))
    first = workflow.compose_review(original)["regression_test_draft"]
    second = workflow.compose_review(changed)["regression_test_draft"]
    assert first["draft_id"] != second["draft_id"]
    assert first["bindings"]["bundle_id"] != second["bindings"]["bundle_id"]


def test_canonical_determinism_and_detached_nested_views():
    bundle = builder.build_review_demo_bundle()
    view = workflow.compose_review(bundle)
    original = deepcopy(view)
    pretty = ValidatedPreviewBundle(json.dumps(bundle.to_dict(), indent=2))
    assert workflow.compose_review(pretty) == original
    view["regression_test_draft"]["cases"][0]["expected"]["count"] = 999
    view["regression_test_draft"]["sources"].clear()
    view["preview"]["evidence"].clear()
    view["comparison"]["results"].clear()
    bundle.to_dict()["manifest"]["expectations"].clear()
    assert workflow.compose_review(bundle) == original


def test_forged_wrapper_or_stale_bindings_fail_before_composition(monkeypatch):
    payload = builder.build_review_demo_bundle().to_dict()
    payload["proposal"]["rationale"] = "Changed without rebinding the manifest."
    monkeypatch.setattr(workflow, "preview_bundle", lambda *a: pytest.fail("Revalidate first"))
    monkeypatch.setattr(workflow, "check_proposal", lambda *a: pytest.fail("Revalidate first"))
    for raw in ("{}", canonical(payload)):
        with pytest.raises(ContractError):
            workflow.compose_review(ValidatedPreviewBundle(raw))


def test_comparison_observations_do_not_change_unexecuted_template_identity(monkeypatch):
    bundle = builder.build_review_demo_bundle()
    original = workflow.compose_review(bundle)
    simulated = deepcopy(original["comparison"])
    simulated["results"][0]["status"] = "unknown"
    simulated["results"][0]["observed"] = None
    monkeypatch.setattr(workflow, "check_proposal", lambda _: simulated)
    changed = workflow.compose_review(bundle)
    assert changed["comparison"] == simulated
    assert changed["regression_test_draft"] == original["regression_test_draft"]


def test_builder_and_composition_are_memory_only_and_do_not_import_target_source(monkeypatch):
    original_import = builtins.__import__

    def safe_import(name, *args, **kwargs):
        if name.split(".")[0] in {"fastapi", "scripts"}:
            pytest.fail("Source and development scripts must not be imported")
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Memory-only review attempted filesystem access or source execution")

    monkeypatch.setattr(builtins, "__import__", safe_import)
    for obj, name in [
        (builtins, "open"),
        (builtins, "exec"),
        (os, "open"),
        (os, "read"),
        (Path, "open"),
        (Path, "read_text"),
        (Path, "read_bytes"),
        (Path, "resolve"),
        (tempfile, "mkdtemp"),
        (tempfile, "TemporaryDirectory"),
        (ScanRunner, "run"),
        (FastAPIRouteParser, "parse_file"),
        (FastAPIRouteParser, "parse_repository"),
    ]:
        monkeypatch.setattr(obj, name, forbidden)
    assert_read_only(workflow.compose_review(builder.build_review_demo_bundle()))
    assert_read_only(workflow.run_review_demo())


def test_builder_and_composition_are_stable_under_windows_path_flavour(monkeypatch):
    native_bundle = builder.build_review_demo_bundle()
    native = workflow.run_review_demo()
    nested = bundle_for(path="pkg/api.py")
    nested_native = workflow.compose_review(nested)
    monkeypatch.setattr(builder, "Path", PureWindowsPath)
    monkeypatch.setattr(declarations, "Path", PureWindowsPath)
    assert builder.build_review_demo_bundle() == native_bundle
    assert workflow.run_review_demo() == native
    assert workflow.compose_review(nested) == nested_native


@pytest.mark.parametrize("color", [False, True])
def test_cli_help_does_not_build_or_compose(monkeypatch, color):
    monkeypatch.setattr(workflow, "run_review_demo", lambda: pytest.fail("No demo work for help"))
    result = runner.invoke(cli.app, ["review-demo", "--help"], color=color)
    assert result.exit_code == 0 and "--json" in unstyle(result.stdout)
    assert "review-demo" in unstyle(runner.invoke(cli.app, ["--help"], color=color).stdout)


@pytest.mark.parametrize(
    "argument",
    [
        "bundle.json",
        "--path=.",
        "--yes",
        "--model=example",
        "--runtime-check",
        "--apply",
        "--output=report.json",
    ],
)
def test_cli_accepts_only_presentation_option(monkeypatch, argument):
    monkeypatch.setattr(workflow, "run_review_demo", lambda: pytest.fail("Reject before demo work"))
    assert runner.invoke(cli.app, ["review-demo", argument]).exit_code == 2


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_runs_outside_checkout_without_changing_existing_files(tmp_path, monkeypatch, as_json):
    sentinel = tmp_path / "main.py"
    sentinel.write_text("# unrelated local source\n")
    monkeypatch.chdir(tmp_path)
    expected = workflow.run_review_demo()
    result = runner.invoke(cli.app, ["review-demo", *(["--json"] if as_json else [])])
    assert result.exit_code == 0 and result.stderr == "" and result.stdout.isascii()
    if as_json:
        assert json.loads(result.stdout) == expected
    else:
        for section in (
            "Source declaration comparison",
            "Defensive regression-test draft",
            "Review limitations",
            "Exact diff",
        ):
            assert section in result.stdout
        assert "caller-authored-mock" in result.stdout
        diff = expected["preview"]["proposal"]["changes"][0]["diff"]
        assert all(
            json.dumps(line, ensure_ascii=True) in result.stdout for line in diff.split("\n")
        )
        assert expected["regression_test_draft"]["draft_id"] in result.stdout
    assert list(tmp_path.iterdir()) == [sentinel]
    assert sentinel.read_text() == "# unrelated local source\n"


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_escapes_controls_bidi_and_non_ascii_in_composed_views(monkeypatch, as_json):
    view = workflow.run_review_demo()
    view["limitations"].append("Display only: \x1b[31m\u202e검토")
    monkeypatch.setattr(workflow, "run_review_demo", lambda: view)
    result = runner.invoke(cli.app, ["review-demo", *(["--json"] if as_json else [])])
    assert result.exit_code == 0 and result.stdout.isascii()
    assert (
        "\x1b" not in result.stdout
        and "\u202e" not in result.stdout
        and "검토" not in result.stdout
    )
    assert "\\u001b" in result.stdout and "\\u202e" in result.stdout


@pytest.mark.parametrize(
    "failure,code,status",
    [
        (ContractError, 1, "review-failed"),
        (RuntimeError, 1, "review-failed"),
        (KeyboardInterrupt, 130, "cancelled"),
    ],
)
def test_cli_errors_are_sanitized_without_partial_output(monkeypatch, failure, code, status):
    def fail():
        raise failure("PRIVATE-REVIEW-ERROR")

    monkeypatch.setattr(workflow, "run_review_demo", fail)
    result = runner.invoke(cli.app, ["review-demo"])
    assert result.exit_code == code and result.stdout == ""
    assert json.loads(result.stderr)["status"] == status
    assert "PRIVATE-REVIEW-ERROR" not in result.output


def test_cli_formats_whole_view_before_emitting_any_output(monkeypatch):
    def fail(view):
        raise RuntimeError("PRIVATE-FORMATTING-ERROR")

    monkeypatch.setattr(cli, "_format_review_demo", fail)
    result = runner.invoke(cli.app, ["review-demo"])
    assert result.exit_code == 1 and result.stdout == ""
    assert json.loads(result.stderr)["status"] == "review-failed"
    assert "PRIVATE-FORMATTING-ERROR" not in result.output
