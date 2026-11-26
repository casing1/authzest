<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_CONTRACT.md">한국어</a>
</p>

# Generated repair contract and opt-in Codex request

[Documentation index](../README.md)

## Status (2026-11-22 KST)

[#151](https://github.com/casing1/authzest/issues/151), under the
[course-release scope](https://github.com/casing1/authzest/issues/150), connects the offline
request/proposal contract to the opt-in `codex-generate` adapter. The
[course demonstration](../guides/COURSE_DEMO.md#evidence-to-cite) records one historical live response
at `34baebc` for the maintained scenario. #151 remains open for final-candidate acceptance.

The preview-only paths render the maintained request offline. The proposal-only command requires
an explicit model and permits one request after exact sharing approval. See the
[generated repair file workflow](../guides/GENERATED_FILE_WORKFLOW.md) for the separate copy, check,
application and recovery stages.

## Reading an archived record in the next candidate

The course demonstration starts with a synthetic FastAPI app. Under the intended policy an owner
can read their active and archived records. The baseline wrongly denies the archived read. Pending records
remain unavailable. The trusted application checks ownership and handles anonymous users and missing records.

Use the following command to inspect the exact sharing request offline. Replace `EXPLICIT_MODEL` with
the model identifier you intend to use. Add `--json` to save a machine-readable preview.

```bash
authzest owner-read-suggest --model EXPLICIT_MODEL --preview-only
```

On a POSIX Python installation, omit `--preview-only` to review the full request and choose whether
to send it using the existing Codex login. Press Enter to decline. The request contains the packaged
availability rule, its policy, and the observed mismatch. Codex is asked to author a new positive
regression for the owner's archived note and a revised rule. The host checks the response structure
and produces both diffs for a proposed change. The CLI reports the test and patch as `not-run`.
With `--json`, interaction goes to stderr and one final result goes to stdout.

### Preparing a private copy

To see what would be copied and the seven expected responses, run this offline command on any supported platform.

```bash
authzest owner-read-suggest --model EXPLICIT_MODEL --prepare-copy --preview-only
```

On supported POSIX source installations, remove `--preview-only` to request a suggestion and then
review the local copy plan. Sharing and creating the directory have separate decisions. Only an
accepted proposal from the current invocation can reach the copy prompt. The plan binds the
installed baseline bytes, current request and sharing decision, exact source and test diffs and
their SHA-256 digests. A digest of installed content does not establish a Git commit. The one-time
copy phrase is bound to a fresh nonce. It must be accepted within 300 seconds. Declining or letting
it expire ends the copy step. Filesystem operations have no hard completion deadline.

The CLI creates a fresh private directory (0700) under the system `/tmp`, resolving the alias on macOS
and ignoring the working directory and `TMPDIR`. It creates each file exclusively (0600), checks its
identity and bytes, and refuses symbolic links.
Diff paths identify the packaged source and proposed test. The copy can contain up to three files,
with at most 4 KiB of validated ASCII per file and 12 KiB of payload in total.

| File                          | Contents at preparation                          |
| ----------------------------- | ------------------------------------------------ |
| `availability.py`             | Exact installed baseline rule                    |
| `test_owner_archived_read.py` | Exact authored regression, staged for inspection |
| `proposed-availability.txt`   | Proposed replacement rule as text                |

The local step runs in the CLI process. It reads no provider credentials, sends no HTTP requests and
executes none of the staged files. There is no worker output. The original checkout stays intact.
If creation fails partway through, inspect the reported directory and file state. The CLI leaves the partial copy in
place and has no reopen, overwrite or retry operation. With `--json`, the copy outcome is in the final
CLI result. The copy contains exactly the three files above. File permissions provide user-level privacy;
another process acting as that user can still change the files.

### Running the packaged regression

From this candidate's checkout, install the test dependencies in your Python environment. The command
runs on POSIX with a regular Python installation.

```bash
python -m pip install '.[owner-read]'
authzest owner-read-rehearse
authzest owner-read-rehearse --json
```

Each invocation exercises the same maintainer-written pytest test against two packaged rules. It first
checks the baseline rule, then checks a reference rule that allows the owner's archived read. In each
phase, the test makes one request through an authenticated owner client. Each of the seven independent
ASGI requests runs in-process against a fresh app instance. The host checks status codes and JSON bodies.

| Phase     | Owner's archived note in pytest                                                      | Independent checks matching intended policy |
| --------- | ------------------------------------------------------------------------------------ | ------------------------------------------- |
| Baseline  | One failed assertion after 403 with `{"detail":"Read denied"}`                       | 6/7                                         |
| Reference | One passed assertion after 200 with `{"id":"archived-note","title":"Archived note"}` | 7/7                                         |

A successful rehearsal includes the expected baseline assertion failure. Collection, setup or teardown
errors fail the rehearsal. The JSON result has kind `owner-read-rehearsal` and provenance
`maintainer-reference`. Its `baseline` and `reference` objects separate the pytest result from the
seven observations. Both rules and the test ship with the package. This command takes no model or file argument.

The host starts each phase with its installed interpreter in a fresh temporary working directory,
using `-I -B` and a minimal environment with pytest plugin autoload disabled. Each child gets a
20-second execution budget and up to 2 additional seconds for local process cleanup. Combined stdout
and stderr are limited to 32 KiB per child. OS startup and filesystem calls can overrun those times.
Both children run with the local user's permissions. Running a generated artifact requires the
separate isolation described below.

### Building the dedicated guest

From the same checkout, choose a new output file for the context. Replace `REVIEWED_LOCAL_T_IMAGE`
with the local reference for the verified pytest image for your platform. Check its identity against
your reviewed image ID and make it available to the Docker builder before building. The context script
writes a tar stream containing only the fixed recipe and guest assets. The recipe uses the test
dependencies already present in the base image.

```bash
python -m scripts.owner_read_image_context > owner-read-context.tar
docker build --pull=false --network=none --build-arg OWNER_READ_TEST_BASE=REVIEWED_LOCAL_T_IMAGE --tag authzest-owner-read:local - < owner-read-context.tar
```

The guest has separate test and control roles. Both receive read-only mounts for the exact
`/input/availability.py` and `/input/test_owner_archived_read.py` files. The control role uses the test
digest to identify the case and runs only the maintained ASGI checks. Before importing the test
packages, the entry checks effective Linux process restrictions, network devices, cgroup limits,
mount flags and input file properties. Those observations describe what the guest can see.
The host must separately verify the image ID, bind sources and removal of both containers.

A Linux arm64 smoke test exercised the packaged test and maintained rule inputs in four fresh
containers. Both roles confirmed the supplied rule and test hashes in each phase. The baseline
pytest run failed its assertion after the owner received 403 with `Read denied` (exit 1). The
reference run passed after the owner received 200 with the archived note (exit 0). In separate
containers, 6/7 baseline and 7/7 reference responses matched the intended policy. The host
confirmed removal of all four containers. Live generation, applying its diff and restoring its
private copy still need to be verified on the same release candidate.

### Host integration for the generated regression

The guest and the host rehearsal supply components for the installed-candidate demonstration.
Connecting the approved copy to these guests, applying the change and restoring the source are
tracked in [#152](https://github.com/casing1/authzest/issues/152). The host integration design follows.

- Bind each plan to the current invocation, installed candidate, request, exact diffs, file identities
  and SHA-256 digests. Read the actual rule and test from the approved private copy, validate their
  fixed grammar and enforce the 4 KiB limit on each artifact. Recheck the inputs before dispatch.
- In each before/after phase, start two fresh guests from a locally present image identified by a
  reviewed digest. One runs the single authored pytest item with the packaged owner client. The other
  runs only the seven maintained ASGI requests on the same captured rule. Give each guest only its
  required inputs as read-only files, a fixed entry point, UID/GID 65532, a read-only root and
  private temporary storage. Disable networking, inherited credentials and capabilities. Restrict
  mounts to the approved inputs. Check the effective isolation before loading either artifact.
- Proposed limits per guest are 1 CPU, 512 MiB of memory, 64 processes and a 32 MiB temporary
  filesystem. Each phase shares a 40-second startup/execution budget and a 256 KiB combined output
  budget across its two guests. Allow a further 10 seconds for cleanup and verify both guests have
  been removed. Record artifact hashes, exit statuses, bounded output and cleanup status privately.
- Require a fresh, single-use decision valid for up to 300 seconds for each before check, exact diff
  acceptance, application, after check and restoration. Proceed to application only after observing the
  specific failing baseline assertion and all seven expected baseline responses. After application,
  require the archived read's exact 200 response, a passing regression and all seven intended responses.
  Before replacing or restoring anything, recheck the private files against the reviewed states.
- Record a missing response, expired decision, changed file, timeout, truncated output or unconfirmed
  cleanup at the affected stage. Preserve user edits. Report restoration only after confirming the
  original source bytes and staged test state. The original checkout stays outside these operations.

### Private session implementation

The private `OwnerReadFileSession` coordinates one current validated proposal through copy,
before, exact diff, apply, after and restore decisions. It is available to a trusted host
coordinator and is connected to `owner-read-suggest --file-workflow --runtime-config`.
The public `owner-read-suggest --prepare-copy` prepares the three inspection files.

Each stage displays the full current request, proposal, exact diffs, previous observations,
private file identities and a session-bound plan ID. A decision is single-use and expires after
at most 300 seconds. The session rechecks the current inputs and checks time after validation.
A successful baseline needs the specific archived-owner assertion failure and all seven baseline
responses. Application and restoration each require their own decision. A failed after comparison
can offer a separate restoration decision when both guests have confirmed cleanup and the copy
still matches the reviewed state. Unconfirmed guest cleanup preserves a recovery-required result.

`OwnerReadWorkspace` adopts only the freshly prepared copy and adds `record.json`. It verifies
the private directory, all three artifacts, file identities, permissions, link counts and bounded
bytes before every transition. A durable pending-operation journal precedes each source replacement.
The final journal is written after source readback and directory synchronization. A journal or
replacement failure retains the files and reports uncertainty. User edits, changed paths, symlinks,
extra files and changed staged test or proposal bytes refuse a write. Restoration confirms the
creation-time baseline bytes while preserving the staged regression test. Concurrent writers under
the same OS account must be excluded because atomic rename does not provide compare-and-swap.

The phase comparator validates two supplied guest captures with matching source/test hashes and
current phase-plan identity. It checks the inner pytest lifecycle and exact HTTP response, then
compares the independent observations. Both guest outputs share a 256 KiB allowance. Their bounded
stdout and stderr are retained as base64 in the detached result. The journal retains observation
hashes and small stage metadata. The caller must retain the complete final result for the private
evidence record. Supplied capture validation establishes consistency of observations. A production
runtime dispatcher must also establish their origin, effective isolation and cleanup.

Temporary-file and fake-dispatcher tests cover the complete sequence, separate decisions and expiry,
stale proposals, user edits, malformed or substituted evidence, independent-control mismatches,
cleanup uncertainty and durable-write failures. These tests execute no proposed source or test code.
The complete CLI path has also been checked with a maintained proposal and four real isolated Linux
guests. It observed the baseline assertion failure with 6/7 intended-policy matches, applied the exact
change to a fresh copy, observed a passing regression with 7/7 matches, and restored the original
source bytes. All four guests were removed. This proof uses a maintainer-authored adapter fixture.
An installed-candidate proof with a real Codex-authored response uses its own current sharing
and file-stage decisions. Retain its full evidence privately.

### Running the approved copy workflow

Use a POSIX Python installation and a reviewed, locally provisioned owner-read image. Docker Desktop
or a rootful Linux Docker daemon must provide cgroup v2, seccomp, memory/swap/process/CPU limits and
the fixed guest controls. The image build procedure appears above. The operator reviews the image
contents and chooses its immutable ID. Runtime metadata comparison checks the declared configuration.
Image provenance remains an operator trust input.

Store the runtime JSON as a private, regular, single-link file with mode `0600`. All paths must be
absolute and resolved. Parent directories must be owned by root or the current user and protected
against group/other writes, with the usual sticky temporary-directory exception. On macOS,
`/Applications` can be group-writable. A byte-identical copy of the reviewed Docker CLI in a private
`0700` directory can supply `docker_executable`; record the copied file's SHA-256. The client must be
executable and the Unix endpoint must refer to the reviewed local daemon.

```json
{
  "schema_version": "1.0",
  "docker_executable": "/ABSOLUTE/PRIVATE/docker",
  "docker_sha256": "REVIEWED_64_CHARACTER_LOWERCASE_HEX",
  "endpoint": "unix:///ABSOLUTE/LOCAL/docker.sock",
  "daemon_id": "REVIEWED_LOCAL_DAEMON_ID",
  "image_id": "sha256:REVIEWED_64_CHARACTER_LOWERCASE_HEX",
  "platform": "linux/arm64"
}
```

Replace the example values with the reviewed local values. `linux/amd64` is also supported. The
workflow creates an empty private Docker configuration and passes a fixed environment to its CLI
children. It pins and rechecks the runtime file, Docker executable and Unix socket. Runtime paths,
metadata and captured logs stay outside the model request.

```bash
authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --preview-only
authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json
authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --json
```

The offline preview displays the source-sharing request and full runtime review. The active command
first requests a fresh `runtime` decision, then performs bounded read-only daemon/image preflight
before requesting sharing approval. The current validated model response is the only proposal input.
A `proposed-change` then presents separate copy, before, diff, apply, after and restore plans. Each
plan includes the runtime pins, current artifact identities and previous observations. `cancel`
stops the workflow and preserves any recovery requirement. `no-change`, `unknown` and `refused`
finish without allocating a copy or starting guests.

The human result shows before/after regression status, independent matches, file application,
restoration and recovery. `--json` writes one final document on stdout; review packets and prompts
use stderr. The result preserves the bounded phase captures and runtime observations. Privately
retain that complete result and the reported copy/staging directories for inspection. Local
filesystem and process-start operations have no universal wall-clock guarantee. A failed or
interrupted cleanup retains uncertainty and refuses further source transitions.

## Offline input preview

From a source checkout installed with this change, these commands display the fixed request without sending it:

```bash
authzest generation-preview
authzest generation-preview --json
```

The default output displays the full prompt and response schema with an explicit no-generation notice. JSON mode prints one `generated-repair-request-preview` document with `status: "preview-only"`, `model_invoked: false`, `applied: false`, and `execution_status: "not-run"`. There are no model, repository-path, or execution options. This is an input preview, not a generated proposal or a live-generation workflow.

## Opt-in request workflow

`codex-generate` requires `--model`; optional `--timeout-seconds` defaults to 120 and must be greater than zero and at most 120. These portable examples display the complete offline sharing preview only; replace `EXPLICIT_MODEL` with the intended exact identifier when reviewing a real request:

```bash
authzest codex-generate --model EXPLICIT_MODEL --timeout-seconds 120 --preview-only
authzest codex-generate --model EXPLICIT_MODEL --timeout-seconds 120 --preview-only --json
```

Without `--preview-only`, the active POSIX path first displays the exact maintained source/policy/declarations, host prompt and output schema, then requires a fresh request-specific sharing confirmation. Declining, cancelling, or an invalid confirmation does not approve sharing. Previewing is not consent. The workflow uses a trusted local Codex `0.153.0` installation and its existing ChatGPT login; Codex adds its own harness context.

An approved request makes one adapter attempt, without AuthZest retry or model fallback. Its requested timeout is at most 120 seconds, with cleanup handled separately; this is not a full end-to-end wall-clock guarantee or a hard cap on Codex-internal retries, tokens, or spending. Do not interpret missing usage as zero.

The default final output starts with a compact result summary instead of repeating the full transport envelope. A valid `proposed-change` yields complete proposed source/test text and host-derived diffs/hashes; nothing is applied or tested yet. `no-change`, `unknown`, and `refused` remain distinct. Transport metadata is host-bound context that does not independently attest model authorship, and mock responses do not prove actual generation.

Final JSON uses `kind: "codex-generated-repair-workflow"`. Outer `status` describes the workflow (`generation-ready`, `not-shared`, `preview-changed`, or `generation-failed`), while `proposal_status` separately describes the proposal. `generation-ready` means a validated response, not a successful repair. `generation` retains the transport envelope and `proposal_preview` the inert host-composed preview. `execution_status`, `patch_application`, and `restoration_status` remain `not-run`, and `applied` remains false. `application_turn_attempts` counts local adapter calls, not accepted or billed provider turns.

### Reading the result

The final human-readable view shows workflow/proposal status and explicit application, execution, patch, restoration, and authorization states first. Missing state is reported as unknown, not inferred to be successful or not run. It then lists changed files, rationale, assumptions, uncertainties, and limitations, followed by the complete proposed source, test, and diffs once each. Long identifiers, hashes, and the redundant transport envelope are omitted from this default view, not from the complete JSON result.

Generated text and code remain untrusted. Each displayed line is prefixed and ASCII-escaped so terminal controls, bidirectional characters, and non-ASCII text cannot silently change the presentation. There is no raw or unescaped display option.

- `--details` appends the complete final JSON after the human-readable result without making another request.
- `--json` emits exactly one complete final result or offline preview on stdout; interactive sharing previews and prompts go to stderr. Combining `--details` with `--json` leaves the JSON unchanged.
- Sharing consent is not abbreviated: the full authoritative sharing preview, including `--preview-only`, remains complete and unchanged by `--details`. Read it before entering a fresh sharing confirmation.

These are presentation options only. They do not approve sharing, execute generated code, apply a patch, restore files, or establish generation or repair acceptance.

## Maintained scenario

[The scenario source](../../src/authzest/codex/generated_repair_scenario.py) contains one synthetic `app.py`, one `GET /documents/{document_id}` route, and in-memory documents owned by `alice` or `bob`. Its deliberately missing ownership check is a demo condition, not a production vulnerability finding. `X-Demo-Actor` is caller-controlled fixture data, **not authentication or a trusted identity**.

The assistant-authored policy is **pending maintainer review**: an owner keeps the existing successful response; a non-owner receives 403 without document disclosure; missing/unknown actors receive 401; and a valid actor requesting a missing document receives 404. These are proposed expectations and source declarations, not observed HTTP results or an independently approved reference set.

The requested output is a newly authored defensive pytest file, `tests/test_generated_ownership.py`, plus complete replacement source for `app.py`. Paths are fixed labels, not arbitrary filesystem targets. `test_before = "absent-in-planned-copy"` describes a planned copy, not a filesystem observation. No registered after-source solution or prewritten test is supplied as a choice.

## Request, proposal, and preview

[The contract API](../../src/authzest/codex/generated_repair.py) exposes immutable request, proposal, and preview wrappers:

- `build_generated_repair_request()` and `validate_generated_repair_request(raw)` bind the maintained source, policy, declarations, prompt, and response schema.
- `generated_repair_prompt(request)` and `generated_repair_output_schema(request)` describe the requested structured output; they do not send it.
- `validate_generated_repair_proposal(raw, request)` checks an untrusted response against that request.
- `prepare_generated_repair_preview(proposal, request)` derives the source/test diff and content bindings on the host; it does not trust a model-supplied diff or apply one.

Only `proposed-change` contains a proposal: fixed `source_path`, matching `before_sha256`, complete `after_text`, fixed `test_path`, and new `test_text`. The other statuses, `no-change`, `unknown`, and `refused`, require `proposal: null`; `unknown` and `refused` also require an uncertainty. A proposal is not evidence that any model produced it.

Each generated source/test text is limited to 16,384 UTF-8 bytes before parse-only AST validation, with at most 4,096 AST nodes and depth 64. JSON, prompt, and preview data have a 256 KiB bound. Current contract bindings are revalidated; the host computes LF-aware source/test diffs and hashes. Preview state remains unverified, not applied, and execution not run.

The object-root output schema is a shaping candidate, not the authoritative validator. The host additionally enforces status/proposal relationships, required uncertainty, unique evidence IDs, exact UTF-8 byte limits and AST budgets. See the [structured-output schema guidance](https://developers.openai.com/api/docs/guides/structured-outputs). Candidate compatibility requires an observed response from the pinned App Server.

## What validation does not prove

- AST parsing is not compilation, test collection, an OS sandbox, semantic validation, or a safety check. Syntax-valid code may violate the requested limits or policy.
- IDs and hashes bind content; they do not authenticate a reviewer/model, prove freshness, or authorize sharing, execution, application, or recovery.
- A model-written test passing against the model-written repair is not independent evidence of a correct fix. The proposal contract uses parse-only validation.
- Prior registered-template approvals do not authorize this new scenario or generated code. No current artifact is claimed to be an accepted live trial, a verified repair, or a stable-release gate completion.

## Verification and result interfaces

[#152](https://github.com/casing1/authzest/issues/152) tracks candidate acceptance for the
[generated repair file workflow](../guides/GENERATED_FILE_WORKFLOW.md). The
[offline verification foundation](GENERATED_REPAIR_VERIFICATION.md) defines the maintained comparison
and can evaluate supplied observations. The active workflow combines that comparison with separately
decided stages and records test, infrastructure and recovery outcomes.

The [local viewer](../guides/RESULT_VIEWER.md) from
[#153](https://github.com/casing1/authzest/issues/153) displays the final JSON read-only. The CLI
owns sharing and stage decisions. The adapter uses the current-turn `outputSchema` field described
in the [Codex App Server documentation](https://learn.chatgpt.com/docs/app-server).

## Opt-in local AI workflow design (23 November 2026)

[#189](https://github.com/casing1/authzest/issues/189) connects the existing owner-read engine to a
local interactive GUI. This section is the design for implementation review. It grants no new live
model call, generated-artifact execution, patch application, or release acceptance. Earlier one-turn
live approval is consumed. Development uses temporary files, scripted adapters and mocked phases;
new live acceptance requires separately bounded authority.

### Launch and request boundary

The ordinary `authzest ui` and the default ASGI application remain read-only. An operator explicitly
enables the new route with `authzest ui --ai-runtime-config /ABSOLUTE/PRIVATE/runtime.json`.
The runtime path is selected at server startup and validated by the existing owner-read loader.
Active mode accepts only numeric loopback `127.0.0.1`, one application instance and no reload or
multiple workers. It supports the existing POSIX non-frozen source installation and the fixed
owner-read scenario. Requests cannot select source files, runtime paths, executable paths, shell
commands, replacement code, saved proposals, or an existing copy.

The launcher creates a fresh 256-bit capability token. Its local launch URL carries the token only
in the `authzest-ai` URL fragment. The browser removes that fragment immediately and keeps the token
in memory, sending it as `X-AuthZest-Token` on every `/api/ai` request. It is absent from query strings,
cookies, persistent browser storage, static assets and ordinary response/log metadata. The launch
URL is private. Closing or restarting the server invalidates the capability; it does not identify a
human or attest that someone read a plan.

Every active request must match the configured numeric Host and port and the launch token using a
constant-time comparison. Mutating requests require the exact same Origin and a bounded JSON body;
cross-origin, `null` Origin and mismatched Host requests are refused. A GET may omit Origin, as
same-origin browser fetches commonly do, but any supplied Origin must match and the token remains
mandatory. There is no permissive CORS exception or Vite development-origin exception. Active
responses use no-store and browser framing/referrer/content-type protections. Default page loading,
health, static scans and result imports do not invoke Codex or Docker.

### Controller and decisions

One controller owns one current run and retains one finished result. It runs the existing
`run_suggestion` file workflow in an owned thread with its own event loop. The core adapter,
runtime preflight, source grammar, independent controls, workspace and restore machinery remain the
execution authority. The bridge supplies the engine's existing `emit` and `read` interfaces.

An emitted packet is retained as the complete current plan. A pending decision contains a fresh
server prompt ID, stage, prompt text, complete plan and remaining time. The client submits that
prompt ID and the exact typed answer. The server consumes a matching current prompt atomically once.
Duplicate, stale, cross-run, mismatched and oversized decisions are refused. The browser cannot
replace the plan, supply an expected answer, approve future stages, extend the original maximum
300 seconds, or bypass the core's file, hash, runtime and deadline rechecks. There is no automatic
approval or continuation from an imported JSON record.

Runtime review, sharing, copy, before, exact diff, apply, after and restore remain separate current
decisions. Starting a run does not approve sharing or any later stage. A completed controller job
only means the engine returned; proposal, comparison, cleanup and recovery statuses determine the
recorded outcome. No-change, unknown and refused proposals remain valid without a new copy.

### Local API contract

All routes below are under `/api/ai` and require the active launch capability.

| Method | Route                      | Body or result                                                                                               |
| ------ | -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| GET    | `/session`                 | `{ "run": snapshot_or_null }`                                                                                |
| POST   | `/runs`                    | `{ "model": exact_model, "timeout_seconds": value }` → snapshot; timeout is optional and at most 120 seconds |
| GET    | `/runs/{run_id}`           | Current snapshot                                                                                             |
| POST   | `/runs/{run_id}/decisions` | `{ "prompt_id": current_id, "answer": typed_text }`                                                          |
| POST   | `/runs/{run_id}/cancel`    | `{}` → stop-request state                                                                                    |
| GET    | `/runs/{run_id}/result`    | Complete final JSON attachment when available                                                                |
| POST   | `/diagnostics`             | `{}` → coarse version/login readiness only                                                                   |

A snapshot contains `run_id`, monotonically increasing `revision`, `state`, `events`, `pending`,
`view`, `view_error`, `result_available`, `failure` and `cancel_requested`. State is one of `running`,
`waiting`, `stopping`, `finished` or `failed`. Events contain `sequence`, `stage` and `status`.
`pending` is null or contains `prompt_id`, `stage`, `prompt`, `plan` and `remaining_seconds`.
Polling shows bounded host activity, not an invented model token stream or raw provider/account logs.

The controller bounds a complete current plan to 2 MiB, the final result to 4 MiB and activity events
to 256. It never truncates a plan into something approvable or evicts an active run to admit another.
Only a run whose owned worker has ended can be replaced. The final display reuses the existing read-only projection;
projection failure is reported through `view_error`, with no fabricated successful view. A complete
bounded result remains available through the authenticated download route. The browser obtains the
attachment through authenticated fetch and a Blob, so no token appears in a download query string.
The API accepts no arbitrary server-side save path. Imported records cannot resume a run.

Diagnostics may inspect the trusted local Codex installation with the existing bounded check, but
return only authenticated/unauthenticated/unknown and version readiness. Raw command output, email,
account identifiers, credentials and auth files are not returned. The workflow uses the existing
Codex ChatGPT login. This design adds no API-key form or OAuth login endpoint.

### Cancellation, shutdown and verification

Cancellation latches a stop request and wakes a pending read with `cancel`. It never kills an owned
thread midway through a source operation. A running model call or synchronous guest phase may need
its existing timeout and cleanup before the next safe checkpoint. `stopping` does not mean the
processes have already ended. The active lease remains held until the worker actually finishes.

Closing or reloading a browser neither approves a prompt nor starts another run. Decisions retain
their original deadline. An interruption after copy application can retain recovery-required state;
`cancel` after application stops without a restore decision. Declining the after check with an empty
answer can offer the core's separate, fresh restore decision when the recorded state permits it.
The bridge never restores automatically without that decision. Server shutdown requests
cooperative stopping and accounts for the owned worker and cleanup. An unfinished or abandoned
operation cannot be reported as successful or silently release the active slot.

Offline regressions cover launch opt-in, Host/Origin/token/content-type enforcement, overlapping
starts, exact current decisions, replay/expiry, disconnects, cancellation and uncertain cleanup,
recovery, complete mocked engine flow, JSON download and English/Korean rendering. These checks
execute no newly generated source or test and make no real Codex or Docker guest call.
