"""Offline, SCRIPTED HTTP facts only; no target import, collection or execution."""

import ast
import asyncio
import base64
import builtins
import copy
import json
import socket
import subprocess
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from authzest.codex.contracts import ContractError, canonical, identity
from authzest.codex.generated_repair_scenario import SOURCE
from authzest.runner import generated_repair_controls as controls


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    """Run pure functions only, including when fact strings contain Python code."""

    def forbidden(*args, **kwargs):
        pytest.fail("HTTP controls tests must remain inert offline comparisons")

    original_import = builtins.__import__
    original_compile = builtins.compile

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "examples", "fastapi", "uvicorn", "openai", "docker"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    def guarded_compile(source, filename, mode, flags=0, *args, **kwargs):
        if (
            flags & ast.PyCF_ONLY_AST
            and sys._getframe(1).f_globals.get("__name__") == "ast"
            and sys._getframe(2).f_globals.get("__name__") in {"_pytest._code.source", "traceback"}
        ):
            return original_compile(source, filename, mode, flags, *args, **kwargs)
        forbidden()

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(builtins, "compile", guarded_compile)
    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(tempfile, "mkdtemp", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def _requests(material=None):
    material = material or controls.build_generated_repair_controls()
    return [request for case in material.to_dict()["cases"] for request in case["requests"]]


def _scripted_facts(candidate="after", material=None):
    """Expected-shape strings, NOT responses from an application or generated test."""
    material = material or controls.build_generated_repair_controls()
    return {
        "schema_version": "1.0",
        "kind": "generated-repair-http-facts",
        "controls_id": material.controls_id,
        "candidate": candidate,
        "facts": [
            {
                "request_id": request["request_id"],
                "status_code": request[f"expected_{candidate}"]["status_code"],
                "headers": [["content-type", "application/json"]],
                "body_base64": base64.b64encode(
                    canonical(request[f"expected_{candidate}"]["body_json"]).encode("utf-8")
                ).decode("ascii"),
            }
            for request in _requests(material)
        ],
    }


def _compare(data, candidate="after", material=None):
    return controls.compare_generated_repair_observations(
        canonical(data), material or controls.build_generated_repair_controls(), candidate=candidate
    ).to_dict()


def test_controls_are_complete_independent_inert_immutable_and_detached():
    material = controls.build_generated_repair_controls()
    data = material.to_dict()
    assert data["kind"] == "generated-repair-controls"
    assert data["schema_version"] == "1.0"
    assert data["case_count"] == len(data["cases"]) == 17
    assert data["request_count"] == len(_requests(material)) == 21
    assert data["authorship"] == "assistant"
    assert data["review"] == "maintainer-accepted-offline-design"
    assert data["runtime_approval"] == "not-granted"
    assert data["actor_identity"] == "caller-controlled-fixture-header-not-authentication"
    assert material.controls_id == "generated-repair-controls-" + identity(data)
    assert controls.validate_generated_repair_controls(material.payload_json) == material
    with pytest.raises(FrozenInstanceError):
        material.payload_json = "{}"
    data["cases"][0]["requests"][0]["expected_after"]["body_json"]["body"] = "caller edit"
    assert data != material.to_dict()
    # Independent literals checked against public source TEXT, never app imported.
    for document_id, owner, body in (
        ("doc-alice", "alice", "Alice's synthetic document"),
        ("doc-bob", "bob", "Bob's synthetic document"),
    ):
        assert f'"{document_id}": {{"owner": "{owner}", "body": "{body}"}}' in SOURCE


def test_case_set_has_all_actor_variations_missing_objects_and_normal_sequences():
    material = controls.build_generated_repair_controls()
    cases = material.to_dict()["cases"]
    assert [case["category"] for case in cases] == (
        ["owner"] * 2
        + ["cross-owner"] * 2
        + ["missing-actor"] * 3
        + ["empty-actor"] * 3
        + ["unknown-actor"] * 3
        + ["missing-document"] * 2
        + ["normal-sequence"] * 2
    )
    assert len({request["request_id"] for request in _requests(material)}) == 21
    assert all(row["method"] == "GET" for row in _requests(material))
    for category, expected_headers in (
        ("missing-actor", []),
        ("empty-actor", [["x-demo-actor", ""]]),
        ("unknown-actor", [["x-demo-actor", "mallory"]]),
    ):
        assert {
            row["path"]
            for case in cases
            if case["category"] == category
            for row in case["requests"]
            if row["headers"] == expected_headers
        } == {"/documents/doc-alice", "/documents/doc-bob", "/documents/missing"}
    for case in cases[-2:]:
        rows = case["requests"]
        assert [row["expected_after"]["status_code"] for row in rows] == [200, 403, 200]
        assert [row["expected_before"]["status_code"] for row in rows] == [200, 200, 200]
        assert rows[0]["expected_after"] == rows[2]["expected_after"]


@pytest.mark.parametrize("candidate", ["before", "after"])
def test_scripted_profile_matches_are_data_only_not_runtime_or_fix_proof(candidate):
    material = controls.build_generated_repair_controls()
    facts = _scripted_facts(candidate, material)
    comparison = controls.compare_generated_repair_observations(
        canonical(facts), material, candidate=candidate
    )
    data = comparison.to_dict()
    assert data["status"] == "data-only"
    assert data["comparison_status"] == "matches-expected-profile"
    assert data["matches_expected_profile"] is True
    assert data["matching_case_count"] == data["case_count"] == 17
    assert data["matching_request_count"] == data["request_count"] == 21
    assert data["provenance"] == "caller-supplied-unverified"
    assert data["execution_status"] == "not-established"
    assert data["authorization_status"] == "unknown"
    assert data["verified_fix"] is data["applied"] is False
    assert data["provider_calls"] == 0
    assert data["observations_id"] == "generated-repair-http-facts-" + identity(facts)
    assert data["expected_profile"] == (
        "intended-before-defect" if candidate == "before" else "repaired-policy-controls"
    )
    with pytest.raises(FrozenInstanceError):
        comparison.payload_json = "{}"
    data["cases"].clear()
    assert len(comparison.to_dict()["cases"]) == 17


@pytest.mark.parametrize(
    "change", ["extra", "missing", "bool", "count", "policy", "order", "review"]
)
def test_controls_rebuild_all_closed_fields_not_a_caller_digest(change):
    data = controls.build_generated_repair_controls().to_dict()
    if change == "extra":
        data["approved"] = True
    elif change == "missing":
        del data["limitations"]
    elif change == "bool":
        data["cases"][0]["requests"][0]["expected_after"]["status_code"] = True
    elif change == "count":
        data["request_count"] = 20
    elif change == "policy":
        data["cases"][2]["requests"][0]["expected_after"]["status_code"] = 200
    elif change == "order":
        data["cases"].reverse()
    else:
        data["review"] = "runtime-approved"
    with pytest.raises(ContractError):
        controls.validate_generated_repair_controls(canonical(data))
    with pytest.raises(ContractError):
        controls.GeneratedRepairControls(canonical(data))


def test_controls_wrapper_is_revalidated_at_comparison_boundary():
    material = controls.build_generated_repair_controls()
    facts = _scripted_facts(material=material)
    forged = copy.deepcopy(material)
    object.__setattr__(forged, "payload_json", "{}")
    with pytest.raises(ContractError):
        _compare(facts, material=forged)


@pytest.mark.parametrize("candidate", [None, True, 0, [], {}, "BEFORE", "both", ""])
def test_candidate_is_explicit_and_strict(candidate):
    with pytest.raises(ContractError):
        controls.compare_generated_repair_observations(
            canonical(_scripted_facts()),
            controls.build_generated_repair_controls(),
            candidate=candidate,
        )


@pytest.mark.parametrize("material", [None, {}, "{}", True])
def test_controls_argument_requires_actual_wrapper(material):
    with pytest.raises(ContractError):
        controls.compare_generated_repair_observations(
            canonical(_scripted_facts()), material, candidate="after"
        )


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "kind",
        "controls",
        "candidate",
        "extra",
        "missing",
        "facts-type",
        "row-extra",
        "row-missing",
    ],
)
def test_fact_envelope_and_rows_are_closed_and_exact_bound(change):
    data = _scripted_facts()
    if change in {"schema", "kind", "controls", "candidate"}:
        key = {"schema": "schema_version", "controls": "controls_id"}.get(change, change)
        data[key] = "unknown"
    elif change == "extra":
        data["success"] = True
    elif change == "missing":
        del data["candidate"]
    elif change == "facts-type":
        data["facts"] = {}
    elif change == "row-extra":
        data["facts"][0]["success"] = True
    else:
        del data["facts"][0]["headers"]
    with pytest.raises(ContractError):
        _compare(data)


@pytest.mark.parametrize("change", ["missing", "extra", "reverse", "duplicate", "unknown-id"])
def test_every_fact_required_once_in_declared_sequence(change):
    data = _scripted_facts()
    if change == "missing":
        data["facts"].pop()
    elif change == "extra":
        data["facts"].append(data["facts"][0])
    elif change == "reverse":
        data["facts"].reverse()
    elif change == "duplicate":
        data["facts"][1] = data["facts"][0]
    else:
        data["facts"][0]["request_id"] = "not-registered"
    with pytest.raises(ContractError):
        _compare(data)


@pytest.mark.parametrize("status", [True, False, None, "200", 200.0, -1, 0, 99, 600, 10**30])
def test_status_must_be_a_bounded_strict_integer(status):
    data = _scripted_facts()
    data["facts"][0]["status_code"] = status
    with pytest.raises(ContractError):
        _compare(data)


@pytest.mark.parametrize(
    "headers",
    [
        None,
        {},
        ["not-a-pair"],
        [["only-name"]],
        [["x-name", "value", "extra"]],
        [[1, "value"]],
        [["x-name", False]],
        [["", "value"]],
        [["bad:name", "value"]],
        [["bad name", "value"]],
        [["é", "value"]],
        [["x-name", "value\r\ninjected: yes"]],
        [["x-name", "\x00"]],
        [["x-name", "\x7f"]],
        [["x-name", "\x85"]],
        [["x-name", "a"]] * 33,
        [["x-name", "a" * 4096]],
        [["x-name", "é" * 2046]],
    ],
)
def test_headers_are_closed_bounded_pairs_without_injection(headers):
    data = _scripted_facts()
    data["facts"][0]["headers"] = headers
    with pytest.raises(ContractError):
        _compare(data)


def test_header_bytes_include_colon_space_crlf_and_final_crlf_with_exact_limit():
    data = _scripted_facts()
    data["facts"][0]["headers"] = [["x", "v" * 4089]]
    assert _compare(data)["matches_expected_profile"] is True
    data["facts"][0]["headers"] = [["x", "v" * 4090]]
    with pytest.raises(ContractError):
        _compare(data)
    # Every field's four separator bytes count, including repeated fields.
    data["facts"][0]["headers"] = [["x", "v" * 4084], ["x", ""]]
    assert _compare(data)["matches_expected_profile"] is True
    data["facts"][0]["headers"].append(["x", ""])
    with pytest.raises(ContractError):
        _compare(data)


@pytest.mark.parametrize("field", ["name", "value"])
def test_oversized_single_header_is_refused_before_regex_or_character_scan(monkeypatch, field):
    class ForbiddenPattern:
        def fullmatch(self, value):
            pytest.fail("Oversized single header reached regex")

    monkeypatch.setattr(controls, "_HEADER_NAME", ForbiddenPattern())
    data = _scripted_facts()
    data["facts"][0]["headers"] = [["x" * 4091, ""]] if field == "name" else [["x", "v" * 4090]]
    with pytest.raises(ContractError):
        _compare(data)


def test_header_budget_counts_utf8_bytes_not_only_character_count():
    data = _scripted_facts()
    data["facts"][0]["headers"] = [["x", "é" * 2044 + "v"]]
    assert _compare(data)["matches_expected_profile"] is True
    data["facts"][0]["headers"] = [["x", "é" * 2045]]
    with pytest.raises(ContractError):
        _compare(data)


@pytest.mark.parametrize(
    "body", [None, True, [], "!", "Zg=", "Zh==", "Zg==\n", "Zg===", "é", "A" * 10925]
)
def test_body_encoding_is_canonical_strict_base64_and_bounded_before_decode(body):
    data = _scripted_facts()
    data["facts"][0]["body_base64"] = body
    with pytest.raises(ContractError):
        _compare(data)


def test_decoded_body_limit_is_8192_not_base64_length_only():
    data = _scripted_facts()
    data["facts"][0]["body_base64"] = base64.b64encode(b"x" * 8192).decode("ascii")
    assert _compare(data)["comparison_status"] == "profile-mismatch"
    data["facts"][0]["body_base64"] = base64.b64encode(b"x" * 8193).decode("ascii")
    with pytest.raises(ContractError):
        _compare(data)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        True,
        "",
        "[]",
        '{"kind":1,"kind":2}',
        '{"kind":NaN}',
        '{"kind":1e999}',
        "{" * 17,
        " " * 262145,
        '{"x":"\\ud800"}',
    ],
)
def test_malformed_duplicate_deep_oversized_nonfinite_json_is_rejected(raw):
    with pytest.raises(ContractError):
        controls.compare_generated_repair_observations(
            raw, controls.build_generated_repair_controls(), candidate="after"
        )


def test_nesting_bound_runs_before_json_parser(monkeypatch):
    material = controls.build_generated_repair_controls()
    # Compare malformed controls directly to avoid expected controls revalidation
    # legitimately using the shared parser before the hostile observation text.
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("Deep input reached parser"))
    with pytest.raises(ContractError):
        controls.validate_generated_repair_controls('{"x":' + "[" * 17 + "0" + "]" * 17 + "}")
    assert material is not None


def test_delimiters_and_escaped_quotes_in_strings_do_not_count_as_nesting():
    data = _scripted_facts()
    data["facts"][0]["headers"] = [["x-data", '[{"quoted": "escaped \\" ["}]' * 12]]
    assert _compare(data)["matches_expected_profile"] is True


@pytest.mark.parametrize("status", [401, 403, 404, 422, 500])
def test_before_requires_exact_intended_disclosure_not_generic_failure(status):
    data = _scripted_facts("before")
    data["facts"][2]["status_code"] = status
    comparison = _compare(data, "before")
    assert comparison["comparison_status"] == "profile-mismatch"
    assert comparison["matching_request_count"] == 20
    assert comparison["cases"][2]["requests"][0]["reasons"] == ["status-code-mismatch"]


def test_before_requires_disclosed_target_payload_not_wrong_document():
    data = _scripted_facts("before")
    data["facts"][2]["body_base64"] = data["facts"][0]["body_base64"]
    comparison = _compare(data, "before")
    assert comparison["comparison_status"] == "profile-mismatch"
    assert comparison["cases"][2]["requests"][0]["reasons"] == ["body-json-mismatch"]


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"\xff",
        b"[]",
        b"null",
        b'{"detail":"Forbidden","detail":"Forbidden"}',
        b'{"detail":NaN}',
        b"[" * 17 + b"0" + b"]" * 17,
        b"__import__('os').system('false')",
    ],
)
def test_invalid_body_is_data_mismatch_not_execution_or_fabricated_denial(body):
    data = _scripted_facts()
    data["facts"][2]["body_base64"] = base64.b64encode(body).decode("ascii")
    comparison = _compare(data)
    assert comparison["comparison_status"] == "profile-mismatch"
    assert "body-json-mismatch" in comparison["cases"][2]["requests"][0]["reasons"]


def test_equivalent_json_whitespace_order_is_allowed_but_extra_keys_are_not():
    data = _scripted_facts()
    data["facts"][0]["body_base64"] = base64.b64encode(
        rb'{ "owner":"alice", "body":"Alice\u0027s synthetic document", "id":"doc-alice" }'
    ).decode("ascii")
    assert _compare(data)["matches_expected_profile"] is True
    data["facts"][0]["body_base64"] = base64.b64encode(
        rb'{"owner":"alice","body":"Alice\u0027s synthetic document","id":"doc-alice","extra":true}'
    ).decode("ascii")
    assert _compare(data)["comparison_status"] == "profile-mismatch"


@pytest.mark.parametrize(
    ("marker", "location"),
    [
        ("doc-bob", "name"),
        ("bob", "name"),
        ("BOB", "name"),
        ("doc-bob", "value"),
        ("bob", "value"),
        ("Bob's synthetic document", "value"),
        ("BOB", "value"),
    ],
)
def test_nonowner_denial_disallows_protected_plaintext_in_headers(marker, location):
    data = _scripted_facts()
    data["facts"][2]["headers"].append(
        [marker, "present"] if location == "name" else ["x-leak", marker]
    )
    comparison = _compare(data)
    assert comparison["cases"][2]["requests"][0]["reasons"] == ["protected-plaintext-marker"]
    assert comparison["comparison_status"] == "profile-mismatch"


def test_normal_sequence_ending_owner_read_must_remain_unchanged():
    data = _scripted_facts()
    data["facts"][-1]["status_code"] = 403
    comparison = _compare(data)
    assert comparison["matching_case_count"] == 16
    assert comparison["matching_request_count"] == 20
    assert comparison["cases"][-1]["matches"] is False
    assert [row["matches"] for row in comparison["cases"][-1]["requests"]] == [True, True, False]


def test_swapping_entire_before_after_profiles_cannot_become_success():
    before = _scripted_facts("before")
    before["candidate"] = "after"
    after = _scripted_facts("after")
    after["candidate"] = "before"
    assert _compare(before)["comparison_status"] == "profile-mismatch"
    assert _compare(after, "before")["comparison_status"] == "profile-mismatch"


def test_untrusted_fact_strings_stay_inert_and_do_not_appear_in_summary():
    data = _scripted_facts()
    source = b"import os\nos.system('false')\nraise RuntimeError('never execute')"
    data["facts"][0]["body_base64"] = base64.b64encode(source).decode("ascii")
    comparison = _compare(data)
    assert comparison["comparison_status"] == "profile-mismatch"
    assert "never execute" not in canonical(comparison)
    assert "body_base64" not in canonical(comparison)
