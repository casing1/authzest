<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_STAGING.md">한국어</a>
</p>

# Generated repair input staging — private inert snapshots

[Documentation index](../README.md) · [Private workspace](GENERATED_REPAIR_WORKSPACE.md) ·
[Runtime profile](GENERATED_REPAIR_RUNTIME_PROFILE.md)

## Scope — 2026-11-13 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) slice prepares private input
snapshots for future T/test and A/application file mounts. It is an internal POSIX source API,
tested only with maintained inert temporary files. It does not mount, import, compile, collect or
execute the staged Python, call Docker/AI or activate the executor, session, CLI or UI.
#152 remains open; file materialization is not PoC reproduction or verified repair.

`GeneratedRepairInputStage(copy, candidate, role, *, _before_create=None)` accepts only an exact live
`GeneratedRepairWorkspace`. Before requires `ready-before`; after requires `applied-after`.
Restored, unconfirmed or closed checkpoints refuse. B/relay staging is forbidden: B must not receive
application/test input. There is no arbitrary destination, resume or imported-checkpoint constructor.

## Separate private parent, fixed readable files

Each stage allocates a fresh sibling of the original private copy, not a child that changes the
tracked copy. The outer directory is `0700`. Its `input` directory and T's `tests` directory become
`0555`; captured ordinary single-link source/test files are `0444`. A bounded host record is `0600`
**outside** `input`. Only the fixed input leaves can enter a later create plan.

| Role | Input leaves                                  | Bound original checkpoint            |
| ---- | --------------------------------------------- | ------------------------------------ |
| T    | `app.py`, `tests/test_generated_ownership.py` | Source, test, record and exact phase |
| A    | `app.py` only; no test directory/file         | Source, test, record and exact phase |
| B    | Refused, no allocation                        | No input staging                     |

These modes permit a later fixed-UID file mount without exposing the private outer directory.
They do not prove actual Docker sharing, guest UID access, effective read-only mounting or an
immutable filesystem. A trusted local owner can still change permissions; detected changes refuse.
Hostile concurrent same-user writers and a compromised OS remain outside the existing assumptions.

## Capture, allocation and identity checks

Existing workspace reads check all six original files and tracked directories. Staging captures
source/test/record `FileState` values and exact phase, including the test for A without copying it.
A trusted synchronous `_before_create` hook may refuse; the checkpoint is compared again after
the hook immediately before allocation. This hook is not authenticated consent or a new clock.
It does not replace a future coordinator's original decision/deadline rechecks.

Held directory descriptors, no-follow/nonblocking/exclusive I/O, bounded raw UTF-8 bytes, fsync and
exact readback bind names to the created objects. Directory scans are held-FD and bounded by the
expected entry count plus one; unexpected files refuse without an unbounded traversal. Snapshots
include device/inode/mode/owner/group/link/size/mtime/ctime identities, not hashes alone.

`assert_current()` and `snapshot()` recheck both the original checkpoint and the staged directories/
files. Managed apply/restore, edits, changed record, missing/symlink/hardlink/special files,
unexpected entries, permissions or same-byte inode replacement invalidate the stage. Invalidity
is latched; restoring bytes does not revive the same stage. The original copy is never written.

## Retained partial state, not automatic recovery

Initialization errors identify the attempted stage, per-file progress and descriptor cleanup
disposition. A confirmed created path is retained; allocation ambiguity must not be described as
zero writes or a known-owned directory. A name collision is not permission to open/delete the
existing target. There is no automatic deletion, collision retry, overwrite, recovery or restart.

`close()` closes descriptors only and retains all files. The host record describes historical
materialization, not fresh validity or authority; exported records cannot reopen a live stage.
Filesystem calls and descriptor cleanup have no universal preemption guarantee. Per-file bounds
are enforced here; the total retained-session budget still needs a future coordinator.

## Nonexecuting create-plan bridge

`prepare_create(profile, session_nonce, role_nonce)` rechecks the live stage before and after the
existing pure argument builder. Its separate `StagedCreatePlan` binds the stage manifest to fixed
T/A create-plan data, not the live workspace/record as mounts. It does not widen the older plan
schema into a readiness receipt or establish that declared engine/image/config identities exist.

Observed host files are distinguished from runtime: `filesystem_observed` can be true, while
`runtime_invoked`, `execution_authorized` and `verified_fix` remain false and authorization unknown.
Neither matching file facts nor imported JSON create consent, a before baseline or source-write
authority. The future dispatcher must recheck the **live** stage/current decision before each effect
and after execution, and still inspect exact stopped-container inputs and confirmed cleanup.

Reviewed images/engine/locks/capabilities, effective mount/resource enforcement, attach/start/
readiness/bounded capture/cleanup, durable session integration and installed acceptance remain
pending. No source sharing, actual worker/generated execution, operational patch/restore, risk
acceptance, issue completion, version change or release is added.
