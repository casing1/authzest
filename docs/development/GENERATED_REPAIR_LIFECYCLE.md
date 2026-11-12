<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_LIFECYCLE.md">한국어</a>
</p>

# Generated repair lifecycle — pure simulation only

[Documentation index](../README.md) · [Offline copy session](GENERATED_REPAIR_SESSION.md) ·
[Verification foundation](GENERATED_REPAIR_VERIFICATION.md)

## Scope — 2026-11-12 KST

This is another partial offline slice of [#152](https://github.com/casing1/authzest/issues/152).
The private lifecycle model describes the accepted **T → fresh A/B** container sequence using
closed simulated events. It has no engine transport, Docker command, process callback, network,
AI request, generated-code execution or file-writing operation. It is not connected to the
copy session, CLI, API or UI. #152 remains open.

The existing preview still has no bound image/engine/launcher/relay identities, and its proposed
resource recipe is not enforced. Default executor preparation remains disabled. The model's
synthetic identities/configuration are test data, not an inspected local image or runtime recipe.
No existing registered worker, prompt, dependency, package version or public command changes.

## Modeled sequence

[The private module](../../src/authzest/runner/_generated_repair_lifecycle.py) emits data-only
intents and accepts bounded, closed replies for the current intent. Names, nonces and expected
synthetic configurations belong to the model; an event cannot select an executable or target.
Reading a result is historical bookkeeping, not a new observation of time, files or containers.

`GeneratedRepairLifecycleModel(clock=...)` exposes `next_intent()`, `reply(event)`, `cancel()`
and `result()`. An outstanding intent must receive one current closed reply; requesting another
intent cannot replay its modeled dispatch. There is no execute, apply, restore or import API.
Python callers and the synchronous clock are trusted, not isolated by this interface.

- T represents the generated test with application/test input. Its modeled termination/removal
  must finish before creating the independent application/relay pair.
- A represents the application without the generated test; B represents the maintained relay
  without source/test input, sharing only A's exact modeled network namespace.
- Each role requires an acknowledged owned-name record before stopped creation, exact modeled
  identity/configuration inspection and output attachment before start.
- Ambiguous creation requires reconciliation of the exact previously recorded name. A foreign
  nonce/image/configuration cannot become a cleanup target. Ambiguous start does not imply that
  the guest stopped; only validated exact IDs may appear in cleanup intents.

The model does not implement the image-owned HTTP relay or import generated pytest reports.
T's exit/report is untrusted auxiliary data. A before test may fail against the intentional
ownership omission; an exit code alone neither reproduces it nor proves a repair. The separate
maintained comparator still accepts supplied data only, not authenticated runtime facts.

## Shared budgets and failures

The simulation models the proposed shared 40-second phase and cumulative startup/readiness at
most 10 seconds within it. Startup covers each role's record/create/inspect/attach/start interval
and A's readiness, not just its final readiness reply. Normal T teardown remains inside the
original phase. Final/failure cleanup gets one additional absolute 10-second deadline shared
by remaining roles, not a fresh deadline per guest. Combined stdout/stderr is at most 256 KiB
across all roles. These are modeled policy limits, not measured Docker capability or a universal
filesystem/daemon/kernel time bound.

Invalid/reversing clocks, replay, wrong ordering, malformed replies, persistence/capture errors,
timeout, output overflow, signal, OOM and cancellation cannot become simulated success. The
first cause is retained separately from cleanup uncertainty. Killing a client or receiving EOF
does not establish termination/removal. Unknown cleanup blocks further modeled work.

No actual stdout/stderr, source or account data is collected. Bounded historical summaries are
not a durable engine journal, execution attestation, consent receipt or resumable checkpoint.

## No runtime or application authority

Even a complete normal trace remains a **simulation**, with runtime not invoked, execution
`not-run`, baseline `not-established`, authorization `unknown` and `verified_fix: false`.
No serialized result can enable a session before baseline, accept a source diff, apply or
restore a file. There is no runtime adapter injection or host-pytest fallback in this model.

Maintained tests use fake events/clocks and block real execution/network boundaries. Passing
those tests verifies modeled ordering and failure handling, not actual isolation, capture,
resource enforcement or a generated repair.

The next integration work still needs reviewed pinned images/local engine, actual stopped-create
inspection, staged-file bindings, bounded attachment/relay capture and exact-object cleanup.
Only then can separately scoped installed before/after observations, CLI integration and the
read-only results UI establish the remaining course-release evidence. This slice is not a
release, real PoC reproduction, verified fix or issue-completion decision.
