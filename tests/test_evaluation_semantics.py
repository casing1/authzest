"""Pure bounded-value tests; no account, files, worker or provider observation."""

import json
import math

import pytest
from scripts import evaluation_semantics as semantics
from scripts.evaluation_trial_plan import TrialConfig


def boundary():
    return semantics.Boundary(TrialConfig("fixture-model", "high", 1, 30), "/owned", "t-1")


def test_deep_detached_exact_data():
    shared = {"text": "한글", "number": -5, "float": 1.5, "null": None, "bool": True}
    original = [shared, shared]
    result = semantics.checked(original)
    assert result == original
    assert result is not original and result[0] is not shared
    assert result[0] is not result[1]
    result[0]["text"] = "changed"
    assert original[0]["text"] == "한글"


@pytest.mark.parametrize(
    "value", [math.nan, math.inf, -math.inf, object(), (1,), {1: 2}, "\ud800", 1 << 4096]
)
def test_invalid_data(value):
    with pytest.raises(semantics.SemanticError):
        semantics.checked(value)


def test_no_custom_hooks():
    class Mapping(dict):
        def items(self):
            pytest.fail("custom hook executed")

    with pytest.raises(semantics.SemanticError, match="invalid-input-type"):
        semantics.checked(Mapping())


def test_cycles_depth_and_node_bounds():
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(semantics.SemanticError, match="cyclic-input"):
        semantics.checked(cyclic)
    deep = None
    for _ in range(34):
        deep = [deep]
    with pytest.raises(semantics.SemanticError, match="input-too-deep"):
        semantics.checked(deep)
    with pytest.raises(semantics.SemanticError, match="input-too-many-nodes"):
        semantics.checked([None] * 65536)


@pytest.mark.parametrize("value", ["한글", '\n"\\', {"x": [1, True, None]}])
def test_exact_utf8_size(value):
    count = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert semantics.checked(value, max_bytes=count) == value
    with pytest.raises(semantics.SemanticError, match="input-too-large"):
        semantics.checked(value, max_bytes=count - 1)


@pytest.mark.parametrize("limit", [True, 0, -1, 2 * 1024 * 1024 + 1, "10"])
def test_invalid_limits(limit):
    with pytest.raises(semantics.SemanticError, match="invalid-limit"):
        semantics.checked({}, max_bytes=limit)


@pytest.mark.parametrize("value", [True, "", "a/b", "한글", "x" * 129, " x", "x\n"])
def test_invalid_identifiers(value):
    with pytest.raises(semantics.SemanticError, match="invalid-identifier"):
        semantics.identifier(value)


@pytest.mark.parametrize(
    "cwd",
    [
        "relative",
        "//owned",
        "/owned/..",
        "/owned/",
        "/a\x00",
        "/" + "x" * 1024,
        "/owned\\label",
        "/owned\nlabel",
    ],
)
def test_invalid_cwd(cwd):
    with pytest.raises(semantics.SemanticError, match="invalid-cwd-label"):
        semantics.Boundary(boundary().configuration, cwd, "t-1")


def test_revalidates_mutated_frozen_configuration():
    value = boundary()
    object.__setattr__(value.configuration, "effort", None)
    with pytest.raises(semantics.SemanticError, match="invalid-configuration"):
        value.validate()


def test_negative_authority_flags():
    result = semantics.limitations()
    for field in (
        "runtime_observed",
        "authenticated",
        "sharing_authorized",
        "execution_authorized",
        "live_configuration_frozen",
        "ready_for_live_trial",
        "accepted_trial",
    ):
        assert result[field] is False
    assert result["actual_model_calls"] == 0
    assert result["target_executed"] is False


def test_incomplete_forged_frozen_boundary_and_configuration_are_closed():
    with pytest.raises(semantics.SemanticError, match="invalid-configuration"):
        object.__new__(semantics.Boundary).validate()
    with pytest.raises(semantics.SemanticError, match="invalid-configuration"):
        semantics.Boundary(object.__new__(TrialConfig), "/owned", "t-1")
