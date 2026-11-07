"""Validate offline host receipt routing, never capture or authenticate a provider.

Fresh namespaces distinguish local batches, not actual model execution. A caller
can rewrap old inner JSON in current metadata. This pure batch check deliberately
does not claim provider freshness, persistent one-use enforcement or live scoring.
The CLI exercises synthetic receipts only; it accepts no receipt/log file paths.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts import evaluation_response as response
from scripts import evaluation_trial_plan as planner

ROOT = Path(__file__).resolve().parents[1]
MAX_RECEIPT_BYTES = 256 * 1024
MAX_BATCH_BYTES = 4 * 1024 * 1024
OUTCOMES = ("valid", "missing", "invalid", "failed", "interrupted", "timeout")
FAULTS = (
    "missing",
    "invalid",
    "duplicate",
    "stale",
    "unmatched",
    "failed",
    "interrupted",
    "timeout",
)
LIMITATIONS = (
    "Host routing only: caller-supplied receipts are unverified, not provider evidence.",
    "Old whole receipts are rejected across namespaces; rewrapped old inner JSON can pass.",
    "No model/configuration/repetition freshness or actual provider execution is proved.",
    "Duplicate detection is within this batch, not persistent one-use enforcement.",
    "A nonce/content ID is neither authentication nor sharing/execution approval.",
    "Session/receipt metadata is NEVER provider input; existing model messages are unchanged.",
    "No transport capture, effective context/model verification, live freeze or scoring.",
    "Public task/reference exposure and answer-only semantic-review limits remain.",
)


class CollectionError(ValueError):
    """Invalid local session/batch specification, not a provider failure."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CollectionError(code)


def _id(value: object, prefix: str) -> bool:
    return (
        type(value) is str and re.fullmatch(re.escape(prefix) + r"[0-9a-f]{64}", value) is not None
    )


@dataclass(frozen=True, slots=True)
class Slot:
    ordinal: int
    repetition: int
    mode: str
    trial_id: str
    message_sha256: str
    spec: response.ResponseSpec

    def __post_init__(self) -> None:
        _require(type(self.ordinal) is int and 1 <= self.ordinal <= 42, "invalid-slot-ordinal")
        _require(type(self.repetition) is int and 1 <= self.repetition <= 3, "invalid-slot-repeat")
        _require(type(self.mode) is str and self.mode in planner.AI_MODES, "invalid-slot-mode")
        _require(_id(self.trial_id, "trial-"), "invalid-trial-id")
        _require(_id(self.message_sha256, ""), "invalid-message-hash")
        _require(type(self.spec) is response.ResponseSpec, "invalid-response-spec")
        try:
            self.spec.__post_init__()
        except response.ContractError as error:
            raise CollectionError("invalid-response-spec") from error

    def original(self, configuration_id: str) -> dict:
        return {
            "ordinal": self.ordinal,
            "repetition": self.repetition,
            "task_id": self.spec.task_id,
            "mode": self.mode,
            "request_id": self.spec.request_id,
            "message_sha256": self.message_sha256,
            "configuration_id": configuration_id,
        }


@dataclass(frozen=True, slots=True)
class CollectionSession:
    """Factory-owned immutable expected metadata; not an authenticated saved session."""

    plan_id: str
    configuration_id: str
    packet_set_id: str
    configuration: planner.TrialConfig
    namespace_nonce: str
    slots: tuple[Slot, ...]

    def __post_init__(self) -> None:
        for value, prefix in (
            (self.plan_id, "trial-plan-"),
            (self.configuration_id, "trial-config-"),
            (self.packet_set_id, "packet-set-"),
            (self.namespace_nonce, ""),
        ):
            _require(_id(value, prefix), "invalid-session-identity")
        _require(type(self.configuration) is planner.TrialConfig, "invalid-configuration")
        try:
            self.configuration.__post_init__()
        except planner.TrialPlanError as error:
            raise CollectionError("invalid-configuration") from error
        _require(
            self.configuration_id
            == planner._identity(
                "trial-config-",
                {
                    "policy_version": planner.POLICY_VERSION,
                    "values": asdict(self.configuration),
                    "order_policy": planner.ORDER_POLICY,
                    "context_policy": planner.CONTEXT_POLICY,
                    "attempt_policy": planner.ATTEMPT_POLICY,
                    "failure_policy": planner.FAILURE_POLICY,
                },
            ),
            "configuration-binding-mismatch",
        )
        _require(
            type(self.slots) is tuple and len(self.slots) == 14 * self.configuration.repetitions,
            "invalid-slot-count",
        )
        for slot in self.slots:
            _require(type(slot) is Slot, "invalid-slot")
            slot.__post_init__()
            _require(
                slot.trial_id == planner._identity("trial-", slot.original(self.configuration_id)),
                "slot-binding-mismatch",
            )
        _require(
            [slot.ordinal for slot in self.slots] == list(range(1, len(self.slots) + 1)),
            "invalid-slot-order",
        )
        _require(len({slot.trial_id for slot in self.slots}) == len(self.slots), "duplicate-slot")
        tasks = {slot.spec.task_id for slot in self.slots}
        _require(len(tasks) == 7, "invalid-task-count")
        for repeat in range(1, self.configuration.repetitions + 1):
            for mode in planner.AI_MODES:
                group = [
                    slot for slot in self.slots if (slot.repetition, slot.mode) == (repeat, mode)
                ]
                _require(
                    len(group) == 7
                    and {slot.spec.task_id for slot in group} == tasks
                    and sum(len(slot.spec.questions) for slot in group) == 21,
                    "invalid-group-denominator",
                )

    @property
    def collection_id(self) -> str:
        return planner._identity(
            "collection-",
            {
                "plan_id": self.plan_id,
                "configuration_id": self.configuration_id,
                "packet_set_id": self.packet_set_id,
                "nonce": self.namespace_nonce,
            },
        )

    def binding(self, slot: Slot) -> dict:
        return {
            "collection_id": self.collection_id,
            "plan_id": self.plan_id,
            "packet_set_id": self.packet_set_id,
            "trial_id": slot.trial_id,
            **slot.original(self.configuration_id),
            "invocation_id": planner._identity(
                "invocation-",
                {
                    "collection_id": self.collection_id,
                    "trial_id": slot.trial_id,
                },
            ),
        }


def new_collection(root: Path, configuration: planner.TrialConfig) -> CollectionSession:
    """Build expected metadata from the owned planner; no serialized session import."""
    plan = planner.build_trial_plan(root, configuration)
    packets = {(item["task_id"], item["mode"]): item for item in plan["packets"]}
    slots = []
    for item in plan["schedule"]:
        payload = json.loads(packets[item["task_id"], item["mode"]]["message_text"])
        slots.append(
            Slot(
                item["ordinal"],
                item["repetition"],
                item["mode"],
                item["trial_id"],
                item["message_sha256"],
                planner.comparison._spec(payload),
            )
        )
    return CollectionSession(
        plan["plan_id"],
        plan["configuration_id"],
        plan["packet_set_id"],
        configuration,
        secrets.token_hex(32),
        tuple(slots),
    )


def _outcome(outcome: str, error: str | None, records: list | None = None) -> dict:
    return {
        "outcome": outcome,
        "error": error,
        "records": records if outcome == "valid" else None if outcome == "missing" else [],
    }


def decode_receipt(session: CollectionSession, slot: Slot, raw: object) -> dict:
    """Strict local routing plus unchanged inner 0.1 validation, not origin attestation."""
    _require(type(session) is CollectionSession, "invalid-session")
    session.__post_init__()
    _require(type(slot) is Slot, "invalid-slot")
    slot.__post_init__()
    _require(slot in session.slots, "foreign-slot")
    if raw is None:
        return _outcome("missing", "missing-receipt")
    if type(raw) is not str:
        return _outcome("invalid", "invalid-receipt-type")
    if len(raw) > MAX_RECEIPT_BYTES:
        return _outcome("invalid", "receipt-too-large")
    try:
        if len(raw.encode("utf-8")) > MAX_RECEIPT_BYTES:
            return _outcome("invalid", "receipt-too-large")
    except UnicodeError:
        return _outcome("invalid", "invalid-receipt-utf8")
    if not response._depth_bounded(raw):
        return _outcome("invalid", "receipt-depth-limit")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=response._unique,
            parse_constant=response._constant,
            parse_float=response._float,
        )
    except response._DecodeError as error:
        return _outcome("invalid", "receipt-" + str(error))
    except (ValueError, RecursionError):
        return _outcome("invalid", "invalid-receipt-json")
    expected = {"schema_version": "0.1", "kind": "evaluation-host-receipt", **session.binding(slot)}
    if type(value) is not dict or set(value) != {*expected, "status", "response_raw"}:
        return _outcome("invalid", "invalid-receipt-fields")
    if any(
        type(value[key]) is not type(wanted) or value[key] != wanted
        for key, wanted in expected.items()
    ):
        return _outcome("invalid", "receipt-binding-mismatch")
    status = value["status"]
    if type(status) is not str or status not in ("completed", "failed", "interrupted", "timeout"):
        return _outcome("invalid", "invalid-reported-status")
    if status != "completed":
        return (
            _outcome(status, "reported-" + status)
            if value["response_raw"] is None
            else _outcome("invalid", "unexpected-failure-response")
        )
    decoded = response.decode_response(slot.spec, value["response_raw"])
    return _outcome(decoded["status"], decoded["error"], decoded["records"])


def collect_receipts(session: CollectionSession, submissions: list[tuple[str, object]]) -> dict:
    """Validate one finite batch, preserving slots and reporting unattributable input.

    The caller supplies routing keys. Unknown routes never create extra slots or
    get assigned to an arbitrary slot; their unmatched errors remain visible.
    Revalidating this same batch is allowed: this is not a persistent replay ledger.
    """
    _require(type(session) is CollectionSession, "invalid-session")
    session.__post_init__()
    _require(
        type(submissions) is list and len(submissions) <= 2 * len(session.slots),
        "invalid-submission-count",
    )
    total_bytes = 0
    for item in submissions:
        if type(item) is tuple and len(item) == 2 and type(item[1]) is str:
            for offset in range(0, len(item[1]), 4096):
                # Invalid surrogates still consume the budget, then fail per receipt.
                total_bytes += len(item[1][offset : offset + 4096].encode("utf-8", "surrogatepass"))
                _require(total_bytes <= MAX_BATCH_BYTES, "batch-too-large")
    bindings = [session.binding(slot) for slot in session.slots]
    routed = {item["invocation_id"]: [] for item in bindings}
    unmatched = []
    for index, item in enumerate(submissions):
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or item[0] not in routed
        ):
            unmatched.append({"submission_index": index, "error": "unmatched-routing-key"})
        else:
            routed[item[0]].append(item[1])
    observations = []
    for slot, binding in zip(session.slots, bindings, strict=True):
        supplied = routed[binding["invocation_id"]]
        result = (
            _outcome("invalid", "duplicate-receipt")
            if len(supplied) > 1
            else decode_receipt(session, slot, supplied[0] if supplied else None)
        )
        observations.append({**binding, "question_count": len(slot.spec.questions), **result})
    groups = []
    for repeat in range(1, session.configuration.repetitions + 1):
        for mode in planner.AI_MODES:
            items = [
                item
                for item in observations
                if (item["repetition"], item["mode"]) == (repeat, mode)
            ]
            groups.append(
                {
                    "repetition": repeat,
                    "mode": mode,
                    "planned_cases": len(items),
                    "question_opportunities": sum(item["question_count"] for item in items),
                    "cases_by_outcome": {
                        key: sum(item["outcome"] == key for item in items) for key in OUTCOMES
                    },
                    "questions_by_outcome": {
                        key: sum(item["question_count"] for item in items if item["outcome"] == key)
                        for key in OUTCOMES
                    },
                }
            )
    return {
        "schema_version": "0.1",
        "kind": "offline-host-receipt-observation",
        "collection_id": session.collection_id,
        "plan_id": session.plan_id,
        "configuration_id": session.configuration_id,
        "configuration": asdict(session.configuration),
        "batch_status": "routing-errors" if unmatched else "routed",
        "planned_slots": len(session.slots),
        "question_opportunities": sum(len(slot.spec.questions) for slot in session.slots),
        "submission_count": len(submissions),
        "unmatched": unmatched,
        "groups": groups,
        "observations": observations,
        "transport_provenance": "caller-supplied-unverified",
        "provider_freshness_verified": False,
        "duplicate_scope": "one-batch-only-no-persistent-one-use-enforcement",
        "model_availability": "unverified",
        "effective_model_observed": None,
        "provider_usage": None,
        "provider_latency_seconds": None,
        "provider_calls_by_this_tool": 0,
        "live_trials": 0,
        "target_execution": "not-run",
        "scoring_status": "not-run",
        "model_quality_measured": False,
        "sharing_authorized": False,
        "execution_authorized": False,
        "live_configuration_frozen": False,
        "live_benchmark_ready": False,
        "limitations": list(LIMITATIONS),
    }


def _synthetic_receipt(session: CollectionSession, slot: Slot, *, status: str = "completed") -> str:
    raw = (
        json.dumps(
            {
                "schema_version": "0.1",
                "kind": "evaluation-comparison-response",
                "task_id": slot.spec.task_id,
                "request_id": slot.spec.request_id,
                "answers": [
                    {"question_id": question.id, "answer": None} for question in slot.spec.questions
                ],
            }
        )
        if status == "completed"
        else None
    )
    return json.dumps(
        {
            "schema_version": "0.1",
            "kind": "evaluation-host-receipt",
            **session.binding(slot),
            "status": status,
            "response_raw": raw,
        }
    )


def dry_run(root: Path, configuration: planner.TrialConfig, *, fault: str | None = None) -> dict:
    _require(fault is None or fault in FAULTS, "invalid-synthetic-fault")
    session = new_collection(root, configuration)
    submissions = [
        (session.binding(slot)["invocation_id"], _synthetic_receipt(session, slot))
        for slot in session.slots
    ]
    key, raw = submissions[0]
    if fault == "missing":
        submissions.pop(0)
    elif fault == "duplicate":
        submissions.append(submissions[0])
    elif fault == "unmatched":
        submissions[0] = ("invocation-" + "0" * 64, raw)
    elif fault in ("invalid", "stale"):
        value = json.loads(raw)
        value["response_raw" if fault == "invalid" else "collection_id"] = "synthetic-fault"
        submissions[0] = (key, json.dumps(value))
    elif fault is not None:
        submissions[0] = (key, _synthetic_receipt(session, session.slots[0], status=fault))
    return {
        **collect_receipts(session, submissions),
        "response_origin": "synthetic-null-receipts-with-optional-fault",
        "fault": fault,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", required=True, help="synthetic receipts only"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--repetitions", required=True, type=int)
    parser.add_argument("--timeout-seconds", required=True, type=int)
    parser.add_argument("--fault", choices=FAULTS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = dry_run(
            ROOT,
            planner.TrialConfig(args.model, args.effort, args.repetitions, args.timeout_seconds),
            fault=args.fault,
        )
    except (
        CollectionError,
        planner.TrialPlanError,
        planner.comparison.reference.ReferenceError,
    ) as error:
        print(
            json.dumps(
                {
                    "kind": "offline-collection-error",
                    "error": str(error),
                    "execution_authorized": False,
                    "provider_calls_by_this_tool": 0,
                }
            )
        )
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print("SYNTHETIC HOST RECEIPTS ONLY. No provider capture, execution, scoring or live freeze.")
    print(f"Collection: {result['collection_id']}")
    print(
        f"Retained: {result['planned_slots']} slots / "
        f"{result['question_opportunities']} question opportunities."
    )
    for group in result["groups"]:
        print(
            f"  repetition {group['repetition']} / {group['mode']}: {group['cases_by_outcome']} "
            f"(cases {group['planned_cases']}, questions {group['question_opportunities']})"
        )
    print(
        f"Unmatched routing errors: {len(result['unmatched'])}. "
        "Schema-valid is NOT model correctness."
    )
    for limitation in result["limitations"]:
        print(f"  - {limitation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
