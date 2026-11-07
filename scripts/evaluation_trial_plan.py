"""Prepare an offline comparison candidate, never start a model or collect answers.

Only fixed public task data is read. Application message candidates are not actual
Codex wire requests or the effective harness context. IDs bind content, not consent,
account/model availability, response freshness, independent review or live freeze.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts import evaluation_comparison as comparison
from scripts.evaluation_response import ContractError

ROOT = Path(__file__).resolve().parents[1]
AI_MODES = ("model-only", "evidence-assisted")
POLICY_VERSION = "offline-trial-candidate-v1"
ORDER_POLICY = "sorted-task-id-alternating-case-and-repetition-first-mode"
CONTEXT_POLICY = "fresh-context-per-slot-required-not-implemented"
ATTEMPT_POLICY = "one-attempt-per-slot-no-authzest-retry-or-model-fallback"
FAILURE_POLICY = "retain-every-planned-slot-no-replacement-required-not-implemented"
MAX_MESSAGE_BYTES = 128 * 1024
PAYLOAD_FIELDS = {
    "schema_version",
    "kind",
    "task_id",
    "request_id",
    "instructions",
    "answer_contract",
    "sources",
    "policies",
    "questions",
    "evidence",
}
REFERENCE_FIELDS = {
    "expected",
    "rationale",
    "source_refs",
    "proposed_split",
    "authorship",
    "decision",
    "review_status",
    "reference_sha256",
    "candidate_sha256",
    "case_id",
}
LIMITATIONS = (
    "The whole plan is evaluator metadata, NEVER provider input.",
    "Candidate only: no sharing/execution approval or live configuration freeze.",
    "Model/effort labels are syntax-checked only; account availability is unverified.",
    "Application messages are not wire envelopes or the effective Codex harness context.",
    "Fresh isolated contexts and tool restrictions are future requirements, not enforced here.",
    "Response schema 0.1 does not bind model/configuration/repetition or fresh invocations.",
    "Trial IDs are deterministic metadata, not consent tokens or response-freshness proof.",
    "Odd repetition counts leave one more pair starting with one mode; order is not random.",
    "Timeout sums are nominal adapter budgets, not hard wall-clock, token or credit caps.",
    "Codex internal retries/usage and cleanup time have no bound established by this planner.",
    "Public assistant-authored tasks are not independently reviewed blind/unseen holdouts.",
    "Answer-only schema cannot measure citation support, explanations or human review effort.",
    "The contract digest binds its public descriptor, not validator implementation bytes.",
)


class TrialPlanError(ValueError):
    """A closed diagnostic for an invalid offline candidate or packet binding."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TrialPlanError(code)


@dataclass(frozen=True, slots=True)
class TrialConfig:
    """Explicit proposed values; constructing this object authorizes nothing."""

    model: str
    effort: str
    repetitions: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        _require(
            type(self.model) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", self.model) is not None,
            "invalid-model-label",
        )
        _require(
            type(self.effort) is str
            and re.fullmatch(r"[a-z][a-z0-9-]{0,19}", self.effort) is not None,
            "invalid-effort-label",
        )
        _require(
            type(self.repetitions) is int and 1 <= self.repetitions <= 3,
            "invalid-repetitions",
        )
        _require(
            type(self.timeout_seconds) is int and 1 <= self.timeout_seconds <= 120,
            "invalid-timeout",
        )


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError, RecursionError) as error:
        raise TrialPlanError("invalid-packet-json") from error


def _digest(text: str) -> str:
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeError as error:
        raise TrialPlanError("invalid-packet-utf8") from error


def _identity(prefix: str, value: object) -> str:
    return prefix + _digest(_canonical(value))


def _exclude_references(value: object) -> None:
    if type(value) is dict:
        _require(not set(value) & REFERENCE_FIELDS, "evaluator-metadata-in-message")
        for child in value.values():
            _exclude_references(child)
    elif type(value) is list:
        for child in value:
            _exclude_references(child)


def _packets(plan: dict) -> tuple[list[dict], str, str, int]:
    """Check paired content/bindings before displaying any message candidate."""
    tasks = plan["tasks"]
    _require(len(tasks) == 7, "unexpected-task-count")
    _require(len({task["task_id"] for task in tasks}) == len(tasks), "duplicate-task-id")
    packets = []
    shared = None
    question_count = 0
    for task in sorted(tasks, key=lambda item: item["task_id"]):
        paired = []
        for mode in AI_MODES:
            wrapper = task["packets"][mode]
            payload = copy.deepcopy(wrapper["payload"])
            _require(type(payload) is dict and set(payload) == PAYLOAD_FIELDS, "packet-fields")
            _exclude_references(payload)
            _require(
                payload["schema_version"] == "0.1"
                and payload["kind"] == "evaluation-comparison-input",
                "packet-schema",
            )
            public = {key: payload[key] for key in ("sources", "policies", "questions")}
            _require(
                _identity("task-", public) == task["task_id"] == payload["task_id"],
                "task-binding-mismatch",
            )
            bound = {key: value for key, value in payload.items() if key != "request_id"}
            _require(
                _identity("request-", {"mode": mode, "payload": bound})
                == payload["request_id"]
                == wrapper["request_id"],
                "request-binding-mismatch",
            )
            try:
                comparison._spec(payload)
            except (ContractError, KeyError, TypeError) as error:
                raise TrialPlanError("invalid-response-specification") from error
            _require(type(payload["instructions"]) is str, "invalid-instructions")
            common = (payload["instructions"], payload["answer_contract"])
            if shared is None:
                shared = common
            _require(common == shared, "inconsistent-common-contract")
            _require(
                payload["evidence"] == []
                if mode == "model-only"
                else type(payload["evidence"]) is list and len(payload["evidence"]) == 1,
                "invalid-mode-evidence",
            )
            message = _canonical(payload)
            digest = _digest(message)
            size = len(message.encode("utf-8"))
            _require(size <= MAX_MESSAGE_BYTES, "message-too-large")
            packets.append(
                {
                    "task_id": task["task_id"],
                    "mode": mode,
                    "request_id": payload["request_id"],
                    "message_sha256": digest,
                    "message_bytes": size,
                    "message_text": message,
                }
            )
            paired.append(
                {
                    key: value
                    for key, value in payload.items()
                    if key not in ("evidence", "request_id")
                }
            )
        _require(paired[0] == paired[1], "unpaired-common-content")
        question_count += len(paired[0]["questions"])
    _require(question_count == 21, "unexpected-question-count")
    return packets, _digest(shared[0]), _identity("contract-", shared[1]), question_count


def build_trial_plan(root: Path, config: TrialConfig) -> dict:
    """Build a deterministic candidate from task-only messages, without reference reads."""
    _require(type(config) is TrialConfig, "invalid-configuration")
    config.__post_init__()
    try:
        packets, prompt_hash, contract_id, question_count = _packets(comparison.build_plan(root))
    except (KeyError, TypeError, AttributeError, RecursionError) as error:
        raise TrialPlanError("invalid-packet-structure") from error
    config_id = _identity(
        "trial-config-",
        {
            "policy_version": POLICY_VERSION,
            "values": asdict(config),
            "order_policy": ORDER_POLICY,
            "context_policy": CONTEXT_POLICY,
            "attempt_policy": ATTEMPT_POLICY,
            "failure_policy": FAILURE_POLICY,
        },
    )
    packet_set_id = _identity("packet-set-", packets)
    task_ids = sorted({packet["task_id"] for packet in packets})
    by_pair = {(packet["task_id"], packet["mode"]): packet for packet in packets}
    schedule = []
    for repeat in range(config.repetitions):
        for index, task_id in enumerate(task_ids):
            order = AI_MODES if (index + repeat) % 2 == 0 else AI_MODES[::-1]
            for mode in order:
                packet = by_pair[task_id, mode]
                slot = {
                    "ordinal": len(schedule) + 1,
                    "repetition": repeat + 1,
                    "task_id": task_id,
                    "mode": mode,
                    "request_id": packet["request_id"],
                    "message_sha256": packet["message_sha256"],
                    "configuration_id": config_id,
                }
                schedule.append({"trial_id": _identity("trial-", slot), **slot})
    core = {
        "schema_version": "0.1",
        "kind": "offline-evaluation-trial-plan",
        "policy_version": POLICY_VERSION,
        "status": "candidate-not-live-frozen",
        "configuration": asdict(config),
        "configuration_id": config_id,
        "model_availability": "unverified",
        "effort_support": "unverified",
        "common_prompt_sha256": prompt_hash,
        "answer_contract_descriptor_id": contract_id,
        "packet_set_id": packet_set_id,
        "case_count": len(task_ids),
        "questions_per_mode_repetition": question_count,
        "modes": list(AI_MODES),
        "order_policy": ORDER_POLICY,
        "context_policy": CONTEXT_POLICY,
        "attempt_policy": ATTEMPT_POLICY,
        "failure_policy": FAILURE_POLICY,
        "static_baseline": "separate-deterministic-observation-not-a-provider-trial",
        "budget": {
            "planned_authzest_attempts": len(schedule),
            "planned_question_opportunities": question_count * 2 * config.repetitions,
            "nominal_adapter_timeout_sum_seconds": len(schedule) * config.timeout_seconds,
            "wall_clock_hard_cap_seconds": None,
            "token_or_credit_hard_cap": None,
            "codex_internal_retry_bound": None,
        },
        "provider_calls_by_this_tool": 0,
        "live_trials": 0,
        "responses_collected": 0,
        "target_execution": "not-run",
        "scoring_status": "not-run",
        "sharing_authorized": False,
        "execution_authorized": False,
        "live_configuration_frozen": False,
        "live_benchmark_ready": False,
        "model_quality_measured": False,
        "citation_support_measured": False,
        "repeat_variation_measured": False,
        "evaluation_independence": "not-established-public-developed-tasks",
        "transport_status": "not-implemented",
        "wire_or_effective_context_verified": False,
        "limitations": list(LIMITATIONS),
        "packets": packets,
        "schedule": schedule,
    }
    return {"plan_id": _identity("trial-plan-", core), **core}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", required=True, help="proposed model label; no availability lookup"
    )
    parser.add_argument("--effort", required=True, help="proposed effort label; no support lookup")
    parser.add_argument("--repetitions", required=True, type=int, help="proposed repeats, 1..3")
    parser.add_argument(
        "--timeout-seconds", required=True, type=int, help="proposed adapter limit, 1..120"
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="emit one complete candidate plan")
    output.add_argument(
        "--show-messages", action="store_true", help="also print all application messages"
    )
    args = parser.parse_args(argv)
    try:
        result = build_trial_plan(
            ROOT, TrialConfig(args.model, args.effort, args.repetitions, args.timeout_seconds)
        )
    except (TrialPlanError, comparison.reference.ReferenceError) as error:
        failure = {
            "kind": "offline-evaluation-trial-plan-error",
            "error": str(error),
            "execution_authorized": False,
            "provider_calls_by_this_tool": 0,
        }
        print(json.dumps(failure) if args.json else str(error))
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print("OFFLINE CANDIDATE ONLY. No account lookup, model call, approval or live freeze.")
    print(f"Plan: {result['plan_id']}")
    print(f"Model/effort (UNVERIFIED): {args.model} / {args.effort}")
    print(f"7 cases / 21 questions per AI mode / {args.repetitions} repetition(s).")
    budget = result["budget"]
    print(
        f"Planned attempts: {budget['planned_authzest_attempts']}; nominal adapter timeout sum: "
        f"{budget['nominal_adapter_timeout_sum_seconds']}s (NOT a wall-clock/usage cap)."
    )
    for limitation in result["limitations"]:
        print(f"  - {limitation}")
    print("The whole plan is evaluator metadata, NEVER provider input.")
    print("Use --show-messages for all application message candidates; --json for the full plan.")
    if args.show_messages:
        for packet in result["packets"]:
            print(f"\nAPPLICATION MESSAGE CANDIDATE: {packet['mode']} / {packet['task_id']}")
            print(f"SHA-256: {packet['message_sha256']}; UTF-8 bytes: {packet['message_bytes']}")
            print(packet["message_text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
