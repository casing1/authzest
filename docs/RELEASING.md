# Releasing AuthZest

AuthZest publishes standalone executables through GitHub Releases. PyPI and npm publishing are not part of
the current release process.

## Version policy

Use Semantic Versioning. Versions below `1.0.0` may introduce breaking changes while AuthZest is in initial
development.

Python package metadata uses PEP 440 spelling, while Git tags use SemVer spelling:

| Release stage | `pyproject.toml` | Git tag          |
| ------------- | ---------------- | ---------------- |
| Alpha         | `0.1.0a1`        | `v0.1.0-alpha.1` |
| Beta          | `0.1.0b1`        | `v0.1.0-beta.1`  |
| Candidate     | `0.1.0rc1`       | `v0.1.0-rc.1`    |
| Final         | `0.1.0`          | `v0.1.0`         |

`pyproject.toml` is the source of truth for the Python runtime and API version. The private frontend is not
versioned independently.

## Prepare a release

1. Create a release issue with the intended version and acceptance criteria.
2. Create a short-lived branch from the latest `main`.
3. Update `project.version` in `pyproject.toml`.
4. Move completed entries from `Unreleased` into a dated section in `CHANGELOG.md`.
5. Run the release checks:

   ```bash
   python -m pip install -e '.[dev,build]'
   ruff check .
   ruff format --check .
   pytest

   cd frontend
   npm ci
   npm run lint
   npm run format:check
   npm run build
   cd ..

   python scripts/verify_release.py v0.1.0-alpha.1
   python -m PyInstaller --clean --noconfirm authzest.spec
   ./dist/authzest --version
   ```

6. Open a pull request and merge it only after CI and CodeQL pass.

## Publish

Tag the exact, verified `main` commit. Do not create the tag from a feature branch.

```bash
git switch main
git pull --ff-only
git tag -a v0.1.0-alpha.1 -m "AuthZest v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

The release workflow verifies the version and commit, repeats the project checks, builds Linux, macOS, and
Windows executables, creates SHA-256 files, and publishes a GitHub prerelease when the tag contains a
prerelease suffix. A manual workflow run builds artifacts without publishing a release.

## Verify and recover

- Download every release asset and its matching `.sha256` file.
- Run `shasum -a 256 -c <asset>.sha256` from the directory containing both downloaded files.
- Run the executable's `--version` and `doctor` commands on at least one clean environment.
- Confirm the GitHub release notes and changelog link to the correct version.
- Never move or overwrite a published tag. If a release is faulty, document the problem and publish a new
  patch or prerelease version.
