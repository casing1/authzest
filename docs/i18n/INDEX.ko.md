<p align="center">
  <a href="../README.md">English</a> ·
  <strong>한국어</strong>
</p>

# 문서 목차

AuthZest는 설치형·CLI 중심 FastAPI 소스 분석 프로젝트입니다. 설치는 프로젝트 README에서 시작하고,
스캔으로 무엇을 알 수 있는지와 알 수 없는지는 파서 범위를 확인하세요.
로컬 대시보드는 선택 사항이며 웹사이트 배포가 필요하지 않습니다.

## 문서와 지원 언어

영어가 원본 언어입니다. 저장소가 직접 관리하는 모든 Markdown 문서는 한국어를 지원하고,
프로젝트 README에는 [일본어](README.ja.md)와 [러시아어](README.ru.md)도 있습니다.
번역은 `docs/i18n/`에 모으고 저장소 루트에는 영어 프로젝트 README만 둡니다.

| 문서                           | English                                               | 한국어                                      |
| ------------------------------ | ----------------------------------------------------- | ------------------------------------------- |
| 프로젝트 소개와 설치           | [README](../../README.md)                             | [프로젝트 소개](README.ko.md)               |
| 문서 목차                      | [Index](../README.md)                                 | [문서 목차](INDEX.ko.md)                    |
| 개발 방향과 TODO 순서          | [Development plan](../DEVELOPMENT_PLAN.md)            | [개발 계획](DEVELOPMENT_PLAN.ko.md)         |
| 지원 소스 구문과 한계          | [Parser scope](../PARSER_SCOPE.md)                    | [파서 범위](PARSER_SCOPE.ko.md)             |
| 유지하는 소스 전용 CLI 데모    | [Examples](../EXAMPLES.md)                            | [예제](EXAMPLES.ko.md)                      |
| 교체 가능한 모델과 측정할 가치 | [Model strategy](../MODEL_STRATEGY.md)                | [모델 전략](MODEL_STRATEGY.ko.md)           |
| 버전이 있는 진단과 등록 근거   | [Report contract](../REPORT_CONTRACT.md)              | [리포트 계약](REPORT_CONTRACT.ko.md)        |
| 기여와 커밋 규칙               | [Contributing](../../CONTRIBUTING.md)                 | [기여 안내](CONTRIBUTING.ko.md)             |
| 필수 검사와 브랜치 보호        | [Branch rules](../BRANCH_RULES.md)                    | [브랜치 규칙](BRANCH_RULES.ko.md)           |
| 버전·바이너리·릴리스 검사      | [Releasing](../RELEASING.md)                          | [릴리스 가이드](RELEASING.ko.md)            |
| 출시·미출시 변경               | [Changelog](../../CHANGELOG.md)                       | [변경 이력](CHANGELOG.ko.md)                |
| 비공개 신고와 안전한 사용 정책 | [Security](../../SECURITY.md)                         | [보안 정책](SECURITY.ko.md)                 |
| PR 항목과 체크리스트           | [PR template](../../.github/pull_request_template.md) | [PR 작성 안내](PULL_REQUEST_TEMPLATE.ko.md) |

## 올바른 버전의 문서 읽기

최신 `main` 소스에는 라우트 소유 객체 인식, 리터럴 router 구성과 저장소 내부 router import가
포함됩니다. 이 개선은 **Unreleased**에 기록되어 있고 공개 `v0.1.0-alpha.1` preview 바이너리에는
포함되지 않습니다. 패키지 메타데이터는 릴리스 준비 변경 전까지 `0.1.0a1`이므로 `--version`뿐 아니라
변경 이력과 커밋/태그도 비교하세요.

현재 스캔은 스키마 1.1, 구조화된 진단, 구별되는 소스 등록 근거와 라우트 직접 의존성 선언을 제공합니다.
상속 의존성 전파, endpoint의 안전한 인가 여부 분류,
AI/능동 테스트는 하지 않습니다. 미해석 소스 패턴은 누락될 수 있으므로 빈 리포트나 성공 종료가
보안 보장은 아닙니다. [리포트 계약](REPORT_CONTRACT.ko.md)은 bounded/partial 상태와 opt-in strict 종료를
정의합니다. [개발 계획](DEVELOPMENT_PLAN.ko.md)은 계획한 기능과 현재 구현을 구분합니다.

## 문서 갱신 규칙

- 영어 원본과 필수 번역을 같은 PR에서 갱신하고 언어별 명령·버전·완료 상태·한계를 동일하게 유지합니다.
- 저장소 상대 링크를 사용하고 번역 파일이 실제 위치한 디렉터리에서 확인합니다. PR 템플릿은 본문으로
  복사되므로 해당 링크에 안정적인 저장소 URL을 사용할 수 있습니다.
- 문서를 추가·이동·이름 변경하면 이 목차도 맞춥니다. 한국어 목차는 프로젝트 README 번역과
  충돌하지 않도록 `INDEX.ko.md`라는 이름을 사용합니다.
- `.github/`를 포함한 추적 중인 프로젝트 Markdown이 점검 대상입니다. 의존성/vendor 문서,
  생성된 빌드 파일과 동기화된 외부 참조는 번역 작업에서 수정하지 않습니다.
- [MIT 라이선스](../../LICENSE) 원문을 보존합니다. `LICENSE`는 Markdown 안내 문서가 아니며
  비공식 번역으로 교체하지 않습니다.

실시간 이슈 현황은 [roadmap #1](https://github.com/casing1/authzest/issues/1), 순서의 근거는 개발
계획에서 확인하세요. 문서 수정만으로 브랜치 설정이 바뀌거나 adapter가 활성화되거나 취약점이
해결되거나 릴리스가 배포되는 것은 아닙니다.
