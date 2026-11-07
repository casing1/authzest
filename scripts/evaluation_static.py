"""Registered source-only static observations, not a general question interpreter.

Recipes translate the exact public tasks into declaration queries, never answers.
Generate every response before loading evaluator references. Policy intent and
runtime assurance are deliberately outside this declaration adapter's scope.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import evaluation_comparison as comparison
from scripts.evaluation_static_query import Query, QueryError, evaluate_query

ADAPTER_VERSION = "registered-source-query-v1"
# Public task-only identities: no expected answer, reference hash or review metadata.
# Changing source/policy/questions requires a newly reviewed query mapping, not an
# automatic recipe retarget based on an unchanged human-readable case name.
QUERIES = {
    "task-4d403203d78838c1092c2a5c5d65a73e74974b989b242e1a78e3935b0a5c9bd4": (
        "post-direct-security-scopes",
        Query("direct-security-scopes", method="POST", path="/parcels"),
    ),
    "task-a6d2d58493b207cc1203135e36ad3c530add29f4d09e51601cc5cd87dc47e2c9": (
        "composed-dependency-count",
        Query("composed-dependency-count"),
    ),
    "task-bded79d1ddcd53fe7e9520177790fa8143b00837f7ea577f83b10c3b831d7902": (
        "source-http-declaration-count",
        Query("source-http-declaration-count"),
    ),
    "task-bd9ede5cc100d1a0b31046253144de4229dfebecf0833fb480f10ef435981965": (
        "source-http-declaration-count",
        Query("source-http-declaration-count"),
    ),
    "task-a9327ec62ab65748e94f13d414822fc70ffd08f9c6303d56377d4dcb9e2ab43f": (
        "direct-route-security-scopes",
        Query("direct-security-scopes", method="GET", path="/ledger"),
    ),
    "task-002ce9a603a540578b262ce668e37f82fcbd3e8a76990e511d1ea8fd6ce5c04b": (
        "source-http-declaration-count",
        Query("source-http-declaration-count"),
    ),
    "task-21f865583e6b02794652768ce1ce05dffd825be6c00ade055d312f47f107ffc2": (
        "source-http-declaration-count",
        Query("source-http-declaration-count"),
    ),
}


def stage_static(root: Path) -> dict:
    """Stage source-derived answers and uncertainty without opening reference data."""
    plan = comparison.build_plan(root)
    records = {}
    observations = []
    for task in plan["tasks"]:
        payload = task["packets"]["static-only"]["payload"]
        public = {key: payload[key] for key in ("sources", "policies", "questions")}
        bound_payload = {key: value for key, value in payload.items() if key != "request_id"}
        identity_matches = (
            comparison._identity("task-", public) == task["task_id"] == payload["task_id"]
            and comparison._identity("request-", {"mode": "static-only", "payload": bound_payload})
            == payload["request_id"]
            == task["packets"]["static-only"]["request_id"]
        )
        recipe = QUERIES.get(task["task_id"]) if identity_matches else None
        answers, questions = [], []
        query_invalid = False
        for question in payload["questions"]:
            result = {"answer": None, "reason": "unregistered-query", "evidence": []}
            if question["family"] == "policy-intent":
                result["reason"] = "policy-intent-not-inferred"
            elif question["family"] == "runtime-assurance":
                result["reason"] = "runtime-assurance-not-established"
            elif recipe is not None and question["id"] == recipe[0]:
                try:
                    result = evaluate_query(payload["sources"], recipe[1])
                except QueryError:
                    # Invalid evaluator inputs are failed cases, not valid abstentions.
                    query_invalid = True
                    result["reason"] = "query-input-invalid"
            answers.append({"question_id": question["id"], "answer": result["answer"]})
            questions.append({"question_id": question["id"], **result})
        raw = json.dumps(
            {
                "schema_version": "0.1",
                "kind": "evaluation-comparison-response",
                "task_id": payload["task_id"],
                "request_id": payload["request_id"],
                "answers": answers,
            }
        )
        decoded = comparison.decode_response(comparison._spec(payload), raw)
        invalid = not identity_matches or query_invalid or decoded["status"] != "valid"
        records[task["case_id"]] = [] if invalid else decoded["records"]
        observations.append(
            {
                "case_id": task["case_id"],
                "task_id": task["task_id"],
                "request_id": payload["request_id"],
                "status": "invalid" if invalid else "valid",
                "error": (
                    "input-identity-mismatch"
                    if not identity_matches
                    else "query-input-invalid"
                    if query_invalid
                    else decoded["error"]
                ),
                "questions": questions,
            }
        )
    return {"plan": plan, "records": records, "observations": observations}


def static_observation(root: Path) -> dict:
    """Record one deterministic owned-source baseline, not model/runtime correctness."""
    staged = stage_static(root)
    result = comparison.reference.score_reference(root, staged["records"])
    return {
        **{key: value for key, value in staged["plan"].items() if key not in ("tasks", "modes")},
        "kind": "registered-static-source-observation",
        "mode": "static-only",
        "response_origin": "deterministic-registered-source-query",
        "static_answer_adapter": ADAPTER_VERSION,
        "static_baseline_measured": True,
        "baseline_scope": "fixed-seven-owned-source-tasks",
        "query_registry_authorship": "assistant",
        "evaluation_independence": "not-established-public-developed-tasks",
        "model_quality_measured": False,
        "citation_support_measured": False,
        "live_trials": 0,
        "reference": {
            "version": result["version"],
            "candidate_sha256": result["candidate_sha256"],
            "manifest_sha256": result["manifest_sha256"],
            "independent_review_attested": result["decision"]["independent_review_attested"],
        },
        "observations": staged["observations"],
        "calculation": result["calculation"],
    }
