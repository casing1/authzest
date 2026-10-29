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

## Editors and unreviewed pull requests

Prettier is a development formatter, not AuthZest's authorization analyzer. Editor formatting does not
automatically call the repository guard. For unfamiliar PRs, first review the diff in GitHub or a
restricted editor: inspect workspace/configuration, formatter scripts, dependencies and workflow changes
before trusting the checkout, installing dependencies or running commands. The guard itself is trusted
code, not isolation from an attacker who changes that code.

For VS Code, the optional [authzest-review.code-workspace](../../authzest-review.code-workspace) opens
only this checkout and supplies these defaults:

- `prettier.enable` is `false` to disable Prettier formatting after restarting VS Code.
- `editor.formatOnSave`, `editor.formatOnPaste`, and `editor.formatOnType` are `false`.
- `editor.codeActionsOnSave` sets `source.fixAll.prettier` to `never` so the separate Prettier save action
  is not requested by this preset.

Use **File → Open Workspace from File** to open the reviewed file, then restart VS Code. Opening just the
repository folder does **not** load this preset. It does not install extensions, add executable tasks,
modify user-wide settings, or overwrite ignored `.vscode/` files. Existing folder settings and
language-specific settings can override these defaults: inspect the effective values in Settings for the
file's language. If uncertain, find **Prettier - Code formatter** in Extensions, choose **Disable
(Workspace)** and complete the restart prompt. Do not enable workspace trust merely to make formatting work.

Keep unfamiliar checkouts in [Restricted Mode](https://code.visualstudio.com/docs/editing/workspaces/workspace-trust)
while reviewing them. This preset is an opt-in workflow aid, not a sandbox or an enforcement mechanism.
Other extensions, code actions, editors, manual commands and direct Prettier API calls remain outside it.
It neither prevents all extension code from loading nor proves the effective settings of a developer's
machine. See the official [setting precedence](https://code.visualstudio.com/docs/configure/settings#settings-precedence),
[Prettier enable/restart setting](https://github.com/prettier/prettier-vscode#prettierenable-default-true),
[save action](https://github.com/prettier/prettier-vscode#using-code-actions-on-save), and
[workspace extension disabling](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace#disable-an-extension).

Once the checkout and toolchain are reviewed, use the guarded commands in [Commands](#commands) from
the terminal. Do not replace them with direct Prettier invocation or **Format Document**. If the guard
refuses a configuration, review the configuration instead of bypassing the guard. Other editors should
disable automatic Prettier integration for this checkout and use the same commands; no cross-editor
settings compatibility is claimed. Tests validate the preset data and npm routing, not a running editor.
This workflow change does not replace Prettier's bundled parser, resolve #89, or accept release risk.

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
`4218b807ad892bb92e27a6bb23c4d64000e2a3bf`, found bundled `brace-expansion` 5.0.6 in the then-installed
Prettier 3.9.6 and the then-latest official npm release inspected on that date, Prettier 3.9.9. The downloaded 3.9.9 tarball matched
the registry's SHA-512 integrity and SHA-1 `09b826918c91cd4cbc80e0cbd1d2a922ff04f233`.
The separate `brace-expansion` 5.0.12 lock entry at that checkpoint
did not replace those embedded bytes. Inspection covered selected bundle, parser, and EditorConfig
routing sections, not all bundled code. The public advisories tracked by #89 are
[GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr),
[GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7), and
[GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p).
At that inspected checkpoint, the legacy CLI imported configuration resolution from `index.mjs`,
and the CJS API delegated to that ESM implementation. The selected EditorConfig-to-Minimatch and
recursive/rewrite parser sections were present. Neither a separate lock override nor an update to
the inspected Prettier 3.9.9 release supplied the fixed embedded implementation at that checkpoint.

The recorded 2026-10-08 overall #89 assessment was **`needs_review`**, with **medium confidence**:
the affected embedded implementation was verified, but an actual DoS through the guarded commands
or an AuthZest runtime vulnerability was not established. At that checkpoint, the arbitrary-section-pattern
input route was rejected before Prettier started. Actual direct editor/API settings, lower-trust
configuration exposure and availability consequences were unverified. This was not a finding that
every Prettier call was safe or exploitable.
No hostile/resource-exhaustion input or dynamic reproduction was run for that 2026-10-08 static assessment.
Bundled dependency follow-up remains under #89 and [#83](https://github.com/casing1/authzest/issues/83).
The 2026-10-16 documentation sync does not add an upstream release check, new security assessment
or risk-acceptance decision; the evidence above remains the dated 2026-10-08 record.

The guard covers these repository commands only. Direct Prettier calls, editor integrations, and
direct CJS/ESM module calls have no guarantee from it. The timeout is not an OS sandbox. The boundary
assumes a trusted installed toolchain and workflow scripts, files stable between preflight and
Prettier's re-read, and no concurrent hostile writers running as the same user.

The runtime source and packaging spec inspected on 2026-10-08 did not invoke Prettier or select its
Node toolchain; the optional dashboard used built frontend assets. That record separated the identified
developer-tooling route from runtime claims; it was not an audit of every dependency or a new
binary-content attestation.

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
