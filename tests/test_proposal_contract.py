import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from authzest.codex.contracts import (
    CodexAnalysisRequest,
    ContractError,
    ValidatedResponse,
    canonical,
    identity,
    prepare_request,
    validate_response,
)
from authzest.codex.mock import scripted_response
from authzest.codex.proposals import (
    ValidatedProposal,
    content_hash,
    prepare_proposal,
    proposal_preview,
    validate_proposal,
)
from authzest.runner import ScanRunner

SOURCE = (
    "from fastapi import FastAPI\napp = FastAPI(debug=True)\n"
    '@app.get("/health")\ndef health(): return {"ok": True}\n'
)
AFTER = SOURCE.replace("debug=True", "debug=False")


def make_context(tmp_path, sources=None, revision=None):
    (tmp_path / "main.py").write_text(SOURCE, encoding="utf-8")
    report = ScanRunner().run(tmp_path)
    request = prepare_request(
        report,
        registration_ids=(),
        sources=sources or {"main.py": SOURCE},
        policies=("Debug should be disabled.",),
        questions=(("review", "Review configuration."),),
        source_revision=revision,
    )
    review = validate_response(
        scripted_response(request, {"review": "Consider disabling debug."}), request
    )
    return request, review


def draft(request, review, **overrides):
    args = dict(
        replacements={"main.py": AFTER},
        rationale="Known caller-authored change.",
        uncertainties=("Runtime impact is unverified.",),
        side_effects=("Debug output disabled.",),
        checks=("fixture-static-inventory",),
        expectations=("Route inventory remains unchanged.",),
    )
    args.update(overrides)
    return prepare_proposal(request, review, **args)


@pytest.fixture
def context(tmp_path):
    return make_context(tmp_path)


def test_exact_diff_identity_and_detached_preview(context):
    request, review = context
    proposal = draft(request, review)
    preview = proposal_preview(proposal, request, review)
    assert preview["changes"][0]["diff"] == (
        "--- a/main.py\n+++ b/main.py\n@@ -1,4 +1,4 @@\n from fastapi import FastAPI\n"
        '-app = FastAPI(debug=True)\n+app = FastAPI(debug=False)\n @app.get("/health")\n'
        ' def health(): return {"ok": True}\n'
    )
    assert preview["changes"][0]["before_sha256"] == content_hash(SOURCE)
    assert preview["changes"][0]["after_sha256"] == content_hash(AFTER)
    assert preview["applied"] is False and preview["verification_status"] == "not-run"
    digest = proposal.proposal_id
    preview["verification"]["checks"].clear()
    proposal.to_dict()["changes"].clear()
    assert proposal.proposal_id == digest
    with pytest.raises(FrozenInstanceError):
        proposal.payload_json = "{}"


@pytest.mark.parametrize("change", ["content", "rationale", "uncertainty", "side-effects", "plan"])
def test_every_material_proposal_change_changes_identity(context, change):
    request, review = context
    original = draft(request, review)
    overrides = {
        "content": {"replacements": {"main.py": AFTER + "# extra change\n"}},
        "rationale": {"rationale": "Another reason."},
        "uncertainty": {"uncertainties": ("Different uncertainty.",)},
        "side-effects": {"side_effects": ()},
        "plan": {"checks": ("fixture-regression-tests",)},
    }
    assert draft(request, review, **overrides[change]).proposal_id != original.proposal_id


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "request",
        "review",
        "extra-diff",
        "create",
        "delete",
        "wrong-hash",
        "no-op",
        "empty-change",
        "duplicate",
        "missing-reference",
        "wrong-reference",
        "empty-uncertainty",
        "shell-check",
        "extra-command",
        "empty-check",
        "duplicate-check",
        "empty-expectation",
        "extra-change-field",
        "bad-after",
        "control-char",
        "too-large",
    ],
)
def test_invalid_proposal_is_rejected(context, mutation):
    request, review = context
    data = draft(request, review).to_dict()
    change = data["changes"][0]
    if mutation == "schema":
        data["schema_version"] = "2.0"
    elif mutation == "request":
        data["request_id"] = "request-stale"
    elif mutation == "review":
        data["review_id"] = "0" * 64
    elif mutation == "extra-diff":
        data["diff"] = "a separate inconsistent diff"
    elif mutation == "create":
        change["path"] = "new.py"
    elif mutation == "delete":
        change["after_text"] = ""
    elif mutation == "wrong-hash":
        change["before_sha256"] = "0" * 64
    elif mutation == "no-op":
        change["after_text"] = SOURCE
    elif mutation == "empty-change":
        data["changes"] = []
    elif mutation == "duplicate":
        data["changes"] *= 2
    elif mutation == "missing-reference":
        change["evidence_ids"] = []
    elif mutation == "wrong-reference":
        change["evidence_ids"] = ["ev-missing"]
    elif mutation == "empty-uncertainty":
        data["uncertainties"] = []
    elif mutation == "shell-check":
        data["verification"]["checks"] = ["shell-command"]
    elif mutation == "extra-command":
        data["verification"]["command"] = "not permitted"
    elif mutation == "empty-check":
        data["verification"]["checks"] = []
    elif mutation == "duplicate-check":
        data["verification"]["checks"] *= 2
    elif mutation == "empty-expectation":
        data["verification"]["expectations"] = []
    elif mutation == "extra-change-field":
        change["mode"] = "executable"
    elif mutation == "bad-after":
        change["after_text"] = 123
    elif mutation == "control-char":
        change["after_text"] = "\x1b[31mnot text"
    else:
        change["after_text"] = "x" * 32_769
    with pytest.raises(ContractError):
        validate_proposal(canonical(data), request, review)


@pytest.mark.parametrize(
    "path",
    [
        "../main.py",
        "/main.py",
        "C:/main.py",
        "a\\main.py",
        "a//main.py",
        "./main.py",
        ".git/hook.py",
        ".github/workflows/script.py",
        "node_modules/app.py",
        "main.sh",
        "app/hidden\n.py",
        "app/\u202efile.py",
    ],
)
def test_unsafe_or_unsupported_paths_rejected(context, path):
    request, review = context
    data = draft(request, review).to_dict()
    data["changes"][0]["path"] = path
    with pytest.raises(ContractError):
        validate_proposal(canonical(data), request, review)


def test_case_colliding_selected_sources_rejected(tmp_path):
    request, review = make_context(tmp_path, {"main.py": SOURCE, "MAIN.py": SOURCE})
    with pytest.raises(ContractError):
        draft(request, review)


def test_multiple_files_have_deterministic_order_and_separate_diffs(tmp_path):
    request, review = make_context(tmp_path, {"main.py": SOURCE, "helper.py": "VALUE = 1\n"})
    proposal = draft(request, review, replacements={"main.py": AFTER, "helper.py": "VALUE = 2\n"})
    changes = proposal_preview(proposal, request, review)["changes"]
    assert [change["path"] for change in changes] == ["helper.py", "main.py"]
    assert "-VALUE = 1\n+VALUE = 2\n" in changes[0]["diff"]
    assert "-app = FastAPI(debug=True)\n+app = FastAPI(debug=False)\n" in changes[1]["diff"]


def test_changed_review_and_forged_wrapper_are_revalidated(context):
    request, review = context
    proposal = draft(request, review)
    changed = validate_response(
        scripted_response(request, {"review": "Different review."}), request
    )
    with pytest.raises(ContractError):
        proposal_preview(proposal, request, changed)
    with pytest.raises(ContractError):
        draft(request, ValidatedResponse("{}"))
    with pytest.raises(ContractError):
        proposal_preview(ValidatedProposal("{}"), request, review)


def test_missing_final_newline_is_visible(tmp_path):
    request, review = make_context(tmp_path, {"main.py": SOURCE.rstrip("\n")})
    proposal = draft(request, review, replacements={"main.py": AFTER.rstrip("\n") + "# edited"})
    diff = proposal_preview(proposal, request, review)["changes"][0]["diff"]
    assert "\\ No newline at end of file\n" in diff


def test_crlf_is_not_silently_normalized(tmp_path):
    source = SOURCE.replace("\n", "\r\n")
    request, review = make_context(tmp_path, {"main.py": source})
    proposal = draft(request, review)
    assert content_hash(source) != content_hash(SOURCE)
    assert "\r\n" in proposal_preview(proposal, request, review)["changes"][0]["diff"]


def test_unicode_separators_are_not_diff_line_boundaries(tmp_path):
    source = SOURCE + 'TEXT = "line\u2028value"\n'
    request, review = make_context(tmp_path, {"main.py": source})
    proposal = draft(
        request, review, replacements={"main.py": source.replace("debug=True", "debug=False")}
    )
    diff = proposal_preview(proposal, request, review)["changes"][0]["diff"]
    assert "@@ -1,5 +1,5 @@" in diff
    assert "\\ No newline at end of file" not in diff


def test_case_insensitive_reserved_target_is_rejected(tmp_path):
    request, review = make_context(tmp_path, {"main.py": SOURCE, "Node_Modules/main.py": SOURCE})
    with pytest.raises(ContractError):
        draft(request, review, replacements={"Node_Modules/main.py": AFTER})


def test_validation_and_preview_do_not_read_or_write_files(context, monkeypatch):
    request, review = context

    def forbidden(*a, **kw):
        pytest.fail("Proposal operations must not access files")

    for method in ("read_text", "read_bytes", "write_text", "write_bytes", "open"):
        monkeypatch.setattr(Path, method, forbidden)
    proposal = draft(request, review)
    assert proposal_preview(proposal, request, review)["applied"] is False


def test_new_input_identity_invalidates_original_proposal(context):
    request, review = context
    proposal = draft(request, review)
    data = request.to_dict()
    data["config"]["model"] = "different-mock"
    changed_request = CodexAnalysisRequest(canonical(data))
    changed_review = validate_response(
        scripted_response(changed_request, {"review": "Review."}), changed_request
    )
    with pytest.raises(ContractError):
        validate_proposal(proposal.payload_json, changed_request, changed_review)


def test_no_false_semantic_guarantee(context):
    request, review = context
    proposal = draft(request, review, rationale="Unverified arbitrary provider prose.")
    assert proposal.to_dict()["rationale"] == "Unverified arbitrary provider prose."
    assert proposal_preview(proposal, request, review)["verification_status"] == "not-run"


def test_record_is_serializable_and_review_identity_is_bound(context):
    request, review = context
    proposal = draft(request, review)
    assert json.loads(proposal.payload_json)["review_id"] == identity(review.to_dict())
