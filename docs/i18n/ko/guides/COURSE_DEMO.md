# 과제 시연과 검증 근거

[English](../../../guides/COURSE_DEMO.md) · [문서 목차](../INDEX.md) · [과제 제출 #85](https://github.com/casing1/authzest/issues/85)

시연에는 [`50706ff`](https://github.com/casing1/authzest/commit/50706ff28f0043497a04b411760e3b41b385b883)의 `0.1.0` 소스 후보를 사용합니다. 한 FastAPI 라우터가 두 경로에 등록되는 과정과 실행 전에 멈춘 워크플로를 대시보드가 어떻게 표시하는지 보여 줍니다. AI 수정 제안은 별도로 기록된 과거 실행을 인용합니다.

## 발표 전 준비

macOS 또는 Linux에서 Python 3.12와 Node.js 22.13 이상인 22.x 버전 또는 Node.js 24를 사용합니다. 발표 전에 한 번 설치합니다. 대시보드는 편집 가능 모드로 설치한 소스와 빌드한 프런트엔드를 사용합니다. macOS arm64, Python 3.12.7, Node.js 24.11.0에서 이 경로를 확인했습니다.

```bash
git clone https://github.com/casing1/authzest.git authzest-course
cd authzest-course
git switch --detach 50706ff28f0043497a04b411760e3b41b385b883
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci --ignore-scripts
npm --prefix frontend run build
.venv/bin/authzest --version
```

`authzest 0.1.0`이 표시되는지 확인합니다. 이후 명령도 같은 저장소 디렉터리에서 실행합니다.

## 1. 라우트가 등록되는 과정 보여 주기

```bash
.venv/bin/authzest scan examples/fastapi_inventory
.venv/bin/authzest scan examples/fastapi_inventory --json
```

`GET /health`, `GET /v1/catalog/items`, `GET /v2/catalog/items`를 짚어 봅니다. 두 카탈로그 경로는 `app/routers/catalog.py`의 같은 함수를 가리킵니다. `app/main.py`의 두 `include_router` 선언에서 서로 다른 접두사를 붙였기 때문입니다. AuthZest는 예제 모듈을 불러오지 않고 소스의 선언을 읽습니다. JSON 리포트는 스키마 `1.2`이며 `python_files: 4`, `route_count: 3`, `analysis_status: bounded`, `codex_status: disabled`를 표시합니다. 라우트 선언만으로 실제 배포 환경에서 누가 접근할 수 있는지 확정할 수는 없습니다.

## 2. 화면에 띄울 워크플로 결과 준비하기

다음 예제는 필수 런타임 프로필을 의도적으로 생략합니다. CLI는 모델에 자료를 보내거나 코드를 실행하기 전에 종료 코드 `2`를 반환합니다. 터미널에 출력되는 파일 경로를 브라우저에서 사용합니다.

```bash
(
  umask 077
  demo_dir=$(mktemp -d) || exit 1
  status_code=0
  .venv/bin/authzest codex-generate --model course-demo --file-workflow --json > "$demo_dir/refused.json" || status_code=$?
  if [ "$status_code" -ne 2 ]; then
    printf 'Expected exit 2, received %s\n' "$status_code" >&2
    exit 1
  fi
  printf '%s\n' "$demo_dir/refused.json"
)
```

워크플로 JSON은 스키마 `1.0`입니다. 상태는 `invalid-input`, 모델 호출 시도는 `application_turn_attempts: 0`이며 실행과 패치 적용은 모두 `not-run`입니다.

## 3. 로컬 대시보드 시연하기

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

터미널을 실행한 채 [로컬 대시보드](http://127.0.0.1:8000)를 엽니다.

1. **Static inventory → Analyze repository**를 선택해 CLI와 같은 세 라우트를 보여 줍니다. 한국어 화면에서는 **정적 선언 목록 → 저장소 분석**입니다.
2. **Workflow results**에서 `refused.json`을 골라 **Open result**를 누릅니다. 거절 상태와 비어 있는 before/after 관찰값을 보여 줍니다. 한국어 화면의 **워크플로 결과 → 결과 열기**는 최대 512 KiB의 워크플로 결과 JSON을 받습니다. 정적 스캔 결과는 별도 탭에서 확인합니다.
3. 언어를 **한국어**로 바꾸면 화면 문구가 바뀌고 기록된 상태값은 그대로 표시됩니다. 가져온 기록의 출처 표시는 `imported-unverified`입니다. 파일을 열면 새 실행 없이 기록에 담긴 내용을 읽을 수 있습니다.

발표가 끝나면 터미널에서 Ctrl-C로 서버를 종료합니다. [결과 화면 안내](RESULT_VIEWER.md)

## 인용할 검증 근거

| 주제              | 발표에서 설명할 근거                                                                                                                                                                                                                                                                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 후보 설치와 UI    | 새로 설치한 CLI와 공개 alpha.4 태그 소스에서 업그레이드한 환경이 각각 13개 검사를 통과했습니다. 소스 설치 대시보드로 스키마 1.0 거절 기록과 정적 목록을 확인했습니다. [후보 PR #180](https://github.com/casing1/authzest/pull/180)                                                                                                                                                               |
| 과거 AI 수정 제안 | `34baebc` 설치형 실행에서 모델이 테스트와 수정을 제안했습니다. 두 단계에서 독립 검사가 각 단계의 기대 결과와 일치했고 비공개 복사본을 복구했습니다. 발표에서는 과거 관찰로 인용합니다. 현재 후보의 새로운 전체 성공 기록은 미확인입니다. [당시 검증 근거](https://github.com/casing1/authzest/blob/c45462889fcbfa5b8354558336f6d4bd1540c27d/docs/i18n/ko/guides/COURSE_DEMO.md#인용할-검증-근거) |
| 네이티브 패키지   | Linux x64, macOS arm64, Windows x64에서 정적 스캔·오프라인 미리보기 검사를 각각 52개 통과했습니다. GitHub Actions 산출물은 후보 검증용으로 빌드했습니다. [체크섬과 검증 실행](https://github.com/casing1/authzest/issues/150#issuecomment-7000856136)                                                                                                                                            |
| 평가와 발행       | #84에서 AI 성능을 독립적으로 비교할 근거는 미확보 상태입니다. 개발 도구에 관한 판단은 `50706ff` 기준으로 기록했습니다. 이 시연을 검증할 당시 공개판은 alpha.4입니다. [평가 #84](https://github.com/casing1/authzest/issues/84) · [릴리스 체크리스트 #150](https://github.com/casing1/authzest/issues/150)                                                                                        |

과거 워크플로 기록을 보여 줄 권한이 있으면 로컬에서 열어 당시의 제안, diff, 복구 결과를 설명할 수 있습니다. 버전이 없는 이전 기록은 `legacy-unversioned`로 표시되며 원본 소스 근거가 들어 있지 않습니다. 원본 파일 없이도 공개된 과거 요약으로 발표할 수 있습니다. 공유 슬라이드에는 비공개 기록과 로컬 경로를 싣지 않습니다.
