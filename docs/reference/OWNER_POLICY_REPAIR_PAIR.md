<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_REPAIR_PAIR.md">한국어</a>
</p>

# Offline registered owner-policy repair-pair API

[Documentation index](../README.md) · [Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Historical pair design](../development/OWNER_POLICY_REPAIR_PAIR_DESIGN.md) ·
[S1 recommendation API](OWNER_POLICY_RECOMMENDATION.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81)

## Availability and boundary — 2026-10-21 KST

The source implementation introduced in [PR #101](https://github.com/casing1/authzest/pull/101)
provides a pure Python data API in `authzest.codex.owner_policy_repair_pair`:
one registered synthetic source pair, its exact case/label and recorded-review bindings, and a
host-derived one-file diff preview. It remains unreleased; CI/review/delivery and merge outcomes
are tracked in PR #101.
It does not complete #81/#35 or add a CLI, provider request, policy execution or file application.
Published alpha.3 is unchanged.

The unchanged [pair design](../development/OWNER_POLICY_REPAIR_PAIR_DESIGN.md) was delivered through
[PR #100](https://github.com/casing1/authzest/pull/100) at
`c12f4b137b30f96202b3a2555b3b5a151edf6e56` on 2026-10-19 KST, the implementation base rather
than a claim about latest main. The maintainer separately approved the exact scenario/source pair
and all eight assistant-authored expectations, then this bounded pure registry/preview slice;
see the [recorded decision](https://github.com/casing1/authzest/pull/100#issuecomment-6258235318).
Original authorship remains assistant-authored. The record is not authenticated approval authority,
runtime consent, an observation, a new model response or a maintained evaluation set.

The API accepts no caller-selected path, source, pair, registry, cases, labels, review record,
model or callback. It imports/evaluates neither policy candidate, reads/writes no target file,
accesses no filesystem/network/provider/process, applies no patch and restores nothing.
`policy.py` is a logical display label, not a path to open. S1 schema `1.0`/registry `empty-v1`,
its refusal of non-null change-pair IDs, the #80 correct-policy worker/allowlist and all historical
#77 model/review/observation records are unchanged. Correct-policy `no-change`/`unknown` stays valid.

## Python entry points

| Entry point                                      | Result                                                                         |
| ------------------------------------------------ | ------------------------------------------------------------------------------ |
| `build_owner_policy_repair_pair()`               | Build the one registered `OwnerPolicyRepairPair`; no configuration arguments   |
| `validate_owner_policy_repair_pair(raw)`         | Rebuild and validate the complete exact current registered manifest            |
| `prepare_owner_policy_repair_pair_preview(pair)` | Revalidate the pair and return an `OwnerPolicyRepairPairPreview` with one diff |

The pair exposes a derived `pair_id`; both wrappers provide `to_dict()` with detached data.
The validator's `raw` argument is serialized JSON text, not a dictionary, file path or executable
input. A directly constructed dataclass, copied ID, hash, `to_dict()` result or preview is not
validation or approval authority. Every consumer must revalidate the complete registered context;
the preview builder does this before deriving the diff. Forged, stale or modified contents are refused.

## Registered manifest and identities

Pair schema `1.0`, registry version `owned-synthetic-v1` and content version `test-only-v1` are
separate from S1's empty registry, report schema `1.2` and package version `0.1.0a3`.
The manifest has exactly `schema_version`, `kind`, `registry_version`, `content` and `review_binding`.
Its `kind` is `owner-policy-repair-pair`. The full closed content is:

| Content field  | Registered value or binding                                                                         |
| -------------- | --------------------------------------------------------------------------------------------------- |
| `version`      | `test-only-v1`                                                                                      |
| `scenario_id`  | `synthetic-owner-omission-v1`                                                                       |
| `path`         | `policy.py`, display data only                                                                      |
| `before`       | Exactly `text` / `sha256`: inert, deliberately incorrect test-only source with the warning retained |
| `after`        | Exactly `text` / `sha256`: the unchanged correct maintained `OWNER_POLICY_SOURCE`                   |
| `criteria`     | Exactly `text` / `sha256`: S1's exact policy-only criteria, without a trailing LF                   |
| `assumptions`  | S1's exact three ordered trusted-input assumptions, each with `id` / `text`                         |
| `cases`        | The exact ordered eight-element reviewed case/expectation array                                     |
| `cases_sha256` | Canonical identity of that full array, including expectations                                       |

Before and after are UTF-8, LF-only, without a BOM, retaining the final LF. Before omits only the
final subject/owner comparison and prepends the explicit intentionally-incorrect test-only warning;
the correct maintained example is not changed or labelled vulnerable. The builder pins the S1
request identity and complete content, not merely a scenario slug or an after hash.

| Content identity    | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| Before, 2,016 bytes | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| After, 1,960 bytes  | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |
| Eight cases/labels  | `96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3` |
| Complete content    | `2cbbc004b46ac2bc65b98c3e3b4b3e1e5919dd3d1b35920871372432c23203fb` |
| Review record       | `3540dd3578ee838b1bfb34f3c02019286716b47664ec942da46e8dac25d4b7e8` |

The current pair ID is
`owner-repair-pair-a4f764f8cbff25089bd40076c5f4a5cc76775312c973e3e22e9b9f353038ba08`.
It is a derived property, not a self-referential manifest field. Structured identities use canonical
UTF-8 JSON with sorted object keys, compact separators, preserved array order and no trailing LF.
Source/diff hashes instead identify exact UTF-8 text bytes. Version/content changes invalidate old
bindings; recomputing a hash for altered data does not register or approve it.

### Separate recorded-review binding

`review_binding` has exactly `content_sha256`, `review_record_sha256` and `review_record`.
The complete record is embedded and printed in the manifest, not loaded from a separate file.
It binds the content and cases hashes to design head `35ebe17d96c07540cf2753f2e53625d138ded0aa`,
decision date `2026-10-19`, decision `accept-scenario-and-case-expectations`, and the recorded-decision
URL above. Its remaining closed fields are `schema_version` = `1.0`,
`kind` = `recorded-owner-policy-pair-review` and exactly
`provenance` = `{"kind":"recorded-maintainer-chat","authenticated":false}`.

Content is hashed first; the separate record refers to that content hash; the manifest binds both
hashes. There is no self-referential hash cycle. The validator checks the full registered record,
not just its URL or copied digest. The recorded maintainer decision is real provenance of the exact
review, but the JSON is not an authenticated receipt or transferable permission for another action.

### Expectations are not observations

| Case ID                        | Reviewed expectation |
| ------------------------------ | -------------------- |
| `owner-control`                | `allow`              |
| `non-owner`                    | `deny`               |
| `missing-read-scope`           | `deny`               |
| `unauthenticated-owner`        | `deny`               |
| `missing-principal`            | `deny`               |
| `missing-report`               | `deny`               |
| `wildcard-is-not-read`         | `deny`               |
| `exact-owner-no-normalization` | `deny`               |

The full principal/report inputs remain visible in the manifest; the leading space in subject
`" alice"` is significant. Static hypotheses in the historical design are not before/after results.
Actual observations remain null, comparison is `not-evaluated`, and authorization is `unknown`.
These eight labels do not replace the historical ten #77 labels or the separate 28 developer-test
labels. Finite synthetic expectations prove neither trusted authentication nor HTTP enforcement.

## Output-only diff preview

Preview `kind` is `owner-policy-repair-pair-preview`. It includes `schema_version`, `pair_id`,
the full revalidated `pair`, `recipe_version`, `diff`, `diff_sha256` and the facts below.
Recipe `unified-v1-context-3` derives the diff from registered exact source bytes using three lines
of context and fixed display headers `a/policy.py` / `b/policy.py`. It accepts no model-supplied diff.
The current exact diff hash is
`0358127d2373c7a729c0b656c1c9cbcb698dc5f04073a917f848280d0c8be75d`.

| Host-owned field                                                | Value                                                                    |
| --------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `provider_calls`                                                | `0`                                                                      |
| `execution_status` / `patch_application` / `restoration_status` | `not-run`                                                                |
| `observations`                                                  | Exactly `{"before":null,"after":null}`                                   |
| `comparison_status`                                             | `not-evaluated`                                                          |
| `authorization_status`                                          | `unknown`                                                                |
| `provenance`                                                    | Exactly `{"kind":"registered-test-only-template","authenticated":false}` |

The preview is inspectable data, not an approval token, renderer, patch service or execution plan.
Displaying it does not apply the diff or verify the policy. Escape text in any later presentation
layer; copied JSON, terminal output or Markdown cannot grant authority.

## Bounds and strict validation

The shared decoder enforces a complete canonical/raw UTF-8 budget of 262,144 bytes, depth 32 and
8,192 visited nodes, including complete host preview metadata and diff. Registered source text is
bounded to 32,768 characters, general text to 4,096 and identifiers to 128. The fixed contract has
three assumptions, eight distinct case IDs and at most 16 distinct scopes per principal.
These bounds do not make the registry configurable: even a well-shaped alternative is refused.

Exact keys/scalar types, duplicate JSON keys, non-finite numbers, invalid Unicode and shared text
control rules are checked without coercion or source normalization. Unknown/additional fields,
changed labels/sources/criteria/assumptions/versions/review provenance, forged hashes and execution,
provider, patch or approval fields are rejected. Full context equality is required after rebuilding
the registered manifest; direct wrapper construction bypasses none of these checks.

## Pure Python preview example

Use a source environment containing PR #101's implementation, not the alpha.3 executable. This example only builds inert
registered data and prints ASCII-escaped JSON; it obtains no AI response, evaluates neither policy
candidate and makes no approval, filesystem/network or patch request.

```python
import json

from authzest.codex.owner_policy_repair_pair import (
    build_owner_policy_repair_pair,
    prepare_owner_policy_repair_pair_preview,
)

pair = build_owner_policy_repair_pair()
preview = prepare_owner_policy_repair_pair_preview(pair)
print(json.dumps(preview.to_dict(), ensure_ascii=True, indent=2))
```

## Remaining gates

Offline verification must cover exact bindings, detached/forged/stale artifacts, strict closed
shapes, complete-preview budgets and guards against side effects or target import/evaluation.
This document records requirements, not test/CI passes or runtime observations.

Model integration needs its own minimized request/output design and fresh bounded sharing decision.
Before/after observations need a separately reviewed fixed recipe and fresh exact-plan execution
decisions; #80 must continue rejecting this negative source. Pair-bound new-copy diff approval,
application, verification and restoration need their own later designs and current-state decisions.
No runtime, provider use, source sharing, file writes, automatic retry/restoration, merge, tag or
release is authorized by this data API or the recorded label approval. Wider #81/#82 and residual
tooling/publication gates remain independent and incomplete.
