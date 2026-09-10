<p align="center">
  <a href="../../../guides/EXAMPLES.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소스 전용 목록화 예제

[문서 목차](../INDEX.md) · [설치](../README.md)

직접 관리하는 예제에는 고정된 공개 샘플 데이터만 있습니다.
서버 시작, 애플리케이션 import, endpoint 접속이나 Codex 호출 없이 소스 탐색을 보여줍니다.
이 예제는 alpha.1 스캐폴딩이 아니라
[alpha.2 실행 파일](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2)과 대응 소스에서 검증했습니다.
fixture가 있는 checkout에서 실행하세요. 독립 실행 파일은 예제 디렉터리를 설치하지 않습니다.
정확한 릴리스 fixture는 [태그 소스 압축 파일](https://github.com/casing1/authzest/archive/refs/tags/v0.1.0-alpha.2.zip)에 있습니다.
아래 명령은 `authzest`가 PATH에 있다는 가정이며, 그렇지 않으면 내려받은 실행 파일의 절대 경로로 바꾸세요.
검증 근거와 한계는 [릴리스 기록](../releases/RELEASING.md)을 참고하세요.

## 라우트 등록 예제

[등록 예제](../../../../examples/fastapi_inventory/)는 파일 간 연결과 반복 router mount를 다룹니다.
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
정확한 예상 JSON은 [별도 저장](../../../../tests/fixtures/fastapi_inventory.json)하며,
[테스트](../../../../tests/test_examples.py)에서 비교할 때는 컴퓨터마다 다른 스캔 루트를 제외하고
라우트 파일의 경로 구분자를 POSIX 형식으로 정규화합니다.
현재 스키마는 1.2이며 이 fixture에는 지원하는 직접·상속 의존성 선언이 없으므로 세 route 모두
`dependencies: []`, `effective_dependencies: []`입니다. 인증이나 인가를 분류한 결과가 아닙니다.

개발 환경을 활성화한 뒤 다음 명령으로 예제를 검증합니다.

```bash
python -m pytest tests/test_examples.py
```

## 라우트 직접 의존성 예제

[의존성 예제](../../../../examples/fastapi_dependencies/)는 지원하는 선언 위치 세 가지를 보여줍니다.
alpha.2 CLI 또는 대응 소스 설치를 사용하여 저장소 루트에서 실행합니다.

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
[전달 계층 회귀 검사](../../../../tests/test_dependency_transports.py)는 소스 위치, core/CLI/API 공통 출력과
partial 리포트·strict 종료 1을 반환하는 별도 동적 scopes 사례를 검증합니다.
각 의존성 필드와 null/빈 목록 구분은 [리포트 계약](../reference/REPORT_CONTRACT.md)에 정의합니다.
이 예제에는 app/router/include 의존성을 선언하지 않았으므로 스키마 1.2의 적용 목록과 직접 목록이 같습니다.

## 상속 등록 예제

[상속 예제](../../../../examples/fastapi_inheritance/)는 router 하나를 두 app에 연결하고 첫 app에서
mount를 반복합니다. 저장소 루트에서 실행합니다.

```bash
authzest scan examples/fastapi_inheritance
authzest scan examples/fastapi_inheritance --json --strict
```

예상 결과는 **Python 파일 1개, GET 등록 3개, bounded 분석, 진단 없음, Codex 비활성**, 종료 코드 0입니다.
모든 등록이 원본 handler `main.py:36`과 직접 `Depends(route_context)`를 공유합니다. 적용 목록은 각각
app → include → router → 라우트 직접 맥락 순서의 선언 4개입니다.

| 경로          | App 생성자   | Include 호출 | 적용 대상 순서                                                              |
| ------------- | ------------ | ------------ | --------------------------------------------------------------------------- |
| `/items`      | `main.py:30` | `main.py:40` | `application_context`, `primary_mount`, `router_context`, `route_context`   |
| `/items`      | `main.py:31` | `main.py:41` | `alternate_context`, `secondary_mount`, `router_context`, `route_context`   |
| `/copy/items` | `main.py:30` | `main.py:42` | `application_context`, `secondary_mount`, `router_context`, `route_context` |

같은 `/items` 경로 두 개도 등록 ID와 app/include 근거로 구분합니다. JSON의 `dependencies`는 직접 선언
하나만 담고 `effective_dependencies`는 원본 호출 위치와 선언 종류를 유지한 항목 4개를 담습니다.
이는 소스 맥락 순서이며 런타임 실행 순서 보장이 아닙니다. 모든 샘플 의존성은 아무 작업도 하지 않는
일반 DI이며 인증·인가를 강제하지 않습니다. [상속 전달 계층 테스트](../../../../tests/test_inherited_dependency_transports.py)는
대상을 import하거나 실행하지 않고 fixture와 core/CLI/API 공통 출력을 검증합니다.

## 알려진 부분 분석 fixture

[부분 분석 fixture](../../../../examples/fastapi_partial/)는 의도적으로 리터럴이 아닌 decorator 의존성
목록을 사용합니다. 소스 전용이며 import하거나 실행하면 오류를 발생시키는 guard가 있으므로 모듈을 실행하지 마세요.

```bash
authzest scan examples/fastapi_partial --json
authzest scan examples/fastapi_partial --json --strict
```

예상 결과는 Python 파일 1개, `GET /partial` route 1개, `analysis_status: "partial"`과
`unsupported-dependency-list` 경고입니다. 직접 의존성 목록은 비어 있고 적용 목록은 인식한 app 선언 하나를
유지하며 동적 decorator 목록은 추측하지 않습니다. 첫 명령은 종료 0이고 두 번째 명령은 전체 리포트를
출력한 뒤 **의도대로 종료 1**을 반환합니다. 보안 finding이 아닌 분석 한계입니다.
[릴리스 smoke 스크립트](../../../../scripts/smoke_release.py)는 fixture 애플리케이션을 import하지 않고
네 예제를 사용해 소스와 패키징 출력이 같은지 확인합니다.

이것은 목록화 회귀 검사이지 접근통제 label을 갖춘 평가 집합이 아닙니다. 취약점 탐지 성능을 측정하거나
애플리케이션이 안전함을 증명하지 않습니다. 미지원 선언은 누락될 수 있으므로 [파서 범위](../reference/PARSER_SCOPE.md)를
확인하세요. AI나 보안 효과를 주장하기 전에 필요한 별도의 정책 fixture와 비교는
[모델 전략](../development/MODEL_STRATEGY.md)에 설명합니다.
