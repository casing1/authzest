<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/CODEX_FIXTURE.md">한국어</a>
</p>

# Opt-in Codex review of an owned fixture

[Documentation index](../README.md) · [Offline copy demo](FIXTURE_APPLICATION.md) · [AI contract](../reference/AI_CONTRACT.md)

## Scope and current evidence

[#50](https://github.com/casing1/authzest/issues/50) adds a source-checkout command for one maintained
configuration fixture. One approved live CLI check on `42ff108` **PASSED** on 2026-09-12: validated
draft, separate exact-phrase decisions, copy application, and restoration. The assistant entered the
phrases within the user-approved test; this is not independent human-approval attestation. This feature
is not in the published alpha.2 binaries and does not complete [#35](https://github.com/casing1/authzest/issues/35).

AuthZest's task/source payload contains a previewed, packaged `main.py` snapshot, its source evidence,
a declared policy, and one question. The only accepted source draft changes `debug=True` to `debug=False`, preserving every
other character. This is a configuration demonstration, not an authorization finding, exploit PoC,
generated regression test, or verified security fix. There is no arbitrary repository/path input.

The ordinary `scan` command stays offline. The existing offline proposal and copy demos remain scripted,
not AI-generated. General repository AI review and arbitrary patching remain unsupported. #52's optional,
separately approved source-configuration check is the default. #54 adds an opt-in fixed runtime plan
selected by `--runtime-check`, described in the [runtime guide](RUNTIME_VERIFICATION.md). Neither check
adds a model call. #54's bounded live source acceptance passed, as recorded in the runtime guide;
final PR/release gates are pending. #35 stays open and alpha.2 is unchanged.

## Run from current source

Use a trusted local Codex **0.153.0** installation with an existing ChatGPT login managed by Codex.
This adapter is version-pinned; other versions are not declared compatible. The live copy workflow is
POSIX-only and does not extend Windows scan support to this command. Choose a model available to your
Codex account; `MODEL` below is a placeholder, not an automatically selected model.

```bash
authzest codex-fixture --model MODEL --timeout-seconds 120
```

The timeout defaults to 120 seconds. Before starting any Codex process, the command displays its exact
`HOST_INSTRUCTIONS`, task/source payload, requested model, and request ID and requires explicit
source-sharing approval bound to that ID. Codex adds its own harness context; this preview does not
claim to show the model's entire context.
Type the displayed `share <request_id>` phrase exactly to approve this request.
Declining or cancelling this step starts no provider process. A successful login never grants consent
to transmit source, apply a patch, or execute verification.

Codex manages its existing login; AuthZest does not read API keys, tokens, or credential files.
See the official [authentication guide](https://learn.chatgpt.com/docs/auth) for Codex login behavior.
The [App Server documentation](https://learn.chatgpt.com/docs/app-server) describes its managed ChatGPT
authentication; the restrictions here are AuthZest's narrower fixture workflow, not general Codex limits.

## At most one model turn, separate file approval

After sharing approval, the adapter uses the supported local App Server for at most one application-issued
turn. The summary's `application_turn_attempts` counts adapter invocations, not dispatched model turns
or billing events: preflight can fail before `turn/start`. AuthZest performs no application retry,
fallback, or model substitution. Codex's internal transport
retries may still occur. The timeout is not a hard token or monetary limit; usage may be incurred before
a failure or cancellation, and missing usage measurements must remain unknown.

Only a same-thread, same-turn `error` with `willRetry: true` and a recognized
`responseStreamConnectionFailed` or `responseStreamDisconnected` variant may wait for recovery within
the existing deadline, byte, and event limits. Its HTTP status must be absent/null, `200`, `408`, or
`500`–`599`. The preview's `max_accepted_retry_notifications: 3` limits observed eligible notifications,
not provider attempts or cost. A fourth notice, other/fatal errors, authentication/policy failures,
malformed data, and identity/tool/context violations stop the flow. No new turn, application retry,
or model change is issued.

Each accepted retry notice discards prior buffered final output and usage. Success requires a fresh
validated final response and successful turn completion; usage remains unknown without a new usage
notice. `provider_retry_notification_count` records observed notices only after a validated draft;
failure leaves it `null`, not zero or a provider-attempt/billing count. The official
[App Server errors page](https://learn.chatgpt.com/docs/app-server#errors) lists broad error categories,
but does not document `willRetry`. Its wire shape is taken from the installed Codex 0.153.0-generated
`ErrorNotification` schema; AuthZest's narrower acceptance rules are application policy.

The model receives no tools or environment access; tool requests are rejected. Output is untrusted JSON.
Host validation binds identity and source references and accepts only the exact maintained replacement.
Valid JSON or a correct source citation does not prove that the explanation is true. The host creates
the diff and proposal identity; model text cannot approve its own change.

The transport starts in a clean, empty working directory, accepts only the built-in OpenAI provider
with ChatGPT authentication, and checks effective tool/context settings before the turn. Remote-control
status must be `disabled` in the status read and subsequent notifications; otherwise the flow stops. It limits
protocol output to 256 KiB per line and 2 MiB in total and cleans up its own process group. Runtime
errors are redacted; raw stderr, account email, and conversation transcripts are not saved by AuthZest.
These controls assume a trusted Codex installation, not a sandbox for an untrusted executable.

Model routing is left to Codex's built-in provider for managed ChatGPT login; AuthZest does not force
the API-key endpoint through `openai_base_url`. Both preflight passes reject any non-null effective
`openai_base_url`, including an official URL or an empty string, before creating a thread or turn.
`OPENAI_BASE_URL` is not forwarded. An inherited override is a configuration incompatibility, not
proof of expired credentials; AuthZest does not edit the user's Codex settings. The official
[configuration guide](https://learn.chatgpt.com/docs/config-file/config-advanced) documents the provider
URL override separately from ChatGPT login settings. This check is not network-route attestation.

The requested model identity is checked against the model negotiated at thread start. The summary
records `model_identity_basis: negotiated-thread-model; not independently served-model attestation`.
This is not independent proof of which model served the response.

Recognized generic `warning` notifications are bounded, non-authoritative metadata. The summary
records the observed `provider_warning_count` only after a successfully validated draft, not warning
text. Other paths retain `null` (unknown), not zero. A warning cannot change settings, authorize tools,
approve sharing/application, or supply usage. Malformed warnings, `configWarning`, `guardianWarning`,
non-eligible errors, and unknown notification types still stop the flow.

`thread/settings/updated` is checked separately against the agreed thread boundary: model/provider,
working directory, approval policy/reviewer, read-only sandbox with network disabled, reasoning effort,
and the collaboration-mode model, reasoning, and instruction settings. A mismatch stops the flow;
an informational warning cannot waive these checks.

A valid draft is shown for a separate exact-diff decision. Approval can change only a newly created,
private fixture copy, never the original checkout. Type the displayed `apply <proposal_id>` phrase
exactly; decline/cancel does not apply the draft. After application, the selected check—default
source-configuration or opt-in owned-fixture runtime—is optional and separately approved.
Restoration requires `restore <proposal_id>` and
refuses detected intervening edits; it does not overwrite user work. The copy, before/after snapshots,
and `record.json` are retained for inspection; the workflow JSON summary includes request/proposal IDs
and available usage. The file-operation limits
and failure meanings in the [copy application guide](FIXTURE_APPLICATION.md) still apply.

## Optional source-configuration verification (default)

After copy application and before restoration, #52 displays a fixed plan and requires the exact
`verify <plan_id>` phrase. Sharing or applying does not approve this step. The plan binds the proposal,
applied source identity, and maintained check/worker identities. The check is
`owned-fixture-debug-disabled-v1`; the preview includes the exact worker source, SHA-256, and limits.
These terminal choices are recorded decisions, not authenticated human-approval receipts.

The fixed worker runs in a separate subprocess with a 5-second startup/I/O deadline, a separate
1-second kill/reap cleanup bound, 1 KiB input and 4 KiB output limits. The plan includes
`max_cleanup_seconds`. The host rechecks the applied copy and passes immutable `main.py` bytes to the
worker. The fixed checker accepts only pinned maintained-source hashes, parses the bytes as an AST,
and inspects the declared `FastAPI(debug=False)` configuration. A separate process is not an OS/network sandbox.
It does not import or execute that source, run a server/test/install hook, accept model-generated
commands, or call a provider. Passing proves this bounded source-configuration check, not runtime behavior,
authorization correctness, or a verified security fix.

The worker receives a reduced environment. In a frozen main process only, it preserves the existing
`_PYI_ARCHIVE_FILE`, `_PYI_APPLICATION_HOME_DIR`, and `_PYI_PARENT_PROCESS_LEVEL` unchanged after checking
that they match the current existing executable, the existing `sys._MEIPASS` directory, and level `1`.
It never manufactures bootloader state. This is private-value consistency, not executable/environment
attestation; source-mode workers still drop those ambient values. The 5-second deadline and separate
1-second cleanup limit are unchanged.

This default mode reports `verification_scope: source-configuration` and `verification_status` as `passed`,
`failed`, or `not-run`; its `runtime_verification_status` always remains `not-run`. A normally produced,
plan-bound `verification` record carries the scope, plan/check/worker/source identities, reason, elapsed
time, and exit status. Unexpected workflow failures may omit result details; inspect the retained
record instead of assuming a missing result means success or `not-run`.
Decline/cancel starts no worker and records `not-run`; this intentional skip gives CLI exit `0`
unless a separate workflow step fails.
Worker failure, stale state, or journal failure causes exit `1`, not a verified result. A separate
restoration decision is still offered after a skip or failure when safe. Restoration is not automatic
and does not change a retained verification result: that result describes the applied source hash,
not the restored file. Application, verification, and restoration outcomes remain distinct.
Journal schema `1.1` retains the full `verification_plan` preview, decision, and result when recorded.
`journal_status: recorded` means the host write completed, not authenticated or permanent durability
proof. A write/fsync error produces `unconfirmed` and triggers a best-effort correction to a failure
record; if correction also fails, the retained record may be uncertain. Inspect actual files and the
reported failure rather than trusting an earlier success entry. The journal cannot restart or resume
the session and is not a replay-proof approval receipt.

The existing `scripts.demo_apply` flow is unchanged and remains `not-run`. #52's source-only addition
does not itself complete #35's separately approved runtime verification and failure/recovery acceptance gate.

## Opt-in owned-fixture runtime verification

Select #54's runtime plan explicitly, after setting up the optional dependencies described in the
[runtime guide](RUNTIME_VERIFICATION.md):

```bash
authzest codex-fixture --model MODEL --timeout-seconds 120 --runtime-check
```

The selector is not approval to share source, apply a change, or execute verification. The same separate
`verify <plan_id>` decision is required after application. The fixed worker accepts only the exact
maintained fixture variants and executes the matching bundled constant. It observes `app.debug` and
an in-memory ASGI `GET /health`, with dependency versions recorded as observations. It accepts no
arbitrary source path or model-generated command and starts no TCP/UDP server. This is not an
OS/network sandbox, authorization test, exploit reproduction, or verified security fix.

Runtime sessions use `verification_scope: owned-fixture-runtime` and journal schema `1.2`.
`runtime_verification_status` reflects the recorded check; an unexpected interruption may omit an
uncertain status rather than imply no execution. Missing dependencies are not installed automatically:
`runtime-dependency-unavailable` is `not-run` with CLI exit `1`, unlike an intentional decline/cancel.
Restoration remains independent, and a retained result describes the checked applied hash, not the
restored file. #54's bounded live source acceptance passed, with evidence in the
[runtime guide](RUNTIME_VERIFICATION.md); final PR/release gates are pending. No release or completion
of #35 is claimed.

## Offline configuration-check demo

After editable development setup, from the repository root:

```bash
python -m scripts.demo_verify
```

This source-checkout demo uses a caller-authored mock draft, never Codex or a model call. It presents
separate exact `apply <proposal_id>`, `verify <plan_id>`, and `restore <proposal_id>` decisions for a fresh
private fixture copy and uses the same fixed configuration worker. Follow the displayed IDs; no step
is approved by default. Passing this demo is offline workflow evidence, not live-model performance,
target-code execution, or security-fix verification. Copies and records remain available for inspection.

To select the runtime worker in the same offline, caller-authored mock workflow:

```bash
python -m scripts.demo_verify --runtime-check
```

This variant still makes zero provider calls, but executes the exact maintained fixture after separate
verification approval. It requires the optional dependencies and has the boundaries in the
[runtime guide](RUNTIME_VERIFICATION.md); it is not evidence of a new live-model check.

## Contract compatibility

AI schema `1.1` permits `temperature: null`, meaning no numeric sampling temperature was requested;
the provider manages it. Existing numeric-temperature requests retain schema `1.0`, their identities,
and the existing `AdapterConfig` default of `0.0`. Null is not zero or deterministic generation.
The scan report remains schema `1.2`; no package version or new release is implied by these changes.

Live attempts, end-to-end results, token usage, and failure recovery evidence must be recorded
separately from offline mocks. Unknown usage is not zero; successful mocks alone do not establish live
end-to-end success. The dated history below preserves the state at each step, including superseded
pending/Draft records. The successful live check below predates #52; newer offline work is labelled separately.

## Historical development validation — 2026-09-11

Local Python 3.12.7 validation passed 1,129 tests in 112.99 seconds, including 394 new tests. The transport
subset includes 242 offline tests with actual fake-server subprocesses and CLI approve/restore and decline flows.
Timeout and cancellation checks observed termination of the test wrapper and its descendant.
Documentation checker tests (14), language/link checks, Ruff, and frontend lint/format/build passed.
The rebuilt wheel and macOS ARM64 development binary exposed the command and cancelled safely on EOF
before sharing. The native inventory smoke passed 14 checks against the selected and relocated binary,
without executing Codex or target source. These artifacts were not published and reused local build dependencies.

A metadata-only preflight against Codex 0.153.0 confirmed ChatGPT login, disabled remote control,
two disabled inherited MCP servers, and a fresh read-only thread with no instruction sources or
runtime workspace roots. It issued **zero model turns** and sent no fixture source. Live model
generation remains **PENDING**; these checks do not establish live end-to-end success or a verified fix.

## Approved live attempts — 2026-09-11

This is the historical record through `807ada2`, before the bounded same-turn recovery change.
The user approved an initial maximum of three live attempts, then two additional attempts. All five
approved host attempts were used; this does not prove five dispatched or billed model turns. None
produced a validated draft. Attempts 1–4 stopped at warning/settings
metadata interoperability checks. These were validation attempts within those explicit approval
limits, not application retries or permission for further calls.

Attempt 5 accepted the bounded generic warning as non-authoritative metadata, then received a Codex error
with `codexErrorInfo: responseStreamDisconnected` and `willRetry: true`. The adapter stopped with the
redacted `Unexpected Codex event` failure. Recorded local latency was `12357.580 ms`. The provider's
retry indicator does not prove that a retry completed or give AuthZest permission for another call;
Codex-internal retries have no AuthZest-enforced hard cap.

Usage remains unknown for all five attempts, and no successful-draft warning count was recorded.
No live human apply/restore flow was reached, no file
application or restoration occurred, and the original checkout remained unchanged. The fake-server
approval/restoration tests above are separate evidence, not a successful live demonstration.
`verification_status` remains `not-run`, live end-to-end validation remains **PENDING**, and
[PR #51](https://github.com/casing1/authzest/pull/51) remains a draft without a merge or release.
There are no remaining approved live attempts; further calls require fresh user approval.

## Offline follow-up — 2026-09-12

The implementation and tests in this offline follow-up made **zero live calls**. Python 3.12.7 passed 1,171 tests in
153.54 seconds, adding 42 tests since the historical 1,129-test run. Transport tests total 276 (+34),
and CLI tests total 66 (+8). Ruff, frontend lint/format/build, 14 documentation checker tests, and
language/link checks passed.

The rebuilt native binary passed all 14 inventory checks at the existing 45-second per-command limit,
including the relocated copy. Independent wheel/native artifact checks passed at the unchanged
30-second limit: command help, pre-sharing EOF cancellation, retry-notification limit `3`, and an
unknown (`null`) retry counter. An earlier parallel artifact run hit the 30-second timeout; the cause
was not established. These checks executed neither Codex nor target source. The original fixture hash
and clean main checkout were unchanged; no artifacts were published.

These offline results do not convert the five historical failures into successes or grant another live
attempt. Live end-to-end validation remains **PENDING** and PR #51 remains a draft.

## Fresh approved live attempt — 2026-09-12

On `ca97ab1`, one newly approved host attempt (maximum 120 seconds, same fixture/login) returned
`draft-failed`/exit `1` in `11610.537 ms`. A diagnostic observer identified `responseStreamDisconnected`
with nested HTTP `401` and `willRetry: true`; production correctly stopped with
`Codex reported a non-recoverable HTTP status`. A retry flag cannot override authentication rejection.
Returned identity, usage, warning/retry counts, application, and restoration were all `null`;
`verification_status` stayed `not-run`, and an independent hash check confirmed the original unchanged.
Codex 0.153.0 subsequently reported a stored ChatGPT login, not proof of server acceptance. This does
not establish credential expiry, quota exhaustion, or model unavailability. No logout, reauthentication,
API-key change, or further attempt was performed. The fresh one-attempt approval is exhausted: six
approved host attempts in total have failed before a validated draft, not proof of six billed turns.
Live validation remains **PENDING**; PR #51 stays draft, with no merge or new call authorization.

## After user reauthentication — 2026-09-12

The user completed login again. CLI login status and a read-only App Server `account/rateLimits/read`
succeeded without a model turn or fixture-source transmission. The user then approved one additional
attempt with the same fixture, `gpt-6-astra`, managed ChatGPT account, and 120-second limit.
On `573f7a3` (runtime unchanged from `ca97ab1`), it failed after `11086.934 ms` with
`responseStreamDisconnected`, nested HTTP `401`, and `willRetry: true`. The adapter stopped;
`status: draft-failed`, exit `1`, null identity/usage/warning/retry/application/restoration fields, and
`verification_status: not-run` were preserved. The original fixture hash remained unchanged.
All seven approved host attempts have ended before a validated draft; that is not a billed-turn count.

Inspection found that AuthZest had forced the built-in model provider to `https://api.openai.com/v1`
despite requiring ChatGPT login. Account-query success and generation failure are consistent with a
routing mismatch, but the exact cause of the 401 is **not established**. The forced override was
removed and inherited overrides now fail preflight. The installed 0.153.0 App Server accepted the
revised boundary and its account/limits metadata reads succeeded, again with zero model turns and
no fixture source sent. No credentials or user settings were changed by AuthZest.

The corrected source passed all 1,203 offline Python tests, including 32 new endpoint cases
(308 transport cases in total), plus Ruff and the 14 documentation checker tests. A separate
restricted transport run could not execute `ps` in two existing descendant-cleanup checks; both
passed unchanged with the required local process permission, as did the full suite. No test timeout
or assertion was relaxed. Earlier wheel/native artifact checks predate this correction.

There has been no model generation after this routing correction. The one-attempt approval is
exhausted; no eighth attempt, merge, or release was made. PR #51 remains draft and #35 stays open.

## Successful approved CLI check — 2026-09-12

After fresh approval for one attempt with the same public fixture, managed ChatGPT account,
`gpt-6-astra`, and 120-second deadline, runtime commit
`42ff1082d6059516b865c2db1b0ebce7ce997763` returned a validated draft. The draft phase took
`13580.995 ms`; reported usage was `input_tokens: 5573` and `output_tokens: 315`, with
`provider_warning_count: 1` and `provider_retry_notification_count: 0`. This is provider-reported usage
for this success, not a total for earlier failures or an independently verified billing record.
Model identity remains negotiated-thread metadata, not served-model attestation.

The assistant inspected the host-derived one-line diff, entered the separate exact application and
restoration phrases within the user-approved E2E test, and observed `status: completed` / exit `0`.
The application result was `applied: true`; the restoration result was `restored: true` for the same
proposal and fresh private copy. These CLI choices demonstrate the decision flow, not independent
human review or authenticated user-approval receipts.

- Request: `request-a04278a94923c955b1e807ee2cd81a1b8b4a062da58f3e7e371b3e2a4ffce34a`.
- Proposal: `proposal-ce153ad1b2ba0b6b427e324403bb127c07aca830ad728e00c68e77a20c34ea04`.
- Before/restored SHA256: `c10770594e77cd1c1ec93c19ef2b810aea34ed873d8dbf392b57e50a1c2729df`.
- Applied SHA256: `e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe`.

A direct hash check before restoration observed the applied bytes. Independent read-only inspection
then matched the restored file and before/after snapshots, journal phase and decisions, and the
unchanged original/worktree fixture hashes. The journal recorded applied then restored; it and the
snapshots remain in the host-created private temporary workspace. No credentials or account profile
were included in this record.

This is the eighth approved host attempt overall: seven earlier failures and this one success, not a
count of billed/dispatched provider turns. There was no application retry or additional model call.
The first post-routing-correction attempt passed without the prior 401; this supports the routing
diagnosis but does not independently trace the earlier HTTP requests. The approval is exhausted.
No release is implied. This recorded #51 run retained `verification_status: not-run`; it did not
exercise the later #52 source-configuration check. In that historical snapshot, source/test execution,
security-fix verification, arbitrary repository AI and the remaining #35 work were unimplemented.

Development wheel and macOS ARM64 artifacts were rebuilt from a fixed `42ff108` runtime snapshot.
Both passed help, full preview and pre-sharing EOF cancellation with zero Codex processes/model turns;
selected/relocated native inventory smoke passed 14 checks. Existing 30-second artifact and 45-second
inventory per-command limits were retained. A native check initially hit the host sandbox semaphore
restriction, then passed unchanged with the needed local permission. These unpublished builds reused
local dependencies; they do not establish clean-device installation, upgrades, signing, notarization,
other-OS support or a live model run from the packaged artifacts.

## Source-configuration extension — offline validation, 2026-09-12

#52's runtime `52311f99a28711d7d362cfd313a7dfde8571f785` passed 1,350 tests in 152.04 seconds.
Ruff lint and formatting (124 Python files), frontend clean install/lint/format/build, 14 documentation
checker tests, and 36 Markdown files / 17 language pairs / 460 links / 82 shell-block checks passed.
Workflow validation used offline fixtures and mocks only: no actual Codex, account, model, or provider-network call.

The source-checkout terminal demo applied the fixture change, passed the fixed AST configuration check
in `23.572 ms`, and restored the copy. Independent checks confirmed the applied and restored hashes
shown above and preservation of the original. The assistant entered exact phrases within the test scope;
this is not independent human approval or a new live-model result.

A rebuilt macOS ARM64 development binary (SHA256
`b86d7da8c33bb61ffb073dc6396aaf4cbae90f845dd3b01bde4d59a80d3ebc55`) passed the production
parent-to-worker flow using a fake Codex server: separate share/apply/verify/restore decisions, exit `0`,
and empty stderr. Bootstrap took 14.732 seconds within the external 30-second limit; the child check
took `131.652 ms` within its unchanged 5-second deadline and separate 1-second cleanup bound.
The whole flow took 15.399 seconds. Actual copy application/restoration and original preservation were
independently confirmed. Fake identity and token fields are scripted test data, not provider usage.

Earlier cold worker starts timed out twice at 5 seconds; a parallel help check also hit 30 seconds,
then passed independently. The minimal validated bootloader-context correction above addressed the
packaged worker startup without relaxing deadlines. The final harness initially hit a host semaphore
restriction before application launch, then passed unchanged with the necessary IPC permission.
The same final binary passed 14 inventory-only smoke checks (7 selected, 7 relocated) at the unchanged
45-second per-command limit; its help check also passed within 30 seconds. The native configuration
check evidence covers the applied `debug=False` source, not a native before-change failure check.

These are unpublished local development artifacts, not clean-device, cross-platform, signing, upgrade,
or live-model package acceptance. #52's source-configuration acceptance is complete; that historical
run retained runtime verification `not-run`. #35 stays open, and no new release or verified security fix is claimed.
