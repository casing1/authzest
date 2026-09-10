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

AuthZest는 FastAPI 애플리케이션의 소스 코드를 바탕으로 접근통제를 분석하기 위한 설치형 CLI 중심
오픈소스 프로젝트입니다. 현재 Python core는 대상 애플리케이션을 import하거나 실행하지 않고
라우트를 수집합니다. 핵심 제품 목표는 Codex 보조 검토와 방어적 테스트·패치 제안, 사용자 승인 또는
거절, 승인된 변경만 적용, 별도 승인한 격리 검증과 변경 기록입니다. 아직 구현되지 않은 계획이며,
정적 스캔은 계속 오프라인으로 동작하고 Codex 사용은 opt-in으로 제공할 예정입니다.

React 대시보드는 선택적인 로컬 인터페이스입니다. AuthZest를 사용하기 위해 웹사이트를 배포할 필요는
없습니다.

> [!IMPORTANT]
> 공개된 [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)는
> 첫 실행 가능한 스캐폴딩입니다. 아래의 라우트 소유 객체 인식, prefix 합성, 파일 간 라우터 연결과 리포트 계약은
> `main`에 구현되어 있지만 해당 실행 파일에는 **아직 릴리스되지 않았습니다**.
> 소스 패키지도 여전히 `0.1.0a1`을 표시하므로 checkout 커밋과 [변경 기록](CHANGELOG.ko.md)을 함께
> 확인해 공개 preview와 구분하세요. 어느 버전도 완성된 취약점 스캐너는 아닙니다.

## 현재 소스에서 지원하는 기능

- 정적으로 생성한 `FastAPI`·`APIRouter` 소유 객체와 지원하는 import 별칭 인식
- 문자열 리터럴 HTTP 라우트 탐색 및 지원 범위 내 라우터·등록 prefix 합성
- 저장소 내부 절대·상대 라우터 import 연결과 원본 파일·줄 위치 보존
- `scan` 명령으로 사람이 읽는 형식 또는 JSON 보고서 출력
- 기존 JSON 필드를 유지하며 스키마 `1.1`, 구조화된 진단, bounded/partial 상태와 원본 선언·app·
  `include_router` 근거를 포함한 구별되는 등록 ID 추가
- 라우트에 직접 선언된 `Depends`·`Security`, 소스 위치와 확인한 scopes 수집. 일반 의존성 주입을
  인증이나 인가로 판단하지 않음
- 선택적인 로컬 API·대시보드, 환경 진단, 독립 실행 파일 패키징

지원 데코레이터는 `get`, `post`, `put`, `patch`, `delete`, `options`, `head`입니다.
정적 분석의 지원 범위는 제한되어 있으며 미해석 route 선언은 생략될 수 있습니다.
지원 route의 의존성 근거가 미해석이면 진단과 함께 리포트에 유지합니다.
구조화된 진단은 일부 미해석 사례와 소스/읽기 오류를 다루며 모든 미지원 패턴을 포괄하지 않습니다.
빈 보고서나 `bounded` 상태가 endpoint의 부재나 접근통제의 안전성을 입증하지 않습니다.
[파서 지원 범위](PARSER_SCOPE.ko.md)와 [리포트 계약](REPORT_CONTRACT.ko.md)을 참고하세요.
상속 의존성 근거, 중첩 의존성 그래프, 인증·인가 분류와 보안 finding은 아직 구현되지 않았습니다.
구문상 의존성 참조를 찾았다는 사실만으로 그 동작을 입증하지 않습니다.

`scan`은 Codex adapter가 비활성화된 로컬 정적 분석을 사용합니다. Codex를 호출하지 않으며 API key나
ChatGPT 로그인이 필요하지 않습니다. 별도의 `doctor` 명령은 아래 설명처럼 설치된 Codex CLI를 호출할
수 있습니다.

## 소스에서 CLI 설치

먼저 Python 3.12 이상과 [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html)를 설치하세요.
개발 기준 버전은 Python 3.12입니다. 다음 명령은 PyPI
패키지가 아니라 현재 저장소 소스를 독립적인 pipx 환경에 설치합니다.

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
pipx install --python 3.12 .

authzest --help
authzest scan /path/to/fastapi-project
authzest scan /path/to/fastapi-project --json
authzest scan /path/to/fastapi-project --json --strict
```

`/path/to/fastapi-project`를 실제 프로젝트 디렉터리로 바꾸세요. 명령을 찾지 못하면 `pipx ensurepath`를
실행하고 새 터미널을 여세요. pipx로 설치한 CLI는 프로젝트 venv를 활성화하지 않아도 사용할 수 있습니다.
예시는 Python 3.12를 선택합니다. 지원되는 다른 인터프리터를 사용한다면 `--python` 뒤의 `3.12`를
해당 버전이나 실행 파일 경로로 바꾸세요.

기본 동작은 부분 분석이어도 리포트를 반환하면 종료 코드 0입니다. `--strict`를 추가하면 리포트를
출력하면서 확인한 부분 분석에 1을 반환합니다. 잘못된 저장소 입력에는 2를 반환합니다.
이 코드는 분석 실행 상태이며 보안 판정이 아닙니다.

소스 설치를 업데이트하려면 변경 사항이 없는 `authzest` checkout의 `main`에서 실행하세요.

```bash
git pull --ff-only
pipx install --force .
```

미리 빌드된 파일은 [독립 실행 파일](#독립-실행-파일)을 참고하세요. `ui` extra는 Python backend 의존성을
설치하지만 일반 wheel·pipx 설치에 빌드된 대시보드 자산을 포함하지 않습니다. 선택적인 대시보드는
아래의 editable 소스 환경을 사용하세요.

## 포함된 예제 실행

저장소 루트에서 현재 소스 설치본으로 함께 제공되는 로컬 fixture를 스캔하세요.

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
```

Python 파일 4개와 `GET` 라우트 3개(`/health`, `/v1/catalog/items`, `/v2/catalog/items`)가 나옵니다.
이 예제는 취약점 탐지가 아니라 정적 탐색과 같은 라우터의 반복 등록을 보여줍니다.
fixture 구성과 예상 근거는 [예제 안내](EXAMPLES.ko.md)를 참고하세요.

## CLI 진단

```bash
authzest --version
authzest doctor
authzest doctor --json
```

`doctor`는 Python 실행 환경을 확인합니다. PATH에서 `codex`를 찾으면 `codex --version`과
`codex login status`도 subprocess로 실행합니다. AI 스캔을 시작하거나 자격 증명 파일을 직접 읽지는
않습니다. Codex가 없거나 로그인하지 않은 경우 경고를 표시하지만 정적 스캔은 계속 사용할 수 있습니다.
로그인에 성공해도 AI 분석이 활성화되지는 않습니다. 해당 연동은 아직 구현되지 않았습니다.

## 개발 환경

복제한 저장소 루트에서 명령을 실행하세요. 예시는 macOS/Linux shell 기준입니다. Windows PowerShell에서는
`py -3.12 -m venv .venv`로 venv를 만들고 `.venv\Scripts\Activate.ps1`로 활성화합니다.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

editable 설치는 현재 checkout을 사용하며 `dev` extra에는 선택적인 backend 의존성도 포함됩니다.
Node.js/npm은 frontend 작업, 문서 검증, 대시보드를 포함하는 빌드에 필요합니다.
CI는 Node.js 22를 사용합니다.

## 선택적인 로컬 대시보드

editable 개발 환경을 준비한 뒤 저장소 루트에서 대시보드를 빌드하고 실행하세요.

```bash
npm --prefix frontend ci
npm --prefix frontend run build
authzest ui --workspace /path/to/fastapi-project --host 127.0.0.1 --port 8000
```

[http://127.0.0.1:8000](http://127.0.0.1:8000)을 여세요. editable backend는 checkout의
`frontend/dist`를 찾습니다. 빌드하지 않으면 `/`에는 대시보드 대신 API 안내가 표시됩니다.
대시보드는 미실행·빈 결과·부분 스캔을 구분하고 구조화된 진단과 parse-error 상세를 보여줍니다.
재스캔이 실패하면 이전 결과를 비웁니다. 이는 라우트 수집 상태이며 접근통제 판정이 아닙니다.

frontend를 개발할 때는 venv를 활성화한 터미널에서
`authzest ui --workspace /path/to/fastapi-project --reload`를 실행하고, 저장소 루트의 다른 터미널에서
`npm --prefix frontend run dev`를 실행하세요. [http://localhost:5173](http://localhost:5173)을 열면
Vite가 `/api`와 `/health`를 8000번 포트로 전달합니다.

로컬 서버는 `GET /health`, `GET /api/health`, `POST /api/scans`와 `/docs`의 API 문서를 제공합니다.
스캔 endpoint는 항상 서버 시작 시 선택한 workspace를 사용하며 요청 본문으로 다른 경로를 선택할 수
없습니다. CLI 직접 스캔은 로컬 사용자가 지정한 경로를 사용합니다. 선택적인 서버는 loopback 주소에서
실행하세요.

## 검증

개발 venv를 활성화한 상태에서 실행하세요.

```bash
python -m pytest
ruff check .
ruff format --check .
```

frontend를 변경했다면 다음도 실행하세요.

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

문서를 변경했다면 위와 같이 frontend 의존성을 설치한 뒤 저장소 루트에서 실행하세요.

```bash
node --test scripts/check_docs.test.mjs
node scripts/check_docs.mjs
git ls-files -z '*.md' | xargs -0 frontend/node_modules/.bin/prettier --check
```

검사기는 문서 예제를 실행하지 않고 번역 쌍, 로컬 링크, 명령어의 일치 여부를 확인합니다.
포맷 명령은 Git이 추적하는 Markdown을 검사하므로 새 안내 문서는 최종 확인 전에 staging에 포함하세요.

## 독립 실행 파일

[공개 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)는 Linux x64,
macOS arm64, Windows x64 실행 파일과 SHA-256 manifest를 제공합니다. 그래픽 설치 프로그램이 아닌
CLI 프로그램이며 `main`의 미출시 파서 변경 사항은 포함하지 않습니다. 아직 서명·notarization이 적용되지
않아 운영체제가 확인되지 않은 게시자 경고를 표시할 수 있습니다.

현재 소스를 로컬에서 빌드하려면 개발 venv를 활성화하고 저장소 루트에서 실행하세요.

```bash
python -m pip install -e '.[build]'
npm --prefix frontend ci
npm --prefix frontend run build
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest --help
```

Windows 결과물은 `dist\authzest.exe`입니다. PyInstaller 빌드는 `frontend/dist`가 있으면 포함합니다.
태그 검증, checksum, 배포 절차는 [릴리스 안내](RELEASING.ko.md)를 참고하세요.

## 프로젝트 구조

```text
src/authzest/
├── analyzer/   # 저장소 분석과 집계
├── parser/     # AST 라우트·import 해석
├── runner/     # 공유 스캔 실행 흐름
├── codex/      # Codex interface; 실제 연동 계획, scan adapter 비활성화
├── cli.py      # Typer 명령줄 인터페이스
├── api/        # 선택적 FastAPI 연결 계층
└── models.py   # core 보고서 데이터
tests/          # 회귀 테스트
frontend/       # 선택적 React/Vite/TypeScript 대시보드
docs/           # 안내, 번역, 자산
scripts/        # 릴리스 도구
.github/        # CI/릴리스 workflow와 기여 템플릿
```

CLI와 선택적인 API·UI는 같은 core를 사용합니다. core 분석은 웹 서버, React 또는 특정 AI provider에
의존하지 않아야 합니다.

## 로드맵과 기여

- [문서 색인](INDEX.ko.md) — 영어 안내와 한국어 번역
- [개발 체크리스트](DEVELOPMENT_PLAN.ko.md)와 [로드맵 issue #1](https://github.com/casing1/authzest/issues/1)
- [모델 및 평가 전략](MODEL_STRATEGY.ko.md)
- [기여 및 커밋 규칙](CONTRIBUTING.ko.md)

범위가 정해진 작업을 issue로 추적하고, 단기 브랜치에서 개발한 뒤 의미 있는 커밋과 검증을 담은 PR을
만들어 주세요. 보호된 `main`은 Python, frontend, CodeQL 검사를 요구합니다. 자유 주제 과목의 개발 계획은
7주로 잡고, 별도의 4–5주는 시험 기간·지연·최종 준비를 위한 여유로 남깁니다.
[#32](https://github.com/casing1/authzest/issues/32)의 리포트·근거 기반과
[#28](https://github.com/casing1/authzest/issues/28)의 라우트 직접 선언 근거는 현재 소스에 구현되어 있습니다.
다음 순서는 아래와 같습니다.

1. [#29: 상속된 의존성 근거](https://github.com/casing1/authzest/issues/29)
2. [#33: 근거를 연결한 오프라인 AI 계약·mock·평가](https://github.com/casing1/authzest/issues/33)
3. [#35: Codex 제안·정확한 diff 승인·승인된 패치 적용·격리 검증](https://github.com/casing1/authzest/issues/35)

이 기능들은 아직 구현되지 않았습니다. AI 지원이 결과를 개선하는지는 입증된 장점이 아니라 평가할
가설입니다. core는 provider나 특정 GPT 모델 없이도 유용해야 합니다.
최종 데모는 직접 소유·관리하는 fixture를 대상으로 하며 데이터 공유·패치·실행은 각각 별도로 허가받습니다.
취약점 악용 PoC 생성, 자율 공격 흐름과 임의 저장소 실행은 범위 밖입니다.

## 라이선스와 보안

AuthZest는 [MIT License](../../LICENSE)를 사용합니다. 취약점은 공개 issue가 아니라
[보안 정책](SECURITY.ko.md)의 비공개 절차를 통해 제보해 주세요.
