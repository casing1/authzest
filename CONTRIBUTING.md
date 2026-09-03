<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/CONTRIBUTING.ko.md">한국어</a>
</p>

# Contributing to AuthZest

AuthZest grows through small, verifiable changes. A clear record of why a change was made, how it was
verified, and which security decisions were considered matters more than the number of features.

## Workflow

1. Open a GitHub issue before implementation and describe the problem, scope, and acceptance criteria.
2. Create a short-lived branch from the latest `main` and include the issue number in its name.
3. Keep the implementation focused on one purpose and add tests in the same change.
4. Run the local checks and commit in meaningful units.
5. Open a pull request linked to the issue and wait for CI.
6. Resolve discussions, merge with a merge commit, and delete the working branch.

Do not push directly to `main`. It must remain runnable and pass all required checks.

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
example `v0.1.0`.

## Commit conventions

Use a lightweight form of [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <summary>
```

- Write the summary in imperative English, without a period, and keep it within 72 characters.
- Keep each commit to one logical change that can be reviewed or reverted independently.
- Include a feature and its tests in the same commit when practical.
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

1. Create a Python 3.12 virtual environment.
2. Install Python development dependencies with `python -m pip install -e '.[dev]'`.
3. Run `npm install` in `frontend/`.
4. Run the checks below before and after a change.

```bash
pytest
ruff check .
ruff format --check .
cd frontend && npm run lint && npm run format:check && npm run build
```

To verify the standalone executable, build the frontend first and run:

```bash
python -m pip install -e '.[build]'
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest doctor
```

## Change principles

- Preserve the boundaries between `analyzer`, `parser`, `codex`, and `runner`.
- Keep the core independent of the CLI, FastAPI transport, and React UI.
- Produce reproducible deterministic results before adding AI judgment.
- Security findings must include source location, evidence, confidence, and a minimal reproducible test.
- Add a real Codex integration as a `CodexAdapter` protocol implementation; do not expose SDK or process
  details to the core.
- Keep external process execution and network requests disabled by default. They require explicit user opt-in.

## Definition of done

A pull request is ready to merge when:

- It satisfies the linked issue's acceptance criteria.
- New or changed behavior is covered by tests.
- Relevant Python and frontend checks pass locally.
- User-facing behavior changes include appropriate documentation.
- Security and backward-compatibility impact is recorded in the pull request.
- No secrets, personal data, or generated files are committed.
- All required GitHub Actions checks pass.

Bug and feature issues should include reproduction steps, expected behavior, actual behavior, and environment
details. Report vulnerabilities privately by following [SECURITY.md](SECURITY.md), not through a public issue.
