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

- Resolved repository-local absolute and relative router imports, aliases, and module references without
  executing target source, preserving cross-file registration paths and original source locations.
- Composed literal same-file router and registration prefixes, preserving repeated registrations and
  route source locations while omitting unresolved paths. See the [parser scope](docs/PARSER_SCOPE.md).

### Changed

- Aligned the roadmap with a CLI-first evidence/report milestone, separate authentication and authorization
  interpretation, and optional AI explanation before optional local regression execution.
- Refreshed all four project README languages, added Korean counterparts for the remaining project guides
  and PR template, and introduced a bilingual documentation index and translation maintenance policy.
- Distinguished source-checkout features from published preview binaries and clarified optional dashboard
  installation and safe release-tag procedures.

### Fixed

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
