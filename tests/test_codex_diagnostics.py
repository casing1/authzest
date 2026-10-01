from dataclasses import FrozenInstanceError
from itertools import product

import pytest

from authzest.codex.contracts import ContractError, contract_failure_code, decode
from authzest.codex.diagnostics import (
    FAILURE_CODES,
    FAILURE_STAGES,
    TURN_START_STATES,
    VALIDATION_CODES,
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


@pytest.mark.parametrize("code", sorted(VALIDATION_CODES))
def test_contract_codes_are_fixed_and_independent_of_exception_text(code):
    error = ContractError("FAKE_SECRET_MODEL_TEXT", code=code)
    assert contract_failure_code(error) == code
    diagnostic = FailureDiagnostic(
        "response-validation", contract_failure_code(error), "acknowledged"
    )
    assert "FAKE_SECRET" not in str(sanitize_failure(diagnostic))


@pytest.mark.parametrize(
    "code",
    [None, True, [], {}, "FAKE_SECRET", StringSubclass("validation-json"), ExplosiveValue()],
    ids=["none", "bool", "list", "dict", "secret", "subclass", "hooks"],
)
def test_contract_code_constructor_and_export_recheck_without_running_hooks(code):
    error = ContractError("FAKE_SECRET", code=code)
    assert contract_failure_code(error) == "response-invalid"
    error.code = code
    assert contract_failure_code(error) == "response-invalid"


def test_contract_export_does_not_trust_subclass_property_or_arbitrary_exception():
    class Forged(ContractError):
        @property
        def code(self):
            raise AssertionError("Subclass diagnostic property must not be read")

    error = ContractError("FAKE_SECRET", code="validation-text")
    del error.code
    for value in (error, Forged.__new__(Forged), ExplosiveValue(), ValueError("FAKE_SECRET")):
        assert contract_failure_code(value) == "response-invalid"


@pytest.mark.parametrize(
    "raw,code",
    [
        ("FAKE_SECRET not json", "validation-json"),
        ('{"x": NaN}', "validation-json"),
        ('{"x": 1, "x": 2}', "validation-duplicate"),
        ('{"x": "' + "x" * 262_144 + '"}', "validation-budget"),
        ('{"x":' + "[" * 34 + "0" + "]" * 34 + "}", "validation-budget"),
        ('{"x": "\\ud800"}', "validation-text"),
        ("[]", "validation-shape"),
    ],
    ids=["syntax", "nonfinite", "duplicate-key", "size", "depth", "unicode", "root"],
)
def test_decoder_keeps_fixed_first_rule_without_parsing_error_messages(raw, code):
    with pytest.raises(ContractError) as error:
        decode(raw)
    assert contract_failure_code(error.value) == code
