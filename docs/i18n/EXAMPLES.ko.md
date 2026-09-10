<p align="center">
  <a href="../EXAMPLES.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소스 전용 목록화 예제

[문서 목차](INDEX.ko.md) · [설치](README.ko.md)

직접 관리하는 예제에는 고정된 공개 샘플 데이터만 있습니다.
서버 시작, 애플리케이션 import, endpoint 접속이나 Codex 호출 없이 소스 탐색을 보여줍니다.
이전 공개 alpha 바이너리가 아니라 최신 소스 checkout을 사용하세요.

## 라우트 등록 예제

[등록 예제](../../examples/fastapi_inventory/)는 파일 간 연결과 반복 router mount를 다룹니다.
프로젝트 README의 안내대로 CLI를 설치한 뒤 저장소 루트에서 실행합니다.

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
```

예상 목록: **Python 파일 4개, 라우트 3개, parse error 없음, Codex 비활성**.

| 메서드 | 경로              | 원본 선언                |
| ------ | ----------------- | ------------------------ |
| GET    | /health           | app/main.py:11           |
| GET    | /v1/catalog/items | app/routers/catalog.py:9 |
| GET    | /v2/catalog/items | app/routers/catalog.py:9 |

import한 router에는 자체 prefix가 있고 두 번 등록됩니다. 두 mount의 라우트는 같은 원본 handler 위치를
유지합니다. 이는 소스 위치이며 배포 URL이나 앱을 실행했다는 증거가 아닙니다.
정확한 예상 JSON은 [별도 저장](../../tests/fixtures/fastapi_inventory.json)하며,
[테스트](../../tests/test_examples.py)에서 비교할 때는 컴퓨터마다 다른 스캔 루트를 제외하고
라우트 파일의 경로 구분자를 POSIX 형식으로 정규화합니다.
현재 스키마는 1.1이며 이 fixture에는 지원하는 라우트 직접 의존성 선언이 없으므로 세 route 모두
`dependencies: []`입니다. 인증이나 인가를 분류한 결과가 아닙니다.

개발 환경을 활성화한 뒤 다음 명령으로 예제를 검증합니다.

```bash
python -m pytest tests/test_examples.py
```

## 라우트 직접 의존성 예제

[의존성 예제](../../examples/fastapi_dependencies/)는 지원하는 선언 위치 세 가지를 보여줍니다.
현재 소스 CLI를 설치한 뒤 저장소 루트에서 실행합니다.

```bash
authzest scan examples/fastapi_dependencies
authzest scan examples/fastapi_dependencies --json --strict
```

예상 결과는 **Python 파일 1개, GET 라우트 2개, bounded 분석, 진단 없음, Codex 비활성**, 종료 코드 0입니다.
`/health`의 의존성 목록은 비어 있고 `/items`는 소스 순서대로 다음 선언을 기록합니다.

| 종류       | 대상              | 선언 위치 종류         | 매개변수  | Scopes           |
| ---------- | ----------------- | ---------------------- | --------- | ---------------- |
| `Depends`  | `trace_request`   | `decorator`            | null      | null             |
| `Depends`  | `pagination`      | `parameter-annotation` | `page`    | null             |
| `Security` | `example_context` | `parameter-default`    | `context` | `["items:read"]` |

세 대상의 `resolution: "reference"`는 단순 이름 구문이며 callable의 동작을 입증하지 않습니다.
샘플 함수는 고정 데이터나 일반 의존성 주입 값을 반환하며 인증·인가를 강제하지 않습니다.
`Security` 선언과 scope 문자열도 보호를 보장하지 않습니다.
[전달 계층 회귀 검사](../../tests/test_dependency_transports.py)는 소스 위치, core/CLI/API 공통 출력과
partial 리포트·strict 종료 1을 반환하는 별도 동적 scopes 사례를 검증합니다.
각 의존성 필드와 null/빈 목록 구분은 [리포트 계약](REPORT_CONTRACT.ko.md)에 정의합니다.

이것은 목록화 회귀 검사이지 접근통제 label을 갖춘 평가 집합이 아닙니다. 취약점 탐지 성능을 측정하거나
애플리케이션이 안전함을 증명하지 않습니다. 미지원 선언은 누락될 수 있으므로 [파서 범위](PARSER_SCOPE.ko.md)를
확인하세요. AI나 보안 효과를 주장하기 전에 필요한 별도의 정책 fixture와 비교는
[모델 전략](MODEL_STRATEGY.ko.md)에 설명합니다.
