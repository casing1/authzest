<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/OWNER_POLICY_FILE_REPAIR.md">한국어</a>
</p>

# Owned policy file repair API

[Documentation index](../README.md) · [Development plan](../development/DEVELOPMENT_PLAN.md) ·
[Reviewed design](../development/OWNER_POLICY_FILE_REPAIR_DESIGN.md) ·
[Recommendation](OWNER_POLICY_REPAIR_RECOMMENDATION.md) ·
[Embedded control checks](OWNER_POLICY_REPAIR_CHECK.md)

## Availability and evidence — 2026-10-29 KST

The unreleased source implementation is introduced in
[PR #118](https://github.com/casing1/authzest/pull/118). The maintainer
[approved design `29d8c82` and offline implementation](https://github.com/casing1/authzest/pull/118#issuecomment-6486618422),
not a real file-policy worker run or an operator acceptance applying a repair. Verification in this
slice uses pure-data checks, temporary-file I/O, static worker inspection and fake process responses.
Scripted responses are not observed policy behavior. Exact test results and their commit binding are
recorded separately in the PR; no new worker acceptance is claimed here.

The live file workflow supports **POSIX, non-frozen Python source mode only**, with the required
descriptor-relative filesystem primitives and a trusted local operator. There is no new CLI command,
API endpoint or GUI view. Published alpha.3 does not contain this implementation. #81/#82/#35 remain
open; neither this document nor offline test success grants review activation, merge, execution,
patch acceptance or release authority. Existing #80/#110 controls and their historical observations
remain unchanged and do not establish execution of this new file worker.

## Supported input and API boundaries

Only the registered `synthetic-owner-omission-v1` before/after pair, host-derived single-file diff
and eight reviewed cases are supported. The new API does not accept an existing checkout, policy
path, caller-selected source, AI-generated replacement, executable or case set.

The pure application layer is
[`authzest.codex.owner_policy_file_repair`](../../src/authzest/codex/owner_policy_file_repair.py).
The live coordinator is
[`authzest.runner.owner_policy_file_repair`](../../src/authzest/runner/owner_policy_file_repair.py).

| API boundary                                                                  | Behavior                                                                                                                  |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `prepare_owner_policy_file_repair(request, recommendation)`                   | Revalidates complete registered inputs and builds detached application data; no I/O, provider, execution or approval.     |
| `validate_owner_policy_file_repair(raw)`                                      | Rebuilds and checks application data; never imports authority.                                                            |
| `OwnerPolicyRepairFileSession(application)`                                   | Revalidates the application and creates in-memory session state; does not create files.                                   |
| `create_copy()`                                                               | Explicitly creates one new private temporary copy only for `registered-change`; does not start a check or apply a change. |
| `prepare(stage)` / `decide(stage, choice, plan_id=..., lifetime_seconds=...)` | Previews a stage and records its separate live choice; neither method performs that stage's check or replacement.         |
| `run_check(stage)`, `accept_diff()`, `apply()`, `restore()`                   | Separate one-attempt actions subject to their current plan, decision and prerequisites.                                   |
| `result()` / `validate_owner_policy_file_result(raw)`                         | Export or validate an unauthenticated checkpoint, not a current-file attestation or resumable session.                    |
| `close()`                                                                     | Releases the copy's descriptor without deleting files; rejects closing an active check.                                   |

`no-change` and `unknown` remain normal recommendation outcomes. The application preserves that
status; a copy-creation request for either outcome creates no directory and reports
`recommendation-has-no-change`. The `_parent` injection point is private to temporary-file tests,
not a supported destination option.

The live session additionally limits the complete application to **32 KiB** before any copy creation.
The pure recommendation/application contracts keep their existing envelope rules. This smaller live
budget reserves room for both captured-check plans in a retained checkpoint. Session history is limited
to **256 events**; exhausting that budget or failing checkpoint serialization marks evidence unconfirmed
and blocks subsequent effects. The full JSON byte/depth/node limits also apply.

## Separate plans and decisions

| Stage          | Required checkpoint and effect                                                                            |
| -------------- | --------------------------------------------------------------------------------------------------------- |
| `before-check` | An unchanged fresh copy; separately run the captured before bytes.                                        |
| `diff`         | A valid completed baseline; accept the exact registered diff without applying it.                         |
| `apply`        | Baseline plus accepted diff and another choice; replace tracked before bytes with registered after bytes. |
| `after-check`  | Confirmed applied snapshot and another choice; separately run the captured after bytes.                   |
| `restore`      | Confirmed tracked applied state and another choice; restore registered before content with a new inode.   |

Each plan binds the session, stage, generation, application and registration, current file/root
identity and bytes, and relevant prior completions. Check previews also contain the worker source,
recipe, cases and reviewed expectations. Read the complete preview, not only its ID.

Choices are `pending`, `approved`, `declined` or `cancelled`. Only a live pending decision may change;
an approval is tied to its exact plan and cannot outlive the original plan's **300-second maximum**
window. Finite monotonic time, expiry, changed inputs and file identities are rechecked at effect
boundaries. An action consumes its stage attempt before its first await or effect, including failed
preflight. There is no automatic retry, reopening of a terminal/expired decision or import of an
approval from JSON. These are local workflow gates, not authenticated human signatures.

A complete baseline with case mismatches is still a valid observation and may precede diff acceptance.
An absent or invalid baseline cannot. After-check refusal, cancellation or failure does not itself
forbid a separate restore while the tracked applied state and evidence persistence remain confirmed.

## Captured-source worker and limits

The new worker is separate from the embedded-control worker:

- Check ID: `owned-owner-file-repair-check-v1`.
- Worker SHA-256: `33413d680ac8e00f514d5897aca2289527cfccfd8a1fccdebb179c774377491d`.
- Source: [`_owner_policy_file_worker.py`](../../src/authzest/runner/_owner_policy_file_worker.py).

The host safely reads the owned `policy.py` and sends its captured exact UTF-8 source, never a path.
The worker checks the registered bytes and closed protocol before compiling **that received source**;
it does not substitute the embedded policy. Expected labels and recommendation prose are not worker
input. Accepted output requires exactly eight bound boolean observations, successful exit, confirmed
child and worker-directory cleanup, and a matching post-run file snapshot.

The fixed recipe uses trusted `sys.executable -I -S -c`, pinned worker text, a fresh private worker
directory and a minimal environment. Limits include 32,768 source bytes, 256 KiB input, 16 KiB output,
five seconds for startup/I/O/completion and one additional second for child cleanup. Filesystem calls
have no hard wall-clock cap. This is **not an OS sandbox** and does not enforce CPU, memory or network
isolation. No provider call, network operation, installation, FastAPI or HTTP test is part of this recipe.
Actual execution still requires a separate approval against concrete source and plan identities.

## Retained files, results and recovery

The fresh copy has a `0700` root and `0600` `policy.py`, with retained `before.txt`, `after.txt` and
`record.json` evidence. Reads compare descriptor/name metadata and bytes; symlinks, non-regular or
multi-link files, changed ownership/modes, changed roots and later user edits are rejected. Apply
and restore use staged registered bytes and atomic rename, followed by durability and state checks.
Restore preserves content, not the original inode or arbitrary checkout metadata. Atomic rename is
not compare-and-swap against a concurrent same-user writer; avoid concurrent modification.

Results keep application, execution, expectation comparison, restoration, file binding, evidence
persistence and consumed decisions separate. Missing or unconfirmed observations never become
invented denials or passing comparisons. `authorization_status` remains `unknown`, this stage's
`provider_calls` is `0`, and provenance is unauthenticated. A recorded pass concerns captured bytes
at a checkpoint, not endpoint enforcement or perpetual correctness of a file.

Copies are retained on success, refusal, cancellation and failure. Initialization failures preserve a
confirmed created path when available; they do not prove that `record.json` exists. Detected user edits
block further effects instead of being overwritten. A replacement whose committed state cannot be
confirmed is reported as `state-unconfirmed`; further checks and programmatic restore are blocked.
Evidence-write failure also blocks subsequent effects, even if the policy snapshot was confirmed.
Inspect the retained path manually in these cases. Interruption checkpoints may be attached to the
original exception; an uncertain write is not reported as safely rolled back.

File replacement and evidence recording are not one transaction. There is no automatic rollback,
deletion, process restart/resume or imported-receipt recovery. Validation of a saved JSON checkpoint
checks data consistency only and cannot reopen its path, authenticate its origin or authorize work.
The next acceptance slice requires separate before-check, exact-diff, apply, after-check and restore
decisions. Readable CLI integration remains separate under #82.
