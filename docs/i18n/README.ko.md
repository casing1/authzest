<p align="center">
  <img src="../assets/authzest-banner.png" alt="AuthZest — 소스 인식형 접근통제 테스트" width="100%">
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <strong>한국어</strong> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ru.md">Русский</a>
</p>

# AuthZest

AuthZest는 FastAPI 프로젝트를 위한 오픈소스 소스 인식형 접근통제 보안 테스트 도구입니다.
저장소 구조와 라우트 선언을 분석하고, 이후 결정론적 규칙과 선택적 AI 분석에서 활용할 수 있는
근거를 생성합니다.

> [!IMPORTANT]
> AuthZest는 초기 개발 단계입니다. 버전 `0.1.0`은 실행 가능한 프로젝트 스캐폴딩이며 완성된
> 취약점 스캐너가 아닙니다. 접근통제 분류, 보안 finding, 능동 테스트와 Codex 기반 분석은 앞으로
> 구현할 기능입니다.

## 현재 동작하는 기능

- 일반적인 FastAPI 라우트 데코레이터의 Python AST 탐색
- Typer CLI 명령: `scan`, `doctor`, `ui`
- JSON 및 사람이 읽을 수 있는 스캔 요약
- FastAPI 상태 확인 및 저장소 스캔 endpoint
- localhost에서 실행되는 선택적 React/Vite 대시보드
- PyInstaller 기반 단일 실행 파일 패키징
- 분리된 `analyzer`, `parser`, `runner`, `codex` 모듈 경계
- GitHub Actions의 Python 및 frontend CI

Codex adapter는 현재 비활성화되어 있습니다. 로컬 분석에는 API key나 ChatGPT 로그인이 필요하지
않습니다.

## pipx로 설치

AuthZest는 Python 3.12 이상이 필요합니다.

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
pipx install .

authzest --version
authzest doctor
authzest scan /path/to/fastapi-project
```

선택적인 로컬 대시보드를 포함하려면 `pipx install '.[ui]'`를 사용합니다. 개발 중인 현재 코드를
다시 설치할 때는 `pipx install . --force`를 사용합니다.

## 개발 환경

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

cd frontend
npm ci
cd ..
```

## CLI

```bash
authzest --help
authzest --version
authzest doctor
authzest scan <path>
authzest scan <path> --json
authzest ui --host 127.0.0.1 --port 8000
```

`doctor`는 실행 환경과 선택적인 Codex CLI 설치 및 로그인 상태를 확인합니다. Codex를 사용할 수
없어도 정적 분석은 계속 동작합니다.

`scan`은 현재 Python 파일 수를 세고 `get`, `post`, `put`, `patch`, `delete`, `options`, `head`
FastAPI 스타일 라우트 데코레이터를 찾습니다. 아직 endpoint의 접근통제가 안전한지는 판단하지
않습니다.

## 선택 기능: 로컬 대시보드

대시보드는 로컬 소프트웨어이며 웹사이트 배포가 필요하지 않습니다.

```bash
cd frontend
npm ci
npm run build
cd ..

authzest ui
```

`http://127.0.0.1:8000`을 여세요. frontend 개발 중에는 `authzest ui --reload`와 `npm run dev`를
서로 다른 터미널에서 실행합니다. Vite는 `/api`와 `/health`를 로컬 FastAPI 서버로 전달합니다.

## 로컬 API

- `GET /health` — backend 상태
- `GET /api/health` — frontend용 동일 endpoint
- `POST /api/scans` — `{ "path": "/absolute/or/relative/path" }`로 저장소 스캔
- `GET /docs` — FastAPI가 생성한 API 문서

## 개발 검증

```bash
pytest
ruff check .
ruff format --check .

cd frontend
npm run lint
npm run format:check
npm run build
```

## 단일 실행 파일

```bash
source .venv/bin/activate
python -m pip install -e '.[build]'
cd frontend && npm ci && npm run build && cd ..
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest doctor
```

`v*` 태그를 push하면 macOS, Linux, Windows 실행 파일과 SHA-256 checksum을 만드는 release
workflow가 시작됩니다.

## 프로젝트 구조

```text
.
├── src/authzest/
│   ├── analyzer/        # 저장소 단위 분석과 집계
│   ├── parser/          # 언어 및 프레임워크 소스 파싱
│   ├── codex/           # 선택적 AI adapter interface와 구현체
│   ├── runner/          # 분석 흐름 orchestration
│   ├── api/             # FastAPI transport
│   ├── cli.py           # Typer CLI transport
│   └── models.py        # core 데이터 모델
├── tests/
├── frontend/            # 선택적인 React/Vite/TypeScript UI
├── docs/                # 개발 계획과 브랜드 자산
├── scripts/             # release 패키징 도구
├── authzest.spec        # PyInstaller 설정
└── .github/workflows/   # CI 및 release workflow
```

의존성은 CLI, API, UI에서 core 방향으로만 흐릅니다. core는 웹 서버, React 또는 특정 AI provider에
의존하지 않아야 합니다.

## 로드맵과 기여

- [개발 계획](../DEVELOPMENT_PLAN.md)
- [공개 로드맵 issue](https://github.com/casing1/authzest/issues/1)
- [기여 및 커밋 규칙](CONTRIBUTING.ko.md)

구현 전에 issue를 만들고 그 issue에 연결된 단기 브랜치를 사용해 주세요. Pull request는 병합 전
Python과 frontend 검사를 통과해야 합니다.

## 라이선스와 보안

AuthZest는 [MIT License](../../LICENSE)로 배포됩니다. 취약점은 공개 issue가 아니라
[한국어 보안 정책](SECURITY.ko.md)의 비공개 절차를 통해 제보해 주세요.
