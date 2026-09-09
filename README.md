<p align="center">
  <img src="docs/assets/authzest-banner.png" alt="AuthZest — Source-aware authorization testing" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/README.ko.md">한국어</a> ·
  <a href="docs/i18n/README.ja.md">日本語</a> ·
  <a href="docs/i18n/README.ru.md">Русский</a>
</p>

# AuthZest

AuthZest is an installable, CLI-first open-source project for source-aware access-control analysis of
FastAPI applications. Its current Python core inventories routes without importing or executing the target
application. Authorization assessment and optional AI assistance are the next development stages.

The React dashboard is an optional local interface. Using AuthZest does not require deploying a website.

> [!IMPORTANT]
> The published [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)
> is the first executable scaffold. Route-owner recognition, prefix composition, and cross-file router
> resolution described below are implemented on `main` but **not yet released** in those binaries.
> The source package still reports `0.1.0a1`; use the checkout commit and [changelog](CHANGELOG.md) to
> distinguish it from the published preview. Neither version is a complete vulnerability scanner.

## What the current source supports

- Recognizes statically constructed `FastAPI` and `APIRouter` owners, including supported import aliases.
- Discovers literal HTTP route declarations and composes supported router and registration prefixes.
- Connects repository-local absolute/relative router imports, retaining original file and line evidence.
- Produces human-readable or JSON reports through the `scan` command.
- Provides optional local API/dashboard, diagnostics, and standalone binary packaging.

Supported decorators are `get`, `post`, `put`, `patch`, `delete`, `options`, and `head`.
This is a bounded static subset: dynamic or unresolved declarations are omitted, and an empty report does
not establish that no endpoints exist or that access control is safe. See the [parser scope](docs/PARSER_SCOPE.md).
Dependency collection, authentication/authorization classification, and security findings are not implemented.

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
```

Replace `/path/to/fastapi-project` with your project directory. If the command is not on your PATH, run
`pipx ensurepath` and open a new terminal. A pipx-installed CLI does not require activating a project venv.
The examples select Python 3.12; for another supported interpreter, replace `3.12` after `--python` with
its version or executable path.

To update this source installation, run the following from your clean `authzest` checkout on `main`:

```bash
git pull --ff-only
pipx install --force .
```

For a prebuilt executable, see [standalone binaries](#standalone-binaries). The `ui` extra installs Python
backend dependencies; it does not include built dashboard assets in a regular wheel/pipx installation.
Use the editable source setup below for the optional dashboard.

## CLI diagnostics

```bash
authzest --version
authzest doctor
authzest doctor --json
```

`doctor` checks the Python runtime. If it finds `codex` on PATH, it also runs `codex --version` and
`codex login status` as subprocesses. It does not start an AI scan or read credential files itself.
Missing Codex or login produces a warning and does not prevent static scans.

## Development setup

Run commands from the cloned repository root. The shell examples use macOS/Linux; on Windows PowerShell,
create the venv with `py -3.12 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The editable install uses this checkout, and the `dev` extra includes the optional backend dependencies.
Node.js/npm are needed only for frontend work or builds that bundle the dashboard; CI uses Node.js 22.

## Optional local dashboard

After the editable development setup, build and run the dashboard from the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
authzest ui --workspace /path/to/fastapi-project --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The editable backend finds `frontend/dist` in the checkout.
Without that build, `/` shows an API message rather than the dashboard.

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

## Standalone binaries

The [published preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1) provides Linux x64,
macOS arm64, and Windows x64 executables with SHA-256 manifests. They are CLI programs, not graphical
installers, and do not include the unreleased parser changes on `main`. The binaries are not yet signed or
notarized, so an operating system may warn about an unverified publisher.

To build the current source locally, activate the development venv and run from the repository root:

```bash
python -m pip install -e '.[build]'
npm --prefix frontend ci
npm --prefix frontend run build
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest --help
```

On Windows, the output is `dist\authzest.exe`. The PyInstaller build includes `frontend/dist` when it exists.
Tag validation, checksums, and publishing are described in the [release guide](docs/RELEASING.md).

## Project structure

```text
src/authzest/
├── analyzer/   # Repository analysis and aggregation
├── parser/     # AST route and import resolution
├── runner/     # Shared scan orchestration
├── codex/      # Optional provider interface; scan adapter disabled
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
- [Development checklist](docs/DEVELOPMENT_PLAN.md) and [roadmap issue #1](https://github.com/casing1/authzest/issues/1)
- [Contribution and commit rules](CONTRIBUTING.md)

Track a bounded task in an issue, develop it on a short-lived branch, and submit a pull request with
meaningful commits and validation. Protected `main` requires the Python, frontend, and CodeQL checks.
The next core milestone is collecting `Depends`/`Security` evidence before introducing access-control judgments.

## License and security

AuthZest uses the [MIT License](LICENSE). Report vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not through a public issue.
