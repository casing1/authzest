<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/ko/CHANGELOG.md">한국어</a>
</p>

# Changelog

[Documentation index](docs/README.md) · [Release guide](docs/releases/RELEASING.md)

All notable changes to AuthZest are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) while the project remains in initial development.

## [Unreleased]

### Added

- Add #54's separately approved [owned-fixture runtime check](docs/guides/RUNTIME_VERIFICATION.md).
  `--runtime-check` selects the exact-plan gate; the default remains source-only configuration.
  Only byte-identical bundled constants execute, checking `app.debug` and one in-process ASGI health
  response. Retain five-second execution and separate one-second cleanup limits, scoped runtime
  evidence, conflict-aware restoration and journal schema `1.2` for runtime sessions.
  Add explicit optional `fixture` dependencies and native/downloaded-artifact runtime smoke gates.
  No arbitrary source/commands, exploit reproduction, automatic installs or security-fix claim.
  One newly approved source-CLI live draft/apply/runtime/restore check passed on `ce2834c` on
  2026-09-12, with the assistant entering exact phrases under bounded user authorization.
- Add #52's optional, separately approved source-configuration check between fixture-copy application
  and restoration: exact-plan approval, a fixed AST configuration worker with pinned source hashes, a 5-second timeout and 4 KiB
  output limit. Report `passed`/`failed`/`not-run` separately from restoration, while runtime verification
  stays `not-run`. No target source, model-generated command, or provider is executed by this check;
  this offline addition is not runtime/security-fix verification or new live-model evidence.
- Add #50's source-only [Codex fixture command](docs/guides/CODEX_FIXTURE.md): pinned App Server 0.153.0,
  exact-request sharing approval before process launch, at most one application-issued turn, and a narrowly
  validated debug-setting draft with separate apply/restore decisions for a fresh POSIX copy.
  One owned-fixture live draft/apply/restore check passed on `42ff108` on 2026-09-12, preserving the original.
  The assistant entered approval phrases under user authorization, not independent human review.
  General repository AI remains unimplemented; that historical check did not run verification.
  The default scan stays offline and parent #35 remains open. No new release is included.
- Handle narrowly validated same-turn Codex stream-recovery notifications without issuing another turn.
  Accept at most three observed notices within the existing time/byte/event limits; discard pre-recovery
  output and usage, require a fresh validated final response, and keep fatal errors fail-closed.
  The notice count is not a provider-attempt or billing cap. The live check observed zero retry notices;
  stream recovery remains offline-tested only.
- Add AI schema `1.1` for provider-managed nullable temperature while preserving numeric-temperature
  schema `1.0`, existing request identities and the numeric default. No token or monetary cap is implied.
- Add #48's [owned-fixture copy application](docs/guides/FIXTURE_APPLICATION.md): explicit terminal
  approval, consumed live-session decisions, current-file checks, atomic single-file replacement,
  retained snapshots/journal and separately confirmed conflict-aware restoration on supported POSIX.
  Original checkouts, live providers and verification execution remain untouched; #35 is incomplete.
- Add #46's offline proposal/decision schema `1.0`, binding exact replacements, original hashes,
  evidence, review identity, rationale and verification intent. Derive diffs from bound text and check
  explicit decisions, expiry and supplied current source without writing or executing anything.
  Include a caller-authored debug-configuration demo, not AI generation or a verified fix.
  See the [proposal contract](docs/reference/PROPOSAL_CONTRACT.md). #35 remains incomplete.
- Implement #33's offline AI schema `1.0`: selected, immutable source/registration evidence, exact-input
  approval checks, strict response/reference validation, configurable identity/provenance, and isolated
  mock review results. Disabled, invalid, failure, timeout, and cancellation paths preserve static scans.
- Add a frozen six-case, three-mode evaluation harness with evaluator-only labels, repeated trials,
  explicit metric denominators, and nullable unmeasured usage/human review data. Policy criteria were
  maintainer-approved; reference labels remain assistant-authored and code-checked. Mock scores do not
  demonstrate model performance. See the [offline contract](docs/reference/AI_CONTRACT.md).

### Changed

- Replace the unused `CodexFinding` adapter placeholder with untrusted JSON responses in #33. That step
  did not add a live adapter or change CLI/API behavior. The separate #50 command above does not change
  scan report schema, target execution, existing-checkout patching, or published alpha.2 artifacts.

### Documentation

- Require appropriate issue/PR labels, maintainer assignment, milestone matching or a documented
  cross-milestone exception, and metadata readback in contribution guidance and PR checklists.
- Synchronize the four README languages and English/Korean guides with the published alpha.2 artifacts,
  release evidence, and next #33/#35 work. Record the post-publication documentation follow-up in the
  release procedure. This documentation-only change does not alter the alpha.2 tag or binaries.

## [0.1.0-alpha.2] - 2026-09-10

Published as [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2), with Python
package `0.1.0a2` and report schema `1.2`, from commit `7cc359acbb864ef6d31e3b536787857da4f7e09c`.
The [release record](docs/releases/RELEASING.md) links artifact checks and their limitations.
These improvements are included in alpha.2, not the alpha.1 binaries.

### Added

- Added binary release smoke checks for source-only examples, JSON/report parity, strict/invalid-input
  exits, and an isolated relocated executable copy. These do not replace clean-machine or upgrade checks.
- Added bilingual dated changelog validation alongside the tag/package-version check.
- Extended the report to schema `1.2` with `effective_dependencies`: supported FastAPI/APIRouter
  constructor and `include_router` declarations plus route-local evidence, preserving original positions
  and declaration levels across repeated/multi-app mounts. `dependencies` remains route-local and both
  lists remain excluded from registration IDs. Context order is not a runtime execution guarantee.
- Added a source-only inheritance example and regression coverage for composition, unresolved collections,
  local-field compatibility, and shared CLI/API output. No AI integration was added.
- Extended the report to schema `1.1` with route-local `Depends`/`Security` evidence from supported
  parameter defaults, inline `Annotated`, and decorator `dependencies`. Records original source locations,
  syntactic targets, known scopes, and unresolved reasons without classifying authentication/authorization.
  Existing registration IDs and fields were preserved; inherited analysis was deferred at that step and
  is now added above. Nested dependency graphs remain deferred.
- Added a source-only dependency example and CLI/API regressions for ordinary DI, scope limits, and
  strict partial-report behavior. No model calls or target execution were added.
- Added report schema `1.0` with structured source diagnostics and explicit `bounded`/`partial`
  analysis status, while retaining existing route fields and legacy parse errors. This schema version
  is independent of the Python package version. See the [report contract](docs/reference/REPORT_CONTRACT.md).
- Added deterministic source-registration IDs, original decorator and owner positions, application
  identity, outer-to-inner include chains, and explicit deferred function-body inventory. Same-path
  registrations remain distinct, including repeated calls on the same line.
- Added opt-in `scan --strict`: a partial report remains available but returns exit code 1. Default
  scan exits and local API HTTP 200 responses for produced reports remain compatible.
- Added a project-owned, four-file FastAPI inventory example with three expected routes and a checked-in
  report fixture; its regression test verifies source analysis without importing the example.
- Added a tested documentation checker and CI checks for local links, language counterparts, matching
  examples/checklists, and Markdown formatting.
- Resolved repository-local absolute and relative router imports, aliases, and module references without
  executing target source, preserving cross-file registration paths and original source locations.
- Composed literal same-file router and registration prefixes, preserving repeated registrations and
  route source locations while omitting unresolved paths. See the [parser scope](docs/reference/PARSER_SCOPE.md).

### Changed

- Grouped English guides by topic and translations by language with mirrored topic directories, updating
  the documentation index, contribution instructions, and repository links together.
- Clarified the final product goal as a Codex-assisted, user-approved defensive repair loop: review
  source evidence, propose regression-test drafts and a patch, obtain approval for the exact diff,
  apply approved changes, and report verification results. This loop is planned in
  [#35](https://github.com/casing1/authzest/issues/35), not implemented by the source-report changes.
  No live model calls, target-code execution, or patch application were added.
- Organized a seven-week development plan around stable source-evidence contracts and evaluations that
  can be repeated when AI models change, reserving the remaining four to five weeks for exams, delays,
  and submission preparation.
- Initially staged the roadmap around a CLI-first evidence/report milestone, separate authentication
  and authorization interpretation, and optional AI explanation before optional local regression
  execution; the final Codex repair-loop goal above now extends that earlier plan.
- Refreshed all four project README languages, added Korean counterparts for the remaining project guides
  and PR template, and introduced a bilingual documentation index and translation maintenance policy.
- Distinguished source-checkout features from published preview binaries and clarified optional dashboard
  installation and safe release-tag procedures.

### Fixed

- Applied ignored-directory names only below the explicitly selected scan root, so an eligible project
  is not skipped because its root or an ancestor is named `dist`, `node_modules`, or `.venv`.
- Parsed UTF-8 BOM and Python source-encoding declarations consistently in single-file and repository
  scans, while retaining diagnostics for invalid bytes and unsupported encodings.
- Printed repository-relative route locations and individual parse errors in the text CLI, preserving
  existing JSON fields and default exit codes. Clarified that Codex installation/login diagnostics do not
  enable AI analysis or become prerequisites for local scans.
- Distinguished unscanned, running, failed, empty, and partial dashboard results, displayed parse-error
  details, cleared stale results before a new attempt, and kept repeated route registrations distinct
  through unique row keys.
- Required statically recognized FastAPI or APIRouter owners before collecting route decorators,
  excluding unrelated objects and shadowed or reassigned names. See the [parser scope](docs/reference/PARSER_SCOPE.md).
- Provided explicit repository context to the GitHub Release publishing job.
- Wrote checksum manifests with portable LF line endings on every build platform.

## [0.1.0-alpha.1] - 2026-09-04

### Added

- Python core boundaries for analyzer, parser, runner, and optional Codex adapters.
- Typer commands for help, version, diagnostics, repository scanning, JSON output, and the local dashboard.
- FastAPI health and scan endpoints with a React, Vite, and TypeScript dashboard.
- Cross-platform PyInstaller builds with SHA-256 checksums.
- CI, CodeQL, contribution guidance, a security policy, and localized project guides.

### Security

- Restricted the HTTP scan endpoint to the workspace selected by the local process owner.
- Removed caller-controlled filesystem paths from the HTTP API contract.

[Unreleased]: https://github.com/casing1/authzest/compare/v0.1.0-alpha.2...main
[0.1.0-alpha.2]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2
[0.1.0-alpha.1]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1
