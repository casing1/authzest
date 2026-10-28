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
not an actual worker run. Verification in this slice uses offline contracts, static worker inspection
and memory-only scripted process responses. **Neither new worker candidate has been executed or
accepted as a real observation.** Scripted booleans in tests are not observed policy behavior.

There is no new CLI command, API endpoint or dashboard view. Published alpha.3 does not include this
feature. The existing #80 coordinator, worker, policy registration and historical observations remain
unchanged. This implementation does not complete #81/#35/#82, activate paid reviews, merge or release.

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

Static reasoning predicts two before mismatches (`non-owner`, `exact-owner-no-normalization`) and
eight after matches; these are **predictions only, not execution results**. Preserve the input identity
including its leading space, and do not change labels to force agreement. The caller still supplies
trusted identity/authentication/scope/ownership facts; this predicate does not authenticate them.

**Executing embedded after would be a control observation, not verification of an applied file.**
No application workspace is read, edited, compared or restored. The initial API has no automatic
before-to-after orchestration or combined comparison helper. Fresh separately bounded candidate
acceptance, final-head CI/reviews/delivery, and a separately designed file-bound apply/check/restore
workflow remain later gates. Existing observations and approvals cannot stand in for those gates.
