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

## Current baseline — 2026-10-02

Baseline main: `142a0dc71c70a95554e837d7a95eda5629038c82`, PR #76 merged on 2026-10-01.
Historical records live in the [changelog](../../CHANGELOG.md), linked issues/PRs and
[release record](../releases/RELEASING.md); this plan records current priorities, not every past test count.

| Implemented                                   | Actual boundary                                                                                                                        |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Installed CLI, local API/UI and static parser | Bounded FastAPI route/registration/local-inherited dependency declarations; no complete Python interpretation or authorization verdict |
| Evidence, proposal and expectation contracts  | Exact identities/references, draft expectations and read-only comparison; schema `1.2`                                                 |
| Mock review/walkthrough and copy application  | Separate source/apply/check/restore decisions; new owned single-file POSIX copy, not arbitrary checkout editing                        |
| Opt-in App Server fixture workflow            | Pinned adapter, exact sharing approval; default AST check, separately approved fixed debug/health runtime option                       |
| Owned report policy example                   | Pure-policy developer tests and scanner inventory; authentication is unconfigured/fail-closed, no HTTP authorization acceptance        |
| Read-only owner Codex review (#75 / PR #76)   | Exact two-source sharing; one approved live run returned one host-valid answer / ten unexecuted cases, not a patch or security proof   |

The recorded owner review at `9257bd7` took about 74 seconds. Its model-authored ten-case expectations
remain **unreviewed**, execution not-run and authorization unknown. The maintainer approved policy
criteria, not these labels or the separate 28 assistant-authored developer-test labels.
[#77](https://github.com/casing1/authzest/issues/77) preserves the exact review envelope/digest.
A host-valid response proves shape/reference checks, not semantic correctness.

Published [v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) remains
package `0.1.0a3`, schema `1.2`. Main has newer unreleased commands; unchanged version output is not proof
that a binary contains them. Do not rewrite existing tags/assets. Windows supports scan; the current
fixture application/runtime mode is supported only on tested POSIX platforms.

## One milestone map

GitHub milestone numbers below are phase identifiers, not development-week numbers or exact release manifests.

| Phase                                       | Current status    | Completion gate / remaining tracking                                 |
| ------------------------------------------- | ----------------- | -------------------------------------------------------------------- |
| 01 — CLI foundation and alpha.1 follow-up   | Closed; preserved | Completed foundation history                                         |
| 02 — Source evidence and alpha.2 follow-up  | Closed; preserved | Completed evidence/release follow-up history                         |
| 03 — Offline AI contract and evaluation     | Closed; preserved | #33 contracts/mock evaluation; not actual model-quality results      |
| 04 — User-approved Codex workflow           | Open              | #35 epic; #77/#80/#81/#82 core gates, #78 coordination               |
| 05 — CLI usability and prerelease readiness | Open              | #79 human-readable CLI, #83 candidate/install/artifact/release gates |
| 06 — Evaluation and course delivery         | Open              | #84 reviewed comparison, #85 reproducible demo/evidence freeze       |

Authenticated reconciliation under [#78](https://github.com/casing1/authzest/issues/78) refined 04
and created 05/06. #79/#83 are assigned to 05 and #84/#85 to 06; verify their assignee, labels and
milestone fields. Closed 01–03 and historical item assignments are preserved. No due dates are invented. At audit start 04 had 31 closed issue/PR items
and two open issues; an item-count percentage is **not** product or effort completion. Keep closed
historical items in their original phases.

## Remaining backlog and order

| Priority     | Focused issue                                                                         | Dependencies and acceptance boundary                                                                                             |
| ------------ | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Now          | [#79 readable CLI](https://github.com/casing1/authzest/issues/79)                     | Offline formatter/fake-provider tests; complete sharing preview and separate decisions remain visible                            |
| Now          | [#77 case review and fixed plan](https://github.com/casing1/authzest/issues/77)       | Offline states/identities/plan contract; pending labels prevent verified results, not contract implementation                    |
| Next         | [#80 fixed owned-policy harness](https://github.com/casing1/authzest/issues/80)       | #77 + explicitly reviewed exact case set + fresh separately approved execution plan                                              |
| Then         | [#81 bounded reproduction/remediation](https://github.com/casing1/authzest/issues/81) | Review design first; implementation depends on #80; exact owned single-file diff or valid no-change                              |
| Core gate    | [#82 integrated acceptance](https://github.com/casing1/authzest/issues/82)            | #77/#79/#80/#81; installation, refusal/failure/recovery and separately approved live/runtime evidence                            |
| Preview gate | [#83 next prerelease](https://github.com/casing1/authzest/issues/83)                  | #77/#79 + exact candidate/platform/install/artifact/publication checks; describe unfinished #35 honestly                         |
| Evaluation   | [#84 measured comparison](https://github.com/casing1/authzest/issues/84)              | Freeze independently reviewed tasks/labels before prompt changes; offline setup can run in parallel, workflow measures after #82 |
| Delivery     | [#85 demo/OSS evidence](https://github.com/casing1/authzest/issues/85)                | #82/#84 results or explicit unavailable evidence; distribution claims consistent with #83                                        |

Immediate work: brief the maintainer, then implement #79 CLI readability and #77 offline contracts in
separate issue-linked PRs. No real model call, case-label approval or target execution is needed for
those implementation tests. Do not block all offline work on the pending ten-label decision.

For #79, define human-readable defaults and explicit JSON compatibility: one final result on stdout
in JSON mode, interactive previews/prompts/progress on stderr, and one complete preview for preview-only
JSON. Preserve exact identity-bound sharing content before consent; summaries alone are insufficient.
Document the default-output migration rather than claiming unchanged stdout behavior.

A future preview may follow #77/#79 without waiting for complete #35 if its implemented scope and
limitations are explicit. It still requires #83's own checks; a docs PR or passing mock is not a release gate.

## Core acceptance and defensive PoC

- [ ] Exact case review and fixed verification-plan contracts accepted (#77).
- [ ] Readable CLI results, retained records and documented text/JSON streams accepted (#79).
- [ ] Maintained fixed policy worker produces expected-versus-observed results under a new separate approval (#80).
- [ ] Reviewed bounded defensive reproduction and evidence-linked remediation/no-change accepted (#81).
- [ ] Installed coherent end-to-end flow, failure/refusal/user-edit/recovery cases and required reviews pass (#82); only then close #35.
- [ ] Frozen independent reference review and measured evaluation, or explicit unavailable evidence, recorded (#84).
- [ ] Exact distribution claims, reproducible demo and course evidence freeze accepted (#83/#85).

“PoC” means local synthetic **defensive regression reproduction** for an explicitly owned pure policy,
not an internet exploit or executing AI-written Python/shell. Model-authored cases are data consumed by
a fixed reviewed decoder/harness. Pure-policy observations do not test HTTP authentication, dependencies,
DB or real endpoint enforcement. A child process is not an OS/network sandbox.

The current correct policy must allow a no-change/unknown result. If a negative scenario is necessary,
propose a clearly labelled intentionally incorrect test-only variant for maintainer design review
before implementation; do not invent a production vulnerability to force a patch.

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
