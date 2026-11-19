"""Offline owner-read request and response contracts. Returned code is data throughout."""

import json
from hashlib import sha256

import pytest

from authzest.codex import owner_read_suggestion as contract
from authzest.codex.contracts import ContractError, canonical

RULE = 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n'
TEST = (
    "def test_owner_reads_archive(owner_client):\n"
    '    response = owner_client.get("/records/archived-note")\n'
    "    assert response.status_code == 200\n"
)


@pytest.fixture
def request_data():
    return contract.build_owner_read_request("offline-model")


def result(req, **changes):
    data = {
        "request_id": req.request_id,
        "status": "proposed-change",
        "rationale": "Allow legitimate owners to read archived notes.",
        "source": RULE,
        "test": TEST,
    }
    return json.dumps(data | changes, ensure_ascii=True)


def test_request_discloses_the_bound_inputs_and_requires_the_same_model(request_data):
    data = request_data.to_dict()
    assert request_data == contract.validate_owner_read_request(request_data)
    assert request_data == contract.build_owner_read_request("offline-model")
    assert request_data.request_id != contract.build_owner_read_request("different").request_id
    assert data["source"]["path"] == contract.SOURCE_PATH
    assert data["source"]["sha256"] == sha256(data["source"]["text"].encode()).hexdigest()
    assert data["source"]["sha256"] == contract.BASELINE_SHA256
    assert data["test_path"] == contract.TEST_PATH
    assert request_data.request_id in data["prompt"]
    assert canonical(data["source"]) in data["prompt"]
    assert RULE not in data["prompt"] and canonical(RULE) not in data["prompt"]
    assert data["output_schema"]["properties"]["request_id"]["enum"] == [request_data.request_id]
    assert data["host_instructions"] == contract.HOST_INSTRUCTIONS


@pytest.mark.parametrize(
    "field",
    ["prompt", "source", "policy", "output_schema", "host_instructions", "request_id", "test_path"],
)
def test_changed_request_rejected(request_data, field):
    payload = request_data.to_dict()
    payload[field] = "different"
    changed = contract.OwnerReadRequest(canonical(payload))
    with pytest.raises(ContractError, match="request changed"):
        contract.validate_owner_read_response(result(request_data), changed)


def test_pinned_package_bytes_rechecked_before_accepting(request_data, monkeypatch, tmp_path):
    (tmp_path / "availability.py").write_bytes(b"different package bytes\n")
    monkeypatch.setattr(contract, "files", lambda _: tmp_path)
    with pytest.raises(ContractError, match="baseline differs"):
        contract.validate_owner_read_response(result(request_data), request_data)


def test_missing_source_reports_a_bounded_error(monkeypatch, tmp_path):
    monkeypatch.setattr(contract, "files", lambda _: tmp_path)
    with pytest.raises(ContractError, match="Packaged baseline unavailable") as error:
        contract.build_owner_read_request("offline-model")
    assert str(tmp_path) not in str(error.value)


@pytest.mark.parametrize(
    "predicate",
    [
        'state in ["archived", "active"]',
        'state == "active" or state == "archived"',
        'state in {"active", "archived"}',
        'state == "pending"',
    ],
)
def test_bounded_source_and_positive_test_shapes_return_as_data(request_data, predicate):
    source = (
        '"""Module documentation."""\n'
        "def available_to_owner(state: str) -> bool:\n"
        '    """Rule documentation."""\n'
        f"    return {predicate}\n"
    )
    test = (
        "def test_archived_item(owner_client) -> None:\n"
        '    """Positive regression."""\n'
        '    assert owner_client.get("/records/archived-note").status_code == 200\n'
    )
    assert contract.validate_owner_read_response(
        result(request_data, source=source, test=test), request_data
    ) == json.loads(result(request_data, source=source, test=test))


def test_assignment_style_positive_regression(request_data):
    assert contract.validate_owner_read_response(result(request_data), request_data)["test"] == TEST


def test_assignment_to_reserved_debug_name_is_rejected(request_data):
    test = TEST.replace("response", "__debug__")
    with pytest.raises(ContractError, match="Invalid positive regression"):
        contract.validate_owner_read_response(result(request_data, test=test), request_data)


def test_parse_warning_is_redacted_and_never_printed(request_data, capsys, recwarn):
    test = TEST.replace("    response =", '    "private\\q"\n    response =')
    with pytest.raises(ContractError, match="Invalid owner-read Python") as error:
        contract.validate_owner_read_response(result(request_data, test=test), request_data)
    assert not recwarn.list
    assert capsys.readouterr().err == ""
    assert "private" not in str(error.value)


@pytest.mark.parametrize("status", ["no-change", "unknown", "refused"])
def test_non_change_must_have_no_artifacts(request_data, status):
    raw = result(request_data, status=status, source=None, test=None)
    assert contract.validate_owner_read_response(raw, request_data) == json.loads(raw)
    with pytest.raises(ContractError):
        contract.validate_owner_read_response(result(request_data, status=status), request_data)


@pytest.mark.parametrize(
    "source",
    [
        None,
        "",
        "x = 1",
        "import os\n" + RULE,
        RULE + "x = 1",
        "@wrapper\n" + RULE,
        RULE.replace("state: str", "state: str = default()"),
        RULE.replace("str)", "str, **kwargs)"),
        RULE.replace("bool:", "factory():"),
        RULE.replace("available_to_owner(", "available_to_owner[T]("),
        RULE.replace("return state", "yield state"),
        RULE.replace('("active", "archived")', "states"),
        RULE.replace('("active", "archived")', '("active", state)'),
        RULE.replace('in ("active", "archived")', '!= "pending"'),
        RULE.replace('in ("active", "archived")', '== "unregistered"'),
        "# coding: text\n" + RULE,
        RULE.replace("state", "staté"),
        "x" * 4097,
    ],
)
def test_unexpected_rule_rejected(request_data, source):
    with pytest.raises(ContractError):
        contract.validate_owner_read_response(result(request_data, source=source), request_data)


@pytest.mark.parametrize(
    "test",
    [
        None,
        "",
        "assert True",
        "import pytest\n" + TEST,
        "@pytest.mark.skip\n" + TEST,
        TEST + TEST,
        TEST.replace("(owner_client)", "(owner_client, data)"),
        TEST.replace("assert response.status_code == 200", "assert True"),
        TEST.replace("== 200", "!= 401"),
        TEST.replace("== 200", "== 200.0"),
        TEST.replace("== 200", "== 200, custom()"),
        TEST.replace("assert response.", "assert other."),
        TEST.replace(".get(", ".post("),
        TEST.replace("archived-note", "active-note"),
        TEST.replace('archived-note")', 'archived-note", headers={})'),
        TEST.replace("response =", "owner_client ="),
        TEST.replace("    assert", "    pass\n    assert"),
        TEST.replace("assert response.status_code", "assert response.json()"),
        "x" * 4097,
    ],
)
def test_unexpected_or_weak_positive_test_rejected(request_data, test):
    with pytest.raises(ContractError):
        contract.validate_owner_read_response(result(request_data, test=test), request_data)


def test_response_is_request_bound_and_changed(request_data):
    with pytest.raises(ContractError) as error:
        contract.validate_owner_read_response(
            result(request_data, request_id="stale"), request_data
        )
    assert error.value.code == "validation-identity"
    with pytest.raises(ContractError, match="unchanged"):
        contract.validate_owner_read_response(
            result(request_data, source=request_data.to_dict()["source"]["text"]), request_data
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": []},
        {"status": "success"},
        {"rationale": None},
        {"rationale": "\u202e"},
        {"rationale": "  "},
        {"rationale": "x" * 1025},
        {"test": "\ud800"},
        {"source_path": "other"},
    ],
)
def test_malformed_responses_fail_with_bounded_local_errors(request_data, mutation):
    with pytest.raises(ContractError):
        contract.validate_owner_read_response(result(request_data, **mutation), request_data)


def test_duplicate_keys_and_oversize_tree_rejected(request_data):
    duplicate = result(request_data).replace('"status":', '"status": "unknown", "status":')
    with pytest.raises(ContractError) as error:
        contract.validate_owner_read_response(duplicate, request_data)
    assert error.value.code == "validation-duplicate"
    long_rule = "def available_to_owner(state: str) -> bool:\n    return " + " or ".join(
        ['state == "active"'] * 50
    )
    with pytest.raises(ContractError) as error:
        contract.validate_owner_read_response(result(request_data, source=long_rule), request_data)
    assert error.value.code == "validation-budget"
