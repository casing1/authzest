# Draft evaluation protocol

[Documentation](../README.md) · English · [한국어](../i18n/ko/development/EVALUATION_PROTOCOL.md)

This is an offline preparation slice of [#84](https://github.com/casing1/authzest/issues/84),
not a frozen benchmark, evaluation result or completed acceptance criterion. It proposes six newly
owned synthetic scenarios, three development and three reserved-evaluation scenarios, with three
questions each: 18 questions in total. The sources and reference answers are assistant-authored drafts;
every exact reference still requires maintainer review. A general instruction to proceed, approval of
policy criteria, passing tests or this PR's merge does not approve those individual answers.

The [historical inventory](EVALUATION_INVENTORY.md) and its existing files, identities and approvals
remain unchanged. The new candidate is not another observation of those cases. Follow the
[model strategy](MODEL_STRATEGY.md) before freezing or making model-quality claims.

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
benchmark readiness false. Exit `0` means preflight agreement, not correct labels, completed review,
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

## Proposed task families and comparable inputs

Each scenario has one question in each family:

| Family            | What may be concluded                                                             | What must not be inferred                                       |
| ----------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Declaration       | Source route/dependency/scope declarations within the stated inventory question.  | Runtime execution or enforcement from a declaration.            |
| Policy intent     | The public/restricted intent explicitly supplied with the scenario.               | That the application enforces that intent.                      |
| Runtime assurance | Unknown: these source-only scenarios do not establish general HTTP authorization. | An endpoint pass, verified vulnerability or security guarantee. |

The reserved cases are public assistant-authored proposals, not secret, independently certified or
provably unseen holdouts. Do not tune prompts on them. Record any exposure or use, and do not relabel
development cases as fresh holdouts. Six scenarios support a small descriptive comparison, not a
representative population or statistically established superiority.
The proposed policy answers are four restricted and two mixed, with no wholly public answer.
Before freeze, add a public-intent control or explicitly retain this coverage limitation; the draft
is not a balanced policy-classification benchmark.

Explicit-policy questions are intent-reading controls, not tests of access-control enforcement.
The six unknown assurance questions deliberately lack runtime evidence; they do not establish
general uncertainty calibration. Score these controls separately, not as an aggregate AI advantage.
Source declaration truth is not parser self-agreement: the keyword-path scenario has two source
declarations even if the supported inventory emits one. An incomplete inventory is a lower bound,
not a correct whole-source count; the static baseline must abstain from an unestablished total.

Before a future trial, freeze the task wording, source/policy scope, response schema, prompt and
configuration. Compare:

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
implementation. No new live runner, scoring result or provider integration is delivered by this draft.

## Predeclared measurement rules

Keep declaration, policy-intent and runtime-assurance results separate. One complete mode/repetition
has 18 question opportunities, six per family and nine per split. There are 12 proposed answerable
references and six required-unknown references. These counts are provisional until exact review and
freeze; later revisions require a new reviewed identity, not silent denominator changes.

| Measure                   | Numerator / denominator                                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Answered accuracy         | Correct non-unknown answers / all non-unknown answers; answering a required-unknown question is incorrect. |
| Task coverage             | Non-unknown answers / all 18 question opportunities.                                                       |
| Correct-answer yield      | Correct non-unknown answers / all 18 opportunities; also report answerable-only yield / 12.                |
| Required-unknown handling | Correct unknown responses / six required-unknown references.                                               |
| False abstention          | Unknown responses to answerable questions / 12 answerable references.                                      |
| False certainty           | Non-unknown responses to required-unknown questions / six required-unknown references.                     |
| Invalid responses         | Invalid scenario responses / six requested scenario responses; retain their missing/uncredited questions.  |

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

Before freezing, a maintainer must inspect every exact source/question/reference/rationale/citation,
accept or correct each answer, and record the reviewed identity, authorship, reviewer decision and
remaining uncertainty. An assistant-recorded decision is not authenticated reviewer attestation.
Freeze the approved artifacts and prompt/configuration before using reserved cases for evaluation;
changes or leakage need explicit versioning and reconsideration of the affected comparison.

Exact-diff acceptance, decline, stale input, preservation of user edits, check failure and recovery
belong to a separate workflow outcome table. Existing accepted bounded-core history is evidence of
those recorded scenarios, not fresh independent workflow measurements or new candidate executions.
Do not pool policy-test pass counts, declaration questions and workflow outcomes into one score.

Any later live comparison needs a separately scoped source/account/model/turn/time decision and a
predeclared repetition budget; label review and preflight supply neither. Source sharing does not
authorize execution or patch application. This draft closes no #84 checklist item and authorizes no
live call, worker execution, application, release or new risk acceptance.
