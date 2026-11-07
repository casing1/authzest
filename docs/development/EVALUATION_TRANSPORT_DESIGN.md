<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/EVALUATION_TRANSPORT_DESIGN.md">한국어</a>
</p>

# Evaluation invocation and capture boundary — design

[Documentation](../README.md) · [Evaluation protocol](EVALUATION_PROTOCOL.md) ·
[Development plan](DEVELOPMENT_PLAN.md) · [Issue #84](https://github.com/casing1/authzest/issues/84)

## Current pure-codec continuation — 2026-11-07 KST

`scripts/evaluation_invocation.py` now provides only an owned offline candidate factory, strict
outer-`0.2`/unchanged-inner-`0.1` decoder, preview and synthetic dry-run. See the
[current protocol and CLI examples](EVALUATION_PROTOCOL.md#offline-invocation-codec-continuation).
Original/final message hashes and schema hashes are distinct. Bounded UTF-8 raw response text is
retained in returned memory; canonical inner JSON is not the original response. The output schema
is a shaping subset, while strict decoder checks remain authoritative; pinned App Server support
is not verified. Echoing current IDs around old inner answers can still pass: decoded responses keep
caller-supplied/unverified provenance and `runtime_observed=false`, not authentication/provider freshness.

No account/network/process/reference/scoring/log-import access or actual AI/worker call is added.
Live capture/isolation/failure handling is still a proposal. Next review the versioned transport
recipe/batch expiry, then separate fake-process tests. Product adapter/pinned `0.153.0`, v1/math/history,
product `0.1.0a4` / report schema `1.2`, live-freeze false and #84's seven pending checks are unchanged;
there is no new risk acceptance or release. Codec delivery does not approve live execution/freeze.

## Original proposal — preserved history

The original design below is preserved at its original source/date. Its “not implemented” codec/API
wording describes that checkpoint, not the current offline continuation above; the live transport
remains unimplemented today. Do not reinterpret the proposal's delivery as execution approval.

## Status and purpose

**Proposed, not implemented — 2026-11-07 KST**, against main
`42e5db7104fd715af1edf1a5032b7761dc1747ca`. This document adds no callable API, CLI command,
provider integration, account lookup, live trial, execution permission or new live freeze. Documentation
delivery/review does not approve a model run or attest benchmark readiness. All seven #84 checks remain
pending. Existing v1 tasks/references, metric code/history, product code/dependencies/versions and
response schema `0.1` remain unchanged; no risk acceptance, patch or release is included.

The next implementation should first supply a **pure offline invocation codec**, followed by a
separately reviewed evaluation-only transport and fake-process lifecycle tests. Actual comparisons
still need a new explicit source/account/model/turn/time decision and the missing review/freeze evidence
listed in the [protocol](EVALUATION_PROTOCOL.md). This is not a proposal to expand the course scope.

## Three different claims

| Layer                                   | What it can establish                                                                                   | What it cannot establish                                                                       |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Existing host receipt `0.1`             | Caller-supplied metadata matches expected local slots; batch denominators are retained                  | Actual model execution, provider origin/freshness, or persistent one-use enforcement           |
| Proposed model-visible invocation `0.2` | A strict response echoes the current opaque invocation identity and contains a valid inner `0.1` answer | A caller cannot rewrap old answers, authentication, actual provider computation or correctness |
| Future direct runtime capture           | The trusted installed Codex/host process observed a correlated local request, stream and completion     | Cryptographic provider attestation, complete hidden harness context, or truth of an answer     |

Never promote caller-supplied JSON/log imports to runtime-observed evidence. A nonce echo alone is not
authentication, consent or provider freshness. Offline and fake-process results keep
`provider_freshness_verified=false`; no codec can set a runtime-observed provenance flag.

## Preserve the product adapter boundary

[`CodexAppServerAdapter`](../../src/authzest/codex/app_server.py) is version-pinned to `0.153.0` and
allows owned fixture/owner-policy requests through its guarded public entry points. Its private
`_turn` uses fixture-specific base/developer instructions and chooses the catalog's
`defaultReasoningEffort`, not the evaluation candidate's explicit effort. It is therefore **not** an
evaluation transport interface.

Do not call that private method with evaluation prompts/schemas, widen its request types/allowlist,
or silently change product instructions, effort selection or version support. A future source-only
evaluation transport must own its narrow request type and lifecycle. Any useful shared low-level
extraction requires separate compatibility review; this design does not authorize it.

The current [official App Server documentation](https://learn.chatgpt.com/docs/app-server) describes
RPC request/response IDs, per-turn `outputSchema` and completion events with distinct statuses. These
are design guidance, not proof that every current field exists in pinned `0.153.0`. Before transport
implementation, review that version's generated schemas and pin the exact wire fields/configuration,
event allowlist and compatibility tests. Do not copy newer examples or upgrade the product adapter.

## Proposed pure invocation codec

Proposed module names below are not available interfaces. `scripts/evaluation_invocation.py` would
build candidates from the owned task-only planner and an in-process collection session, not imported
plans, arbitrary prompt/schema dictionaries, arbitrary source paths or evaluator reference data.

Rebuild/revalidate the configuration, plan, packet set, slot membership, task/request/trial identities
and original application-message SHA-256 before selecting a packet. Verify the actual packet against
the expected slot, not just a caller-supplied digest. Keep the old planner/collector contracts intact.

The proposed outer objects have exactly these fields:

| Object   | Fields and meaning                                                                                                                                                            |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input    | `schema_version="0.2"`, `kind="evaluation-invocation-input"`, opaque `invocation_id`, common `instructions`, and `task` containing the complete unchanged `0.1` input payload |
| Response | `schema_version="0.2"`, `kind="evaluation-invocation-response"`, exact current `invocation_id`, and `response` containing the complete unchanged `0.1` response object        |

The common outer instructions must make packaging unambiguous: the old task instructions and answer
contract govern the **inner `response` object**, while the outer object echoes `invocation_id`. Treat
source/policy/evidence as data, use only the supplied task, request no tools/execution, and return one
complete JSON object without prose. Final instruction bytes and output schema are future reviewed
candidate artifacts, not frozen by this document. The schema must constrain syntax/IDs, never insert
expected answer values or evaluator reference metadata.

Use a new versioned recipe and content-ID namespace. Derive an opaque invocation ID from the fresh
collection namespace, trial/configuration bindings and recipe digest **before** inserting it into the
message. Then hash the completed canonical UTF-8 `0.2` application message and output schema separately.
Do not hash a message containing its own hash. Retain the original `0.1` message hash under an explicitly
different field; it is not the final `0.2` message hash. Bind the complete candidate to its old plan ID,
new recipe, final messages/schemas and requested settings. Do not relabel the old plan as a frozen live
plan or transfer its IDs to new message bytes.

Only the selected opaque invocation ID, common framing and original task are model-visible. Keep the
whole plan, mode/case/split labels, reference/manifest hashes, expected answers, rationales, reviewer
data, account data and local paths outside application messages. The two modes have the same framing,
source/policy/questions/answer formats and schema structure; only existing declaration evidence and
necessary opaque binding values differ. These identifier differences are not randomization or blinding.

### Strict response validation

Proposed outer limits are 64 KiB of complete UTF-8 response text and JSON depth 16, including the inner
object. Reject duplicate keys at every level, nonfinite/overflowed numbers, wrong types/fields/versions,
extra text/fences, wrong invocation IDs and bare `0.1` responses. Validate the exact outer echo before
passing the inner object through the unchanged strict `0.1` decoder with the factory-owned specification.
Preserve raw received text separately; canonical serialization of an already checked inner object is
not the original provider response and must not be labeled as such. No repair, coercion, partial credit
or conversion of invalid/missing responses into valid unknowns is allowed. `""` remains a known empty
sorted-CSV set; only null is unknown.

Old responses from another namespace/slot/repetition must fail unchanged. Explicitly test the
counterexample: old inner answers wrapped in a current, valid `0.2` object can pass. Record that limit
instead of claiming the codec authenticates output or proves that a new model invocation occurred.

## Future evaluation-only direct capture

`scripts/evaluation_transport.py` is a proposed separate coordinator, not an implemented launcher.
It must receive only the owned current candidate and fresh bounded decision, rebuild and compare the
complete preview immediately before dispatch, and consume the slot attempt **before the first possible
turn send**. A failed write/uncertain acknowledgement must not cause another application-level attempt.
The later consent UI should present all selected batch messages, settings, attempt counts and time/usage
limitations in one complete bounded decision, not demand a new user confirmation for every normal slot.
Per-slot single-use state is an internal constraint, not additional authority. The batch dispatch window,
expiry bounds and monotonic-clock rules must be fixed/tested in the transport recipe before its process
boundary is implemented; do not assume a preview has an unlimited lifetime or automatically renew it.
One slot uses a new empty ephemeral thread and one turn; no resume, fork, history import, steering,
model substitution or AuthZest retry. Metadata discovery may use a separately cleaned process, but it
must not create a model turn. Each slot's generation transport is separate and cannot reuse another
slot's context. This is not a promise of only one OS process per slot.

Before generation, validate the exact candidate model and explicit effort against the pinned catalog
and server-reported settings. Never choose a default effort or alternate model. If the pinned protocol
cannot establish required settings, refuse the live benchmark rather than claiming they were enforced.
Record requested and server-reported values separately; a server report is not attestation of hidden
provider computation. Missing optional usage/latency metadata remains null, not zero.

Review fixed base/developer instructions, sanitized environment, empty working directory, inherited
configuration checks, disabled external context/discovery/tools/MCP/apps/hooks and sandbox settings as
one versioned evaluation recipe. Reject unexpected tool/approval requests, context/settings changes,
model rerouting, foreign RPC/thread/turn identities and ambiguous final outputs. Application-message
hashes do not cover all Codex wire bytes or hidden harness instructions. Do not claim full context
isolation merely because the directory is empty or read-only; compare an explicitly configured Codex
harness, not a bare model. Installed Codex, its authentication and the stable local host are trusted.

The runtime must directly correlate the attempted send, matching RPC acknowledgement, thread/turn IDs,
one completed final agent-message item and successful `turn/completed` status from that process.
Partial deltas, a final-looking JSON string, or a matching echo before successful completion are not a
completed trial. Record a monotonic dispatch/completion interval separately from startup and cleanup;
do not call the interval provider-only latency. Preserve only bounded private/redacted evidence needed
for validation, never credentials/raw stderr/account profiles. Public summaries need a separate scope
check; this design does not approve raw log publication or a new persistent export/import feature.

Proposed limits for the later transport are the candidate's explicit startup/generation adapter budget
of 1–120 seconds, a separate cleanup wait of at most five seconds per created process group (not a
combined five-second cleanup bound for the whole slot), 256 KiB per JSONL frame, 2 MiB
aggregate stream bytes, 4,096 events and at most 128 queued notifications. Exceeding a bound fails the
slot and triggers cleanup. These are application limits, not an OS sandbox, total-filesystem wall cap
or token/credit cap. Codex-internal retries/usage cannot be bounded by this design: reject a surfaced
retry/recovery error rather than silently restarting/recovering a trial, but do not claim hidden retries
are prevented. Any live consent must disclose that limit. Preserve primary failure and cleanup failure
separately; publish no successful result if cleanup is unconfirmed.

## State, failures and later scoring

Required progression is candidate → reviewed preview/decision → consumed dispatch → acknowledgement →
matching stream/completion → strict response validation → cleanup-confirmed observation. A refusal,
stale/expired decision, transport failure, interruption, timeout, invalid response or cleanup failure
must not create an executable success or replenish a slot. Content IDs and caller decisions are not
authenticated human approval.

Keep a future direct-observation type separate from caller-supplied host receipts; the current collector
cannot manufacture or certify runtime provenance. Retain every planned slot: seven cases/21 question
opportunities per mode/repetition, and 14/28/42 slots for one/two/three repetitions. Report skipped/refused,
missing, invalid, failed, interrupted and timeout outcomes distinctly, with cleanup status and attempt
stage. Do not coerce new statuses into the old collector schema or discard them to improve a score.
Unconfirmed cleanup or a context/configuration integrity violation stops further batch dispatch; retain
undispatched slots with an explicit skipped reason. Continuation after an ordinary terminal slot failure
with confirmed cleanup must be an explicit frozen policy, not an opportunistic rerun or implicit default.

Stage all validated responses and terminal failures before the separate evaluator opens references.
The later scoring bridge must map missing to `None` and invalid/failure/refused/skipped outcomes to
no-credit `[]`,
preserving original failure reasons and denominators. Available usage, observed intervals, human review,
semantic citation support and repeated variation remain separate measurements. Answer-only `0.1`
still cannot measure explanations/citations/review effort. Public assistant-developed tasks and the
unestablished independent review/blinding limit remain even after a successful live run.

## Implementation gates and offline acceptance

1. Implement the pure owned `0.2` codec with zero account/network/process/reference access. Test every
   outer field/type/binding, strict JSON boundary, unchanged inner answer semantics, original/final
   message hashes, input/reference separation, paired framing, and the rewrapping counterexample.
2. Review the exact version-specific evaluation transport recipe before adding its process boundary.
   Use deterministic fake-process tests for foreign/duplicate/early events, settings/effort/model
   mismatches, tools/approvals, rerouting, surfaced retries, failed/interrupted completion, EOF,
   limits/timeouts/cancellation, uncertain send and cleanup failure. Fake events are not live evidence.
3. Keep decline/stale/expired decisions and every missing/failure slot visible. Demonstrate that retries,
   fallback, context reuse and partial-output acceptance cannot silently improve completion counts.
4. Review/fix the candidate instructions/schema, exact transport/configuration, ordering, repeats and
   measured/unmeasured fields before a live freeze. Preserve current reference values/authorship and
   missing independent-review evidence; this proposal does not resolve either by assertion.
5. Only then request one clear bounded live-comparison decision covering exact sources, account/model,
   effort, attempts and time/usage limitations. Existing fixture/owner-repair approvals do not transfer.
   Run no trial from a preview or documentation example. Publish descriptive results/limits, not a
   benchmark-quality or evidence-assisted-improvement claim without the corresponding evidence.
