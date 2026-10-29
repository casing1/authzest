<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/OWNER_POLICY_FILE_REPAIR_DESIGN.md">한국어</a>
</p>

# Owned policy file application, checks and restoration — design for review

[Documentation index](../README.md) · [Development plan](DEVELOPMENT_PLAN.md) ·
[Issue #81](https://github.com/casing1/authzest/issues/81) ·
[Repair recommendation](../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md) ·
[Embedded control checks](../reference/OWNER_POLICY_REPAIR_CHECK.md)

## Status and decision

**Proposed — 2026-10-29 KST**, against main `80110e02ec8b3392e1841a42f8761179219285cd`.
This document specifies the next #81 implementation: apply the registered repair to one new owned
copy, check bytes read from that copy, and offer a separate restoration choice. It adds no executable
API, worker, CLI or observation. Existing contracts, historical observations and consumed approvals
remain unchanged. #81/#82/#35 stay open; the separate #83 prerelease conditions still apply.

Review this exact design before implementing its new write/execution boundary, as required by
[#81's design gate](https://github.com/casing1/authzest/issues/81). The requested decision covers
implementation with offline, temporary-file and mocked-process tests. A real policy-worker run,
product model call, operator acceptance applying a patch, review activation and publication each
remain separate operational decisions. Passing documentation checks does not provide that consent.

## Existing gap and smallest supported input

The current recommendation validator accepts `registered-change` only for the registered before
candidate and pair; `no-change` and `unknown` remain normal outcomes. Its preview is output data.
The [current checker](../../src/authzest/runner/owner_policy_repair_check.py) takes a candidate name;
its [worker](../../src/authzest/runner/_owner_policy_repair_worker.py) compiles embedded constants.
That after control cannot establish what an applied file contains or which bytes were executed.

Use only the unchanged `synthetic-owner-omission-v1` pair, host-derived one-file diff and eight reviewed
cases from the [pair registry](../reference/OWNER_POLICY_REPAIR_PAIR.md). Neither model prose nor a
caller can choose a source file, replacement, command, executable, case or expected label.

- Before SHA-256: `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950`.
- After SHA-256: `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04`.
- Cases SHA-256: `96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3`.

Rebuild and validate the complete registration, review binding, request and recommendation rather
than trusting these copied hashes, a constructed dataclass or a preview JSON object. Valid data does
not authenticate provider origin. Preserve caller-supplied provenance and any separate transport
record; importing a historical result never restores a live session or an approval.

For `no-change` or `unknown`, return the validated recommendation without creating a copy or write plan.
For `registered-change`, prepare a pure application preview, then create the copy only through an
explicit local API operation. No provider is called by this new file workflow.

## Private copy and file identity

The first implementation supports POSIX, non-frozen Python source mode and a trusted local operator.
It creates a fresh system-temporary directory, mode `0700`, and a fixed `policy.py`, mode `0600`, from
the registered before bytes. Retain fixed `before.txt`, `after.txt` and `record.json` evidence files.
No existing path, destination parent, checkout, directory tree or resume file is accepted by the
production API. Tests may inject a pytest-owned temporary parent through a private seam.

Use a dedicated owner-policy workspace/coordinator. Follow the bounded I/O patterns in
[`FixtureWorkspace`](../../src/authzest/runner/_fixture_workspace.py), without extending that legacy
fixture's filename or verification allowlist. Hold a directory descriptor; use relative operations,
`O_NOFOLLOW`/`O_NONBLOCK`, exclusive creation and ordinary single-link files owned by the current user.
Check directory identity, ownership and mode on each operation. A read is at most 32,768 bytes and
must round-trip exact UTF-8 without newline normalization. Compare before/after descriptor and
filename metadata: device, inode, mode, owner/group, link count, size, mtime and ctime, plus the bytes.
The opened descriptor and current filename must identify the same file. Reject unsupported primitives.

Apply compares the current file with the original tracked snapshot, stages the exact registered
after bytes, rechecks the state and decision immediately before replacement, then uses an atomic
rename and confirms fsync and the new snapshot. Restore similarly requires the tracked applied
snapshot and writes the original registered before bytes. It restores content with a new inode;
it does not promise original filesystem metadata or rollback of an existing checkout.

Keep the copy and its evidence after completion, refusal, cancellation or failure. Closing the session
releases descriptors; it does not delete the copy. Initialization failures report the confirmed path
and failure stage without claiming a record exists or that writes were rolled back.
Atomic rename is not compare-and-swap against a hostile concurrent same-user writer. The operator
must avoid concurrent modification; this is not an OS sandbox or a multi-file transaction.

## Plans and separate live decisions

Proposed API names describe boundaries, not callable interfaces available today:

- A pure application preparer revalidates the request/recommendation and builds the registered diff.
- `OwnerPolicyRepairFileSession` initially performs no I/O; explicit copy creation starts a live session.
- Stage-specific preview/decision/action methods handle before-check, diff acceptance, apply,
  after-check and restore. No method automatically advances to the next effect.
- A result validator checks data consistency only; it cannot reopen a path or authorize an action.

Every stage plan binds its kind/schema/recipe, action, fresh session nonce, generation, request and
recommendation IDs, pair/content/review identities, before/after and diff hashes, fixed filename,
workspace identity, exact current file snapshot and relevant prior completion IDs. The complete
preview shows the source/diff, scope, cases, expected labels, worker bytes and limits relevant to that
action. Hashes alone are insufficient for an informed decision. No model/reviewer prose enters child input.

Diff acceptance records agreement with the exact host-derived change; it does not apply it. Applying
requires another choice bound to that acceptance and current before snapshot. Copy creation, source
sharing and case-label provenance cannot substitute for either choice. Each check and restore also
has its own plan and choice.

Choices are `pending`, `approved`, `declined` or `cancelled`, bound to the current stage and exact plan.
Only a live pending choice may become terminal. Use a finite monotonic clock, maximum 300-second
lifetime, and reject clock reversal, stale IDs, changed content, wrong stage/session and imported
decisions. Consume each attempt before its first await or effect, including failed preflight.
There is one attempt per stage, no automatic retry and no reopening a declined/cancelled/expired stage.
Fresh approvals cannot authorize detected user edits in the same copy; preserve it for inspection.
These are local workflow gates, not authenticated human signatures or protection from the caller itself.

## File checks execute the captured bytes

Introduce a separate file-check kind, protocol, recipe and pinned worker identity. Keep #80, #110's
embedded worker/results and the existing Codex fixture workflow unchanged. Do not widen an existing
general execution helper to accept arbitrary source, paths, commands or environments.

1. Prepare a plan from a safe read of this live session's `policy.py`: the exact immutable UTF-8 byte
   snapshot, its identity/length/hash, candidate, registered pair, eight inputs/expected labels,
   worker bytes/hash, mapping and transport recipe. Before requires the tracked before snapshot;
   after requires the confirmed applied snapshot.
2. After fresh check approval, revalidate the complete registration/plan and reread the file immediately
   before launch. The bytes and full tracked identity must match the preview. The worker receives
   the captured source text and input cases, never a filesystem path or expected labels.
3. The new strict worker validates closed fields, duplicate-key/depth/node/size limits, exact candidate
   bytes and hash against its fixed registration, and all eight registered inputs. Only then does it
   compile **the received captured source**, not a substitute embedded policy. It maps reviewed data
   to the fixed nullable dataclasses and returns exactly eight boolean observations with bindings.
4. The host checks complete output, identities, exit and cleanup, and rereads the file after completion.
   Publish accepted observations only if the file still matches the planned snapshot and both child
   and temporary-worker-directory cleanup are confirmed. A changed file or incomplete response keeps
   comparison inconclusive; a raw worker diagnostic is not an accepted file-check result.

Launch a trusted `sys.executable -I -S -c` with pinned worker text, an empty private worker cwd and
the existing minimal-environment pattern. Proposed limits retain 256 KiB input, 16 KiB output, depth 32,
8,192 nodes, eight cases, 128-character identifiers, 16 scopes, one attempt, five seconds for process
startup/I/O/completion and one additional second for child cleanup. The retained policy copy is
separate from the disposable worker directory. No network, installation, model, FastAPI or HTTP operation
is part of this recipe. These limits do not hard-cap filesystem calls, CPU, memory or OS/network access.
The actual worker hash must be pinned from the implemented source before any operational run approval.

## State, comparison and recovery

The normal file states are `ready-before`, `applied-after` and `restored-before`. Decisions, check
outcomes, cleanup and evidence persistence are separate fields, not one global success flag.

| Stage           | Prerequisite and effect                                     | Refusal or failure                                                                                   |
| --------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Before check    | Fresh copy; one approved captured-before run                | Keep copy; no apply after an absent or invalid baseline                                              |
| Diff acceptance | Valid completed baseline; approve the exact diff only       | End mutation path with copy retained                                                                 |
| Apply           | Separate choice; unchanged tracked before snapshot          | Preserve current file; distinguish pre-write failure from uncertain committed write                  |
| After check     | Confirmed applied snapshot; one separate choice/run         | Keep apply history; allow a separately approved safe restore while evidence persistence is confirmed |
| Restore         | Separate choice; exact tracked after snapshot still present | Keep copy/user edits; never overwrite a changed or unconfirmed state                                 |

A complete baseline may legitimately report mismatches: the intentionally incorrect before policy is
expected to mismatch two labels. A valid mismatch observation is not a transport failure. The registered
after is expected to match eight labels; those are expectations for the future file run, not new evidence.
The earlier embedded-control observations remain separate historical records.

Compare only accepted before/after observations from the same session, with the same cases, reviewed
expectations, pair, diff and worker/mapping recipe, and the corresponding tracked before/applied states.
Retain per-case expected/observed values and changes. Missing, refused, stale or unconfirmed stages,
and execution/protocol/cleanup failures, yield `not-evaluated` or `inconclusive`, never invented denials
or a passing comparison. Accepted case mismatches remain failed expectation comparisons and may
participate in the before/after comparison; they are not execution failures.
An after-check refusal/failure must not disable restore when the tracked applied state and evidence
persistence remain confirmed. A session-level evidence failure takes precedence over that recovery path.

Record application, execution, comparison, restoration, file binding, decision consumption and evidence
persistence separately. Keep `authorization_status="unknown"`, current-stage `provider_calls=0` and
unauthenticated provenance. A passed check describes the captured owned-file bytes at the recorded
checkpoint, not endpoint enforcement or perpetual current-file correctness.

File replacement and evidence recording are not one transaction. A failure after rename must report
a committed/unconfirmed outcome and the retained location, never `not-applied` or silent success.
Without a confirmed tracked applied snapshot, block further checks and programmatic restoration,
including a freshly approved restore; retain the copy for manual inspection with no resume or imported
receipt. With that snapshot and confirmed evidence persistence, a failed check may still lead to a fresh
restore decision. Evidence-write failure overrides that recovery path: block subsequent effects and
report the persistence failure. No automatic
rollback, retry, process restart/resume or deletion is provided. Detected edits, inode/link/permission/root
changes and missing files invalidate affected decisions and are preserved without overwrite.

## Implementation and acceptance slices

1. Implement new data validation, live decisions and private-copy apply/restore with temporary-file
   tests. Add the captured-file plan and strict worker protocol; test source data and AST guards without
   compiling the policy. Keep provider and real subprocess entry points patched to fail in offline tests.
2. Add bounded transport and coordinator tests using fake subprocesses. Cover exact received-source
   compilation structurally; malformed/partial output, cancellation, cleanup uncertainty, expiry/replay,
   different sessions/stages, identical-byte inode replacement, mid-read/staging edits, symlink/hardlink,
   absent files, permission/root replacement, commit/fsync/journal failures and after-check refusal with
   safe restore. Retain existing #80/#110 and fixture regressions without weakening their allowlists.
3. After source review, request bounded operational acceptance against concrete source/worker hashes
   and new live plans. Before and after worker runs, exact-diff acceptance, apply and restore are distinct
   decisions. No previous run or review approval is reusable. Record new evidence without rewriting old records.
4. Connect a readable CLI with complete previews, text/JSON stream rules and refusal/recovery scenarios
   under #82. A later integrated acceptance is required before completing #81/#82/#35. GUI, arbitrary
   repository/AI-generated code execution, existing-checkout edits, Windows/frozen execution and broader
   remediation remain outside this first file workflow. Release work remains under #83.
