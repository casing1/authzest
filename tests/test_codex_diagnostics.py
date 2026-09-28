from dataclasses import FrozenInstanceError
from itertools import product

import pytest

from authzest.codex.diagnostics import (
    FAILURE_CODES,
    FAILURE_STAGES,
    TURN_START_STATES,
    FailureDiagnostic,
    sanitize_failure,
)


class StringSubclass(str):
    pass


class ExplosiveValue:
    def __hash__(self):
        raise AssertionError("Private value must not be hashed")

    def __eq__(self, other):
        raise AssertionError("Private value must not be compared")

    def __str__(self):
        raise AssertionError("Private value must not be formatted")

    def __repr__(self):
        raise AssertionError("Private value must not be formatted")


def test_all_closed_diagnostic_values_round_trip_without_extra_fields():
    for stage, code, turn_start in product(FAILURE_STAGES, FAILURE_CODES, TURN_START_STATES):
        value = FailureDiagnostic(stage, code, turn_start)
        assert sanitize_failure(value) == {"stage": stage, "code": code, "turn_start": turn_start}


def test_diagnostic_is_frozen_and_output_is_detached():
    value = FailureDiagnostic("turn-stream", "protocol-rejected", "acknowledged")
    with pytest.raises(FrozenInstanceError):
        value.stage = "unknown"
    output = sanitize_failure(value)
    output["stage"] = "FAKE_SECRET"
    assert value.stage == "turn-stream"


@pytest.mark.parametrize("field", ["stage", "code", "turn_start"])
@pytest.mark.parametrize(
    "bad",
    [None, True, 42, [], {}, "FAKE_SECRET", StringSubclass("unknown"), ExplosiveValue()],
    ids=["none", "bool", "integer", "list", "dict", "secret", "subclass", "hooks"],
)
def test_diagnostic_constructor_and_sanitizer_reject_invalid_fields(field, bad):
    fields = {"stage": "unknown", "code": "unexpected-error", "turn_start": "unknown"}
    fields[field] = bad
    with pytest.raises(ValueError, match="Invalid bounded failure diagnostic"):
        FailureDiagnostic(**fields)
    value = FailureDiagnostic("startup", "transport-error", "not-attempted")
    object.__setattr__(value, field, bad)
    assert sanitize_failure(value, stage="result-validation", code="response-invalid") == {
        "stage": "result-validation",
        "code": "response-invalid",
        "turn_start": "unknown",
    }


def test_sanitizer_rejects_dict_subclass_incomplete_and_arbitrary_objects():
    class ChildDiagnostic(FailureDiagnostic):
        pass

    fallback = {"stage": "unknown", "code": "unexpected-error", "turn_start": "unknown"}
    for value in (
        None,
        fallback,
        ChildDiagnostic("startup", "transport-error", "not-attempted"),
        object.__new__(FailureDiagnostic),
        ExplosiveValue(),
    ):
        assert sanitize_failure(value) == fallback


def test_invalid_fallback_enums_are_redacted_without_running_hooks():
    assert sanitize_failure(None, stage=ExplosiveValue(), code=StringSubclass("timeout")) == {
        "stage": "unknown",
        "code": "unexpected-error",
        "turn_start": "unknown",
    }
