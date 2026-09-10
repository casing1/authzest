<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/ko/CONTRIBUTING.md">한국어</a>
</p>

# Contributing to AuthZest

AuthZest grows through small, verifiable changes. A clear record of why a change was made, how it was
verified, and which security decisions were considered matters more than the number of features.
Find the project guides in the [documentation index](docs/README.md).

## Workflow

1. Check the [roadmap issue](https://github.com/casing1/authzest/issues/1), then open or select a focused
   GitHub issue with a problem statement, scope, and acceptance criteria before implementation.
2. Create a short-lived branch from the latest `main` and include the issue number in its name.
3. Keep the implementation focused on one purpose and add tests in the same change.
4. Run the local checks and commit in meaningful units.
5. Open a pull request linked to the issue and wait for the required Python, frontend, and CodeQL checks.
6. Resolve discussions, merge with a merge commit, and delete the working branch.

Do not push directly to `main`. It must remain runnable and pass all required checks.
The [branch protection policy](docs/development/BRANCH_RULES.md) requires Python, frontend, and CodeQL checks.

## Branch names

Use `<type>/<issue-number>-<short-description>`. Write the description in lowercase English with hyphens.

```text
feat/12-router-prefix-resolution
fix/23-invalid-python-path
test/31-nested-router-fixtures
docs/7-security-model
refactor/42-report-model
chore/55-update-actions
```

Recommended types are `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`, and `build`. AuthZest does
not maintain a long-lived `develop` branch. Releases are created by tagging a verified commit on `main`, for
example `v0.1.0-alpha.2`. Follow the [release guide](docs/releases/RELEASING.md); published tags are immutable.

## Commit conventions

Use a lightweight form of [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <summary>
```

- Write the summary in imperative English, without a period, and keep it within 72 characters.
- Keep each commit to one logical change that can be reviewed or reverted independently.
- Include a feature and its tests in the same commit when practical.
- Do not split a coherent change merely to increase the commit count.
- Avoid unclear messages such as `update`, `fix stuff`, or `WIP`.
- When a body is needed, explain why the change is necessary and record important tradeoffs.
- Reference related issues with `Refs #12`. Use `Closes #12` in the pull request that completes the issue.
- Never rebase or force-push the published history of `main`.

Recommended scopes are `parser`, `analyzer`, `runner`, `cli`, `api`, `web`, `codex`, `release`, and `docs`.

```text
feat(parser): resolve nested router prefixes
fix(cli): reject nonexistent repository paths
test(analyzer): cover inherited security dependencies
docs(contributing): define development workflow
ci(actions): update Python test matrix
```

Commit types have the following meanings:

- `feat`: functionality available to users or callers
- `fix`: correction of incorrect behavior or a regression
- `test`: tests only, without a product behavior change
- `refactor`: structural improvement that preserves external behavior
- `docs`: documentation-only changes
- `chore`: general maintenance
- `ci`: automation workflow changes
- `build`: packaging or build-system changes

## Development setup

Run the commands below from the cloned repository root with the development virtual environment active.

1. Create and activate a Python 3.12 virtual environment using the
   [README setup instructions](README.md#development-setup).
2. Install Python development dependencies with `python -m pip install -e '.[dev]'`.
3. Run `npm --prefix frontend ci` to install the committed frontend dependency versions.
4. Run the checks below before and after a change.

```bash
python -m pytest
ruff check .
ruff format --check .
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

For documentation changes, run these checks from the repository root after installing frontend dependencies:

```bash
node --test scripts/check_docs.test.mjs
node scripts/check_docs.mjs
git ls-files -z '*.md' | xargs -0 frontend/node_modules/.bin/prettier --check
```

The checker validates translation pairs, local links, and command parity without executing documentation
examples. The formatting command covers tracked Markdown; stage new guides before the final check.
The [included example](docs/guides/EXAMPLES.md) provides a deterministic local CLI demonstration.

After building the frontend above, verify the standalone executable from the repository root with the
same virtual environment active:

```bash
python -m pip install -e '.[build]'
python -m PyInstaller --clean --noconfirm authzest.spec
python scripts/smoke_release.py --binary dist/authzest
```

On Windows, use `--binary dist/authzest.exe`. This bounded smoke checks source-only fixtures, report parity,
CLI exits, and a relocated copy without invoking Codex or scanned application code. It does not establish
consumer-device installation or upgrade support. Explicitly running the optional `doctor` can invoke an installed Codex CLI through
`codex --version` and `codex login status`; it does not start an AI scan. A successful login does not
enable AI analysis, because that integration is not implemented. See
[CLI diagnostics](README.md#cli-diagnostics).

## Change principles

- Preserve the boundaries between `analyzer`, `parser`, `codex`, and `runner`.
- Keep the core independent of the CLI, FastAPI transport, and React UI.
- Prioritize the CLI MVP; maintain the local UI without expanding its scope ahead of the core.
- Produce reproducible deterministic results before adding AI judgment.
- Collect source facts and define report, authentication, and authorization semantics before adding
  optional AI explanations or an active test runner. A `Depends` or `Security` declaration alone does not
  prove that access is protected; preserve `unknown` when evidence is insufficient.
- Security findings must include source location, evidence, confidence, and a minimal reproducible test.
- Add a real Codex integration as a `CodexAdapter` protocol implementation; do not expose SDK or process
  details to the core.
- Treat improved results from AI as a hypothesis to evaluate, not an established advantage. Follow the
  [model and evaluation strategy](docs/development/MODEL_STRATEGY.md), keeping provider and model choices outside the core.
- Keep external process execution and network requests disabled by default. They require explicit user opt-in.

## Documentation and translations

Every first-party Markdown document has an English source and a Korean counterpart. The root project
`README.md` also has Japanese and Russian translations; other documents, including the documentation
index, require English and Korean only.

- Keep conventional English root documents; group detailed guides in `docs/guides/`, `docs/reference/`,
  `docs/development/`, and `docs/releases/`.
- Put translations in `docs/i18n/<language>/`, mirroring topic directories without filename language suffixes.
  For example, `docs/development/BRANCH_RULES.md` pairs with `docs/i18n/ko/development/BRANCH_RULES.md`.
- Use `docs/i18n/ko/INDEX.md` for `docs/README.md` so it does not conflict with the project README
  translation. The authored `.github/pull_request_template.md` pairs with
  `docs/i18n/ko/PULL_REQUEST_TEMPLATE.md`; GitHub continues to load the English template by default.
- Add reciprocal language links and register new guides in the English and Korean documentation indexes.
- Update the source and all its translations in the same pull request. Keep supported behavior, limitations,
  commands, links, and checklist state aligned. Leave code identifiers and command syntax unchanged.
- Keep the project README focused on an overview and getting started; put detailed guidance under `docs/`
  and link it from the [documentation index](docs/README.md).
- After a release is actually published and its public assets are verified, synchronize release status,
  download links, completed checklist items, and validation limits across the READMEs and English/Korean
  guides in a follow-up docs PR. Keep this change in `Unreleased`; do not rewrite the released tag/assets.

This policy covers Markdown authored for the repository, including contribution templates. Generated
output and third-party dependency documentation are not translated or committed as project guidance.

## Definition of done

A pull request is ready to merge when:

- It satisfies the linked issue's acceptance criteria.
- New or changed behavior is covered by tests.
- Relevant Python and frontend checks pass locally.
- Documentation checker tests, translation/link checks, and Markdown formatting pass for documentation changes.
- User-facing behavior changes include appropriate documentation.
- Documentation changes include the corresponding translations and working language links.
- Security and backward-compatibility impact is recorded in the pull request.
- No secrets, personal data, or generated files are committed.
- All required GitHub Actions checks pass.

Bug and feature issues should include reproduction steps, expected behavior, actual behavior, and environment
details. Report vulnerabilities privately by following [SECURITY.md](SECURITY.md), not through a public issue.
