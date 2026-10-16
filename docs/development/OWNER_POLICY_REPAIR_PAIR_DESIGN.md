<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/OWNER_POLICY_REPAIR_PAIR_DESIGN.md">한국어</a>
</p>

# Synthetic owner-policy repair pair — design for review

[Documentation index](../README.md) · [Development plan](DEVELOPMENT_PLAN.md) ·
[Implemented S1 API](../reference/OWNER_POLICY_RECOMMENDATION.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81)

## Status and requested decision

**Proposed, unregistered and unexecuted — 2026-10-16 KST.** This document proposes one deliberately
incorrect **test-only** policy and its exact repair, plus eight assistant-authored expected labels.
It adds no source variant, registry entry, model request, executable case, worker, CLI or application
capability. Documentation/CI success is not scenario review, label approval or execution evidence.

Baseline: main `7173a54d12f50605b5f5e4d4388d350fd6df276d`. S1 was delivered through
[PR #99](https://github.com/casing1/authzest/pull/99) at `4290d2d`; it still accepts only `no-change`
and `unknown`, with registry `empty-v1`. This proposal does not edit S1 or the historical
[original design](OWNER_POLICY_IMPROVEMENT_DESIGN.md).

The next maintainer decision is whether to accept **this exact synthetic scenario, source pair and
eight expected labels** for a subsequent offline registry/diff-preview implementation. That does not
approve unspecified future schemas, source sharing, a paid review, policy execution, file application,
restoration, merge or publication. Changed bytes/cases require fresh review; implementation should not
register a negative variant before this review. #81 and #35 remain incomplete.

## One owned regression, not a production finding

The maintained predicate correctly requires trusted authentication, literal `reports:read` and exact
subject/owner equality. Do not change `examples/fastapi_owner_policy/policy.py` or
`OWNER_POLICY_SOURCE`, or describe them as vulnerable. The proposed negative fixture deliberately
omits only the final ownership comparison while retaining authentication, scope and input checks.
The correct maintained source is the repaired control.

Inputs are local synthetic trusted context, not HTTP claims. Dataclass construction authenticates
nothing; report identity/ownership require a trusted lookup. No HTTP, authentication provider, router,
database, network target or real user data is involved. This is a policy-level defensive regression,
not an exploit script or endpoint-authorization test. Correct-policy `no-change`/`unknown` remains
valid; producing a patch is not the success criterion.

## Exact candidate bytes

Use the complete `OWNER_POLICY_SOURCE` literal at the pinned baseline as the **after** bytes. It is
byte-identical to the maintained example file there. Both candidates are UTF-8, LF-only, without a
BOM, and retain the final LF. No newline, indentation or identifier normalization is permitted.

Derive **before** in memory by replacing the single exact line
`    return subject == owner_id and "reports:read" in scopes` with
`    return "reports:read" in scopes`, preserving its LF, then prepending exactly this line and one LF:

```text
# INTENTIONALLY INCORRECT TEST-ONLY: ownership comparison deliberately omitted.
```

No other byte changes. The exact repair removes that warning and restores the equality clause;
the first line of the existing module docstring remains unchanged. The logical filename `policy.py`
is display data, not an existing-checkout write target.

| Snapshot | UTF-8 bytes | SHA-256                                                            |
| -------- | ----------- | ------------------------------------------------------------------ |
| before   | 2,016       | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| after    | 1,960       | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |

The following is an illustrative exact-content diff; future host code derives its own complete diff
from the registered bytes, never trusting a model-supplied diff:

```diff
--- a/policy.py
+++ b/policy.py
@@ -1,2 +1,1 @@
-# INTENTIONALLY INCORRECT TEST-ONLY: ownership comparison deliberately omitted.
 """Pure policy for a maintained synthetic example, not an authentication provider.
@@ -51,4 +50,4 @@
         return False
     if not all(_nonblank_string(scope) for scope in scopes):
         return False
-    return "reports:read" in scopes
+    return subject == owner_id and "reports:read" in scopes
```

The proposed scenario name is `synthetic-owner-omission-v1`; it is not an accepted registry ID or
approval credential. An implementation must bind a host-derived pair ID to the complete versioned
manifest: both full source texts/hashes, logical path, exact S1 policy-only criteria and trusted-input
assumptions, scenario and complete case/label data. Do not identify a pair only by a human-readable
slug, the after hash or a copied preview. Any content/version change invalidates the relevant binding.

## Eight proposed cases and labels

These are **assistant-authored, unreviewed** data, not new AI output, a maintained evaluation set or
previously approved #77 labels. Review them as a new exact set. `expected` is the policy criterion;
it does not change to match the intentionally incorrect candidate. Scope arrays are decoded into
the fixed harness's supported `frozenset`, never arbitrary objects or executable expressions.

```json
[
  {
    "case_id": "owner-control",
    "principal": {
      "subject": "alice",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "allow"
  },
  {
    "case_id": "non-owner",
    "principal": {
      "subject": "bob",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "missing-read-scope",
    "principal": { "subject": "alice", "authenticated": true, "scopes": [] },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "unauthenticated-owner",
    "principal": {
      "subject": "alice",
      "authenticated": false,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "missing-principal",
    "principal": null,
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "missing-report",
    "principal": {
      "subject": "alice",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": null,
    "expected": "deny"
  },
  {
    "case_id": "wildcard-is-not-read",
    "principal": {
      "subject": "alice",
      "authenticated": true,
      "scopes": ["reports:*"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "exact-owner-no-normalization",
    "principal": {
      "subject": " alice",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  }
]
```

The proposed set has one allow and seven deny labels. Static reasoning predicts that **two deny
cases**, `non-owner` and `exact-owner-no-normalization`, would incorrectly allow before and deny
after. The positive `owner-control` is predicted to allow on both; the other five controls are
predicted to deny on both. These are hypotheses, not observations. The leading space in subject
`" alice"` is significant; the owner is exactly `"alice"`.

The exact eight-element array above has canonical SHA-256
`96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3`:
UTF-8 JSON, recursively sorted object keys, compact separators, preserved array order, no trailing LF.
This content identity includes the proposed expected labels; it is not a label-review receipt.

For every case, actual before/after observations are currently **null / not-run**, comparison is
not evaluated, and authorization remains unknown. Even eight later matches would support only
this finite synthetic policy regression, not a security proof or HTTP enforcement. Do not overwrite
the original ten model cases, #77 review/observation records, or the separate 28 developer-test labels.

## Subsequent implementation boundaries

1. **Offline registry and preview first.** After exact design/label review, implement a separate
   versioned closed contract for this registered pair and host-derived one-file diff. Preserve S1
   schema `1.0`/`empty-v1`, old payload acceptance/refusal and all historical identities. Revalidate
   complete artifacts and final-preview budgets; IDs and dataclasses are not approval capabilities.
2. **Codex integration separately.** Review the exact minimized request/output schema and prompt
   before wiring it. Reuse no old sharing decision: a later call requires a fresh complete sharing
   preview, account/model/usage/timeout limits and explicit approval. Model case suggestions remain
   bounded JSON data with separately reviewed expectations; model text never becomes source, shell,
   commands, imports or a trusted approval/status. The first repair is registered-template selection,
   not arbitrary AI-generated code or an independently discovered production flaw.
3. **Dedicated fixed check recipe.** #80 pins the correct policy and its worker; it must reject the
   negative source. Do not broaden its source hash or accept caller-selected paths/text. A separately
   reviewed worker/recipe must pin the pair, exact implementation/worker identities, case/label set,
   transport, limits and cleanup behavior. Do not execute this design's fences or an AI-written test.
4. **New-copy application only.** The existing `FixtureApplySession` is for `main.py`; its generic
   proposal checks do not prove registration of this pair. Do not merely allow a new filename or
   coerce this into the debug/configuration-health checker. Design a pair-bound single-file
   `policy.py` coordinator with current before/after bytes, workspace/file identities and an exact
   host diff. Preserve originals, later user edits and failure/recovery records. No existing-checkout,
   multi-file, Windows application or restart/resume claim follows from current support.

Source sharing, exact-label review, before-check, exact-diff approval, apply, after-check and restore
are separate current-state decisions. A completed before-check cannot authorize an after-check or
prove a patch applied. A valid preview or applying the diff cannot mean verified. Timeouts, cancellation,
stale/declined/expired/reused decisions, changed worker/cases/source and later user edits fail closed.
Unknown observations, incomplete cleanup, journal/fsync failures and uncertain restoration stay
unknown/failed, never silently pass. No automatic retry or restoration. A child process is not an
OS/network sandbox; trusted tooling and no hostile concurrent same-user writer remain assumptions.

## Review and delivery checklist

- [ ] Maintainer reviews this exact scenario and full before/after bytes, hashes and warning.
- [ ] Maintainer separately approves or corrects all eight expected labels as one exact set.
- [ ] Review the closed offline pair/preview schema before implementing that next slice.
- [ ] Add offline positive/refusal/stale/forged/budget and side-effect-guard tests with implementation.
- [ ] Separately review provider sharing, fixed execution recipe and copy/apply/check/restore design.
- [ ] Obtain fresh bounded live/runtime approvals only when those exact plans exist.

Keep this checklist unchecked in a design-only PR. Assign casing1, relevant existing labels and
milestone 04; use draft status while maintainer review is pending. Normal CI does not authorize
manual paid reviews, automatic-review activation or merging. Keep #81/#35/#82 acceptance and
#89/#83 residual-tooling/publication gates independent; no version, tag or release changes here.
