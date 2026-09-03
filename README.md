# AuthGuard (working title)

FastAPI 저장소의 소스를 읽어 접근통제 구조를 분석하고 보안 테스트를 보조하는 OSS
프로젝트의 초기 스캐폴드입니다. **AuthGuard는 가칭**이며, 공개 배포 전 패키지·프로젝트 이름의
충돌 여부를 확인해야 합니다.

현재 단계는 설치 가능한 CLI의 작은 수직 슬라이스에 집중합니다.

- Python AST 기반 FastAPI 라우트 탐색
- Typer CLI (`authguard scan`, `authguard doctor`)
- pipx 설치 및 PyInstaller 독립 실행 파일
- 선택 기능인 FastAPI + React 로컬 대시보드 (`authguard ui`)
- 향후 Codex CLI 또는 App Server를 연결할 수 있는 adapter 경계

Codex 연동은 아직 비활성입니다. 현재 구현은 API 키나 ChatGPT 로그인을 요구하지 않으며,
`src/authguard/codex/`의 인터페이스 뒤에 실제 adapter를 추가하도록 설계했습니다. 공식
[Codex App Server 문서](https://learn.chatgpt.com/docs/app-server)에 따르면 App Server는 인증,
대화 기록, 승인과 스트리밍 이벤트가 필요한 제품 내 통합에 적합합니다.

## 권장 설치: pipx

Python 3.12 이상과 pipx가 설치되어 있다면 저장소 루트에서 설치합니다. 설치 후에는 가상환경을
직접 활성화하지 않아도 어느 디렉터리에서든 `authguard`를 실행할 수 있습니다.

```bash
pipx install .
authguard --version
authguard doctor
authguard scan /path/to/fastapi-project
```

개발 중인 코드를 다시 설치할 때는 `pipx install . --force`를 사용합니다. 선택적인 로컬
대시보드까지 pipx 환경에 포함하려면 `pipx install '.[ui]'`를 사용합니다.

## 개발 환경

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

authguard --help
authguard doctor
authguard scan .
```

## 독립 실행 파일

Python이나 npm이 없는 사용자에게는 GitHub Releases의 운영체제별 단일 실행 파일을 제공합니다.
로컬에서 같은 파일을 만들려면 다음을 실행합니다.

```bash
source .venv/bin/activate
python -m pip install -e '.[build]'
cd frontend && npm ci && npm run build && cd ..
python -m PyInstaller --clean --noconfirm authguard.spec
./dist/authguard doctor
./dist/authguard scan /path/to/fastapi-project
```

Apple Silicon Mac에서 빌드 결과를 PATH에 설치하는 예시는 다음과 같습니다. 설치 대상에 같은 이름의
파일이 없는지 먼저 확인하세요.

```bash
install -m 755 dist/authguard /opt/homebrew/bin/authguard
authguard --version
authguard doctor
```

`v*` 태그를 push하면 GitHub Actions가 macOS, Linux, Windows 실행 파일과 SHA-256 checksum을
생성해 GitHub Release에 첨부합니다. Homebrew formula는 최종 저장소 주소와 공개 프로젝트명을
확정한 뒤 추가합니다.

## 선택 기능: 로컬 대시보드

외부 웹사이트 배포는 필요하지 않습니다. 프론트엔드를 빌드한 뒤 실행하면 FastAPI가
`127.0.0.1`에서 정적 대시보드를 제공합니다.

```bash
cd frontend
npm install
npm run build
cd ..

authguard ui
```

브라우저에서 `http://127.0.0.1:8000`을 여세요. 프론트엔드 개발 중에는 두 프로세스를
분리해서 실행할 수 있습니다.

```bash
# terminal 1
authguard ui --reload

# terminal 2
cd frontend
npm run dev
```

Vite 개발 서버는 `/api`와 `/health` 요청을 `http://127.0.0.1:8000`으로 전달합니다.

## 명령

```bash
authguard --help
authguard --version
authguard doctor
authguard scan <path>
authguard scan <path> --json
authguard ui --host 127.0.0.1 --port 8000
```

`doctor`는 실행 환경과 선택적인 Codex CLI 설치·로그인 상태를 확인합니다. Codex가 없거나 아직
로그인하지 않았어도 로컬 정적 분석은 실행됩니다. Codex CLI 로그인은 공식
[OpenAI 인증 문서](https://learn.chatgpt.com/docs/auth)의 `codex login` 흐름을 따릅니다.

`scan`은 현재 Python 파일 수와 FastAPI 스타일 라우트 데코레이터
(`get`, `post`, `put`, `patch`, `delete`, `options`, `head`)를 셉니다. 인증·인가 의미 분석과
테스트 생성은 후속 단계입니다.

## API

- `GET /health`: 백엔드 상태
- `GET /api/health`: 프론트엔드용 동일 상태
- `POST /api/scans`: `{ "path": "/absolute/or/relative/path" }` 저장소 스캔
- `GET /docs`: FastAPI가 생성한 API 문서

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

## 구조

```text
.
├── src/authguard/
│   ├── analyzer/        # 저장소 단위 분석과 집계
│   ├── parser/          # 언어/프레임워크 소스 파싱
│   ├── codex/           # AI adapter interface와 구현체
│   ├── runner/          # 분석 흐름 orchestration
│   ├── api/             # FastAPI transport
│   ├── cli.py           # Typer CLI transport
│   └── models.py        # core 데이터 모델
├── tests/
├── frontend/            # 선택적인 React/Vite/TypeScript UI
├── scripts/             # Release 파일명 및 checksum 생성
├── authguard.spec       # PyInstaller 단일 실행 파일 설정
└── .github/workflows/   # CI와 운영체제별 Release 빌드
```

의존 방향은 CLI/API/UI에서 core 쪽으로만 흐르게 유지합니다. core는 FastAPI 웹 서버나 React를
알지 못하고, Codex도 protocol을 통해서만 참조합니다.

## 라이선스와 보안

MIT 라이선스로 배포합니다. 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md), 취약점 제보
방법과 안전한 사용 범위는 [SECURITY.md](SECURITY.md)를 확인하세요.
