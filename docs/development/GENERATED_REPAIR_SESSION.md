<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_SESSION.md">한국어</a>
</p>

# Generated repair session (guarded private-copy workflow)

[Documentation index](../README.md) · [Private workspace](GENERATED_REPAIR_WORKSPACE.md) ·
[CLI workflow](../guides/GENERATED_FILE_WORKFLOW.md)

## Current scope (2026-11-16 KST)

The source implementation for [#152](https://github.com/casing1/authzest/issues/152) now connects
current local decisions to a private copy, before check, exact diff acceptance/application, fresh
after check and restoration. This is an explicit opt-in path. The default session still permits only
copy creation and disabled before preparation. Neither mode imports a saved checkpoint as authority.

Tests use inert owned files, fake phase/kernel replies and existing trusted regression children.
No new live AI, Docker, generated-code execution, operational patch or release acceptance is claimed.
Current rebuilt images and separately scoped installed acceptance remain pending; #152 and #150 stay open.

## API and trusted coordination

[`_generated_repair_session.py`](../../src/authzest/runner/_generated_repair_session.py) provides:

- `GeneratedRepairSession(preview, clock=...)`: default copy/disabled-preparation behavior.
- `GeneratedRepairSession(preview, runtime_profile=..., runtime_guard=..., clock=...)`: opt-in
  current-profile flow with a required trusted synchronous guard. A profile declaration is not readiness.
- `prepare(stage)` and `decide(stage, choice, plan_id=..., lifetime_seconds=...)`: inspect the full
  current plan and record one terminal `approved`, `declined` or `cancelled` choice.
- `create_copy()`, `run_before()`, `accept_diff()`, `apply_source()`, `run_after()` and
  `restore_source()`: consume their separate stage attempts in that order.
- `prepare_before()`: retain the default disabled readiness check; it does not run a phase.
- `result()` and `close()`: export bounded historical summaries or release descriptors while
  retaining the copy/evidence. There is no import, restart or resume API.

Python callers, guards and clocks are trusted coordination, not human authentication or a sandbox.
The CLI adds a fresh runtime review and separate stage phrases; its guide describes the interaction.
The private `_parent` copy argument remains an owned-test seam, not a user-selected destination.

## Current bindings and original expiry

Each plan binds the current scenario/proposal, source/test text and host-derived diffs, session nonce,
profile identity, preceding accepted results and actual managed file identities/hashes. Later stages
capture the expected `ready-before`, `applied-after` or `restored-before` workspace state.
Changed bytes, same-byte inode replacement, changed snapshots/journal or directory replacement refuse
the planned operation rather than silently rebinding approval.

A plan keeps its original creation time and deadline at most 300 seconds later. Preparation cannot
refresh it; a later decision can only shorten expiry. Exact expiry is expired. Choices are terminal,
and each action consumes one attempt even if its preconditions fail. Reentry, replay and invalid clocks
are refused. Filesystem operations have no universal time bound.

For source application and restoration, the active session always supplies the workspace's optional
`commit_guard`. It runs after durable pending intent and final tracked-file/staging checks, rechecking
the original profile/decision, source/test and pending record with the monotonic clock last before
`os.replace`. Expiry or cancellation there performs no app rename, but the written pending journal
remains `state-unconfirmed` for inspection; no retry or forced restore follows. This bounds dispatch,
not filesystem completion, and is not atomic compare-and-swap. Exclude hostile concurrent same-user writers.

## Before, application and recovery

Before/after consume only the directly returned current phase object. The session checks candidate,
session/plan/profile identities, captured source/test hashes, owned objects and cleanup. It independently
recomputes the complete B capture against the maintained 17 cases / 21 requests. Supplied JSON,
pytest output, startup hints or a fabricated ready flag cannot establish a baseline.

T's before exit 1 and after exit 0 are distinct auxiliary observations, not assertion authenticity
or general authorization proof. Complete host comparison and confirmed cleanup are separate gates.
The fixed image entry checks supported kernel controls before target/tool imports; missing or wrong
properties refuse with exit 78. These are narrow kernel-reported settings, not escape proof or
resource stress benchmarks. Current image contents must still be reviewed.

Only a confirmed intended before profile opens exact source-diff acceptance and source application.
The existing workspace replaces only the reviewed `app.py` bytes in the new private copy; it retains
the generated test. After uses fresh staged inputs. A failed after may offer separately reviewed
restoration only when the applied file and cleanup remain confirmed. Changed or uncertain files,
invalid receipts and unknown cleanup require inspection rather than blind restoration.

There is no automatic restore, deletion or retry. EOF/Ctrl-C/SystemExit stop further interaction;
completed or uncertain effects remain visible. A restored-before file does not inherit a historical
after pass, and restoration does not run another check.

## Budgets and retained results

Before and after share one 2 MiB retained-evidence budget. Full plans are charged; bounded final
summary and restoration-plan capacity are reserved before effects so ordinary evidence exhaustion
does not silently consume recovery bookkeeping. Raw captures stay in private phase records; the
session exports bounded summaries and evidence references.

Each phase retains its original 40-second deadline, cumulative 10-second setup allowance and one
additional shared 10-second cleanup window. Captured CLI output shares 256 KiB, with 224 KiB for normal
capture and 32 KiB reserved for cleanup. These limits do not establish universal filesystem/kernel timing.

Results keep authorization unknown, `verified_fix: false` and distinct application/restoration states.
An uncertain write reports `applied: null` and an explicit `current_copy_state`, rather than inferring
no effect. A recorded historical application may remain true after confirmed restoration.
The current source flow is implemented; actual installed acceptance, local read-only results UI
[#153](https://github.com/casing1/authzest/issues/153) and the stable release remain pending.
