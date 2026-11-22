"""Synthetic imported owner-read records; no provider, generated code or private logs."""

from __future__ import annotations

import json
from hashlib import sha256

import pytest

from authzest._owner_read_viewer import preview_owner_read_result  # preloaded before effect guards
from authzest.owner_read_demo.checks import compare_owner_read_observations, owner_read_controls
from authzest.result_viewer import ResultViewError, _diff, preview_workflow_result

SOURCE = "src/authzest/owner_read_demo/availability.py"
TEST_PATH = "tests/test_owner_archived_read.py"
BEFORE = 'def available_to_owner(state: str) -> bool:\n    return state == "active"\n'
AFTER = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_owner_archive(owner_client):\n"
    '    assert owner_client.get("/records/archived-note").status_code == 200\n'
)


def digest(text):
    return sha256(text.encode()).hexdigest()


def phase(candidate):
    before = candidate == "before"
    cases = owner_read_controls()
    observations = [
        {"case_id": row["case_id"], **row["before" if before else "intended"]} for row in cases
    ]
    return {
        "kind": "owner-read-phase-result",
        "schema_version": "1.0",
        "phase": candidate,
        "status": "matched",
        "source_sha256": digest(BEFORE if before else AFTER),
        "test_sha256": digest(TEST),
        "cleanup_confirmed": True,
        "failure": None,
        "regression": {
            "status": "assertion-failed" if before else "passed",
            "pytest_exit": int(before),
            "collected": 1,
            "setup": "passed",
            "call": "failed" if before else "passed",
            "teardown": "passed",
            "requests": 1,
            "response": cases[1]["before" if before else "intended"],
        },
        "observations": observations,
        "comparison": compare_owner_read_observations(observations),
        "plan_id": "PRIVATE-DO-NOT-DISPLAY-PLAN",
        "captures": {"raw": "PRIVATE-DO-NOT-DISPLAY-CAPTURE"},
    }


def record(*, source=True):
    value = {
        "kind": "owner-read-suggestion",
        "schema_version": "1.0",
        "status": "proposed-change",
        "request_id": "1" * 64,
        "sharing_id": "PRIVATE-DO-NOT-DISPLAY-SHARING",
        "model": "PRIVATE-DO-NOT-DISPLAY-MODEL",
        "application_turn_attempts": 1,
        "exit_code": 0,
        "execution_status": "completed",
        "patch_application": "applied-to-copy",
        "restoration_status": "restored",
        "original_checkout_modified": False,
        "runtime_descriptor_cleanup_confirmed": True,
        "proposal": {
            "request_id": "1" * 64,
            "status": "proposed-change",
            "rationale": "Scripted owner-read example with supplied claims only.",
            "source": AFTER,
            "test": TEST,
        },
        "diffs": [
            {
                "path": SOURCE,
                "before_sha256": digest(BEFORE),
                "after_sha256": digest(AFTER),
                "diff": _diff(BEFORE, AFTER, SOURCE),
            },
            {
                "path": TEST_PATH,
                "before_sha256": None,
                "after_sha256": digest(TEST),
                "diff": _diff("", TEST, TEST_PATH, new=True),
            },
        ],
        "file_workflow": {
            "kind": "owner-read-file-session",
            "schema_version": "1.0",
            "status": "completed",
            "exit_code": 0,
            "patch_application": "applied-to-copy",
            "restoration_status": "restored",
            "recovery_required": False,
            "descriptor_cleanup_confirmed": True,
            "guest_cleanup_confirmed": True,
            "workspace_state": "restored-before",
            "original_checkout_modified": False,
            "before": phase("before"),
            "after": phase("after"),
            "copy": {"path": "/PRIVATE-DO-NOT-DISPLAY-COPY"},
            "stages": {
                name: {
                    "status": status,
                    "guest_dispatch_started": name in ("before", "after"),
                    "plan_id": "PRIVATE-DO-NOT-DISPLAY-PLAN",
                }
                for name, status in (
                    ("copy", "prepared"),
                    ("before", "matched"),
                    ("diff", "accepted"),
                    ("apply", "applied"),
                    ("after", "matched"),
                    ("restore", "restored"),
                )
            },
        },
        "failure": None,
        "runtime_review": {"path": "/PRIVATE-DO-NOT-DISPLAY-CONFIG"},
        "runtime_observations": [{"daemon": "PRIVATE-DO-NOT-DISPLAY-DAEMON"}],
        "account": "PRIVATE-DO-NOT-DISPLAY-ACCOUNT",
    }
    if source:
        value["source_evidence"] = {
            "scenario_id": "owner-archived-read",
            "source": {"path": SOURCE, "sha256": digest(BEFORE), "text": BEFORE},
            "declarations": [],
            "policy": ["An authenticated owner may read an archived note."],
            "policy_authorship": "project-maintained",
            "policy_review": "declared-policy",
        }
    return value


def encoded(value):
    return json.dumps(value).encode()


def test_owner_result_projects_source_artifacts_stages_and_distinct_counts():
    value = record()
    view = preview_workflow_result(encoded(value))
    assert (
        view["kind"] == "authzest-workflow-view" and view["record_kind"] == "owner-read-suggestion"
    )
    assert view["record_version"] == "1.0" and view["provenance"] == "imported-unverified"
    assert view["source_evidence"]["source"]["text"] == BEFORE
    assert view["proposal"]["after_source"]["text"] == AFTER
    assert view["proposal"]["test"]["text"] == TEST
    assert view["proposal"]["changes"] == value["diffs"]
    assert view["summary"]["status"] == "completed"
    assert view["summary"]["recovery_required"] is False
    assert view["summary"]["applied"] is True
    assert view["summary"]["current_copy_state"] == "restored-before"
    assert [row["stage"] for row in view["session"]["stages"]] == [
        "copy",
        "before",
        "source-diff",
        "source-apply",
        "after",
        "restore",
    ]
    before, after = (view["session"]["checks"][name] for name in ("before", "after"))
    assert before["comparison"]["matching_case_count"] == 7
    assert before["comparison"]["intended_match_count"] == 6
    assert before["test_exit_code"] == 1 and before["regression_status"] == "assertion-failed"
    assert before["response_status"] == 403
    assert (
        after["comparison"]["matching_case_count"]
        == after["comparison"]["intended_match_count"]
        == 7
    )
    assert after["test_exit_code"] == 0 and after["response_status"] == 200
    assert view["session"]["verified_fix"] is False
    assert view["session"]["authorization_status"] == "unknown"
    assert "PRIVATE-DO-NOT" not in json.dumps(view)


def test_older_owner_version_one_record_can_omit_original_source():
    view = preview_workflow_result(encoded(record(source=False)))
    assert view["source_evidence"] is None
    assert view["availability"]["before_source"] is False
    assert view["availability"]["declarations"] is False
    assert view["proposal"]["changes"][0]["diff"]
    assert any("Original source evidence is absent" in text for text in view["warnings"])


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_nonchange_assessment_has_no_test_patch_or_claimed_checks(status):
    value = record()
    value.update(
        status=status,
        execution_status="not-run",
        patch_application="not-run",
        restoration_status="not-run",
        file_workflow={"status": "not-started", "recovery_required": False},
        diffs=[],
    )
    value["proposal"].update(status=status, source=None, test=None)
    view = preview_workflow_result(encoded(value))
    assert view["proposal"] is None and view["assessment"]["status"] == status
    assert view["session"]["checks"] == {"before": None, "after": None}
    assert view["summary"]["applied"] is False


def test_early_versioned_refusal_does_not_infer_execution_or_recovery():
    value = {
        "kind": "owner-read-suggestion",
        "schema_version": "1.0",
        "status": "invalid-input",
        "exit_code": 2,
        "execution_status": "not-run",
        "patch_application": "not-run",
    }
    view = preview_workflow_result(encoded(value))
    assert view["summary"]["status"] == "invalid-input"
    assert view["summary"]["recovery_required"] is None
    assert view["session"] is None and view["proposal"] is None


def test_cli_missing_runtime_exports_a_versioned_importable_refusal():
    from typer.testing import CliRunner

    from authzest.cli import app

    result = CliRunner().invoke(
        app, ["owner-read-suggest", "--model", "test-model", "--file-workflow", "--json"]
    )
    assert result.exit_code == 2
    raw = result.stdout.encode()
    assert json.loads(raw)["schema_version"] == "1.0"
    view = preview_workflow_result(raw)
    assert view["summary"]["status"] == "invalid-input"
    assert view["summary"]["execution_status"] == "not-run"
    assert view["session"] is None and view["proposal"] is None


def test_partial_recovery_required_result_keeps_observations_without_success():
    value = record()
    value.update(exit_code=130, execution_status="partial", restoration_status="required")
    workflow = value["file_workflow"]
    workflow.update(
        status="cancelled",
        exit_code=130,
        restoration_status="required",
        recovery_required=True,
        workspace_state="applied-after",
        guest_cleanup_confirmed=None,
        after=None,
    )
    workflow["stages"]["after"].update(status="expired", guest_dispatch_started=True)
    workflow["stages"]["restore"]["status"] = "not-run"
    view = preview_workflow_result(encoded(value))
    assert view["summary"]["status"] == "cancelled" and view["summary"]["recovery_required"] is True
    assert view["session"]["checks"]["after"] is None
    assert view["session"]["verified_fix"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("cleanup_confirmed", False),
        ("test_sha256", "f" * 64),
        ("source_sha256", "f" * 64),
        ("phase", "before"),
    ],
)
def test_completed_cannot_hide_phase_failure_or_stale_binding(field, value):
    data = record()
    data["file_workflow"]["after"][field] = value
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("collected", True),
        ("collected", 0),
        ("requests", 2),
        ("setup", "failed"),
        ("teardown", "failed"),
        ("pytest_exit", False),
        ("status", "unknown"),
    ],
)
def test_pytest_lifecycle_must_match_claimed_regression(field, value):
    data = record()
    data["file_workflow"]["after"]["regression"][field] = value
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-after",
        "no-apply",
        "no-restore",
        "recovery",
        "missing-stage",
        "no-dispatch",
        "changed-original",
    ],
)
def test_contradictory_completed_records_are_rejected(mutation):
    data = record()
    workflow = data["file_workflow"]
    if mutation == "missing-after":
        workflow["after"] = None
    elif mutation == "no-apply":
        workflow["patch_application"] = "not-run"
    elif mutation == "no-restore":
        workflow["restoration_status"] = "required"
    elif mutation == "recovery":
        workflow["recovery_required"] = True
    elif mutation == "missing-stage":
        del workflow["stages"]["restore"]
    elif mutation == "no-dispatch":
        workflow["stages"]["after"]["guest_dispatch_started"] = False
    else:
        data["original_checkout_modified"] = True
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


@pytest.mark.parametrize(
    "mutation",
    [
        "after-hash",
        "test-hash",
        "test-diff",
        "source-diff",
        "source-hash",
        "source-path",
        "request-id",
    ],
)
def test_proposal_source_test_and_exact_diff_bindings_are_checked(mutation):
    data = record()
    if mutation == "after-hash":
        data["diffs"][0]["after_sha256"] = "a" * 64
    elif mutation == "test-hash":
        data["diffs"][1]["after_sha256"] = "a" * 64
    elif mutation == "test-diff":
        data["diffs"][1]["diff"] = "different"
    elif mutation == "source-diff":
        data["diffs"][0]["diff"] = "different"
    elif mutation == "source-hash":
        data["source_evidence"]["source"]["sha256"] = "a" * 64
    elif mutation == "source-path":
        data["diffs"][0]["path"] = "/private/other.py"
    else:
        data["proposal"]["request_id"] = "b" * 64
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


def test_independent_counts_cannot_be_forged_and_failed_phase_remains_failed():
    data = record()
    data["file_workflow"]["before"]["comparison"]["intended_matches"] = 7
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))
    data = record()
    data.update(execution_status="partial", restoration_status="required", exit_code=1)
    workflow = data["file_workflow"]
    workflow.update(
        status="after-failed",
        exit_code=1,
        after={
            **phase("after"),
            "status": "failed",
            "regression": None,
            "observations": None,
            "comparison": None,
            "failure": "invalid-controls",
        },
        restoration_status="required",
        recovery_required=True,
        workspace_state="applied-after",
    )
    workflow["stages"]["after"]["status"] = "failed"
    workflow["stages"]["restore"]["status"] = "not-run"
    view = preview_workflow_result(encoded(data))
    assert view["session"]["checks"]["after"]["comparison"] is None
    assert view["session"]["checks"]["after"]["regression_status"] is None
    assert view["summary"]["recovery_required"] is True


def test_runtime_descriptor_failure_stays_visible_after_source_restoration():
    data = record()
    data.update(
        status="runtime-descriptor-cleanup-unconfirmed",
        exit_code=1,
        runtime_descriptor_cleanup_confirmed=False,
    )
    view = preview_workflow_result(encoded(data))
    assert view["summary"]["status"] == "runtime-descriptor-cleanup-unconfirmed"
    assert view["summary"]["recovery_required"] is True
    assert view["session"]["cleanup_unconfirmed"] is True


def test_projection_has_no_path_process_model_or_code_execution(monkeypatch):
    import builtins
    import os
    import socket
    import subprocess

    def forbidden(*_args, **_kwargs):
        pytest.fail("Imported viewer must remain read-only data projection")

    for obj, names in (
        (builtins, ("open", "exec", "eval", "compile")),
        (os, ("open", "system")),
        (socket, ("socket", "create_connection")),
        (subprocess, ("Popen", "run")),
    ):
        for name in names:
            monkeypatch.setattr(obj, name, forbidden)
    assert preview_owner_read_result(record())["provenance"] == "imported-unverified"


def test_future_cli_source_evidence_comes_from_its_existing_sharing_preview():
    import asyncio

    from authzest.runner.owner_read_suggestion import run_suggestion

    previews = []
    result = asyncio.run(
        run_suggestion(
            "offline-source-view",
            emit=lambda text: previews.append(json.loads(text)),
            read=lambda _: "",
        )
    )
    evidence = result["source_evidence"]
    assert evidence["source"] == previews[0]["request"]["source"]
    assert evidence["policy"] == previews[0]["request"]["policy"]
    assert result["application_turn_attempts"] == 0
    assert result["status"] == "not-shared"
    view = preview_workflow_result(encoded(result))
    assert view["source_evidence"]["source"] == evidence["source"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("exit_code", 1),
        ("exit_code", True),
        ("runtime_descriptor_cleanup_confirmed", False),
        ("runtime_descriptor_cleanup_confirmed", None),
        ("failure", "unexpected-error"),
    ],
)
def test_completed_suggestion_cannot_hide_outer_failure_or_missing_cleanup(field, value):
    data = record()
    data[field] = value
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


def test_top_level_proposal_status_must_match_the_assessment():
    data = record()
    data["status"] = "no-change"
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


def test_output_limit_failure_can_include_large_omitted_transport_capture():
    data = record()
    data.update(execution_status="partial", restoration_status="required", exit_code=1)
    workflow = data["file_workflow"]
    workflow.update(
        status="dispatcher-failed",
        exit_code=1,
        after=None,
        restoration_status="required",
        recovery_required=True,
        workspace_state="applied-after",
        guest_cleanup_confirmed=None,
    )
    workflow["stages"]["after"]["status"] = "unconfirmed"
    workflow["stages"]["restore"]["status"] = "not-run"
    data["runtime_observations"] = [
        {
            "failure": "normal-output-limit",
            "commands": [
                {"stdout_base64": "A" * 100000, "stderr_base64": "PRIVATE-DO-NOT-DISPLAY"}
            ],
        }
    ]
    view = preview_workflow_result(encoded(data))
    assert view["summary"]["recovery_required"] is True
    assert view["session"]["checks"]["after"] is None
    assert "stdout_base64" not in json.dumps(view)
    assert "PRIVATE-DO-NOT" not in json.dumps(view)


def test_large_projected_owner_field_is_still_rejected():
    data = record()
    data["proposal"]["source"] = "A" * 70000
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


def test_producer_accepted_tab_indented_source_and_test_can_be_imported():
    import asyncio

    from authzest.runner.owner_read_suggestion import run_suggestion

    source = AFTER.replace("\n    ", "\n\t")
    test = TEST.replace("\n    ", "\n\t")
    previews = []

    class Adapter:
        async def suggest_owner_read(self, request):
            return {
                "request_id": request.request_id,
                "status": "proposed-change",
                "rationale": "Scripted producer response using supported tab indentation.",
                "source": source,
                "test": test,
            }

    value = asyncio.run(
        run_suggestion(
            "offline-tab-view",
            emit=lambda text: previews.append(json.loads(text)),
            read=lambda _: "share " + previews[-1]["sharing_id"],
            adapter_factory=lambda **_: Adapter(),
        )
    )
    assert value["status"] == "proposed-change"
    assert value["proposal"]["source"] == source and value["proposal"]["test"] == test
    view = preview_workflow_result(encoded(value))
    assert view["proposal"]["after_source"]["text"] == source
    assert view["proposal"]["test"]["text"] == test
    assert view["provenance"] == "imported-unverified"


@pytest.mark.parametrize("control", ["\r", "\x00", "\x1b", "\x7f"])
def test_unsupported_source_controls_remain_rejected(control):
    value = record()
    value["proposal"]["source"] += control
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(value))


@pytest.mark.parametrize(
    "status,code,cleanup",
    [
        ("runtime-observations-unconfirmed", 1, True),
        ("cancelled", 130, True),
        ("runtime-descriptor-cleanup-unconfirmed", 1, False),
    ],
)
def test_observation_retention_failure_preserves_completed_phases_and_recovery(
    status, code, cleanup
):
    value = record()
    value.update(
        status=status,
        exit_code=code,
        runtime_observations_status="unconfirmed",
        runtime_descriptor_cleanup_confirmed=cleanup,
    )
    value["file_workflow"]["recovery_required"] = True
    view = preview_workflow_result(encoded(value))
    assert view["summary"]["status"] == status and view["summary"]["exit_code"] == code
    assert view["summary"]["recovery_required"] is True
    assert view["summary"]["restoration_status"] == "restored"
    assert view["session"]["status"] == "completed"
    assert all(
        view["session"]["checks"][name]["status"] == "matched" for name in ("before", "after")
    )
    assert "Runtime observation collection is unconfirmed." in view["warnings"]
    assert ("Runtime profile descriptor cleanup is unconfirmed." in view["warnings"]) is (
        cleanup is False
    )
    assert view["session"]["verified_fix"] is False
    assert "PRIVATE-DO-NOT" not in json.dumps(view)


@pytest.mark.parametrize(
    "changes",
    [
        {"runtime_observations_status": None},
        {"status": "proposed-change"},
        {"status": "cancelled", "exit_code": 1},
        {"status": "runtime-observations-unconfirmed", "exit_code": 130},
        {"runtime_descriptor_cleanup_confirmed": False},
        {"runtime_descriptor_cleanup_confirmed": None},
        {"exit_code": True},
        {"failure": "unexpected-error"},
    ],
)
def test_completed_recovery_exception_requires_the_exact_outer_failure_state(changes):
    value = record()
    value.update(
        status="runtime-observations-unconfirmed",
        exit_code=1,
        runtime_observations_status="unconfirmed",
    )
    value["file_workflow"]["recovery_required"] = True
    value.update(changes)
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(value))
