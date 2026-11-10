<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_WORKSPACE.md">한국어</a>
</p>

# Generated repair private workspace — offline file-I/O foundation

[Documentation index](../README.md) · [Verification foundation](GENERATED_REPAIR_VERIFICATION.md)

## Scope — 2026-11-10 KST

This is a further offline slice of [#152](https://github.com/casing1/authzest/issues/152).
It implements a **private low-level file-I/O seam**, not the active generated-repair workflow.
The generation/verification preview commands and default disabled executor remain unchanged.
No CLI, public API route, live decision/session coordinator, image, container, worker or new
provider request is connected to this helper. #152 remains open.

Maintained tests use hand-authored inert proposal strings and pytest-owned temporary parents.
Copying those bytes and replacing/restoring the test copy are filesystem regressions, not an
approved operational model patch, generated-test execution, PoC reproduction or verified repair.
No private actual-generation response, account history or historical live copy is used.

## Private boundary

[`_generated_repair_workspace.py`](../../src/authzest/runner/_generated_repair_workspace.py) is
internal implementation machinery for a future separately gated coordinator. Its Python caller
and synchronous guard callback are trusted. Neither underscore names, a valid preview, a file
hash nor that callback authenticates a user or grants execution/patch authority.

The future coordinator must still bind fresh, expiring, single-use copy/diff/apply/restore
decisions and accepted independent runtime evidence. In particular, a caller-supplied
`data-only` HTTP comparison **cannot satisfy the before-check gate**. This helper has no API to
turn such JSON into runtime proof. Do not connect its writes directly to a model response or UI.

## New copy and fixed files

`GeneratedRepairWorkspace(preview)` revalidates the complete current verification preview,
request/proposal, both host-derived diffs and maintained definitions before any filesystem effect.
Only `proposed-change` can create a copy. The before source is the fixed maintained scenario;
the after source/test are the exact validated proposal bytes. Paths in the proposal are fixed
labels, not caller-selected destinations.

The production default creates only a fresh private system-temporary directory. It cannot reopen
an existing workspace, import a journal as a session, replace an existing checkout or resume an
interrupted operation. A private `_parent` seam exists for trusted temporary-file tests, not an
artifact-controlled destination or a supported end-user option.

The managed files are:

```text
fresh-private-copy/
├── app.py                              # fixed before, then exact after, then before
├── tests/
│   └── test_generated_ownership.py      # materialized test; retained unchanged
├── before.txt                          # immutable source bytes
├── after.txt                           # immutable proposed source bytes
├── test.txt                            # immutable test bytes
└── record.json                         # bounded host bookkeeping, not an approval receipt
```

Directories are owned `0700`; managed files are owned `0600` ordinary single-link files.
The helper holds directory descriptors for the root and `tests` directory and verifies both
opened/named identities. Initialization must finish exact source/test/snapshot readback,
directory sync and the initial durable journal before reporting a usable before state.
Partial initialization retains its confirmed path, failure stage and materialization information;
it does not claim zero writes, remove the evidence or silently retry.

## Reads, exact source replacement and restoration

`read_source()`, `read_test()` and `read_record()` return immutable `FileState` byte/identity
snapshots. Source/test reads retain exact UTF-8 bytes without newline normalization, with the
existing 16,384-byte source/test limit. Pre/post descriptor and named-file checks cover device,
inode, mode, owner/group, link count, size, mtime and ctime. Missing files, symlinks, hardlinks,
special files, permission changes, root/subdirectory replacement and same-byte inode replacement
are not silently accepted as the reviewed state.

`apply_source(expected, guard=...)` may replace only `app.py` with the exact proposed after bytes;
`restore_source(expected, guard=...)` may return that confirmed applied file to the exact before
bytes. The helper also verifies the unchanged test, immutable snapshots and tracked journal.
The synchronous guard must complete normally with `None`; it is a recheck hook, not consent.
It runs once before the intent journal/source commit; preparing an exact private staging file
can precede the callback. Reentrant transitions are refused. Tracked files are checked again after it. Those reads
take time, so this callback does not promise real-time expiry enforcement or an atomic decision/write.
Persist a durable unconfirmed intent before source replacement, then fsync/read back the source
and confirm the host journal only after those steps succeed.
Wrong phase, stale input or detected user edits must refuse a write, not overwrite the changed file.

The copy-created baseline is **before app plus the generated test**. Test materialization belongs
to copy creation; later source apply changes only the app. Restore preserves the test and evidence;
it does not reconstruct an absent-test original tree, remove the generated test or modify the
original checkout. These steps are not one atomic app-plus-test transaction.

## Failure and bookkeeping

The helper distinguishes a ready before state, confirmed applied after state, restored before
state and unconfirmed state. Its bounded host journal binds the current preview/file identities
and file-operation states while keeping execution not run and authorization assurance unknown.
It is inspectable bookkeeping, not an authenticated receipt or imported execution capability.

The journal records an unconfirmed write intent before source replacement; that state is not a
successful apply/restore and cannot authorize resumption. A replacement followed by fsync,
readback or final journal failure may already have changed the file.
Such an outcome must report an attempted/committed-but-unconfirmed write rather than `not-applied`.
An uncertain state, changed evidence or failed persistence blocks subsequent effects, including
programmatic restoration; retain the copy for manual inspection. A new callback cannot authorize
overwriting detected edits. Interruption metadata must retain the same distinction.

Only exact just-created staging entries are cleanup targets. Unconfirmed staging cleanup cannot
be silently treated as success or broadened to user-selected paths. `close()` releases held
descriptors; it does not delete the copy, test or journal. There is no automatic retry, process
restart, imported-journal resume, forced rollback or success through partial evidence.

## Limits and next integration

This supports POSIX non-frozen source installation with the required descriptor/no-follow
primitives. Other platforms must refuse this file boundary; ordinary portable scan/preview and
contract support are separate. No Docker dependency is added to those paths.

Private permissions, file hashes and atomic rename are not an OS sandbox or atomic
compare-and-swap against a hostile concurrent same-user writer. The trusted operator must exclude
such writers. Directory creation, multiple file writes, application and journal persistence are
not one filesystem transaction; filesystem calls have no universal wall-clock guarantee.

The next coordinator must consume real stage decisions before any effect, enforce finite
monotonic lifetimes and once-only attempts, require a valid real before baseline before apply,
and connect actual captured-byte runtime checks with confirmed guest cleanup. The current default
executor is still disabled, and the private file helper is not an alternate execution path.
Generated pytest reports remain untrusted auxiliary data; independent controls, actual after-file
observations, refusal/recovery paths and exact installed-candidate acceptance are still required.
Local read-only UI and release work remain separate gates.
