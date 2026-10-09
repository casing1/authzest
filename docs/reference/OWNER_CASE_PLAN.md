<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_CASE_PLAN.md">한국어</a>
</p>

# Offline owner-case review and fixed-plan contract

[Documentation index](../README.md) · [Owner review](../guides/CODEX_OWNER_REVIEW.md) ·
[Development plan](../development/DEVELOPMENT_PLAN.md)

## Scope and availability

[#77](https://github.com/casing1/authzest/issues/77) adds a pure Python data API in unreleased source,
schema `1.0`, under `authzest.codex.owner_case_plan`. There is no new CLI command or executor. The
published alpha.3 assets, package version `0.1.0a3`, scan schema `1.2`, provider and fixture allowlists
are unchanged. On 2026-10-09 KST the maintainer explicitly approved the exact ten recorded
expectations: `owner-read` and `exact-padded-owner` allow; the other eight deny. The separate
[review record](../../tests/fixtures/owner_case_review/maintainer_review.json) preserves that
labels-only chat decision without changing model authorship or claiming authenticated approval.
Implementation/testing does not itself approve labels, run cases or call a model.

Only the existing packaged owner-policy request/draft is accepted. The APIs operate on supplied
in-memory artifacts; they do not read paths, accounts or credentials, import/evaluate the policy,
start a process, connect to a network or change files. The FastAPI example is not imported or served.
Model reasons and reviewer comments remain untrusted display data, never Python/shell instructions.

## Case set and provenance

`prepare_owner_case_set(draft, request, origin=None)` revalidates the request and owner-policy result
using the existing contracts. `OwnerCaseSet` preserves every exact case input, model-proposed boolean,
reason, evidence reference and model authorship, with request/draft/source identities, both source
hashes, policy evidence, model identity and prompt/output-schema digests. The 1–16 case and shared
256 KiB UTF-8 / depth-32 / 8,192-node budgets also apply to the new complete artifacts.

Optional origin has exactly `code_head` (40 lowercase hexadecimal characters or null) and `date`
(valid ISO date or null). It is caller-declared provenance, always `authenticated: false`, not proof
that a model ran at that commit or that its serving identity was attested. The test fixture
`tests/fixtures/owner_case_review/proposed_review.json` preserves #77's public ten-case envelope and
SHA-256 `7d6296c07ec57b57b217a6fc03bd6fa48304cfe475c1adaf9dbd1d9b285ea598` unchanged. Test answers and
review decisions are explicitly scripted; they are not fresh provider output or user approval.

## Exact-label decisions

`review_owner_cases(case_set, draft, request, decisions=..., reviewer=None)` records choices keyed
by known case IDs. Every supplied choice has exactly `decision`, `expected`, `reason`; missing IDs
remain pending. A nonpending reason must be nonblank bounded text; pending reason is null.

| Decision   | Selected expectation                         | Plan readiness                 |
| ---------- | -------------------------------------------- | ------------------------------ |
| `pending`  | null; original suggestion remains unreviewed | `blocked-pending`              |
| `declined` | null; no selected label                      | `blocked-declined`             |
| `approved` | exact original boolean, without coercion     | reviewed only if all cases are |
| `changed`  | a different boolean, recorded separately     | reviewed only if all cases are |

A changed label does not rewrite the model's input, original expected value, reason or authorship.
The overall status prioritizes declined, pending, changed, then approved. All cases must be approved
or changed for `all_labels_reviewed: true`. The optional reviewer name is caller text and
`reviewer_authenticated` is always false. This is not an authenticated approval receipt or proof
of independent semantic review. The separate 2026-10-09 maintainer record applies only to the
unchanged envelope digest above; it grants no execution, source-sharing or patch permission and
does not approve the separate 28 assistant-authored developer labels or frozen evaluation set.

## Fixed plan, not execution

`prepare_owner_policy_plan(review, case_set, draft, request)` creates an inspectable
`OwnerPolicyPlan`: exact maintained `policy.py` bytes, original cases, separately selected labels,
all artifact identities and a versioned known harness recipe with its content hash. Missing/declined
labels produce a blocked preview; fully caller-reviewed labels produce `reviewed-preview`.

Every plan still has `execution_available: false`, `requires_separate_execution_approval: true`,
`execution_status: not-run`, `authorization_status: unknown`, no patch application and zero provider
calls. A content ID is not permission to share, apply or run anything. Proposed limits (16 cases,
16 scopes, 128-character identifiers, 256 KiB input, 16 KiB output and five seconds) are **design data**,
not enforced process/sandbox guarantees. This offline contract itself starts no harness or worker
and produces no observations; the separate #80 check API has its own bounds and result record.

[#80](https://github.com/casing1/authzest/issues/80) adds a separate source-only
[fixed policy-check API](OWNER_POLICY_CHECK.md), currently in progress. It preserves exact
input-to-dataclass mapping (scope array to frozenset; no identifier normalization) and requires a
fresh independent exact-plan execution decision. The offline plan here remains non-executable.
Only the owned pure policy is in scope; HTTP/auth/database, arbitrary source/commands, generated
test execution, install hooks, networking and model calls are excluded. The labels-only decision
grants no execution; a later separately approved exact #80 source check produced
[ten matching observations](OWNER_POLICY_CHECK.md#actual-source-acceptance--2026-10-09-kst).
Pure-policy results do not prove authentication
or endpoint authorization. A correct policy may need no change.

## Validation and immutable snapshots

The three frozen JSON wrappers return detached dictionaries. Direct construction, caller status and
hashes are not trust boundaries. Use `validate_owner_case_set`, `validate_owner_case_review` and
`validate_owner_policy_plan` on supplied serialized artifacts with their complete current context.
They rebuild expected host metadata and reject duplicate/missing/reordered decisions, unknown fields,
invalid labels/evidence, changed source/model/case data, stale binding and forged statuses/recipes.
Any input, original expectation, reason, evidence or source change invalidates the old label review.
Changing reviewed labels/comments or recipe/limits changes the plan identity and rejects its old preview.
The API cannot prevent deliberate re-recording of caller choices; authentication, decision consumption,
expiry and execution consent must not be inferred from this data contract.

## Python API and offline checks

Given an existing validated `draft` and its exact packaged `request`, this example makes only pending
records. It is not an approval example and does not obtain a draft from a live account:

```python
from authzest.codex.owner_case_plan import (
    prepare_owner_case_set,
    prepare_owner_policy_plan,
    review_owner_cases,
    validate_owner_policy_plan,
)

case_set = prepare_owner_case_set(draft, request)
labels = review_owner_cases(case_set, draft, request, decisions={})
plan = prepare_owner_policy_plan(labels, case_set, draft, request)
assert plan.to_dict()["planning_status"] == "blocked-pending"
assert plan.to_dict()["execution_available"] is False
validate_owner_policy_plan(plan.payload_json, labels, case_set, draft, request)
```

```bash
python -m pytest tests/test_owner_case_plan.py
```

Tests block filesystem/provider/process/network and target imports during contract operations.
They retain the exact public envelope and cover stale/invalid/forged inputs and all label states.
They are offline contract evidence, not real label approval, runtime results, model-quality scores,
consumer installation or release acceptance.
