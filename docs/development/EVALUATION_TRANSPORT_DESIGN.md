<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/EVALUATION_TRANSPORT_DESIGN.md">한국어</a>
</p>

# Evaluation invocation and capture boundary — design

[Documentation](../README.md) · [Evaluation protocol](EVALUATION_PROTOCOL.md) ·
[Development plan](DEVELOPMENT_PLAN.md) · [Issue #84](https://github.com/casing1/authzest/issues/84)

## Current offline dispatch continuation — 2026-11-08 KST

`scripts/evaluation_dispatch_recipe.py` now materializes owned descriptors/recipe IDs and canonical
JSONL frame candidates with hashes and byte limits. Requested model/effort and common codec
instructions are explicit; mutable product configuration is neither imported nor changed. Selected
owned projections of generated experimental schemas check request shapes, not the full bundle,
nested-provider schema support, effective configuration or tool isolation. `remoteControl/status/read`
uses `params=null`, while `initialized` omits params; see the dated correction below.

`scripts/evaluation_dispatch.py` adds a pure serial `Batch` simulation: fresh preview namespaces,
revision tickets rejecting old transitions, and explicit decide/reserve/send/ack/checkpoint/finish
states. Caller-supplied integer-nanosecond `Clock` samples model the 300-second confirmation TTL,
acceptance-fixed `W`, five-second original-anchor discrepancy and never-reset slot budget. Synthetic
null responses remain valid; the first nonvalid or unconfirmed cleanup stops later slots, preserving
every planned denominator. Decisions, acknowledgements and cleanup are caller assertions, not
authenticated approval, process inspection or runtime evidence. See the
[current API/CLI scope](EVALUATION_PROTOCOL.md#offline-dispatch-recipe-and-state-simulation).

No account/configuration RPC, provider/process execution, timer/cancellation/cleanup enforcement,
log import, persistent cross-process ledger or scoring is implemented. Next review effective
configuration/discovery startup semantics, then a separate fake-process transport boundary. Live
capture/generation still needs new source/account/model/turn/time approval and missing review/freeze
evidence. Existing codec/pin/product `0.1.0a4` / report `1.2`/v1/math/history are unchanged; #84 stays
OPEN with seven pending checks and live freeze false. No actual AI/worker call, risk acceptance or release.

## Pure-codec checkpoint — 2026-11-07 KST

This earlier checkpoint is retained for chronology; its next-step wording preceded the offline
dispatch continuation above, not an account of unavailable current recipe/state helpers.

`scripts/evaluation_invocation.py` now provides only an owned offline candidate factory, strict
outer-`0.2`/unchanged-inner-`0.1` decoder, preview and synthetic dry-run. See the
[current protocol and CLI examples](EVALUATION_PROTOCOL.md#offline-invocation-codec-continuation).
Original/final message hashes and schema hashes are distinct. Bounded UTF-8 raw response text is
retained in returned memory; canonical inner JSON is not the original response. The output schema
is a shaping subset, while strict decoder checks remain authoritative; pinned App Server support
is not verified. Echoing current IDs around old inner answers can still pass: decoded responses keep
caller-supplied/unverified provenance and `runtime_observed=false`, not authentication/provider freshness.

No account/network/process/reference/scoring/log-import access or actual AI/worker call is added.
Live capture/isolation/failure handling is still a proposal. The version-specific dispatch proposal below
precedes pure offline decision/state tests and separate fake-process tests. Product adapter/pinned `0.153.0`, v1/math/history,
product `0.1.0a4` / report schema `1.2`, live-freeze false and #84's seven pending checks are unchanged;
there is no new risk acceptance or release. Codec delivery does not approve live execution/freeze.

## Version-specific dispatch proposal — 2026-11-08 KST

Historical design-only checkpoint: the original unimplemented/next-step wording below records that
proposal, not the current offline builder/ledger. The dated params correction is identified inline;
actual process/configuration/capture semantics remain unimplemented.

**Design only, against main `851d84cd4ab35bb35d262e2dbef23af7810dc5f3`.** Proposed recipe name:
`evaluation-stdio-0.153.0-v1`. No dispatch API, decision ledger, frame builder, process transport or live
configuration freeze is implemented by this update. Next implement pure offline recipe/frame and
batch-state tests; add process lifecycle tests only after that boundary is reviewed. These are not
additional course features or permission to reuse the private product `_turn`.

### Pinned schema evidence, not runtime evidence

The installed CLI reported `0.153.0`. Its local `app-server generate-json-schema` subcommand generated
both default and `--experimental` protocol bundles without starting a server or making account/model
RPCs. The experimental bundle is the relevant field reference for `experimentalApi=true`: the default
bundle omits fields such as `allowProviderModelFallback`, `environments` and `runtimeWorkspaceRoots`.
Do not infer unsupported fields from that default omission.

Selected raw experimental schema SHA-256 values from that generation are below. These identify public
generated protocol documents, not the executable, a signed release, actual wire capture or config.
The generated bundles are not vendored or imported by the current codec.

| Generated document                          | SHA-256                                                            |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `v2/ThreadStartParams.json`                 | `25f490368ec6df52a2a3b82a5469d2413307eb93439121b309f415b5648eee7a` |
| `v2/ThreadStartResponse.json`               | `a338467af5fc271ace917f9d1262405642c3df3b66116aa105343db86cc9a76d` |
| `v2/TurnStartParams.json`                   | `b36fb37326b1cf69f75c8b306f1f886d53a57c4b1b985e08e298e2407ea2ad02` |
| `v2/ThreadSettingsUpdatedNotification.json` | `f7865eabaa34c7895a1ae345e51c1ba181a63c649237d36583b80f9d759b0f53` |

The [official App Server reference](https://learn.chatgpt.com/docs/app-server) explains version-specific
schema generation and RPC lifecycle. Here the generated files were read and compared with local
product code, not used to mechanically validate every existing fake fixture. In particular, existing
fake Model/Thread/item/usage payloads omit some generated required fields; passing those tests is not
full protocol-schema conformance. `outputSchema` accepts arbitrary JSON at the protocol layer, which
does not establish provider support for the codec's nested shaping schema. Config also permits extra
keys: field presence alone does not establish effective configuration or disabled capabilities.

### Proposed recipe and wire choices

The future source-checkout-only POSIX transport must own its recipe values rather than importing
mutable product configuration. Use the exact `CONFIG` and `DISABLED_FEATURES` values from product
source at the baseline above as the starting descriptor, **except** replace fixture-specific developer
instructions with the codec's exact common `INSTRUCTIONS`, and explicitly set model, requested effort
and `approvals_reviewer="user"`. Use the same common instruction bytes for thread base/developer
instructions and collaboration developer instructions in both modes. The next offline builder must
materialize and hash all values, schema selections, limits and clock/failure rules; this document is
not an executable recipe digest. Unknown instruction/profile/provider/context overrides must not be
silently inherited. Effective configuration, including ambient MCP behavior during discovery, remains
a process-implementation gate, not a guarantee supplied by this descriptor.

| Stage                   | Proposed exact choice and required observation                                                                                                                                                             |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Process boundary        | At most two sequential process groups per slot: config-only discovery, then generation. New empty cwd; stdio JSONL; version `0.153.0` from executable and initialize user agent. No shell launcher.        |
| Initialization/config   | `experimentalApi=true`, then `initialized`; `config/read` with `includeLayers=false`. Enumerate at most 64 bounded MCP names and disable each on generation restart; verify all recipe values.             |
| Environment             | Only `PATH`, `HOME`, `CODEX_HOME`, `TMPDIR`, `LANG`, `LC_ALL`, `USER`, `LOGNAME` may be inherited. Preserve existing auth location; never copy credentials or forward API keys/proxies/endpoint overrides. |
| Account/catalog         | Existing ChatGPT login only; `account/read` with `refreshToken=false`. `model/list`: `limit=100`, `includeHidden=false`, bounded 10 pages/1,000 entries, unique progressing cursors.                       |
| Model/effort            | Exactly one visible catalog entry matching the requested model and one advertised `supportedReasoningEfforts[].reasoningEffort` matching explicit effort. No default, substitute, alias or fallback.       |
| `thread/start`          | Exact model/provider `openai`, `allowProviderModelFallback=false`, `ephemeral=true`; empty environments/tools/capability/workspace roots; read-only/on-request; reviewer `user`; fixed instructions.       |
| Initial effort setting  | Set `model_reasoning_effort` in process config and `thread/start.config` to the requested effort. Require non-null matching response `reasoningEffort`; absence is unverified, not success.                |
| Initial thread evidence | Match model/provider/cwd/approval/reviewer/read-only no-network; `thread.ephemeral=true`, empty turns/instruction sources/roots, no fork/parent context. No resume/fork/history import or steering.        |
| `turn/start`            | Exact thread ID, model and effort; one text input equal to `Invocation.message_text`; exact `Invocation.output_schema`; empty environments/roots; same sandbox/approval/reviewer/cwd.                      |
| Collaboration/tier      | Explicit `collaborationMode.mode="default"`, settings model/`reasoning_effort` equal requested values and non-null common `developer_instructions`; `serviceTierForTurn="default"`.                        |

**2026-11-08 schema correction:** the generated experimental `ClientRequest` permits optional/null
params for `remoteControl/status/read`, not `{}`; offline frame candidates choose `null`. This is a
selected shape check, not a product adapter change or runtime/provider compatibility result.

Before account/catalog/thread creation, call `remoteControl/status/read` with `null` and require
`status="disabled"`; missing, malformed or other status refuses the batch. Notification absence is
not evidence that remote control is disabled. `collaborationMode` takes precedence over top-level
model/effort/developer settings, and null developer instructions select built-in mode instructions;
the explicit equal/non-null settings above prevent that silent substitution.

Generated `ReasoningEffort` is a nonempty string, not the product adapter's five-value compatibility
list. Validate the exact requested label against the bounded catalog, not its default. Null/duplicate
model entries, cursor cycles, too many pages, malformed settings, or missing required reported effort
refuse the batch. A server-reported setting is still not telemetry of hidden provider computation.
Do not expose account identities, configuration paths or catalog contents in public evidence.

Use a closed event policy, not the product retry policy. Expected methods are `thread/started`,
`thread/status/changed`, `thread/settings/updated`, `turn/started`, `turn/completed`, `item/started`,
`item/completed`, `item/agentMessage/delta`, the three product-listed reasoning delta methods,
`thread/tokenUsage/updated`, `account/rateLimits/updated`, `model/verification`,
`model/safetyBuffering/updated`, `turn/moderationMetadata`, and `remoteControl/status/changed` only
when disabled. Every field/payload still needs pinned-schema and semantic validation; an allowlisted
method alone is insufficient. Bound and correlate queued pre-ack notifications after the matching RPC
acknowledgement. Reject foreign/duplicate RPC identities and foreign thread/turn identities.

Every `error` including `willRetry=true`, `warning`, `configWarning`, `guardianWarning`, deprecation,
auth recovery, model rerouting, tool/approval request, unexpected item/context/settings or unknown
event is batch-fatal. Never parse warning prose as configuration, usage or an approval. Drop private
warning/error text and retain only bounded closed diagnostics. Reject settings with null/different
effort or collaboration effort, model, developer instructions, reviewer or boundary values; do not
relabel missing metadata as verified. Do not reuse the product's allowance for three retry notices.
Without a complete matching settings observation, keep settings unverified and do not publish a
validated runtime observation, even if the final JSON and completion otherwise pass.
Already initiated/hidden Codex retries and usage still cannot be capped or certified absent.

Require a correlated `item/completed` agent message with explicit `phase="final_answer"`, unique
item ID and bounded text, followed by matching successful `turn/completed` with null error. Unknown
phase is not final in this recipe. Deltas or turn snapshots alone do not supply a final result. A
snapshot may repeat the same completed item only with identical content; it must not introduce a
second/conflicting final item. Then invoke the unchanged strict codec, and publish an observation
only after confirmed cleanup. Missing usage remains null and last-turn usage is not total billing.

Keep existing proposed limits: 256 KiB per complete JSONL frame, 2 MiB received stream bytes and
4,096 events across both slot processes, at most 128 queued notifications, and a single slot budget
`T` of 1–120 seconds for startup/preflight/generation. Do not reset `T` after discovery or events.
Cleanup waits may extend beyond `T`, at most five seconds per created process group; this does not
bound blocking filesystem work, total wall time, tokens or cost. The actual encoded request frame
must fit its limit even when message/schema separately fit codec limits.

### Whole-batch decision and fixed clocks

One future complete review covers all selected messages/schemas, ordering, exact settings/recipe,
source/account scope, up to `N` one-turn attempts and all disclosed time/usage limitations. Do not ask
for another confirmation at each ordinary slot. Fresh live source/account/model/turn/time permission
and missing review/freeze evidence remain separate prerequisites; document/CI approval is not that
permission. No current content ID or caller-supplied decision authenticates a human.

All stored clock values and differences use integer nanoseconds: convert each seconds value below
by multiplying by `1_000_000_000`. In particular,
`dispatch_deadline_ns=m_accept_ns+W_seconds*1_000_000_000`; the confirmation and discrepancy limits
are `300*1_000_000_000` and `5*1_000_000_000` respectively. The following equations use seconds as
readable shorthand, never unconverted arithmetic against `monotonic_ns()`.

Proposed rules for a later single-owner coordinator are:

1. Fix preview creation `m0=monotonic_ns()` and wall-clock `w0` in one process. Accept exactly one
   matching batch decision only while `0 <= m-m0 < 300 seconds`. Decline, invalid/stale decision or
   expiry is terminal. No automatic prompt renewal, timestamp refresh, restart, import or resume.
2. At acceptance fix once `dispatch_deadline=m_accept+W`, where `W=60+N*(T+10)` seconds. `N` is the
   complete 14/28/42-slot schedule, never a success count. Maximum windows at `T=120` are 1,880,
   3,700 and 5,520 seconds. The `+10` allows nominal two-group cleanup waits, not a completion promise.
3. Use the original planner order and one concurrent slot. Revalidate full candidate/recipe before
   reservation and before turn write; check time at both points. Reserve consumes that slot before
   any process starts. Mark `turn_send_state=attempted` immediately before the first possible write,
   without an intervening await. Uncertain write/acknowledgement never replenishes the slot.
4. New reservations/sends require `m < dispatch_deadline`. Expiry before send leaves that slot and
   every unsent slot `skipped-expired`, with attempted-send state recorded separately. If already
   sent before expiry, drain that slot under its original `T`/cleanup limits and retain its result;
   expiry is not permission to extend its timer or start another turn.
5. Every checkpoint uses nondecreasing monotonic time. Relative to the **original preview anchors**,
   `abs((wall_now-w0)-(mono_now-m0)) > 5 seconds` is a clock-integrity failure. Never re-anchor this
   check at acceptance or per slot. Cancel any active slot and clean up; skip unsent slots with a
   distinct clock-failure reason. Check at acceptance/reservation/pre-write and during observed
   async progress. Wall time never grants more authority. This detects some observed clock/suspend
   anomalies, not all sleep or real-time overruns; at most five seconds discrepancy is tolerated.
6. Activity, valid output, user delay or partial progress never extends either deadline. Preview
   metadata must bind candidate, recipe, complete limits/order/failure policy and one fresh namespace.
   Immutable offline transition snapshots alone cannot enforce one-use: the future coordinator must
   serially own one in-memory ledger and reject stale snapshot reuse. No persistence/import or
   adversarial-process protection is promised by this source-only design.

### Terminal outcomes and implementation gate

Freeze **stop-on-first-nonvalid observation**: missing, invalid, failed, interrupted or timed-out
slots stop further dispatch even when cleanup succeeds; retain all others as `skipped-stopped`.
Valid null/unknown answers are valid responses and do not stop the batch. Integrity/clock failures and
unconfirmed cleanup are separately fatal; record primary failure and cleanup outcome independently.
Reserve-without-send is not a completed provider attempt. Keep all planned denominators and reasons,
including declined/expired/never-dispatched slots. Do not compare modes for superiority from an
order-dependent truncated batch, or replace failed slots with fresh attempts. Scoring remains separate.

Next offline tests must cover exact recipe/frame hashes and generated-schema-shaped fixtures;
catalog pagination and explicit effort; 300-second boundary and maximum `W`; backward/forward/suspend
clock examples; no re-anchoring; reserve/send expiry races; old snapshot reuse; sent-slot expiry;
null validity; failure/cleanup/skipped denominators. Tests must label clocks/events as synthetic and
leave runtime provenance/provider freshness/execution authorization false. Before process code,
review complete effective config/MCP startup semantics and pin conforming fake-process payloads.
Actual nested-schema/provider support and effective harness context remain unverified. No current
codec, product adapter, v1 values/bytes, metrics/history, release version or #84 checklist is changed.

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
