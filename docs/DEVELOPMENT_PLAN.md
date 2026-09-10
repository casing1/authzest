<p align="center">
  <strong>English</strong> ·
  <a href="i18n/DEVELOPMENT_PLAN.ko.md">한국어</a>
</p>

# AuthZest Development Plan

[Documentation index](README.md) · [Public roadmap](https://github.com/casing1/authzest/issues/1)

## Product direction

Build an installable, CLI-first, source-aware FastAPI access-control review and improvement tool for an
OSS course. The final demo must connect Codex to source evidence, reviewable defensive regression-test
and patch proposals, an explicit approve/decline decision, approved-only patch application, and separately
approved isolated verification with a change record. Codex integration is a core product goal, not a
later optional explanation feature. These stages are planned, not implemented capabilities.

The static core must still produce useful, repeatable evidence without an AI provider. Each Codex use
is opt-in; external data sharing, applying a specific patch, and executing a verification plan require
distinct permissions. An AI assumption must never become a confirmed finding merely because it is generated.

The existing local API and dashboard are optional interfaces to the same core. Website deployment,
a native desktop shell, and new UI features are not prerequisites for the CLI milestone. Keep the
`analyzer`, `parser`, `runner`, and `codex` boundaries independent of transports.

The [roadmap issue](https://github.com/casing1/authzest/issues/1) is the public task tracker. This document
explains ordering and completion criteria. Split a task into a bounded issue before implementation;
mark it complete only when its acceptance criteria and required PR checks pass and it merges.

Model upgrades are not a reason to replace the core with an autonomous agent. Treat the benefit of
evidence-assisted AI over a direct model as a measurable hypothesis; see the [model strategy](MODEL_STRATEGY.md).
Limit syntax expansion to maintained use cases. Prioritize evidence identity and evaluation over new UI
features, extra adapters, or a general-purpose Python interpreter.

## Seven-week delivery plan

As of 2026-09-10, approximately 11–12 weeks remain and the course has no mandated feature list. Allocate
only **seven development weeks**; leave **four to five weeks outside that plan** for exams, slippage,
and final submission preparation. These are working-week estimates, not seven uninterrupted calendar
weeks or a commitment to fill all remaining time. Pause development during exams and reduce scope if needed.

| Development week | Bounded outcome                                                         | Completion gate                                                                                       |
| ---------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 1                | Reliability baseline and report contract (#31, #32)                     | Reproducible demo; versioned diagnostics and distinct registration evidence tested                    |
| 2                | Route-local dependency evidence (#28)                                   | Supported declarations, ordinary DI, and unresolved cases have source-backed expectations             |
| 3                | Inherited context (#29) and a small policy-labelled fixture set         | Repeated mounts remain distinct; public/authentication/authorization expectations are explicit        |
| 4                | Offline proposal and approval contract after #33                        | Mock responses, invalid references, exact-diff approval, stale input, and decline paths tested        |
| 5                | One opt-in Codex integration and a small owned-fixture improvement flow | Review → approve/decline → approved patch → separately approved isolated verification demonstrated    |
| 6                | Failure/recovery cases, installation, and a small three-mode evaluation | Failed tests, stale approval, user edits, and recovery handled; actual usage and limitations recorded |
| 7                | Freeze a coherent CLI demo and submission evidence                      | Reproducible demo, reviewed documentation, issue/PR/test history, and release checklist ready         |

A new preview release is conditional on its checks, not required every week. Week 5 does not require
finishing all deterministic findings first. Demonstrate one bounded, user-approved improvement flow on
a maintained owned fixture, not a general autonomous scanner. If provider or execution approval is absent,
retain an explicitly labelled mock demo and report the live integration as incomplete. If the schedule
slips, cut extra rules, UI work, multiple integrations, and broader execution support; preserve the core
approval flow, reviewable evidence, tests, and honest evaluation. Do not silently consume the exam/submission
buffer to expand features.

## Current baseline

- [x] Installable Python CLI with `scan`, `doctor`, `ui`, and basic text/JSON reports.
- [x] Optional workspace-bound local API and React dashboard.
- [x] FastAPI/APIRouter owner recognition ([#19](https://github.com/casing1/authzest/issues/19)).
- [x] Literal same-file router prefixes and registrations ([#21](https://github.com/casing1/authzest/issues/21)).
- [x] Repository-local static router imports and cross-file registration ([#25](https://github.com/casing1/authzest/issues/25)).
- [x] Documented source-syntax subset and limitations in the [parser scope](PARSER_SCOPE.md).
- [x] Python/frontend CI, CLI/API fixture regressions, required CodeQL checks, and issue-linked
      merge-commit workflow.
- [x] PyInstaller packaging and the published `v0.1.0-alpha.1` preview with checksums.
- [x] Maintained [source-only demo](EXAMPLES.md), exact inventory regression, and documentation checks in CI.

The latest source includes unreleased parser improvements; the published alpha binary does not include
them. Package metadata still uses `0.1.0a1`, so a version string alone does not identify these source
changes. Consult the [changelog](../CHANGELOG.md) and release tag.

Current-source JSON uses schema `1.0`, structured diagnostics, bounded/partial status, and distinct
source registration evidence; see the [report contract](REPORT_CONTRACT.md). Dependency analysis,
authentication/authorization classification, finding schemas, Codex review, patch application, and
verification execution are not implemented. `scan` does not execute the target application or Codex.
Explicitly running `doctor` can invoke an installed Codex CLI for diagnostics.

## Prerequisite — Evidence and diagnostics contract

- [x] Define a versioned report, compatibility policy, and deterministic ordering
      ([#32](https://github.com/casing1/authzest/issues/32)).
- [x] Give route registrations distinct stable identities with original handler, application, and
      include-site provenance, including identical-path repeated mounts.
- [x] Represent known unresolved reasons, source/read errors, and bounded analysis explicitly; document
      and test text/JSON output and CLI exit semantics without claiming exhaustive unsupported-pattern detection.

Completion: positive, repeated-mount, dynamic, malformed-source, and stable-order fixtures exercise the
current-source contract. The next core tasks are #28/#29; dependency and policy data will extend this
foundation without claiming complete Python coverage or runtime registration certainty.

## Milestone 1 — Dependency evidence

1. [ ] Collect route-local declarations ([#28](https://github.com/casing1/authzest/issues/28)):
       parameter defaults, supported inline `Annotated`, and decorator `dependencies`.
       Recognize actual `Depends`/`Security` imports, aliases, and shadowing. Record kind, target,
       source position, declaration level, resolution state, and statically known scopes.
2. [ ] Propagate application/router/`include_router` evidence to each route registration
       ([#29](https://github.com/casing1/authzest/issues/29)), using #32's registration identity and retaining
       distinct repeated-mount contexts rather than grouping by path or handler alone.
3. [ ] Resolve a documented subset of dependency references and nested dependency relationships.
       Keep missing, cyclic, dynamic, overridden, or unsupported relationships explicit rather than guessing.
4. [ ] Expose unresolved evidence and parsing limitations in reports instead of treating missing
       evidence as a negative security result.

Completion: supported local fixtures have the expected declaration evidence and original source positions
in CLI/API reports. Existing route fields remain compatible or a deliberate schema change is documented.
Each issue includes positive, ordinary non-security, and unresolved cases; scanned source is never executed.

## Milestone 2 — Interpretation and report contract

- [ ] Distinguish authentication (who the caller is) from authorization (what they may access).
- [ ] Define the supported evidence rules, explicitly public endpoints, and unsupported middleware,
      overrides, custom checks, and object-level policies before choosing classification labels.
- [ ] Represent observed declarations separately from authentication evidence, authorization evidence,
      and unknown/incomplete analysis. Neither `Depends` nor `Security` alone proves protection.
- [ ] Extend the prerequisite report contract for policy evidence and eventual findings, maintaining
      deterministic ordering, source-path handling, and text/JSON compatibility.
- [ ] Extend the prerequisite CLI exit contract when eventual findings are introduced.
      A successful scan or zero routes must not be described as a security pass.
- [ ] Add a small maintained local fixture corpus with expected policy annotations and expected results.
      Include public endpoints, ordinary DI, authentication checks, role/ownership scenarios, and unresolved cases.

Completion: a reviewer can explain every reported state from source evidence and the documented rule.
The fixture corpus reports matches, false positives, false negatives, and unknown cases; unsupported
application behavior is not silently declared safe or vulnerable.

The current [report contract](REPORT_CONTRACT.md) retains exit code 0 for a returned report by default,
even when analysis is partial. Opt-in `--strict` returns 1 for known partial analysis; invalid repository
input returns 2. Structured diagnostics record selected unresolved cases and source/read errors, not every
unsupported declaration. Neither `bounded` status nor exit code 0 means complete analysis or a security pass.

## Milestone 3 — Explainable deterministic checks

- [ ] Add narrowly scoped source checks against documented or user-declared access-control expectations;
      absence of a recognizable dependency alone is not a vulnerability.
- [ ] Attach source evidence and separate severity, confidence, and analysis completeness.
- [ ] Add reasoned suppression, regression cases, and stable finding export on top of the existing JSON report.
- [ ] Document how findings should be reviewed and what the tool cannot establish, including general
      runtime authorization correctness and object ownership guarantees.

Completion: every rule has matching, nonmatching, and unresolved fixtures and an explanation that can be
reviewed without AI. Checks run locally on source code without generating or executing exploitation steps.

## Milestone 4 — Codex-assisted, user-approved improvement

This is the final-demo target after the evidence/report contract and initial dependency fixtures.
Implement a bounded end-to-end flow before expanding rules or adding a second integration. The offline
contract and mocks in [#33](https://github.com/casing1/authzest/issues/33) remain prerequisites;
[#35](https://github.com/casing1/authzest/issues/35) tracks the bounded Codex proposal, approval, application,
and verification workflow. These are future tasks, not features enabled by the report contract.

- [ ] Define evidence-linked explanations and offline evaluation
      ([#33](https://github.com/casing1/authzest/issues/33)); extend the disabled adapter with mock responses,
      invalid-reference cases, and failure tests.
- [ ] Define the permitted evidence payload, data minimization, secret handling, timeout, cancellation,
      and separate data-sharing, patch-application, and verification-execution permissions before live calls.
- [ ] Add one opt-in Codex adapter behind the interface; choose CLI or App Server, not both. Keep AI
      suggestions separate from deterministic results and preserve the local report on adapter failure.
- [ ] Generate evidence-linked explanations, defensive regression-test drafts, and a reviewable diff in
      an isolated temporary workspace. Do not execute scanned source or write the user's worktree while proposing.
- [ ] Present rationale, affected files, the exact diff, source revision/content identity, and verification
      plan. Bind approval to that proposal; decline/cancel changes nothing, and changed inputs invalidate approval.
- [ ] Apply only the approved diff after rechecking its preconditions. Preserve existing user edits,
      record before/after content identities, and provide recoverable changes without resetting unrelated work.
- [ ] Separately approve and run a bounded isolated verification plan for a maintained owned fixture.
      Record commands, exit status, results, and failures; a patch applied or a test passed is not proof
      of general authorization correctness. Never label failed or unrun verification as a successful fix.
- [ ] Compare static-only, model-only, and evidence-assisted model modes on frozen, human-labelled fixtures,
      with held-out cases, repeated trials, actual usage, and limitations as described in the [model strategy](MODEL_STRATEGY.md).

Completion: one maintained fixture demonstrates evidence → Codex review/proposal → approve or decline →
approved patch → separately approved verification → change/result record. Tests cover invalid citations,
provider failure, changed source or diff, pre-existing user edits, declined/cancelled requests, failed
verification, and recovery conflicts. The default scan and CI remain offline and do not require credentials.
Do not substitute Codex's settings-dependent tool approvals for AuthZest's exact-proposal approval gate.

## Milestone 5 — CLI release and OSS evaluation

Release preparation can proceed alongside the milestones above; packaging is already present and does not
need to be rebuilt as a new product.

- [ ] Run the installed CLI/binary against the maintained policy fixture corpus in CI, beyond the
      existing in-process CLI/API regression tests.
- [ ] Verify clean installation, execution, and upgrade for each advertised OS/architecture.
- [ ] Define a tested support matrix and reproducible Python dependency constraints/build manifest rather
      than assuming every allowed dependency version is equivalent.
- [ ] Verify release notes, both changelogs, tag/package version, and actual binary contents together.
      The current release script checks tag/version spelling, not changelog completeness.
      Automate the missing changelog/content consistency checks as a separate release task.
- [ ] Publish a new preview from a verified `main` commit when a coherent milestone is ready.
- [ ] Preserve issue decisions, meaningful commits, PR discussion, CI evidence, and a short reproducible demo.
- [ ] Consider signing/notarization separately before broader binary distribution.

Completion: the documented CLI demo works from a clean installation, release claims match the downloaded
binary, and changes can be traced from issue to test to PR. Do not inflate commit counts or publish a new
release for every documentation edit. See the [release guide](RELEASING.md).

## Execution scope and deliberate exclusions

The bounded verification in milestone 4 belongs to the core demo, but it is never an implicit part of
`scan` or permission to execute an arbitrary repository. Start only with a maintained owned fixture and
a reviewed defensive regression plan in an isolated environment with explicit input/output scope,
timeouts, and protection against unintended data changes. Test drafts are untrusted until reviewed.

Internet-target scanning, exploit-PoC generation or execution, autonomous offensive workflows, and arbitrary
repository execution are out of scope. Broader runtime coverage or additional execution environments need
a separate design issue; they are not a condition for the seven-week deliverable.

## Working checklist

Before implementation, record the issue, supported subset, completion criteria, and a branch from current
`main`. During implementation, add tests alongside each behavior and avoid unrelated refactoring.
Before merge, update the English source and required translations together, verify links and commands,
and pass Python, frontend, and CodeQL checks. Use meaningful commits and a merge commit, then synchronize
the roadmap and remove the working branch. See [contributing](../CONTRIBUTING.md) and
[branch rules](BRANCH_RULES.md).
