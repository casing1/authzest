<p align="center">
  <strong>English</strong> ·
  <a href="i18n/ko/INDEX.md">한국어</a>
</p>

# Documentation

AuthZest is an installable, CLI-first FastAPI source-analysis project. Start with the project README
for installation, then use the parser scope to understand what a scan does and does not establish.
The local dashboard is optional and does not require website deployment.

## Guides and languages

English is the canonical language. Every repository-owned Markdown document has Korean content;
the project README also has [Japanese](i18n/ja/README.md) and [Russian](i18n/ru/README.md) versions.
English detail pages are grouped by topic; translations mirror that structure under language folders.
The conventional English README, contributing, security, and changelog files remain at the repository root.

```text
docs/
├── README.md                 # English index
├── guides/                   # Usage and examples
├── reference/                # Parser scope and report contracts
├── development/              # Plan, model strategy, branch rules
├── releases/                 # Release procedure
├── assets/                   # Shared images
└── i18n/
    ├── ko/                   # Korean root docs, INDEX.md, mirrored topics
    ├── ja/README.md          # Japanese project overview
    └── ru/README.md          # Russian project overview
```

| Document                                        | English                                                | 한국어                                                |
| ----------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| Project overview and installation               | [README](../README.md)                                 | [프로젝트 소개](i18n/ko/README.md)                    |
| Documentation index                             | [Index](README.md)                                     | [문서 목차](i18n/ko/INDEX.md)                         |
| Development direction and TODO order            | [Development plan](development/DEVELOPMENT_PLAN.md)    | [개발 계획](i18n/ko/development/DEVELOPMENT_PLAN.md)  |
| Supported source syntax and limitations         | [Parser scope](reference/PARSER_SCOPE.md)              | [파서 범위](i18n/ko/reference/PARSER_SCOPE.md)        |
| Maintained source-only CLI demo                 | [Examples](guides/EXAMPLES.md)                         | [예제](i18n/ko/guides/EXAMPLES.md)                    |
| Opt-in owned-fixture Codex draft                | [Codex fixture](guides/CODEX_FIXTURE.md)               | [Codex fixture](i18n/ko/guides/CODEX_FIXTURE.md)      |
| Separately approved fixed-fixture runtime check | [Runtime verification](guides/RUNTIME_VERIFICATION.md) | [런타임 검증](i18n/ko/guides/RUNTIME_VERIFICATION.md) |
| Replaceable models and measurable value         | [Model strategy](development/MODEL_STRATEGY.md)        | [모델 전략](i18n/ko/development/MODEL_STRATEGY.md)    |
| Versioned diagnostics and registration evidence | [Report contract](reference/REPORT_CONTRACT.md)        | [리포트 계약](i18n/ko/reference/REPORT_CONTRACT.md)   |
| Contributions and commit conventions            | [Contributing](../CONTRIBUTING.md)                     | [기여 안내](i18n/ko/CONTRIBUTING.md)                  |
| Required checks and branch protection           | [Branch rules](development/BRANCH_RULES.md)            | [브랜치 규칙](i18n/ko/development/BRANCH_RULES.md)    |
| Versions, binaries, and release checks          | [Releasing](releases/RELEASING.md)                     | [릴리스 가이드](i18n/ko/releases/RELEASING.md)        |
| Released and unreleased changes                 | [Changelog](../CHANGELOG.md)                           | [변경 이력](i18n/ko/CHANGELOG.md)                     |
| Private reporting and safe-use policy           | [Security](../SECURITY.md)                             | [보안 정책](i18n/ko/SECURITY.md)                      |
| Pull request fields and checklist               | [PR template](../.github/pull_request_template.md)     | [PR 작성 안내](i18n/ko/PULL_REQUEST_TEMPLATE.md)      |

## Read the right version

The [offline proposal/decision contract](reference/PROPOSAL_CONTRACT.md), also available in
[Korean](i18n/ko/reference/PROPOSAL_CONTRACT.md), implements only #46's preview and simulated-decision
slice of #35. That pure contract does not apply files, call a provider or execute verification.

The subsequent [owned-fixture application demo](guides/FIXTURE_APPLICATION.md)
([한국어](i18n/ko/guides/FIXTURE_APPLICATION.md)) adds #48's explicit terminal approval and restoration
in a fresh POSIX copy only. It never edits an existing checkout and remains an offline scripted demo.

[#50's Codex fixture command](guides/CODEX_FIXTURE.md) ([한국어](i18n/ko/guides/CODEX_FIXTURE.md))
adds an opt-in, version-pinned App Server draft followed by separate copy-application decisions.
One owned-fixture live draft/apply/restore check passed, with assistant-entered approval phrases under
user authorization, not independent human review. #52 adds an optional, separately approved subprocess
AST configuration check of the applied fixture with pinned source hashes, not runtime behavior or a verified security fix.
#54 adds an opt-in [owned-fixture runtime plan](guides/RUNTIME_VERIFICATION.md)
([한국어](i18n/ko/guides/RUNTIME_VERIFICATION.md)) through `--runtime-check`; static checking remains the default.
The selector is not execution approval. Only the exact bundled fixture may execute, with a separate
decision and no automatic dependency installation. #54's bounded live source acceptance and the separate
alpha.3 publication checks passed. General repository AI and the complete #35 workflow remain open.

The [offline AI contract and evaluation](reference/AI_CONTRACT.md) is implemented in the source checkout
with a matching [Korean guide](i18n/ko/reference/AI_CONTRACT.md). Its pure contracts support alpha.3's fixture
command; the evaluation scripts/corpus and offline copy demos still require a development checkout.
The offline evaluation does not call a model.

[v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) was published on 2026-09-12
with package version `0.1.0a3` and unchanged report schema `1.2`, from
`99be6f5614d283befa2a421b64f84958b680f92f`. It includes the fixed fixture draft/copy/check workflow on
supported POSIX systems. Windows supports scanning, not fixture application/runtime verification.
All six public assets were downloaded and matched to the checked tag artifacts; public macOS scan/runtime
smokes also passed through standard-library controllers under Python `-I -S`, without importing project
dependencies. No model call was made by those package checks.

The earlier [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2) was published on 2026-09-10
with package version `0.1.0a2` and schema `1.2`. Its binaries include route-owner recognition, literal router
composition, repository-local imports, and local/inherited dependency evidence. The alpha.1 scaffold
does not contain these improvements. See the [release record](releases/RELEASING.md) for the exact commit,
three-platform artifacts, and validation limits. Compare the changelog and commit/tag as well as
`--version`; `main` can advance beyond the released source. The offline foundation in
[#33](https://github.com/casing1/authzest/issues/33) is implemented in source; next is [#35](https://github.com/casing1/authzest/issues/35).

Current scans provide schema 1.2, structured diagnostics, distinct source registration evidence, and
route-local plus inherited dependency declarations. They do not classify endpoints
as securely authorized, or run AI/active tests. Unresolved source patterns may be omitted, so an empty
report or successful exit is not a security guarantee. The [report contract](reference/REPORT_CONTRACT.md) defines
bounded/partial status and opt-in strict exits. The [development plan](development/DEVELOPMENT_PLAN.md) separates
those planned capabilities from the current implementation.

## Updating documentation

- Update the English original and its required translations in the same PR; retain identical commands,
  versions, completion status, and limitations across languages.
- Use relative repository links and check them from each translated file's actual directory. GitHub PR
  template links may use stable repository URLs because the template is copied into a PR body.
- Keep this index in sync when adding, moving, or renaming a guide. The Korean index is `i18n/ko/INDEX.md`
  to avoid colliding with the project README translation.
- Audit tracked project Markdown, including `.github/`; do not edit dependency/vendor documentation,
  generated build files, or synced external references as part of localization.
- Preserve the [MIT license](../LICENSE) text. `LICENSE` is not a Markdown guide and is not replaced by
  an unofficial translation.

Use [roadmap #1](https://github.com/casing1/authzest/issues/1) for live issue status and the development plan
for the rationale. Documentation changes do not by themselves modify branch settings, enable an adapter,
remediate a vulnerability, or publish a release.
