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

The unreleased source implementation was delivered in
[PR #118](https://github.com/casing1/authzest/pull/118). The maintainer
[approved design `29d8c82` and offline implementation](https://github.com/casing1/authzest/pull/118#issuecomment-6486618422),
not a real file-policy worker run or an operator acceptance applying a repair. That initial verification
used pure-data checks, temporary-file I/O, static worker inspection and fake process responses.
Scripted responses are not observed policy behavior; exact offline test results and their commit
binding remain recorded in the PR. The later, separately approved
[file-workflow acceptance](#file-workflow-acceptance--2026-10-29-kst) below records actual captured-file
observations without changing the scope of that earlier approval.

The live file workflow supports **POSIX, non-frozen Python source mode only**, with the required
descriptor-relative filesystem primitives and a trusted local operator. There is no new CLI command,
API endpoint or GUI view. Published alpha.3 does not contain this implementation. #81/#82/#35 remain
open; neither this document nor offline test success grants review activation, merge, execution,
patch acceptance or release authority. Existing #80/#110 controls and their historical observations
remain unchanged and do not establish execution of this new file worker.

## File-workflow acceptance — 2026-10-29 KST

One fresh owned-copy workflow completed using source commit
`fb90c46db1c6afa858451d434ccff1ebf8184fcd` and Python **3.12.7** on POSIX macOS. A previously
captured real `registered-change` recommendation was revalidated against the current contracts.
This slice made **zero new provider calls**; it is not a new model acceptance or an installed CLI/GUI
demonstration. The source repository was not changed. The
[public tracking summary](https://github.com/casing1/authzest/issues/81#issuecomment-6491128132)
records the bounded outcome, not an authenticated execution attestation.

Before this session, an earlier preparation-only before plan expired without a worker attempt or
check result. Its session was closed and its private copy retained. The expired plan was not extended
or executed, and a later reply did not revive it. Fresh preparation approval created this new session
and copy; the earlier preparation was not an automatic retry or a reusable execution permission.

The user separately approved each effect below. The assistant reviewed each complete live plan and
entered its exact decision within the plan's validity window. Each stage completed once and consumed
its own one-attempt approval; none permits replay, a retry or a future run.

| Stage          | Recorded effect                                                         |
| -------------- | ----------------------------------------------------------------------- |
| `before-check` | Captured actual before bytes; 6 matches and 2 expected mismatches.      |
| `diff`         | Accepted the exact host-derived registered diff; no file replacement.   |
| `apply`        | Replaced only the owned copy's `policy.py` with registered after bytes. |
| `after-check`  | Captured the actual applied file; 8 matches and no mismatches.          |
| `restore`      | Restored registered before bytes with a new inode; retained evidence.   |

The exact source, diff and worker identities were:

| Binding                | SHA-256                                                            |
| ---------------------- | ------------------------------------------------------------------ |
| Before source          | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| After source           | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |
| Registered host diff   | `0358127d2373c7a729c0b656c1c9cbcb698dc5f04073a917f848280d0c8be75d` |
| Captured-source worker | `33413d680ac8e00f514d5897aca2289527cfccfd8a1fccdebb179c774377491d` |

The eight registered cases kept their reviewed expectations and order:

| Case                           | Expected | Before observation | Applied-after observation |
| ------------------------------ | -------- | ------------------ | ------------------------- |
| `owner-control`                | allow    | `true`             | `true`                    |
| `non-owner`                    | deny     | `true`             | `false`                   |
| `missing-read-scope`           | deny     | `false`            | `false`                   |
| `unauthenticated-owner`        | deny     | `false`            | `false`                   |
| `missing-principal`            | deny     | `false`            | `false`                   |
| `missing-report`               | deny     | `false`            | `false`                   |
| `wildcard-is-not-read`         | deny     | `false`            | `false`                   |
| `exact-owner-no-normalization` | deny     | `true`             | `false`                   |

Both checks completed with worker exit **0**, confirmed child and worker-directory cleanup, and
confirmed evidence persistence and file binding. The before comparison failed because of the two
expected case mismatches, not an infrastructure failure. Only `non-owner` and
`exact-owner-no-normalization` changed from `true` to `false`; the after comparison passed.

The final checkpoint is **`restored-before`, generation 3**, with completed application and restoration
and retained historical before/after observations. Its historical `comparison_status=passed` describes
the earlier applied-after check, **not a passing check of the now-restored before file**. No check was
rerun after restoration. The private files and evidence were retained; session and plan identifiers,
local artifact digests, private paths, raw records and the raw model capture are not published here.

After that checkpoint, `close()` released the descriptor and marked the in-memory session closed;
the host exited **0**. `close()` does not rewrite `record.json`, so its last durable `closed` field
remains `false`. This is not an open or resumable session. The record digest identifies retained bytes
for integrity comparison only; it is not execution proof, a signature or authorization. Receipts and
provenance remain unauthenticated, and `authorization_status` remains `unknown`.

This is source-API acceptance for one registered pure-policy pair and eight cases, not arbitrary
repository execution, HTTP/FastAPI or authentication-provider enforcement, an OS sandbox, or a
cross-platform/native-binary claim. No network/provider call, installation or release occurred; these
completed approvals grant no continuing authority. Readable CLI integration under #82 and the wider
#81/#35/release gates remain separate; published alpha.3 is unchanged.

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
Any future acceptance requires fresh separate before-check, exact-diff, apply, after-check and restore
decisions; the recorded workflow above grants no continuing authority. Readable CLI integration remains
separate under #82.
