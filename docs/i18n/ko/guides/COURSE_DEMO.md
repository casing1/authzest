# 과제 시연과 검증 근거

[English](../../../guides/COURSE_DEMO.md) · [문서 목차](../INDEX.md) · [과제 제출 #85](https://github.com/casing1/authzest/issues/85)

현재 시연은 소유자의 보관 노트를 조회하는 합성 사례 흐름을 따릅니다. 저장한 CLI 결과를 로컬
대시보드에서 열고 제안한 변경, before/after 관찰과 복구 상태를 설명합니다. 시연 동안 같은
checkout과 저장한 결과를 사용합니다. 검토한 Docker 이미지, 비공개 런타임 설정과 개별 결정은
워크플로 계약에서 설명합니다. [워크플로 계약](../development/GENERATED_REPAIR_CONTRACT.md#승인형-복사본-흐름-실행)

## 현재 소유자 조회 시연

시연에 사용할 checkout에서 로컬 UI를 빌드하고 실행합니다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

Python 3.12와 Node.js 22.13 이상인 22.x 또는 Node.js 24를 사용합니다.
[로컬 대시보드](http://127.0.0.1:8000)를 엽니다. 제공하는 목록 예제에는 Python 파일 4개와
라우트 등록 3개가 있습니다. workspace는 정적 목록의 기준 경로를 정합니다. 워크플로 가져오기는
직접 선택한 결과 파일의 바이트를 사용합니다.

열람할 권한이 있는 기존 결과가 있으면 대시보드에서 최종 JSON을 선택합니다. 새 결과를 준비하려면
먼저 정확한 모델과 비공개 런타임 설정으로 전체 오프라인 미리보기를 검토합니다.

```bash
.venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --preview-only
```

범위를 검토한 뒤 아래 명령으로 대화형 흐름을 실행하고 최종 stdout JSON을 새 비공개 디렉터리에
저장합니다. 런타임·공유, 이어지는 복사본·before·정확한 diff·적용·after·복구 결정은 stderr를
사용합니다. 모델과 런타임 경로는 검토한 값으로 바꾸고, 결정을 입력할 터미널을 열어 둡니다.

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

가져온 결과에서 다음 항목을 보여 줍니다.

1. 제안 요약, 확보된 소스 근거, 생성 회귀 테스트와 정확한 소스·테스트 diff.
2. 파일 단계 6개의 결정과 소스 적용 상태.
3. Before의 HTTP 403, 회귀 단언 실패와 의도한 정책 일치 6/7.
4. After의 HTTP 200, 회귀 테스트 통과와 의도한 정책 일치 7/7.
5. 복구와 복구 필요 상태. after 열은 복구 전 복사본의 관찰을 기록합니다.

각 단계는 자체 기대 응답을 가지므로 기대 프로필 일치는 두 단계 모두 7/7일 수 있습니다.
의도한 정책 일치는 6/7에서 7/7로의 수정을 보여 줍니다. 불명·거절·미실행·실패·복구 필요 기록은
확보된 근거와 상태를 유지합니다.

공개한 관리형 테스트 예제 검증은 유지보수자가 작성한 제안과 실제 격리된 Linux guest 4개를
사용했습니다. 기대한 before 단언 실패를
관찰하고 정확한 변경을 새 복사본에만 적용했으며, after 테스트 통과와 의도한 대조 7개 일치를
확인했습니다. 원래 소스 바이트로 복구하고 guest 4개를 모두 제거했습니다. 제출에 사용하는 저장
결과에는 해당 호출의 출처와 한계가 함께 있어야 합니다. [관리형 테스트 예제 검증 #187](https://github.com/casing1/authzest/pull/187)

화면은 `owner-read-suggestion` 버전 1.0과 아래의 이전 생성 파일 형식을 지원합니다. 선택한 최대
512 KiB 파일을 로컬 API로 표시 자료로 바꾸고 `imported-unverified`로 표시합니다. 기록에 적힌
주장을 보여 주며 참조된 런타임·복사본·로그 경로는 읽지 않습니다. 전체 JSON과 원본 캡처는
비공개로 보관합니다. 소스 자료 유무, 생략하는 필드와 가져오기 제한은
[결과 화면 안내](RESULT_VIEWER.md)에서 설명합니다.

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
