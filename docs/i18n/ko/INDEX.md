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
├── reference/                # Parser scope, contracts, threat model
├── development/              # Plan, model strategy, branch rules
├── releases/                 # Release procedure
├── assets/                   # Shared images
└── i18n/
    ├── ko/                   # Korean root docs, INDEX.md, mirrored topics
    ├── ja/README.md          # Japanese project overview
    └── ru/README.md          # Russian project overview
```

| 문서                                   | English                                                         | 한국어                                               |
| -------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------- |
| 프로젝트 소개와 설치                   | [README](../../../README.md)                                    | [프로젝트 소개](README.md)                           |
| 문서 목차                              | [Index](../../README.md)                                        | [문서 목차](INDEX.md)                                |
| 개발 방향과 TODO 순서                  | [Development plan](../../development/DEVELOPMENT_PLAN.md)       | [개발 계획](development/DEVELOPMENT_PLAN.md)         |
| 지원 소스 구문과 한계                  | [Parser scope](../../reference/PARSER_SCOPE.md)                 | [파서 범위](reference/PARSER_SCOPE.md)               |
| 유지하는 소스 전용 CLI 데모            | [Examples](../../guides/EXAMPLES.md)                            | [예제](guides/EXAMPLES.md)                           |
| 오프라인 제안·예상 결과 CLI 미리보기   | [Proposal preview](../../guides/PROPOSAL_PREVIEW.md)            | [제안 미리보기](guides/PROPOSAL_PREVIEW.md)          |
| 소스 전용 제안 선언 비교               | [Proposal check](../../guides/PROPOSAL_CHECK.md)                | [제안 선언 검사](guides/PROPOSAL_CHECK.md)           |
| 통합 검토와 설명문 테스트 초안         | [Review demo](../../guides/REVIEW_DEMO.md)                      | [통합 검토 시연](guides/REVIEW_DEMO.md)              |
| 소유 보고서 정책과 단위 테스트 예제    | [Owner policy](../../guides/OWNER_POLICY.md)                    | [소유 보고서 정책](guides/OWNER_POLICY.md)           |
| 소유 정책의 읽기 전용 Codex 검토       | [Codex owner review](../../guides/CODEX_OWNER_REVIEW.md)        | [소유 정책 Codex 검토](guides/CODEX_OWNER_REVIEW.md) |
| 패키지에 포함한 오프라인 fixture 시연  | [Fixture demo](../../guides/FIXTURE_DEMO.md)                    | [오프라인 fixture 시연](guides/FIXTURE_DEMO.md)      |
| opt-in 소유 fixture Codex 초안         | [Codex fixture](../../guides/CODEX_FIXTURE.md)                  | [Codex fixture](guides/CODEX_FIXTURE.md)             |
| 별도 승인하는 고정 fixture 런타임 검사 | [Runtime verification](../../guides/RUNTIME_VERIFICATION.md)    | [런타임 검증](guides/RUNTIME_VERIFICATION.md)        |
| 교체 가능한 모델과 측정할 가치         | [Model strategy](../../development/MODEL_STRATEGY.md)           | [모델 전략](development/MODEL_STRATEGY.md)           |
| 버전이 있는 진단과 등록 근거           | [Report contract](../../reference/REPORT_CONTRACT.md)           | [리포트 계약](reference/REPORT_CONTRACT.md)          |
| 오프라인 근거 연결 예상 결과           | [Expectation contract](../../reference/EXPECTATION_CONTRACT.md) | [예상 결과 계약](reference/EXPECTATION_CONTRACT.md)  |
| 기여와 커밋 규칙                       | [Contributing](../../../CONTRIBUTING.md)                        | [기여 안내](CONTRIBUTING.md)                         |
| 필수 검사와 브랜치 보호                | [Branch rules](../../development/BRANCH_RULES.md)               | [브랜치 규칙](development/BRANCH_RULES.md)           |
| 버전·바이너리·릴리스 검사              | [Releasing](../../releases/RELEASING.md)                        | [릴리스 가이드](releases/RELEASING.md)               |
| 출시·미출시 변경                       | [Changelog](../../../CHANGELOG.md)                              | [변경 이력](CHANGELOG.md)                            |
| 비공개 신고와 안전한 사용 정책         | [Security](../../../SECURITY.md)                                | [보안 정책](SECURITY.md)                             |
| 저장소 위협 모델과 검토 경계           | [Threat model](../../reference/threat-model.md)                 | [위협 모델](reference/threat-model.md)               |
| PR 항목과 체크리스트                   | [PR template](../../../.github/pull_request_template.md)        | [PR 작성 안내](PULL_REQUEST_TEMPLATE.md)             |

## 올바른 버전의 문서 읽기

[오프라인 제안/결정 계약](reference/PROPOSAL_CONTRACT.md)과
[영어 안내](../../reference/PROPOSAL_CONTRACT.md)는 #35 중 #46의 미리보기·모의 결정 단계만 구현합니다.
해당 순수 계약 자체는 파일 적용·제공자 호출·검증 실행을 하지 않습니다.

[#61 오프라인 예상 결과 manifest](reference/EXPECTATION_CONTRACT.md)
([English](../../reference/EXPECTATION_CONTRACT.md))는 alpha.3 이후 소스에 추가한 미출시 기능입니다.
호출자가 작성한 정책·선언 목표를 정확한 제안과 기준 근거에 연결하며 항상 draft/not-run 데이터로
표시합니다. 테스트를 생성·실행하지 않고 승인이나 소스 실행 권한을 부여하지 않습니다.
[#63 제안 미리보기](guides/PROPOSAL_PREVIEW.md)([English](../../guides/PROPOSAL_PREVIEW.md))는
지원하는 POSIX 시스템에서 엄격한 bundle을 읽기 전용으로 표시하는 미출시 CLI 기능입니다.
정확한 diff·연결된 근거·예상 결과를 보여주며 승인·실행·실제 공유 범위는 바꾸지 않습니다.
[#69 소스 전용 제안 검사](guides/PROPOSAL_CHECK.md)([English](../../guides/PROPOSAL_CHECK.md))는
같은 bundle의 지원 범위 내 변경 전후 소스 snapshot을 선언 목표와 비교합니다.
정책 의도는 `not-evaluated`, 런타임 검증은 `not-run`, 인가는 `unknown`을 유지합니다.
종료 `0`은 비교 처리 완료이지 선언 일치나 보안 통과가 아닙니다.
[#71 통합 검토 시연](guides/REVIEW_DEMO.md)([English](../../guides/REVIEW_DEMO.md))은 메모리에서
고정 mock diff·선언 비교·실행 불가 설명문 테스트 초안을 함께 표시합니다. 입력 파일이나 POSIX
reader가 필요 없고 제공자를 호출하거나 적용·실행을 허가하지 않습니다.
[#73 소유 보고서 정책](guides/OWNER_POLICY.md)([English](../../guides/OWNER_POLICY.md))은 별도
checkout 예제입니다. 개발용 테스트는 순수 정책 함수만 실행하고 scanner 검사는 FastAPI 소스를
import 없이 읽습니다. 인증 서비스나 제품 런타임 모드를 추가하지 않습니다.
[#75 읽기 전용 Codex 소유 정책 검토](guides/CODEX_OWNER_REVIEW.md)
([English](../../guides/CODEX_OWNER_REVIEW.md))는 모든 지원 OS에서 패키지 내 두 소스의 정확한
입력을 오프라인으로 미리 보고, POSIX 제공자 경로에서 정확한 공유 동의를 요구합니다.
검토와 구조화된 방어적 사례는 미검토 초안, 실행은 not-run, 인가는 unknown을 유지합니다.
패치·대상 실행·새로운 실제 모델 인수 검증을 주장하지 않으며 alpha.3는 그대로입니다.
[#65 패키지 오프라인 시연](guides/FIXTURE_DEMO.md)([English](../../guides/FIXTURE_DEMO.md))은
지원하는 POSIX 시스템에 미출시 `fixture-demo` 명령을 추가합니다. mock 초안과 별도의 복사본
적용·고정 AST 검사·복구 결정을 사용하며 Codex나 fixture 소스를 실행하지 않습니다.
미리보기 bundle이나 런타임 선택 옵션은 받지 않습니다.

후속 [소유 fixture 적용 데모](guides/FIXTURE_APPLICATION.md)
([English](../../guides/FIXTURE_APPLICATION.md))는 #48의 터미널 승인·복구를 새 POSIX 복사본에만
추가합니다. 기존 checkout은 편집하지 않으며 고정 응답을 쓰는 오프라인 데모를 유지합니다.

[#50 Codex fixture 명령](guides/CODEX_FIXTURE.md)([English](../../guides/CODEX_FIXTURE.md))은
opt-in 버전 고정 App Server 초안과 별도의 복사본 적용 결정을 추가합니다. 한 소유 fixture의 실제
초안·적용·복구 확인 1회가 성공했으며 승인 문구는 사용자 허가 아래 assistant가 입력했습니다.
독립적인 사람 검토는 아닙니다. #52는 별도 승인하는 선택적 자식 프로세스 검사로 적용된 fixture의
소스 해시를 고정한 fixture의 AST 설정만 확인하며 런타임 동작이나 보안 수정 효과를 검증하지 않습니다.
#54는 `--runtime-check`로 [소유 fixture 런타임 계획](guides/RUNTIME_VERIFICATION.md)
([English](../../guides/RUNTIME_VERIFICATION.md))을 선택적으로 추가하며 정적 검사를 기본값으로 유지합니다.
선택 자체는 실행 승인이 아닙니다. 별도 결정 뒤 정확히 고정한 번들 fixture만 실행할 수 있고
의존성을 자동 설치하지 않습니다. #54의 제한된 실제 소스 환경 인수 검증과 별도의 alpha.3 발행 검사가
통과했습니다. 일반 저장소 AI와 완전한 #35 흐름은 미완료입니다.

소스 checkout에 [오프라인 AI 계약과 평가](reference/AI_CONTRACT.md)를 구현했으며
[영어 안내](../../reference/AI_CONTRACT.md)도 있습니다. 순수 계약은 alpha.3 fixture 명령에서도 사용하지만
평가 스크립트·데이터셋과 기존 `scripts` 데모에는 계속 개발 checkout이 필요합니다.
오프라인 평가는 모델을 호출하지 않습니다.

[v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3)는 2026-09-12에 패키지
버전 `0.1.0a3`, 바뀌지 않은 리포트 스키마 `1.2`로 커밋
`99be6f5614d283befa2a421b64f84958b680f92f`에서 발행했습니다. 지원하는 POSIX 시스템에 고정 fixture
초안·복사본·검사 흐름을 포함합니다. Windows는 스캔을 지원하고 fixture 적용·런타임 검증은 지원하지 않습니다.
공개 파일 6개를 모두 내려받아 검사한 태그 산출물과 대조했으며 공개 macOS 스캔·런타임 smoke도
Python `-I -S`의 표준 라이브러리 제어 프로그램으로 프로젝트 의존성을 import하지 않고 통과했습니다.
이 패키지 검사에서는 모델을 호출하지 않았습니다.

이전 [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2)는 2026-09-10에 패키지
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
