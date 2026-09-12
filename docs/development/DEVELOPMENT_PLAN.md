<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/DEVELOPMENT_PLAN.md">한국어</a>
</p>

# AuthZest Development Plan

[Documentation index](../README.md) · [Public roadmap](https://github.com/casing1/authzest/issues/1)

## Product direction

Build an installable, CLI-first, source-aware FastAPI access-control review and improvement tool for an
OSS course. The final demo must connect Codex to source evidence, reviewable defensive regression-test
and patch proposals, an explicit approve/decline decision, approved-only patch application, and separately
approved isolated verification with a change record. Codex integration is a core product goal, not a
later optional explanation feature. The full flow remains unfinished. #33/#46/#48 are offline slices;
[#50](../guides/CODEX_FIXTURE.md) adds an opt-in owned-fixture App Server draft; one live draft/apply/restore check passed.

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

A new preview release is conditional on its checks, not required every week.
[v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2), package `0.1.0a2`, was
published after #28/#29 and release issue #39. Bilingual changelog checks, three-OS builds, and fresh
downloaded-artifact fixture checks passed for its exact commit; see the [release record](../releases/RELEASING.md).
Consumer-device clean installation and upgrades remain unverified. Future releases need their own checks.
This does not restart the seven-week plan or consume the exam buffer. Week 5 does not require
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
- [x] Documented source-syntax subset and limitations in the [parser scope](../reference/PARSER_SCOPE.md).
- [x] Python/frontend CI, CLI/API fixture regressions, required CodeQL checks, and issue-linked
      merge-commit workflow.
- [x] PyInstaller packaging and the published `v0.1.0-alpha.1` preview with checksums.
- [x] Publish `v0.1.0-alpha.2` with schema `1.2`, local/inherited evidence, and checked three-platform
      binaries ([#39](https://github.com/casing1/authzest/issues/39), [PR #40](https://github.com/casing1/authzest/pull/40)).
- [x] Maintained [source-only demo](../guides/EXAMPLES.md), exact inventory regression, and documentation checks in CI.

The parser/report/dependency improvements are now in alpha.2, not just an unreleased source checkout.
The release commit is `7cc359acbb864ef6d31e3b536787857da4f7e09c`; consult the
[changelog](../../CHANGELOG.md) and release record before equating later `main` changes with those binaries.

Current-source JSON uses schema `1.2`, structured diagnostics, bounded/partial status, distinct
source registration evidence, and route-local plus inherited dependency declarations; see the [report contract](../reference/REPORT_CONTRACT.md).
The source-only [offline AI contract and mock evaluation](../reference/AI_CONTRACT.md) is implemented
after alpha.2; the published binaries remain unchanged.
Nested dependency graphs, authentication/authorization classification, finding
schemas, general repository AI review and existing-checkout patch application are not implemented.
The [#48 application demo](../guides/FIXTURE_APPLICATION.md) changes only a fresh POSIX fixture copy.
The separate [#50 Codex fixture command](../guides/CODEX_FIXTURE.md) uses pinned Codex 0.153.0 and at most one
application-issued turn after sharing approval; one owned-fixture live check passed. It only accepts the maintained
debug-setting change and retains separate copy-application/restoration decisions. That live check did not
run verification. #52 adds an optional, separately approved fixed-source check of the applied copy;
that static-only mode leaves runtime verification `not-run` and supplies no new live-model evidence.
#54 adds a separate opt-in [runtime plan](../guides/RUNTIME_VERIFICATION.md) for the exact bundled
configuration/health fixture, not arbitrary source or authorization testing. End-to-end acceptance
and release gates remain distinct from implementing the checker.
`scan` does not execute the target application or Codex.
Explicitly running `doctor` can invoke an installed Codex CLI for diagnostics.

## Prerequisite — Evidence and diagnostics contract

- [x] Define a versioned report, compatibility policy, and deterministic ordering
      ([#32](https://github.com/casing1/authzest/issues/32)).
- [x] Give route registrations distinct stable identities with original handler, application, and
      include-site provenance, including identical-path repeated mounts.
- [x] Represent known unresolved reasons, source/read errors, and bounded analysis explicitly; document
      and test text/JSON output and CLI exit semantics without claiming exhaustive unsupported-pattern detection.

Completion: positive, repeated-mount, dynamic, malformed-source, and stable-order fixtures exercise the
current-source contract. Route-local declarations (#28) and inherited registration context (#29) are
included in alpha.2. The offline AI contract (#33) is now implemented in source; next is the user-approved
Codex workflow (#35), without claiming complete Python coverage or runtime registration certainty.

## Milestone 1 — Dependency evidence

1. [x] Collect route-local declarations ([#28](https://github.com/casing1/authzest/issues/28)):
       parameter defaults, supported inline `Annotated`, and decorator `dependencies`.
       Recognize actual `Depends`/`Security` imports, aliases, and shadowing. Record kind, target,
       source position, declaration level, resolution state, and statically known scopes.
       `reference` identifies simple/dotted-name syntax, not callable/import resolution or protection.
2. [x] Propagate application/router/`include_router` evidence to each route registration
       ([#29](https://github.com/casing1/authzest/issues/29)), using #32's registration identity and retaining
       distinct repeated-mount contexts rather than grouping by path or handler alone.
       Keep route-local `dependencies` unchanged and expose the combined source context in
       `effective_dependencies`, not as a runtime execution order or authorization verdict.
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

The current [report contract](../reference/REPORT_CONTRACT.md) retains exit code 0 for a returned report by default,
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
and verification workflow. The offline slices and the narrowly scoped #50 adapter do not complete it;
one owned-fixture live draft/apply/restore check passed for #50. #52's source-configuration check does
not complete runtime verification. #54 supplies the bounded runtime implementation; complete its
end-to-end acceptance before declaring the core demonstration ready. Broader proposal scope is separate work.

- [x] Define evidence-linked explanations and offline evaluation
      ([#33](https://github.com/casing1/authzest/issues/33)): minimized immutable requests, strict response/reference
      validation, mock lifecycle tests, and a frozen three-mode harness. Policy criteria are maintainer-approved;
      labels are assistant-authored/code-checked and mock scores do not establish live model performance.
- [x] Implement the offline proposal/decision slice ([#46](https://github.com/casing1/authzest/issues/46)):
      exact-content diff previews, bound explicit decisions, expiry and supplied stale-state checks.
      The [contract](../reference/PROPOSAL_CONTRACT.md) does not apply files, execute checks, or authenticate consent.
- [x] Add [#48's owned-fixture copy application](../guides/FIXTURE_APPLICATION.md): explicit terminal
      decisions, single-session consumption, POSIX file/state checks, atomic single-file replacement,
      retained records and separately confirmed restoration. Existing checkouts and verification remain untouched.
- [x] Validate [#50's fixed-fixture sharing and adapter boundary](../guides/CODEX_FIXTURE.md):
      exact-request approval, minimized input, timeout/cancellation and separate copy-application decisions.
      Broader input sharing and verification permissions need their own design and acceptance evidence.
- [x] Complete one owned-fixture live draft/apply/restore check of the selected, version-pinned Codex
      App Server adapter. The assistant entered approval phrases under user authorization, not independent
      human review. The source-only fixture command keeps suggestions separate from static reports;
      that #50 slice added no second transport or verification executor.
- [x] Complete offline validation of #52's optional source-configuration check: a separate exact-plan
      decision, fixed AST configuration subprocess with pinned source hashes, bounded output/time, honest skip/failure records, and
      independently offered restoration. This is not target execution or runtime/security-fix verification.
- [ ] Generate evidence-linked explanations, defensive regression-test drafts, and a reviewable diff in
      an isolated temporary workspace. Do not execute scanned source or write the user's worktree while proposing.
- [ ] Present rationale, affected files, the exact diff, source revision/content identity, and verification
      plan. Bind approval to that proposal; decline/cancel changes nothing, and changed inputs invalidate approval.
- [ ] Apply only the approved diff after rechecking its preconditions. Preserve existing user edits,
      record before/after content identities, and provide recoverable changes without resetting unrelated work.
- [x] Implement a separately approved bounded runtime plan for the exact maintained configuration/health
      fixture (#54); source mode remains the default. Record fixed checks, exits, results, and failures.
      Applying a patch or passing a test is not proof
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

- [x] For alpha.2, check four owned source-only fixtures through built/relocated binaries and fresh
      downloaded-artifact jobs on Linux x64, macOS arm64, and Windows x64; verify checksums (#39).
- [ ] Run the installed CLI/binary against the maintained policy fixture corpus in CI, beyond the
      existing in-process CLI/API regression tests.
- [ ] Verify clean installation, execution, and upgrade for each advertised OS/architecture.
- [ ] Define a tested support matrix and reproducible Python dependency constraints/build manifest rather
      than assuming every allowed dependency version is equivalent.
- [x] Verify alpha.2 release notes, both changelogs, tag/package version, and actual binary contents together (#39).
      The release script checks tag/version spelling and matching dated, nonempty English/Korean entries;
      it does not replace the semantic content and artifact review performed for alpha.2.
- [x] Publish alpha.2 from the verified `main` commit after its artifact gates pass (#39).
- [ ] Repeat version, content, artifact, publication, and documentation checks for each future release.
- [ ] Preserve issue decisions, meaningful commits, PR discussion, CI evidence, and a short reproducible demo.
- [ ] Consider signing/notarization separately before broader binary distribution.

Completion: the documented CLI demo works from a clean installation, release claims match the downloaded
binary, and changes can be traced from issue to test to PR. Do not inflate commit counts or publish a new
release for every documentation edit. See the [release guide](../releases/RELEASING.md).

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
the roadmap and remove the working branch. See [contributing](../../CONTRIBUTING.md) and
[branch rules](BRANCH_RULES.md).
