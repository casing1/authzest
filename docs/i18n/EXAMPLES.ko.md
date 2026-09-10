<p align="center">
  <a href="../EXAMPLES.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소스 전용 목록화 예제

[문서 목차](INDEX.ko.md) · [설치](README.ko.md)

직접 관리하는 [FastAPI 예제](../../examples/fastapi_inventory/)에는 고정된 공개 샘플 데이터만 있습니다.
서버 시작, 애플리케이션 import, endpoint 접속이나 Codex 호출 없이 소스 탐색을 보여줍니다.
이전 공개 alpha 바이너리가 아니라 최신 소스 checkout을 사용하세요.

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

개발 환경을 활성화한 뒤 다음 명령으로 예제를 검증합니다.

```bash
python -m pytest tests/test_examples.py
```

이것은 목록화 회귀 검사이지 접근통제 label을 갖춘 평가 집합이 아닙니다. 취약점 탐지 성능을 측정하거나
애플리케이션이 안전함을 증명하지 않습니다. 미지원 선언은 누락될 수 있으므로 [파서 범위](PARSER_SCOPE.ko.md)를
확인하세요. AI나 보안 효과를 주장하기 전에 필요한 별도의 정책 fixture와 비교는
[모델 전략](MODEL_STRATEGY.ko.md)에 설명합니다.
