<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/THIRD_PARTY.md">한국어</a>
</p>

# References and third-party software

[Documentation index](../README.md) · [MIT license](../../LICENSE)

AuthZest is released under the MIT license. Reviewed on 2026-11-26: the repository contains no code
copied or adapted from other projects. It builds on the open-source packages and external tools below.
Each keeps its own license; the MIT label of AuthZest does not replace those terms.

## What each distribution contains

| Distribution                       | Third-party content                                                                                                                                                                                                                                              |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source repository and source ZIP   | No third-party code. Dependencies are declared in `pyproject.toml` and `frontend/package-lock.json` and installed separately.                                                                                                                                    |
| Python wheel                       | AuthZest code only; pip installs the dependencies listed below from their own sources.                                                                                                                                                                           |
| Standalone executables (GitHub)    | Bundle CPython (PSF-2.0), the PyInstaller bootloader (GPL-2.0 with the bootloader exception, which permits distributing the executable under any terms), the core Python dependencies and the built frontend assets that include React (MIT). They are unsigned. |
| A/B runtime images (built locally) | Built on the user's machine from the pinned `python` Docker base image and 14 checksum-verified wheels. They are not published.                                                                                                                                  |

## Python dependencies

| Package                                                                          | License            | Used by                      |
| -------------------------------------------------------------------------------- | ------------------ | ---------------------------- |
| Typer, Rich, markdown-it-py, mdurl, annotated-doc                                | MIT                | CLI                          |
| Click                                                                            | BSD-3-Clause       | CLI                          |
| Pygments                                                                         | BSD-2-Clause       | CLI                          |
| shellingham                                                                      | ISC                | CLI                          |
| typing_extensions                                                                | PSF-2.0            | CLI, UI and A image          |
| FastAPI, Pydantic, pydantic-core, AnyIO, h11, annotated-types, typing-inspection | MIT                | UI extra and A image         |
| Starlette, Uvicorn, idna                                                         | BSD-3-Clause       | UI extra and A image         |
| opentelemetry-api                                                                | Apache-2.0         | A image (FastAPI dependency) |
| httpx, pytest, pytest-cov, jsonschema, Ruff                                      | BSD-3-Clause / MIT | Development and tests only   |

The A image wheels are pinned in `runtime/generated_repair/images/locks/linux-arm64-A.txt`. The
[runtime setup](../guides/REPOSITORY_HTTP_FIX.md) checks each one by byte and hash; see the
[HTTP image reference](REPOSITORY_HTTP_IMAGES.md).

## Frontend dependencies

React and React DOM (MIT) are compiled into the dashboard assets. Build and quality tools are not
shipped: Vite (MIT), TypeScript (Apache-2.0), ESLint and its plugins (MIT), Prettier (MIT). The
developer-tool advisories for Prettier's bundled matchers are tracked in
[#89](https://github.com/casing1/authzest/issues/89) and
[#171](https://github.com/casing1/authzest/issues/171).

## External tools and services

- **Docker Desktop** runs the isolated A/B checks. AuthZest does not redistribute it; its own
  license terms apply.
- **OpenAI Codex CLI** (Apache-2.0) is called through its local App Server with the user's own
  ChatGPT login. AuthZest does not bundle it. Model use follows the user's account terms.
- The `python` base image comes from Docker Hub and contains CPython (PSF-2.0) and Debian packages
  under their respective licenses.

## References

- OWASP API Security Top 10 2023,
  [API1: Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/):
  the class of defect that `repo-fix` targets.
- MITRE [CWE-639: Authorization Bypass Through User-Controlled Key](https://cwe.mitre.org/data/definitions/639.html).
- [FastAPI documentation](https://fastapi.tiangolo.com/) for route, dependency and header handling.
- [Docker documentation](https://docs.docker.com/) for container isolation, networking and image building.
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
  [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for release records.
