<p align="center">
  <a href="../../README.md">English</a> ·
  <strong>한국어</strong>
</p>

# 문서 목차

AuthZest는 설치형·CLI 중심 FastAPI 소스 분석 프로젝트입니다. 설치는 프로젝트 README에서 시작하고,
스캔으로 무엇을 알 수 있는지와 알 수 없는지는 파서 범위를 확인하세요.
로컬 대시보드는 선택 사항이며 웹사이트 배포가 필요하지 않습니다.

## 문서와 지원 언어

영어가 원본 언어입니다. 저장소가 직접 관리하는 모든 Markdown 문서는 한국어를 지원하고,
프로젝트 README에는 [일본어](../ja/README.md)와 [러시아어](../ru/README.md)도 있습니다.
영어 상세 문서는 주제별로 묶고 번역은 언어 폴더 안에서 같은 구조를 사용합니다.
관례적인 영어 README·기여 안내·보안 정책·변경 이력은 저장소 루트에 유지합니다.

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

| 문서                           | English                                                   | 한국어                                       |
| ------------------------------ | --------------------------------------------------------- | -------------------------------------------- |
| 프로젝트 소개와 설치           | [README](../../../README.md)                              | [프로젝트 소개](README.md)                   |
| 문서 목차                      | [Index](../../README.md)                                  | [문서 목차](INDEX.md)                        |
| 개발 방향과 TODO 순서          | [Development plan](../../development/DEVELOPMENT_PLAN.md) | [개발 계획](development/DEVELOPMENT_PLAN.md) |
| 지원 소스 구문과 한계          | [Parser scope](../../reference/PARSER_SCOPE.md)           | [파서 범위](reference/PARSER_SCOPE.md)       |
| 유지하는 소스 전용 CLI 데모    | [Examples](../../guides/EXAMPLES.md)                      | [예제](guides/EXAMPLES.md)                   |
| opt-in 소유 fixture Codex 초안 | [Codex fixture](../../guides/CODEX_FIXTURE.md)            | [Codex fixture](guides/CODEX_FIXTURE.md)     |
| 교체 가능한 모델과 측정할 가치 | [Model strategy](../../development/MODEL_STRATEGY.md)     | [모델 전략](development/MODEL_STRATEGY.md)   |
| 버전이 있는 진단과 등록 근거   | [Report contract](../../reference/REPORT_CONTRACT.md)     | [리포트 계약](reference/REPORT_CONTRACT.md)  |
| 기여와 커밋 규칙               | [Contributing](../../../CONTRIBUTING.md)                  | [기여 안내](CONTRIBUTING.md)                 |
| 필수 검사와 브랜치 보호        | [Branch rules](../../development/BRANCH_RULES.md)         | [브랜치 규칙](development/BRANCH_RULES.md)   |
| 버전·바이너리·릴리스 검사      | [Releasing](../../releases/RELEASING.md)                  | [릴리스 가이드](releases/RELEASING.md)       |
| 출시·미출시 변경               | [Changelog](../../../CHANGELOG.md)                        | [변경 이력](CHANGELOG.md)                    |
| 비공개 신고와 안전한 사용 정책 | [Security](../../../SECURITY.md)                          | [보안 정책](SECURITY.md)                     |
| PR 항목과 체크리스트           | [PR template](../../../.github/pull_request_template.md)  | [PR 작성 안내](PULL_REQUEST_TEMPLATE.md)     |

## 올바른 버전의 문서 읽기

[오프라인 제안/결정 계약](reference/PROPOSAL_CONTRACT.md)과
[영어 안내](../../reference/PROPOSAL_CONTRACT.md)는 #35 중 #46의 미리보기·모의 결정 단계만 구현합니다.
해당 순수 계약 자체는 파일 적용·제공자 호출·검증 실행을 하지 않습니다.

후속 [소유 fixture 적용 데모](guides/FIXTURE_APPLICATION.md)
([English](../../guides/FIXTURE_APPLICATION.md))는 #48의 터미널 승인·복구를 새 POSIX 복사본에만
추가합니다. 기존 checkout은 편집하지 않으며 고정 응답을 쓰는 오프라인 데모를 유지합니다.

[#50 Codex fixture 명령](guides/CODEX_FIXTURE.md)([English](../../guides/CODEX_FIXTURE.md))은
opt-in 버전 고정 App Server 초안과 별도의 복사본 적용 결정을 추가합니다. 한 소유 fixture의 실제
초안·적용·복구 확인 1회가 성공했으며 승인 문구는 사용자 허가 아래 assistant가 입력했습니다.
독립적인 사람 검토는 아닙니다. #52는 별도 승인하는 선택적 자식 프로세스 검사로 적용된 fixture의
소스 해시를 고정한 fixture의 AST 설정만 확인하며 런타임 동작이나 보안 수정 효과를 검증하지 않습니다.
런타임 검증과 일반 저장소 AI는 미구현이며 완전한 #35 흐름은 미완료입니다. alpha.2 바이너리는 그대로입니다.

소스 checkout에 [오프라인 AI 계약과 평가](reference/AI_CONTRACT.md)를 구현했으며
[영어 안내](../../reference/AI_CONTRACT.md)도 있습니다. 실제 연동이나 alpha.2의 일부는 아닙니다.

[v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2)는 2026-09-10에 패키지
버전 `0.1.0a2`, 스키마 `1.2`로 발행됐습니다. 실행 파일에는 라우트 소유 객체 인식, 리터럴 router 구성,
저장소 내부 import와 직접·상속 의존성 근거가 포함됩니다. alpha.1 스캐폴딩에는 이 개선이 없습니다.
정확한 커밋, 세 플랫폼 산출물과 검증의 한계는 [릴리스 기록](releases/RELEASING.md)을 참고하세요.
`--version`뿐 아니라 변경 이력과 커밋/태그도 비교하세요. `main`은 배포된 소스 이후로 변경될 수 있습니다.
[#33](https://github.com/casing1/authzest/issues/33)의 오프라인 기반은 소스에 구현됐으며 다음 개발은 [#35](https://github.com/casing1/authzest/issues/35)입니다.

현재 스캔은 스키마 1.2, 구조화된 진단, 구별되는 소스 등록 근거와 라우트 직접·상속 의존성 선언을 제공합니다.
endpoint의 안전한 인가 여부 분류,
AI/능동 테스트는 하지 않습니다. 미해석 소스 패턴은 누락될 수 있으므로 빈 리포트나 성공 종료가
보안 보장은 아닙니다. [리포트 계약](reference/REPORT_CONTRACT.md)은 bounded/partial 상태와 opt-in strict 종료를
정의합니다. [개발 계획](development/DEVELOPMENT_PLAN.md)은 계획한 기능과 현재 구현을 구분합니다.

## 문서 갱신 규칙

- 영어 원본과 필수 번역을 같은 PR에서 갱신하고 언어별 명령·버전·완료 상태·한계를 동일하게 유지합니다.
- 저장소 상대 링크를 사용하고 번역 파일이 실제 위치한 디렉터리에서 확인합니다. PR 템플릿은 본문으로
  복사되므로 해당 링크에 안정적인 저장소 URL을 사용할 수 있습니다.
- 문서를 추가·이동·이름 변경하면 이 목차도 맞춥니다. 한국어 목차는 프로젝트 README 번역과
  충돌하지 않도록 `i18n/ko/INDEX.md`를 사용합니다.
- `.github/`를 포함한 추적 중인 프로젝트 Markdown이 점검 대상입니다. 의존성/vendor 문서,
  생성된 빌드 파일과 동기화된 외부 참조는 번역 작업에서 수정하지 않습니다.
- [MIT 라이선스](../../../LICENSE) 원문을 보존합니다. `LICENSE`는 Markdown 안내 문서가 아니며
  비공식 번역으로 교체하지 않습니다.

실시간 이슈 현황은 [roadmap #1](https://github.com/casing1/authzest/issues/1), 순서의 근거는 개발
계획에서 확인하세요. 문서 수정만으로 브랜치 설정이 바뀌거나 adapter가 활성화되거나 취약점이
해결되거나 릴리스가 배포되는 것은 아닙니다.
