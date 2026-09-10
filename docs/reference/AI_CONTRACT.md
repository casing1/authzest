<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/AI_CONTRACT.md">한국어</a>
</p>

# Offline AI contract and evaluation

[Documentation index](../README.md) · [Model strategy](../development/MODEL_STRATEGY.md)

## Status and scope

The source checkout implements #33's offline foundation; alpha.2 binaries do not include it.
AI schema `1.0` is separate from scan report schema `1.2` and package version `0.1.0a2`.
No live provider, new CLI command, source execution, test/patch generation, or patch application is added.
The ordinary scan and its JSON/exit behavior remain unchanged. #35 owns the later live improvement flow.
The old unused `CodexFinding` placeholder is removed; adapters now return untrusted JSON, not findings.

## Input and identity

`prepare_request` accepts an existing report, explicitly selected registration IDs, caller-supplied
repository-relative source snapshots, declared policies, questions, and `AdapterConfig`. It never opens
repository files. The caller must collect the report and snapshots from the same reviewed source state.
Sources and policies are untrusted data, not tool permissions or system instructions.

- Each source/route/policy/limitation item has a content-derived `ev-` identifier. Routes retain the
  report's `route-` registration ID, original locations, and dependency evidence. Source references
  must be inside the supplied snapshots. Repeated mounts remain distinct.
- The request contains no repository root, raw parse errors, or raw diagnostic messages. Selected
  diagnostic codes/counts and bounded/partial status remain explicit; they are not security verdicts.
- Source identity hashes the supplied path/text mapping. The request identity also binds evidence,
  questions, policy, mode, schema, and configuration. An optional source revision is caller-supplied,
  not verified against Git. Neither identity is a runtime guarantee or patch approval token.
- Limits are 16 source files, 32,768 characters per file, 256 evidence items, 32 questions, 262,144 JSON
  bytes, nesting depth 32, and 8,192 JSON nodes. Non-relative paths, missing registrations, duplicate
  IDs/keys, incompatible versions, non-finite numbers, and invalid Unicode are rejected.
- `CodexAnalysisRequest` stores immutable JSON; `to_dict()` returns a detached preview. Exact request-ID
  approval is required by the optional review service. No approval or a changed input produces
  `not-approved` before an adapter is called. This programmatic guard is not a user-facing consent UI.

Selection is not automatic secret detection or anonymization. Before a future live call, a user must
inspect the exact snapshot and remove secrets/private content. The library does not read credentials,
infer consent, provide an API client, or turn repository text into commands.

## Response and failure behavior

`validate_response` requires the current schema/request ID and exact provider/model/adapter/prompt
identity. Silent model substitution is rejected. Every question must have exactly one response with
existing evidence IDs, an explanation, assumptions, unknowns, and suggested review questions.

Only `hypothesis` and `unknown` statuses are allowed. Unknown requires a null answer and a stated
limitation. Confirmed findings/severity/extra fields are rejected; the original deterministic report
is never replaced or updated with model assertions. Model output is returned separately.

Structural validation cannot establish whether free-form prose is true or whether a valid citation
actually supports it. A malicious or mistaken explanation can still pass schema checks. Semantic
unsupported claims require human review; do not present schema acceptance as a confirmed diagnosis.

`review_report` records input/configuration identities, returned identity, nullable provider-reported
token counts, and measured local round-trip latency. It does not invent cost/token measurements or
log raw source/provider exceptions. Mocks report no model usage. Adapter failure, unavailability,
malformed output, and timeout preserve the original report. Cancellation propagates to the caller
and cooperative async adapter. Timeouts are not an OS sandbox and cannot stop a blocking/uncooperative
transport; future live implementations need process cleanup and independent permission enforcement.

## Reproduce the offline evaluation

From the repository root after the editable development setup:

```bash
python scripts/evaluate_offline.py --repeats 2
python -m pytest tests/test_ai_contract.py tests/test_ai_evaluation.py
```

The runner reads only the maintained source-only corpus in `tests/fixtures/ai_evaluation/v1/`.
It never imports/executes those apps or calls a provider. Six cases cover public intent, ordinary DI,
scope declarations, repeated mounts, dynamic prefixes, and unresolved dependencies. Three cases are
development cases and three are held out for later prompt evaluation (not secret data).

`dataset.json` contains questions and declared policies; `mock_answers.json` contains explicitly scripted
transport outputs. `labels.json` is evaluator-only and is loaded after all requests/responses are prepared.
The two mock modes use identical source, policy, questions, and model configuration; only extracted
evidence differs. Static-only answers supported inventory facts and abstains from policy interpretation.
It uses the shared response shape for scoring, not an AI call. A hash test freezes every corpus file.

The maintainer approved the five policy criteria on 2026-09-10. Expected values were drafted by the
assistant and checked against source; they are not represented as human-authored labels or a completed
independent benchmark review. Changing sources, labels, questions, or scripts requires deliberate corpus
review and an updated hash/version; do not tune prompts on the held-out cases.

The default is 36 trials: 6 cases × 3 modes × 2 repetitions. JSON includes per-case split, denominator-
bearing task accuracy/coverage, unknown handling, policy agreement, reference validity, provenance, and
repeated-output changes relative to the first trial. Invalid responses earn no task credit. Abstention
does not count as a correct answered task; correct unknown handling is measured separately.

Counts of answers containing unsupported claims (including misleading abstentions) and measured human
review seconds can be supplied to the scoring library;
the unattended runner leaves them null. Aggregate values remain null if any trial is unmeasured, with
the number of human-scored trials reported separately. Missing token counts are also null, not zero.
Do not compare the mock scores as evidence that AI helps, that authorization is correct, or that a
model upgrade is safe. Real repeated trials, independent semantic review, usage, and reviewer effort
remain requirements for a later approved live evaluation.

## Before any live adapter

Require separate approval for the exact source/policy snapshot, provider/model identity, privacy/data
handling, and budget. Choose one transport and record actual returned identity/usage when available.
No automatic fallback or model upgrade is permitted. Source-sharing approval never authorizes a patch
or verification execution. #35 must separately bind approval to the exact proposed diff and then to a
bounded verification plan; decline, cancellation, changed input, and failure must preserve user edits.
