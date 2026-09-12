# Releasing AuthZest

[Documentation](../README.md) · English · [한국어](../i18n/ko/releases/RELEASING.md)

AuthZest publishes standalone executables through GitHub Releases. PyPI and npm publishing are not part of
the current release process. The binaries are not signed or notarized.

## Published preview and current source

### Alpha.3 preparation (not yet published)

[#56](https://github.com/casing1/authzest/issues/56) prepares package `0.1.0a3` / tag
`v0.1.0-alpha.3` after [PR #55](https://github.com/casing1/authzest/pull/55). This checkpoint combines
the offline evidence/proposal contracts, opt-in pinned Codex fixture draft, approved copy changes,
source-configuration checks and separately approved fixed runtime verification. The scan report
schema stays `1.2`. [Bounded acceptance](../guides/RUNTIME_VERIFICATION.md) passed locally; exact-main
three-platform builds, fresh downloaded artifacts and public assets must still pass before publication.
Windows runtime is unsupported, existing Windows scan support is unchanged, and no new live Codex
request is authorized by release preparation. Keep the alpha.2 download record below until a separate
post-publication documentation PR confirms the new release; do not move or replace existing tags/assets.

### Published alpha.2

[v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2) was published on 2026-09-10,
with Python package `0.1.0a2` and report schema `1.2`, from commit
`7cc359acbb864ef6d31e3b536787857da4f7e09c` ([preparation PR #40](https://github.com/casing1/authzest/pull/40),
[completed release issue #39](https://github.com/casing1/authzest/issues/39)). This is an alpha prerelease,
not a stable security product. Subsequent source/documentation changes on `main` do not modify its tag or assets.
The original [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)
does not contain the parser/report/dependency improvements documented in the
[parser scope](../reference/PARSER_SCOPE.md) and [alpha.2 changelog](../../CHANGELOG.md#010-alpha2---2026-09-10).
Record the source commit with `git rev-parse HEAD` when reporting source-build behavior.

### Alpha.2 validation record

The [manual main run 34442310332](https://github.com/casing1/authzest/actions/runs/34442310332) and
[tag publishing run 34442837616](https://github.com/casing1/authzest/actions/runs/34442837616) passed on the
exact commit above. Checks included 451 Python tests, 14 documentation-checker tests, frontend lint/format
and builds, four source-only fixtures, report parity, strict/invalid-input exits, and relocated binaries.
Separate fresh jobs downloaded and checked each artifact without installing AuthZest's Python dependencies.

| Platform    | Published executable                     |
| ----------- | ---------------------------------------- |
| Linux x64   | `authzest-0.1.0-alpha.2-linux-x64`       |
| macOS arm64 | `authzest-0.1.0-alpha.2-macos-arm64`     |
| Windows x64 | `authzest-0.1.0-alpha.2-windows-x64.exe` |

Each executable has a matching `.sha256` manifest in the release: three binaries and three manifests.
All public assets were downloaded again and their checksums verified. The published macOS binary also
passed local isolated-copy fixture checks with a Python runtime containing no installed project dependencies.
These records do not establish clean installation or upgrades on consumer devices, compatibility with
every OS/Python/FastAPI version, signing/notarization, or authorization correctness. No Codex call, scanned
application execution, or user-source modification was part of the smoke checks.

## Version policy

Release timing is milestone-based at the maintainer's discretion, not one tag per issue or a fixed
calendar cadence. The maintainer delegated timing decisions on 2026-09-11; this does not waive any
release checks below. Keep internal-only contract slices such as #33/#46 in `Unreleased` until a
coherent user-facing checkpoint is ready and artifact/compatibility checks pass. A bounded demonstrable
#35 workflow is the next candidate checkpoint, not a promised date or reserved version. Preserve the
seven development weeks and separate exam/submission buffer; do not publish to inflate activity.

Use Semantic Versioning. Versions below `1.0.0` may introduce breaking changes while AuthZest is in initial
development.

Python package metadata uses PEP 440 spelling, while Git tags use SemVer spelling. These examples explain
the mapping; they do not reserve the next release version:

| Release stage | `pyproject.toml` | Git tag          |
| ------------- | ---------------- | ---------------- |
| Alpha         | `0.1.0a2`        | `v0.1.0-alpha.2` |
| Beta          | `0.1.0b1`        | `v0.1.0-beta.1`  |
| Candidate     | `0.1.0rc1`       | `v0.1.0-rc.1`    |
| Final         | `0.1.0`          | `v0.1.0`         |

[`pyproject.toml`](../../pyproject.toml) is the source of truth for the Python runtime and API version. The
frontend package marked `private: true` is not versioned independently. Choose a new, unused version for
each new release; neither the published `v0.1.0-alpha.1` nor `v0.1.0-alpha.2` may be issued again.

## Prepare a release

Run the following commands from the repository root, with the project's development environment active.
The command examples use Bash. On Windows, use Git Bash for these commands and the `.exe` binary when
checking a local build.

1. Create a release issue with the intended version, scope, and acceptance criteria. Check existing
   [releases](https://github.com/casing1/authzest/releases) and tags before choosing the version.
2. Create a short-lived branch from the latest `main`.
3. Update `project.version` in `pyproject.toml`.
4. Move the completed changes from `Unreleased` into a dated heading such as
   `## [X.Y.Z-alpha.N] - YYYY-MM-DD` in [`CHANGELOG.md`](../../CHANGELOG.md). Keep its
   [Korean counterpart](../i18n/ko/CHANGELOG.md) aligned, including the version, date, and links.
5. Replace the placeholder below with the unused tag chosen in the issue, matching the new package
   version. The placeholder intentionally fails validation until replaced.

   ```bash
   AUTHZEST_NEXT_TAG='vX.Y.Z-alpha.N'
   ```

6. Run the release checks:

   The scan smoke checks do not invoke `doctor`, Codex, or target application code. Dependency installation
   and artifact downloads can access the network.

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
   python scripts/smoke_release.py --binary dist/authzest
   python scripts/smoke_fixture_runtime.py --binary dist/authzest
   ```

   [`verify_release.py`](../../scripts/verify_release.py) validates the exact tag/package-version match,
   one matching dated heading per English/Korean changelog, valid equal dates, and nonempty content.
   It does not prove publication or semantic translation/feature accuracy; review the entries as well.
   The default Korean path is `docs/i18n/ko/CHANGELOG.md`.

   [`smoke_release.py`](../../scripts/smoke_release.py) checks version/help/text output, schema `1.2` JSON
   against the checkout core, all four maintained source-only fixtures, bounded strict exit 0, partial
   default/strict exits 0/1, and invalid-root exit 2. Binary mode tests the selected executable and a
   relocated temporary copy with an isolated working directory and sanitized Python environment.
   On Windows use `--binary dist/authzest.exe`. The per-command timeout defaults to 45 seconds;
   `--expected-version` can explicitly select the expected PEP 440 version instead of `pyproject.toml`.

   The separate [runtime smoke](../guides/RUNTIME_VERIFICATION.md) checks the actual native parent
   and its worker on the fixed bundled AFTER fixture, plus a relocated copy. POSIX must pass exact
   debug/ASGI health observations; Windows must return unsupported without a worker. It makes no
   Codex call and accepts no user source. The outer deadline is 45 seconds; worker startup/I/O
   remains five seconds with a separate one-second cleanup allowance. This is not an OS sandbox.

7. Open a pull request and merge it only after the required CI and CodeQL checks pass.
8. Run the release workflow on `main` to verify all three platform builds before publishing:

   ```bash
   gh workflow run release.yml --ref main
   ```

   Inspect that run in [GitHub Actions](https://github.com/casing1/authzest/actions/workflows/release.yml)
   and download its artifacts for smoke checks. A manual run on `main` builds artifacts without creating
   a release. A manual run against a tag is not a dry run: the publishing conditions depend on the ref
   being a tag.

   In this checkout, validate each downloaded platform artifact directory separately on its matching OS:

   ```bash
   python scripts/smoke_release.py --artifact-dir /path/to/ONE_PLATFORM_ARTIFACT_DIRECTORY
   python scripts/smoke_fixture_runtime.py --artifact-dir /path/to/ONE_PLATFORM_ARTIFACT_DIRECTORY
   ```

   Artifact mode requires exactly one executable and its matching `.sha256` manifest, validates the
   checksum, then executes only a relocated temporary copy. It does not modify or execute the original
   downloaded file. Match the checkout to that build's commit; report comparison uses its core and fixtures.

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

The [release workflow](../../.github/workflows/release.yml) checks that the tag targets the current remote
`main` commit **when validation runs**. `main` can advance after the local check, so coordinate other merges
until validation has completed. If it advances before validation and the run fails, do not move or
overwrite the tag; record the failed attempt and prepare a new version from the verified current `main`.

During validation, the workflow repeats the Python and frontend quality checks. It then builds Linux,
macOS, and Windows executables with the dashboard assets, runs binary/relocated-copy fixture smoke checks,
and writes a `.sha256` file for each binary. The versioned artifact also receives checksum-aware smoke checks.
Separate fresh jobs download each platform's artifact, confirm AuthZest is not installed in the Python
environment, and run artifact smoke with Python isolated mode (`-I`) without installing project packages.
Publishing requires validation, builds, and all fresh artifact-verification jobs to pass. These fresh-job
checks still do not establish clean installation or upgrades on consumer devices.
Asset names include the release version, operating system, and detected build architecture. Tags with a prerelease
suffix create a GitHub prerelease; final-version tags create a regular release. This workflow does not
publish Python or npm packages or perform binary signing.

## Verify and recover

- Download every release asset and its matching `.sha256` file.
- On macOS or Linux, run `shasum -a 256 -c <asset>.sha256` from the directory containing both downloaded
  files, replacing `<asset>` with the actual filename. On Windows, compare `Get-FileHash -Algorithm SHA256`
  output with the corresponding manifest. A checksum verifies file integrity, not publisher identity.
- Run the downloaded executable's `--version`, `--help`, and maintained fixture scans in a clean environment.
  After verifying its checksum, enable execution on the exact downloaded macOS/Linux file. From its
  download directory, replace the filename placeholder and run:

  ```bash
  AUTHZEST_DOWNLOADED_BINARY='REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME'
  chmod u+x "./$AUTHZEST_DOWNLOADED_BINARY"
  "./$AUTHZEST_DOWNLOADED_BINARY" --version
  "./$AUTHZEST_DOWNLOADED_BINARY" --help
  ```

  Windows `.exe` files do not need `chmod`. From the download directory in PowerShell, select the exact
  downloaded file instead:

  ```powershell
  $AuthZestDownloadedBinary = '.\REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME.exe'
  & $AuthZestDownloadedBinary --version
  & $AuthZestDownloadedBinary --help
  ```

  Verify each supported platform before describing its clean installation or upgrade as tested. Use the
  [source-only examples](../guides/EXAMPLES.md) for fixture commands, with the reviewed fixtures copied into
  that environment. `doctor` is optional and can invoke installed Codex diagnostic commands; it is not a
  release smoke prerequisite.

- Confirm the generated GitHub release notes and both changelogs refer to the correct version and
  features. Build artifacts from `main` are not automatically a published release.
- After publication and public-asset verification, open a documentation follow-up issue/PR from current
  `main`. Replace preparation-only wording and old download links in all four README languages and
  English/Korean guides. Record the release URL, date, exact commit, actual checks, and remaining limits;
  update development/roadmap completion only for satisfied criteria. Keep later documentation changes in
  `Unreleased`, run the documentation checks, and merge through required CI. Do not move the tag, replace
  assets, or publish another version merely for this follow-up. Before publication, keep release claims
  conditional; a planned version or successful dry run alone is not a public release.
- If building or publishing fails, inspect the failed job before retrying. A transient failure can be
  retried for the same unchanged tag if its commit still satisfies validation. Do not use asset overwrite
  options to silently replace a release that users may already have downloaded.
- Never move or overwrite an existing release tag. If a published release is faulty, document the
  problem in an issue and the changelogs, then publish a new patch or prerelease version.

The workflow's isolated relocated-copy checks are not clean-machine installation or upgrade tests.
Independently verify downloaded assets on each advertised platform and review release-note/content accuracy.
Signing/notarization, general FastAPI compatibility, and access-control correctness are not established by
these smoke checks. Publish only after the required run and artifact checks pass for the exact selected SHA.
