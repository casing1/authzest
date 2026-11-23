# External private file sessions (S2)

[Documentation](../README.md) · English · [한국어](../i18n/ko/reference/REPOSITORY_FILE_SESSION.md)

This source Python API implements the private **file boundary** from
[#204](https://github.com/casing1/authzest/issues/204) and the
[external file-workflow design](../development/REPOSITORY_FILE_WORKFLOW.md). It has no model client,
target/test execution, CLI/GUI operator or original-project write. `repo-suggest` still returns
proposal-only results and does not call this API. Packaged workers and the existing GUI are unchanged.

## Live input and ownership

`capture_repository_origin(root, source, policy, contexts=())` returns a `RepositoryOrigin` holding
the initially captured root/parent/file descriptors and exact selected bytes. `snapshot` is the
content-only `RepositoryInput`; it never proves freshness on its own. `verify(selection)` checks
the complete initial selection, exact bytes and initial file identities against held and named
descriptors. It refuses same-byte inode replacement, edits, metadata/link changes and path replacement.
Unselected files are not discovered, copied or executed; unrelated directory-content changes are allowed.

Construct `RepositoryFileSession(origin, request, response, copy_plan)` only with a currently validated
request/response, matching S1 plan and the exact live origin. Successful construction transfers
descriptor ownership to the session, without creating files. The same origin cannot transfer to a
second session. Failed construction neither acquires nor closes the origin; its prior owner remains
responsible. To claim continuity across generation, a future operator must capture this origin
**before** sharing/generation. Capturing a new origin afterward establishes only a new baseline;
the current content-only `repo-suggest` capture cannot reconstruct earlier inode continuity.

The caller and synchronous clock are trusted Python coordination. Input JSON, hashes and typed
phrases do not authenticate a human, a provider or a fresh model invocation. The future operator must
bind those separate observations itself. Objects cannot be copied, pickled, reopened by path, or
rehydrated from saved request/plan/result/journal JSON. Operations are bound to the creating process
and session thread; private fields are not a defense against arbitrary code in that process.

## Current plans and exact transitions

The supported API sequence is:

```text
capture_repository_origin(...) → build_repository_request(origin.snapshot, model)
validate response → prepare_repository_copy_plan(request, response)
RepositoryFileSession(origin, request, response, copy_plan)
prepare(step) → review complete plan → decide(the_same_plan, exact_confirmation)
perform(the_same_decision)

copy → accept-diff → apply → restore → close
```

`prepare(step)` returns a frozen `RepositoryFilePlan`. It includes full selected input, validated
proposal and exact host-derived diffs, S1 material identities, local origin/private paths and current
private file identities. Treat this data as private source material. The complete local review is
bounded to 256 KiB; oversized reviews fail before allocation. Existing selection/material/journal
bounds still apply. Atomic replacement needs one extra staging file of at most 64 KiB beyond the
retained material and journal; failed staging is preserved. This is a new file-session contract,
not an accepted GUI import format.

`decide(plan, confirmation)` returns a `RepositoryFileDecision` bound to the exact current plan object,
session, revision and original expiry. A reconstructed equal object is refused. Each step is single
use and lasts at most 300 seconds on its original monotonic clock. Repeated preparation returns the
same plan without resetting its deadline. Expiry, replay, wrong stage, process/thread mismatch and
reentrant operations cannot create permission. There is no saved-record resume or automatic approval.

- **copy:** reverify the original selection/initial identities, then check expiry immediately before
  allocating one new private root. Create only the S1 selected-source layout with `0700` directories,
  `0600` single-link regular files and exclusive no-follow operations. Record initialization as pending
  until the private tree and completion journal have read back exactly.
- **accept-diff:** separately accept the exact current change and durably record that local decision.
  No source replacement occurs.
- **apply:** require the current private before source and immutable evidence; persist pending intent,
  stage exact after bytes and check the current decision immediately before source replacement.
  Read back the exact new source, then persist completion.
- **restore:** require the current private source to equal accepted after and the before snapshot to
  equal captured before; replace only that source with before. Keep test, contexts, snapshots and
  history. Empty before source is supported. Changes to the original after copying do not block this
  independent private recovery and are never overwritten.

Every journal replacement has its own final check within the current step's original deadline.
The live file handle compares the mutable journal with its last verified self-committed bytes and
identity; it updates this baseline only after durable readback. It never trusts saved JSON for state.
Original input freshness is checked only before copy, not while recovering an independent copy.

## Failure and observation limits

Private tree entries, permissions, single-link regular file identities and exact bytes are checked
before operations. User edits, extra entries, links, or metadata changes refuse writes. Replacements
use exclusive sibling staging, file sync, a final decision guard, atomic rename, directory sync and
readback. There is no filesystem work between the final guard and rename. Filesystem/clock/durability
failure cannot become an assumed successful rollback. These checks are not compare-and-swap against
a hostile same-user writer, an OS sandbox or a hard whole-filesystem time limit.

Initialization failures retain any partial root and file-state report. Write failures retain staging
and observed artifacts, latch `recovery-required` where a root exists and disable ordinary mutations.
The failure result distinguishes the operation phase and whether replacement was attempted or returned;
`committed: false` after an attempted rename does not prove unchanged source. If the source read back
successfully but completion journaling fails, retain the last confirmed after observation and report
the overall failure. Do not blindly restore or retry an uncertain session.

`result()` returns detached **historical metadata**, not a fresh filesystem inspection. Its source
observation is explicitly `last-confirmed-not-refreshed-by-result`. All outcomes retain
`execution_status: not-run`, `authorization_status: unknown` and `verified_fix: false`. A private
file transition does not reproduce a vulnerability, pass a regression or establish a corrected app.
`close()` releases owned descriptors and retains all files; closed liveness and confirmed descriptor
cleanup are separate fields. An uncertain close is reported without claiming confirmed cleanup.

## Verification and remaining gates

Tests use owned inert temporary files, synthetic proposals, fake clocks and injected I/O failures.
Source/test bytes deliberately include top-level exceptions and are never imported, collected or run.
This is offline implementation evidence, not an actual user-project run or installed live acceptance.

The [S3 test interface/case codecs](REPOSITORY_VERIFICATION.md) now provide pure declarations and
supplied comparisons, which are not accepted as live evidence or decisions by this API.
Next are the separate external runtime and human-reviewed independent before/after case acceptance,
followed by the CLI operator, current installed external acceptance, explicit original-project
final correction and GUI integration. #152/#150 remain open; no version/tag, risk acceptance or release
is granted by S2 delivery. Original generated-test absence remains uninspected, and final original
test/source placement requires its own later current-state design and decision.
