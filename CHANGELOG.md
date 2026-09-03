# Changelog

All notable changes to AuthZest are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) while the project remains in initial development.

## [Unreleased]

### Fixed

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
