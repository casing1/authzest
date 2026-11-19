"""Data-only comparator coverage for the fixed synthetic owner-read observations."""

import json

import pytest

from authzest.owner_read_demo.checks import compare_owner_read_observations, owner_read_controls


def _intended():
    # The mock collector is independent of the expectation builder.
    return [
        {"case_id": case_id, "status_code": status, "body": body}
        for case_id, status, body in (
            ("owner-active", 200, {"id": "active-note", "title": "Active note"}),
            ("owner-archived", 200, {"id": "archived-note", "title": "Archived note"}),
            ("other-active", 403, {"detail": "Read denied"}),
            ("other-archived", 403, {"detail": "Read denied"}),
            ("anonymous-active", 401, {"detail": "Authentication required"}),
            ("owner-missing", 404, {"detail": "Record not found"}),
            ("owner-pending", 403, {"detail": "Read denied"}),
        )
    ]


def test_corrected_observations_match_all_seven_maintained_controls():
    result = compare_owner_read_observations(_intended())
    assert result["status"] == "compared"
    assert result["intended_matches"] == result["checks_total"] == 7
    assert result["matches_intended_policy"] is True
    assert result["matches_before_profile"] is False
    assert [r["case_id"] for r in result["checks"] if not r["before_match"]] == ["owner-archived"]


def test_preview_changes_cannot_change_either_expected_profile():
    preview = owner_read_controls()
    snapshot = json.dumps(preview)
    preview[1]["before"]["body"]["detail"] = "edited"
    preview[1]["intended"]["body"]["title"] = "edited"
    preview.pop()
    assert json.dumps(owner_read_controls()) == snapshot
    assert compare_owner_read_observations(_intended())["matches_intended_policy"] is True


@pytest.mark.parametrize(
    ("index", "status", "body"),
    (
        (0, 200, {"id": "active-note", "title": "Wrong"}),
        (0, 200, {"id": "active-note", "title": "Active note", "other": "PRIVATE"}),
        (1, 403, {"detail": "Wrong denial"}),
        (1, 200, {"id": "active-note", "title": "Active note"}),
        (1, 403, {"id": "archived-note", "title": "Archived note"}),
        (2, 403, {"detail": "Read denied", "title": "PRIVATE"}),
        (4, 401, {}),
        (5, 500, {"detail": "Record not found"}),
    ),
)
def test_status_and_entire_body_must_both_match(index, status, body):
    rows = _intended()
    rows[index].update(status_code=status, body=body)
    result = compare_owner_read_observations(rows)
    assert result["intended_matches"] == 6
    assert result["matches_intended_policy"] is False
    assert result["matches_before_profile"] is False
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize(
    "make_invalid",
    (
        lambda rows: None,
        lambda rows: {"observations": rows},
        lambda rows: rows[:-1],
        lambda rows: [*rows, rows[-1]],
        lambda rows: [*rows[:-1], rows[0]],
        lambda rows: rows[::-1],
        lambda rows: [*rows[:-1], None],
        lambda rows: [*rows[:-1], {**rows[-1], "case_id": "PRIVATE"}],
        lambda rows: [*rows[:-1], {**rows[-1], "status_code": True}],
        lambda rows: [*rows[:-1], {**rows[-1], "status_code": 999}],
        lambda rows: [*rows[:-1], {**rows[-1], "body": ["PRIVATE"]}],
        lambda rows: [*rows[:-1], {**rows[-1], "body": {"detail": {"raw": "PRIVATE"}}}],
        lambda rows: [*rows[:-1], {**rows[-1], "body": {"detail": True}}],
        lambda rows: [*rows[:-1], {**rows[-1], "body": {"detail": 1}}],
        lambda rows: [*rows[:-1], {**rows[-1], "body": {i: "x" for i in range(9)}}],
        lambda rows: [*rows[:-1], {**rows[-1], "body": {"detail": "x" * 257}}],
        lambda rows: [*rows[:-1], {**rows[-1], "extra": "PRIVATE"}],
    ),
)
def test_incomplete_or_malformed_observations_produce_no_conclusion(make_invalid):
    result = compare_owner_read_observations(make_invalid(_intended()))
    assert result == {
        "status": "invalid-observations",
        "checks_total": 7,
        "intended_matches": None,
        "matches_before_profile": None,
        "matches_intended_policy": None,
        "checks": [],
    }


def test_malformed_nested_body_is_rejected_without_traversal():
    rows = _intended()
    cycle = {}
    cycle["nested"] = cycle
    rows[-1]["body"] = {"detail": cycle}
    assert compare_owner_read_observations(rows)["status"] == "invalid-observations"
