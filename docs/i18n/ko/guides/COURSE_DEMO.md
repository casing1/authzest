# 과제 시연과 검증 근거

[English](../../../guides/COURSE_DEMO.md) · [문서 목차](../INDEX.md) · [과제 제출 #85](https://github.com/casing1/authzest/issues/85)

로컬 AI 작업 공간에서 관리하는 소유자의 보관 노트 사례를 시연합니다. 새 회귀 테스트와 규칙 변경을
검토하고 before/after 관찰과 복구 상태를 확인합니다. GUI와 CLI는 같은 owner-read 엔진과 개별 현재
결정을 사용합니다. 시연 동안 같은 checkout을 사용하고 다른 실행을 시작하기 전에 결과를 내려받습니다.

이 안내는 현재 소스 기능을 설명합니다. 소스 패키지 버전 `0.1.0`은 과제용 정식판 준비 상태이며 최신
공개판은 [alpha.4](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.4)입니다. 공개된 구현과
모의 검사만으로 새 설치 후보의 수용이 성립하지는 않습니다. 아래 과거 근거는 기록한 소스와 출처에
묶어서 설명합니다.

## 현재 소유자 조회 시연

### 소스 설치 준비

활성 AI 기능에는 동결 바이너리가 아닌 POSIX의 편집 가능 소스 checkout, Python 3.12, UI extra와
빌드한 프런트엔드 자산이 필요합니다. Node.js 22.13 이상인 22.x 또는 Node.js 24를 사용합니다.
Wheel과 독립 스캔/미리보기 바이너리는 완전한 활성 GUI 설치판이 아닙니다. 저장소 루트에서 실행합니다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest scan examples/fastapi_inventory
```

목록 예제에는 Python 파일 4개와 라우트 등록 3개가 있습니다. 정적 소스 근거를 보여 주는 예제입니다.
GUI의 workspace는 정적 스캔 기준 경로만 정하며 AI로 수정할 임의 저장소를 선택하지 않습니다.
AI 흐름은 패키지에 포함된 합성 보관 노트 소스와 정책을 사용합니다.

[소유자 조회 워크플로 계약](../development/GENERATED_REPAIR_CONTRACT.md#승인형-복사본-흐름-실행)에
따라 로컬 Docker 이미지와 비공개 런타임 설정을 준비하고 검토합니다. 검토한 Docker 런타임을 켜 둡니다.
기존 Codex ChatGPT 로그인을 사용하며 API 키 입력이나 새 OAuth 로그인 화면은 제공하지 않습니다.
현재 어댑터는 신뢰하는 Codex CLI `0.153.0`을 요구합니다.
런타임·소스 공유·실행은 각각 현재 계획과 결정이 필요합니다.

### 활성 GUI 열기

아래 자리표시자를 검토한 비공개 런타임 설정의 절대 경로로 바꿉니다. 기본 주소는 숫자 loopback
`127.0.0.1:8000`이며 이 모드는 단일 프로세스·reload 없음이 필요합니다.

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory --ai-runtime-config /ABSOLUTE/PRIVATE/runtime.json
```

**터미널에 출력된 비공개 AI 작업 공간 URL 전체를 새 브라우저 탭에서 엽니다.** `authzest-ai`
fragment에는 새 접속 권한이 담기며 화면이 이를 제거하고 메모리에만 유지합니다. URL은 비공개로
보관하고 녹화에서 제외합니다. 일반 대시보드 URL만으로는 활성 기능을 사용할 수 없습니다.
새로고침했다면 전체 실행 URL로 다시 열고, 서버를 재시작하면 다른 접속 권한을 사용합니다.
Vite 개발 프록시 대신 빌드한 같은 출처 대시보드를 사용합니다.

### 결정과 결과 시연

1. **AI 수정**에서 필요하면 기존 로그인·CLI 호환성을 확인하고 검토한 정확한 모델 식별자를 입력해
   실행을 준비합니다. 간략한 로그인 상태가 모델 접근 권한을 입증하지는 않습니다.
2. 전체 현재 런타임 계획과 별도의 소스 공유 미리보기를 검토합니다. 실행 준비만으로 두 단계를
   승인하지 않습니다.
3. 표시된 정확한 문구를 다음 순서로 검토·입력합니다.
   `runtime → share → copy → before → diff → apply → after → restore`. 각 결정은 새로 만들어진
   1회용이며 원래 최대 300초 안에 만료됩니다. 미리 승인하거나 이전 결정을 재사용할 수 없습니다.
   현재 계획을 수용할 수 없으면 해당 단계를 거절합니다.
4. 소스와 선언한 정책, 모델이 작성한 회귀 테스트와 수정안, 호스트가 계산한 정확한 소스·테스트 diff를
   보여 줍니다. 제한된 호스트 활동을 설명하며 원본 Codex 로그나 모델 토큰 스트림과 구분합니다.
5. 아래 표에 따라 기록된 검사와 복구를 비교합니다. 호스트 작업 종료만으로 수정 성공을 판단하지 않고
   의미상 결과, 적용 상태, 정리와 복구를 확인합니다.
6. **결과 JSON 다운로드** 후 브라우저 다운로드 목록에서 파일을 찾거나 브라우저 다운로드 설정으로
   찾기 쉬운 비공개 폴더를 선택합니다. 새 실행으로 결과가 교체되거나 서버를 닫기 전에 저장합니다.
   API는 서버 저장 경로를 받지 않습니다.

| 단계   | 소유자의 보관 노트 | 생성 회귀 테스트       | 의도한 정책 일치 |
| ------ | ------------------ | ---------------------- | ---------------- |
| Before | HTTP 403           | 단언 실패, 종료 코드 1 | 6/7              |
| After  | HTTP 200           | 통과, 종료 코드 0      | 7/7              |

관리하는 시나리오의 기대값이며 새 실행의 관찰값을 미리 채운 것이 아닙니다. 기준 프로필은 잘못된 거절을
기대한 baseline 응답으로 두므로 기대 프로필 일치는 두 단계 모두 7/7일 수 있습니다. 의도한 정책
일치는 6/7에서 7/7로의 수정을 보여 줍니다. after 열은 복구 전 복사본이므로 `restored-before`와
복구가 필요하지 않은 상태를 확인합니다. 불명·거절·미실행·실패·복구 필요 기록은 확보된 근거와 상태를
유지합니다.

`finished` 또는 `failed` 후에는 세션 반복 조회를 멈추며 실행 중·결정 대기·중단 처리 중에는 계속
갱신합니다. 새 활성 실행을 시작하면 갱신을 재개합니다. 브라우저를 닫아도 worker는 중단되지 않습니다.
중단은 협력적으로 처리하며 적용된 복사본에 복구가 필요할 수 있고 복구를 승인하지는 않습니다.
Core가 별도의 복구 계획을 제시하면 그 계획을 새로 검토·결정합니다. 현재 실행 링크로 메모리에 있는
현재 실행에 다시 연결할 수 있지만 결정의 만료 시간은 늘어나지 않습니다. 저장 결과 가져오기나 서버
재시작으로 결정을 재사용하거나 이전 파일 세션을 재개할 수 없습니다.

### 읽기 전용 표시와 CLI 대안

정적 스캔과 기존 결과 가져오기는 일반 읽기 전용 대시보드로 실행합니다.

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

열람할 권한이 있는 최종 JSON을 선택합니다. `owner-read-suggestion` 버전 1.0과 아래의 이전 생성
파일 형식을 최대 **512 KiB**까지 가져옵니다. 로컬 API의 `imported-unverified` 표시는 기록에 적힌
주장을 보여 준다는 뜻이며 참조된 런타임·복사본·로그 경로를 읽지 않습니다. 활성 GUI의 최종 다운로드는
최대 **4 MiB**이므로 모든 다운로드 결과를 다시 가져올 수 있는 것은 아닙니다. 전체 JSON과 원본 캡처는
비공개로 보관합니다. [결과 화면 안내](RESULT_VIEWER.md)

CLI도 같은 owner-read 엔진을 사용합니다. 먼저 전체 오프라인 미리보기를 검토합니다.

```bash
.venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --preview-only
```

범위를 검토한 뒤 아래 명령으로 대화형 흐름을 실행하고 최종 stdout JSON의 위치를 출력합니다.
모델과 런타임 경로는 검토한 값으로 바꿉니다. 런타임·공유와 파일 단계 6개의 계획·질문은 stderr를
사용하며 각각 현재 결정이 필요하므로 터미널을 열어 둡니다.

```bash
(
  umask 077
  demo_result_dir=$(mktemp -d) || exit 1
  demo_result_status=0
  .venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --json > "$demo_result_dir/owner-read-result.json" || demo_result_status=$?
  printf '%s\n' "$demo_result_dir/owner-read-result.json"
  exit "$demo_result_status"
)
```

### 근거와 발표 한계

[#190](https://github.com/casing1/authzest/pull/190)에서 선택형 GUI를 구현했고
[#192](https://github.com/casing1/authzest/pull/192)에서 종료 상태의 반복 조회를 중단했습니다.
두 PR의 오프라인·모의 검사는 UI 연결을 다루며 새 실제 모델/guest 관찰이나 정식판 수용을 뜻하지
않습니다. 발표할 권한이 있는 호출 근거만 해당 소스 리비전·출처·한계와 함께 사용합니다.
비공개 실행 URL, 계정 정보, 원본 로그나 로컬 결과/복사본 경로를 녹화에서 공개하지 않습니다.

공개한 관리형 테스트 예제 검증은 유지보수자가 작성한 제안과 실제 격리된 Linux guest 4개를
사용했습니다. 기대한 before 단언 실패를 관찰하고 정확한 변경을 새 복사본에만 적용했으며,
after 테스트 통과와 의도한 대조 7개 일치, 원래 소스 바이트 복구와 guest 4개 제거를 확인했습니다.
이 근거는 모델 생성 및 GUI 수용과 구별합니다. [관리형 테스트 예제 검증 #187](https://github.com/casing1/authzest/pull/187)

## 이전 alpha.4 시연 기록

아래 보관된 alpha.4 시연은 소스 커밋 [`c454628`](https://github.com/casing1/authzest/commit/c45462889fcbfa5b8354558336f6d4bd1540c27d)
(패키지 메타데이터 `0.1.0a4`)과 이전에 기록한 소유권 예제 실행 한 건을 사용합니다.
당시 기록한 제출 목표는 2026년 11월 18일 전후였습니다.

### 설치하고 대시보드 열기

macOS 또는 Linux에서 Python 3.12와 Node.js 22.13 이상인 22.x 또는 Node.js 24를 사용합니다.
기록된 설치를 재현하려면 표시한 리비전을 별도 디렉터리에 받습니다.

```bash
git clone https://github.com/casing1/authzest.git authzest-course
cd authzest-course
git switch --detach c45462889fcbfa5b8354558336f6d4bd1540c27d
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest scan examples/fastapi_inventory
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

[로컬 대시보드](http://127.0.0.1:8000)를 엽니다. 제공하는 목록 예제는 Python 파일 4개와
라우트 등록 3개를 표시합니다. 새 설치 시연은 macOS arm64, Python 3.12.7, Node.js 24.11.0에서
검증했습니다. Windows CI는 이식 가능한 CLI와 결과 계약을 검사합니다.
자산 빌드와 가져오기 형식은 [결과 화면 안내](RESULT_VIEWER.md)를 참고하세요.

### 기존 실행 기록 보여 주기

1. 정적 목록을 띄우고 소스의 선언을 보여 주는 화면이라고 설명합니다.
2. 열람할 권한이 있는 최종 CLI 결과 JSON을 엽니다. 이전 기록은 `legacy-unversioned`로 표시됩니다.
   해당 파일에는 가져올 수 있는 원본 소스와 선언이 없습니다.
3. 생성 테스트, 제안 diff, 기록된 결정, 두 대조 요약과 `restored-before`를 보여 줍니다.
   after 열은 복구하기 전에 검사했던 복사본의 관찰 결과입니다.
4. 아래 예제로 터미널과 결과 화면에서 입력 거절을 보여 줍니다. 실행·적용·복구 행에 관찰값이 없는
   이유를 설명합니다.

결과 화면은 사용자가 고른 최대 512 KiB JSON을 가져와 `imported-unverified`로 표시합니다.
저장된 기록을 열 때 모델이나 작업자를 호출하지 않습니다. 원본 결과 파일이 없으면 아래 집계 근거를
제시하고 거절 기록을 대화형 시연에 사용합니다. 원본 캡처와 계정·런타임·경로 정보는 비공개로
보관합니다.

이전 예제는 메모리 데이터와 시연용 행위자 헤더가 있는 관리형 FastAPI 소유권 사례 하나를 사용했습니다.
시연용 헤더는 사용자 인증을 제공하지 않습니다. 대조 검사는 그 정책과 관리하는 유한한 대조 항목을
다룹니다. 활성 실행 흐름에는 별도로 동결 바이너리가 아닌 POSIX 설치와 검토한 Linux 런타임 이미지가
필요합니다. [생성 파일 흐름](GENERATED_FILE_WORKFLOW.md)에서 지원 범위와 승인 단계를 설명합니다.

### 실행 전 입력 거절 보여 주기

아래 명령은 필수 런타임 프로필을 의도적으로 생략합니다. 모델 공유, 런타임 시작, workspace 변경 전에
종료 코드 `2`로 끝납니다. 출력된 경로의 파일을 결과 화면에서 엽니다.

```bash
(
  umask 077
  demo_dir=$(mktemp -d) || exit 1
  refusal_status=0
  .venv/bin/authzest codex-generate --model course-demo --file-workflow --json > "$demo_dir/refused.json" || refusal_status=$?
  if [ "$refusal_status" -ne 2 ]; then
    printf 'Expected refusal exit 2, received %s\n' "$refusal_status" >&2
    exit 1
  fi
  printf '%s\n' "$demo_dir/refused.json"
)
```

`invalid-input`, `not-run`, 어댑터 시도 0회와 before/after 관찰 없음이 표시됩니다.
이식성 CI는 로컬 회귀 테스트 예제로 만료된 결정과 변경된 바이트를 덮어쓰지 않는 동작도 검사합니다.
이 테스트 근거는 아래 실제 실행 관찰과 구분해 설명합니다.

### 인용할 검증 근거

| 범위                                                                                                                                                              | 관찰과 한계                                                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`34baebc`](https://github.com/casing1/authzest/commit/34baebc) 설치형 실행 기록, [#172 병합 `ad4dea7`](https://github.com/casing1/authzest/pull/172)과 같은 트리 | 실제 어댑터가 테스트와 소스 변경을 제안했습니다. 생성 테스트 종료 코드는 before 1, after 0이었습니다. 독립 대조는 각 단계의 기대 프로필에 대해 사례 17/17개와 요청 21/21개에 일치했습니다. 승인한 변경은 복사본에만 적용했고 복사본을 원래 바이트로 복구했습니다. 정리를 확인했고 checkout 바이트를 보존했습니다. |
| [`c454628` / #173](https://github.com/casing1/authzest/pull/173) 로컬 화면                                                                                        | 브라우저에서 이전 실제 기록을 열었고, 별도로 버전 1.0 거절도 표시했습니다. 버전 1.0 성공과 소스 필드는 테스트 예제로 검증했습니다. 이 리비전의 새로운 버전 1.0 실제 성공 기록은 없습니다.                                                                                                                         |
| [PR CI](https://github.com/casing1/authzest/actions/runs/44273783577)와 [병합 CI](https://github.com/casing1/authzest/actions/runs/44276437537)                   | 검토한 PR에서 Python 테스트 8,712개와 Windows 테스트 3,037개가 통과했고 Windows 테스트 422개를 건너뛰었습니다. 병합 후 [CodeQL 분석](https://github.com/casing1/authzest/actions/runs/44276438312)을 포함한 검사 작업이 통과했습니다.                                                                             |
| [독립 평가 #84](https://github.com/casing1/authzest/issues/84)                                                                                                    | 이 제출에서 인용할 독립 비교 근거는 확보되지 않았습니다. 기록한 단계는 한정된 흐름의 동작을 측정하며 접근제어 보장 여부는 불명입니다.                                                                                                                                                                             |

정식판 수용은 [#150](https://github.com/casing1/authzest/issues/150)에서 추적하며, 설치형 수용의 후속
작업은 [#151](https://github.com/casing1/authzest/issues/151)과 [#152](https://github.com/casing1/authzest/issues/152)에
남아 있습니다. 공개 alpha.4 산출물은 과거 릴리스 근거입니다. 후보별 도구 의존성에 관한
[#89](https://github.com/casing1/authzest/issues/89)와 [#171](https://github.com/casing1/authzest/issues/171)은
별도로 추적합니다.
