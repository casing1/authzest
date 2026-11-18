"""Inert imported records only: no model, worker, target import or path reads."""

from __future__ import annotations

import copy
import json
from hashlib import sha256

import pytest

from authzest.result_viewer import MAX_RESULT_BYTES, ResultViewError, preview_workflow_result


def digest(text):
    return sha256(text.encode()).hexdigest()


def record():
    # Deliberately scripted claims; no test has actually run. The viewer cannot
    # authenticate them even when every internal binding is consistent.
    before, after, test = "value = 1\n", "value = 2\n", "def test_value():\n    assert True\n"
    source = {"path": "app.py", "sha256": digest(before), "text": before}
    proposal = {
        "schema_version": "1.0",
        "status": "proposed-change",
        "rationale": "Scripted proposal, not model output or an observed repair.",
        "assumptions": ["Synthetic scenario only."],
        "uncertainties": [],
        "limitations": ["No actual execution."],
        "proposal": {
            "source_path": "app.py",
            "before_sha256": digest(before),
            "after_text": after,
            "test_path": "tests/test_demo.py",
            "test_text": test,
        },
    }
    changes = [
        {
            "path": "app.py",
            "before_sha256": digest(before),
            "after_sha256": digest(after),
            "diff": "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
        },
        {
            "path": "tests/test_demo.py",
            "before_sha256": None,
            "after_sha256": digest(test),
            "diff": "--- /dev/null\n+++ b/tests/test_demo.py\n@@ -0,0 +1,2 @@\n"
            "+def test_value():\n+    assert True\n",
        },
    ]
    checks = {}
    for candidate in ("before", "after"):
        checks[candidate] = {
            "candidate": candidate,
            "status": "complete",
            "cleanup_confirmed": True,
            "generated_runtime_attempted": True,
            "test_exit_code": 1 if candidate == "before" else 0,
            "application_sha256": digest(before if candidate == "before" else after),
            "test_sha256": digest(test),
            "failure": None,
            "transport_failure": None,
            "evidence_directory": "/PRIVATE-DO-NOT-FOLLOW",
            "comparison": {
                "expected_profile": "intended-before-defect"
                if candidate == "before"
                else "repaired-policy-controls",
                "comparison_status": "matches-expected-profile",
                "matches_expected_profile": True,
                "case_count": 17,
                "matching_case_count": 17,
                "request_count": 21,
                "matching_request_count": 21,
            },
        }
    return {
        "schema_version": "1.0",
        "kind": "codex-generated-file-workflow",
        "status": "file-workflow-complete",
        "exit_code": 0,
        "proposal_status": "proposed-change",
        "execution_status": "after-checked",
        "patch_application": "applied-copy-only",
        "applied": True,
        "current_copy_state": "restored-before",
        "restoration_status": "restored-before",
        "original_checkout_modified": False,
        "source_evidence": {
            "scenario_id": "scripted-test-only",
            "source": source,
            "declarations": [{"path": "/synthetic"}],
            "policy": ["Draft only."],
            "policy_authorship": "assistant",
            "policy_review": "pending-maintainer-review",
        },
        "generation": {"schema_version": "1.0", "proposal": proposal, "usage": {"private": 99}},
        "proposal_preview": {
            "schema_version": "1.0",
            "status": "proposed-change",
            "proposal": copy.deepcopy(proposal),
            "changes": changes,
        },
        "file_workflow": {
            "status": "complete",
            "stopped_stage": None,
            "close_status": "confirmed",
            "runtime_input_cleanup": "confirmed",
            "session_result": {
                "schema_version": "1.0",
                "closed": True,
                "cleanup_unconfirmed": False,
                "clock_unconfirmed": False,
                "execution_status": "after-checked",
                "source_application": "applied-copy-only",
                "restoration_status": "restored-before",
                "workspace": {"state": "restored-before", "path": "/PRIVATE-DO-NOT-READ"},
                "stages": {
                    name: {
                        "decision": "approved",
                        "status": status,
                        "expired": False,
                        "attempted": True,
                        "dispatched": name != "source-diff",
                        "reason": None,
                    }
                    for name, status in (
                        ("copy", "copied-private-workspace"),
                        ("before", "checked-before"),
                        ("source-diff", "accepted-exact-diff"),
                        ("source-apply", "applied-copy-only"),
                        ("after", "checked-after"),
                        ("restore", "restored-before"),
                    )
                },
                "checks": checks,
                "authorization_status": "unknown",
                "verified_fix": False,
                "isolation_established": False,
                "resource_enforcement_established": False,
                "test_report_authenticity": "not-established",
            },
        },
        "failure": None,
    }


def encoded(data):
    return json.dumps(data).encode()


def test_complete_is_only_an_imported_unverified_finite_observation():
    view = preview_workflow_result(encoded(record()))
    assert view["kind"] == "authzest-workflow-view"
    assert view["schema_version"] == "1.0" and view["record_version"] == "1.0"
    assert view["provenance"] == "imported-unverified"
    assert view["summary"]["applied"] is True  # historical application, not current after state
    assert view["summary"]["current_copy_state"] == "restored-before"
    assert view["session"]["checks"]["before"]["test_exit_code"] == 1
    assert view["session"]["checks"]["after"]["comparison"]["matching_request_count"] == 21
    assert view["session"]["verified_fix"] is False
    assert view["availability"] == {
        "before_source": True,
        "declarations": True,
        "raw_phase_captures": False,
    }
    assert "PRIVATE-DO-NOT" not in json.dumps(view)
    assert "usage" not in json.dumps(view)
    assert any("unverified" in warning for warning in view["warnings"])


def test_legacy_does_not_reconstruct_source_or_follow_private_paths():
    data = record()
    del data["schema_version"]
    del data["source_evidence"]
    view = preview_workflow_result(encoded(data))
    assert view["record_version"] == "legacy-unversioned"
    assert view["source_evidence"] is None
    assert view["availability"]["before_source"] is False
    assert view["proposal"]["test"]["text"].startswith("def test_value")


@pytest.mark.parametrize(
    "status", ["invalid-input", "cancelled", "generation-failed", "runtime-review-declined"]
)
def test_early_failure_missing_observations_stay_unknown(status):
    data = {
        "schema_version": "1.0",
        "kind": "codex-generated-file-workflow",
        "status": status,
        "failure": {"code": "redacted", "private_detail": "/private/secret"},
    }
    view = preview_workflow_result(encoded(data))
    assert view["session"] is None and view["proposal"] is None
    assert view["summary"]["applied"] is None and view["summary"]["exit_code"] is None
    assert view["failure"] == {"stage": None, "code": "redacted", "turn_start": None}
    assert "secret" not in json.dumps(view)


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_no_generated_change_is_not_a_completed_file_workflow(status):
    data = record()
    data.update(
        status="generation-ready",
        proposal_status=status,
        execution_status="not-run",
        patch_application="not-run",
        applied=False,
        restoration_status="not-run",
        current_copy_state=None,
    )
    proposal = data["generation"]["proposal"]
    proposal.update(status=status, proposal=None)
    data["proposal_preview"].update(status=status, proposal=copy.deepcopy(proposal), changes=[])
    data["file_workflow"] = {"status": "no-proposed-change", "session_result": None}
    view = preview_workflow_result(encoded(data))
    assert view["proposal"] is None and view["session"]["checks"]["before"] is None
    assert view["summary"]["proposal_status"] == status
    assert view["assessment"]["status"] == status
    assert view["assessment"]["rationale"] == proposal["rationale"]


def test_failed_after_does_not_erase_successful_restoration():
    data = record()
    data.update(status="file-workflow-failed", exit_code=1)
    phase = data["file_workflow"]["session_result"]["checks"]["after"]
    phase.update(
        status="failed", test_exit_code=None, comparison=None, failure="bounded-capture-failed"
    )
    view = preview_workflow_result(encoded(data))
    assert view["summary"]["status"] == "file-workflow-failed"
    assert view["summary"]["restoration_status"] == "restored-before"
    assert view["session"]["checks"]["after"]["failure"]["code"] == "bounded-capture-failed"


def test_partial_application_and_missing_phase_do_not_turn_into_false_or_success():
    data = record()
    data.update(
        status="file-workflow-failed",
        exit_code=1,
        applied=None,
        patch_application="state-unconfirmed",
        current_copy_state="state-unconfirmed",
        restoration_status="not-run",
    )
    session = data["file_workflow"]["session_result"]
    session.update(source_application="state-unconfirmed", restoration_status="not-run")
    session["workspace"]["state"] = "state-unconfirmed"
    session["checks"]["after"] = None
    view = preview_workflow_result(encoded(data))
    assert view["summary"]["applied"] is None
    assert view["summary"]["current_copy_state"] == "state-unconfirmed"
    assert view["session"]["checks"]["after"] is None


def test_file_flow_failure_is_not_lost_when_there_is_no_phase_receipt():
    data = record()
    data.update(status="file-workflow-failed", exit_code=1)
    data["file_workflow"].update(failure="current-context-or-stage-failed", stopped_stage="after")
    view = preview_workflow_result(encoded(data))
    assert view["failure"] == {
        "stage": "after",
        "code": "current-context-or-stage-failed",
        "turn_start": None,
    }


@pytest.mark.parametrize(
    "path,value",
    [
        (("kind",), "mock-workflow"),
        (("schema_version",), "2.0"),
        (("schema_version",), "legacy-unversioned"),
        (("applied",), "true"),
        (("exit_code",), True),
        (("current_copy_state",), "applied-after"),
        (("patch_application",), "not-run"),
        (("source_evidence", "source", "sha256"), "0" * 64),
        (("file_workflow", "session_result", "schema_version"), "2.0"),
        (("file_workflow", "session_result", "cleanup_unconfirmed"), True),
        (("file_workflow", "status"), "stage-failed"),
        (("file_workflow", "close_status"), "unconfirmed"),
        (("file_workflow", "runtime_input_cleanup"), "unconfirmed"),
        (("file_workflow", "session_result", "verified_fix"), True),
        (("file_workflow", "session_result", "test_report_authenticity"), "established"),
        (("file_workflow", "session_result", "stages", "restore", "decision"), "declined"),
        (("file_workflow", "session_result", "stages", "before", "expired"), True),
        (("file_workflow", "session_result", "checks", "after", "application_sha256"), None),
        (("file_workflow", "session_result", "checks", "after", "candidate"), "before"),
        (("file_workflow", "session_result", "checks", "after", "test_sha256"), "0" * 64),
        (
            (
                "file_workflow",
                "session_result",
                "checks",
                "after",
                "comparison",
                "matching_case_count",
            ),
            18,
        ),
        (
            ("file_workflow", "session_result", "checks", "after", "comparison", "request_count"),
            True,
        ),
        (
            (
                "file_workflow",
                "session_result",
                "checks",
                "after",
                "comparison",
                "matches_expected_profile",
            ),
            "yes",
        ),
        (("proposal_preview", "changes"), []),
    ],
)
def test_rejects_inconsistent_or_wrongly_typed_records(path, value):
    data = record()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ResultViewError):
        preview_workflow_result(encoded(data))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"kind":1,"kind":2}',
        b'{"anything":NaN}',
        b'{"anything":Infinity}',
        b'{"anything":1e999}',
        b"{}{}",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b'"not-an-object"',
        b'{"x":"\\ud800"}',
        b"[" * 35 + b"0" + b"]" * 35,
        b'{"values":[' + b"0," * 512 + b"0]}",
        b'{"text":"' + b"a" * 65_537 + b'"}',
        b'{"number":' + b"9" * 5000 + b"}",
        b" " * (MAX_RESULT_BYTES + 1),
    ],
)
def test_rejects_malformed_or_over_budget_json(raw):
    with pytest.raises(ResultViewError):
        preview_workflow_result(raw)


def test_source_and_model_markup_is_inert_exact_data():
    data = record()
    proposal = data["generation"]["proposal"]
    proposal["rationale"] = '<script>alert("untrusted")</script>\u202e'
    data["proposal_preview"]["proposal"] = copy.deepcopy(proposal)
    view = preview_workflow_result(encoded(data))
    assert view["proposal"]["rationale"] == proposal["rationale"]
