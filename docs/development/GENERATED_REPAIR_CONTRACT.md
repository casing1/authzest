<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_CONTRACT.md">한국어</a>
</p>

# Offline generated repair contract

[Documentation index](../README.md)

## Status — 2026-11-09 KST

This is the first offline contract slice of [#151](https://github.com/casing1/authzest/issues/151), under the [course-release scope](https://github.com/casing1/authzest/issues/150). It prepares and validates in-memory requests and untrusted proposals; it does **not** deliver actual AI generation, generated-test execution, file application, or a results UI. #151 remains open. Existing registered-template acceptance is not acceptance of a newly authored repair.

The contract does not start Codex, read credentials or arbitrary repositories, create a copy, write files, run a test, or grant execution consent. Existing product/report versions and the Codex pin/model configuration are unchanged.

## Offline input preview

From a source checkout installed with this change, these commands display the fixed request without sending it:

```bash
authzest generation-preview
authzest generation-preview --json
```

The default output displays the full prompt and response schema with an explicit no-generation notice. JSON mode prints one `generated-repair-request-preview` document with `status: "preview-only"`, `model_invoked: false`, `applied: false`, and `execution_status: "not-run"`. There are no model, repository-path, or execution options. This is an input preview, not a generated proposal or a live-generation workflow.

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

The [official Codex App Server documentation](https://learn.chatgpt.com/docs/app-server) is the future integration reference for structured output such as `outputSchema`. This link and the offline schema are **not** compatibility evidence for the existing pinned Codex version `0.153.0`; that integration still needs its own checks and consent.
