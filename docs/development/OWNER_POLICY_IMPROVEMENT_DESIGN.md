<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/OWNER_POLICY_IMPROVEMENT_DESIGN.md">한국어</a>
</p>

# Owned policy improvement design

[Documentation index](../README.md) · [Development plan](DEVELOPMENT_PLAN.md) ·
[Fixed policy check](../reference/OWNER_POLICY_CHECK.md) · [Issue #81](https://github.com/casing1/authzest/issues/81)

## Status and decision to review

**Proposed, not implemented — 2026-10-15 KST.** This specifies only the first offline recommendation
contract and read-only preview for #81. It is not a new API, CLI command, model invocation or approved
patch workflow. Maintainer design review precedes implementation. Passing documentation checks or
merging this design does not record that approval or complete #81.

The baseline is main `38587c30e644aa459cdd5242faf279f44ffa2240`, which merged #80 through
[PR #97](https://github.com/casing1/authzest/pull/97). The separately approved recipe `1.1` source run
at `e037986` matched all ten reviewed expectations; the original recipe `1.0` observation remains
separate. Both one-run approvals are consumed. These are historical pure-policy observations, not
HTTP/authentication acceptance, a new model response or permission for another check.

Review this bounded choice: one registered policy snapshot plus policy criteria; results limited to
`no-change` or `unknown`; an empty change-pair registry. Cases, labels and observations are excluded
from this first request schema, rather than importing old results as current execution evidence.
Their later inclusion requires a separately reviewed version and exact artifact bindings.

## Keep existing contracts unchanged

The existing owner review binds two source snapshots and returns answers/cases. Its sharing decision
does not cover this new input or a patch. The general proposal contract requires a change and allows
up to eight caller-authored replacements. Neither contract should be relaxed for this slice.
The #80 worker continues accepting only its registered correct policy; its source, recipe and
execution allowlist are unchanged. A valid recommendation is not an execution capability.

## Proposed request

A pure builder would use registered in-memory constants only. It accepts no path, arbitrary source,
repository, model choice, callback, case set, label record or observation record. The logical name
`policy.py` identifies displayed data, not a file to open or a patch destination.

The proposed schema version is `1.0`, independent of report schema `1.2`, existing owner-review
schemas and package version `0.1.0a3`. The following are the complete request payload fields:

| Field            | Host-owned value or rule                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `schema_version` | Exactly `1.0`                                                                                                             |
| `kind`           | Exactly `owner-policy-recommendation-request`                                                                             |
| `scenario_id`    | Exactly `owned-report-read-policy-v1`                                                                                     |
| `source`         | Exactly `path`, `text`, `sha256`, `evidence_id`; registered `policy.py` bytes only                                        |
| `criteria`       | Exactly `text`, `sha256`, `evidence_id`; the proposed policy-only snapshot below                                          |
| `assumptions`    | Fixed ordered objects with exactly `id`, `text`: trusted principal, trusted ownership lookup, synthetic pure-policy scope |
| `registry`       | Exactly `version`, `pairs`; version `empty-v1` and an empty array                                                         |

The source bytes are the existing `OWNER_POLICY_SOURCE` constant in the
[maintained source template](../../src/authzest/codex/owner_policy_review.py), not an ambient file.
Text hashes use exact UTF-8 bytes, including line endings. Source evidence uses prefix
`owner-recommendation-source-` and the canonical hash of its `path`, `text`, `sha256` object;
criteria evidence uses prefix `owner-recommendation-criteria-` and the canonical hash of its
`text`, `sha256` object. Neither includes its own `evidence_id`. The request ID is
`owner-recommendation-request-` plus the shared canonical SHA-256 of the complete payload; it is a
host-derived property, not a self-referential payload field. Any relevant byte/version change changes
the ID and makes an old result stale. Hashes identify content; they do not attest identity or approval.

The proposed new criteria snapshot preserves the previously approved policy meaning, not the old
owner-review prompt's historical label-review sentence. Its exact new wording is part of this review:

```text
Allow a report read only for an already trusted principal whose authenticated value is exactly true, whose scopes contain the literal reports:read value, and whose subject exactly matches a trusted report owner. Deny missing or malformed principal/report context, blank identifiers or malformed scopes. Do not normalize identifiers. There is no administrator, wildcard or ownership exception. This pure predicate does not authenticate inputs or prove HTTP enforcement.
```

This criteria value is the single line above, with no trailing LF. The fence's closing newline is
not part of the string. The source constant, by contrast, retains all of its original line endings.
The request's exact ordered assumptions are:

```json
[
  {
    "id": "trusted-principal",
    "text": "The caller supplies an already trusted principal; constructing a dataclass does not authenticate identity, scopes or authentication claims."
  },
  {
    "id": "trusted-ownership",
    "text": "Report ownership and report identity come from a trusted lookup, not request-supplied claims."
  },
  {
    "id": "synthetic-pure-policy",
    "text": "Only the maintained synthetic pure predicate is in scope; HTTP, authentication-provider, database and endpoint enforcement are not evaluated."
  }
]
```

Do not edit the existing `OWNER_POLICY_TEXT` or rewrite model/label history to introduce this snapshot.
Constructing the principal/report data does not make request-supplied identity or ownership trusted.

## Proposed raw result

Accept exactly the fields below. No status, source hash or typed wrapper supplied by a caller bypasses
revalidation against the current registered request. This data may be caller-authored or scripted;
its valid shape is not proof that Codex produced it or that its explanation is correct.

| Field              | Validation                                                       |
| ------------------ | ---------------------------------------------------------------- |
| `schema_version`   | Exactly `1.0`                                                    |
| `request_id`       | Exact current host-derived request ID                            |
| `status`           | Exactly `no-change` or `unknown`                                 |
| `rationale`        | Nonblank bounded text                                            |
| `evidence_ids`     | Both source and criteria IDs, no unknown or duplicate IDs        |
| `assumptions`      | Bounded nonblank text list; at least one entry                   |
| `uncertainties`    | Bounded nonblank text list; at least one entry for `unknown`     |
| `expected_effects` | Bounded nonblank text list; at least one entry                   |
| `limitations`      | Bounded nonblank text list; at least one entry for either status |
| `change_pair_id`   | Exactly JSON null; every non-null value is rejected              |

`no-change` means no source change is supported within this input scope, not a security pass.
`unknown` identifies the missing basis for a recommendation, not a fabricated denial or observed
failure. Free-form explanations remain data, including text that looks like instructions or code.
Structural checks cannot establish semantic support, trusted authentication or endpoint enforcement.

Reject additional fields even when empty: replacement source, `after_text`, `changes`, `diffs`,
patches, commands, executable tests, cases, labels, observations, provider/model identity claims,
approval choices and execution/application statuses are outside this raw schema.

## Host preview and initial registry

The proposed pure preview revalidates both artifacts and returns detached request/result snapshots,
their IDs, exact content hashes and registry version. A recommendation ID uses prefix
`owner-recommendation-` and the canonical hash of the validated raw result, including its request ID.
The complete preview object has exactly the following fields. It is output-only; no submitted
preview is an approval input. The host rebuilds every field, never accepting raw-result overrides:

| Preview field          | Fixed value in this slice                                                               |
| ---------------------- | --------------------------------------------------------------------------------------- |
| `schema_version`       | Exactly `1.0`                                                                           |
| `kind`                 | Exactly `owner-policy-recommendation-preview`                                           |
| `request_id`           | Current host-derived request ID                                                         |
| `recommendation_id`    | Current host-derived recommendation ID                                                  |
| `request`              | Detached complete validated request payload                                             |
| `recommendation`       | Detached complete validated raw result                                                  |
| `source_sha256`        | Exact current `source.sha256`                                                           |
| `criteria_sha256`      | Exact current `criteria.sha256`                                                         |
| `registry_version`     | Exactly `empty-v1`                                                                      |
| `changes` / `diffs`    | Empty arrays                                                                            |
| `provider_calls`       | `0` for this operation                                                                  |
| `execution_status`     | `not-run`                                                                               |
| `patch_application`    | `not-run`                                                                               |
| `restoration_status`   | `not-run`                                                                               |
| `authorization_status` | `unknown`                                                                               |
| `provenance`           | Exactly `kind` = `caller-supplied-data` and `authenticated` = JSON false; no other keys |

There is no constructor option to populate the registry. A later registered pair would require
maintainer review of an explicitly owned synthetic scenario, exact before/after bytes, hashes and
version. Only then could a separately reviewed extension accept a pair ID and derive a one-file
diff on the host. No negative variant or replacement source is proposed here, and the current
correct policy must not be labelled vulnerable merely to demonstrate a fix.

The preview is inspectable data, not a renderer or approval service. A later presentation layer must
escape all untrusted text, for example with ASCII-escaped JSON; it must not execute it or treat
Markdown/terminal controls as authority. IDs, serialized snapshots and copied previews never grant
sharing, application, verification or restoration permission.

## Validation budgets and offline acceptance

Apply the existing shared JSON rules to requests, raw results, immutable snapshots and the completed
host preview, not only the incoming result. No filesystem/provider/process access or policy evaluation
is part of these operations.

| Bound                             | Proposed limit                          |
| --------------------------------- | --------------------------------------- |
| Complete canonical UTF-8 artifact | 262,144 bytes                           |
| JSON depth / visited nodes        | 32 / 8,192                              |
| Registered source text            | 32,768 characters                       |
| Each general text item            | 4,096 characters                        |
| Each ID                           | 128 characters                          |
| Each text list                    | At most 32 items; minimums as above     |
| Evidence IDs                      | Exactly the two distinct registered IDs |

Require exact object keys and scalar types; do not coerce booleans, numbers, strings or null.
Reject duplicate JSON keys, non-finite numbers, invalid Unicode and the control characters rejected
by the shared text helper. TAB/LF/CR are permitted in general text; the helper does not block every
bidi/zero-width character. Safe presentation is still necessary.

The implementation PR should cover:

- Valid results for both statuses, detached snapshots, deterministic identities and empty changes/diffs.
- Missing/extra/duplicate keys, wrong types/status/version and non-object JSON.
- Source/criteria/newline/hash/assumption/registry changes and stale or directly forged wrappers.
- Missing/unknown/duplicate evidence, empty required lists, and every non-null change-pair ID.
- Forbidden source/diff/command/case/observation/approval fields, including empty values.
- Character, UTF-8, depth, node and collection boundaries, including final host-metadata growth.
- Guards that fail on filesystem/network/provider/process effects and target import/evaluation.

These are proposed tests, not tests already added or passed. Scripted answers must remain explicitly
scripted. Error diagnostics should use existing closed codes without echoing source or raw payloads.

## Review and delivery gates

1. Maintainer reviews this exact first-slice input, output and refusal design before implementation.
2. Implement only the pure contract/preview with guarded offline tests and matching English/Korean docs.
3. Use a focused PR with casing1, existing labels and milestone 04; required CI/reviews remain normal gates.
4. Review case/label/observation bindings, a negative test-only scenario if needed, and registered repair
   pairs separately before extending the schema or #80 worker.
5. A later actual provider request needs its own minimized sharing preview and bounded approval.
   Source sharing, label review, before-check, exact-diff application, after-check and restore remain
   separate current-state decisions. Preserve the original checkout and later user edits.

This design grants no paid/manual re-review, model invocation, code execution, patch, release or tag.
It adds no new CLI, provider adapter, dependency, workflow or change to existing scan behavior.
Full #81 and the installed integrated acceptance under #82 remain open.
