<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_RECOMMENDATION.md">한국어</a>
</p>

# Offline owner-policy recommendation API

[Documentation index](../README.md) · [Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Original S1 design](../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81)

## Availability and boundary — 2026-10-16 KST

This branch implements S1's source-only pure Python data API in
`authzest.codex.owner_policy_recommendation`: a fixed request, strict recommendation validation
and an inspectable preview. It is not published in alpha.3, a new CLI command, provider adapter,
AI-generated patch or complete #81 workflow. Final implementation CI/reviews and wider #81/#82
acceptance remain separate gates.

The unchanged [design](../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md) is the historical
2026-10-15 proposal. At this implementation checkpoint, [PR #98](https://github.com/casing1/authzest/pull/98)
at `a170d82` remains draft and unmerged. The bounded S1 continuation does not imply approval of
all #81 extensions, merge that design PR, or authorize a model call, policy execution or patch.
The separate [S1 scope decision](https://github.com/casing1/authzest/issues/81#issuecomment-6206079101)
records the 2026-10-16 continuation; it is not approval authority carried by these data objects.

The API uses registered in-memory constants only. It accepts no path, arbitrary source, repository,
model choice, callback, case set, label record or observation record. It performs no filesystem,
network, provider or process access, policy evaluation/import, application or restoration.
`policy.py` is a logical data label, not a file to open. Existing owner-review/proposal contracts,
the #80 worker/allowlist, scan behavior and historical model/label/observation records are unchanged.

## Python entry points

| Entry point                                                            | Result                                                                                              |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `build_owner_policy_recommendation_request()`                          | Build the registered `OwnerPolicyRecommendationRequest`; no caller-selected source or configuration |
| `validate_owner_policy_recommendation_request(raw)`                    | Rebuild and validate the exact current request                                                      |
| `validate_owner_policy_recommendation(raw, request)`                   | Validate an exact-bound `OwnerPolicyRecommendation`                                                 |
| `prepare_owner_policy_recommendation_preview(recommendation, request)` | Revalidate both artifacts and build an `OwnerPolicyRecommendationPreview`                           |

The request exposes `request_id`; the validated recommendation exposes `recommendation_id`.
All three wrappers provide `to_dict()` with detached data. A directly constructed dataclass,
copied ID, status or typed wrapper is not validation or approval authority. Revalidate supplied
artifacts against the complete current registered context; changed or forged contents are rejected.
The validators' `raw` argument is serialized JSON text, not a dictionary, path or executable input.

## Request and raw recommendation

Request schema `1.0` is independent of report schema `1.2` and package version `0.1.0a3`.
It contains exactly `schema_version`, `kind`, `scenario_id`, `source`, `criteria`, `assumptions`
and `registry`. The registered `OWNER_POLICY_SOURCE` bytes retain their line endings; the new
policy-only criteria snapshot has no trailing LF. Fixed ordered trusted-input assumptions and
registry version `empty-v1` with no pairs are host-owned, not caller overrides.

Source/criteria evidence IDs and request/recommendation IDs bind exact canonical content using
the prefixes and hash inputs in the [design](../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md).
The request ID is a derived property, not a self-referential request field. Byte/version changes
invalidate old bindings. Hashes identify content; they attest neither identity nor consent.

The raw recommendation has exactly these fields:

| Field              | Rule                                                                      |
| ------------------ | ------------------------------------------------------------------------- |
| `schema_version`   | Exactly `1.0`                                                             |
| `request_id`       | Exact current request ID                                                  |
| `status`           | Exactly `no-change` or `unknown`                                          |
| `rationale`        | Bounded nonblank text                                                     |
| `evidence_ids`     | Both distinct registered source/criteria IDs; no unknown or duplicate IDs |
| `assumptions`      | Bounded nonblank text items; at least one                                 |
| `uncertainties`    | Bounded nonblank text items; at least one for `unknown`                   |
| `expected_effects` | Bounded nonblank text items; at least one                                 |
| `limitations`      | Bounded nonblank text items; at least one for either status               |
| `change_pair_id`   | Exactly JSON null                                                         |

`no-change` means no source change is supported within this input scope, not that the policy is
secure. `unknown` records missing support for a recommendation, not a fabricated denial or
observed failure. Shape/reference validation does not establish semantic correctness, trusted
authentication or endpoint enforcement. Text that resembles instructions or code remains data.

Additional fields are rejected even when empty: cases, labels, observations, replacement source,
diffs/patches/commands/executable tests, provider/model identity claims, approval choices and
execution/application statuses are outside the raw contract. Every non-null change-pair ID is
rejected. There is no registry-population option or negative test-only variant in S1.

## Preview facts and limits

The output-only preview rebuilds detached request/result snapshots, their IDs, exact source/criteria
hashes and registry version. It never accepts a submitted preview as approval. Host-owned facts are:

| Field                                                           | Value                                                                 |
| --------------------------------------------------------------- | --------------------------------------------------------------------- |
| `changes` / `diffs`                                             | Empty arrays                                                          |
| `provider_calls`                                                | `0` for this operation                                                |
| `execution_status` / `patch_application` / `restoration_status` | `not-run`                                                             |
| `authorization_status`                                          | `unknown`                                                             |
| `provenance`                                                    | Exactly `kind` = `caller-supplied-data`, `authenticated` = JSON false |

These facts provide no live-model provenance, authenticated review receipt or sharing/execution
permission. The preview is data, not a renderer or approval service. Escape untrusted text when
displaying it; copied snapshots, Markdown or terminal controls cannot grant authority.

| Bound                             | Limit                               |
| --------------------------------- | ----------------------------------- |
| Complete canonical UTF-8 artifact | 262,144 bytes                       |
| JSON depth / visited nodes        | 32 / 8,192                          |
| Registered source text            | 32,768 characters                   |
| General text item / ID            | 4,096 / 128 characters              |
| Text list                         | At most 32 items; minimums above    |
| Evidence IDs                      | Exactly two distinct registered IDs |

Budgets cover requests, recommendations, snapshots and the complete host preview, including host
metadata growth. Exact object keys/scalar types, duplicate JSON keys, non-finite numbers, invalid
Unicode and shared text-control rules are checked without coercion. General text permits TAB/LF/CR;
the helper does not remove every bidi/zero-width character, so safe presentation remains necessary.

## Explicitly scripted Python example

This example constructs an `unknown` **SCRIPTED** response; it does not infer `no-change`, obtain
an AI answer, evaluate the policy or approve anything. JSON output is ASCII-escaped display data.
Use an environment containing this branch's source implementation, not the alpha.3 executable.

```python
import json

from authzest.codex.owner_policy_recommendation import (
    build_owner_policy_recommendation_request,
    prepare_owner_policy_recommendation_preview,
    validate_owner_policy_recommendation,
    validate_owner_policy_recommendation_request,
)

request = build_owner_policy_recommendation_request()
request = validate_owner_policy_recommendation_request(
    json.dumps(request.to_dict(), ensure_ascii=True)
)
payload = request.to_dict()

# SCRIPTED caller-owned example, not a model response or a policy verdict.
SCRIPTED_RESULT = {
    "schema_version": "1.0",
    "request_id": request.request_id,
    "status": "unknown",
    "rationale": "Scripted example: no semantic review was performed.",
    "evidence_ids": [
        payload["source"]["evidence_id"],
        payload["criteria"]["evidence_id"],
    ],
    "assumptions": ["This is caller-supplied demonstration data."],
    "uncertainties": ["The example does not establish recommendation correctness."],
    "expected_effects": ["No source change or execution is requested."],
    "limitations": ["No provider, policy evaluation or endpoint verification."],
    "change_pair_id": None,
}
recommendation = validate_owner_policy_recommendation(
    json.dumps(SCRIPTED_RESULT, ensure_ascii=True), request
)
preview = prepare_owner_policy_recommendation_preview(recommendation, request)
print(json.dumps(preview.to_dict(), ensure_ascii=True, indent=2))
```

## Verification and next gates

Required offline verification covers both result statuses, detached/forged/stale artifacts, exact
evidence and closed fields, budget boundaries and guards against filesystem/network/provider/process
effects or target import/evaluation. These are verification requirements, not test counts or passes
recorded by this document; implementation results must be reported from actual runs.

S1 does not complete #81. Cases/labels/observations, provider wiring, registered repair pairs and
before/after policy checks need separately reviewed extensions and exact artifact bindings.
A later live request needs fresh minimized sharing approval; exact-diff application, verification
and restoration require distinct current-state decisions. No release, tag or further approval
follows from preparing or validating these data objects.
