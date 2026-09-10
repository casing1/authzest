<p align="center">
  <strong>English</strong> ·
  <a href="i18n/MODEL_STRATEGY.ko.md">한국어</a>
</p>

# Model strategy and evaluation

[Documentation index](README.md) · [Development plan](DEVELOPMENT_PLAN.md)

## Decision

Keep the installable CLI and the existing core/adapter boundary. Do not rewrite the product around a
particular GPT release. AuthZest's proposed value is repeatable source evidence, explicit policy
expectations, evidence-linked Codex review, and a user-controlled path from a proposed improvement to
an approved patch and verification record. Whether this helps more than giving the same task directly
to a model is a hypothesis to test, not an established advantage.

Codex integration and the approve/decline improvement flow are core final-demo goals. They are not merely
optional future explanations. Runtime use remains opt-in: an offline static scan must stay useful, and
permission to share source is not permission to apply a patch or execute a test. The workflow below is
a design target, not a claim that an adapter, approval gate, or patch executor already exists.

The current product inventories a bounded subset of FastAPI routes and route-local dependency declarations.
It does not yet propagate inherited dependencies, resolve nested dependency graphs, determine authorization
correctness, or run an AI adapter. The [source-only examples](EXAMPLES.md)
are parser regressions/demos, not a security benchmark.

## Stable contracts, replaceable models

| Layer                    | Responsibility                                                                                         | Must not imply                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Parser and analyzer      | Deterministic declarations, original locations, supported registration context                         | Complete understanding of arbitrary Python                        |
| Policy and report        | Separate observed facts, user-specified expectations, unresolved evidence, and eventual checks         | A dependency declaration proves authentication or authorization   |
| Codex adapter            | Review a permitted evidence payload and propose defensive tests/changes; validate shape and references | A model's unsupported assertion becomes a confirmed finding       |
| Approval and application | Bind the user's decision to an exact diff and source identity; apply only that validated proposal      | Codex tool permission or earlier consent authorizes another patch |
| Isolated verification    | Run a separately approved, bounded owned-fixture plan; record results and recovery information         | A passing test proves general authorization correctness           |
| CLI and optional API/UI  | Present the same core report and honest failure/partial states                                         | Successful execution or zero routes is a security pass            |

Do not expand the parser into a general Python interpreter. Add syntax support only when a documented
use case and maintained fixtures justify it. Repeated mounts need distinct registration identity and
application/include-site provenance; a URL path or a handler location alone cannot identify their context.
Record known unresolved cases without claiming every unsupported construct can be discovered.

The current source implements [#32: report and registration contract](https://github.com/casing1/authzest/issues/32)
with structured diagnostics and distinct registration evidence, extended to schema `1.1` by
[#28: route-local declarations](https://github.com/casing1/authzest/issues/28). Next is
[#29: inherited declarations](https://github.com/casing1/authzest/issues/29). A dependency `reference` means
simple/dotted-name syntax only, not resolved callable behavior or a security classification. Dependency
evidence does not participate in the original registration-ID hash.
The [report contract](REPORT_CONTRACT.md) retains default exit code 0 for returned partial reports;
`--strict` opts into code 1 for known partial analysis, and invalid repository input returns 2.
`bounded` is not complete analysis or a security pass. Registration IDs identify source registrations,
not complete file contents, source revisions, runtime objects, or patch approvals.

## Codex boundary before a live integration

Start with [#33: evidence-linked explanations and offline evaluation](https://github.com/casing1/authzest/issues/33).
Define a minimal evidence payload and mock adapter tests before choosing one live integration.
[#35: user-approved Codex improvement workflow](https://github.com/casing1/authzest/issues/35) then covers
proposal/approval contracts, the adapter, approved application, and isolated verification; #33 alone does
not implement that workflow. No provider call, credentials, subscription, or paid model is required by
the default scan or CI.

For a later opt-in adapter, require explicit data-sharing approval and inspect the permitted input scope.
Repository text is untrusted data, not instructions granting the model tools or access. Minimize source
content, handle secrets, and define timeout, cancellation, malformed output, unavailable-provider, and
unsupported-reference behavior. A local report must survive adapter failure.

Validate each explanation against the supplied evidence identifiers and keep inferred policy separate
from human-declared policy. Public endpoints and ordinary dependency injection are legitimate cases;
missing recognizable authorization evidence is not by itself a vulnerability.

Make provider/model selection configurable when an adapter exists. Record the exact returned model
identifier, prompt/adapter/report versions, source revision or content identity, permitted input manifest,
and actual usage and latency when available. Do not silently substitute a newer model or invent missing
usage data. Keep sensitive source and credentials out of telemetry. CLI and App Server are integration
options behind the interface, not parallel implementations required for this term project.

## Planned proposal, approval, and verification contract

The minimum final demo is one maintained owned fixture taken through these separate stages:

1. Collect source evidence and human-declared policy; explicitly select and approve the input shared with Codex.
2. Produce an evidence-linked review, a defensive regression-test draft, and a proposed diff in an isolated
   temporary workspace. Preserve the original worktree; do not execute the scanned application while proposing.
3. Show the rationale, evidence references, affected files, exact diff, source revision/content identities,
   and intended verification plan. The user can approve, decline, or cancel; silence is not approval.
4. Recheck the proposal's identity and source preconditions, then apply only the approved diff. Reject stale
   approval if source or the proposed diff changed, and do not overwrite existing user edits.
5. Request distinct permission for the reviewed verification plan and execute it only in the bounded isolated
   owned-fixture environment. Record what ran, exit status, passed/failed/unrun checks, and remaining uncertainty.
6. Preserve the approved proposal, decision, before/after identities, and results in a source-minimized change
   record. Offer recovery only when its preconditions still hold; otherwise report a conflict without resetting
   unrelated work. A failed or unrun test is not a successful fix.

These stages need offline contract tests for refusal, cancellation, invalid citations, malformed proposals,
provider failure, stale approval, pre-existing user edits, changed verification plans, failed tests, and
recovery conflicts. Generated tests and repository content are untrusted data; neither may broaden the
allowed files, tools, network, or execution scope. A change to the verification plan needs fresh execution
approval. No exploit-PoC generation, autonomous offensive workflow, or arbitrary repository execution is planned.

App Server can request command/file-change approvals depending on Codex settings; it does not guarantee a
prompt before every edit. Therefore AuthZest needs its own exact-proposal gate, separate from transport/tool
permissions. The product must not require a blanket session-wide acceptance to work. This is our product
design based on the documented approval behavior, not an App Server feature already implemented by AuthZest.
[Codex App Server approval documentation](https://learn.chatgpt.com/docs/app-server#approvals).

## Test the product hypothesis

Before tuning prompts, freeze a small, human-reviewed set of owned local fixtures and expected policy
labels. Include ordinary DI, intentionally public routes, relevant access-control declarations, repeated
mounts, incomplete inputs, and unsupported patterns. Keep the expected answers out of model input and
reserve held-out cases for evaluation rather than prompt development.

Compare three modes on the same task and permitted source/policy scope:

1. Static evidence without AI.
2. A model given the permitted source and policy directly, without AuthZest's extracted evidence.
3. The same model given that scope plus AuthZest's evidence.

Keep the model and task instructions comparable between the two AI modes, document any unavoidable
input differences, and record actual token usage rather than claiming equal cost. Run repeated trials
for the nondeterministic modes. A static-only mode may abstain from explanation tasks; report task
coverage separately from correctness instead of scoring an abstention as a correct answer.

Measure route/declaration correctness and coverage, valid source citations, unsupported claims, policy
agreement, unresolved outcomes, repeated-run variation, latency, actual usage, and human review effort.
Evaluate the approval/application flow separately: exact approved changes, declined/stale no-change outcomes,
preservation of user edits, verification failures reported correctly, and safe recovery. A test passing is
evidence about that test and fixture, not a general security guarantee.
Report denominators, fixture limitations, and representative errors alongside any aggregate score.
More routes or fewer unknowns alone do not establish better security analysis. Keep inventory fixtures
separate from the later labelled policy evaluation set.

A small comparison can begin after the evidence contract and initial dependency fixtures; a complete
deterministic finding engine is not a prerequisite. If the evidence-assisted mode does not help, narrow
the claim or revise the workflow rather than adding more agent autonomy.

## Evidence for this design

Official documentation reviewed on 2026-09-10: model capabilities and recommendations change, so model
selection belongs at a replaceable boundary. This is our architectural inference, not a demonstrated
AuthZest performance result. [OpenAI model guide](https://developers.openai.com/api/docs/guides/latest-model).

Task-specific datasets, expert labels, explicit metrics, comparisons, and repeat evaluation inform the
evaluation process above. [OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

App Server documents an interface and managed authentication flow that can be evaluated later; reading
those docs does not enable the adapter or grant permission to send repository data.
[Codex App Server documentation](https://learn.chatgpt.com/docs/app-server).
