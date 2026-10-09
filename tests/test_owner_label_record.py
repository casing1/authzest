"""Static provenance check of a recorded chat decision, not execution authority."""

import json
from hashlib import sha256
from pathlib import Path

from authzest.codex.contracts import identity
from authzest.codex.owner_policy_review import OWNER_POLICY_MAIN_SOURCE, OWNER_POLICY_SOURCE

DIRECTORY = Path(__file__).parent / "fixtures/owner_case_review"


def test_label_record_is_bound_to_preserved_exact_model_envelope():
    original = json.loads((DIRECTORY / "proposed_review.json").read_text(encoding="utf-8"))
    record = json.loads((DIRECTORY / "maintainer_review.json").read_text(encoding="utf-8"))
    assert (
        record["proposed_review_canonical_sha256"]
        == identity(original)
        == ("7d6296c07ec57b57b217a6fc03bd6fa48304cfe475c1adaf9dbd1d9b285ea598")
    )
    assert record["origin_request_id"] == original["origin"]["request_id"]
    assert record["source_identity"] == original["origin"]["source_identity"]
    assert (
        record["source_sha256"]
        == original["source_sha256"]
        == {
            "main.py": sha256(OWNER_POLICY_MAIN_SOURCE.encode()).hexdigest(),
            "policy.py": sha256(OWNER_POLICY_SOURCE.encode()).hexdigest(),
        }
    )
    assert record["decisions"] == [
        {"case_id": case["id"], "decision": "approved", "expected": case["expected"]}
        for case in original["cases"]
    ]
    assert len(record["decisions"]) == 10
    assert {row["case_id"] for row in record["decisions"] if row["expected"]} == {
        "owner-read",
        "exact-padded-owner",
    }
    assert original["label_review_status"] == "pending-maintainer-review"
    assert record["label_review_status"] == "approved"
    assert record["case_authorship"] == original["case_authorship"] == "model-authored"
    assert record["review_date"] == "2026-10-09" and record["timezone"] == "Asia/Seoul"
    assert record["reviewer_authenticated"] is False
    assert record["execution_status"] == record["patch_application"] == "not-run"
    assert record["authorization_status"] == "unknown" and record["provider_calls"] == 0


def test_observation_record_preserves_exact_cases_without_granting_reexecution():
    original = json.loads((DIRECTORY / "proposed_review.json").read_text(encoding="utf-8"))
    record = json.loads((DIRECTORY / "observed_check.json").read_text(encoding="utf-8"))
    prepared, result = record["prepared"], record["result"]
    assert prepared["review_set_sha256"] == identity(original)
    assert prepared["case_ids"] == [case["id"] for case in original["cases"]]
    assert result["cases"] == [
        {
            "id": case["id"],
            "case_sha256": identity(case),
            "expected": case["expected"],
            "observed": case["expected"],
            "result": "passed",
        }
        for case in original["cases"]
    ]
    for field in ("check_plan_id", "policy_source_sha256", "worker_sha256", "input_sha256"):
        observed = (
            result["source_sha256"]["policy.py"]
            if field == "policy_source_sha256"
            else result[field]
        )
        assert prepared[field] == observed
    assert result["status"] == "passed" and result["exit_code"] == 0
    assert result["cleanup_status"] == "confirmed" and result["execution_status"] == "completed"
    assert result["authorization_status"] == "unknown" and result["provider_calls"] == 0
    assert result["patch_application"] == "not-run"
    assert record["approved_attempts"] == record["observed_attempts"] == 1
    assert prepared["execution_status"] == "not-run"  # Preparation never grants authority.
    # Historical coordinator bytes at 5297934, not the current implementation.
    # Later orchestration changes must not rewrite a consumed observation as new evidence.
    old_coordinator = "756862d69fef3fc6def6e0c7ef0bfc68059e0a858dd07aa344aa0d0ea91d922e"
    old_worker = "c8f6c53ddb68f3c7900ecae9914c39e9fb5b9c298a827b074551cf9afe8f408f"
    assert record["source_files_sha256"] == {
        "src/authzest/runner/owner_policy_check.py": old_coordinator,
        "src/authzest/runner/_owner_policy_worker.py": old_worker,
    }
    assert prepared["recipe"]["version"] == "1.0"


def test_recipe_1_1_record_is_a_separate_consumed_observation_of_the_same_exact_cases():
    original = json.loads((DIRECTORY / "proposed_review.json").read_text(encoding="utf-8"))
    labels = json.loads((DIRECTORY / "maintainer_review.json").read_text(encoding="utf-8"))
    old = json.loads((DIRECTORY / "observed_check.json").read_text(encoding="utf-8"))
    record = json.loads((DIRECTORY / "observed_check_recipe_1_1.json").read_text(encoding="utf-8"))
    prepared, result = record["prepared"], record["result"]
    assert record["schema_version"] == "1.0"
    assert record["kind"] == "recorded-owned-policy-source-observation"
    assert record["tested_commit"] == "e03798645c2678477ac141724396beaa013286d9"
    coordinator_sha256 = "eb25f29df157b17057cab51d63855507237b896a17d84709d4282c02df2d059f"
    worker_sha256 = "c8f6c53ddb68f3c7900ecae9914c39e9fb5b9c298a827b074551cf9afe8f408f"
    assert record["source_files_sha256"] == {
        "src/authzest/runner/owner_policy_check.py": coordinator_sha256,
        "src/authzest/runner/_owner_policy_worker.py": worker_sha256,
    }
    assert prepared["recipe"] == {**old["prepared"]["recipe"], "version": "1.1"}
    assert old["prepared"]["recipe"]["version"] == "1.0"
    assert (
        prepared["check_plan_id"]
        == result["check_plan_id"]
        == ("owner-policy-check-a327b9dba5799d957e165e9c83ba1e66eb983a7da18c0130506c2f9b709db0c7")
    )
    assert prepared["check_plan_id"] != old["prepared"]["check_plan_id"]
    assert (
        prepared["review_set_sha256"] == old["prepared"]["review_set_sha256"] == identity(original)
    )
    assert (
        prepared["case_ids"]
        == old["prepared"]["case_ids"]
        == [case["id"] for case in original["cases"]]
    )
    assert (
        result["cases"]
        == old["result"]["cases"]
        == [
            {
                "id": case["id"],
                "case_sha256": identity(case),
                "expected": case["expected"],
                "observed": case["expected"],
                "result": "passed",
            }
            for case in original["cases"]
        ]
    )
    assert [(case["id"], case["expected"]) for case in result["cases"]] == [
        (choice["case_id"], choice["expected"]) for choice in labels["decisions"]
    ]
    assert all(
        type(case["expected"]) is bool and type(case["observed"]) is bool
        for case in result["cases"]
    )
    input_cases = [
        {
            "id": case["id"],
            "case_sha256": identity(case),
            "principal": case["principal"],
            "report": case["report"],
        }
        for case in original["cases"]
    ]
    assert (
        prepared["input_sha256"]
        == result["input_sha256"]
        == old["result"]["input_sha256"]
        == (identity(input_cases))
    )
    assert (
        prepared["worker_sha256"]
        == result["worker_sha256"]
        == old["result"]["worker_sha256"]
        == ("7a3ac77d65c7a0fd16ac0dbb2cf64bcff0843737027c6ce4e805acf3bf236496")
    )
    assert (
        result["source_identity"]
        == old["result"]["source_identity"]
        == (original["origin"]["source_identity"])
    )
    assert result["source_sha256"] == old["result"]["source_sha256"] == original["source_sha256"]
    assert prepared["policy_source_sha256"] == result["source_sha256"]["policy.py"]
    assert result["status"] == "passed" and result["reason"] == "cases-match"
    assert type(result["exit_code"]) is int and result["exit_code"] == 0
    assert result["cleanup_status"] == "confirmed" and result["execution_status"] == "completed"
    assert result["authorization_status"] == "unknown" and result["patch_application"] == "not-run"
    assert type(prepared["provider_calls"]) is int and type(result["provider_calls"]) is int
    assert prepared["provider_calls"] == result["provider_calls"] == 0
    assert prepared["answer_envelope"] == "scripted control-plane data; no new AI response"
    assert prepared["execution_status"] == "not-run"
    assert type(record["approved_attempts"]) is int and type(record["observed_attempts"]) is int
    assert record["approved_attempts"] == record["observed_attempts"] == 1
    assert "not an authenticated receipt" in record["execution_approval"]
    assert (
        "This consumed one fixed-check approval; it does not authorize another run, another plan, "
        "source sharing, new AI proposals, patches or release."
    ) in record["limitations"]
