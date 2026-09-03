<p align="center">
  <img src="docs/assets/authzest-banner.png" alt="AuthZest — Source-aware authorization testing" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ru.md">Русский</a>
</p>

# AuthZest

AuthZest is an open-source, source-aware authorization security testing tool for FastAPI projects.
It analyzes repository structure and route declarations, then produces evidence that future deterministic
rules and optional AI analysis can use.

> [!IMPORTANT]
> AuthZest is in early development. Version `0.1.0` is an executable project scaffold, not a complete
> vulnerability scanner. Authorization classification, security findings, active testing, and Codex-backed
> analysis are planned work.

## What works today

- Python AST discovery for common FastAPI route decorators
- Typer CLI commands: `scan`, `doctor`, and `ui`
- JSON and human-readable scan summaries
- FastAPI health and repository scan endpoints
- Optional local React/Vite dashboard served from localhost
- Standalone binary packaging with PyInstaller
- Separate `analyzer`, `parser`, `runner`, and `codex` boundaries
- Python and frontend CI on GitHub Actions

The Codex adapter is currently disabled. Local analysis does not require an API key or ChatGPT login.

## Install with pipx

AuthZest requires Python 3.12 or newer.

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
pipx install .

authzest --version
authzest doctor
authzest scan /path/to/fastapi-project
```

To include the optional local dashboard, use `pipx install '.[ui]'`. During development, reinstall the
current checkout with `pipx install . --force`.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

cd frontend
npm ci
cd ..
```

## CLI

```bash
authzest --help
authzest --version
authzest doctor
authzest scan <path>
authzest scan <path> --json
authzest ui --host 127.0.0.1 --port 8000
```

`doctor` checks the runtime and the optional Codex CLI installation and login state. Static analysis still
works when Codex is unavailable.

`scan` currently counts Python files and discovers FastAPI-style route decorators: `get`, `post`, `put`,
`patch`, `delete`, `options`, and `head`. It does not yet decide whether an endpoint is securely authorized.

## Optional local dashboard

The dashboard is local software and does not require website deployment.

```bash
cd frontend
npm ci
npm run build
cd ..

authzest ui
```

Open `http://127.0.0.1:8000`. For frontend development, run `authzest ui --reload` and `npm run dev` in
separate terminals. Vite proxies `/api` and `/health` to the local FastAPI server.

## Local API

- `GET /health` — backend health
- `GET /api/health` — equivalent endpoint for the frontend
- `POST /api/scans` — scan a repository with `{ "path": "/absolute/or/relative/path" }`
- `GET /docs` — generated FastAPI API documentation

## Verification

```bash
pytest
ruff check .
ruff format --check .

cd frontend
npm run lint
npm run format:check
npm run build
```

## Standalone binary

```bash
source .venv/bin/activate
python -m pip install -e '.[build]'
cd frontend && npm ci && npm run build && cd ..
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest doctor
```

Pushing a `v*` tag starts the release workflow for macOS, Linux, and Windows binaries with SHA-256
checksums.

## Project structure

```text
.
├── src/authzest/
│   ├── analyzer/        # Repository-level analysis and aggregation
│   ├── parser/          # Language and framework source parsing
│   ├── codex/           # Optional AI adapter interface and implementations
│   ├── runner/          # Analysis orchestration
│   ├── api/             # FastAPI transport
│   ├── cli.py           # Typer CLI transport
│   └── models.py        # Core data models
├── tests/
├── frontend/            # Optional React/Vite/TypeScript UI
├── docs/                # Development plan and brand assets
├── scripts/             # Release packaging helpers
├── authzest.spec        # PyInstaller configuration
└── .github/workflows/   # CI and release workflows
```

Dependencies point inward from the CLI, API, and UI toward the core. The core must not depend on the web
server, React, or a specific AI provider.

## Roadmap and contributing

- [Development plan](docs/DEVELOPMENT_PLAN.md)
- [Public roadmap issue](https://github.com/casing1/authzest/issues/1)
- [Contribution and commit rules](CONTRIBUTING.md)

Please open an issue before implementation and use a short-lived branch linked to that issue. Pull requests
must pass the Python and frontend checks before merging.

## License and security

AuthZest is released under the [MIT License](LICENSE). Report vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not through a public issue.
