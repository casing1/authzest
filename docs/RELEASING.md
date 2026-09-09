# Releasing AuthZest

[Documentation](README.md) · English · [한국어](i18n/RELEASING.ko.md)

AuthZest publishes standalone executables through GitHub Releases. PyPI and npm publishing are not part of
the current release process. The binaries are not signed or notarized.

## Published preview and current source

The published preview is [v0.1.0-alpha.1](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1).
The owner recognition, router prefix composition, and cross-file import resolution documented in the
[parser scope](PARSER_SCOPE.md) were added afterward and are still listed under
[`Unreleased`](../CHANGELOG.md#unreleased). They are available from current source, not from that preview
binary.

Current source still declares `0.1.0a1` in `pyproject.toml`. Until the next release preparation bumps that
version, `authzest --version` alone cannot distinguish the preview from a source installation. Record the
source commit with `git rev-parse HEAD` when reporting source-build behavior.

## Version policy

Use Semantic Versioning. Versions below `1.0.0` may introduce breaking changes while AuthZest is in initial
development.

Python package metadata uses PEP 440 spelling, while Git tags use SemVer spelling. These examples explain
the mapping; they do not reserve the next release version:

| Release stage | `pyproject.toml` | Git tag          |
| ------------- | ---------------- | ---------------- |
| Alpha         | `0.1.0a1`        | `v0.1.0-alpha.1` |
| Beta          | `0.1.0b1`        | `v0.1.0-beta.1`  |
| Candidate     | `0.1.0rc1`       | `v0.1.0-rc.1`    |
| Final         | `0.1.0`          | `v0.1.0`         |

[`pyproject.toml`](../pyproject.toml) is the source of truth for the Python runtime and API version. The
frontend package marked `private: true` is not versioned independently. Choose a new, unused version for
each new release; the already-published `v0.1.0-alpha.1` must not be issued again.

## Prepare a release

Run the following commands from the repository root, with the project's development environment active.
The command examples use Bash. On Windows, use Git Bash for these commands and the `.exe` binary when
checking a local build.

1. Create a release issue with the intended version, scope, and acceptance criteria. Check existing
   [releases](https://github.com/casing1/authzest/releases) and tags before choosing the version.
2. Create a short-lived branch from the latest `main`.
3. Update `project.version` in `pyproject.toml`.
4. Move the completed changes from `Unreleased` into a dated heading such as
   `## [X.Y.Z-alpha.N] - YYYY-MM-DD` in [`CHANGELOG.md`](../CHANGELOG.md). Keep its
   [Korean counterpart](i18n/CHANGELOG.ko.md) aligned, including the version, date, and links.
5. Replace the placeholder below with the unused tag chosen in the issue, matching the new package
   version. The placeholder intentionally fails validation until replaced.

   ```bash
   AUTHZEST_NEXT_TAG='vX.Y.Z-alpha.N'
   ```

6. Run the release checks:

   `doctor` can invoke an installed Codex CLI through the diagnostic commands `codex --version` and
   `codex login status`. It does not start AI analysis; missing Codex or authentication produces a warning.

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

   python scripts/verify_release.py "${AUTHZEST_NEXT_TAG:?Set the unused release tag first}"
   git grep -F "## [${AUTHZEST_NEXT_TAG#v}] - " -- CHANGELOG.md
   python -m PyInstaller --clean --noconfirm authzest.spec
   ./dist/authzest --version
   ./dist/authzest doctor
   ```

   [`verify_release.py`](../scripts/verify_release.py) validates only the exact tag/package-version
   match. It does **not** validate the changelog. The separate heading check and a review of both
   changelogs are maintainer steps; verify that the date and released entries are correct.

7. Open a pull request and merge it only after the required CI and CodeQL checks pass.
8. Run the release workflow on `main` to verify all three platform builds before publishing:

   ```bash
   gh workflow run release.yml --ref main
   ```

   Inspect that run in [GitHub Actions](https://github.com/casing1/authzest/actions/workflows/release.yml)
   and download its artifacts for smoke checks. A manual run on `main` builds artifacts without creating
   a release. A manual run against a tag is not a dry run: the publishing conditions depend on the ref
   being a tag.

9. After the manual `main` run succeeds and its artifacts pass smoke checks, inspect its full `headSha`.
   Replace `RUN_ID` below with that run's ID, confirm `status` is `completed` and `conclusion` is `success`,
   and copy the full returned SHA into `AUTHZEST_VERIFIED_COMMIT`:

   ```bash
   gh run view RUN_ID --json headSha,status,conclusion
   AUTHZEST_VERIFIED_COMMIT='COPY_THE_SUCCESSFUL_MAIN_RUN_HEAD_SHA_HERE'
   ```

   Use the commit from the successful run, not the latest local SHA as a substitute. If `main` advances
   afterward, rerun the workflow and artifact checks for that new commit before updating this value.

## Publish

Tag the exact, verified `main` commit. Keep both `AUTHZEST_NEXT_TAG` and `AUTHZEST_VERIFIED_COMMIT` from
preparation. This guarded example stops on a dirty worktree, a commit not built by the verified run,
a version/changelog mismatch, or an existing tag:

```bash
(
  set -e
  : "${AUTHZEST_NEXT_TAG:?Set the unused release tag first}"
  : "${AUTHZEST_VERIFIED_COMMIT:?Copy the successful main workflow headSha first}"
  test -z "$(git status --porcelain)"
  git switch main
  git pull --ff-only origin main
  git fetch --tags origin
  test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
  test "$(git rev-parse HEAD)" = "$AUTHZEST_VERIFIED_COMMIT"
  python scripts/verify_release.py "$AUTHZEST_NEXT_TAG"
  git grep -F "## [${AUTHZEST_NEXT_TAG#v}] - " -- CHANGELOG.md
  if git show-ref --verify --quiet "refs/tags/$AUTHZEST_NEXT_TAG"; then
    printf 'Refusing to reuse existing tag: %s\n' "$AUTHZEST_NEXT_TAG"
    exit 1
  fi
  git tag -a "$AUTHZEST_NEXT_TAG" "$AUTHZEST_VERIFIED_COMMIT" -m "AuthZest $AUTHZEST_NEXT_TAG"
  git push origin "refs/tags/$AUTHZEST_NEXT_TAG"
)
```

The [release workflow](../.github/workflows/release.yml) checks that the tag targets the current remote
`main` commit **when validation runs**. `main` can advance after the local check, so coordinate other merges
until validation has completed. If it advances before validation and the run fails, do not move or
overwrite the tag; record the failed attempt and prepare a new version from the verified current `main`.

During validation, the workflow repeats the Python and frontend quality checks. It then builds Linux,
macOS, and Windows executables with the dashboard assets and writes a `.sha256` file for each binary.
Asset names include the release version, operating system, and detected build architecture. Tags with a prerelease
suffix create a GitHub prerelease; final-version tags create a regular release. This workflow does not
publish Python or npm packages or perform binary signing.

## Verify and recover

- Download every release asset and its matching `.sha256` file.
- On macOS or Linux, run `shasum -a 256 -c <asset>.sha256` from the directory containing both downloaded
  files, replacing `<asset>` with the actual filename. On Windows, compare `Get-FileHash -Algorithm SHA256`
  output with the corresponding manifest. A checksum verifies file integrity, not publisher identity.
- Run the downloaded executable's `--version` and `doctor` commands on at least one clean environment.
  After verifying its checksum, enable execution on the exact downloaded macOS/Linux file. From its
  download directory, replace the filename placeholder and run:

  ```bash
  AUTHZEST_DOWNLOADED_BINARY='REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME'
  chmod u+x "./$AUTHZEST_DOWNLOADED_BINARY"
  "./$AUTHZEST_DOWNLOADED_BINARY" --version
  "./$AUTHZEST_DOWNLOADED_BINARY" doctor
  ```

  Windows `.exe` files do not need `chmod`. From the download directory in PowerShell, select the exact
  downloaded file instead:

  ```powershell
  $AuthZestDownloadedBinary = '.\REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME.exe'
  & $AuthZestDownloadedBinary --version
  & $AuthZestDownloadedBinary doctor
  ```

  Verify each supported platform before describing its installation as tested. As with the local checks,
  `doctor` can invoke installed Codex diagnostic commands; missing Codex or authentication may warn.

- Confirm the generated GitHub release notes and both changelogs refer to the correct version and
  features. Build artifacts from `main` are not automatically a published release.
- If building or publishing fails, inspect the failed job before retrying. A transient failure can be
  retried for the same unchanged tag if its commit still satisfies validation. Do not use asset overwrite
  options to silently replace a release that users may already have downloaded.
- Never move or overwrite an existing release tag. If a published release is faulty, document the
  problem in an issue and the changelogs, then publish a new patch or prerelease version.

The workflow runs the version command on every built executable. Clean-environment installation,
checksum verification after download, changelog review, and release-note accuracy remain maintainer
checks rather than fully automated guarantees.
