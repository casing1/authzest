<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_CHECK.md">한국어</a>
</p>

# Fixed owned-policy check API

[Documentation index](../README.md) · [Offline case-plan contract](OWNER_CASE_PLAN.md) ·
[Owner review](../guides/CODEX_OWNER_REVIEW.md) · [Development plan](../development/DEVELOPMENT_PLAN.md)

## Scope and current state

[#80](https://github.com/casing1/authzest/issues/80) adds a source-only API under
`authzest.runner.owner_policy_check` for one maintained, owned pure policy. It is unreleased work
in progress, not a generic repository executor, new CLI command or published alpha.3 feature.
Windows and frozen executables explicitly return unsupported/not-run; the worker path is limited
to supported POSIX Python source installations.

On 2026-10-09 KST the maintainer approved only the exact ten expected labels in #77's canonical
envelope SHA-256 `7d6296c07ec57b57b217a6fc03bd6fa48304cfe475c1adaf9dbd1d9b285ea598`:
`owner-read` and `exact-padded-owner` allow, the other eight deny. The separate
[review record](../../tests/fixtures/owner_case_review/maintainer_review.json) records that explicit
chat decision through the assistant, with authentication false. It preserves the original model
authorship and does not approve the separate 28 developer labels or frozen evaluation set.
This labels-only decision grants no policy execution. A later, separately approved exact source
check ran once on the same date; its limited observations are recorded below, separately from the
original draft and offline plans.

## Separate check plan and session

`prepare_owner_policy_check(offline_plan, labels, case_set, draft, request)` creates an
`OwnerPolicyCheckPlan` after revalidating all supplied artifacts and their exact relationships.
It binds the maintained policy bytes, registered worker and recipe identities, selected labels,
case inputs and fixed limits. The #77 offline plan itself remains non-executable.

`OwnerPolicyCheckSession` owns an immutable plan with the same complete context. Its
`decide(choice, plan_id=..., lifetime_seconds=...)` records a separate in-memory choice:
`pending`, `approved`, `declined` or `cancelled`. Approval must name the exact plan ID and has
a lifetime of at most 300 seconds. The choice is caller-recorded, not an authenticated receipt,
proof of human action or consent for another plan. It does not grant source sharing or patch authority.

`await session.run(...)` requires the same current artifact context and revalidates the
request/draft/case set/labels/offline plan, source, worker and recipe before execution.
The session becomes single-use before any await, including failed preconditions. Pending,
declined, cancelled, expired, changed or reused sessions cannot execute. An invalidated decision
cannot be repaired by reusing its old session; prepare a fresh exact plan and obtain a new decision.

Hashes and immutable wrappers detect relevant changes but are not identity attestation, an
approval service or protection against a caller who deliberately controls the Python process.
Concurrent hostile same-user changes and a compromised interpreter/toolchain are not isolated.

## Fixed worker and bounds

Only the registered embedded maintained `policy.py` source is eligible. There is no path, command,
generated Python or shell input. The worker decodes validated case data into the fixed policy's
dataclasses; scope arrays map to frozensets and identifiers are not trimmed or normalized.
Model reasons and reviewer comments remain display-only data and are not sent on worker stdin.
The FastAPI example is not imported or served. HTTP/authentication/database operations, arbitrary
target code, install hooks, provider calls and patch application are outside this API.

| Bound                          | Fixed limit         |
| ------------------------------ | ------------------- |
| Cases / scopes per principal   | 16 / 16             |
| Identifier length              | 128 characters      |
| UTF-8 worker input / output    | 256 KiB / 16 KiB    |
| Child startup and I/O deadline | 5 seconds           |
| Kill/reap cleanup budget       | 1 additional second |
| Decision lifetime              | At most 300 seconds |

The worker uses a fixed minimal environment and temporary working directory, without a shell
or model-selected arguments. These are bounded process controls, not an OS/network sandbox,
container or proof that arbitrary code is safe. The API has no intentional networking path;
it does not claim to isolate the trusted interpreter from the network or other host resources.

## Honest observations and failures

Each case retains its reviewed `expected` value and an `observed` boolean or null. Comparisons
are `passed`, `failed` or `unknown`; aggregate outcomes are `passed`, `failed` or `not-run`.
Missing, malformed, unsupported, cancelled or failed observations remain null/unknown, never
fabricated denials or security passes. A comparison failure is distinct from inability to observe.
Timeout/output/worker/precondition failures do not trigger a retry, fallback worker or model call.

Every result keeps authorization unknown, provider calls zero and patch application not-run.
A pure-policy comparison does not attest actual authentication, FastAPI dependency behavior,
database access or endpoint authorization. A correct policy can legitimately need no change.

## Actual source acceptance — 2026-10-09 KST

After a fresh separate approval for one exact fixed-policy check, the assistant ran that check on
macOS arm64 with Python `3.12.7` from the POSIX source installation. The check plan ID was
`owner-policy-check-387aeb1740773dc8b05a8570685e73e4ab52df489ce41bd1664f29cf6fb71119`;
registered worker SHA-256 was
`7a3ac77d65c7a0fd16ac0dbb2cf64bcff0843737027c6ce4e805acf3bf236496`.
The separate [observed check record](../../tests/fixtures/owner_case_review/observed_check.json)
retains public worker output, limits and current host identities. It is an assistant-recorded
observation, not an authenticated approval receipt or independent execution attestation.

All ten expected/observed comparisons matched: `owner-read` and `exact-padded-owner` allowed,
the other eight denied. Aggregate status was `passed`, child exit `0` and cleanup confirmed.
Provider calls were zero, authorization remained `unknown` and patch application remained
`not-run`. A scripted answer reconstructed the validated control-plane draft around the retained
exact public model-authored cases; it was not a new AI response. No model/provider call or new
source sharing was part of this check, and original model authorship was not changed.

This consumes the separately approved single run. It does not grant future executions or extend
coverage to Windows, frozen binaries, HTTP/authentication/database behavior, arbitrary policy
inputs or the separate 28-label developer matrix. The offline #77 plans and labels-only review
record remain non-executable/not-run. #80 is still in progress until final-head CI and review
gates pass; nothing was published and the broader #35 workflow is not complete.

## Acceptance still required

Offline contracts and mocked-process tests can validate preparation, exact bindings, refusal,
expiry, one-use behavior, budgets and failure records without running the actual policy.
They do not consume the maintainer's labels-only approval as execution consent.
Any further actual observation requires a separately reviewed current check plan and a fresh bounded
execution decision. Final-head CI/reviews, additional supported-platform evidence and later #81/#82
remediation/integrated acceptance remain separate gates. This work publishes no release.
