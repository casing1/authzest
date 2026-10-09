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
