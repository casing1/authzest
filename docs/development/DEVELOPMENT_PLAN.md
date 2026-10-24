<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/DEVELOPMENT_PLAN.md">한국어</a>
</p>

# AuthZest Development Plan

[Documentation index](../README.md) · [Public roadmap](https://github.com/casing1/authzest/issues/1)

## Product direction

Build an installable, CLI-first FastAPI source-evidence tool for the OSS course. The core deliverable is
one bounded, owned access-control scenario: source evidence → reviewed defensive reproduction/case plan
→ Codex recommendation or valid no-change → exact-diff approve/decline → approved new-copy application
→ separately approved observations → inspectable recovery records. Codex is a core goal, not an optional
explanation add-on. Keep deterministic scan useful without an AI account.

Keep parser/analyzer, Codex adapter, runner and presentation boundaries independent. The existing
local API/React dashboard is optional and shows static inventory; it does not yet present Codex decisions.
Improve CLI usability before adding an AI GUI, deployment or a second adapter. Model improvements do
not justify rewriting the product as an autonomous agent or general Python interpreter. Evidence-assisted
value is a hypothesis to measure, not an established advantage; see [model strategy](MODEL_STRATEGY.md).

## Current baseline — 2026-10-25 KST

The current sharing/adapter work starts from offline repair-recommendation delivery `8409bc7`, merged
through [PR #102](https://github.com/casing1/authzest/pull/102) on 2026-10-24 KST. The registered pair
was delivered at `cbe6b37` through [PR #101](https://github.com/casing1/authzest/pull/101) on 2026-10-21 KST. The earlier pair implementation
base `c12f4b137b30f96202b3a2555b3b5a151edf6e56` delivered the unchanged [pair design](OWNER_POLICY_REPAIR_PAIR_DESIGN.md) through
[PR #100](https://github.com/casing1/authzest/pull/100) on 2026-10-19 KST. The maintainer separately
approved its exact scenario/source pair/eight expected labels and the bounded pure registry/preview
slice in the [recorded decision](https://github.com/casing1/authzest/pull/100#issuecomment-6258235318).
The source implementation introduced in [PR #101](https://github.com/casing1/authzest/pull/101)
remains unreleased; its delivery records are tracked there. The separate
[repair-recommendation reference](../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md) now covers
the delivered offline contract and the next unreleased exact-sharing/adapter stage. This is not
live-model acceptance or the completed remediation workflow. #81/#35 remain incomplete.
The earlier original design was delivered at `f1cbd2fdcfc91453488ac38bbd53ac2a14940b7e` through
[PR #98](https://github.com/casing1/authzest/pull/98) on 2026-10-16 KST. These are recorded bases,
not claims about latest main. Design head `a170d82` passed ten CI checks and completed
[code/security automated reviews without reported findings](https://github.com/casing1/authzest/pull/98#issuecomment-6206327402).
The earlier #80 delivery through [PR #97](https://github.com/casing1/authzest/pull/97) at `38587c3`
passed ten final-head CI checks and both code/security re-reviews, then six reported post-merge checks.
#77 and #80 are closed. The source implementation introduced in [PR #99](https://github.com/casing1/authzest/pull/99) provides #81 S1's
[offline recommendation data API](../reference/OWNER_POLICY_RECOMMENDATION.md), not the full #81
workflow or a published feature. The unchanged [original design](OWNER_POLICY_IMPROVEMENT_DESIGN.md)
remains the historical proposal delivered through PR #98. Implementation CI/review/delivery
outcomes are tracked separately in PR #99. The separate
[2026-10-16 S1 continuation](https://github.com/casing1/authzest/issues/81#issuecomment-6206079101)
does not approve all #81 extensions or authorize provider calls, policy execution or patches.
Historical records live in the [changelog](../../CHANGELOG.md), linked issues/PRs and
[release record](../releases/RELEASING.md); this plan records current priorities, not every past test count.

| Implemented                                   | Actual boundary                                                                                                                                                  |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Installed CLI, local API/UI and static parser | Bounded FastAPI route/registration/local-inherited dependency declarations; no complete Python interpretation or authorization verdict                           |
| Evidence, proposal and expectation contracts  | Exact identities/references, draft expectations and read-only comparison; schema `1.2`                                                                           |
| Mock review/walkthrough and copy application  | Separate source/apply/check/restore decisions; new owned single-file POSIX copy, not arbitrary checkout editing                                                  |
| Opt-in App Server fixture workflow            | Pinned adapter, exact sharing approval; default AST check, separately approved fixed debug/health runtime option                                                 |
| Owned report policy example                   | Pure-policy developer tests and scanner inventory; authentication is unconfigured/fail-closed, no HTTP authorization acceptance                                  |
| Read-only owner Codex review (#75 / PR #76)   | Exact two-source sharing; one approved live run returned one host-valid answer / ten unexecuted cases, not a patch or security proof                             |
| Readable CLI output (#79 / PR #90)            | Human-readable defaults, explicit JSON streams and complete sharing previews; no new AI authority                                                                |
| Offline case-review / fixed-plan API (#77)    | Pure data with exact source/case/decision bindings; caller choices are not authenticated approval, and every plan is non-executable                              |
| Fixed owned-policy check API (#80 / PR #97)   | Source-only fixed policy observations under a fresh one-use decision; Windows/frozen execution refuses; no HTTP/authentication proof                             |
| S1 recommendation contract (PR #99)           | Pure data request/result validation and output-only preview; caller-supplied provenance, empty changes, no provider/policy execution                             |
| Registered repair-pair API (PR #101)          | Exact registered data and host-derived one-file diff preview only; unreleased, no observations or apply/execute capability                                       |
| Repair recommendation / sharing (source)      | PR #102's pure result contract plus separate opt-in `codex-owner-repair`; offline preview, exact sharing and one transport attempt, no apply or policy execution |

The recorded owner review at `9257bd7` took about 74 seconds. On 2026-10-09 KST the maintainer
explicitly approved that exact envelope's ten labels: two allow and eight deny; see the separate
[review record](../../tests/fixtures/owner_case_review/maintainer_review.json) and
[#77 contract](../reference/OWNER_CASE_PLAN.md). Model authorship and the original envelope remain
unchanged. This labels-only decision is not authenticated execution consent and does not approve
the separate 28 assistant-authored developer-test labels or frozen evaluation set. The original
draft and offline plans remain not-run. A later separate historical recipe `1.0` #80 source check produced
[ten matching observations](../reference/OWNER_POLICY_CHECK.md#actual-source-acceptance--2026-10-09-kst);
authorization remains unknown. One later freshly and separately approved recipe `1.1` check at
`e037986` also matched all ten expectations, recorded
[separately](../reference/OWNER_POLICY_CHECK.md#current-coordinator-source-acceptance--2026-10-09-kst).
Both one-run approvals are consumed. Final-head review/CI and delivery subsequently completed in
[PR #97](https://github.com/casing1/authzest/pull/97) on 2026-10-15 KST, without another policy execution.
A host-valid response proves shape/reference checks, not correctness.

Published [v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) remains
package `0.1.0a3`, schema `1.2`. Main has newer unreleased commands; unchanged version output is not proof
that a binary contains them. Do not rewrite existing tags/assets. Windows supports scan; the current
fixture application/runtime mode is supported only on tested POSIX platforms.

## One milestone map

GitHub milestone numbers below are phase identifiers, not development-week numbers or exact release manifests.

| Phase                                       | Current status    | Completion gate / remaining tracking                             |
| ------------------------------------------- | ----------------- | ---------------------------------------------------------------- |
| 01 — CLI foundation and alpha.1 follow-up   | Closed; preserved | Completed foundation history                                     |
| 02 — Source evidence and alpha.2 follow-up  | Closed; preserved | Completed evidence/release follow-up history                     |
| 03 — Offline AI contract and evaluation     | Closed; preserved | #33 contracts/mock evaluation; not actual model-quality results  |
| 04 — User-approved Codex workflow           | Open              | #77/#80 complete; #35 epic still needs #81/#82, #78 coordination |
| 05 — CLI usability and prerelease readiness | Open              | #79 completed; #83 candidate/install/artifact/release gates      |
| 06 — Evaluation and course delivery         | Open              | #84 reviewed comparison, #85 reproducible demo/evidence freeze   |

Authenticated reconciliation under [#78](https://github.com/casing1/authzest/issues/78) refined 04
and created 05/06. #79/#83 are assigned to 05 and #84/#85 to 06; verify their assignee, labels and
milestone fields. Closed 01–03 and historical item assignments are preserved. No due dates are invented. At audit start 04 had 31 closed issue/PR items
and two open issues; an item-count percentage is **not** product or effort completion. Keep closed
historical items in their original phases.

## Remaining backlog and order

| Priority                       | Focused issue                                                                         | Dependencies and acceptance boundary                                                                                                                                                                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Completed                      | [#79 readable CLI](https://github.com/casing1/authzest/issues/79)                     | PR #90 merged; offline formatter/fake-provider checks and exact sharing previews retained                                                                                                                                                                           |
| Completed                      | [#77 case review and fixed plan](https://github.com/casing1/authzest/issues/77)       | Exact ten-label approval recorded separately; original model history and non-executable offline plans preserved; closed by PR #97                                                                                                                                   |
| Completed                      | [#80 fixed owned-policy harness](https://github.com/casing1/authzest/issues/80)       | PR #97 merged; separate recipe 1.0/1.1 source runs matched ten cases each; approvals consumed; exact-head CI/reviews complete                                                                                                                                       |
| In progress: sharing / adapter | [#81 bounded reproduction/remediation](https://github.com/casing1/authzest/issues/81) | S1/pair/recommendation contracts delivered through PRs #99/#101/#102; [exact sharing and adapter stage](../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md) adds an opt-in command. Live acceptance, before/after observations and new-copy remediation remain open |
| Core gate                      | [#82 integrated acceptance](https://github.com/casing1/authzest/issues/82)            | #77/#79/#80/#81; installation, refusal/failure/recovery and separately approved live/runtime evidence                                                                                                                                                               |
| Preview gate                   | [#83 next prerelease](https://github.com/casing1/authzest/issues/83)                  | #77/#79 + exact candidate/platform/install/artifact/publication checks; describe unfinished #35 honestly                                                                                                                                                            |
| Evaluation                     | [#84 measured comparison](https://github.com/casing1/authzest/issues/84)              | Freeze independently reviewed tasks/labels before prompt changes; offline setup can run in parallel, workflow measures after #82                                                                                                                                    |
| Delivery                       | [#85 demo/OSS evidence](https://github.com/casing1/authzest/issues/85)                | #82/#84 results or explicit unavailable evidence; distribution claims consistent with #83                                                                                                                                                                           |

#80's [fixed policy-check API](../reference/OWNER_POLICY_CHECK.md) is delivered with stale/declined/
expired/reused decision handling and unknown failure outcomes. #79 is complete and #77's exact ten
labels have been reviewed. Offline contract/mocked-process tests need no model call or actual policy
execution. Label approval does not authorize execution; any further observation requires a fresh,
separately bounded exact-plan decision. The recipe `1.0` and corrected `1.1` source-run approvals
are both consumed. Their retained observations are not new AI evidence or HTTP authorization proof.

#81 S1's source implementation introduced in PR #99 provides a separate pure recommendation
contract and read-only preview under the bounded continuation above. The registered request contains only the fixed policy source,
policy-only criteria and trusted-input assumptions. Cases, labels, observations, provider/model
claims and approval/execution fields are rejected, not silently accepted. The registry is empty;
`no-change` and `unknown` are valid data statuses, not verified fixes or security verdicts.
No filesystem/network/provider/process access, policy evaluation, CLI or patch capability is added.
The [reference](../reference/OWNER_POLICY_RECOMMENDATION.md) documents the implemented API and an
explicitly SCRIPTED `unknown` example. Implementation CI/review/delivery outcomes are tracked in
PR #99, separately from the unchanged design delivered through PR #98; #81 as a whole remains incomplete.

S1 delivery subsequently completed through PR #99 at merge `4290d2d` on 2026-10-16 KST.
The unchanged historical [repair-pair design](OWNER_POLICY_REPAIR_PAIR_DESIGN.md) was delivered through
PR #100 on 2026-10-19 KST. The maintainer approved that exact test-only ownership-omission scenario,
its source pair and eight assistant-authored expected labels, separately from the next offline
registry/preview implementation slice. Authorship remains assistant-authored; this decision is not
an authenticated approval capability, observation or runtime consent.

The source implementation introduced in PR #101 provides the separate [registered pair API](../reference/OWNER_POLICY_REPAIR_PAIR.md)
with full fixed source/criteria/assumption/case data, a separate review-record binding and host-derived
one-file diff. This unreleased pure API does not call a provider, import/evaluate
the policy, access files/network, execute a process, apply a patch or produce observations. Its state
stays provider `0`, execution/application/restoration `not-run`, before/after observations null,
comparison `not-evaluated` and authorization `unknown`. Existing S1 schema `1.0`/`empty-v1` and
the #80 worker stay unchanged. Model sharing, fixed before/after observations and new-copy
apply/restore require their own later designs and approvals. Do not treat this finite synthetic
regression as a production vulnerability or evaluation set; #81 as a whole remains incomplete.

PR #102 delivered the separate offline repair-recommendation contract: a fixed `before`/`after`
request, strict registered-change/no-change/unknown results and host-derived diff selection.
The next source slice connects it through the separate `codex-owner-repair` command. Complete
source/prompt/schema/settings previews and a fresh exact sharing decision precede one pinned
App Server attempt; preview-only remains offline. Host transport metadata is not signed provider
provenance, and validated explanations/expected effects are not observed policy behavior.
Offline refusal, stale-sharing and scripted-response checks precede separately approved live
acceptance. Fixed before/after worker observations and new-copy apply/restore remain later stages;
existing `codex-owner-review`, S1 and the #80 worker stay unchanged.

Implemented #79 defines human-readable defaults and explicit JSON compatibility: one final result on stdout
in JSON mode, interactive previews/prompts/progress on stderr, and one complete preview for preview-only
JSON. Preserve exact identity-bound sharing content before consent; summaries alone are insufficient.
The guides document the default-output migration rather than claiming unchanged stdout behavior.

A future preview may follow #77/#79 without waiting for complete #35 if its implemented scope and
limitations are explicit. It still requires #83's own checks; a docs PR or passing mock is not a release gate.

## Core acceptance and defensive PoC

- [x] Exact ten-case label review recorded separately on 2026-10-09 KST (#77); offline contracts exist, but plans remain non-executable and execution consent is separate.
- [x] Readable CLI results, retained records and documented text/JSON streams accepted (#79 / PR #90).
- [x] #80 source-only fixed harness delivered through [PR #97](https://github.com/casing1/authzest/pull/97), with exact-head CI/code/security reviews complete on 2026-10-15 KST. Source observations are not endpoint authorization evidence.
- [ ] Reviewed bounded defensive reproduction and evidence-linked remediation/no-change accepted (#81).
- [ ] Installed coherent end-to-end flow, failure/refusal/user-edit/recovery cases and required reviews pass (#82); only then close #35.
- [ ] Frozen independent reference review and measured evaluation, or explicit unavailable evidence, recorded (#84).
- [ ] Exact distribution claims, reproducible demo and course evidence freeze accepted (#83/#85).

“PoC” means local synthetic **defensive regression reproduction** for an explicitly owned pure policy,
not an internet exploit or executing AI-written Python/shell. Model-authored cases are data consumed by
a fixed reviewed decoder/harness. Pure-policy observations do not test HTTP authentication, dependencies,
DB or real endpoint enforcement. A child process is not an OS/network sandbox.

The current correct policy must allow a no-change/unknown result. The exact clearly labelled,
intentionally incorrect test-only pair and eight labels were reviewed on 2026-10-19 KST; that review
does not authorize runtime observation or patch application. Do not invent a production vulnerability
to force a patch or extend this approval to changed bytes/cases.

Source sharing, exact-case label review, exact-diff approval/application, before/after checks and restore
are separate bound decisions. Changes to relevant source/cases/plan require fresh decisions. Planning
approval, tool permission or an earlier live run cannot authorize them. Record applied/checked/restored/
failed/not-run/unknown distinctly and preserve originals and later user edits.

## Schedule: keep the existing seven-week budget

The seven **development** weeks agreed on 2026-09-10 include work already done; this audit does not
start a fresh seven-week plan. The original remaining-calendar estimate is historical, not a current
submission date. Confirm the actual course date/rubric before adding deadlines.

Foundation/evidence/offline contracts and partial live integration already consume the early delivery
budget. Use remaining working sessions for the focused core/usability gates, then evaluation/failure/
installation checks and demo freeze. Preserve the separate exam/slippage/submission buffer; do not
fill it with optional features. If time or provider approval is unavailable, cut optional scope and
report the live/verification gap honestly. Do not call an incomplete core complete.

## Deliberately deferred

General nested dependency/callable interpretation, broad authentication/security classification,
multi-file/existing-checkout transactions, arbitrary repositories/apps/generated code execution,
additional adapters, AI dashboard/deployment and signing/notarization are not prerequisites for the
bounded course core. Open a separately justified issue before reconsidering one. The static parser
still needs maintained regressions, but finishing a complete deterministic vulnerability engine is
not a dependency of the Codex improvement demo.

## Working rules

Use focused issue → short-lived branch → meaningful implementation/tests → bilingual docs → PR →
exact-head required CI and resolved review conversations → merge commit. Assign casing1, relevant
existing labels and a verified milestone to every issue/PR; #1 deliberately spans phases without a
single milestone. Preserve historical authorship and approvals. Mark criteria complete only when
actually satisfied and merged; do not inflate commit counts.

English documents require Korean counterparts; the root README additionally requires Japanese and
Russian. Update guides only for implemented behavior and keep links/commands/status/limitations aligned.
No planning change grants paid/manual reviews, source transmission, case review, patch/execution or
publication. See [contributing](../../CONTRIBUTING.md) and [branch rules](BRANCH_RULES.md).
