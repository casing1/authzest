<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_REPAIR_CHECK.md">한국어</a>
</p>

# Registered repair-policy check API

[Documentation index](../README.md) · [Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Reviewed design](../development/OWNER_POLICY_REPAIR_CHECK_DESIGN.md) ·
[Registered pair](OWNER_POLICY_REPAIR_PAIR.md) · [Recommendation](OWNER_POLICY_REPAIR_RECOMMENDATION.md)

## Availability and evidence — 2026-10-28 KST

The unreleased source implementation in [PR #110](https://github.com/casing1/authzest/pull/110)
adds `authzest.runner.owner_policy_repair_check`, a dedicated fixed worker and its bounded transport.
The maintainer [approved the design and offline implementation](https://github.com/casing1/authzest/pull/110#issuecomment-6459020000),
not an actual worker run. Initial implementation verification at `510377c` used offline contracts,
static worker inspection and memory-only scripted process responses. Scripted booleans in those
tests are not observed policy behavior. Subsequent, separately approved **before-only** and
**after-only** runs completed as recorded below. Both one-run approvals are consumed. The after run
used the later documentation-only commit `7f9c5ce`; runtime source remained unchanged from `510377c`.

There is no new CLI command, API endpoint or dashboard view. Published alpha.3 does not include this
feature. The existing #80 coordinator, worker, policy registration and historical observations remain
unchanged. This implementation does not complete #81/#35/#82, activate paid reviews, merge or release.

## Separately approved before acceptance — 2026-10-28 KST

The [separate before-only approval](https://github.com/casing1/authzest/pull/110#issuecomment-6460245210)
was consumed by one fixed source run at `510377c`, on **2026-10-28 11:49:55 KST**. This was separate
from the earlier offline implementation checks and the earlier Codex recommendation attempt.
The host recorded `31.640417` ms, execution `completed`, exit `0`, and child/workspace/overall
cleanup all `confirmed`. Output revalidation passed.

| Recorded binding     | Value                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------- |
| Before plan ID       | `owner-repair-check-141cb7a9bd522d851529d795241d7c4a9018ee1758f4a4285b83de12015e0829` |
| Worker SHA-256       | `9d81411933c8a42b33e3162acc16d4bea828a70b6c5a97c87c1fe0a9e41ee3f2`                    |
| Capture file SHA-256 | `acf78772b41331b1c26b8127787b94fe50c076c989e65d81d8b12663dfea0cbc`                    |

The eight observed booleans, in registered case order, were
`[true, true, false, false, false, false, false, true]`: six expectation matches and two mismatches,
`non-owner` and `exact-owner-no-normalization`. Aggregate `status` and `comparison_status` were
`failed`, reason `case-mismatch`. This is the **expected successful demonstration of the intentionally
incorrect before policy**, not a worker/transport failure. The labels were not changed to force a pass.

Provider calls were `0`, authorization remained `unknown`, and application/restoration remained
`not-run`. The 17 historical artifact hashes remained unchanged, the original main checkout stayed
clean and #80 remained unchanged. This is an unauthenticated host record, not independent execution
attestation, a benchmark, endpoint authorization or applied-file verification; its hash identifies the
captured bytes without proving their origin. The capture hash covers the `capture.json` envelope
(decision, result and metadata), not only `result.payload_json`. No new committed fixture or schema
is introduced here.

This one-run before approval is consumed. At that before-only checkpoint, after remained unapproved
and unexecuted; the separate later after approval and observation are recorded below. The before run
did not authorize or automatically start after, and another before run requires fresh approval.

## Separately approved after-control acceptance — 2026-10-28 KST

The [separate after-only acceptance record](https://github.com/casing1/authzest/pull/110#issuecomment-6460474112)
records one approved run on **2026-10-28 13:11:38 KST**, at
`7f9c5ce5ef31ea8e49cd125e6c8459721b0cf6d7`. That commit changed documentation only; runtime source
was unchanged from `510377c`. The host recorded `36.152000` ms, execution `completed`, exit `0`,
and child/workspace/overall cleanup all `confirmed`. Output validation and separate offline
revalidation of the saved record passed; the latter did not rerun either candidate.

| Recorded binding     | Value                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------- |
| After plan ID        | `owner-repair-check-a034e599a2dd51b862f06084f23e1924e79c6a517d691bf1b9ef9d0187d214f5` |
| Plan bytes SHA-256   | `63e3a48561468a2b0d648c899f2fdf765f2e71d19df40a8428681cd2d88d256c`                    |
| Worker SHA-256       | `9d81411933c8a42b33e3162acc16d4bea828a70b6c5a97c87c1fe0a9e41ee3f2`                    |
| After source SHA-256 | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04`                    |
| Capture file SHA-256 | `16d235b8f3c9479821541f45e7284a917edd1386cadee8e74b65642ee7769714`                    |

The observed booleans, in registered case order, were
`[true, false, false, false, false, false, false, false]`: eight matches and zero mismatches.
Aggregate `status` and `comparison_status` were `passed`, reason `cases-match`. A separate pure-data
comparison of the captured before/after records confirmed equal pair/review/case/worker/recipe/input
bindings; only `non-owner` and `exact-owner-no-normalization` changed from `true` to `false`.
Candidate/source/plan identities remain intentionally different. This was offline inspection of
captured records, not a new product comparison API or authenticated execution attestation.

The capture-file hash covers the full decision/result/metadata envelope, not just result JSON.
Provider calls were `0`, authorization stayed `unknown`, and application/restoration stayed `not-run`.
No before rerun, retry, AI/network call, arbitrary repository execution or patch occurred. The 17
historical artifact hashes, original main checkout and #80 remained unchanged. These are bounded,
unauthenticated host observations of the registered synthetic controls, not an independent benchmark,
general authorization assurance or verification of an applied file.

Both candidate approvals are consumed; another run requires fresh approval. PR #110 remains draft.
The next gate is final-head review/delivery under new approval, followed by a separately reviewed
file-bound apply/check/restore design. Neither observation authorizes review activation, merge,
patching or release, and #81/#35/#82 remain incomplete.

## Fixed source and data boundary

The only inputs are the unchanged `synthetic-owner-omission-v1` pair and its eight reviewed cases.
Candidate is exactly `before` or `after`, with no default or `both` mode. `before` is intentionally
incorrect, owned, synthetic test-only text; it is not a reported production vulnerability. `after`
is the maintained correct-policy control. `policy.py` is a logical display label, never a caller path.
No caller source, case replacement, expected-label override, command, model response or
policy-execution callback is accepted.

The complete plan binds the registered pair/review record, selected source bytes/hash, eight ordered
cases and expected labels, input-only rows, dedicated worker bytes/hash and versioned recipe. The
derived plan ID is added to worker input after hashing the bindings. Current identity values are:

| Identity              | Value                                                              |
| --------------------- | ------------------------------------------------------------------ |
| Check ID              | `owned-owner-repair-check-v1`                                      |
| Recipe / coordinator  | `1.0` / `repair-check-coordinator-v1`                              |
| Worker SHA-256        | `9d81411933c8a42b33e3162acc16d4bea828a70b6c5a97c87c1fe0a9e41ee3f2` |
| Before source SHA-256 | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| After source SHA-256  | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |

Hashes detect changed bindings; they are not independent code attestation or execution permission.
Consult the complete plan and [pair reference](OWNER_POLICY_REPAIR_PAIR.md), not only these hashes.
Preparation and plan/result validation do not read a target path, start a child or evaluate policy.

## Python interface and separate decisions

| Entry point                                                 | Meaning                                                                              |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `prepare_owner_policy_repair_check(candidate)`              | Prepare the complete immutable, offline plan for one explicit candidate              |
| `validate_owner_policy_repair_check_plan(raw)`              | Rebuild and compare serialized JSON with the exact current plan                      |
| `OwnerPolicyRepairCheckSession(candidate)`                  | Create one live session with a complete `plan` and no execution decision             |
| `session.decide(choice, plan_id=..., lifetime_seconds=...)` | Record one exact-plan, expiring in-process choice                                    |
| `await session.run()`                                       | Consume the single attempt and enforce the decision before the fixed child path      |
| `validate_owner_policy_repair_check_result(raw)`            | Revalidate record shape, current bindings and comparison consistency; not provenance |

Snapshots expose `payload_json` and a detached `to_dict()`; plans additionally expose `check_plan_id`.
The session retains its result in `last_result`, including a cancellation record before re-raising the
original cancellation. Imported JSON, directly constructed snapshots or model recommendations cannot
grant a session decision. The caller controls this Python process: records and decisions are explicitly
unauthenticated, not an access-control boundary against a hostile caller.

Choices are `pending`, `approved`, `declined` or `cancelled`. Only an unexpired `pending` choice can
be replaced. Other choices are terminal. Invalid first/replacement decisions invalidate that session;
expired/reused choices, clock rollback and changed current plans cannot launch a child. Lifetimes must
be finite non-boolean numbers with `0 < lifetime_seconds <= 300`; clock readings and expiry must be
finite and nonnegative. One attempt is consumed before the first await, including failed preflight.
Concurrent calls and replay cannot obtain another attempt; there is no retry or fallback.

Review the fresh complete plan before recording consent. **A before decision never authorizes after.**
An after check needs a separate session and fresh decision against its own complete plan. The past
label-review decision, consumed Codex sharing approval and design-implementation approval authorize
neither candidate's actual execution. No real-run example is provided here.

This example only prepares and prints inert, ASCII-escaped plan data; it records no decision:

```python
import json

from authzest.runner.owner_policy_repair_check import prepare_owner_policy_repair_check

plan = prepare_owner_policy_repair_check("before")
print(json.dumps(plan.to_dict(), ensure_ascii=True, indent=2))
```

## Worker recipe and failure handling

Execution is POSIX, non-frozen Python source only. The fixed trusted interpreter command is
`sys.executable -I -S -c` with pinned embedded worker text, a minimal non-inherited environment,
a fresh private temporary working directory and a new process group. It does not copy/import a
repository, inherit account/provider/proxy settings, or intentionally use network, FastAPI, HTTP,
databases or install hooks. These are trusted-process controls, **not an OS/network sandbox or a
CPU/memory hard cap**. A trusted interpreter/toolchain and stable registered code are assumptions.

Startup, input/output and completion share **5 seconds**. Child launch settlement, kill and reap share
**1 additional second**. Host temporary-directory creation/removal has no hard wall-clock guarantee:
this is not a hard six-second total deadline. Worker input is at most 256 KiB and output at most
16 KiB; defensive JSON bounds are depth 32 and 8,192 nodes. Fields allow at most 16 scopes and
128 characters per identifier/scope, but exact registered equality remains mandatory.

Worker stdin contains exact request identities and eight ordered input-only rows, not expected labels,
source text, paths, model explanations or reviewer prose. The worker validates the whole request before
compiling exactly one embedded candidate. The coordinator accepts only exact identities and eight
ordered case-ID/input-hash/strict-boolean rows. Missing/extra/reordered/duplicate/coerced/partial or
malformed output is not an observation.

Launch state (`not-attempted`, `no-child`, `ambiguous`, `started`) is separate from child and workspace
cleanup (`not-needed`, `confirmed`, `unconfirmed`). A known launch failure with no child does not waive
workspace cleanup; directory cleanup failure remains unconfirmed. An unresolved in-flight launch
cannot claim no child. Repeated cancellation preserves the original cancellation after bounded child
cleanup and host workspace cleanup; exception/stderr text is not result data.

## Reading results without overclaiming

Each result retains the full exact plan, candidate, expectations, null-or-boolean observations and
separate execution/comparison/launch/cleanup diagnostics. Publication of observations requires a
zero exit, strict output validation and confirmation of both child and workspace cleanup.

| Result field        | Meaning                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------- |
| `status`            | `not-run`, `passed` or `failed`; `not-run` means no accepted comparison, not necessarily no process attempt |
| `execution_status`  | `not-run`, `attempted` or `completed`; failed/ambiguous attempts are not completion                         |
| `comparison_status` | `not-evaluated`, `passed` or `failed`; failed means a mismatch with unchanged expectations                  |
| `cases`             | Separate `expected`, `observed` and per-case `result`; unknown is not fabricated denial                     |
| `cleanup_status`    | Overall status derived from separate child/workspace cleanup evidence                                       |
| `provenance`        | Unauthenticated `in-process-host-record`, not proof that imported booleans were executed                    |

Timeout, cancellation, overflow, nonzero exit, malformed output, stale/refused/unsupported decisions
and unconfirmed cleanup retain null observations and unknown per-case results. Provider calls remain
`0`, authorization `unknown`, and application/restoration `not-run` even for a completed comparison.
A `passed` comparison is not endpoint authorization or general policy correctness. A `failed`
comparison is not itself a production vulnerability finding.

Static reasoning predicted two before mismatches (`non-owner`, `exact-owner-no-normalization`)
and eight after matches; the two separately approved runs above observed those outcomes. Those
bounded observations do not establish correctness outside the fixed cases. Preserve the input
identity including its leading space, and do not change labels to force agreement. The caller still supplies
trusted identity/authentication/scope/ownership facts; this predicate does not authenticate them.

**The executed embedded after is a control observation, not verification of an applied file.**
No application workspace is read, edited, compared or restored. The initial API has no automatic
before-to-after orchestration or combined comparison helper. Final-head CI/reviews/delivery under
new approval and a separately reviewed file-bound apply/check/restore design remain later gates.
Existing observations and consumed approvals cannot stand in for those gates.
