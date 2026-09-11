<p align="center">
  <img src="docs/assets/authzest-banner.png" alt="AuthZest — Source-aware authorization testing" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/ko/README.md">한국어</a> ·
  <a href="docs/i18n/ja/README.md">日本語</a> ·
  <a href="docs/i18n/ru/README.md">Русский</a>
</p>

# AuthZest

AuthZest is an installable, CLI-first open-source project for source-aware access-control analysis of
FastAPI applications. Its current Python core inventories routes without importing or executing the target
application. The core product goal is Codex-assisted review and defensive test/patch proposals, user
approval or refusal, approved-only changes, and separately approved isolated verification with a change
record. That workflow is planned, not implemented; static scans remain offline and Codex use will be opt-in.

The React dashboard is an optional local interface. Using AuthZest does not require deploying a website.

> [!IMPORTANT]
> [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2) was published on
> 2026-09-10 with Python package version `0.1.0a2` and report schema `1.2`. Its binaries include the
> source-inventory, report, and local/inherited dependency features described below.
> See the [changelog](CHANGELOG.md) and [release record](docs/releases/RELEASING.md) for the exact
> commit and validation evidence. A checkout of `main` can advance beyond that tag.
> This is still an alpha source-analysis tool, not a complete vulnerability scanner or a working Codex repair loop.

## What the current source supports

- Recognizes statically constructed `FastAPI` and `APIRouter` owners, including supported import aliases.
- Discovers literal HTTP route declarations and composes supported router and registration prefixes.
- Connects repository-local absolute/relative router imports, retaining original file and line evidence.
- Produces human-readable or JSON reports through the `scan` command.
- Adds schema `1.2`, structured diagnostics, bounded/partial status, and distinct registration IDs with
  original declaration, application, and `include_router` evidence while retaining existing JSON fields.
- Collects route-local `Depends`/`Security` declarations, source locations, and known scopes without
  treating ordinary dependency injection as authentication or authorization.
- Carries supported application, router, and `include_router` dependency declarations into each
  registration's effective evidence, preserving the separate route-local list and original source positions.
- Provides optional local API/dashboard, diagnostics, and standalone binary packaging.

Supported decorators are `get`, `post`, `put`, `patch`, `delete`, `options`, and `head`.
This is a bounded static subset: unresolved route declarations may be omitted. A supported route with
unresolved dependency evidence remains in the report with diagnostics. Structured diagnostics
cover selected unresolved cases and source/read errors, not every unsupported pattern. An empty report or
`bounded` status does not establish that no endpoints exist or that access control is safe.
See the [parser scope](docs/reference/PARSER_SCOPE.md) and [report contract](docs/reference/REPORT_CONTRACT.md).
Nested dependency graphs, authentication/authorization classification, and security findings are not
implemented. Effective evidence describes source context, not runtime dependency order or protection.

`scan` uses local static analysis with the Codex adapter disabled. It does not invoke Codex or require an
API key or ChatGPT login. The separate `doctor` command can invoke the installed Codex CLI, as explained below.

## Install the CLI from source

Install Python 3.12 or newer and [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html) first;
Python 3.12 is the development baseline. These commands install
the current repository source into an isolated pipx environment, not a package from PyPI:

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
pipx install --python 3.12 .

authzest --help
authzest scan /path/to/fastapi-project
authzest scan /path/to/fastapi-project --json
authzest scan /path/to/fastapi-project --json --strict
```

Replace `/path/to/fastapi-project` with your project directory. If the command is not on your PATH, run
`pipx ensurepath` and open a new terminal. A pipx-installed CLI does not require activating a project venv.
The examples select Python 3.12; for another supported interpreter, replace `3.12` after `--python` with
its version or executable path.

By default, a returned report exits with code 0 even if analysis is partial. Add `--strict` to return 1
for known partial analysis while still printing the report. Invalid repository input returns 2.
These codes describe analysis execution, not a security verdict.

To update this source installation, run the following from your clean `authzest` checkout on `main`:

```bash
git pull --ff-only
pipx install --force .
```

For a prebuilt executable, see [standalone binaries](#standalone-binaries). The `ui` extra installs Python
backend dependencies; it does not include built dashboard assets in a regular wheel/pipx installation.
Use the editable source setup below for the optional dashboard.

## Try the included example

From the repository root, use the current source installation to scan the bundled local fixture:

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
```

Expect 4 Python files and 3 `GET` routes: `/health`, `/v1/catalog/items`, and `/v2/catalog/items`.
This demonstrates static discovery and repeated router registration, not vulnerability detection.
See the [example guide](docs/guides/EXAMPLES.md) for the fixture and expected evidence.

## CLI diagnostics

```bash
authzest --version
authzest doctor
authzest doctor --json
```

`doctor` checks the Python runtime. If it finds `codex` on PATH, it also runs `codex --version` and
`codex login status` as subprocesses. It does not start an AI scan or read credential files itself.
Missing Codex or login produces a warning and does not prevent static scans.
A successful login does not enable AI analysis; that integration is not implemented.

## Development setup

Run commands from the cloned repository root. The shell examples use macOS/Linux; on Windows PowerShell,
create the venv with `py -3.12 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The editable install uses this checkout, and the `dev` extra includes the optional backend dependencies.
Node.js/npm are needed for frontend work, documentation checks, or builds that bundle the dashboard;
CI uses Node.js 22.

## Optional local dashboard

After the editable development setup, build and run the dashboard from the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
authzest ui --workspace /path/to/fastapi-project --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The editable backend finds `frontend/dist` in the checkout.
Without that build, `/` shows an API message rather than the dashboard.
The dashboard distinguishes unstarted, empty, and partial scans and displays structured diagnostics and parse-error details.
A failed rescan clears the previous result. These are inventory states, not access-control verdicts.

For frontend development, run `authzest ui --workspace /path/to/fastapi-project --reload` in one activated
terminal and `npm --prefix frontend run dev` in another terminal at the repository root. Open
[http://localhost:5173](http://localhost:5173); Vite proxies `/api` and `/health` to port 8000.

The local server exposes `GET /health`, `GET /api/health`, `POST /api/scans`, and API documentation at `/docs`.
The scan endpoint always uses the workspace chosen at server startup; a request body cannot select another
path. Direct CLI scans use the path supplied by the local user. Keep the optional server on loopback.

## Verification

With the development venv active, run:

```bash
python -m pytest
ruff check .
ruff format --check .
```

For frontend changes, also run:

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

For documentation changes, install frontend dependencies as above, then run from the repository root:

```bash
node --test scripts/check_docs.test.mjs
node scripts/check_docs.mjs
git ls-files -z '*.md' | xargs -0 frontend/node_modules/.bin/prettier --check
```

The checker compares language pairs, local links, and commands without executing documentation examples.
The formatting command covers tracked Markdown; include new guides in staging before the final check.

## Standalone binaries

The [alpha.2 release](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2) provides Linux x64,
macOS arm64, and Windows x64 executables with matching SHA-256 manifests. They include the source-analysis
features above and report schema `1.2`. They are standalone CLI programs, not graphical installers;
running a prebuilt binary does not require installing Python or Node.js.

Download the file for your OS/architecture and its `.sha256` manifest. Follow the
[checksum and execution instructions](docs/releases/RELEASING.md#verify-and-recover) before running it.
Three-platform CI builds and downloaded-artifact smoke checks passed; consumer-device clean installation,
upgrades, and compatibility with every OS version have not been established. The binaries are unsigned
and unnotarized, so an operating system may warn about an unverified publisher.

To build the current source locally, activate the development venv and run from the repository root:

```bash
python -m pip install -e '.[build]'
npm --prefix frontend ci
npm --prefix frontend run build
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest --help
```

On Windows, the output is `dist\authzest.exe`. The PyInstaller build includes `frontend/dist` when it exists.
Tag validation, checksums, and publishing are described in the [release guide](docs/releases/RELEASING.md).

## Project structure

```text
src/authzest/
├── analyzer/   # Repository analysis and aggregation
├── parser/     # AST route and import resolution
├── runner/     # Shared scan orchestration
├── codex/      # Codex interface; live integration planned, scan adapter disabled
├── cli.py      # Typer command-line interface
├── api/        # Optional FastAPI transport
└── models.py   # Core report data
tests/          # Regression tests
frontend/       # Optional React/Vite/TypeScript dashboard
docs/           # Guides, translations, and assets
scripts/        # Release helpers
.github/        # CI/release workflows and contribution templates
```

The CLI and optional API/UI use the same core. Core analysis must not depend on the web server, React,
or a specific AI provider.

## Roadmap and contributing

- [Documentation index](docs/README.md) — English guides and Korean translations
- [Development checklist](docs/development/DEVELOPMENT_PLAN.md) and [roadmap issue #1](https://github.com/casing1/authzest/issues/1)
- [Model and evaluation strategy](docs/development/MODEL_STRATEGY.md)
- [Contribution and commit rules](CONTRIBUTING.md)

Track a bounded task in an issue, develop it on a short-lived branch, and submit a pull request with
meaningful commits and validation. Protected `main` requires the Python, frontend, and CodeQL checks.
The open-topic course plan uses 7 development weeks, with a separate 4–5 weeks reserved for exams, delays,
and final preparation. The report/evidence foundation in [#32](https://github.com/casing1/authzest/issues/32)
and route-local/inherited evidence in [#28](https://github.com/casing1/authzest/issues/28) and
[#29](https://github.com/casing1/authzest/issues/29) are included in alpha.2.
Release preparation and publication [#39](https://github.com/casing1/authzest/issues/39) are complete.
Current source and next step:

1. Implemented in source: [#33: evidence-linked offline AI contract, mocks, and evaluation](https://github.com/casing1/authzest/issues/33).
2. [#35: Codex proposals, exact-diff approval, approved patching, and isolated verification](https://github.com/casing1/authzest/issues/35)

The [offline foundation](docs/reference/AI_CONTRACT.md) is not included in alpha.2 binaries; #35's live workflow is not implemented yet.
The first #35 slice, [#46's offline proposal/decision contract](docs/reference/PROPOSAL_CONTRACT.md),
is implemented in source with diff previews and simulated approval checks; it never applies files or runs verification.
The six-case, three-mode mock evaluation tests contracts, not model performance. Whether AI assistance improves results is a hypothesis to
evaluate, not an established advantage; the core remains useful without a provider or a fixed GPT model.
The final demo targets a maintained owned fixture, with separate data-sharing, patch, and execution
permissions. Exploit-PoC generation, autonomous offensive workflows, and arbitrary repository execution
are out of scope.

## License and security

AuthZest uses the [MIT License](LICENSE). Report vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not through a public issue.
