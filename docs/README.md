<p align="center">
  <strong>English</strong> ·
  <a href="i18n/INDEX.ko.md">한국어</a>
</p>

# Documentation

AuthZest is an installable, CLI-first FastAPI source-analysis project. Start with the project README
for installation, then use the parser scope to understand what a scan does and does not establish.
The local dashboard is optional and does not require website deployment.

## Guides and languages

English is the canonical language. Every repository-owned Markdown document has Korean content;
the project README also has [Japanese](i18n/README.ja.md) and [Russian](i18n/README.ru.md) versions.
Translations are grouped in `docs/i18n/`, leaving only the English project README at the repository root.

| Document                                        | English                                            | 한국어                                           |
| ----------------------------------------------- | -------------------------------------------------- | ------------------------------------------------ |
| Project overview and installation               | [README](../README.md)                             | [프로젝트 소개](i18n/README.ko.md)               |
| Documentation index                             | [Index](README.md)                                 | [문서 목차](i18n/INDEX.ko.md)                    |
| Development direction and TODO order            | [Development plan](DEVELOPMENT_PLAN.md)            | [개발 계획](i18n/DEVELOPMENT_PLAN.ko.md)         |
| Supported source syntax and limitations         | [Parser scope](PARSER_SCOPE.md)                    | [파서 범위](i18n/PARSER_SCOPE.ko.md)             |
| Maintained source-only CLI demo                 | [Examples](EXAMPLES.md)                            | [예제](i18n/EXAMPLES.ko.md)                      |
| Replaceable models and measurable value         | [Model strategy](MODEL_STRATEGY.md)                | [모델 전략](i18n/MODEL_STRATEGY.ko.md)           |
| Versioned diagnostics and registration evidence | [Report contract](REPORT_CONTRACT.md)              | [리포트 계약](i18n/REPORT_CONTRACT.ko.md)        |
| Contributions and commit conventions            | [Contributing](../CONTRIBUTING.md)                 | [기여 안내](i18n/CONTRIBUTING.ko.md)             |
| Required checks and branch protection           | [Branch rules](BRANCH_RULES.md)                    | [브랜치 규칙](i18n/BRANCH_RULES.ko.md)           |
| Versions, binaries, and release checks          | [Releasing](RELEASING.md)                          | [릴리스 가이드](i18n/RELEASING.ko.md)            |
| Released and unreleased changes                 | [Changelog](../CHANGELOG.md)                       | [변경 이력](i18n/CHANGELOG.ko.md)                |
| Private reporting and safe-use policy           | [Security](../SECURITY.md)                         | [보안 정책](i18n/SECURITY.ko.md)                 |
| Pull request fields and checklist               | [PR template](../.github/pull_request_template.md) | [PR 작성 안내](i18n/PULL_REQUEST_TEMPLATE.ko.md) |

## Read the right version

The latest `main` source includes route-owner recognition, literal router composition, and repository-local
router imports. Those improvements are listed under **Unreleased**; they are not in the published
`v0.1.0-alpha.1` preview binary. Package metadata remains `0.1.0a1` until a release-preparation change,
so compare the changelog and commit/tag as well as `--version`.

Current scans provide schema 1.0, structured diagnostics, and distinct source registration evidence;
they do not collect dependency evidence, classify endpoints
as securely authorized, or run AI/active tests. Unresolved source patterns may be omitted, so an empty
report or successful exit is not a security guarantee. The [report contract](REPORT_CONTRACT.md) defines
bounded/partial status and opt-in strict exits. The [development plan](DEVELOPMENT_PLAN.md) separates
those planned capabilities from the current implementation.

## Updating documentation

- Update the English original and its required translations in the same PR; retain identical commands,
  versions, completion status, and limitations across languages.
- Use relative repository links and check them from each translated file's actual directory. GitHub PR
  template links may use stable repository URLs because the template is copied into a PR body.
- Keep this index in sync when adding, moving, or renaming a guide. The Korean index is `INDEX.ko.md`
  to avoid colliding with the project README translation.
- Audit tracked project Markdown, including `.github/`; do not edit dependency/vendor documentation,
  generated build files, or synced external references as part of localization.
- Preserve the [MIT license](../LICENSE) text. `LICENSE` is not a Markdown guide and is not replaced by
  an unofficial translation.

Use [roadmap #1](https://github.com/casing1/authzest/issues/1) for live issue status and the development plan
for the rationale. Documentation changes do not by themselves modify branch settings, enable an adapter,
remediate a vulnerability, or publish a release.
