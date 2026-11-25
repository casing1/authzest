"""Saved repo-fix results in the read-only viewer, built from the offline flow."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from tests.helpers.repository_http_verification_data import AFTER, SOURCE

from authzest.result_viewer import ResultViewError, preview_workflow_result
from test_repository_http_fix import ALL, Answers, Project


@pytest.fixture
def record(tmp_path):
    project = Project(tmp_path)
    result = project.run(Answers(*ALL))
    assert result["status"] == "original-applied"
    return result


def _view(value):
    return preview_workflow_result(json.dumps(value).encode())


def test_applied_record_projects_checks_and_rebuilt_diff(record):
    view = _view(record)
    assert view["record_kind"] == "repository-http-fix-result"
    assert view["summary"]["status"] == "original-applied"
    assert view["summary"]["patch_application"] == "applied-to-original"
    assert view["session"]["verified_fix"] is True
    assert view["session"]["checks"]["after"]["comparison"]["matches_expected_profile"] is True
    assert view["session"]["checks"]["before"]["candidate"] == "before"
    change = view["proposal"]["changes"][0]
    assert change["path"] == "app.py" and '+    if x_user != "test-owner":' in change["diff"]
    assert view["source_evidence"]["source"]["text"] == SOURCE
    assert view["proposal"]["after_source"]["text"] == AFTER
    assert view["proposal"]["test"]["text"] == "GET /items/one x-user: test-other"
    assert [stage["status"] for stage in view["session"]["stages"]] == [
        "completed",
        "complete",
        "completed",
        "completed",
        "complete",
    ]


def test_private_paths_and_raw_records_are_dropped(record):
    text = json.dumps(_view(record))
    for secret in (record["original"]["record_path"], record["original"]["root"], "record_path"):
        assert secret not in text


def test_records_without_source_evidence_warn_instead_of_inventing_a_diff(record):
    record["source_evidence"] = None
    view = _view(record)
    assert view["proposal"]["changes"] == []
    assert view["availability"]["before_source"] is False
    assert "cannot be independently rebuilt" in view["warnings"][-1]


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["source_evidence"]["source"].update(text=SOURCE + "# edited\n"),
        lambda r: r["proposal"]["proposal"].update(source_path="other.py"),
        lambda r: r["proposal"]["proposal"].update(before_sha256="0" * 64),
        lambda r: r.update(after_phase=None),
        lambda r: r["after_phase"]["comparison"]["counts"].update(match=9),
        lambda r: r["after_phase"].update(status="failed"),
        lambda r: r.update(original_checkout_modified=False),
        lambda r: r["original"].update(state="intent-recorded"),
        lambda r: r.update(schema_version="1.0"),
        lambda r: r["after_phase"]["comparison"]["outcomes"][0].update(outcome="passed"),
        # A failed regression row cannot hide behind an unchanged match count.
        lambda r: r["after_phase"]["comparison"]["outcomes"][1].update(outcome="mismatch"),
        # Checks must belong to the displayed before source and repair.
        lambda r: r["proposal"]["proposal"].update(after_text=AFTER + "# other repair\n"),
        lambda r: r["after_phase"].update(source_sha256="0" * 64),
        lambda r: r["before_phase"].update(source_sha256="0" * 64),
    ],
)
def test_contradictory_or_tampered_records_are_refused(record, change):
    value = deepcopy(record)
    change(value)
    with pytest.raises(ResultViewError):
        _view(value)


def test_declined_record_stays_readable_without_checks(tmp_path):
    project = Project(tmp_path)
    result = project.run(Answers("accept", "decline"))
    view = _view(result)
    assert view["summary"]["status"] == "copy-declined"
    assert view["summary"]["execution_status"] == "not-run"
    assert view["session"]["checks"] == {"before": None, "after": None}
    assert view["session"]["verified_fix"] is False
