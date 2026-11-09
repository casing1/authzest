<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/MODEL_STRATEGY.md">한국어</a>
</p>

# Model strategy and evaluation

[Documentation index](../README.md) · [Development plan](DEVELOPMENT_PLAN.md)

## Decision

Keep the installable CLI and the existing core/adapter boundary. Do not rewrite the product around a
particular GPT release. AuthZest's proposed value is repeatable source evidence, explicit policy
expectations, evidence-linked Codex review, and a user-controlled path from a proposed improvement to
an approved patch and verification record. Whether this helps more than giving the same task directly
to a model is a hypothesis to test, not an established advantage.

Codex integration and the approve/decline improvement flow are core final-demo goals. They are not merely
optional future explanations. Runtime use remains opt-in: an offline static scan must stay useful, and
permission to share source is not permission to apply a patch or execute a test. The broader design
below is not a general-repository implementation claim; the finite accepted core is recorded under
current priorities. The separate
[#50 fixture adapter](../guides/CODEX_FIXTURE.md) has a much narrower scope; one owned-fixture live draft/apply/restore check passed.
The later [#54 source-live acceptance](../guides/RUNTIME_VERIFICATION.md#bounded-live-acceptance--2026-09-12)
also completed the separately approved fixed runtime check and restoration. Published
[alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) includes this bounded workflow;
its separate [public-asset evidence](../releases/RELEASING.md) is not another live-model result or completion of #35.

The current product inventories a bounded subset of FastAPI routes, route-local dependency declarations,
and inherited application/router/include context. It does not yet resolve nested dependency graphs, determine authorization
correctness, or run AI as part of a scan. The [source-only examples](../guides/EXAMPLES.md)
are parser regressions/demos, not a security benchmark.

## Release-first priorities — 2026-11-09 KST

The course-complete stable target is [#150](https://github.com/casing1/authzest/issues/150), not
another comparison-transport milestone. Deliver [#151 genuine PoC/test and repair-source generation](https://github.com/casing1/authzest/issues/151),
then [#152 approved-copy verification and recovery](https://github.com/casing1/authzest/issues/152),
and [#153 local results UI](https://github.com/casing1/authzest/issues/153), followed by
[#85 installation/documentation/demo freeze](https://github.com/casing1/authzest/issues/85).
Scope one maintained, owned FastAPI object-ownership scenario, explicit policy, in-memory data and
one application source file plus a generated test. This is a planned release slice, not implemented
generation support. Do not send the registered after solution as a repair choice.

The model must author a new defensive PoC/test and repair source; selecting a known template does
not satisfy this goal. Validate bounded artifacts offline first. Review the new execution boundary
before enabling generated code: a timeout is not an OS sandbox, and the existing registered worker's
allowlist must not be relaxed as a shortcut. Verify the before defect and repaired actual bytes with
maintained independent controls, not only the generated test's assertions. Preserve exact-diff
approve/decline, new-copy-only changes, stale/user-edit refusal and recovery.

CLI remains the decision/execution path. The local React UI must show actual evidence, generated
tests, diff, before/after and recovery; it initially adds no browser execution/patch authority or
website deployment. Keep #84's seven criteria and reference history pending, but put broader model
comparison/executor expansion after the product core. Unavailable independent evidence must stay
visible; a limited stable release cannot claim model superiority. This direction does not authorize
new sharing, AI/generated-code execution, patching, risk acceptance or publication.

### Delivered foundation and evaluation history

The read-only owner review, #77 exact-case review, #79 readable output and
[#80 fixed-policy API](../reference/OWNER_POLICY_CHECK.md) are delivered. #80's final-head CI/reviews
completed through PR #97 on October 15; its separately scoped source observations do not establish
HTTP authorization. Original model authorship, labels-only decisions and consumed execution approvals
remain distinct from later evidence.

The maintainer accepted #81/#82/#35's bounded core on November 2: one registered synthetic policy pair,
eight reviewed cases, Codex selection of a registered repair template, exact-diff approval/application,
captured-file before/after observations and recovery through the POSIX non-frozen source CLI.
PR #123 delivered that acceptance and the issues closed in order. The installed happy-path observation
remains bound to `c868152`; acceptance and packaging are not new live-model observations.
General FastAPI PoC generation, model-authored replacement source, native active-file operation and
Windows policy execution remain unsupported, not prerequisites silently completed by that acceptance.

Alpha.4 was published on November 5 from exact source `090002d`; the
[release guide](../releases/RELEASING.md#alpha4-publication-and-public-asset-verification--2026-11-05-kst)
records tag-run attempt 2 and all six public files. Its failed first attempt remains part of the
release history. The post-alpha.4 source change under [#130](https://github.com/casing1/authzest/issues/130)
atomically publishes complete fake-server JSONL snapshots with strict record validation and
deterministic regressions; verification and delivery are tracked in the issue. This is test-harness
reliability work, not a production Codex fix, new live-AI acceptance or independent model evaluation.
The published alpha.4 tag/assets are unchanged.

For a later independent comparison, collect the missing independent-reference review attestation
and fix the separate live-trial configuration before prompt iteration or measuring the three-mode hypothesis under
[#84](https://github.com/casing1/authzest/issues/84). Historical model
inputs and development cases cannot become fresh holdouts. Use
[#85](https://github.com/casing1/authzest/issues/85) to freeze a reproducible owned-scenario demo,
installation instructions, limitations and OSS contribution evidence. If a measurement is unavailable,
report that gap rather than manufacturing a model-quality claim. Complete the bounded course scope
before adding models, another transport, a complete Python interpreter or browser-side execution.
The local results UI above is now a release deliverable, not an optional post-course expansion.

The separate [evaluation protocol](EVALUATION_PROTOCOL.md) records November 6 direct user acceptance
of the current 21 reference values in seven assistant-authored scenarios. v1 fixes source, questions,
splits, reference values and `scripts/evaluation_metrics.py` math, not a live benchmark. Raw task/
reference copies preserve their historical pending proposal metadata; the new manifest records
`accepted-current-reference-values` from `direct-user-chat-confirmation`, recorded by assistant.
It neither authenticates identity nor attests all-source/rationale/citation inspection or human
authorship. `independent_review_attested` is false; earlier preparation is not retroactively approved.
The split stays three development/four reserved with four restricted/two mixed/one public policy
values. One reserved public control is not class balance or a secret/guaranteed unseen holdout.
Explicit public intent and ordinary formatting DI still establish no runtime authorization guarantee.
The source-only `python -m scripts.evaluate_reference` preflight checks the pinned snapshot;
`--control` creates all-unknown synthetic task-only responses before references are loaded. This
control is not a static baseline, a model run or evidence of model quality. Generic unit math tests
remain separate from this pinned reference adapter; changed v1 data/math requires reviewed v2.
Live prompts/model/configuration/repeat budget remain unfixed and `live_benchmark_ready` is false.
Citation/prose support, usage, latency, repeats, reviewer effort and workflow measurements remain
unmeasured/null. No product command/schema relaxation, actual model/source/worker/workflow execution,
release or risk acceptance is added; historical bytes/observations stay unchanged and all seven #84
checklist items remain pending.

The offline comparison contract now pairs task-only packets and strict schema-`0.1` responses bound
to opaque task IDs and mode/payload-derived request IDs. Both AI inputs share source, policy,
questions, answer formats and development-draft instructions; only partial single-module evidence
and the derived request ID differ. No evaluator references, review metadata or case/split identifiers
enter provider payloads, and the complete evaluator plan is not provider input. The current
`python -m scripts.evaluation_comparison --dry-run` feeds synthetic unknowns to all three mode slots;
it measures no static baseline or model quality. A separate registered static adapter is now available
through `python -m scripts.evaluation_comparison --static-only` (`--json` optional). Task-only digest
queries derive source declaration counts/direct scopes from existing parser observations without
reading references; unknown coverage and all policy/runtime questions abstain. This is a bounded
fixed-seven-owned-task source observation, not general question interpretation or model evaluation.
Its mapping was developed in a context exposed to public v1 tasks/references. No-read-before-staging
is not blind, independent or unseen-holdout evidence; descriptive observations cannot establish
general benchmark performance, model value or completed independent scoring/review criteria.
It leaves paired AI inputs and v1/raw/math/history unchanged. Independent-review attestation, live
prompt/model/configuration/repetition freeze and actual model comparison are still missing. Do not
aggregate the three synthetic modes into an AI score or interpret strict parsing as semantic quality.

`scripts/evaluation_trial_plan.py` adds only an offline candidate: explicit syntax-only model/effort
labels, one to three planned repeats, proposed adapter timeouts and hashed application messages.
No catalog/account availability is verified. Deterministic alternating order is not randomized;
seven case pairs leave a first-mode imbalance for odd repeats. Nominal timeout sums are not wall/
usage caps. Message/configuration/trial hashes neither authorize sharing nor bind response-`0.1`
freshness across configuration/repeats. Fresh contexts/tool limits and live collection are not
implemented; live prompt/configuration/repeat freeze remains false. Public-data exposure and the
answer-only contract still prevent independence, citation-support/review-effort or model-value claims.

Offline host-receipt validation now separates expected slots from caller-supplied batches, not real
provider responses. Namespace/plan/configuration/trial/invocation bindings reject whole stale receipts
and within-batch duplicates, but old inner JSON rewrapped in current metadata can remain valid.
`provider_freshness_verified` stays false, provenance unverified, provider usage/latency/effective model
null and scoring not run. Revalidation is allowed; this is not persistent one-use enforcement or
authentication/consent. A later versioned provider-visible/capture boundary is still needed before live
collection; unchanged answer-only payloads cannot prove execution/context, independent evaluation or
model value. All seven #84 checks remain pending.

The historical registered workflow's defensive PoC is owned synthetic regression-case **data**,
not generated executable code. The new #151/#152 slice instead requires a newly generated defensive
test under its separately reviewed execution boundary; neither scope permits external exploits.
A correct-policy no-change or unknown result is valid; policy observations do not
attest HTTP authentication/authorization. Actual sharing, case labels, exact-diff application and
execution retain separate bound decisions. This planning update grants no live call or execution.
The alpha.4-only #89 decision is not stable-release clearance: reassess the current shipped bytes,
exposure and disposition for that new candidate. See the [development plan](DEVELOPMENT_PLAN.md)
for the conditional RC/stable target, submission buffer and existing inclusive seven-week budget.

## Stable contracts, replaceable models

| Layer                    | Responsibility                                                                                          | Must not imply                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Parser and analyzer      | Deterministic declarations, original locations, supported registration context                          | Complete understanding of arbitrary Python                        |
| Policy and report        | Separate observed facts, user-specified expectations, unresolved evidence, and eventual checks          | A dependency declaration proves authentication or authorization   |
| Codex adapter            | Review a permitted evidence payload and propose defensive tests/changes; validate shape and references  | A model's unsupported assertion becomes a confirmed finding       |
| Approval and application | Bind the user's decision to an exact diff and source identity; apply only that validated proposal       | Codex tool permission or earlier consent authorizes another patch |
| Isolated verification    | Run a separately approved, bounded owned-fixture plan; record results and recovery information          | A passing test proves general authorization correctness           |
| CLI and local results UI | Present the same core artifacts and honest failure/partial states; decisions/execution remain CLI-first | Successful execution or zero routes is a security pass            |

Do not expand the parser into a general Python interpreter. Add syntax support only when a documented
use case and maintained fixtures justify it. Repeated mounts need distinct registration identity and
application/include-site provenance; a URL path or a handler location alone cannot identify their context.
Record known unresolved cases without claiming every unsupported construct can be discovered.

The current source implements [#32: report and registration contract](https://github.com/casing1/authzest/issues/32)
with structured diagnostics and distinct registration evidence, extended to schema `1.2` by
[#28: route-local declarations](https://github.com/casing1/authzest/issues/28) and
[#29: inherited declarations](https://github.com/casing1/authzest/issues/29). Effective context preserves
each declaration's location/level; its outer-to-inner sequence does not promise runtime execution order.
A dependency `reference` means
simple/dotted-name syntax only, not resolved callable behavior or a security classification. Dependency
evidence does not participate in the original registration-ID hash.
The [report contract](../reference/REPORT_CONTRACT.md) retains default exit code 0 for returned partial reports;
`--strict` opts into code 1 for known partial analysis, and invalid repository input returns 2.
`bounded` is not complete analysis or a security pass. Registration IDs identify source registrations,
not complete file contents, source revisions, runtime objects, or patch approvals.

## Codex boundary and the selected fixture integration

The source implements [#33: evidence-linked explanations and offline evaluation](https://github.com/casing1/authzest/issues/33).
The [offline contract](../reference/AI_CONTRACT.md) defines minimized inputs, validated hypotheses,
mock failures, and a frozen comparison harness. Policy criteria are maintainer-approved; expected values
are assistant-authored and code-checked. Mock metrics are not model-quality evidence.
[#35: user-approved Codex improvement workflow](https://github.com/casing1/authzest/issues/35) then covers
proposal/approval contracts, the adapter, approved application, and isolated verification; #33 alone does
not implement that workflow. No provider call, credentials, subscription, or paid model is required by
the default scan or CI.

The opt-in #50 command selects Codex App Server 0.153.0, a caller-selected model and the packaged fixture
only. It requires exact-request sharing approval before starting a process, then separate apply/restore
decisions for a fresh POSIX copy. One live fixture check passed with assistant-entered approval phrases
under user authorization, not independent human review. That recorded #50 run did not execute runtime
verification; general repository AI remains unsupported.
At most one application-issued turn has no application retry/fallback; Codex internal transport retries can still
occur. A 120-second default timeout is not a hard token or monetary cap. See the [fixture guide](../guides/CODEX_FIXTURE.md).
The later #52 extension separately approves a fixed-source check in a bounded subprocess. It checks
AST configuration with pinned source hashes, executes no target source or model command, and adds no live-model evidence.
The [#54 runtime option](../guides/RUNTIME_VERIFICATION.md) keeps that static default and selects one
different, separately approved plan with `--runtime-check`. Only identical bundled fixture code runs;
the check observes `app.debug`, one in-memory ASGI `GET /health`, and dependency versions. It accepts
no arbitrary repository, generated command or regression suite, and makes no model-quality or
verified-security-fix claim. Process isolation is not an OS/network or dependency sandbox.
Alpha.3's native fixture workflow uses these core contracts; the evaluation corpus and demo scripts
remain source-checkout tools. Packaged fixed runtime checking is supported only on the tested POSIX
platforms; Windows retains scan support and explicitly refuses this fixture workflow.

For every live adapter, require explicit data-sharing approval and inspect the permitted input scope.
Repository text is untrusted data, not instructions granting the model tools or access. Minimize source
content, handle secrets, and define timeout, cancellation, malformed output, unavailable-provider, and
unsupported-reference behavior. A local report must survive adapter failure.

Validate each explanation against the supplied evidence identifiers and keep inferred policy separate
from human-declared policy. Public endpoints and ordinary dependency injection are legitimate cases;
missing recognizable authorization evidence is not by itself a vulnerability.

Keep the model choice explicit within a supported adapter. Record the exact returned model
identifier, prompt/adapter/report versions, source revision or content identity, permitted input manifest,
and actual usage and latency when available. Do not silently substitute a newer model or invent missing
usage data. Keep sensitive source and credentials out of telemetry. App Server is the selected fixture
transport; a second CLI integration is not required for this term project. AI schema 1.1 records
provider-managed temperature as null; numeric-temperature requests keep schema 1.0 and their identities.

## Planned proposal, approval, and verification contract

This preserves the earlier design rationale, not a new backlog replacing the accepted owned-file
scope above. That finite source workflow is implemented; extending it to general repositories or
model-authored replacement code remains out of scope for the bounded course release.

The [offline proposal/decision contract](../reference/PROPOSAL_CONTRACT.md) in #46 implements only
bound artifacts, previews and in-memory decision checks. It neither generates code nor mutates source,
and it does not replace the future current-filesystem/revocation/atomic-application checks below.

[#48's copy-only demonstration](../guides/FIXTURE_APPLICATION.md) adds terminal decisions, consumption,
file checks, application and restoration within a fresh POSIX fixture copy. It never edits the original
checkout or executes checks. Exclusive-writer assumptions, no restart and no authenticated approval
remain explicit limits; it does not finish the live workflow below.

#52's default source-configuration result leaves runtime verification `not-run`. In the opt-in #54
mode, the separately approved runtime result is `passed`, `failed`, or `not-run` and retains the exact
checked-content identity after restoration. Missing dependencies and unconfirmed outcomes are not
successful checks. Neither a matching file nor the fixed health probe establishes a general security
fix or completes the broader #35 gate. Live, mock, and packaged acceptance evidence must remain distinct.

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
design based on the documented approval behavior. The fixture adapter rejects model tool requests;
its separate exact-diff gate is implemented by AuthZest, not delegated to App Server tool approvals.
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
