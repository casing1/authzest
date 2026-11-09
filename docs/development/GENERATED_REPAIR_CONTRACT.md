<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_CONTRACT.md">한국어</a>
</p>

# Generated repair contract and opt-in Codex request

[Documentation index](../README.md)

## Status — 2026-11-09 KST

[#151](https://github.com/casing1/authzest/issues/151), under the [course-release scope](https://github.com/casing1/authzest/issues/150), now connects the offline request/proposal contract to an opt-in `codex-generate` adapter workflow. This change is verified with offline/mocked tests only: no actual account, Codex process, or model was used for generation acceptance. Real provider/schema compatibility and genuine-generation acceptance remain unverified, so #151 stays open. Existing registered-template acceptance is not acceptance of a newly authored repair.

The pure contract and preview-only paths do not start Codex. The active workflow can make one separately approved request for this fixed scenario; it does not accept an arbitrary repository, create a source copy, apply a patch, execute generated code, or restore files. #152/#153 verification/UI work is not implemented here. Existing product/report versions and the Codex pin are unchanged; the new command requires an explicit model.

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

The default final output starts with a compact result summary instead of repeating the full transport envelope. A valid `proposed-change` yields complete proposed source/test text and host-derived diffs/hashes, not an applied or tested repair. `no-change`, `unknown`, and `refused` remain distinct. Transport metadata is host-bound context, not independent attestation of model authorship; mock responses are not proof of actual generation.

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

The object-root output schema is a shaping candidate, not the authoritative validator. The host additionally enforces status/proposal relationships, required uncertainty, unique evidence IDs, exact UTF-8 byte limits and AST budgets. Following the [current structured-output schema guidance](https://developers.openai.com/api/docs/guides/structured-outputs) does not establish compatibility with the pinned App Server; that remains untested.

## What validation does not prove

- AST parsing is not compilation, test collection, an OS sandbox, semantic validation, or a safety check. Syntax-valid code may violate the requested limits or policy.
- IDs and hashes bind content; they do not authenticate a reviewer/model, prove freshness, or authorize sharing, execution, application, or recovery.
- A model-written test passing against the model-written repair is not independent evidence of a correct fix. No generated code is executed in this slice.
- Prior registered-template approvals do not authorize this new scenario or generated code. No current artifact is claimed to be an accepted live trial, a verified repair, or a stable-release gate completion.

## Next boundaries

[#152](https://github.com/casing1/authzest/issues/152) must first define and review the new execution boundary and independent maintained owner/non-owner/anonymous/normal-use controls. Separately approved, isolated before/after checks must distinguish test failures from infrastructure failures. Copy-only application, exact diff review, stale-edit refusal, and recovery need their own reviewed behavior and consent; this document authorizes none of them.

[#153](https://github.com/casing1/authzest/issues/153) will present actual scan, PoC/test, diff, check, and recovery results in a read-only local React UI. Initial action and approval controls stay in the CLI; cloud deployment is not required. These integrations remain future work.

The adapter uses the current-turn `outputSchema` direction described by the [official Codex App Server documentation](https://learn.chatgpt.com/docs/app-server). The source connection, offline schema and mocked tests are **not** actual provider compatibility evidence for the unchanged pinned Codex version `0.153.0`; a real request still needs separate consent and acceptance evidence.
