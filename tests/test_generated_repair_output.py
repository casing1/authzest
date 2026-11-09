"""Presentation-only scripted artifacts, never model or runtime observations."""

from __future__ import annotations

import copy
import json
import socket
import subprocess

import pytest

from authzest.cli_output import (
    WorkflowOutput,
    format_generated_repair_result,
    format_record,
    format_sharing_preview,
    json_output,
)
from authzest.codex.contracts import canonical
from authzest.codex.generated_repair import (
    prepare_generated_repair_preview,
    validate_generated_repair_proposal,
)
from authzest.codex.generated_repair_transport import (
    build_generated_repair_transport_request,
    prepare_generated_repair_transport_result,
)
from authzest.runner.codex_generated_repair import build_generated_repair_sharing_preview
from test_generated_repair import draft
from test_generated_repair_transport import inner

SOURCE_MARKER = "scripted_generated_source_marker"
TEST_MARKER = "scripted_generated_test_marker"


@pytest.fixture(autouse=True)
def no_process_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Presentation tests cannot execute generated code or access providers")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def result(status="proposed-change", *, final_newline=True):
    """Construct current contract artifacts with no adapter, process, files or AI."""
    request = build_generated_repair_transport_request("offline-output-test-model")
    generation_request = inner(request)
    raw = draft(generation_request, status)
    raw["rationale"] = "Scripted rationale marker; no runtime observation."
    raw["assumptions"] = ["Scripted assumption marker."]
    raw["uncertainties"] = ["Scripted uncertainty marker."]
    raw["limitations"] = ["Scripted limitation marker."]
    if raw["proposal"]:
        raw["proposal"]["after_text"] += f"# {SOURCE_MARKER}\n"
        raw["proposal"]["test_text"] += f"# {TEST_MARKER}\n"
        if not final_newline:
            for key in ("after_text", "test_text"):
                raw["proposal"][key] = raw["proposal"][key].removesuffix("\n")
    transport = prepare_generated_repair_transport_result(
        canonical(raw), request, usage={"input_tokens": 11, "output_tokens": 22}
    )
    preview = prepare_generated_repair_preview(
        # The transport already validated this exact scripted proposal.
        # Reconstruct only its inert contract wrapper, never import its source.
        validate_generated_repair_proposal(canonical(raw), generation_request),
        generation_request,
    ).to_dict()
    return {
        "kind": "codex-generated-repair-workflow",
        "status": "generation-ready",
        "exit_code": 0,
        "request_id": request.request_id,
        "generation_request_id": generation_request.request_id,
        "sharing_id": "share-private-marker",
        "sharing_content_id": "content-private-marker",
        "invocation_nonce": "nonce-private-marker",
        "sharing_decision": "approve",
        "limits": {"timeout_seconds": 120, "application_retries": 0},
        "application_turn_attempts": 1,
        "returned_identity": transport.to_dict()["identity"],
        "model_identity_basis": transport.to_dict()["identity_basis"],
        "usage": transport.to_dict()["usage"],
        "provider_warning_count": 0,
        "provider_retry_notification_count": 0,
        "latency_ms": 1.25,
        "generation": transport.to_dict(),
        "proposal_status": status,
        "proposal_preview": preview,
        "failure": None,
        "applied": False,
        "original_checkout_modified": False,
        "execution_status": "not-run",
        "patch_application": "not-run",
        "restoration_status": "not-run",
        "authorization_status": "unknown",
    }


def test_default_result_has_distinct_host_summary_and_model_explanation():
    text = format_generated_repair_result(result())
    assert text.startswith("Generated repair result\n")
    for value in ("generation-ready", "proposed-change", "not-run", "unknown"):
        assert value in text
    for label in ("Execution", "Patch application", "Restoration", "Authorization"):
        assert label in text
    for marker in ("rationale", "assumption", "uncertainty", "limitation"):
        assert f"Scripted {marker} marker" in text
    for notice in ("unverified", "ast-parse-only", "not-assessed", "pending-maintainer-review"):
        assert notice in text
    assert "Changed files" in text
    assert "app.py" in text and "tests/test_generated_ownership.py" in text


def test_source_test_and_exact_diff_are_rendered_once_with_individual_inert_lines():
    value = result()
    text = format_generated_repair_result(value)
    assert text.count("Generated source (untrusted; not executed)") == 1
    assert text.count("Generated test (untrusted; not executed)") == 1
    assert text.count("Exact proposed diff (untrusted; not applied)") == 1
    # Each candidate appears once in its code block and once in its exact diff,
    # not again through nested transport/proposal/preview serialization.
    for marker in (SOURCE_MARKER, TEST_MARKER):
        assert text.count(marker) == 2
    assert "\\ndef test_scripted_candidate" not in text
    assert "  | def test_scripted_candidate():" in text
    assert "  |     assert True" in text
    assert "  | --- /dev/null" in text
    assert "  | +++ b/tests/test_generated_ownership.py" in text
    for change in value["proposal_preview"]["changes"]:
        for line in change["diff"].split("\n"):
            if line:
                assert "  | " + line in text


def test_default_hides_transport_identifiers_evidence_hashes_and_usage():
    value = result()
    text = format_generated_repair_result(value)
    for key in ("request_id", "generation_request_id", "sharing_id", "sharing_content_id"):
        assert value[key] not in text
    assert value["invocation_nonce"] not in text
    for evidence_id in value["generation"]["proposal"]["evidence_ids"]:
        assert evidence_id not in text
    for change in value["proposal_preview"]["changes"]:
        for key in ("before_sha256", "after_sha256"):
            if change[key]:
                assert change[key] not in text
    for field in ("input_tokens", "output_tokens", "latency_ms", "adapter_version"):
        assert field not in text
    assert "--details" in text


def test_missing_source_and_test_final_newline_stays_explicit_in_exact_diff():
    value = result(final_newline=False)
    text = format_generated_repair_result(value)
    assert "no newline at end of file" in text.lower()
    # Prefixing and literal-backslash escaping do not silently insert an LF
    # into either candidate or turn the diff marker into a host instruction.
    assert r"  | \\ No newline at end of file" in text
    for field in ("after_text", "test_text"):
        assert not value["generation"]["proposal"]["proposal"][field].endswith("\n")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("code\n", "  | code\n  | "),
        ("code", "  | code\n  [No terminal LF in this text]"),
        ("", "  | \n  [No terminal LF in this text]"),
    ],
)
def test_source_display_distinguishes_terminal_lf_no_lf_and_empty_text(source, expected):
    value = result()
    value["generation"]["proposal"]["proposal"]["after_text"] = source
    text = format_generated_repair_result(value)
    source_block = text.split("Generated source (untrusted; not executed)\n", 1)[1]
    assert source_block.split("\n\n", 1)[0] == expected


@pytest.mark.parametrize(
    ("separator", "escaped"),
    [("\r", r"\r"), ("\f", r"\f"), ("\u2028", r"\u2028"), ("\u2029", r"\u2029")],
)
def test_only_lf_separates_source_lines_other_separators_are_visible_inert_text(separator, escaped):
    value = result()
    value["generation"]["proposal"]["proposal"]["after_text"] = "FIRST" + separator + "SECOND"
    text = format_generated_repair_result(value)
    source_block = text.split("Generated source (untrusted; not executed)\n", 1)[1]
    assert source_block.split("\n\n", 1)[0] == (
        "  | FIRST" + escaped + "SECOND\n  [No terminal LF in this text]"
    )


@pytest.mark.parametrize(
    ("generation", "preview"),
    [
        (None, None),
        ([], []),
        ("malformed", "malformed"),
        ({"proposal": None}, {"changes": None}),
        ({"proposal": []}, {}),
        ({"proposal": "malformed"}, {}),
    ],
)
def test_malformed_nested_results_remain_unknown_without_crashes_or_invented_observations(
    generation, preview
):
    value = {
        "kind": "codex-generated-repair-workflow",
        "status": "generation-ready",
        "generation": generation,
        "proposal_preview": preview,
    }
    text = format_generated_repair_result(value)
    assert "unknown (not reported)" in text
    assert "Generated source (untrusted; not executed)" not in text
    assert "Generated test (untrusted; not executed)" not in text
    for label in ("Execution", "Patch application", "Restoration", "Authorization"):
        line = next(line for line in text.splitlines() if line.lstrip().startswith(label + ":"))
        assert "unknown" in line and "not-run" not in line and "passed" not in line


def test_details_append_the_complete_unmodified_authoritative_json():
    value = result()
    before = copy.deepcopy(value)
    default = format_generated_repair_result(value)
    detailed = format_generated_repair_result(value, details=True)
    heading = "Complete result (authoritative JSON)\n"
    assert heading not in default
    assert detailed.startswith(default)
    assert detailed.count(heading) == 1
    serialized = detailed.split(heading, 1)[1]
    assert json.loads(serialized) == value
    assert serialized == json_output(value)
    assert value == before


@pytest.mark.parametrize("status", ["proposed-change", "no-change", "unknown", "refused"])
def test_four_proposal_statuses_are_distinct_and_never_become_a_runtime_pass(status):
    text = format_generated_repair_result(result(status))
    assert status in text
    assert "not-run" in text and "unknown" in text
    assert "Authorization: passed" not in text
    assert "Execution: passed" not in text
    if status != "proposed-change":
        assert "Generated source (untrusted; not executed)" not in text
        assert "Generated test (untrusted; not executed)" not in text
        assert "Exact proposed diff (untrusted; not applied)" not in text


@pytest.mark.parametrize(
    "status", ["not-shared", "cancelled", "generation-failed", "preview-changed"]
)
def test_decline_cancel_and_failures_do_not_invent_generated_code_or_provider_observations(status):
    value = result()
    value.update(
        status=status,
        proposal_status=None,
        generation=None,
        proposal_preview=None,
        returned_identity=None,
        usage=None,
        latency_ms=None,
        provider_warning_count=None,
        provider_retry_notification_count=None,
        failure={"stage": "turn-start", "code": "timeout", "turn_start": "unknown"}
        if status == "generation-failed"
        else None,
    )
    text = format_generated_repair_result(value)
    assert status in text
    assert "unknown" in text
    assert SOURCE_MARKER not in text and TEST_MARKER not in text
    assert "Generated source (untrusted; not executed)" not in text
    if value["failure"]:
        assert "timeout" in text and "turn-start" in text


def test_missing_statuses_remain_unknown_without_inference_from_applied_false():
    value = {
        "kind": "codex-generated-repair-workflow",
        "status": "generation-ready",
        "applied": False,
    }
    text = format_generated_repair_result(value)
    for label in ("Execution", "Patch application", "Restoration", "Authorization"):
        line = next(line for line in text.splitlines() if line.lstrip().startswith(label + ":"))
        assert "unknown" in line
        assert "not-run" not in line and "passed" not in line


def test_non_ascii_controls_tabs_crlf_bidi_and_forged_headings_are_inert_prefixed_lines():
    value = result()
    payload = "ATTACK\x1b[31m\u009b0m\u202e\u2066\t\r\nExecution: passed\n# 한국어 日本語"
    proposal = value["generation"]["proposal"]
    proposal["rationale"] = payload
    proposal["assumptions"] = [payload]
    proposal["uncertainties"] = [payload]
    proposal["limitations"] = [payload]
    proposal["proposal"]["after_text"] = payload
    proposal["proposal"]["test_text"] = payload
    value["proposal_preview"]["proposal"] = proposal
    value["proposal_preview"]["changes"][0]["diff"] = payload
    for details in (False, True):
        text = format_generated_repair_result(value, details=details)
        assert text.isascii()
        assert all(character == "\n" or 32 <= ord(character) <= 126 for character in text)
        for escaped in ("\\u001b", "\\u009b", "\\u202e", "\\u2066", "\\t", "\\r"):
            assert escaped in text
        human = text.split("Complete result (authoritative JSON)\n", 1)[0]
        for line in human.splitlines():
            if "ATTACK" in line or line.endswith("Execution: passed") or "\\ud55c" in line:
                assert line.startswith("  | ")
        assert "\nExecution: passed\n" not in human


@pytest.mark.parametrize("details", [False, True])
def test_workflow_output_keeps_authoritative_sharing_preview_complete_and_unchanged(
    capsys, details
):
    value = build_generated_repair_sharing_preview("offline-output-test-model")
    output = WorkflowOutput(details=details)
    output.emit(json_output(value))
    captured = capsys.readouterr()
    assert captured.out == format_sharing_preview(value) + "\n"
    assert not captured.err
    assert value["prompt"] in captured.out or "REQUEST_JSON" in captured.out
    complete = captured.out.split(
        "Complete sharing envelope (authoritative JSON; review every field before consent)\n", 1
    )[1]
    assert json.loads(complete) == value


@pytest.mark.parametrize("details", [False, True])
def test_json_result_is_one_unmodified_document_independent_of_details(capsys, details):
    value = result()
    WorkflowOutput(as_json=True, details=details).finish(value)
    captured = capsys.readouterr()
    assert captured.out == json_output(value) + "\n"
    assert json.loads(captured.out) == value
    assert not captured.err


@pytest.mark.parametrize("details", [False, True])
def test_workflow_finish_dispatches_only_the_generated_result_to_readable_formatter(
    capsys, details
):
    value = result()
    WorkflowOutput(details=details).finish(value)
    captured = capsys.readouterr()
    assert captured.out == format_generated_repair_result(value, details=details) + "\n"
    assert not captured.err


@pytest.mark.parametrize("details", [False, True])
def test_existing_non_generated_result_keeps_its_previous_human_format(capsys, details):
    value = {"kind": "codex-owner-repair-workflow", "status": "not-shared", "usage": None}
    WorkflowOutput(details=details).finish(value)
    captured = capsys.readouterr()
    assert captured.out == format_record(value) + "\n"
    assert not captured.err


@pytest.mark.parametrize("details", [False, True])
def test_json_interaction_remains_complete_on_stderr_not_stdout(capsys, details):
    value = build_generated_repair_sharing_preview("offline-output-test-model")
    WorkflowOutput(as_json=True, details=details).emit(json_output(value))
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == json_output(value) + "\n"
    assert json.loads(captured.err) == value
