<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/CHANGELOG.ko.md">한국어</a>
</p>

# Changelog

[Documentation index](docs/README.md) · [Release guide](docs/RELEASING.md)

All notable changes to AuthZest are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) while the project remains in initial development.

## [Unreleased]

These entries describe changes on `main` after the published `v0.1.0-alpha.1` tag. They are not included
in that preview binary, even though current Python package metadata still uses `0.1.0a1`.

### Added

- Extended the report to schema `1.1` with route-local `Depends`/`Security` evidence from supported
  parameter defaults, inline `Annotated`, and decorator `dependencies`. Records original source locations,
  syntactic targets, known scopes, and unresolved reasons without classifying authentication/authorization.
  Existing registration IDs and fields are preserved; inherited and nested dependency analysis remain deferred.
- Added a source-only dependency example and CLI/API regressions for ordinary DI, scope limits, and
  strict partial-report behavior. No model calls, target execution, or release publication were added.
- Added report schema `1.0` with structured source diagnostics and explicit `bounded`/`partial`
  analysis status, while retaining existing route fields and legacy parse errors. This schema version
  is separate from the unchanged Python package version. See the [report contract](docs/REPORT_CONTRACT.md).
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
  route source locations while omitting unresolved paths. See the [parser scope](docs/PARSER_SCOPE.md).

### Changed

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
  excluding unrelated objects and shadowed or reassigned names. See the [parser scope](docs/PARSER_SCOPE.md).
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

[Unreleased]: https://github.com/casing1/authzest/compare/v0.1.0-alpha.1...HEAD
[0.1.0-alpha.1]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1
