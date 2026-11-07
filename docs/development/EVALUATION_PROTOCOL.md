# Evaluation protocol and v1 reference snapshot

[Documentation](../README.md) · English · [한국어](../i18n/ko/development/EVALUATION_PROTOCOL.md)

This is an offline reference-preparation slice of [#84](https://github.com/casing1/authzest/issues/84),
not a complete frozen live benchmark, model evaluation result or completed acceptance criterion.
It contains seven owned synthetic scenarios, three development and four reserved-evaluation scenarios,
with three questions each: 21 questions in total. On November 6 the user directly confirmed the
current exact 21 reference values in reply to that specific acceptance question. The decision is recorded as
`accepted-current-reference-values`, with source `direct-user-chat-confirmation` and `recorded_by`
assistant. Source and reference authorship remains assistant, not human.

The user had requested a public-intent control; preparation placed `status-probe-context` in reserved
evaluation without changing the original six scenarios, their splits or their 18 reference proposals.
The earlier positive reaction and preparatory merges remain nonapprovals at those historical points;
the November 6 direct confirmation is the new reference-values decision, not a retroactive approval.
The v1 snapshot fixes source, questions, splits, reference values and scoring math only. Independent
review attestation and an all-source/rationale/citation inspection attestation were not collected;
`independent_review_attested` is false. Live prompts, model/configuration and repeat budget remain
unfixed, `live_benchmark_ready` is false, and all seven #84 checklist items remain pending.

The [historical inventory](EVALUATION_INVENTORY.md) and its existing files, identities and approvals
remain unchanged. The new reference set is not another observation of those cases. Follow the
[model strategy](MODEL_STRATEGY.md) before any live trial or model-quality claim.

## Candidate and read-only preflight

The source-checkout-only files are
`tests/fixtures/evaluation_candidate/draft/tasks.json` and `references.json`.
The task file embeds virtual source paths and source text as inert JSON data; these are not runnable
fixture modules. The reference file is evaluator-only and contains proposed answers, rationales and
citations for exact review. No reference is human-authored merely because a human later reviews it.

From the repository root with Python 3.12 or later:

```bash
python scripts/check_evaluation_candidate.py
python scripts/check_evaluation_candidate.py --json
python scripts/check_evaluation_candidate.py --review
python scripts/check_evaluation_candidate.py --review --json
```

The default is a concise preflight summary; `--json` selects machine-readable output. `--review`
adds the exact proposed-answer/rationale review packet. That packet must never become provider input.
Human review output includes numbered, escaped virtual-source lines and question text;
review JSON includes the bound public inputs alongside the draft references.
Successful output still declares `draft-not-frozen`, execution not run, zero live trials and
benchmark readiness false. That checker reads the unchanged original proposal metadata, which
intentionally retains its historical pending status; it does not read the new v1 decision manifest.
Do not mistake the archived proposal state for the current reference-values decision, or rewrite it
as though approval existed earlier. Exit `0` means preflight agreement, not correct labels, completed review,
performance, permission or security. Exit `1` indicates invalid candidate data or a failed check;
exit `2` indicates invalid command-line usage.

The checker validates strict schemas, bounded reads, safe paths, UTF-8, content bindings and citation
line ranges. It does not import source, run a policy, call a provider, use the network, apply a patch
or grant approval. A citation within range can still be irrelevant or misleading. Hash agreement is
not semantic correctness or authenticity; an editor can change both data and its binding.

The public-input identity binds canonical JSON projections containing source paths/text, declared
policy and questions. It is not a raw-byte hash of the outer JSON file: harmless outer formatting
does not change that identity, while embedded source-text changes do. Do not substitute it for a
historical inventory hash, source revision, approval identity or authenticated review record.

`public_inputs(root)` reads only task/source data and returns those public projections. It excludes
references, rationales, split and authorship metadata; preflight reads references separately afterward.
This separation is a leakage check, not an implemented live comparison adapter or consent workflow.

## Accepted v1 reference snapshot and offline checks

The source-checkout-only snapshot is
`tests/fixtures/evaluation_reference/v1/{tasks.json,references.json,manifest.json}`. Tasks and
references are raw-byte copies of the accepted proposal files, including their original historical
pending/authorship metadata. The separate manifest records the current decision, its November 6
date and provenance using `current-21-reference-values-confirmed`, without reproducing chat text.
It does not authenticate a GitHub identity, provide a signature or attest that
every rationale/citation was inspected. The assistant-recorded chat decision is not tool-authenticated
reviewer identity or independent/blinded review.

The manifest pins source revision `ee1b988a11d8ce561f6e155451ef6e40c6a5c318`, combined canonical
task/reference candidate identity `1a84d57c0ea80d9d4f5bf53c1a1676c08a8a66f8902354fb2424285b12bae938`, raw hashes of both
copied data files and the current `scripts/evaluation_metrics.py` bytes. See the manifest for all
complete pinned values. These bindings establish agreement, not authenticity or semantic truth.
Treat v1 as an immutable versioned snapshot: changed data or math needs a new reviewed v2, not
refreshed v1 hashes.

```bash
python -m scripts.evaluate_reference
python -m scripts.evaluate_reference --json
python -m scripts.evaluate_reference --control
python -m scripts.evaluate_reference --control --json
```

Default output is a read-only pinned-reference preflight, not a trial or score. `--control` first builds
an all-unknown synthetic response from task-only inputs, before loading evaluator references, then
uses the pinned math. It does not copy labels into a perfect response. Its deliberate control has
seven cases/21 questions, 14 answerable references and seven required unknowns:

| Control measure           | Expected synthetic value |
| ------------------------- | ------------------------ |
| Answered accuracy         | 0/0, null                |
| Task coverage             | 0/21                     |
| Required-unknown handling | 7/7                      |
| False abstention          | 14/14                    |
| Invalid cases             | 0/7                      |

These are intentionally synthetic mathematics checks, not the static baseline, model quality,
independent review or a completed comparison. Citation/prose support, latency, provider usage,
repeats, reviewer effort and workflow observations remain unmeasured/null.

`reference_inputs(root)` reads task-only public inputs. `load_reference(root)` strictly checks the
three pinned snapshot files and the pinned math in both the trusted owned checkout and supplied
root; it does not dynamically import a target-root module. This checks source bytes, not Python memory
attestation or a hostile-filesystem sandbox. `score_reference(root, responses)` accepts
caller-normalized response records and uses the existing math. None calls a provider, imports or
executes the embedded source, runs a worker/workflow, or supplies a live prompt/model/trial policy.
This adds no product command/schema change, release or risk acceptance.

## Task families and comparable inputs

Each scenario has one question in each family:

| Family            | What may be concluded                                                             | What must not be inferred                                       |
| ----------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Declaration       | Source route/dependency/scope declarations within the stated inventory question.  | Runtime execution or enforcement from a declaration.            |
| Policy intent     | The public/restricted intent explicitly supplied with the scenario.               | That the application enforces that intent.                      |
| Runtime assurance | Unknown: these source-only scenarios do not establish general HTTP authorization. | An endpoint pass, verified vulnerability or security guarantee. |

The reserved cases are public assistant-authored data, not secret, independently certified or
provably unseen holdouts. Do not tune prompts on them. Record any exposure or use, and do not relabel
development cases as fresh holdouts. Seven scenarios support a small descriptive comparison, not a
representative population or statistically established superiority.
The accepted policy values are four restricted, two mixed and one public. Development retains two
restricted/one mixed/no public value; reserved evaluation has two restricted/one mixed/one
public. A public answer is now present in reserved evaluation, but its single public control cannot
establish representative coverage. This remains a small, unbalanced policy-classification draft.
The new control declares public intent for two informational GET routes; its ordinary dependency is
formatting only, not authorization evidence. Public intent comes from the explicit supplied policy,
not from a missing authentication dependency or the presence of `Depends`. It does not establish
runtime enforcement. Its accepted reference values are two route declarations, public intent and
unknown runtime assurance; acceptance is not an independent-review or runtime guarantee.

Explicit-policy questions are intent-reading controls, not tests of access-control enforcement.
The seven unknown assurance questions deliberately lack runtime evidence; they do not establish
general uncertainty calibration. Score these controls separately, not as an aggregate AI advantage.
Source declaration truth is not parser self-agreement: the keyword-path scenario has two source
declarations even if the supported inventory emits one. An incomplete inventory is a lower bound,
not a correct whole-source count; the static baseline must abstain from an unestablished total.

The v1 reference snapshot fixes task wording and source/policy scope. The offline response contract
below is a development interface, not a complete live-trial freeze. Before a future trial, separately
confirm its response contract and fix the live prompt, model/configuration and repetition budget. Compare:

1. Static-only: deterministic supported declaration facts; abstain from policy interpretation and
   runtime assurance. Do not read evaluator references to manufacture static answers.
2. Model-only: permitted source, declared policy and questions, without extracted AuthZest evidence.
3. Evidence-assisted: the same source, policy, questions and model configuration, plus extracted
   AuthZest evidence. The additional evidence is the intended input difference.

The AI modes must share the exact model identity, instructions, source scope and trial policy. Record
unavoidable differences, prompt/adapter/report versions, content identities and returned model ID.
Do not include expected answers, review packets, answer-revealing metadata or labels in either input.
Token counts need not be equal; record actual available usage rather than asserting equal cost.
Set repeat counts and ordering before trials, keep failures visible, and report variation by case.
The existing historical scorer special-cases the question ID `policy`; it is not a new-family scoring
implementation. The v1 helper supplies only offline preflight/scoring and a synthetic control, not
a live runner, model result or provider integration.

## Offline comparison packets and strict response contract

`scripts/evaluation_response.py` defines the separate evaluation response schema `0.1`, not a change
to any product schema. It accepts one complete, bounded JSON object with exactly `schema_version`,
`kind`, `task_id`, `request_id` and `answers`; `kind` is `evaluation-comparison-response`. Each answer
record contains exactly `question_id` and `answer`, with one record for every requested question.
Duplicate keys/answers, missing or extra questions/fields, wrong bindings and noncanonical values
invalidate the whole case. Strings are not repaired: `""` is a known empty sorted-CSV set, while only
JSON null is unknown. Missing raw responses remain missing, not successful unknown responses.

`scripts/evaluation_comparison.py` builds three mode slots with the same source, explicit policy,
questions, answer formats and common development-draft instructions. Only evidence-assisted gets
additional in-memory declaration evidence from the existing core `parse_source`; modules are parsed
independently, without importing, materializing or executing their source. Evidence is always marked
partial: cross-module router/include context and callable dependency graphs are unresolved, deferred
declarations do not establish invocation/deployment, and diagnostics/parse errors remain visible.
An extracted declaration is not proof of access control or complete inventory.

Opaque `task_id` values bind task-only source/policy/questions. `request_id` derives from the mode and
payload, so a response for another request/mode is rejected. The two AI payloads differ only in
declaration evidence and that derived request ID; their common draft instructions are not a frozen
live prompt. Case names, splits, reference manifest/candidate hash, expected answers, rationales and
review metadata are excluded from potential provider payloads. The evaluator plan itself contains
case mapping and is **not** provider input. Hash bindings are not authentication or a secrecy claim.

From the repository root, prepare a plan or an explicitly synthetic dry run:

```bash
python -m scripts.evaluation_comparison
python -m scripts.evaluation_comparison --json
python -m scripts.evaluation_comparison --dry-run
python -m scripts.evaluation_comparison --dry-run --json
python -m scripts.evaluation_comparison --dry-run --fault missing
python -m scripts.evaluation_comparison --dry-run --fault invalid
```

All packets and mock responses are staged before evaluator references are loaded for scoring. Every
mode slot uses synthetic null answers in a dry run, including `static-only`; the separately available
registered static adapter below is not used by dry-run. This measures neither a static baseline nor
model quality. Each mode separately retains seven cases/21 questions, 14 answerable references and seven
required unknowns. A fault affects the first case in each mode; missing responses become `None` and
invalid responses become `[]` at the math boundary, retaining their failure kinds and denominators.
Invalid cases earn no unknown credit. Do not pool 63 synthetic opportunities into an AI-quality score.
`--fault` requires `--dry-run`.

Independent-review attestation and live prompt/model/configuration/repeat freeze remain future work.
No provider call or actual model trial is implemented; v1/raw reference
bytes, pinned math, historical records, product schemas/versions, risk acceptance and releases are
unchanged. #84 remains open with all seven checklist items pending.

## Registered static-only source observation

The separate `scripts/evaluation_static.py` adapter uses a task-only digest registry of explicit
declaration queries, not stored expected answers or a general natural-language question interpreter.
Unregistered tasks and changed questions abstain. It computes answers from existing in-memory core
parser observations: count source HTTP decorator declarations, or extract direct `Security` scopes
for a literal method/path. AST coverage is checked against parser declaration locations; diagnostics,
ambiguity, missing coverage and cross-module composition limits produce unknown rather than an
unestablished total. Policy intent and runtime assurance are always unknown in this adapter.

These mappings are authored in a development context already exposed to the public v1 tasks and
available references. Not reading reference files while generating answers does not make the tasks
independent, blinded or unseen holdouts. Report a descriptive static observation on these fixed source
tasks, not general benchmark performance, model value or completion of independent review/scoring
criteria.

Declaration counts retain distinct source declarations even when two apps use the same path.
Deferred factory declarations are source declarations, not proof of invocation or deployment.
Direct-scope queries exclude inherited `Security` and callable-provider graphs; an ordinary dependency
or a scope declaration does not prove access-control enforcement. The registered queries do not
establish complete Python interpretation, general repository coverage or HTTP/runtime correctness.

```bash
python -m scripts.evaluation_comparison --static-only
python -m scripts.evaluation_comparison --static-only --json
```

This explicitly selects a deterministic source-only observation scoped to the fixed seven owned
tasks, not a model comparison. All seven cases' responses are completed before references are loaded
for scoring; failures and abstentions retain their denominators. The AI paired payloads are unchanged;
the default command still prepares a plan. `--dry-run` remains synthetic null in every mode, is mutually exclusive with
`--static-only`, and is the only mode that accepts `--fault`; no fault is inserted into real static
observations. Model quality remains unmeasured and live trials zero. v1/raw references, pinned math,
historical records and product source/schemas/versions are unchanged; independent-review attestation,
live configuration/repeat freeze and actual model comparison remain pending. This adds no AI/worker
execution, patch, risk acceptance, release or completed #84 checklist item.

This slice's source-only CLI observation on the fixed public development set produced five answers
out of 21 questions, 16 abstentions and zero invalid cases. The family breakdown is:

| Family            | Answered | Abstained |
| ----------------- | -------- | --------- |
| Declaration       | 5/7      | 2/7       |
| Policy intent     | 0/7      | 7/7       |
| Runtime assurance | 0/7      | 7/7       |

This is a descriptive observation of these exposed owned tasks, not independent/blinded holdout
performance, an AI/model comparison or acceptance of independent scoring/review criteria. An unknown
runtime answer is not observed runtime enforcement; the answered subset must not be presented as
general benchmark accuracy.

The JSON observation identifies `kind: registered-static-source-observation`,
`baseline_scope: fixed-seven-owned-source-tasks` and
`response_origin: deterministic-registered-source-query`. Its `static_baseline_measured: true` means
only this bounded static observation; `model_quality_measured` remains false. The reference metadata
includes the v1 candidate/manifest identities and false independent-review attestation, not proof of
freshness or blind evaluation. It also records assistant query-registry authorship and
`evaluation_independence: not-established-public-developed-tasks`.

## Offline AI trial candidate, not execution

The source-checkout helper `scripts/evaluation_trial_plan.py` proposes explicit model/effort labels,
repetitions and an adapter timeout without collecting responses or running a trial. All four arguments
are required; repetitions are `1..3`, timeout seconds `1..120`. Labels are syntax-checked only, not
checked against an account or model catalog. `offline-example-model` below is a placeholder, not a
verified available model. `--show-messages` and `--json` are mutually exclusive output options.

```bash
python -m scripts.evaluation_trial_plan --model offline-example-model --effort medium --repetitions 1 --timeout-seconds 120
python -m scripts.evaluation_trial_plan --model offline-example-model --effort medium --repetitions 1 --timeout-seconds 120 --show-messages
python -m scripts.evaluation_trial_plan --model offline-example-model --effort medium --repetitions 1 --timeout-seconds 120 --json
```

For seven cases and two AI modes, the candidate describes these opportunities, not executed calls:

| Repetitions | Planned slots | Planned question opportunities | Nominal adapter timeout sum at 120 seconds |
| ----------- | ------------- | ------------------------------ | ------------------------------------------ |
| 1           | 14            | 42                             | 1,680 seconds                              |
| 2           | 28            | 84                             | 3,360 seconds                              |
| 3           | 42            | 126                            | 5,040 seconds                              |

The timeout sum is not a wall-clock, token or credit cap. Cleanup time and Codex internal retries/
usage have no bound established here. A desired one-attempt/no-AuthZest-retry-or-fallback policy is
candidate metadata, not an implemented executor guarantee. Task IDs are sorted and the first mode
flips by case/repetition. Seven pairs give a 4-versus-3 first-mode split in one repetition; odd repeat
counts leave an imbalance. This order is deterministic, not randomized or fully counterbalanced.

The planner keeps the existing paired payloads, common draft instructions and response schema `0.1`.
It verifies task/request bindings and reports canonical application-message text, UTF-8 byte lengths
and SHA-256 values. These candidates are not actual RPC wire envelopes or the effective Codex harness
context. Fresh contexts and tool restrictions are future requirements, not enforced by this helper.
Configuration, packet-set, plan and trial IDs are deterministic content metadata, not consent or
invocation-freshness proof. Request IDs remain the same across configurations/repetitions; response
schema `0.1` cannot bind a response to those settings, repeats or a fresh invocation. Collection/run
support is not implemented. `answer_contract_descriptor_id` binds the public descriptor, not the full
validator implementation.

Only task data is read: no evaluator labels/reference scoring, account lookup, network, child process,
target-source import/execution, AI or worker call. The full plan is evaluator metadata, never provider
input. It is not a native executable feature or `authzest` product command. Prompt/model/configuration/
repeat freeze, sharing and execution authorization, and `live_benchmark_ready` all remain false.
Answer-only responses cannot measure semantic citation support, explanations or human review effort;
public v1/reference exposure still prevents an independence claim. No model result, v1/math/history/
product-version change, risk acceptance, release or completed #84 checklist item is added.

## Candidate-independent offline mathematics

The source-checkout-only module `scripts/evaluation_metrics.py` separates generic measurement
mathematics from candidate loading or evaluation. Its API is `score_cases(cases, responses)`, with
`cases` a tuple of `CaseSpec(id, split, questions)` values and each `questions` value a tuple of
`QuestionSpec(id, family, answer_format, expected)` values. Each expected answer is a canonical string
or `None` (the unknown value represented by JSON null). Responses map a case ID to a list of records
containing exactly `question_id` and `answer`, or to `None` for an absent case response.

Answer formats require exact canonical decimal, sorted CSV, boolean or policy strings; the module
does not trim, coerce, sort, normalize or otherwise repair answers. The empty string is valid only for
an empty sorted-CSV answer; only `None` means unknown. Invalid, missing, extra or duplicate answer
records invalidate the whole case without removing any of its question or case denominators.
Family and split summaries sum counts before calculating rates, rather than averaging group rates.
Undefined rates remain null. Citation/prose support, latency, provider usage, repeats, reviewer effort
and workflow metrics are not measured by this module; their placeholders remain null, not zero.

This standalone module has no CLI or file/network/provider/source/runner imports. It is not a product
command, a schema relaxation, a candidate adapter or a live comparison harness. Its synthetic-only
tests do not load, score, freeze or approve the actual seven-scenario/21-question candidate; candidate
data, bindings and historical evaluation artifacts remain unchanged. From the repository root:

```bash
python -m pytest tests/test_evaluation_metrics.py
```

This command checks generic math using synthetic unit data only. Passing such tests would establish
neither correct reference labels nor a measured model-quality result. The separate v1 helper now
connects the accepted reference snapshot to that math; independent review attestation and any future
live comparison retain the boundaries stated elsewhere in this protocol.

## Predeclared measurement rules

Keep declaration, policy-intent and runtime-assurance results separate. One complete mode/repetition
has 21 question opportunities, seven per family, nine in development and 12 in reserved evaluation.
There are 14 accepted answerable references and seven required-unknown references. These reference
denominators are fixed by v1; later changes need a new reviewed version/identity, not silent
denominator changes or refreshed v1 hashes. No live-trial count or repeat budget is fixed here.

| Measure                   | Numerator / denominator                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Answered accuracy         | Correct non-unknown answers / all non-unknown answers; answering a required-unknown question is incorrect.  |
| Task coverage             | Non-unknown answers / all 21 question opportunities.                                                        |
| Correct-answer yield      | Correct non-unknown answers / all 21 opportunities; also report answerable-only yield / 14.                 |
| Required-unknown handling | Correct unknown responses / seven required-unknown references.                                              |
| False abstention          | Unknown responses to answerable questions / 14 answerable references.                                       |
| False certainty           | Non-unknown responses to required-unknown questions / seven required-unknown references.                    |
| Invalid responses         | Invalid scenario responses / seven requested scenario responses; retain their missing/uncredited questions. |

Apply the corresponding fixed family/split denominators as well. Invalid responses earn no answer or
unknown-handling credit and no coverage; they are not successful abstentions. A zero denominator is
null/not applicable, not perfect. Report missing answers and failures rather than dropping them.
Static abstentions are expected limitations, not proof of policy correctness. A lower unknown count
or higher coverage alone is not better analysis.
An empty CSV string is a known empty declaration set; only null represents an unknown reference.

Citation-ID existence is a structural metric only. Separately record semantic support for manually
reviewed citations and the number of reviewed answers containing at least one unsupported claim,
including misleading prose accompanying an unknown answer. Record the reviewed denominators and
rubric; do not let valid IDs earn semantic credit automatically. Measure actual reviewer time, with
mode-blinded review where feasible, rather than estimating it from response length or approval time.

Record available local latency, provider usage, repeats and human review seconds with provenance.
Unmeasured semantic support, unsupported claims, reviewer effort, usage and latency stay null, not
zero. Publish per-case errors and limitations alongside any aggregate; mock output demonstrates the
harness only and cannot establish AI value or a model-upgrade recommendation.

## Review, freeze and workflow boundaries

The November 6 direct confirmation accepts the current exact reference values, not an attestation
that every source/question/rationale/citation was inspected. That inspection attestation was not
collected, and `independent_review_attested` remains false. Before claiming #84's independent-review
criterion, collect its actual review evidence and remaining uncertainty without inventing authorship,
signed approval or authenticated identity. An assistant-recorded decision is not authenticated reviewer
attestation. Fix the separate prompt/model/configuration/repetition policy before using reserved cases
for a live evaluation; changes or leakage need versioning and reconsideration of the comparison.

Exact-diff acceptance, decline, stale input, preservation of user edits, check failure and recovery
belong to a separate workflow outcome table. Existing accepted bounded-core history is evidence of
those recorded scenarios, not fresh independent workflow measurements or new candidate executions.
Do not pool policy-test pass counts, declaration questions and workflow outcomes into one score.

Any later live comparison needs a separately scoped source/account/model/turn/time decision and a
predeclared repetition budget; label review and preflight supply neither. Source sharing does not
authorize execution or patch application. This reference slice closes no #84 checklist item and authorizes no
live call, worker execution, application, release or new risk acceptance.
