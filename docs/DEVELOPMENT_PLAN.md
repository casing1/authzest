<p align="center">
  <strong>English</strong> ·
  <a href="i18n/DEVELOPMENT_PLAN.ko.md">한국어</a>
</p>

# AuthZest Development Plan

[Documentation index](README.md) · [Public roadmap](https://github.com/casing1/authzest/issues/1)

## Product direction

Build an installable, CLI-first, source-aware FastAPI access-control analysis tool for an OSS course.
The core must produce useful, repeatable source evidence without an AI provider. Optional AI assistance
can later explain that evidence and its limitations; it must not turn an assumption into a confirmed finding.

The existing local API and dashboard are optional interfaces to the same core. Website deployment,
a native desktop shell, and new UI features are not prerequisites for the CLI milestone. Keep the
`analyzer`, `parser`, `runner`, and `codex` boundaries independent of transports.

The [roadmap issue](https://github.com/casing1/authzest/issues/1) is the public task tracker. This document
explains ordering and completion criteria. Split a task into a bounded issue before implementation;
mark it complete only when its acceptance criteria and required PR checks pass and it merges.

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

The latest source includes unreleased parser improvements; the published alpha binary does not include
them. Package metadata still uses `0.1.0a1`, so a version string alone does not identify these source
changes. Consult the [changelog](../CHANGELOG.md) and release tag.

Basic JSON already exists. Versioned evidence/finding schemas, dependency analysis, authentication or
authorization classification, AI analysis, and active testing do not. `scan` does not execute the target
application or Codex. Explicitly running `doctor` can invoke an installed Codex CLI for diagnostics.

## Milestone 1 — Dependency evidence

1. [ ] Collect route-local declarations ([#28](https://github.com/casing1/authzest/issues/28)):
       parameter defaults, supported inline `Annotated`, and decorator `dependencies`.
       Recognize actual `Depends`/`Security` imports, aliases, and shadowing. Record kind, target,
       source position, declaration level, resolution state, and statically known scopes.
2. [ ] Propagate application/router/`include_router` evidence to each route registration
       ([#29](https://github.com/casing1/authzest/issues/29)), retaining distinct repeated-mount contexts.
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
- [ ] Define a versioned evidence/report schema, deterministic ordering, source-path handling, and
      compatibility policy for text and JSON consumers.
- [ ] Define and test CLI exit codes for invalid input, incomplete analysis, and eventual findings.
      A successful scan or zero routes must not be described as a security pass.
- [ ] Add a small maintained local fixture corpus with expected policy annotations and expected results.
      Include public endpoints, ordinary DI, authentication checks, role/ownership scenarios, and unresolved cases.

Completion: a reviewer can explain every reported state from source evidence and the documented rule.
The fixture corpus reports matches, false positives, false negatives, and unknown cases; unsupported
application behavior is not silently declared safe or vulnerable.

Current behavior is not the future contract: `scan` reports invalid repository paths with exit code 2,
while returned parse errors can coexist with a successful exit. The CLI/API currently have no dedicated
list of unresolved declarations. Those gaps must be addressed before security verdicts are introduced.

## Milestone 3 — Explainable deterministic checks

- [ ] Add narrowly scoped source checks against documented or user-declared access-control expectations;
      absence of a recognizable dependency alone is not a vulnerability.
- [ ] Attach source evidence and separate severity, confidence, and analysis completeness.
- [ ] Add reasoned suppression, regression cases, and stable finding export on top of the existing JSON report.
- [ ] Document how findings should be reviewed and what the tool cannot establish, including general
      runtime authorization correctness and object ownership guarantees.

Completion: every rule has matching, nonmatching, and unresolved fixtures and an explanation that can be
reviewed without AI. Checks run locally on source code without generating or executing exploitation steps.

## Milestone 4 — Optional AI-assisted explanation

This follows a stable evidence/report contract and comes before any optional active test runner.
A small, clearly labelled explanation demo can support the term project without requiring a complete
vulnerability scanner first.

- [ ] Extend the existing adapter protocol/disabled implementation with mock responses and failure tests.
- [ ] Define the exact evidence payload, data minimization, secret redaction, approval, timeout, and
      cancellation behavior before connecting any provider.
- [ ] Add one explicit opt-in adapter behind the interface; evaluate CLI versus App Server separately.
- [ ] Keep AI suggestions separate from deterministic results, attach evidence references, and preserve
      the local report when AI is unavailable or wrong.
- [ ] Evaluate the explanation demo on the maintained fixtures and document its limitations.

Completion: the same scan remains useful with no credentials, network, or AI. No source content is sent
externally without explicit approval, and AI-generated assumptions are never promoted to confirmed findings.

## Milestone 5 — CLI release and OSS evaluation

Release preparation can proceed alongside the milestones above; packaging is already present and does not
need to be rebuilt as a new product.

- [ ] Run the installed CLI/binary against the maintained policy fixture corpus in CI, beyond the
      existing in-process CLI/API regression tests.
- [ ] Verify clean installation, execution, and upgrade for each advertised OS/architecture.
- [ ] Define a tested support matrix rather than assuming every allowed dependency version is equivalent.
- [ ] Verify release notes, both changelogs, tag/package version, and actual binary contents together.
      The current release script checks tag/version spelling, not changelog completeness.
- [ ] Publish a new preview from a verified `main` commit when a coherent milestone is ready.
- [ ] Preserve issue decisions, meaningful commits, PR discussion, CI evidence, and a short reproducible demo.
- [ ] Consider signing/notarization separately before broader binary distribution.

Completion: the documented CLI demo works from a clean installation, release claims match the downloaded
binary, and changes can be traced from issue to test to PR. Do not inflate commit counts or publish a new
release for every documentation edit. See the [release guide](RELEASING.md).

## Later, optional — Local regression execution

This is not a prerequisite for source discovery, AI-assisted explanation, or the initial CLI deliverable.

- [ ] Generate reviewable regression-test plans for maintained, owned local fixtures without sending requests.
- [ ] Consider an explicitly approved local test harness with isolation, fixture-only scope, timeouts,
      request limits, and protection against unintended data changes.
- [ ] Keep execution opt-in and separate from `scan`; record reproducible results and unresolved outcomes.

Internet-target scanning, autonomous exploitation, and arbitrary repository execution are not part of this
development milestone. Revisit any execution scope in its own design issue before implementation.

## Working checklist

Before implementation, record the issue, supported subset, completion criteria, and a branch from current
`main`. During implementation, add tests alongside each behavior and avoid unrelated refactoring.
Before merge, update the English source and required translations together, verify links and commands,
and pass Python, frontend, and CodeQL checks. Use meaningful commits and a merge commit, then synchronize
the roadmap and remove the working branch. See [contributing](../CONTRIBUTING.md) and
[branch rules](BRANCH_RULES.md).
