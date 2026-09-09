<p align="center">
  <a href="../../CHANGELOG.md">English</a> ·
  <strong>한국어</strong>
</p>

# 변경 이력

[문서 목차](INDEX.ko.md) · [릴리스 가이드](RELEASING.ko.md)

AuthZest의 주요 변경사항을 기록합니다.

[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 형식을 따르며 초기 개발 중에도 버전은
[Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 기준으로 합니다.

## [Unreleased]

이 항목은 공개 `v0.1.0-alpha.1` 태그 이후 `main`의 변경입니다. 현재 Python 패키지 메타데이터가
아직 `0.1.0a1`이어도 해당 preview 바이너리에는 포함되지 않습니다.

### 추가

- 대상 소스를 실행하지 않고 저장소 내부의 절대·상대 router import, 별칭과 모듈 참조를 해석하며
  cross-file 등록 경로와 원본 소스 위치를 보존합니다.
- 같은 파일의 리터럴 router 및 등록 prefix를 합성하고 반복 등록과 라우트 소스 위치를 보존하며
  미해석 경로를 생략합니다. [파서 범위](PARSER_SCOPE.ko.md)를 참고하세요.

### 변경

- 로드맵을 CLI 중심 근거/리포트 단계, 분리된 인증·인가 해석과 선택적 로컬 회귀 실행보다 앞선
  선택적 AI 설명 순서로 맞췄습니다.
- 프로젝트 README의 네 언어를 최신화하고 나머지 프로젝트 안내 문서와 PR 템플릿의 한국어판,
  영·한 문서 목차와 번역 유지관리 규칙을 추가했습니다.
- 소스 checkout 기능과 공개 preview 바이너리를 구분하고 선택적 대시보드 설치와 안전한 릴리스
  태그 절차를 명확히 했습니다.

### 수정

- 라우트 데코레이터 수집 전에 정적으로 인식한 FastAPI 또는 APIRouter 객체를 요구하여 무관한
  객체와 가려지거나 재할당된 이름을 제외합니다. [파서 범위](PARSER_SCOPE.ko.md)를 참고하세요.
- GitHub Release 게시 작업에 저장소 정보를 명시적으로 제공했습니다.
- 모든 빌드 플랫폼에서 checksum manifest를 이식 가능한 LF 줄바꿈으로 작성합니다.

## [0.1.0-alpha.1] - 2026-09-04

### 추가

- analyzer, parser, runner와 선택적 Codex adapter를 분리한 Python core 구조.
- 도움말·버전·진단·저장소 스캔·JSON 출력·로컬 대시보드용 Typer 명령.
- React/Vite/TypeScript 대시보드와 FastAPI health·scan endpoint.
- SHA-256 checksum을 포함한 cross-platform PyInstaller 빌드.
- CI, CodeQL, 기여 안내, 보안 정책과 다국어 프로젝트 안내.

### 보안

- HTTP scan endpoint의 대상을 로컬 프로세스 소유자가 선택한 workspace로 제한했습니다.
- HTTP API 계약에서 호출자가 지정하는 파일시스템 경로를 제거했습니다.

[Unreleased]: https://github.com/casing1/authzest/compare/v0.1.0-alpha.1...HEAD
[0.1.0-alpha.1]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1
