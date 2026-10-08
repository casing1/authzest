# Repository formatting

[Documentation](../README.md) · English · [한국어](../i18n/ko/development/FORMATTING.md)

The repository formatting commands validate EditorConfig and file discovery before starting Prettier.
This is a scoped developer/CI mitigation for [#89](https://github.com/casing1/authzest/issues/89), not
a replacement of Prettier's bundled dependency or a demonstrated AuthZest runtime security fix.

## Commands

Install the committed frontend dependencies, then run from the repository root:

```bash
npm --prefix frontend ci
node --test scripts/format.test.mjs
node scripts/format.mjs markdown --check
node scripts/format.mjs markdown --write
npm --prefix frontend run format:check
npm --prefix frontend run format
```

Choose `--check` to report formatting differences or `--write` to apply formatting. Markdown discovery
uses Git-tracked files only; stage new guides before the final check. The frontend npm commands retain
their names and route through `scripts/format.mjs frontend --check` and
`scripts/format.mjs frontend --write`. Frontend exclusions for `dist`, `node_modules`, and
`package-lock.json` remain in effect. The formatter child has a 120-second timeout.

## Reviewed configuration

The root [`.editorconfig`](../../.editorconfig) stays active. It must be a regular file of at most
4 KiB, with `root = true`, no duplicate entries or malformed lines, and only the reviewed sections
`[*]`, `[*.py]`, and `[Makefile]`. Supported properties are `charset`, `end_of_line`,
`insert_final_newline`, `indent_style`, `indent_size`, and `trim_trailing_whitespace`, using the guard's
reviewed simple values. Ordinary EditorConfig formatting is retained; arbitrary patterns and options
are not supported.

The guard rejects nested, case-aliased, and symlink EditorConfig files in its checked scope. Target
discovery is bounded and checks selected files before launching Prettier. The explicit
[`scripts/prettier-options.json`](../../scripts/prettier-options.json), an empty object, bypasses
ambient and executable Prettier configuration discovery while keeping the reviewed EditorConfig active.
The wrapper explicitly sets `--ignore-path`: frontend formatting uses the validated
[`frontend/.prettierignore`](../../frontend/.prettierignore), and Markdown formatting uses
[`scripts/prettier-markdown.ignore`](../../scripts/prettier-markdown.ignore), which must remain exactly
zero bytes. Ambient `.gitignore` and `.prettierignore` discovery therefore does not determine wrapper
coverage; Prettier's built-in vendor and version-control directory exclusions still apply.
The frontend ignore file must contain the exact reviewed entries, without leading or trailing
whitespace; LF and CRLF line endings, empty lines, and comments starting with `#` are supported.
Changes to configuration patterns, options, exclusions, or ignore discovery require review of the
guard and its regression tests together.

## Dependency evidence and limits

Static reinspection on 2026-10-08, against source commit
`4218b807ad892bb92e27a6bb23c4d64000e2a3bf`, found bundled `brace-expansion` 5.0.6 in the installed
Prettier 3.9.6 and the current official npm latest, Prettier 3.9.9. The downloaded 3.9.9 tarball matched
the registry's SHA-512 integrity and SHA-1 `09b826918c91cd4cbc80e0cbd1d2a922ff04f233`.
The separate `brace-expansion` 5.0.12 lock entry
does not replace those embedded bytes. Inspection covered selected bundle, parser, and EditorConfig
routing sections, not all bundled code. The public advisories tracked by #89 are
[GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr),
[GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7), and
[GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p).
The legacy CLI imports configuration resolution from `index.mjs`, and the CJS API delegates to that
ESM implementation. Selected EditorConfig-to-Minimatch and recursive/rewrite parser sections remain
present. Neither a lock override nor upgrading to this inspected latest release replaces the embedded
implementation with the advisory fixes.

The overall #89 assessment is **`needs_review`**, with **medium confidence**: the affected embedded
implementation is verified, but an actual DoS through the guarded commands or an AuthZest runtime
vulnerability is not established. The arbitrary-section-pattern input route is rejected before
Prettier starts. Actual direct editor/API settings, lower-trust configuration exposure and availability
consequences remain unverified. This is not a finding that every Prettier call is safe or exploitable.
No hostile/resource-exhaustion input or dynamic reproduction was run for this static assessment.
Bundled dependency follow-up remains under #89 and [#83](https://github.com/casing1/authzest/issues/83).

The guard covers these repository commands only. Direct Prettier calls, editor integrations, and
direct CJS/ESM module calls have no guarantee from it. The timeout is not an OS sandbox. The boundary
assumes a trusted installed toolchain and workflow scripts, files stable between preflight and
Prettier's re-read, and no concurrent hostile writers running as the same user.

The inspected runtime source and packaging spec do not invoke Prettier or select its Node toolchain;
the optional dashboard uses built frontend assets. This separates the identified developer-tooling
route from runtime claims; it is not an audit of every dependency or a new binary-content attestation.

## Prerelease disposition

Keep #89 and #83 open. Normal development and separately scoped candidate compatibility/artifact
checks can continue, but green CI or an empty npm audit does not settle the residual embedded risk.
Before tagging or publishing, record either a reviewed compatible upstream replacement with shipped-byte
and ordinary compatibility evidence, or an explicit maintainer decision for the exact candidate's residual
developer-tooling risk. Such a decision must name the wrapper-only scope, unguarded integrations,
assumptions, remaining gaps and follow-up; this assessment does not grant risk acceptance.
The other release gates, including case-label acceptance and advertised-platform/installation checks,
remain independent. See the [release guide](../releases/RELEASING.md).

This unreleased tooling change does not create a release or change the package version, existing tags,
or alpha.3 assets. See the [release guide](../releases/RELEASING.md) for the separate release gates.
