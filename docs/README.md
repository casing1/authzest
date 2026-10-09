<p align="center">
  <strong>English</strong> ·
  <a href="i18n/ko/INDEX.md">한국어</a>
</p>

# Documentation

AuthZest is an installable, CLI-first FastAPI source-analysis project. Start with the project README
for installation, then use the parser scope to understand what a scan does and does not establish.
The local dashboard is optional and does not require website deployment.

## Current work — 2026-10-09 KST

PR #90 merged #79's readable CLI output and explicit JSON streams. Read-only owner-policy Codex review
and the new [offline case-review / fixed-plan Python API](reference/OWNER_CASE_PLAN.md) are unreleased
source additions, not published alpha.3 features. The maintainer separately approved the exact ten
model-authored labels on 2026-10-09 KST; original authorship and the not-run draft/offline plans are preserved.
The offline contract has no executor or new CLI command. Current work is
[#80's fixed policy-check API](reference/OWNER_POLICY_CHECK.md), then bounded remediation/acceptance.
Label review is not actual execution consent or an authenticated receipt. The current dashboard
displays static inventory; it is not an AI review/approval viewer.
One later separately approved historical recipe `1.0` macOS arm64 source check matched all ten expected values;
see the [limited observation record](reference/OWNER_POLICY_CHECK.md#actual-source-acceptance--2026-10-09-kst).
It made no new AI call, leaves authorization unknown and consumes only that one approved run.
Current coordinator recipe `1.1` has not been rerun under fresh approval. Final-head #80 CI/reviews
remain pending; alpha.3 is unchanged.

Use the [current development plan](development/DEVELOPMENT_PLAN.md) for priorities, milestone state,
release/evaluation gates and the existing seven-development-week budget. Historical completion records
remain in issues/changelog/releases; issue-count percentages do not measure product completion.

## Guides and languages

English is the canonical language. Every repository-owned Markdown document has Korean content;
the project README also has [Japanese](i18n/ja/README.md) and [Russian](i18n/ru/README.md) versions.
English detail pages are grouped by topic; translations mirror that structure under language folders.
The conventional English README, contributing, security, and changelog files remain at the repository root.

```text
docs/
├── README.md                 # English index
├── guides/                   # Usage and examples
├── reference/                # Parser scope, contracts, threat model
├── development/              # Plan, model strategy, branch rules
├── releases/                 # Release procedure
├── assets/                   # Shared images
└── i18n/
    ├── ko/                   # Korean root docs, INDEX.md, mirrored topics
    ├── ja/README.md          # Japanese project overview
    └── ru/README.md          # Russian project overview
```

| Document                                        | English                                                   | 한국어                                                         |
| ----------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------- |
| Project overview and installation               | [README](../README.md)                                    | [프로젝트 소개](i18n/ko/README.md)                             |
| Documentation index                             | [Index](README.md)                                        | [문서 목차](i18n/ko/INDEX.md)                                  |
| Development direction and TODO order            | [Development plan](development/DEVELOPMENT_PLAN.md)       | [개발 계획](i18n/ko/development/DEVELOPMENT_PLAN.md)           |
| Supported source syntax and limitations         | [Parser scope](reference/PARSER_SCOPE.md)                 | [파서 범위](i18n/ko/reference/PARSER_SCOPE.md)                 |
| Maintained source-only CLI demo                 | [Examples](guides/EXAMPLES.md)                            | [예제](i18n/ko/guides/EXAMPLES.md)                             |
| Offline proposal and expectation CLI preview    | [Proposal preview](guides/PROPOSAL_PREVIEW.md)            | [제안 미리보기](i18n/ko/guides/PROPOSAL_PREVIEW.md)            |
| Source-only proposal declaration comparison     | [Proposal check](guides/PROPOSAL_CHECK.md)                | [제안 선언 검사](i18n/ko/guides/PROPOSAL_CHECK.md)             |
| Integrated review and prose test draft          | [Review demo](guides/REVIEW_DEMO.md)                      | [통합 검토 시연](i18n/ko/guides/REVIEW_DEMO.md)                |
| Owned report policy and unit-test example       | [Owner policy](guides/OWNER_POLICY.md)                    | [소유 보고서 정책](i18n/ko/guides/OWNER_POLICY.md)             |
| Read-only owner-policy Codex review             | [Codex owner review](guides/CODEX_OWNER_REVIEW.md)        | [소유 정책 Codex 검토](i18n/ko/guides/CODEX_OWNER_REVIEW.md)   |
| Offline owner-case review and fixed plans       | [Owner case plan](reference/OWNER_CASE_PLAN.md)           | [소유 사례 검토 계획](i18n/ko/reference/OWNER_CASE_PLAN.md)    |
| Source-only fixed owned-policy check API        | [Owner policy check](reference/OWNER_POLICY_CHECK.md)     | [고정 소유 정책 검사](i18n/ko/reference/OWNER_POLICY_CHECK.md) |
| Packaged offline fixture walkthrough            | [Fixture demo](guides/FIXTURE_DEMO.md)                    | [오프라인 fixture 시연](i18n/ko/guides/FIXTURE_DEMO.md)        |
| Opt-in owned-fixture Codex draft                | [Codex fixture](guides/CODEX_FIXTURE.md)                  | [Codex fixture](i18n/ko/guides/CODEX_FIXTURE.md)               |
| Separately approved fixed-fixture runtime check | [Runtime verification](guides/RUNTIME_VERIFICATION.md)    | [런타임 검증](i18n/ko/guides/RUNTIME_VERIFICATION.md)          |
| Replaceable models and measurable value         | [Model strategy](development/MODEL_STRATEGY.md)           | [모델 전략](i18n/ko/development/MODEL_STRATEGY.md)             |
| Versioned diagnostics and registration evidence | [Report contract](reference/REPORT_CONTRACT.md)           | [리포트 계약](i18n/ko/reference/REPORT_CONTRACT.md)            |
| Offline evidence-linked expected outcomes       | [Expectation contract](reference/EXPECTATION_CONTRACT.md) | [예상 결과 계약](i18n/ko/reference/EXPECTATION_CONTRACT.md)    |
| Contributions and commit conventions            | [Contributing](../CONTRIBUTING.md)                        | [기여 안내](i18n/ko/CONTRIBUTING.md)                           |
| Required checks and branch protection           | [Branch rules](development/BRANCH_RULES.md)               | [브랜치 규칙](i18n/ko/development/BRANCH_RULES.md)             |
| Guarded repository formatting                   | [Formatting](development/FORMATTING.md)                   | [포맷 검사](i18n/ko/development/FORMATTING.md)                 |
| Versions, binaries, and release checks          | [Releasing](releases/RELEASING.md)                        | [릴리스 가이드](i18n/ko/releases/RELEASING.md)                 |
| Released and unreleased changes                 | [Changelog](../CHANGELOG.md)                              | [변경 이력](i18n/ko/CHANGELOG.md)                              |
| Private reporting and safe-use policy           | [Security](../SECURITY.md)                                | [보안 정책](i18n/ko/SECURITY.md)                               |
| Repository threat model and review boundaries   | [Threat model](reference/threat-model.md)                 | [위협 모델](i18n/ko/reference/threat-model.md)                 |
| Pull request fields and checklist               | [PR template](../.github/pull_request_template.md)        | [PR 작성 안내](i18n/ko/PULL_REQUEST_TEMPLATE.md)               |

## Read the right version

The [offline proposal/decision contract](reference/PROPOSAL_CONTRACT.md), also available in
[Korean](i18n/ko/reference/PROPOSAL_CONTRACT.md), implements only #46's preview and simulated-decision
slice of #35. That pure contract does not apply files, call a provider or execute verification.

[#61's offline expectation manifest](reference/EXPECTATION_CONTRACT.md)
([한국어](i18n/ko/reference/EXPECTATION_CONTRACT.md)) is an unreleased source addition after alpha.3.
It binds caller-authored policy/declaration targets to an exact proposal and baseline evidence, always
as draft/not-run data. It generates or executes no tests and grants no approval or source execution.
[#63's proposal preview](guides/PROPOSAL_PREVIEW.md) ([한국어](i18n/ko/guides/PROPOSAL_PREVIEW.md))
adds an unreleased, read-only CLI view of a strict bundle on supported POSIX systems. It shows the
exact diff, linked evidence and expected outcomes without changing approval, execution or live-sharing scope.
[#69's source-only proposal check](guides/PROPOSAL_CHECK.md) ([한국어](i18n/ko/guides/PROPOSAL_CHECK.md))
compares declaration targets with a bounded subset of the same bundle's before/after source snapshots.
It leaves policy intent `not-evaluated`, runtime verification `not-run` and authorization `unknown`;
exit `0` means comparison processing completed, not that declarations matched or security passed.
[#71's integrated review demo](guides/REVIEW_DEMO.md) ([한국어](i18n/ko/guides/REVIEW_DEMO.md))
combines a fixed mock diff, declaration comparison and non-executable prose test draft in memory.
It requires no input files or POSIX reader, calls no provider and grants no application or execution.
[#73's owned report policy](guides/OWNER_POLICY.md) ([한국어](i18n/ko/guides/OWNER_POLICY.md)) is a
separate checkout example: developer tests execute only its pure policy function, while scanner tests
read the FastAPI source without importing it. It adds no authentication service or product runtime mode.
[#75's read-only Codex owner review](guides/CODEX_OWNER_REVIEW.md)
([한국어](i18n/ko/guides/CODEX_OWNER_REVIEW.md)) previews the exact packaged two-source input offline
on all supported OSes, then requires exact sharing consent for its POSIX provider path. Its review
and structured defensive cases remain unreviewed drafts, with execution not-run and authorization
unknown. One separately approved live run on 2026-10-01 returned a host-valid answer and ten cases;
no patch or target execution occurred, and alpha.3 is unchanged.
That provider result remains a draft/not-run record. The later exact-label review and separate
[#80 source observation](reference/OWNER_POLICY_CHECK.md) do not retroactively change it or
approve new model cases.
[#65's packaged offline walkthrough](guides/FIXTURE_DEMO.md) ([한국어](i18n/ko/guides/FIXTURE_DEMO.md))
adds the unreleased `fixture-demo` command on supported POSIX systems. It uses a mock draft and
separate copy-application, fixed AST-check and restoration choices, without Codex or fixture-source
execution. It accepts neither the preview bundle nor a runtime selector.

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
command; the evaluation scripts/corpus and original `scripts` demos still require a development checkout.
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
