<p align="center">
  <a href="../../../reference/THIRD_PARTY.md">English</a> ·
  <strong>한국어</strong>
</p>

# 참고 자료와 서드파티 소프트웨어

[문서 색인](../INDEX.md) · [MIT 라이선스](../../../../LICENSE)

AuthZest는 MIT 라이선스로 배포합니다. 2026-11-26에 점검한 결과, 저장소에는 다른 프로젝트에서 복사하거나 변형한
코드가 없습니다. 아래 오픈소스 패키지와 외부 도구를 사용하며, 각 구성 요소는 고유 라이선스를 따릅니다.
AuthZest의 MIT 표기가 그 조건을 대신하지 않습니다.

## 배포 형태별 포함 내용

| 배포 형태                     | 서드파티 구성 요소                                                                                                                                                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 소스 저장소와 소스 ZIP        | 서드파티 코드는 없습니다. 의존성은 `pyproject.toml`과 `frontend/package-lock.json`에 선언하고 따로 설치합니다.                                                                                                           |
| Python wheel                  | AuthZest 코드만 들어 있으며, 아래 의존성은 pip가 각 출처에서 설치합니다.                                                                                                                                                 |
| 독립 실행 파일(GitHub)        | CPython(PSF-2.0), PyInstaller 부트로더(실행 파일을 어떤 조건으로든 배포할 수 있게 하는 부트로더 예외가 붙은 GPL-2.0), 핵심 Python 의존성, React(MIT)가 포함된 프론트엔드 빌드 자산을 함께 담습니다. 서명하지 않았습니다. |
| A/B runtime 이미지(로컬 빌드) | 고정한 `python` Docker 기본 이미지와 체크섬을 확인한 wheel 14개로 사용자 컴퓨터에서 빌드하며, 배포하지 않습니다.                                                                                                         |

## Python 의존성

| 패키지                                                                           | 라이선스           | 사용처                   |
| -------------------------------------------------------------------------------- | ------------------ | ------------------------ |
| Typer, Rich, markdown-it-py, mdurl, annotated-doc                                | MIT                | CLI                      |
| Click                                                                            | BSD-3-Clause       | CLI                      |
| Pygments                                                                         | BSD-2-Clause       | CLI                      |
| shellingham                                                                      | ISC                | CLI                      |
| typing_extensions                                                                | PSF-2.0            | CLI, UI, A 이미지        |
| FastAPI, Pydantic, pydantic-core, AnyIO, h11, annotated-types, typing-inspection | MIT                | UI 추가 구성, A 이미지   |
| Starlette, Uvicorn, idna                                                         | BSD-3-Clause       | UI 추가 구성, A 이미지   |
| opentelemetry-api                                                                | Apache-2.0         | A 이미지(FastAPI 의존성) |
| httpx, pytest, pytest-cov, jsonschema, Ruff                                      | BSD-3-Clause / MIT | 개발·테스트 전용         |

A 이미지 wheel은 `runtime/generated_repair/images/locks/linux-arm64-A.txt`에 고정되어 있으며,
[runtime 준비](../guides/REPOSITORY_HTTP_FIX.md) 과정에서 각각 바이트와 해시를 확인합니다.
[HTTP 이미지 문서](REPOSITORY_HTTP_IMAGES.md)도 참고하세요.

## 프론트엔드 의존성

React와 React DOM(MIT)은 대시보드 자산에 컴파일되어 들어갑니다. 빌드·품질 도구인 Vite(MIT),
TypeScript(Apache-2.0), ESLint와 플러그인(MIT), Prettier(MIT)는 배포물에 포함하지 않습니다. Prettier에 묶인
matcher의 개발 도구 경고는 [#89](https://github.com/casing1/authzest/issues/89)와
[#171](https://github.com/casing1/authzest/issues/171)에서 추적합니다.

## 외부 도구와 서비스

- **Docker Desktop**으로 격리된 A/B 검사를 실행합니다. AuthZest는 이를 재배포하지 않으며 Docker의 라이선스
  조건을 따릅니다.
- **OpenAI Codex CLI**(Apache-2.0)는 사용자 자신의 ChatGPT 로그인으로 로컬 App Server를 통해 호출합니다.
  AuthZest에 포함하지 않으며, 모델 사용은 사용자 계정 약관을 따릅니다.
- `python` 기본 이미지는 Docker Hub에서 받으며 CPython(PSF-2.0)과 각 라이선스를 따르는 Debian 패키지를
  포함합니다.

## 참고 자료

- OWASP API Security Top 10 2023,
  [API1: Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/):
  `repo-fix`가 다루는 결함 유형입니다.
- MITRE [CWE-639: Authorization Bypass Through User-Controlled Key](https://cwe.mitre.org/data/definitions/639.html).
- 라우트·의존성·헤더 처리는 [FastAPI 문서](https://fastapi.tiangolo.com/)를 참고했습니다.
- 컨테이너 격리·네트워크·이미지 빌드는 [Docker 문서](https://docs.docker.com/)를 참고했습니다.
- 릴리스 기록은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)와
  [Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 따릅니다.
