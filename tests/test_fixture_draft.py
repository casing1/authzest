import builtins
import json
import socket
import subprocess
from pathlib import Path

import pytest

from authzest.codex.contracts import CodexAnalysisRequest, ContractError, canonical, identity
from authzest.codex.fixture_draft import (
    FIXTURE_AFTER,
    FIXTURE_DRAFT_SCHEMA_VERSION,
    FIXTURE_PROMPT_VERSION,
    FIXTURE_SOURCE,
    build_fixture_request,
    fixture_output_schema,
    fixture_prompt,
    validate_fixture_draft,
)
from authzest.codex.proposals import CHECK_IDS, content_hash, proposal_preview


@pytest.fixture
def context():
    return build_fixture_request("fixture-test-model")


def response_data(request):
    """Caller-authored offline test response; never represented as a live model result."""
    source_id = next(
        item["id"] for item in request.to_dict()["evidence"] if item["kind"] == "source"
    )
    return {
        "answers": [
            {
                "question_id": "review",
                "status": "hypothesis",
                "answer": "Consider explicitly disabling debug mode.",
                "explanation": "The fixture declares debug=True; its deployment is not observed.",
                "evidence_ids": [source_id],
                "assumptions": ["The supplied deployment policy is intended."],
                "unknowns": ["Runtime effects have not been tested."],
                "review_questions": ["Is this policy appropriate for the intended deployment?"],
            }
        ],
        "after_text": FIXTURE_AFTER,
        "reason": "Explicitly disable the declared framework debug setting.",
        "uncertainties": ["Source configuration alone does not establish runtime behavior."],
        "side_effects": ["This setting would no longer enable debug diagnostics."],
    }


def test_packaged_source_matches_maintained_fixture_and_known_hashes():
    fixture = Path(__file__).parent / "fixtures/proposal_demo/main.py"
    assert fixture.read_text(encoding="utf-8") == FIXTURE_SOURCE
    assert len(FIXTURE_SOURCE.splitlines()) == 10
    assert content_hash(FIXTURE_SOURCE) == (
        "c10770594e77cd1c1ec93c19ef2b810aea34ed873d8dbf392b57e50a1c2729df"
    )
    assert content_hash(FIXTURE_AFTER) == (
        "e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe"
    )


def test_request_uses_real_static_parser_and_is_deterministic(context, tmp_path, monkeypatch):
    request = context
    (tmp_path / "main.py").write_text("raise RuntimeError('unrelated source must not be read')")
    monkeypatch.chdir(tmp_path)
    another = build_fixture_request("fixture-test-model")
    assert another.request_id == request.request_id
    payload = request.to_dict()
    assert payload["config"] == {
        "provider": "codex-app-server",
        "model": "fixture-test-model",
        "adapter_version": "0.1",
        "prompt_version": FIXTURE_PROMPT_VERSION,
        "temperature": None,
        "seed": None,
    }
    assert payload["schema_version"] == "1.1"
    assert payload["source_revision"] is None
    assert payload["source_identity"] == identity({"main.py": FIXTURE_SOURCE})
    assert payload["mode"] == "evidence-plus-model"
    sources = [item["data"] for item in payload["evidence"] if item["kind"] == "source"]
    assert sources == [{"path": "main.py", "text": FIXTURE_SOURCE}]
    routes = [item["data"] for item in payload["evidence"] if item["kind"] == "route"]
    assert len(routes) == 1
    assert routes[0]["file"] == "main.py"
    assert routes[0]["path"] == "/health"
    assert routes[0]["methods"] == ["GET"]
    assert routes[0]["function"] == "health"
    assert routes[0]["line"] == 9
    assert str(tmp_path) not in request.payload_json
    assert "authzest-source-fixture-" not in request.payload_json


def test_request_reads_only_private_temporary_copy_and_never_imports_or_executes(monkeypatch):
    original_import = builtins.__import__
    original_read = Path.read_bytes
    reads = []

    def checked_import(name, *args, **kwargs):
        assert name != "fastapi", "Fixture source must not be imported"
        return original_import(name, *args, **kwargs)

    def read(path):
        assert path.name == "main.py"
        assert path.parent.name.startswith("authzest-source-fixture-")
        reads.append(path)
        return original_read(path)

    def forbidden(*args, **kwargs):
        pytest.fail("Source context must not start a process or access the network")

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    build_fixture_request("fixture-test-model")
    assert reads
    assert all(not path.parent.exists() for path in reads)


@pytest.mark.parametrize("model", ["", " spaces ", "a\nmodel", "a" * 129, None, 1])
def test_invalid_model_identity_rejected_before_source_scan(model, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid identity must fail before source reads")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    with pytest.raises(ContractError):
        build_fixture_request(model)


@pytest.mark.parametrize("helper", [fixture_prompt, fixture_output_schema, validate_fixture_draft])
@pytest.mark.parametrize("mutation", ["provider", "temperature", "revision", "question", "policy"])
def test_helpers_reject_valid_but_nonfixture_requests(context, helper, mutation):
    request = context
    payload = request.to_dict()
    if mutation == "provider":
        payload["config"]["provider"] = "other-provider"
    elif mutation == "temperature":
        payload["config"]["temperature"] = 0.0
    elif mutation == "revision":
        payload["source_revision"] = "a" * 40
    elif mutation == "question":
        payload["questions"][0]["text"] = "Unreviewed extra question."
    else:
        policy = next(item for item in payload["evidence"] if item["kind"] == "policy")
        policy["data"] = "Unreviewed extra policy."
        policy["id"] = "ev-" + identity({"kind": policy["kind"], "data": policy["data"]})
    changed = CodexAnalysisRequest(canonical(payload))
    with pytest.raises(ContractError, match="exact packaged fixture"):
        if helper is validate_fixture_draft:
            helper(canonical(response_data(request)), changed, usage=None)
        else:
            helper(changed)


def test_prompt_is_versioned_full_previewable_input_with_no_ambient_data(context):
    request = context
    prompt = fixture_prompt(request)
    assert FIXTURE_PROMPT_VERSION in prompt
    assert FIXTURE_DRAFT_SCHEMA_VERSION in prompt
    assert "Do not use tools" in prompt
    assert "not an exploit" in prompt
    assert "separate user decision" in prompt
    assert json.loads(prompt.split("REQUEST DATA:\n", 1)[1]) == request.to_dict()


def test_schema_is_strict_detached_and_does_not_delegate_host_metadata(context):
    request = context
    schema = fixture_output_schema(request)
    assert schema["title"].endswith(FIXTURE_DRAFT_SCHEMA_VERSION)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(response_data(request))
    assert set(schema["properties"]) == set(schema["required"])
    answer = schema["properties"]["answers"]["items"]
    assert answer["additionalProperties"] is False
    assert set(answer["required"]) == set(response_data(request)["answers"][0])
    assert answer["properties"]["question_id"]["enum"] == ["review"]
    assert answer["properties"]["status"]["enum"] == ["hypothesis", "unknown"]
    assert schema["properties"]["uncertainties"]["maxItems"] == 31
    schema["properties"].clear()
    assert fixture_output_schema(request)["properties"]


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"input_tokens": 123, "output_tokens": 45},
        {"input_tokens": None, "output_tokens": None},
    ],
)
def test_draft_binds_review_and_exact_diff_without_approval_or_verification(context, usage):
    request = context
    result = validate_fixture_draft(canonical(response_data(request)), request, usage=usage)
    review = result.review.to_dict()
    assert review["request_id"] == request.request_id
    assert review["schema_version"] == request.to_dict()["schema_version"]
    assert review["identity"] == {
        key: request.to_dict()["config"][key]
        for key in ("provider", "model", "adapter_version", "prompt_version")
    }
    assert review["usage"] == usage
    proposal = result.proposal.to_dict()
    assert proposal["review_id"] == identity(review)
    assert proposal["changes"][0]["before_sha256"] == content_hash(FIXTURE_SOURCE)
    assert proposal["changes"][0]["after_text"] == FIXTURE_AFTER
    assert tuple(proposal["verification"]["checks"]) == CHECK_IDS
    assert "not an authorization finding or verified fix" in proposal["uncertainties"][-1]
    preview = proposal_preview(result.proposal, request, result.review)
    assert (
        "-app = FastAPI(debug=True)\n+app = FastAPI(debug=False)\n" in preview["changes"][0]["diff"]
    )
    assert preview["applied"] is False
    assert preview["verification_status"] == "not-run"


def test_unknown_answer_remains_an_explicit_abstention(context):
    request = context
    data = response_data(request)
    data["answers"][0].update(status="unknown", answer=None)
    result = validate_fixture_draft(canonical(data), request, usage=None)
    assert result.review.to_dict()["answers"][0]["answer"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "extra-usage",
        "extra-identity",
        "extra-command",
        "missing-field",
        "no-op",
        "arbitrary-source",
        "missing-newline",
        "extra-whitespace",
        "non-string-source",
        "missing-answer",
        "extra-answer",
        "confirmed-answer",
        "wrong-question",
        "invented-citation",
        "policy-only-citation",
        "unknown-without-abstention",
        "empty-uncertainties",
        "too-many-uncertainties",
        "string-uncertainties",
        "bad-uncertainty",
        "string-side-effects",
        "too-many-side-effects",
        "bad-side-effect",
        "blank-reason",
        "long-reason",
        "terminal-control",
        "non-string-reason",
    ],
)
def test_invalid_model_fields_rejected(context, mutation):
    request = context
    data = response_data(request)
    answer = data["answers"][0]
    if mutation.startswith("extra-") and mutation not in ("extra-answer", "extra-whitespace"):
        data[mutation.removeprefix("extra-")] = "Model must not supply authoritative metadata"
    elif mutation == "missing-field":
        del data["reason"]
    elif mutation == "no-op":
        data["after_text"] = FIXTURE_SOURCE
    elif mutation == "arbitrary-source":
        data["after_text"] = FIXTURE_AFTER + "raise RuntimeError('not accepted')\n"
    elif mutation == "missing-newline":
        data["after_text"] = FIXTURE_AFTER.rstrip("\n")
    elif mutation == "extra-whitespace":
        data["after_text"] = FIXTURE_AFTER + "\n"
    elif mutation == "non-string-source":
        data["after_text"] = {"text": FIXTURE_AFTER}
    elif mutation == "missing-answer":
        data["answers"] = []
    elif mutation == "extra-answer":
        data["answers"] *= 2
    elif mutation == "confirmed-answer":
        answer["status"] = "confirmed"
    elif mutation == "wrong-question":
        answer["question_id"] = "unasked"
    elif mutation == "invented-citation":
        answer["evidence_ids"] = ["ev-missing"]
    elif mutation == "policy-only-citation":
        answer["evidence_ids"] = [
            next(item["id"] for item in request.to_dict()["evidence"] if item["kind"] == "policy")
        ]
    elif mutation == "unknown-without-abstention":
        answer["status"] = "unknown"
    elif mutation == "empty-uncertainties":
        data["uncertainties"] = []
    elif mutation == "too-many-uncertainties":
        data["uncertainties"] *= 32
    elif mutation == "string-uncertainties":
        data["uncertainties"] = "not an array"
    elif mutation == "bad-uncertainty":
        data["uncertainties"] = [1]
    elif mutation == "string-side-effects":
        data["side_effects"] = "not an array"
    elif mutation == "too-many-side-effects":
        data["side_effects"] *= 33
    elif mutation == "bad-side-effect":
        data["side_effects"] = [False]
    elif mutation == "blank-reason":
        data["reason"] = " "
    elif mutation == "long-reason":
        data["reason"] = "a" * 4097
    elif mutation == "terminal-control":
        data["reason"] = "\x1b[31mterminal escape"
    else:
        data["reason"] = 1
    with pytest.raises(ContractError):
        validate_fixture_draft(canonical(data), request, usage=None)


@pytest.mark.parametrize(
    "raw", ["not json", "[]", "{}", '{"x": 1, "x": 2}', '{"x": NaN}', "x" * 262145]
)
def test_invalid_raw_json_rejected(context, raw):
    request = context
    with pytest.raises(ContractError):
        validate_fixture_draft(raw, request, usage=None)


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"input_tokens": 1},
        {"input_tokens": 1, "output_tokens": 2, "cost": 0},
        {"input_tokens": -1, "output_tokens": 2},
        {"input_tokens": True, "output_tokens": 2},
        {"input_tokens": 1, "output_tokens": "2"},
    ],
)
def test_transport_usage_still_requires_valid_contract(context, usage):
    request = context
    with pytest.raises(ContractError):
        validate_fixture_draft(canonical(response_data(request)), request, usage=usage)


def test_maximum_model_uncertainties_leave_space_for_host_limit(context):
    request = context
    data = response_data(request)
    data["uncertainties"] *= 31
    result = validate_fixture_draft(canonical(data), request, usage=None)
    assert len(result.proposal.to_dict()["uncertainties"]) == 32
