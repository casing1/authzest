"""Pure comparisons of supplied owner-read output, without executing artifacts."""

import base64
import json
from dataclasses import FrozenInstanceError

import pytest

from authzest.owner_read_demo.checks import owner_read_controls
from authzest.runner._owner_read_phase_result import (
    MAX_CAPTURE_BYTES,
    MAX_RESULT_BYTES,
    OwnerReadPhaseResult,
    validate_owner_read_phase,
)

_SOURCE = "a" * 64
_TEST = "b" * 64
_PLAN = "owner-read-before-plan"


def _records(phase):
    before = phase == "before"
    cases = owner_read_controls()
    base = {
        "kind": "owner-read-guest-observation",
        "schema_version": "1.0",
        "source_sha256": _SOURCE,
        "test_sha256": _TEST,
    }
    records = {
        "test": {
            **base,
            "role": "test",
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
        },
        "controls": {
            **base,
            "role": "controls",
            "observations": [
                {"case_id": case["case_id"], **case["before" if before else "intended"]}
                for case in cases
            ],
        },
    }
    return json.loads(json.dumps(records))


def _captures(records):
    return {
        role: {
            "exit_code": 0,
            "stdout": json.dumps(record).encode(),
            "stderr": b"",
            "cleanup_confirmed": True,
        }
        for role, record in records.items()
    }


def _validate(phase="before", captures=None, **changes):
    arguments = {
        "phase": phase,
        "plan_id": _PLAN,
        "source_sha256": _SOURCE,
        "test_sha256": _TEST,
        "captures": _captures(_records(phase)) if captures is None else captures,
    }
    arguments.update(changes)
    return validate_owner_read_phase(**arguments)


@pytest.mark.parametrize("phase,count", [("before", 6), ("after", 7)])
def test_complete_distinct_roles_match_the_specific_phase(phase, count):
    captures = _captures(_records(phase))
    result = _validate(phase, captures)
    assert type(result) is OwnerReadPhaseResult
    value = result.to_dict()
    assert value["status"] == "matched" and value["failure"] is None
    assert value["phase"] == phase and value["plan_id"] == _PLAN
    assert value["source_sha256"] == _SOURCE and value["test_sha256"] == _TEST
    assert value["provenance"] == "supplied-guest-captures"
    assert value["cleanup_confirmed"] is True
    assert value["comparison"]["intended_matches"] == count
    for role, capture in captures.items():
        retained = value["captures"][role]
        assert base64.b64decode(retained["stdout_base64"]) == capture["stdout"]
        assert retained["stdout_bytes"] == len(capture["stdout"])
        assert retained["stderr_bytes"] == 0 and retained["stderr_base64"] == ""
    value["status"] = "changed"
    captures["test"]["stdout"] = b"changed"
    assert result.to_dict()["status"] == "matched"
    with pytest.raises(FrozenInstanceError):
        result.payload_json = "{}"


@pytest.mark.parametrize("phase", ["before", "after"])
def test_valid_opposite_phase_is_a_mismatch_with_retained_observations(phase):
    other = "after" if phase == "before" else "before"
    value = _validate(phase, _captures(_records(other))).to_dict()
    assert value["status"] == "mismatch" and value["failure"] == "unexpected-observations"
    assert value["regression"] == _records(other)["test"]["regression"]
    assert value["observations"] == _records(other)["controls"]["observations"]
    assert value["comparison"]["status"] == "compared"


def test_authored_test_pass_cannot_replace_independent_after_controls():
    records = _records("after")
    records["controls"] = _records("before")["controls"]
    value = _validate("after", _captures(records)).to_dict()
    assert value["regression"]["status"] == "passed"
    assert value["comparison"]["intended_matches"] == 6
    assert value["status"] == "mismatch"


@pytest.mark.parametrize("role", ["test", "controls"])
@pytest.mark.parametrize("key", ["source_sha256", "test_sha256", "role", "schema_version"])
def test_stale_hashes_swapped_role_or_version_fail(role, key):
    records = _records("before")
    records[role][key] = "wrong"
    value = _validate(captures=_captures(records)).to_dict()
    assert value["status"] == "failed" and value["failure"] == "guest-identity-mismatch"


def test_swapped_guest_captures_cannot_be_relabelled():
    captures = _captures(_records("before"))
    captures["test"], captures["controls"] = captures["controls"], captures["test"]
    value = _validate(captures=captures).to_dict()
    assert value["status"] == "failed" and value["failure"] == "invalid-guest-json"


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b"{}{}",
        b"[]",
        b"\xff",
        b'{"role":"test","role":"controls"}',
        b'{"unexpected":NaN}',
        b'{"unexpected":Infinity}',
        b'{"unexpected":1e999}',
    ],
)
def test_malformed_duplicate_nonfinite_or_truncated_guest_json_is_failed(raw):
    captures = _captures(_records("before"))
    captures["test"]["stdout"] = raw
    value = _validate(captures=captures).to_dict()
    assert value["status"] == "failed" and value["failure"] == "invalid-guest-json"
    assert base64.b64decode(value["captures"]["test"]["stdout_base64"]) == raw


@pytest.mark.parametrize(
    "changes",
    [
        {"pytest_exit": True},
        {"collected": True},
        {"requests": True},
        {"collected": 0},
        {"collected": 2},
        {"requests": 0},
        {"requests": 2},
        {"setup": "failed"},
        {"teardown": "failed"},
        {"call": "skipped"},
        {"pytest_exit": 2},
        {"status": "error"},
        {"status": "passed"},
        {"response": {"status_code": True, "body": {}}},
        {"response": None},
        {"extra": "field"},
    ],
)
def test_infrastructure_lifecycle_failure_cannot_be_expected_assertion_failure(changes):
    records = _records("before")
    records["test"]["regression"].update(changes)
    value = _validate(captures=_captures(records)).to_dict()
    assert value["status"] == "failed" and value["failure"] == "pytest-lifecycle-error"
    assert value["comparison"]["matches_before_profile"] is True


def test_wrong_actual_response_is_a_retained_mismatch():
    records = _records("after")
    records["test"]["regression"]["response"]["body"]["title"] = "Wrong note"
    value = _validate("after", _captures(records)).to_dict()
    assert value["status"] == "mismatch"
    assert value["regression"]["response"]["body"]["title"] == "Wrong note"
    assert value["comparison"]["matches_intended_policy"] is True


@pytest.mark.parametrize("role", ["test", "controls"])
@pytest.mark.parametrize("exit_code,stderr", [(1, b""), (65, b"failure"), (0, b"diagnostic")])
def test_outer_guest_failure_cannot_be_hidden_by_valid_stdout(role, exit_code, stderr):
    captures = _captures(_records("before"))
    captures[role].update(exit_code=exit_code, stderr=stderr)
    value = _validate(captures=captures).to_dict()
    assert value["status"] == "failed" and value["failure"] == "guest-failed"
    assert base64.b64decode(value["captures"][role]["stderr_base64"]) == stderr


@pytest.mark.parametrize("role", ["test", "controls"])
def test_cleanup_unconfirmed_always_fails_even_with_matching_output(role):
    captures = _captures(_records("before"))
    captures[role]["cleanup_confirmed"] = False
    value = _validate(captures=captures).to_dict()
    assert value["status"] == "failed" and value["failure"] == "cleanup-unconfirmed"
    assert value["cleanup_confirmed"] is False


@pytest.mark.parametrize(
    "key,value",
    [("exit_code", False), ("stdout", "text"), ("stderr", None), ("cleanup_confirmed", 1)],
)
def test_capture_field_types_are_exact(key, value):
    captures = _captures(_records("before"))
    captures["test"][key] = value
    result = _validate(captures=captures).to_dict()
    assert result["status"] == "failed" and result["failure"] == "invalid-capture-shape"


@pytest.mark.parametrize("captures", [{}, {"test": {}}, {"test": {}, "controls": {}, "extra": {}}])
def test_missing_or_extra_capture_roles_fail(captures):
    value = _validate(captures=captures).to_dict()
    assert value["failure"] == "invalid-capture-shape"


@pytest.mark.parametrize(
    "arguments",
    [
        {"phase": "reference"},
        {"phase": True},
        {"source_sha256": "a" * 63},
        {"test_sha256": "B" * 64},
        {"plan_id": ""},
        {"plan_id": "with\nnewline"},
        {"plan_id": "x" * 129},
        {"plan_id": None},
    ],
)
def test_expected_bindings_must_be_valid(arguments):
    value = _validate(**arguments).to_dict()
    assert value["status"] == "failed" and value["failure"] == "invalid-expected-identity"


def test_both_streams_and_roles_share_one_output_allowance():
    captures = _captures(_records("before"))
    captures["test"]["stdout"] = b"a" * (MAX_CAPTURE_BYTES // 2)
    captures["controls"]["stderr"] = b"b" * (MAX_CAPTURE_BYTES // 2)
    value = _validate(captures=captures).to_dict()
    assert value["failure"] == "capture-budget-exceeded" and value["captures"] == {}
    assert len(json.dumps(value).encode()) <= MAX_RESULT_BYTES


def test_bounded_failed_capture_preserves_exact_output_within_result_budget():
    captures = _captures(_records("before"))
    other_bytes = len(captures["controls"]["stdout"])
    captures["test"]["stdout"] = b"a" * (MAX_CAPTURE_BYTES - other_bytes)
    result = _validate(captures=captures)
    value = result.to_dict()
    assert value["failure"] == "invalid-guest-json"
    assert (
        base64.b64decode(value["captures"]["test"]["stdout_base64"]) == captures["test"]["stdout"]
    )
    assert len(result.payload_json.encode()) <= MAX_RESULT_BYTES


@pytest.mark.parametrize("change", ["missing", "boolean-status", "wrong-order", "extra-field"])
def test_incomplete_or_type_confused_independent_controls_fail(change):
    records = _records("after")
    observations = records["controls"]["observations"]
    if change == "missing":
        observations.pop()
    elif change == "boolean-status":
        observations[0]["status_code"] = True
    elif change == "wrong-order":
        observations.reverse()
    else:
        observations[0]["extra"] = "unexpected"
    value = _validate("after", _captures(records)).to_dict()
    assert value["status"] == "failed" and value["failure"] == "invalid-controls"
