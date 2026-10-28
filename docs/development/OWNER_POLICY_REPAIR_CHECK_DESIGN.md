<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/OWNER_POLICY_REPAIR_CHECK_DESIGN.md">한국어</a>
</p>

# Registered repair-policy checks — design for review

[Documentation index](../README.md) · [Development plan](DEVELOPMENT_PLAN.md) ·
[Registered pair](../reference/OWNER_POLICY_REPAIR_PAIR.md) ·
[Existing #80 check](../reference/OWNER_POLICY_CHECK.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81)

## Status and requested decision

Historical design text below is preserved. The maintainer subsequently
[approved this design and offline implementation](https://github.com/casing1/authzest/pull/110#issuecomment-6459020000).
See the [implementation reference](../reference/OWNER_POLICY_REPAIR_CHECK.md) for PR #110's source API
and original offline/mock evidence at `510377c`. That design decision did not approve actual worker
execution. A subsequent [separate before-only approval](https://github.com/casing1/authzest/pull/110#issuecomment-6460245210)
was consumed by the 2026-10-28 11:49:55 KST before run documented in the reference: expected two
mismatches, execution completed, exit `0`, cleanup confirmed. A later
[separately approved after-only run](https://github.com/casing1/authzest/pull/110#issuecomment-6460474112)
at documentation-only commit `7f9c5ce` on 2026-10-28 13:11:38 KST matched eight cases with unchanged
runtime code, exit `0` and confirmed cleanup. Both run approvals are consumed. Final-head
review/delivery needs new approval; file-bound application/verification/restoration remains a separate
design. The original proposal/checklist below is preserved, not a current execution receipt.

**Proposed only — 2026-10-28 KST.** Baseline main is
`cc644a16fb67d1a89538c5b4b27549ee1f136604`. This document adds no worker, execution API, CLI,
policy observation, application or restoration capability. It does not change #80 or register new
policy bytes, cases or labels. A passing documentation check is not design approval.

The [separate real recommendation attempt](https://github.com/casing1/authzest/issues/81#issuecomment-6458726176)
selected the registered pair; its sharing approval is consumed and grants no execution authority.
The [previous pair design](OWNER_POLICY_REPAIR_PAIR_DESIGN.md#subsequent-implementation-boundaries)
requires a separately reviewed fixed check recipe before extending execution capability.

The requested maintainer decision is whether to implement **this dedicated, single-candidate,
source-only fixed check design**, initially with offline and mocked-process tests. Design approval
does not approve a real policy run, source sharing, automatic PR review, merge, patch or release.
A separately merged design PR is not required; review of the exact design is required before worker
implementation. Any subsequent actual worker test/acceptance needs its own bounded decision against
the implemented source/worker identities. #81/#35 remain incomplete.

## Exact existing input, no new scenario

Use the unchanged registered `synthetic-owner-omission-v1` pair and eight reviewed expected labels
from the [pair API](../reference/OWNER_POLICY_REPAIR_PAIR.md) and its
[registration source](../../src/authzest/codex/owner_policy_repair_pair.py).
The before policy is intentionally incorrect test-only text, not a production finding. The maintained
correct policy remains the after control. `policy.py` is a display label, not a caller path.

| Binding                       | SHA-256                                                            |
| ----------------------------- | ------------------------------------------------------------------ |
| before source                 | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| after source                  | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |
| eight cases with expectations | `96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3` |
| complete pair content         | `2cbbc004b46ac2bc65b98c3e3b4b3e1e5919dd3d1b35920871372432c23203fb` |
| recorded label review         | `3540dd3578ee838b1bfb34f3c02019286716b47664ec942da46e8dac25d4b7e8` |

Expected labels are one allow (`owner-control`) and seven denials. Static reasoning predicts two
before mismatches, `non-owner` and `exact-owner-no-normalization`, and eight after matches.
These remain **predictions, not observations**. Preserve identifiers verbatim, including the leading
space in the last case. Input scope lists map only to the fixed dataclass's `frozenset`.
Trusted identity, authentication, scopes and ownership still come from the caller; this synthetic
predicate does not authenticate them or establish HTTP/database/endpoint enforcement.

## Proposed module and API boundary

All names below are proposed, not available commands or callable implementation.

| Component                                    | Responsibility                                                                                              |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Existing `codex/owner_policy_repair_pair.py` | Unchanged sole registration authority and exact pair/review validation                                      |
| New `runner/owner_policy_repair_check.py`    | Complete offline plan, one-use session, terminal expiring decision, bounded transport and output validation |
| New `runner/_owner_policy_repair_worker.py`  | Dedicated trusted stdlib worker embedding only the two registered sources and exact eight input cases       |
| Later application coordinator                | Separate future design for file-bound apply/check/restore; not part of this slice                           |

The initial public API is source-only: `prepare_owner_policy_repair_check(candidate)` and
`OwnerPolicyRepairCheckSession(candidate)`. Candidate is exactly `before` or `after`, with no
implicit default. There is no `both` selector, automatic before-to-after run, path, arbitrary source,
case override, executable callback, command, model response or imported approval parameter.
Preparation and serialization neither start a child nor compile/evaluate a policy.

Keep `owner_policy_check.py`, `_owner_policy_worker.py`, their hashes, recipe and #80 historical
records unchanged. Do not monkeypatch their source, broaden their allowlist, or make the new worker
a configurable generic executor. Only the new checker may select the exact registered before source.
No CLI or frozen/Windows support is added in this initial slice.

## Complete plan and identities

One immutable, revalidated plan binds one candidate to the complete registered pair and review
record, exact selected source text/hash, all eight ordered cases/expected labels and their hashes.
It also binds the dedicated worker source/hash, versioned coordinator recipe, mapping, wire protocol,
comparison rules, fixed environment, transport limits and cleanup policy.

Proposed identifiers are `owned-owner-repair-check-v1` and recipe version `1.0`, in a namespace
separate from #80. Exact worker bytes/hash and implementation revision are **not yet available**;
implementation review must record them before any execution request. Hash the actual embedded
worker bytes and revalidate them against the implementation's pinned digest, not a caller-supplied
digest. Recipe/version and worker identity are change detectors, not independent code attestation.

The plan ID hashes the complete versioned bindings, excluding its own derived ID. Add that ID to
the worker input afterward to avoid a self-referential digest. Rebuild the full current plan at
execution time and compare it byte-for-byte with the session's prepared plan. A changed candidate,
pair, labels, review record, worker or recipe requires a new session and decision.

## Separate one-attempt decisions

A live session, not deserialized JSON, owns the execution decision. A fresh full-plan preview must
make selected source, cases, recipe and bounds inspectable. The source API accepts
`decide(choice, plan_id=..., lifetime_seconds=...)`; choices are pending, approved, declined or
cancelled. Lifetime must be a finite integer/float (not a boolean) with
`0 < lifetime_seconds <= 300`. Monotonic readings and the computed expiry must be finite,
nonnegative numbers; clock rollback is invalid. An invalid first decision or decision-time reading
irreversibly invalidates the session.

Only an unexpired pending decision may be replaced. Approved/declined/cancelled decisions are
terminal. An invalid, expired or terminal replacement irreversibly invalidates that session.
The session consumes its single attempt synchronously before the first await, even when preflight
fails. Concurrent calls, replay, expiration, clock rollback and changed plans cannot launch a child.
No retry, fallback, automatic restoration or approval inferred from a recommendation is allowed.

A before decision authorizes only before, never after. After needs a separate session and fresh
current decision. The existing recorded label review is not an authenticated execution receipt.
Directly controlling the Python process or internal worker is outside this in-process consent boundary.

## Worker input and process recipe

The new worker embeds the registered source pair and exact input-only cases. Stdin is closed JSON:
schema/check/plan identities, candidate, selected source and worker hashes, input-case hash and
ordered case rows containing only case ID, input identity, principal and report data. Expected
labels, model explanations, reviewer prose, paths and source text are not worker input.
The worker must reject any case/context alteration, not just a syntactically valid alternative.

It validates the complete input before compiling exactly one embedded policy candidate in a fixed
internal module. The caller selects only one of the two registered candidates, never arbitrary
source bytes, imports, filenames or expressions.
Stdout repeats the request identities and exactly eight ordered case-ID/input-hash/boolean rows.
The coordinator validates both exact bindings and strict booleans; missing, extra, duplicate,
reordered, coerced, non-finite, malformed or partial output cannot become an observation.

| Fixed control              | Proposed value                                                                                      |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| Platform                   | POSIX, non-frozen Python source installation                                                        |
| Launch                     | Trusted interpreter, `-I -S -c`, fixed embedded worker, no shell                                    |
| Cases                      | Exactly the eight registered cases; no caller extension                                             |
| Defensive parser limits    | 256 KiB input, 16 KiB output, depth 32, 8,192 nodes                                                 |
| Case field limits          | At most 16 scopes and 128 characters per identifier/scope; exact registered equality still required |
| Startup + I/O + completion | 5 seconds total per attempt                                                                         |
| Kill/reap cleanup          | 1 additional second                                                                                 |
| Decision lifetime          | At most 300 seconds                                                                                 |
| Environment                | Fixed minimal environment; no inherited HOME/account/provider/proxy/Python injection                |
| Working directory          | Fresh private temporary directory; no repository copy/import                                        |
| Process group              | New session; cleanup targets only this invocation's process group                                   |

No intentional network/provider/FastAPI/HTTP/database/install-hook path exists. These are bounded
trusted-process controls, **not an OS/network sandbox or CPU/memory hard cap**. A trusted interpreter,
toolchain and stable registered code, without hostile concurrent same-user modification, are assumptions.
No arbitrary repository or AI-generated code is made safe by this design.

## Result, cleanup and comparison semantics

Keep expected labels and actual booleans separate. For a fully validated, successfully cleaned-up
run, each case compares its observed boolean with its unchanged expected label. Aggregate
`passed` means eight expectation matches; `failed` means at least one mismatch, not worker failure.
The intentionally incorrect before candidate is predicted to finish successfully while producing
a failed comparison. Never change labels to make it pass.

Failure/unsupported/refusal outcomes retain null observations and unknown comparisons, not fabricated
denials. Distinguish execution `not-run`, `attempted` and `completed` from comparison
`not-evaluated`, `passed` and `failed`. Record child and temporary-workspace cleanup separately.
A known launch failure with no child makes child cleanup `not-needed`; ambiguous in-flight launch
or failed reaping makes it `unconfirmed`. Any temporary-directory cleanup failure makes overall
cleanup `unconfirmed`, even if no child launched. Overall `not-needed` is valid only when neither
resource needed cleanup; otherwise confirmation requires both relevant cleanup steps to succeed.
The extra one-second budget bounds child kill/reap only. Directory creation/removal and other host
filesystem operations have no hard wall-clock guarantee; this is not a hard six-second total cap.
Confirmed cleanup includes process-group termination/reaping and temporary-directory cleanup. Timeout,
cancellation, output overflow, nonzero exit, identity mismatch or unconfirmed cleanup never publish
successful observations. Preserve the original cancellation while completing bounded cleanup; raw
stderr/exception text must not become result data.

Every result binds the exact plan, selected source, cases, worker/recipe, attempt/cleanup diagnostics
and per-case expectations/observations. It retains provider calls zero, authorization unknown,
application and restoration not-run. A comparison failure is not an endpoint vulnerability finding.

An optional pure comparison helper may later join separately validated before and after results
only when their pair, case/label, worker and recipe bindings match. Candidate/source/plan IDs differ
as expected and remain explicit. Require before then after in the supplied roles; reject swapped,
stale, partial, different-context or fabricated-shape data. Imported records are caller-supplied,
not authenticated proof of execution. The helper never launches a missing check or applies a patch.

**Running embedded after is a control observation, not verification of an applied file.** Neither
run reads an application workspace or establishes that a patch was applied. New-copy application
requires its own file-identity-bound design and separate diff/apply/check/restore decisions.
Do not relabel these observations as applied-file verification later.

## Implementation and verification gates

- [ ] Maintainer reviews this exact recipe, candidate separation and non-sandbox limitations.
- [ ] Implement the new modules and full closed plan/result contracts; record exact implementation/worker identities.
- [ ] Guard offline plan/serialization tests against filesystem, subprocess, provider and policy evaluation.
- [ ] Cover all decision transitions, stale/reused/concurrent calls and Windows/frozen refusal with mocks.
- [ ] Cover malformed/oversized/partial/changed worker data, launch failure, timeout, repeated cancellation and cleanup uncertainty.
- [ ] Verify #80 source/worker identities, historical inventory and existing public behavior remain unchanged.
- [ ] Complete paired English/Korean implementation docs and exact-head CI/review gates.
- [ ] Obtain fresh bounded approval for actual worker regression/acceptance using the finalized plan(s); preserve observations separately from predictions.
- [ ] Design new-copy application and file-bound verification separately; leave #81/#35/#82 and release gates open.

This design contains no runnable policy command. Do not execute its descriptive examples or infer
runtime approval from tests, a draft PR, hashes or this checklist. Automatic/manual paid reviews,
merge and publication remain separate workflow decisions.
