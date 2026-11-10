<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_SESSION.md">한국어</a>
</p>

# Generated repair session — offline decisions and copy only

[Documentation index](../README.md) · [Private workspace](GENERATED_REPAIR_WORKSPACE.md) ·
[Verification foundation](GENERATED_REPAIR_VERIFICATION.md)

## Scope — 2026-11-10 KST

This is another partial offline slice of [#152](https://github.com/casing1/authzest/issues/152).
The internal session binds fresh local decisions to **copy creation** and **disabled before-check
preparation** only. It is not connected to a CLI, public API route or browser approval surface.
No runtime executor, engine probe, image, generated Python execution or new provider call is added.
#152 remains open; neither a reproduced PoC nor an independently verified repair is established.

The preceding workspace helper can replace and restore inert file bytes in maintained tests.
This session deliberately exposes **no apply or restore method**. There is no accepted-before
baseline, runtime-evidence importer or executor injection. Matching caller-supplied HTTP facts,
a generated test report, an exported checkpoint or a fabricated ready result cannot open those stages.

## Internal API and trust

[`_generated_repair_session.py`](../../src/authzest/runner/_generated_repair_session.py) provides:

- `GeneratedRepairSession(preview, clock=...)`: validate the exact current preview and start a fresh
  in-process identity; construction performs no filesystem or runtime operation.
- `prepare("copy")` and `prepare("before")`: produce inspectable content-bound plans for the
  current allowed stage, not execution capabilities.
- `decide(stage, choice, plan_id=..., lifetime_seconds=...)`: record one terminal local choice,
  `approved`, `declined` or `cancelled`, for that exact current plan.
- `create_copy()`: consume one copy attempt and create only the existing fresh private workspace
  when all current preconditions and its independent decision allow it.
- `prepare_before()`: consume its own attempt and check only the default disabled readiness path.
- `result()` and `close()`: export a bounded historical checkpoint or release descriptors while
  retaining files. There is no imported-checkpoint constructor or restart/resume API.

Python callers and clock callbacks are trusted. These methods do not authenticate a human,
verify provider provenance or establish an OS sandbox. The private `_parent` argument on copy
creation is a pytest-owned temporary-parent seam, not a supported artifact-controlled destination.
No report/package version, dependency, Codex pin or existing registered workflow is changed.

## Plans and original deadlines

The copy plan binds the full current source/test artifacts and both host-derived diffs, fixed paths,
scenario/control/recipe identities, a fresh session identity and generation. It distinguishes
test materialization during copy creation from later source replacement, which is not enabled here.
Before a copy exists its filesystem identity is explicitly unobserved.

After confirmed creation, a before plan binds the current checked root/test-directory manifest,
all six managed file identities/hashes, including the host journal, and the same current artifacts.
It is built from the active workspace's checked state, not supplied manifest JSON. Changed bytes,
same-byte inode replacement, changed snapshots/journal or root/subdirectory replacement invalidate
the planned state instead of silently rebinding approval.

A plan keeps its original creation time and a hard deadline at most 300 seconds later. Repeated
preparation does not refresh it. A later decision has its own decision time and may shorten that
deadline, never extend it. Choices are terminal; there is no replacement approval after refusal,
expiration or consumption. Exact expiry is expired.

The monotonic clock must be finite, nonnegative and nondecreasing, and the requested duration must
be representable within the fixed bound. Boolean, NaN, infinity, backward and unrepresentable values
are not valid times. Context/file checks take time, so the session rechecks time after validation
and immediately before copy allocation. Filesystem operations still have no universal deadline.

## One attempt and accurate effects

Copy and before preparation each have a separate once-only attempt. An action call consumes its
attempt before dispatch, including when its plan/decision is absent, pending, declined, cancelled
or expired. Calling the action early does not reserve a later retry. Invalid decision input must
not replace an existing pending choice. Reentrant state-changing operations are refused without
allowing a nested call to release the outer busy guard.

The copy baseline is the exact before app plus the proposed test, immutable snapshots and host
journal. Only a confirmed readback/sync can report a confirmed copy. Partial initialization retains
its known path, stage, file materialization and uncertainty; interruption does not become zero writes.
There is no automatic retry, deletion, forced rollback or recreation of an existing directory.

`prepare_before()` records preparation separately from actual execution. Even when preparation
completes normally, the default remains not ready: execution is not run, the runtime baseline is
not established, source application/restoration are not run, authorization assurance is unknown
and `verified_fix` is false. No generated test is imported, compiled, collected or executed.

Later `source-diff`, `source-apply`, `after` and `restore` stages refuse with
`runtime-not-implemented`. This is an intentional incomplete execution boundary, not a fallback to
host pytest or the existing fixed-policy worker.

## Checkpoints, closure and next boundary

`result()` is a bounded unauthenticated historical checkpoint. It reports what this session recorded;
reading it does not freshly inspect files, authenticate consent or reconstruct live decisions.
The low-level file journal remains separate bookkeeping, not a durable session approval store.
Closing retains the copy and all evidence, and closed sessions cannot authorize further actions.

Maintained tests use hand-authored inert text, temporary files and fake clocks. They cover original
deadline preservation, refused/expired/replayed decisions, file identity changes, partial creation,
interruption, reentry and inability to acquire runtime or source-write authority. Such tests are
not a real model response, a generated-code run or installed-candidate workflow acceptance.

Next, the reviewed container/relay lifecycle must produce real captured-file observations with
confirmed cleanup before any apply gate is connected. Future source writes need a final trusted
expiry recheck immediately before commit: the workspace's earlier guard plus intervening journal
I/O is not that guarantee. The independent controls and generated reports remain distinct, and
operational execution, exact-candidate acceptance, local read-only UI and release are separate gates.
